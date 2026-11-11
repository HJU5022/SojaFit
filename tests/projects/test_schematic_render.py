"""고정 commit 원본 렌더러의 형식, 완전성, 리소스 경계."""
import io
import subprocess
import zipfile
from dataclasses import replace

import httpx
import pytest
from PIL import Image

from backend.projects import schematic_render as render
from backend.projects.schematic_source import (
    ExternalSchematicInvalidSource, ExternalSchematicUpstreamError, VerifiedSchematicSource,
)


SOURCE = VerifiedSchematicSource("a/b", "a" * 40, "MIT", "a", "", "", "board.kicad_sch",
                                 "png", ("board.png",), "board.kicad_sch")


def picture(kind, colors):
    pages = [Image.new("RGB", (20, 10), color) for color in colors]
    stream = io.BytesIO()
    options = {"save_all": True, "append_images": pages[1:]} if kind == "PDF" else {}
    pages[0].save(stream, format=kind, **options)
    return stream.getvalue()


def fetch(data, mime, kind="png", **kwargs):
    source = replace(SOURCE, asset_kind=kind, asset_paths=(f"board.{kind}",) if kind != "kicad" else ())
    if "expected_sheets" in kwargs:
        source = replace(source, expected_sheets=kwargs.pop("expected_sheets"))
    expected = (f"https://codeload.github.com/a/b/zip/{SOURCE.commit}" if kind == "kicad" else
                f"https://raw.githubusercontent.com/a/b/{SOURCE.commit}/board.{kind}")

    def respond(request):
        assert str(request.url) == expected
        return httpx.Response(200, headers={"Content-Type": mime}, content=data)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        return render.render_external_schematic(source, client=client, **kwargs)


def bundle(files, link=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            entry = zipfile.ZipInfo(f"b-{SOURCE.commit}/{name}")
            if link:
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
            z.writestr(entry, data)
    return stream.getvalue()


def test_png_returns_exact_bytes():
    png = picture("PNG", ["red"])
    assert fetch(png, "image/png") == (png,)


def test_png_rejects_magic_mime_and_dimensions(monkeypatch):
    png = picture("PNG", ["red"])
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(png, "application/pdf")
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(b"GIF89a", "image/png")
    monkeypatch.setattr(render, "MAX_PIXELS", 199)
    with pytest.raises(ExternalSchematicInvalidSource):
        render._valid_png(png)
    monkeypatch.setattr(render, "MAX_IMAGE_BYTES", len(png) - 1)
    with pytest.raises(ExternalSchematicInvalidSource):
        render._valid_png(png)


def test_svg_rasterizes_visible_geometry():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"><rect width="20" height="10" fill="red"/></svg>'
    png, = fetch(svg, "text/plain", "svg")
    with Image.open(io.BytesIO(png)) as img:
        assert img.size == (20, 10) and img.getpixel((3, 3))[:3] == (255, 0, 0)


@pytest.mark.parametrize("body", [
    b"<script/>", b"<foreignObject/>", b'<g onclick="a"/>', b'<use href="https://unsafe.example"/>',
    b'<g style="fill:url(file:///tmp/x)"/>', b'<style>@import "https://unsafe.example";</style>',
    b'<use xml:base="file:///tmp/x" href="#x"/>', b"<g/>" * 50_000,
])
def test_svg_rejects_active_content_and_node_limit(body):
    with pytest.raises(ExternalSchematicInvalidSource):
        render._svg(b'<svg width="10" height="10">' + body + b"</svg>")


@pytest.mark.parametrize("data", [
    b'<!DOCTYPE svg [<!ENTITY e "d">]><svg/>', b'<svg width="999999" height="999999"/>',
])
def test_svg_rejects_entity_and_pixel_overflow(data):
    with pytest.raises(ExternalSchematicInvalidSource):
        render._svg(data)


def test_pdf_renders_every_page_in_order_and_rejects_partial_pair():
    pdf = picture("PDF", ["red", "blue"])
    pages = fetch(pdf, "application/pdf", "pdf", expected_sheets=2)
    assert len(pages) == 2
    for index, data in enumerate(pages):
        with Image.open(io.BytesIO(data)) as image:
            assert image.size[0] >= 80 and image.size[1] >= 40
            assert image.getpixel((2, 2))[index * 2] > 240
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(pdf, "application/pdf", "pdf", expected_sheets=1)


def test_pdf_rejects_page_and_byte_limits(monkeypatch, tmp_path):
    pdf = picture("PDF", ["red"] * 21)
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(pdf, "application/pdf", "pdf")
    monkeypatch.setattr(render, "MAX_PDF_BYTES", len(pdf) - 1)
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(pdf, "application/pdf", "pdf")


@pytest.mark.parametrize(("creator", "rejected"), [("Pcbnew-PDF", True), ("Eeschema-PDF", False), ("", False)])
def test_pdf_creator_identifies_pcbnew_exports(creator, rejected):
    stream = io.BytesIO()
    Image.new("RGB", (20, 10), "red").save(stream, format="PDF", creator=creator)
    data = stream.getvalue()
    if rejected:
        with pytest.raises(ExternalSchematicInvalidSource):
            fetch(data, "application/pdf", "pdf")
    else:
        assert len(fetch(data, "application/pdf", "pdf")) == 1


def test_kicad_archive_renders_whole_hierarchy_and_rejects_partial_pdf():
    archive = bundle({"board.kicad_sch": '(kicad_sch (sheet (property "Sheetfile" "child.kicad_sch")))',
                      "child.kicad_sch": "(kicad_sch)", "sym-lib-table": "not supplied to KiCad"})

    def exporter(root, output):
        assert root.name == "board.kicad_sch"
        assert sorted(p.name for p in root.parent.iterdir()) == ["board.kicad_sch", "child.kicad_sch"]
        path = output / "out.pdf"
        path.write_bytes(picture("PDF", colors))
        return "fixture", path

    colors = ["blue", "red"]
    assert len(fetch(archive, "application/zip", "kicad", kicad_export=exporter, expected_sheets=2)) == 2
    colors.pop()
    with pytest.raises(ExternalSchematicInvalidSource):
        fetch(archive, "application/zip", "kicad", kicad_export=exporter, expected_sheets=2)


@pytest.mark.parametrize("files,link", [
    ({"../escape": ""}, False), ({"board.kicad_sch": ""}, True),
    ({"A": "", "a": ""}, False),
    ({"board.kicad_sch": '(kicad_sch (sheet (property "Sheetfile" "../file.kicad_sch")))'}, False),
    ({"board.kicad_sch": '(kicad_sch (sheet (property "Sheetfile" "\u0024{HOME}/secret.kicad_sch")))'}, False),
    ({"board.kicad_sch": '(kicad_sch (sheet (property "Sheetfile" "missing.kicad_sch")))'}, False),
    ({"board.kicad_sch": '(kicad_sch (sheet (property "Sheetfile" "board.kicad_sch")))'}, False),
    ({"board.kicad_sch": '(kicad_sch (symbol (lib_id "Device:R")))'}, False),
])
def test_archive_rejects_unsafe_or_missing_dependencies(files, link, tmp_path):
    with pytest.raises(ExternalSchematicInvalidSource):
        render._archive(SOURCE, bundle(files, link), tmp_path)


def test_archive_size_limits(monkeypatch, tmp_path):
    archive = bundle({"board.kicad_sch": "(kicad_sch)"})
    monkeypatch.setattr(render, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 4)
    with pytest.raises(ExternalSchematicInvalidSource):
        render._archive(SOURCE, archive, tmp_path)
    monkeypatch.setattr(render, "MAX_ARCHIVE_BYTES", len(archive) - 1)
    with pytest.raises(ExternalSchematicInvalidSource):
        render._archive(SOURCE, archive, tmp_path)


def test_raster_worker_timeout_is_sanitized(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("private", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    path = tmp_path / "input"
    path.write_bytes(b"")
    with pytest.raises(ExternalSchematicUpstreamError):
        render._sheets("pdf", path, tmp_path / "out")


def test_kicad_pdf_cli_is_bounded_and_uses_only_conversion_environment(monkeypatch, tmp_path):
    from backend.projects import schematic

    calls = []

    def run(command, **options):
        calls.append((command, options))
        return type("Result", (), {"stdout": "9.0.2\n"})()

    monkeypatch.setattr(schematic.subprocess, "run", run)
    version, pdf = schematic.run_kicad_pdf(tmp_path / "board.kicad_sch", tmp_path)
    assert version == "9.0.2"
    assert calls[1][0][-6:] == ["sch", "export", "pdf", "--output", str(pdf), str(tmp_path / "board.kicad_sch")]
    assert all(options["timeout"] == schematic.COMMAND_TIMEOUT_SECONDS
               and set(options["env"]) == {"PATH", "HOME"} for _, options in calls)


def test_kicad_pdf_timeout_is_a_service_error(monkeypatch, tmp_path):
    from backend.projects import schematic

    def timeout(*args, **kwargs):
        raise schematic.subprocess.TimeoutExpired("private input", 1)

    monkeypatch.setattr(schematic.subprocess, "run", timeout)
    with pytest.raises(schematic.KicadServiceUnavailable):
        schematic.run_kicad_pdf(tmp_path / "board.kicad_sch", tmp_path)
