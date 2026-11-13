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
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree as ET

import httpx
from PIL import Image

from backend.graph.netlist import _sexpr
from backend.projects.schematic import (
    COMMAND_TIMEOUT_SECONDS, KicadServiceUnavailable, run_kicad_pdf,
)
from backend.projects.schematic_source import (
    ExternalSchematicInvalidSource, ExternalSchematicUpstreamError, VerifiedSchematicSource,
)

MIB = 1024 * 1024
MAX_IMAGE_BYTES = 10 * MIB
MAX_PDF_BYTES = 20 * MIB
MAX_ARCHIVE_BYTES = 25 * MIB
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * MIB
MAX_TREE_ITEMS = 5000
MAX_SHEETS = 20
MAX_PIXELS = 40_000_000
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


def _rasterize(kind: str, path: Path, output: Path):
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
        for index in range(len(document)):
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
                    out = output / f"{index + 1:02}.png"
                    bitmap.to_pil().save(out, format="PNG")
                    _valid_png(out.read_bytes())
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()


def _sheets(kind: str, path: Path, output: Path) -> tuple[bytes, ...]:
    output.mkdir()
    if path.stat().st_size > (MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES):
        raise _invalid()
    try:
        subprocess.run(
            [sys.executable, "-m", "backend.projects.schematic_render", kind, str(path), str(output)],
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


def render_official_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None) -> tuple[bytes, ...]:
    """등록된 제조사 원본을 한 번 받아 해시를 확인한 뒤 임시로 rasterize한다."""
    from backend.projects.schematic_discovery import download_bounded

    if (source.source_type != "manufacturer_official" or source.evidence_grade != 2
            or not source.source_sha256 or not re.fullmatch(r"[0-9a-f]{64}", source.source_sha256)
            or not isinstance(source.source_url, str)):
        raise _invalid()
    parsed = urlsplit(source.source_url)
    host = parsed.hostname
    if host not in {"cdn.sparkfun.com", "www.sparkfun.com", "learn.sparkfun.com",
                    "cdn-learn.adafruit.com", "learn.adafruit.com", "www.adafruit.com"}:
        raise _invalid()
    kind = source.asset_kind
    if kind not in {"pdf", "png", "svg"}:
        raise _invalid()
    limit = MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES
    data, mime = download_bounded(source.source_url, max_bytes=limit,
                                  allowed_hosts=frozenset({host}), client=client)
    if hashlib.sha256(data).hexdigest() != source.source_sha256:
        raise _invalid()
    generic = {"application/octet-stream"} | ({"text/plain"} if kind == "svg" else set())
    if mime not in MIME[kind] | generic:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-official-render-") as temporary:
        work = Path(temporary)
        path = work / source.source_file
        path.write_bytes(data)
        sheets = _sheets(kind, path, work / "pages")
    if len(sheets) != source.expected_sheets:
        raise _invalid()
    return sheets


if __name__ == "__main__":
    _rasterize(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
