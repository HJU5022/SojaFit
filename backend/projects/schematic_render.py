"""고정 커밋의 공개 회로 원본을 검증하고 모든 시트를 PNG로 변환한다."""
from __future__ import annotations

import io
import hashlib
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET

import httpx
from PIL import Image

from backend.graph.netlist import _sexpr
from backend.projects.external_circuit_search import canonical_product_query, is_non_circuit_asset
from backend.projects.schematic import (
    COMMAND_TIMEOUT_SECONDS, KicadServiceUnavailable, run_kicad_pdf,
)
from backend.projects.schematic_source import (
    ExternalSchematicInvalidSource, ExternalSchematicUpstreamError, VerifiedSchematicSource,
)

MIB = 1024 * 1024
MAX_IMAGE_BYTES = 10 * MIB
MIN_SCHEMATIC_IMAGE_DIMENSION = 128
MAX_PDF_BYTES = 20 * MIB
MAX_ARCHIVE_BYTES = 25 * MIB
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * MIB
MAX_TREE_ITEMS = 5000
MAX_SHEETS = 20
MAX_PIXELS = 40_000_000
MAX_PDF_TEXT_BYTES = 256 * 1024
PDF_DPI = 300
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MIME = {
    "png": {"image/png"}, "svg": {"image/svg+xml", "text/xml", "application/xml"},
    "pdf": {"application/pdf"}, "kicad": {"application/zip", "application/x-zip-compressed"},
}
SVG_ELEMENTS = set("svg g defs title desc metadata path rect line polyline polygon circle ellipse text tspan use clipPath linearGradient radialGradient stop".split())


def _invalid():
    return ExternalSchematicInvalidSource("전체 회로도 원본을 안전하게 변환할 수 없습니다.")


def _path(value: str) -> PurePosixPath:
    if (not value or any(ord(c) < 32 or c in '\\:"*?<>|' for c in value)
            or any(part in {"", ".", ".."} or part.endswith((" ", "."))
                   or PureWindowsPath(part).is_reserved() for part in value.split("/"))):
        raise _invalid()
    return PurePosixPath(value)


def _valid_png(data: bytes) -> bytes:
    if not data.startswith(PNG_MAGIC) or len(data) > MAX_IMAGE_BYTES:
        raise _invalid()
    with Image.open(io.BytesIO(data), formats=["PNG"]) as png:
        if png.width * png.height > MAX_PIXELS or png.n_frames != 1:
            raise _invalid()
        png.verify()
    with Image.open(io.BytesIO(data), formats=["PNG"]) as png:
        png.load()
    return data


def _svg_dimension(value: str) -> float:
    match = re.fullmatch(r"(\d*\.?\d+(?:[eE][+-]?\d+)?)(px|pt|mm|cm|in|pc)?", value.strip())
    if not match:
        raise _invalid()
    return float(match[1]) * {None: 1, "px": 1, "pt": 96 / 72, "mm": 96 / 25.4,
                              "cm": 96 / 2.54, "in": 96, "pc": 16}[match[2]]


def _svg(data: bytes) -> bytes:
    from cairosvg.surface import PNGSurface

    # UTF-8만 허용해 UTF-16 선언과 CSS escape로 인한 검사 우회를 막는다.
    xml = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?xml-stylesheet", xml, re.I) or "\x00" in xml:
        raise _invalid()
    root = ET.fromstring(xml)
    ns = "{http://www.w3.org/2000/svg}"
    if root.tag not in {"svg", ns + "svg"}:
        raise _invalid()
    for count, element in enumerate(root.iter(), start=1):
        if count > 50_000 or element.tag.removeprefix(ns) not in SVG_ELEMENTS:
            raise _invalid()
        for key, value in element.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or local in {"base", "src"}:
                raise _invalid()
            if local == "href" and not re.fullmatch(r"#[\w.-]+", value):
                raise _invalid()
            if any(char in value for char in ("\\", "@", "/*")):
                raise _invalid()
            without_fragments = re.sub(r"url\(\s*#[\w.-]+\s*\)", "", value, flags=re.I)
            if re.search(r"url\s*\(", without_fragments, re.I):
                raise _invalid()
    box = root.get("viewBox", "").replace(",", " ").split()
    width = _svg_dimension(root.attrib["width"]) if "width" in root.attrib else float(box[2])
    height = _svg_dimension(root.attrib["height"]) if "height" in root.attrib else float(box[3])
    if (not all(math.isfinite(n) and 0 < n <= MAX_PIXELS for n in (width, height))
            or math.ceil(width) * math.ceil(height) > MAX_PIXELS):
        raise _invalid()

    def deny_fetch(*args, **kwargs):
        raise _invalid()

    return PNGSurface.convert(bytestring=ET.tostring(root), url_fetcher=deny_fetch,
                              output_width=math.ceil(width), output_height=math.ceil(height))


def _pdf_creator_is_pcbnew(document) -> bool:
    metadata = document.get_metadata_dict()
    creator = metadata.get("Creator", "")
    return isinstance(creator, str) and creator.strip().casefold() == "pcbnew-pdf"


def _rasterize(kind: str, path: Path, output: Path, page_indices: str | None = None):
    """별도 프로세스에서 실행한다. 전체 변환 성공 후 부모가 결과를 읽는다."""
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_IMAGE_BYTES, MAX_IMAGE_BYTES))
    if kind != "pdf":
        data = path.read_bytes()
        (output / "01.png").write_bytes(_valid_png(_svg(data) if kind == "svg" else data))
        return
    import pypdfium2 as pdfium

    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise _invalid()
    document = pdfium.PdfDocument(path)
    try:
        if _pdf_creator_is_pcbnew(document):
            raise _invalid()
        if not 1 <= len(document) <= MAX_SHEETS:
            raise _invalid()
        selected = list(range(len(document)))
        if page_indices is not None:
            try:
                selected = [int(value) for value in page_indices.split(",")]
            except ValueError:
                raise _invalid() from None
            if not selected or len(selected) > MAX_SHEETS or any(index < 0 or index >= len(document) for index in selected):
                raise _invalid()
        for output_index, index in enumerate(selected):
            page = document[index]
            try:
                width, height = page.get_size()
                if not all(math.isfinite(n) and n > 0 for n in (width, height)):
                    raise _invalid()
                # PDFium reports page dimensions in points. Render at 300 DPI so
                # labels and pin numbers remain legible when the browser zooms in.
                # Large posters still obey the global pixel ceiling.
                scale = min(PDF_DPI / 72, math.sqrt(MAX_PIXELS / (width * height)))
                if math.ceil(width * scale) * math.ceil(height * scale) > MAX_PIXELS:
                    scale *= .99
                if math.ceil(width * scale) * math.ceil(height * scale) > MAX_PIXELS:
                    raise _invalid()
                bitmap = page.render(scale=scale)
                try:
                    out = output / f"{output_index + 1:02}.png"
                    bitmap.to_pil().save(out, format="PNG")
                    _valid_png(out.read_bytes())
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()


def _sheets(kind: str, path: Path, output: Path, *, pdf_pages: tuple[int, ...] | None = None) -> tuple[bytes, ...]:
    output.mkdir()
    if path.stat().st_size > (MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES):
        raise _invalid()
    try:
        command = [sys.executable, "-m", "backend.projects.schematic_render", kind, str(path), str(output)]
        if pdf_pages is not None:
            command.append(",".join(str(index) for index in pdf_pages))
        subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2], check=True, timeout=COMMAND_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ},
        )
    except subprocess.CalledProcessError:
        raise _invalid() from None
    except (subprocess.TimeoutExpired, OSError):
        raise ExternalSchematicUpstreamError("회로도 변환기를 사용할 수 없습니다.") from None
    sheets = sorted(output.glob("*.png"))
    if not 1 <= len(sheets) <= MAX_SHEETS or any(p.stat().st_size > MAX_IMAGE_BYTES for p in sheets):
        raise _invalid()
    return tuple(p.read_bytes() for p in sheets)


def _archive(source: VerifiedSchematicSource, data: bytes, dest: Path) -> tuple[Path, int]:
    prefix = source.repository.split("/")[1] + "-" + source.commit
    if (not data.startswith(b"PK\x03\x04") or len(data) > MAX_ARCHIVE_BYTES
            or data.count(b"PK\x01\x02") > MAX_TREE_ITEMS):
        raise _invalid()
    root = _path(source.root_schematic)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        items = archive.infolist()
        if len(items) > MAX_TREE_ITEMS or sum(i.file_size for i in items) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise _invalid()
        names = set()
        schematics = {}
        for item in items:
            name = item.orig_filename.removesuffix("/") if item.is_dir() else item.orig_filename
            path = _path(name)
            filetype = stat.S_IFMT(item.external_attr >> 16)
            if (path.parts[0] != prefix or name.casefold() in names or item.flag_bits & 1
                    or filetype not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}):
                raise _invalid()
            names.add(name.casefold())
            if not item.is_dir() and path.suffix == ".kicad_sch":
                schematics[path.relative_to(prefix)] = item

        # KiCad에는 검증한 계층의 회로 파일만 전달한다. 저장소 설정과 라이브러리
        # 테이블은 외부 파일 경로를 지정할 수 있어 임시 프로젝트에 복사하지 않는다.
        count = 0
        children = {}

        def visit(path, ancestors):
            nonlocal count
            count += 1
            if count > MAX_SHEETS or path in ancestors or path not in schematics:
                raise _invalid()
            if path not in children:
                item = schematics[path]
                if item.file_size > MAX_IMAGE_BYTES:
                    raise _invalid()
                raw = bytearray()
                with archive.open(item) as member:
                    while chunk := member.read(65536):
                        raw.extend(chunk)
                        if len(raw) > item.file_size:
                            raise _invalid()
                if len(raw) != item.file_size:
                    raise _invalid()
                tree = _sexpr(raw.decode("utf-8-sig"))
                if not tree or tree[0] != "kicad_sch":
                    raise _invalid()
                libraries = {lib[1] for node in tree if isinstance(node, list)
                             and node[:1] == ["lib_symbols"] for lib in node[1:]
                             if isinstance(lib, list) and lib[:1] == ["symbol"]
                             and len(lib) >= 2 and isinstance(lib[1], str)}
                for symbol in (n for n in tree if isinstance(n, list) and n[:1] == ["symbol"]):
                    ids = [n[1] for n in symbol if isinstance(n, list)
                           and n[:1] == ["lib_id"] and len(n) == 2]
                    aliases = [n[1] for n in symbol if isinstance(n, list)
                               and n[:1] == ["lib_name"] and len(n) == 2]
                    if (len(ids) != 1 or len(aliases) > 1
                            or (aliases or ids)[0] not in libraries):
                        raise _invalid()
                subs = []
                for sheet in (s for s in tree if isinstance(s, list) and s[:1] == ["sheet"]):
                    files = [p[2] for p in sheet if isinstance(p, list) and len(p) >= 3
                             and p[0] == "property" and str(p[1]).lower().replace(" ", "") == "sheetfile"]
                    if len(files) != 1 or not isinstance(files[0], str) or any(c in files[0] for c in "$%{}~"):
                        raise _invalid()
                    subs.append(path.parent / _path(files[0]))
                target = dest / path
                target.parent.mkdir(exist_ok=True, parents=True)
                target.write_bytes(raw)
                children[path] = subs
            for child in children[path]:
                visit(child, ancestors | {path})

        visit(root, set())
    return dest / root, count


def render_external_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None,
                              kicad_export: Callable = run_kicad_pdf) -> tuple[bytes, ...]:
    from backend.projects.schematic_discovery import download_bounded

    if (not re.fullmatch(r"[\w.-]+/[\w.-]+", source.repository, re.ASCII)
            or not re.fullmatch(r"[0-9a-f]{40}", source.commit)):
        raise _invalid()
    _path(source.repository)
    kind = source.asset_kind
    if kind not in MIME:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-render-") as temporary:
        work = Path(temporary)
        if kind == "kicad":
            host = "codeload.github.com"
            urls = [f"https://{host}/{source.repository}/zip/{source.commit}"]
        else:
            host = "raw.githubusercontent.com"
            if not 1 <= len(source.asset_paths) <= MAX_SHEETS:
                raise _invalid()
            urls = [f"https://{host}/{source.repository}/{source.commit}/{quote(str(_path(p)))}"
                    for p in source.asset_paths]
        result = []
        for index, url in enumerate(urls):
            limit = {"pdf": MAX_PDF_BYTES, "kicad": MAX_ARCHIVE_BYTES}.get(kind, MAX_IMAGE_BYTES)
            data, mime = download_bounded(url, max_bytes=limit, allowed_hosts=frozenset({host}), client=client)
            # GitHub raw에서는 PDF와 SVG에도 generic media type을 사용한다.
            generic = {"application/octet-stream"} | ({"text/plain"} if kind == "svg" else set())
            if len(data) > limit or mime not in MIME[kind] | generic:
                raise _invalid()
            if kind == "kicad":
                try:
                    root, count = _archive(source, data, work / "source")
                    output = work / "export"
                    output.mkdir()
                    _, pdf = kicad_export(root, output)
                    if not pdf.is_file():
                        raise _invalid()
                    sheets = _sheets("pdf", pdf, work / "pages")
                    if len(sheets) != count or count != source.expected_sheets:
                        raise _invalid()
                    return sheets
                except KicadServiceUnavailable:
                    raise ExternalSchematicUpstreamError("KiCad를 사용할 수 없습니다.") from None
                except (ValueError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    if isinstance(exc, ExternalSchematicUpstreamError):
                        raise
                    raise _invalid() from None
            path = work / f"asset-{index}"
            path.write_bytes(data)
            result.extend(_sheets(kind, path, work / f"pages-{index}"))
            if len(result) > MAX_SHEETS:
                raise _invalid()
        if len(result) != source.expected_sheets:
            raise _invalid()
        return tuple(result)


def _public_asset(url: str, kind: str, *, client: httpx.Client | None = None) -> tuple[bytes, str]:
    """Download one discovered public asset with the same SSRF and size guards."""
    from backend.projects.schematic_discovery import download_bounded

    if kind not in {"png", "svg", "pdf"} or not isinstance(url, str):
        raise _invalid()
    parsed = urlsplit(url)
    host = parsed.hostname
    if not host or parsed.scheme != "https":
        raise _invalid()
    limit = MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES
    data, mime = download_bounded(url, max_bytes=limit, allowed_hosts=frozenset({host}),
                                  client=client, phase="public_asset")
    generic = {"application/octet-stream"} | ({"text/plain"} if kind == "svg" else set())
    if mime not in MIME[kind] | generic:
        raise _invalid()
    return data, mime


def _pdf_schematic_pages(data: bytes) -> tuple[int, ...]:
    """Find pages explicitly labelled schematic, excluding a table of contents."""
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    try:
        count = len(document)
        if not 1 <= count <= MAX_SHEETS or _pdf_creator_is_pcbnew(document):
            raise _invalid()
        if count == 1:
            return (0,)
        selected = []
        for index in range(count):
            page = document[index]
            try:
                text = page.get_textpage().get_text_range().casefold()
                if "table of contents" not in text and re.search(r"\bschematic\b", text):
                    selected.append(index)
            finally:
                page.close()
        if not selected:
            raise _invalid()
        return tuple(selected)
    finally:
        document.close()


def _bounded_pdf_schematic_pages(data: bytes) -> tuple[int, ...]:
    """Inspect untrusted PDF bytes in the bounded worker process."""
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-pdf-inspect-") as temporary:
        path = Path(temporary) / "input.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.projects.schematic_render", "inspect-pdf", str(path)],
                cwd=Path(__file__).resolve().parents[2], check=True, timeout=COMMAND_TIMEOUT_SECONDS,
                capture_output=True, text=True,
                env={key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ},
            )
        except subprocess.CalledProcessError:
            raise _invalid() from None
        except (subprocess.TimeoutExpired, OSError):
            raise ExternalSchematicUpstreamError("회로도 변환기를 사용할 수 없습니다.") from None
    raw = result.stdout.strip()
    try:
        pages = tuple(int(value) for value in raw.split(",") if value != "")
    except ValueError:
        raise _invalid() from None
    if not pages or len(pages) > MAX_SHEETS or any(index < 0 for index in pages):
        raise _invalid()
    return pages


def _pdf_identity_text(data: bytes) -> str:
    """Extract a bounded amount of PDF text in the same worker boundary as page inspection."""
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-pdf-text-") as temporary:
        path = Path(temporary) / "input.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.projects.schematic_render", "inspect-pdf-text", str(path)],
                cwd=Path(__file__).resolve().parents[2], check=True, timeout=COMMAND_TIMEOUT_SECONDS,
                capture_output=True, text=True, encoding="utf-8",
                env={**{key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ},
                     "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.CalledProcessError:
            raise _invalid() from None
        except (subprocess.TimeoutExpired, OSError):
            raise ExternalSchematicUpstreamError("회로도 변환기를 사용할 수 없습니다.") from None
    return result.stdout[:MAX_PDF_TEXT_BYTES]


_IDENTITY_STOPWORDS = {
    "schematic", "schematics", "circuit", "diagram", "drawing", "original", "board",
    "development", "dev", "module", "electronics", "official", "pdf", "png",
    "svg", "and", "the", "for", "with", "회로도", "원본",
}
_ACCESSORY_MARKERS = {"clickshield", "add-onboard", "addonboard", "motorcarrier", "carriershield"}
_PARTIAL_MARKERS = {"reducedschematics", "reducedschematic", "partialschematic", "excerpt", "summary"}
_NON_SCHEMATIC_DOCUMENT_MARKERS = {"whitesheet", "datasheet", "productbrief", "productsheet", "flyer"}


def _identity_compact(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", value.casefold())


def _identity_terms(query: str) -> tuple[str, ...]:
    return tuple(
        _identity_compact(token) for token in re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*|[가-힣]+", query, re.I)
        if len(token) > 1 and token.casefold() not in _IDENTITY_STOPWORDS
    )


_VOLTAGE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*(mv|v)(?![a-z0-9])", re.I)


def _voltage_tokens(text: str) -> set[tuple[str, str]]:
    return {(number, unit.casefold()) for number, unit in _VOLTAGE.findall(unquote(text))}


def _official_link_identity(query: str, page_url: str, source_url: str, *, client=None) -> str:
    from backend.projects.external_circuit_search import _manufacturer_for, _page_assets, _page_asset_host_allowed

    if (page_url == source_url or not _manufacturer_for(page_url)
            or not _page_asset_host_allowed(source_url, page_url)):
        return ""
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return _official_link_identity(query, page_url, source_url, client=owned)
    voltage_terms = {_identity_compact(number + unit) for number, unit in _voltage_tokens(query)}
    terms = set(_identity_terms(_VOLTAGE.sub(lambda match: "".join(match.groups()), query))) - voltage_terms
    for url, label in _page_assets(page_url, client=client, required=True):
        if (url == source_url and all(term in _identity_compact(label) for term in terms)
                and _voltage_tokens(query) <= _voltage_tokens(label)):
            return label
    return ""


def _pico_variant(identity: str) -> str | None:
    for variant in ("pico2w", "pico2", "picow", "pico"):
        if variant in identity:
            return variant
    return None


def _verify_artifact_name(query: str, source_file: str, source_url: str, title: str) -> None:
    if is_non_circuit_asset(source_url, f"{title} {source_file}"):
        raise _invalid()
    filename = _identity_compact(source_file or urlsplit(source_url).path.rsplit("/", 1)[-1])
    if any(marker in filename for marker in _NON_SCHEMATIC_DOCUMENT_MARKERS):
        raise _invalid()
    requested = _pico_variant(_identity_compact(canonical_product_query(query)))
    actual = _pico_variant(filename)
    if requested and actual and requested != actual:
        raise _invalid()


def _verify_public_identity(query: str, *, title: str, page_url: str, source_file: str,
                            source_url: str, kind: str, pdf_text: str = "", linked_identity: str = "") -> None:
    """Reject a valid image/PDF whose board variant is not the requested one."""
    from backend.projects.external_circuit_search import _MANUFACTURER_ALIASES

    _verify_artifact_name(query, source_file, source_url, title)
    query = _VOLTAGE.sub(lambda match: "".join(match.groups()), canonical_product_query(query))
    voltages = _voltage_tokens(query)
    # Preserve decimal points; source text or a verified official link must support voltages.
    # A linked page only supplements a PDF with no extractable voltage evidence.
    if _voltage_tokens(pdf_text):
        linked_identity = ""
    if not voltages <= _voltage_tokens(" ".join((pdf_text, source_file, source_url, linked_identity))):
        raise _invalid()
    voltage_terms = {_identity_compact(number + unit) for number, unit in voltages}
    terms = _identity_terms(query)
    if not terms:
        return
    metadata = _identity_compact(" ".join((title, page_url, source_file, source_url)))
    source_identity = _identity_compact(" ".join((page_url, source_file, source_url)))
    artifact_identity = _identity_compact(" ".join((source_file, source_url)))
    text = _identity_compact(pdf_text)
    haystack = metadata + text
    # Numeric/model tokens and explicit variants must occur in the source identity.
    # This blocks e.g. ATP -> the general Artemis and LC -> Teensy 4.1.
    for term in terms:
        if term in voltage_terms:
            continue
        if any(char.isdigit() for char in term) or term in {
            "atp", "qwiic", "breakout", "lc", "nano", "every", "rp2040", "esp32c3", "esp32s2",
            "zero", "core2",
        }:
            if term not in haystack or (kind == "pdf" and term not in text and term not in source_identity):
                raise _invalid()
    query_identity = _identity_compact(query)
    manufacturer_identity = _identity_compact(canonical_product_query(
        f"{title} {page_url} {source_file} {source_url} {pdf_text} {linked_identity}"))
    for aliases in _MANUFACTURER_ALIASES.values():
        if (any(_identity_compact(alias) in query_identity for alias in aliases)
                and not any(_identity_compact(alias) in manufacturer_identity for alias in aliases)):
            raise _invalid()
    if any(marker in haystack for marker in _ACCESSORY_MARKERS) and "shield" not in query_identity:
        raise _invalid()
    if "qwiic" in artifact_identity and "qwiic" not in query_identity:
        raise _invalid()
    if "atp" in artifact_identity and "atp" not in query_identity:
        raise _invalid()
    if "atp" in query_identity and "atp" not in artifact_identity:
        raise _invalid()
    if "shield" in artifact_identity and "shield" not in query_identity:
        raise _invalid()
    if "every" in artifact_identity and "every" not in query_identity and "nano" in query_identity:
        raise _invalid()
    if any(marker in haystack for marker in _PARTIAL_MARKERS) and not any(
            marker in _identity_compact(query) for marker in _PARTIAL_MARKERS):
        raise _invalid()
    if "zio" in artifact_identity and "zio" not in terms:
        raise _invalid()
    # Product-page titles can be broad; the downloaded artifact must not name
    # a different board or accessory variant.
    artifact_conflicts = {
        "qtrp": "qtpy",
        "itsybitsy": "itsybitsy",
        "9dof": "9dof",
        "imu": "9dof",
        "hookupguide": "hookup",
        "hookup": "hookup",
    }
    for marker, requested in artifact_conflicts.items():
        if marker in artifact_identity and requested not in query_identity:
            raise _invalid()
    # Product pages cover multiple boards; the artifact must match the requested variant.
    requested_pico = _pico_variant(query_identity)
    file_identity = _identity_compact(source_file or urlsplit(source_url).path.rsplit("/", 1)[-1])
    if requested_pico:
        variants = tuple(filter(None, (_pico_variant(file_identity),
                                       _pico_variant(_identity_compact(urlsplit(source_url).path)),
                                       _pico_variant(text))))
        if not variants or any(variant != requested_pico for variant in variants):
            raise _invalid()
    numeric_terms = [term for term in terms if any(char.isdigit() for char in term)]
    source_tokens = re.findall(r"[a-z]+[0-9][a-z0-9]*", " ".join(
        (page_url, source_file, source_url)).casefold())
    for term in numeric_terms:
        match = re.fullmatch(r"([a-z]+)(\d[0-9a-z]*)", term)
        if not match:
            continue
        prefix, digits = match.groups()
        for candidate in re.findall(r"([a-z]+)(" + re.escape(digits) + r")", " ".join(source_tokens)):
            if candidate[0] != prefix and candidate[0] not in {"qtpy", "py"}:
                raise _invalid()


def _verify_image_page(page_url: str, source_url: str, *, client=None) -> None:
    from backend.projects.external_circuit_search import _page_assets

    if not page_url or page_url == source_url:
        raise _invalid()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return _verify_image_page(page_url, source_url, client=owned)
    # Search also reads the HTML counterpart of an indexed Markdown page.
    page_url = page_url[:-3] if page_url.endswith(".md") else page_url
    # shortcut: verify publisher evidence, not image semantics; use content review if mislabelling persists.
    if not any(url == source_url for url, _ in _page_assets(
            page_url, client=client, required=True, require_schematic_context=True)):
        raise _invalid()


def inspect_public_schematic(url: str, kind: str, query: str, *, title: str = "",
                             page_url: str = "", source_file: str = "",
                             client: httpx.Client | None = None) -> tuple[str, int]:
    """Download, identify, and fingerprint one public schematic in one pass."""
    _verify_artifact_name(query, source_file, url, title)
    if kind in {"png", "svg"}:
        _verify_image_page(page_url, url, client=client)
    data, _ = _public_asset(url, kind, client=client)
    pdf_text = _pdf_identity_text(data) if kind == "pdf" else ""
    linked_identity = ""
    if kind == "pdf" and not _voltage_tokens(pdf_text) and not _voltage_tokens(query) <= _voltage_tokens(
            " ".join((source_file, url))):
        linked_identity = _official_link_identity(canonical_product_query(query), page_url, url, client=client)
    _verify_public_identity(query, title=title, page_url=page_url, source_file=source_file,
                            source_url=url, kind=kind, pdf_text=pdf_text, linked_identity=linked_identity)
    if kind == "png":
        _valid_png(data)
        with Image.open(io.BytesIO(data), formats=["PNG"]) as png:
            if (png.width < MIN_SCHEMATIC_IMAGE_DIMENSION
                    or png.height < MIN_SCHEMATIC_IMAGE_DIMENSION):
                raise _invalid()
        count = 1
    elif kind == "svg":
        _svg(data)
        count = 1
    else:
        count = len(_bounded_pdf_schematic_pages(data))
    return hashlib.sha256(data).hexdigest(), count


def fingerprint_public_schematic(url: str, kind: str, *, client: httpx.Client | None = None) -> tuple[str, int]:
    """Fetch and validate a discovered public PDF/PNG/SVG, returning hash and sheets."""
    data, _ = _public_asset(url, kind, client=client)
    if kind == "png":
        _valid_png(data)
        count = 1
    elif kind == "svg":
        _svg(data)
        count = 1
    else:
        count = len(_bounded_pdf_schematic_pages(data))
    return hashlib.sha256(data).hexdigest(), count


def render_public_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None) -> tuple[bytes, ...]:
    """Re-fetch a discovered public asset, verify its fingerprint, and rasterize it."""
    if (source.source_type not in {"manufacturer_official", "public_web"}
            or not isinstance(source.source_url, str)
            or not isinstance(source.source_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source.source_sha256)
            or source.asset_kind not in {"png", "svg", "pdf"}
            or type(source.expected_sheets) is not int or not 1 <= source.expected_sheets <= MAX_SHEETS):
        raise _invalid()
    data, _ = _public_asset(source.source_url, source.asset_kind, client=client)
    if hashlib.sha256(data).hexdigest() != source.source_sha256:
        raise _invalid()
    pages = None
    if source.asset_kind == "png":
        _valid_png(data)
    elif source.asset_kind == "svg":
        _svg(data)
    else:
        pages = _bounded_pdf_schematic_pages(data)
        if len(pages) != source.expected_sheets:
            raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-render-") as temporary:
        work = Path(temporary)
        path = work / (source.source_file or f"schematic.{source.asset_kind}")
        path.write_bytes(data)
        sheets = _sheets(source.asset_kind, path, work / "pages", pdf_pages=pages if source.asset_kind == "pdf" else None)
    if len(sheets) != source.expected_sheets:
        raise _invalid()
    return sheets


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "inspect-pdf":
        try:
            pages = _pdf_schematic_pages(Path(sys.argv[2]).read_bytes())
            print(",".join(str(index) for index in pages))
        except (ExternalSchematicInvalidSource, OSError, ValueError):
            raise SystemExit(1)
    elif len(sys.argv) >= 3 and sys.argv[1] == "inspect-pdf-text":
        try:
            import pypdfium2 as pdfium
            document = pdfium.PdfDocument(Path(sys.argv[2]).read_bytes())
            try:
                chunks = []
                for index in range(min(len(document), MAX_SHEETS)):
                    page = document[index]
                    try:
                        chunks.append(page.get_textpage().get_text_range())
                    finally:
                        page.close()
                print(" ".join(chunks)[:MAX_PDF_TEXT_BYTES])
            finally:
                document.close()
        except (ExternalSchematicInvalidSource, OSError, ValueError, RuntimeError):
            raise SystemExit(1)
    else:
        _rasterize(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
