"""고정 커밋의 공개 회로 원본을 검증하고 모든 시트를 PNG로 변환한다."""
from __future__ import annotations

import io
import json
import hashlib
import logging
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import BoundedSemaphore, RLock
from typing import Callable
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET

import httpx
from PIL import Image

from backend.graph.netlist import TOKEN as _SEXPR_TOKEN, _sexpr
from backend.projects.external_circuit_search import (
    _MANUFACTURER_ALIASES, canonical_product_query, is_non_circuit_asset,
)
from backend.projects.schematic import (
    COMMAND_TIMEOUT_SECONDS, KicadServiceUnavailable, run_kicad_pdf, run_kicad_netlist,
)
from backend.projects.schematic_source import (
    ExternalSchematicInvalidSource, ExternalSchematicRateLimited, ExternalSchematicUpstreamError,
    VerifiedSchematicSource,
)

MIB = 1024 * 1024
MAX_IMAGE_BYTES = 10 * MIB
MIN_SCHEMATIC_IMAGE_DIMENSION = 128
MAX_PDF_BYTES = 20 * MIB
MAX_PDF_PAGES = 200
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


@dataclass(frozen=True)
class _CheckedOfficialPDF:
    url: str
    query: str
    manufacturer: str
    digest: str
    pages: tuple[int, ...]
    data: bytes = field(repr=False)


_PDF_REQUEST = ContextVar('schematic_pdf_request', default=None)
_PDF_LOG = logging.getLogger(__name__)
_PDF_INSPECTION_SLOTS = BoundedSemaphore(2)


@contextmanager
def official_pdf_request():
    """Pass at most two checked PDFs to conversion within one request."""
    if _PDF_REQUEST.get() is not None:
        yield
        return
    state = {'prepared': [], 'work': {}, 'lock': RLock(), 'active': 0, 'peak': 0}
    token = _PDF_REQUEST.set(state)
    try:
        yield
    finally:
        work = list(state['work'].values())
        peak = state['peak']
        state.clear()
        _PDF_REQUEST.reset(token)
        if work:
            _PDF_LOG.info('schematic_pdf_request_work', extra={'pdf_work': work, 'pdf_inspection_peak': peak})


@contextmanager
def official_pdf_inspection_slot(url):
    """Bound actual official candidate inspections across requests to two."""
    with _PDF_INSPECTION_SLOTS:
        state = _PDF_REQUEST.get()
        if state is not None:
            with state['lock']:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
        started = time.perf_counter()
        try:
            yield
        finally:
            finished = time.perf_counter()
            if state is not None:
                with state['lock']:
                    state['active'] -= 1
            _PDF_LOG.info('schematic_pdf_inspection_worker', extra={
                'source_id': hashlib.sha256(url.encode()).hexdigest(),
                'started_ms': round(started * 1000, 3), 'finished_ms': round(finished * 1000, 3),
            })


def clear_checked_pdfs():
    state = _PDF_REQUEST.get()
    if state is not None:
        with state['lock']:
            state['prepared'].clear()


def _pdf_work(url, manufacturer):
    state = _PDF_REQUEST.get()
    if state is None:
        return None
    identity = hashlib.sha256(url.encode()).hexdigest()
    with state['lock']:
        return state['work'].setdefault(identity, {
            'source_id': identity, 'manufacturer': manufacturer,
            'downloads': 0, 'inspections': 0, 'reuses': 0,
            'download_ms': 0.0, 'inspection_ms': 0.0, 'conversion_ms': 0.0,
        })


def _record_pdf_work(work, **increments):
    if work is not None:
        with _PDF_REQUEST.get()['lock']:
            for key, value in increments.items():
                work[key] += value


def _official_pdf_download(url, manufacturer, client):
    work = _pdf_work(url, manufacturer)
    started = time.perf_counter()
    try:
        return _public_asset(url, 'pdf', client=client)
    finally:
        _record_pdf_work(work, downloads=1, download_ms=round((time.perf_counter() - started) * 1000, 3))


def _official_pdf_pages(data, query, manufacturer, url):
    work = _pdf_work(url, manufacturer)
    started = time.perf_counter()
    try:
        return _bounded_official_pdf_schematic_pages(data, query, manufacturer)
    finally:
        _record_pdf_work(work, inspections=1, inspection_ms=round((time.perf_counter() - started) * 1000, 3))


def _take_checked_pdf(source, manufacturer):
    state = _PDF_REQUEST.get()
    if state is not None:
        with state['lock']:
            for index, prepared in enumerate(state['prepared']):
                if (prepared.url == source.source_url and prepared.query == source.model
                        and prepared.manufacturer == manufacturer and prepared.digest == source.source_sha256
                        and len(prepared.pages) == source.expected_sheets):
                    return state['prepared'].pop(index)
    return None


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
    if sys.platform == "linux":  # [왜] RLIMIT_AS는 Linux 전용. macOS는 ValueError로 하위 프로세스가 죽는다
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
        if not 1 <= len(document) <= MAX_PDF_PAGES:
            raise _invalid()
        if page_indices is None and len(document) > MAX_SHEETS:
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


def _kicad_nodes(text):
    """Inspect direct KiCad objects with bounded depth and without a full-sheet AST."""
    stack, starts = [], []
    end = count = 0
    finished = False
    for match in _SEXPR_TOKEN.finditer(text):
        if match.start() != end:
            raise _invalid()
        end = match.end()
        token = match.group()
        if token.isspace():
            continue
        count += 1
        if finished or count > 2_000_000:
            raise _invalid()
        if token == '(':
            if len(stack) >= 64:
                raise _invalid()
            stack.append(None); starts.append(match.start())
        elif token == ')':
            if not stack or stack[-1] is None:
                raise _invalid()
            tag = None
            if stack in (["kicad_sch", "symbol"], ["kicad_sch", "sheet"]):
                tag = stack[-1]
            elif stack == ["kicad_sch", "lib_symbols", "symbol"]:
                tag = "library"
            if tag:
                yield tag, _sexpr(text[starts[-1]:match.end()])
            stack.pop(); starts.pop()
            finished = not stack
        elif not stack:
            raise _invalid()
        elif stack[-1] is None:
            stack[-1] = token
            if len(stack) == 1 and token != "kicad_sch":
                raise _invalid()
    if end != len(text) or not finished or stack:
        raise _invalid()


def _sheet_files(raw: bytes) -> list[str]:
    """회로도 한 장의 직접 객체를 검사하고 하위 시트 파일 이름을 돌려준다. 놓인 부품은 내장 라이브러리에 있어야 한다."""
    # KiCad permits literal newlines in quoted descriptions. Normalize only
    # the inspection copy for the shared JSON-string S-expression reader.
    inspection = re.sub(r'"(?:\\.|[^"\\])*"',
                        lambda match: json.dumps(json.loads(match[0], strict=False)),
                        raw.decode("utf-8-sig"))
    libraries, placed, children = set(), [], []
    for tag, node in _kicad_nodes(inspection):
        if tag == "library":
            if len(node) < 2 or not isinstance(node[1], str):
                raise _invalid()
            libraries.add(node[1])
        elif tag == "symbol":
            symbol = node
            ids = [n[1] for n in symbol if isinstance(n, list) and n[:1] == ["lib_id"] and len(n) == 2]
            aliases = [n[1] for n in symbol if isinstance(n, list) and n[:1] == ["lib_name"] and len(n) == 2]
            if (len(ids) != 1 or len(aliases) > 1
                    or not isinstance((aliases or ids)[0], str)):
                raise _invalid()
            placed.append((aliases or ids)[0])
        elif tag == "sheet":
            sheet = node
            found = [p[2] for p in sheet if isinstance(p, list) and len(p) >= 3
                     and p[0] == "property" and str(p[1]).lower().replace(" ", "") == "sheetfile"]
            if len(found) != 1 or not isinstance(found[0], str) or any(c in found[0] for c in "$%{}~"):
                raise _invalid()
            children.append(found[0])
    if any(lib not in libraries for lib in placed):
        raise _invalid()
    return children


class HierarchicalSchematic(ValueError):
    """하위 시트를 가리키는 업로드 회로도. 아직 받지 않는다(#52)."""


def uploaded_schematic_text(raw: bytes) -> str:
    """사용자가 올린 .kicad_sch 한 장을 KiCad에 넘기기 전에 검사한다: UTF-8 · (kicad_sch ...) 한 덩어리 · 하위 시트 없음.

    형식이 틀리면 ExternalSchematicInvalidSource, 하위 시트가 있으면 HierarchicalSchematic.
    """
    try:
        text = raw.decode("utf-8")
        if "\x00" in text:
            raise _invalid()
        children = _sheet_files(raw)
    except (UnicodeDecodeError, ValueError):  # json 정규화 실패도 ValueError
        raise _invalid() from None
    if children:
        raise HierarchicalSchematic()
    return text


def render_uploaded_schematic(text: str, *, kicad_export: Callable = run_kicad_pdf,
                              kicad_netlist_export: Callable = run_kicad_netlist) -> tuple[bytes, tuple[bytes, ...]]:
    """업로드한 회로도 한 장에서 (KiCad 넷리스트 원문, PNG 시트 1장)을 만든다. 파일 이름은 고정이라 사용자 경로가 명령에 들어가지 않는다."""
    from backend.projects.netlist import MAX_BYTES

    uploaded_schematic_text(text.encode("utf-8"))  # 렌더러도 API와 같은 검사를 다시 한다
    with tempfile.TemporaryDirectory(prefix="sojafit-upload-") as temporary:
        work = Path(temporary)
        (work / "source").mkdir()
        root = work / "source" / "upload.kicad_sch"
        root.write_text(text, encoding="utf-8")
        # [주의] 두 변환은 출력 폴더를 따로 쓴다. _run_export가 그 폴더에 home을 만들어 같은 폴더면 두 번째가 실패한다
        (work / "netlist").mkdir()
        netlist = kicad_netlist_export(root, work / "netlist")
        if not netlist.is_file() or netlist.stat().st_size > MAX_BYTES:
            raise _invalid()
        (work / "export").mkdir()
        _, pdf = kicad_export(root, work / "export")
        if not pdf.is_file():
            raise _invalid()
        sheets = _sheets("pdf", pdf, work / "pages")
        if len(sheets) != 1:
            raise _invalid()
        return netlist.read_bytes(), sheets


def _selected_kicad(source: VerifiedSchematicSource, fetch: Callable[[str], bytes], dest: Path) -> tuple[Path, int]:
    """Fetch only the already inspected KiCad hierarchy, never the whole repository archive."""
    paths = tuple(dict.fromkeys(source.asset_paths))
    if not paths or len(paths) > MAX_SHEETS or source.root_schematic not in paths:
        raise _invalid()
    files, contents = {}, {}
    total = 0
    for name in paths:
        path = _path(name)
        if path.suffix.casefold() != ".kicad_sch":
            raise _invalid()
        raw = fetch(str(path))
        total += len(raw)
        if len(raw) > MAX_IMAGE_BYTES or total > MAX_ARCHIVE_BYTES:
            raise _invalid()
        contents[path] = raw
        files[path] = [path.parent / _path(name) for name in _sheet_files(raw)]
    root = _path(source.root_schematic)
    count = 0
    seen = set()
    def visit(path, ancestors):
        nonlocal count
        if path in ancestors or path not in files:
            raise _invalid()
        seen.add(path); count += 1
        if count > MAX_SHEETS:
            raise _invalid()
        target = dest / path
        target.parent.mkdir(exist_ok=True, parents=True)
        target.write_bytes(contents[path])
        for child in files[path]:
            visit(child, ancestors | {path})
    visit(root, set())
    if len(seen) != len(files) or count != source.expected_sheets:
        raise _invalid()
    return dest / root, count


def render_external_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None,
                              kicad_export: Callable = run_kicad_pdf,
                              expected_connections=None, kicad_netlist_export: Callable = run_kicad_netlist,
                              connection_consumer: Callable | None = None) -> tuple[bytes, ...]:
    from backend.projects.schematic_discovery import download_bounded

    if (not re.fullmatch(r"[\w.-]+/[\w.-]+", source.repository, re.ASCII)
            or not re.fullmatch(r"[0-9a-f]{40}", source.commit)):
        raise _invalid()
    _path(source.repository)
    kind = source.asset_kind
    if kind not in MIME or ((expected_connections is not None or connection_consumer) and kind != 'kicad'):
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
            # A discovered KiCad hierarchy carries its exact files; do not fetch
            # the potentially huge repository archive before selective download.
            if kind == "kicad" and source.asset_paths:
                data, mime = b"", "application/zip"
            else:
                data, mime = download_bounded(url, max_bytes=limit, allowed_hosts=frozenset({host}), client=client)
            # GitHub raw에서는 PDF와 SVG에도 generic media type을 사용한다.
            generic = {"application/octet-stream"} | ({"text/plain"} if kind == "svg" else set())
            if len(data) > limit or mime not in MIME[kind] | generic:
                raise _invalid()
            if kind == "kicad":
                try:
                    if source.asset_paths:
                        def fetch_selected(path):
                            selected_url = f"https://raw.githubusercontent.com/{source.repository}/{source.commit}/{quote(path)}"
                            body, selected_mime = download_bounded(selected_url, max_bytes=MAX_IMAGE_BYTES,
                                allowed_hosts=frozenset({'raw.githubusercontent.com'}),client=client,phase='github_raw')
                            if selected_mime not in {'text/plain','application/octet-stream'}:
                                raise _invalid()
                            return body
                        root,count = _selected_kicad(source,fetch_selected,work/'source')
                    else:
                        root, count = _archive(source, data, work / "source")
                    if expected_connections is not None or connection_consumer:
                        from backend.projects.netlist import MAX_BYTES, same_circuit, normalize_netlist
                        net_output = work / 'netlist'
                        net_output.mkdir()
                        netlist = kicad_netlist_export(root, net_output)
                        if not netlist.is_file() or netlist.stat().st_size > MAX_BYTES:
                            raise _invalid()
                        actual = normalize_netlist(netlist.read_bytes()).connections
                        if expected_connections is not None and not same_circuit(actual, expected_connections):
                            raise _invalid()
                        if connection_consumer:
                            connection_consumer(actual)
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
                except ExternalSchematicRateLimited:
                    raise
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
    from backend.projects.external_circuit_search import _manufacturer_for, _SCHEMATIC_WORDS

    if kind not in {"png", "svg", "pdf"} or not isinstance(url, str):
        raise _invalid()
    parsed = urlsplit(url)
    host = parsed.hostname
    if not host or parsed.scheme != "https":
        raise _invalid()
    archive = kind == "pdf" and parsed.path.casefold().endswith(".zip")
    if archive and not _manufacturer_for(url):
        raise _invalid()
    limit = MAX_ARCHIVE_BYTES if archive else MAX_PDF_BYTES if kind == "pdf" else MAX_IMAGE_BYTES
    data, mime = download_bounded(url, max_bytes=limit, allowed_hosts=frozenset({host}),
                                  client=client, phase="public_asset")
    generic = {"application/octet-stream"} | ({"text/plain"} if kind == "svg" else set())
    if archive:
        if mime not in MIME['kicad'] | generic:
            raise _invalid()
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                entries = bundle.infolist()
                if len(entries) > MAX_TREE_ITEMS or sum(e.file_size for e in entries) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise _invalid()
                pdfs = [e for e in entries if e.filename.casefold().endswith('.pdf')
                        and _SCHEMATIC_WORDS.search(e.filename)]
                if len(pdfs) != 1 or pdfs[0].file_size > MAX_PDF_BYTES or pdfs[0].flag_bits & 1:
                    raise _invalid()
                _path(pdfs[0].filename)
                _verify_artifact_name(parsed.path.rsplit('/', 1)[-1], pdfs[0].filename.rsplit('/', 1)[-1], url, '')
                with bundle.open(pdfs[0]) as stream:
                    data = stream.read(MAX_PDF_BYTES + 1)
                if len(data) > MAX_PDF_BYTES or not data.startswith(b'%PDF-'):
                    raise _invalid()
        except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
            raise _invalid() from None
        return data, 'application/pdf'
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
        if not 1 <= count <= MAX_PDF_PAGES or _pdf_creator_is_pcbnew(document):
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
        return tuple(selected[:MAX_SHEETS])
    finally:
        document.close()


def _is_tsc_datasheet(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname == 'services.taiwansemi.com'
            and parsed.username is None and parsed.password is None and parsed.port in (None, 443)
            and not parsed.query and not parsed.fragment
            and bool(re.fullmatch(r'/storage/resources/datasheet/[^/]+\.pdf', parsed.path, re.I)))


def _tsc_circuit_wires(page, top: float) -> bool:
    """Require real vector connections below the application heading, not a package photo."""
    import ctypes
    from collections import Counter
    import pypdfium2 as pdfium
    lines, segments = set(), 0
    for count, obj in enumerate(page.get_objects(max_depth=5), 1):
        if count > 10000:
            return False
        if obj.type != pdfium.raw.FPDF_PAGEOBJ_PATH:
            continue
        previous = None
        matrix = obj.get_matrix()
        for index in range(pdfium.raw.FPDFPath_CountSegments(obj)):
            segments += 1
            if segments > 50000:
                return False
            segment = pdfium.raw.FPDFPath_GetPathSegment(obj, index)
            x, y = ctypes.c_float(), ctypes.c_float()
            if not pdfium.raw.FPDFPathSegment_GetPoint(segment, x, y):
                return False
            point = matrix.on_point(x.value, y.value)
            if not all(math.isfinite(v) for v in point):
                return False
            if previous and max(previous[1], point[1]) <= top + 2 and pdfium.raw.FPDFPathSegment_GetType(segment) == pdfium.raw.FPDF_SEGMENT_LINETO:
                dx, dy = abs(point[0]-previous[0]), abs(point[1]-previous[1])
                if (5 <= dx < page.get_width()*.8 and dy < .1) or (5 <= dy < page.get_height()*.8 and dx < .1):
                    lines.add(tuple(sorted((tuple(round(v*2) for v in previous), tuple(round(v*2) for v in point)))))
            previous = point
    if len(lines) > 2000:
        return False
    ends = Counter(point for line in lines for point in line)
    # CAD exporters frequently draw a T-junction as a wire ending on an
    # uninterrupted bus. Count those connections as well as shared endpoints.
    for point in tuple(ends):
        for first, last in lines:
            if point in (first, last):
                continue
            if (abs(first[1]-last[1]) <= 1 and abs(point[1]-first[1]) <= 1
                    and min(first[0],last[0]) < point[0] < max(first[0],last[0])) or (
                    abs(first[0]-last[0]) <= 1 and abs(point[0]-first[0]) <= 1
                    and min(first[1],last[1]) < point[1] < max(first[1],last[1])):
                ends[point] += 2
    return len(lines) >= 8 and sum(count >= 3 for count in ends.values()) >= 2


def _tsc_bitmap_has_connections(image) -> bool:
    """Recognize thin orthogonal wiring and branches, not a lone IC/block photo."""
    if image.mode == 'RGBA':
        image = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image)
    image = image.convert('L')
    image.thumbnail((600, 600))
    width, height = image.size
    if width < 128 or height < 64:
        return False
    pixels = image.load()
    if sum(image.histogram()[221:]) < width * height * .65:
        return False
    def runs(vertical=False):
        found = []
        across, along = (width, height) if vertical else (height, width)
        for cross in range(across):
            start = None
            for index in range(along + 1):
                dark = index < along and (pixels[cross,index] if vertical else pixels[index,cross]) < 100
                if dark and start is None:
                    start = index
                if not dark and start is not None:
                    if index - start >= 12:
                        middle = (start + index) // 2
                        neighbors = [pixels[c,middle] if vertical else pixels[middle,c]
                                     for c in (max(0,cross-3), min(across-1,cross+3))]
                        if max(neighbors) > 220 and not any(
                                abs(cross-c) <= 3 and abs(start-a) <= 3 and abs(index-b) <= 3
                                for a,b,c in found[-20:]):
                            found.append((start,index,cross))
                            if len(found) > 500:
                                return []
                    start = None
        return found
    horizontal, vertical = runs(), runs(True)
    if len(horizontal) < 3 or len(vertical) < 3 or len(horizontal)+len(vertical) < 8:
        return False
    branches = set()
    for left,right,y in horizontal:
        for top,bottom,x in vertical:
            if left-2 <= x <= right+2 and top-2 <= y <= bottom+2 and (
                    left+3 < x < right-3 or top+3 < y < bottom-3):
                branches.add((x//4,y//4))
    return len(branches) >= 2


def _tsc_circuit_bitmap(page, top: float) -> bool:
    import pypdfium2 as pdfium
    for count, obj in enumerate(page.get_objects(max_depth=5), 1):
        if count > 10000:
            return False
        if obj.type != pdfium.raw.FPDF_PAGEOBJ_IMAGE or obj.get_bounds()[3] > top + 2:
            continue
        width,height = obj.get_px_size()
        if width*height > MAX_PIXELS:
            continue
        # Render the image's alpha mask; raw stencil bitmaps have a black background.
        bitmap = obj.get_bitmap(render=True)
        if _tsc_bitmap_has_connections(bitmap.to_pil()):
            return True
    return False


def _require_english_official_text(text: str) -> None:
    """Require English introductory text, not just an English diagram caption.

    This conservative lexical gate has no model/network dependency. Short
    circuit-only documents use engineering labels; prose must also contain
    English function words. Structured CAD sheets use English project/sheet
    fields and component references instead. A few foreign brand names do not
    reject English.
    """
    letters = [char for char in text if char.isalpha()]
    words = set(re.findall(r'\b[a-z]+\b', text.casefold()))
    english = {'the', 'and', 'for', 'with', 'this', 'from', 'is', 'are', 'of', 'to', 'in', 'as', 'by'}
    labels = {'typical', 'application', 'circuit', 'schematic', 'diagram', 'power',
              'supply', 'input', 'output', 'voltage', 'current', 'vin', 'gnd', 'vcc'}
    cad_sheet = (re.search(r'(?i)\bproject\s*:', text)
                 and re.search(r'(?i)\bsheet\s*:\s*o\s*f\b', text)
                 and len(set(re.findall(r'\b(?:IC|R|C|D|Q|U|L|J)\s*\d{1,4}\b', text, re.I))) >= 6)
    if (not letters or sum(char.isascii() for char in letters) / len(letters) < .9
            or (not cad_sheet and len(words & english) < 3
                and (len(letters) >= 400 or len(words & labels) < 3))):
        raise _invalid()


def _tsc_application_pages(data: bytes, query: str) -> tuple[int, ...]:
    """Select connected application circuits only from an identified TSC datasheet."""
    if not data.startswith(b'%PDF-') or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    import pypdfium2 as pdfium
    parts = re.findall(r'\b[a-z]+\d[a-z0-9]*\b', query.casefold())
    if not parts:
        raise _invalid()
    document = pdfium.PdfDocument(data)
    selected = []
    try:
        if not 1 <= len(document) <= MAX_PDF_PAGES or _pdf_creator_is_pcbnew(document):
            raise _invalid()
        identity_text = []
        for page in document:
            try:
                textpage = page.get_textpage()
                try:
                    identity_text.append(textpage.get_text_range())
                finally:
                    textpage.close()
            finally:
                page.close()
        identity = '\n'.join(identity_text)
        if len(identity) > MAX_PDF_TEXT_BYTES or not all(re.search(
                r'(?<![a-z0-9])'+re.escape(part)+r'(?![a-z0-9])',identity,re.I) for part in parts):
            raise _invalid()
        _require_english_official_text('\n'.join(identity_text[:3]))
        for index in range(len(document)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    text = identity_text[index]
                    if 'taiwan semiconductor' not in ' '.join(text.casefold().split()):
                        continue
                    heading = re.search(r'(?i)(?:typical\s+)?applicati(?:on|n)\s+circuit(?:s)?\b|typical\s+circuit\b', text)
                    if heading is None or 'table of contents' in text.casefold():
                        continue
                    try:
                        _require_english_official_text(text)
                    except ExternalSchematicInvalidSource:
                        continue
                    bottom = textpage.get_charbox(heading.start())[1]
                    if _tsc_circuit_wires(page, bottom) or _tsc_circuit_bitmap(page, bottom):
                        selected.append(index)
                finally:
                    textpage.close()
            finally:
                page.close()
        if not selected:
            raise _invalid()
        return tuple(selected[:MAX_SHEETS])
    finally:
        document.close()


_OFFICIAL_APPLICATION_HEADING = re.compile(
    r"(?i)(?:typical\s+application(?:\s+circuit)?|application\s+circuit|"
    r"circuit\s+design|reference\s+design|schematic(?:\s+diagram)?|"
    r"pfc\s+circuit|diode\s+(?:detector|application))\b"
)
_OFFICIAL_NON_CIRCUIT_PAGE = re.compile(
    r"(?i)\b(?:table\s+of\s+contents|block\s+diagram|pin\s*(?:out|configuration)|"
    r"package\s+(?:outline|dimensions)|product\s+photo|ordering\s+information)\b"
)
_OFFICIAL_NON_CIRCUIT_CONTENT = re.compile(
    r"(?i)\b(?:table\b|bom\b|bill\s+of\s+materials|selection\s+table|"
    r"manufacturers?|measurement\s+results?|waveforms?|waveform|"
    r"characteristics?|actual\s+iv\s+curve|power\s+losses?|"
    r"nomograph|photo\s+of|layout\s+example|"
    r"thermal\s+considerations?|device\s+support|disclaimer)\b"
)
_OFFICIAL_PAGE_HINT = re.compile(
    r"(?i)\b(?:top\s*&\s*power|mcu|stlink|extension\s+connectors?|"
    r"power\s+(?:stage|supply|converter)|application\s+information|"
    r"pfc|detector|sheet\s*:\s*of|project\s*:|reference\s+design)\b"
)
_OFFICIAL_QUERY_STOPWORDS = {
    "ti", "texas", "instruments", "st", "stmicroelectronics", "analog", "devices",
    "adi", "onsemi", "semiconductor", "infineon", "vishay", "diode", "diodes", "rf",
    "pfc", "application", "applications", "circuit", "circuits", "reference", "design",
    "schematic", "datasheet", "data", "sheet", "note", "notes", "typical", "official",
    "nucleo", "board", "module", "the", "and", "of", "for",
}


def _official_query_model_terms(query: str) -> tuple[str, ...]:
    terms = []
    for raw in re.findall(r"[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*", query or ""):
        compact = re.sub(r"[^a-z0-9]", "", raw.casefold())
        if len(compact) < 3 or compact in _OFFICIAL_QUERY_STOPWORDS:
            continue
        if any(char.isdigit() for char in compact) or raw.isupper():
            if compact not in terms:
                terms.append(compact)
    return tuple(terms)


def _semiconductor_official_manufacturer(url: str) -> str | None:
    try:
        from backend.projects.external_circuit_search import semiconductor_source_manufacturer
        return semiconductor_source_manufacturer(url)
    except (ImportError, TypeError, ValueError):
        return None


_OFFICIAL_MANUFACTURER_ALIASES = {
    "texas instruments": ("texas", "instruments", "ti"),
    "stmicroelectronics": ("stmicroelectronics", "st"),
    "analog devices": ("analog", "devices", "adi"),
    "onsemi": ("onsemi", "semiconductor"),
    "infineon": ("infineon",),
    "vishay": ("vishay",),
}


def _official_application_pages(data: bytes, query: str, manufacturer: str) -> tuple[int, ...]:
    """Select connected application-circuit pages from an identified official PDF."""
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES or not manufacturer:
        raise _invalid()
    import pypdfium2 as pdfium
    model_terms = _official_query_model_terms(query)
    if not model_terms:
        raise _invalid()
    document = pdfium.PdfDocument(data)
    selected = []
    try:
        if not 1 <= len(document) <= MAX_PDF_PAGES or _pdf_creator_is_pcbnew(document):
            raise _invalid()
        texts = []
        for page in document:
            try:
                texts.append(page.get_textpage().get_text_range())
            finally:
                page.close()
        identity = "\n".join(texts)
        if len(identity) > MAX_PDF_TEXT_BYTES:
            raise _invalid()
        identity_compact = _identity_compact(identity)
        if not all(term in identity_compact for term in model_terms):
            raise _invalid()
        from backend.projects.external_circuit_search import semiconductor_part_query, _part_identifiers
        bare_part = semiconductor_part_query(query)
        if bare_part and bare_part.replace('-', '').casefold() not in _part_identifiers(identity):
            raise _invalid()
        manufacturer_terms = [re.sub(r"[^a-z0-9]", "", token.casefold())
                              for token in _OFFICIAL_MANUFACTURER_ALIASES.get(
                                  manufacturer.casefold(), tuple(re.findall(r"[A-Za-z0-9]+", manufacturer)))
                              if len(token) > 2 and token.casefold() not in {"inc", "ltd", "corp", "company"}]
        if manufacturer.casefold() == "texas instruments":
            manufacturer_terms.append("ti")
        elif manufacturer.casefold() == "stmicroelectronics":
            manufacturer_terms.append("st")
        if manufacturer_terms and not any(term in identity_compact for term in manufacturer_terms):
            raise _invalid()
        _require_english_official_text('\n'.join(texts[:3]))
        for index, text in enumerate(texts):
            if (_OFFICIAL_NON_CIRCUIT_PAGE.search(text)
                    and not re.search(r"(?i)\b(?:detailed\s+design|design\s+requirements)\b", text)):
                continue
            heading = _OFFICIAL_APPLICATION_HEADING.search(text)
            refs = re.findall(r"\b(?:IC|R|C|D|Q|U|L|J)\s*\d{1,4}\b", text, re.I)
            families = {re.sub(r"\s+", "", ref.casefold())[0] for ref in refs}
            cad_title = re.search(r"(?i)\b(?:sheet\s*:\s*of|project\s*:|title\s*:)", text)
            content_marker = _OFFICIAL_NON_CIRCUIT_CONTENT.search(text)
            allow_rf_diagram = (content_marker and heading
                                and len(families) < 2
                                and re.search(r"(?i)(?:application|detector)", heading.group(0))
                                and re.search(r"(?i)\bschematic\b", text))
            allow_pfc_intro = (index == 0 and content_marker and heading
                               and re.search(r"(?i)pfc\s+circuit", heading.group(0))
                               and re.search(r"(?i)typical\s+active\s+pfc", text))
            allow_component_design = (content_marker and content_marker.group(0).casefold() == "manufacturers"
                                      and len(families) >= 3)
            if content_marker and not (allow_rf_diagram or allow_pfc_intro or allow_component_design):
                continue
            if heading is None and len(families) < 2 and not cad_title:
                continue
            if heading and len(families) < 2 and not re.search(
                    r"(?i)(?:application|detector|pfc)", heading.group(0)):
                continue
            unique_refs = {re.sub(r"\s+", "", ref.casefold()) for ref in refs}
            if (len(families) >= 2 and len(unique_refs) < 3
                    and not (index == 0 and re.search(r"(?i)pfc\s+circuit", text))):
                continue
            if heading is None and not (_OFFICIAL_PAGE_HINT.search(text) and (
                    refs or re.search(r"(?i)\b(?:sheet\s*:\s*of|project\s*:|title\s*:)", text))):
                continue
            try:
                _require_english_official_text(text)
            except ExternalSchematicInvalidSource:
                continue
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    bottom = textpage.get_charbox(heading.start())[1] if heading else 0
                finally:
                    textpage.close()
                connected = (_tsc_circuit_wires(page, bottom) or _tsc_circuit_bitmap(page, bottom)
                             or _official_vector_connections(page, text))
                if (not connected and heading and len(families) < 2
                        and re.search(r"(?i)(?:application|detector|pfc)\s+circuit", heading.group(0))):
                    try:
                        connected = _official_page_raster_connections(page)
                    except (OSError, RuntimeError, ValueError):
                        connected = False
                if connected:
                    selected.append(index)
            finally:
                page.close()
        if not selected:
            raise _invalid()
        return tuple(selected[:MAX_SHEETS])
    finally:
        document.close()


def _official_page_raster_connections(page) -> bool:
    """Check a rasterized page for thin orthogonal wires and branches."""
    image = page.render(scale=0.8).to_pil()
    return _tsc_bitmap_has_connections(image)


def _official_vector_connections(page, text: str) -> bool:
    """Fallback for CAD-exported official schematics whose wires are compound paths."""
    import ctypes
    from collections import Counter
    import pypdfium2 as pdfium
    if _OFFICIAL_NON_CIRCUIT_PAGE.search(text):
        return False
    lines, segments = set(), 0
    for count, obj in enumerate(page.get_objects(max_depth=5), 1):
        if count > 10000:
            return False
        if obj.type != pdfium.raw.FPDF_PAGEOBJ_PATH:
            continue
        previous = None
        matrix = obj.get_matrix()
        for index in range(pdfium.raw.FPDFPath_CountSegments(obj)):
            segments += 1
            if segments > 50000:
                return False
            segment = pdfium.raw.FPDFPath_GetPathSegment(obj, index)
            x, y = ctypes.c_float(), ctypes.c_float()
            if not pdfium.raw.FPDFPathSegment_GetPoint(segment, x, y):
                return False
            point = matrix.on_point(x.value, y.value)
            kind = pdfium.raw.FPDFPathSegment_GetType(segment)
            if previous and kind == pdfium.raw.FPDF_SEGMENT_LINETO:
                dx, dy = abs(point[0] - previous[0]), abs(point[1] - previous[1])
                if (5 <= dx < page.get_width() * .8 and dy < .1) or (
                        5 <= dy < page.get_height() * .8 and dx < .1):
                    lines.add(tuple(sorted((tuple(round(v * 2) for v in previous),
                                            tuple(round(v * 2) for v in point)))))
            previous = point
    if len(lines) < 8:
        return False
    ends = Counter(point for line in lines for point in line)
    for point in tuple(ends):
        for first, last in lines:
            if point in (first, last):
                continue
            if ((abs(first[1] - last[1]) <= 1 and abs(point[1] - first[1]) <= 1
                 and min(first[0], last[0]) < point[0] < max(first[0], last[0])) or
                (abs(first[0] - last[0]) <= 1 and abs(point[0] - first[0]) <= 1
                 and min(first[1], last[1]) < point[1] < max(first[1], last[1]))):
                ends[point] += 2
    return sum(value >= 3 for value in ends.values()) >= 2


def _bounded_pdf_schematic_pages(data: bytes, *, tsc_query: str | None = None) -> tuple[int, ...]:
    """Inspect untrusted PDF bytes in the bounded worker process."""
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-pdf-inspect-") as temporary:
        path = Path(temporary) / "input.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.projects.schematic_render",
                 "inspect-tsc-pdf" if tsc_query else "inspect-pdf", str(path), *([tsc_query] if tsc_query else [])],
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


def _bounded_official_pdf_schematic_pages(data: bytes, query: str, manufacturer: str) -> tuple[int, ...]:
    """Run official-semiconductor PDF inspection under the same worker limits."""
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-official-pdf-inspect-") as temporary:
        path = Path(temporary) / "input.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.projects.schematic_render", "inspect-official-pdf",
                 str(path), query, manufacturer],
                cwd=Path(__file__).resolve().parents[2], check=True, timeout=COMMAND_TIMEOUT_SECONDS,
                capture_output=True, text=True,
                env={key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ},
            )
        except subprocess.CalledProcessError:
            raise _invalid() from None
        except (subprocess.TimeoutExpired, OSError):
            raise ExternalSchematicUpstreamError("회로도 변환기를 사용할 수 없습니다.") from None
    try:
        pages = tuple(int(value) for value in result.stdout.strip().split(",") if value != "")
    except ValueError:
        raise _invalid() from None
    if not pages or len(pages) > MAX_SHEETS or any(index < 0 for index in pages):
        raise _invalid()
    return pages


def _pdf_identity_text(data: bytes, *, require_circuit: bool = False) -> str:
    """Extract a bounded amount of PDF text in the same worker boundary as page inspection."""
    if not isinstance(data, bytes) or len(data) > MAX_PDF_BYTES:
        raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-pdf-text-") as temporary:
        path = Path(temporary) / "input.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.projects.schematic_render",
                 "inspect-published-pdf" if require_circuit else "inspect-pdf-text", str(path)],
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
    stem = unquote(source_file or urlsplit(source_url).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    stem = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem)
    query_identity = _identity_compact(canonical_product_query(query))
    format_words = _IDENTITY_STOPWORDS | {
        "public", "products", "schem", "sch", "print", "schaltplan", "page", "sheet",
        "rev", "revision", "version", "optimized", "large", "small", "medium", "guide",
    }
    # shortcut: compare named project identities, not pixels; opaque/mislabelled assets need content review.
    known_board = any(_identity_compact(alias) in query_identity
                      for aliases in _MANUFACTURER_ALIASES.values() for alias in aliases)
    if known_board and not re.fullmatch(r"[0-9a-f\s-]+", stem, re.I):
        for word in set(re.findall(r"[a-z]{3,}", canonical_product_query(stem).casefold())) - format_words:
            identity = "qtpy" if word == "qtrp" else word
            if identity not in query_identity:
                raise _invalid()
    requested = _pico_variant(_identity_compact(canonical_product_query(query)))
    actual = _pico_variant(filename)
    if requested and actual and requested != actual:
        raise _invalid()


def _verify_public_identity(query: str, *, title: str, page_url: str, source_file: str,
                            source_url: str, kind: str, pdf_text: str = "", linked_identity: str = "") -> None:
    """Reject a valid image/PDF whose board variant is not the requested one."""
    _verify_artifact_name(query, source_file, source_url, title)
    query = _VOLTAGE.sub(lambda match: "".join(match.groups()), canonical_product_query(query))
    from backend.projects.external_circuit_search import component_evidence_matches, component_context
    if component_context(query) == "diode" and not component_evidence_matches(query, " ".join((title, page_url, source_file, source_url, pdf_text))):
        raise _invalid()
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
    if component_context(query) == "diode" and not component_evidence_matches(
            query, " ".join((title, page_url, source_file, source_url, pdf_text))):
        raise _invalid()
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


def _verify_image_page(page_url: str, source_url: str, *, client=None) -> str:
    from backend.projects.external_circuit_search import _page_assets

    if not page_url or page_url == source_url:
        raise _invalid()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return _verify_image_page(page_url, source_url, client=owned)
    # Search also reads the HTML counterpart of an indexed Markdown page.
    page_url = page_url[:-3] if page_url.endswith(".md") else page_url
    # shortcut: verify publisher evidence, not image semantics; use content review if mislabelling persists.
    for url, label in _page_assets(page_url, client=client, required=True, require_schematic_context=True):
        if url == source_url:
            return label
    raise _invalid()


def inspect_public_schematic(url: str, kind: str, query: str, *, title: str = "",
                             page_url: str = "", source_file: str = "",
                             client: httpx.Client | None = None) -> tuple[str, int]:
    """Download, identify, and fingerprint one public schematic in one pass."""
    from backend.projects.external_circuit_search import english_official_document_url
    if english_official_document_url(url) != url:
        raise _invalid()
    if kind == 'pdf' and _is_tsc_datasheet(url):
        if not _is_tsc_datasheet(page_url):
            raise _invalid()
        data, _ = _public_asset(url, kind, client=client)
        pages = _bounded_pdf_schematic_pages(data, tsc_query=query)
        return hashlib.sha256(data).hexdigest(), len(pages)
    official_manufacturer = _semiconductor_official_manufacturer(url) if kind == "pdf" else None
    if official_manufacturer:
        state = _PDF_REQUEST.get()
        data, _ = _official_pdf_download(url, official_manufacturer, client)
        pages = _official_pdf_pages(data, query, official_manufacturer, url)
        digest = hashlib.sha256(data).hexdigest()
        if state is not None and len(data) <= MAX_PDF_BYTES:
            with state['lock']:
                if len(state['prepared']) == 2:
                    state['prepared'].pop(0)
                state['prepared'].append(_CheckedOfficialPDF(url, query, official_manufacturer, digest, pages, data))
        return digest, len(pages)
    _verify_artifact_name(query, source_file, url, title)
    publisher_label = ''
    if kind in {"png", "svg"}:
        publisher_label = _verify_image_page(page_url, url, client=client)
    data, _ = _public_asset(url, kind, client=client)
    pdf_text = _pdf_identity_text(data) if kind == "pdf" else ""
    linked_identity = ""
    if kind == "pdf" and not _voltage_tokens(pdf_text) and not _voltage_tokens(query) <= _voltage_tokens(
            " ".join((source_file, url))):
        linked_identity = _official_link_identity(canonical_product_query(query), page_url, url, client=client)
    _verify_public_identity(query, title=title, page_url=page_url, source_file=source_file,
                            source_url=url, kind=kind, pdf_text=pdf_text, linked_identity=linked_identity)
    from backend.projects.external_circuit_search import _manufacturer_for
    if _manufacturer_for(page_url) or _manufacturer_for(url):
        proof = _identity_compact(canonical_product_query(
            f'{source_file} {url} {pdf_text} {publisher_label} {linked_identity}'))
        if any(term not in proof for term in _identity_terms(canonical_product_query(query))):
            raise _invalid()
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


def _verify_pdf_circuit(document):
    """Conservative vector-content heuristic; it does not establish design correctness."""
    import ctypes
    from collections import Counter
    import pypdfium2 as pdfium

    if len(document) != 1 or _pdf_creator_is_pcbnew(document):
        raise _invalid()
    page = document[0]
    try:
        textpage = page.get_textpage()
        try:
            if textpage.count_chars() > MAX_PDF_TEXT_BYTES:
                raise _invalid()
            text = textpage.get_text_range()
        finally:
            textpage.close()
        refs = set(re.findall(r'\b(?:IC|R|C|D|Q|U|L)\d{1,4}\b', text.upper()))
        if (len(refs) < 6 or len({re.sub(r'\d+', '', ref).upper() for ref in refs}) < 2
                or is_non_circuit_asset('', text)
                or any(marker in _identity_compact(text) for marker in _NON_SCHEMATIC_DOCUMENT_MARKERS)):
            raise _invalid()
        lines, segments = set(), 0
        for count, obj in enumerate(page.get_objects(max_depth=1), 1):
            if count > 10000 or obj.type in {pdfium.raw.FPDF_PAGEOBJ_IMAGE, pdfium.raw.FPDF_PAGEOBJ_FORM}:
                raise _invalid()
            if obj.type != pdfium.raw.FPDF_PAGEOBJ_PATH:
                continue
            previous = None
            matrix = obj.get_matrix()
            for index in range(pdfium.raw.FPDFPath_CountSegments(obj)):
                segments += 1
                if segments > 50000:
                    raise _invalid()
                segment = pdfium.raw.FPDFPath_GetPathSegment(obj, index)
                x, y = ctypes.c_float(), ctypes.c_float()
                if not pdfium.raw.FPDFPathSegment_GetPoint(segment, x, y):
                    raise _invalid()
                point = matrix.on_point(x.value, y.value)
                if not all(math.isfinite(v) for v in point):
                    raise _invalid()
                if previous and pdfium.raw.FPDFPathSegment_GetType(segment) == pdfium.raw.FPDF_SEGMENT_LINETO:
                    dx, dy = abs(point[0]-previous[0]), abs(point[1]-previous[1])
                    if (5 <= dx < page.get_width()*.8 and dy < .1) or (5 <= dy < page.get_height()*.8 and dx < .1):
                        lines.add(tuple(sorted((tuple(round(v*2) for v in previous), tuple(round(v*2) for v in point)))))
                previous = point
        ends = Counter(point for line in lines for point in line)
        if len(lines) < 8 or sum(count >= 3 for count in ends.values()) < 2:
            raise _invalid()
    finally:
        page.close()


def inspect_published_pdf(url: str, query: str, *, page_url: str, source_file: str,
                          client: httpx.Client | None = None) -> tuple[str, int]:
    """Require publisher linkage and document content; metadata cannot prove either."""
    _verify_artifact_name(query, source_file, url, '')
    label = _verify_image_page(page_url, url, client=client)
    terms = _identity_terms(canonical_product_query(query))
    def matches(value):
        value = canonical_product_query(value).casefold()
        return terms and all(re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])', value) for term in terms)
    if not matches(label):
        raise _invalid()
    data, _ = _public_asset(url, 'pdf', client=client)
    text = _pdf_identity_text(data, require_circuit=True)
    if not any(matches(line) for line in text.splitlines() if len(line) <= 200):
        raise _invalid()
    _verify_public_identity(query, title='', page_url=page_url, source_file=source_file,
                            source_url=url, kind='pdf', pdf_text=text)
    return hashlib.sha256(data).hexdigest(), 1


def render_public_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None) -> tuple[bytes, ...]:
    """Re-fetch a discovered public asset, verify its fingerprint, and rasterize it."""
    from backend.projects.external_circuit_search import english_official_document_url
    if english_official_document_url(source.source_url) != source.source_url:
        raise _invalid()
    if (source.source_type not in {"manufacturer_official", "public_web"}
            or not isinstance(source.source_url, str)
            or not isinstance(source.source_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source.source_sha256)
            or source.asset_kind not in {"png", "svg", "pdf"}
            or type(source.expected_sheets) is not int or not 1 <= source.expected_sheets <= MAX_SHEETS):
        raise _invalid()
    manufacturer = (_semiconductor_official_manufacturer(source.source_url)
                    if source.asset_kind == 'pdf' else None)
    prepared = _take_checked_pdf(source, manufacturer) if manufacturer else None
    if prepared is not None:
        data = prepared.data
    elif manufacturer:
        data, _ = _official_pdf_download(source.source_url, manufacturer, client)
    else:
        data, _ = _public_asset(source.source_url, source.asset_kind, client=client)
    if hashlib.sha256(data).hexdigest() != source.source_sha256:
        raise _invalid()
    pages = None
    if source.asset_kind == "png":
        _valid_png(data)
    elif source.asset_kind == "svg":
        _svg(data)
    else:
        if manufacturer:
            if prepared is not None:
                pages = prepared.pages
                _record_pdf_work(_pdf_work(source.source_url, manufacturer), reuses=1)
            else:
                pages = _official_pdf_pages(data, source.model, manufacturer, source.source_url)
        else:
            pages = _bounded_pdf_schematic_pages(
                data, tsc_query=source.model if _is_tsc_datasheet(source.source_url) else None)
        if len(pages) != source.expected_sheets:
            raise _invalid()
    with tempfile.TemporaryDirectory(prefix="sojafit-public-render-") as temporary:
        work = Path(temporary)
        path = work / (source.source_file or f"schematic.{source.asset_kind}")
        path.write_bytes(data)
        activity = _pdf_work(source.source_url, manufacturer) if manufacturer else None
        started = time.perf_counter()
        try:
            sheets = _sheets(source.asset_kind, path, work / "pages", pdf_pages=pages if source.asset_kind == "pdf" else None)
        finally:
            _record_pdf_work(activity, conversion_ms=round((time.perf_counter() - started) * 1000, 3))
    if len(sheets) != source.expected_sheets:
        raise _invalid()
    return sheets


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == 'inspect-tsc-pdf':
        if os.name == 'posix':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        try:
            print(','.join(map(str, _tsc_application_pages(Path(sys.argv[2]).read_bytes(), sys.argv[3]))))
        except (ExternalSchematicInvalidSource, OSError, ValueError, RuntimeError):
            raise SystemExit(1)
    elif len(sys.argv) == 5 and sys.argv[1] == "inspect-official-pdf":
        try:
            pages = _official_application_pages(Path(sys.argv[2]).read_bytes(), sys.argv[3], sys.argv[4])
            print(",".join(str(index) for index in pages))
        except (ExternalSchematicInvalidSource, OSError, ValueError, RuntimeError):
            raise SystemExit(1)
    elif len(sys.argv) >= 3 and sys.argv[1] == "inspect-pdf":
        try:
            pages = _pdf_schematic_pages(Path(sys.argv[2]).read_bytes())
            print(",".join(str(index) for index in pages))
        except (ExternalSchematicInvalidSource, OSError, ValueError):
            raise SystemExit(1)
    elif len(sys.argv) >= 3 and sys.argv[1] in {"inspect-pdf-text", "inspect-published-pdf"}:
        try:
            if sys.argv[1] == 'inspect-published-pdf' and sys.platform == 'linux':
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
            import pypdfium2 as pdfium
            document = pdfium.PdfDocument(Path(sys.argv[2]).read_bytes())
            try:
                if sys.argv[1] == 'inspect-published-pdf':
                    _verify_pdf_circuit(document)
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
