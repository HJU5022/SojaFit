"""고정 commit 원본 렌더러의 형식, 완전성, 리소스 경계."""
import io
import base64
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


def test_diode_query_rejects_radio_transceiver_artifact():
    with pytest.raises(ExternalSchematicInvalidSource):
        render._verify_public_identity(
            "SS33 diode", title="RANGER SS33 SCH Service Manual",
            page_url="https://example.org/ranger_ss33_sch.pdf/download.html",
            source_file="ranger_ss33_sch.pdf_1.png",
            source_url="https://example.org/ranger_ss33_sch.pdf_1.png",
            kind="png",
        )


def picture(kind, colors):
    pages = [Image.new("RGB", (20, 10), color) for color in colors]
    stream = io.BytesIO()
    options = {"save_all": True, "append_images": pages[1:]} if kind == "PDF" else {}
    pages[0].save(stream, format=kind, **options)
    return stream.getvalue()


def schematic_picture():
    stream = io.BytesIO()
    Image.new("RGB", (128, 128), "red").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def verified_image_page(monkeypatch):
    # Identity/size unit tests isolate the page gate; its HTTP boundary is tested separately.
    monkeypatch.setattr(render, "_verify_image_page", lambda *args, **kwargs: None)


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


def public_source(url, kind, digest, count=1):
    return VerifiedSchematicSource(
        "", "", "미확인", "공개 출처", url, url, f"schematic.{kind}", kind, (),
        f"schematic.{kind}", count, "public_web", 3, None, None, None, digest, None,
    )


def test_public_png_fingerprint_and_render_recheck_hash(monkeypatch):
    png = picture("PNG", ["red"])
    url = "https://assets.example.test/schematic.png"

    def respond(request):
        return httpx.Response(200, headers={"Content-Type": "image/png"}, content=png)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        digest, count = render.fingerprint_public_schematic(url, "png", client=client)
        assert count == 1
        monkeypatch.setattr(render, "_sheets", lambda kind, path, output, **kwargs: (png,))
        source = public_source(url, "png", digest)
        assert render.render_public_schematic(source, client=client) == (png,)

        bad = public_source(url, "png", "0" * 64)
        with pytest.raises(ExternalSchematicInvalidSource):
            render.render_public_schematic(bad, client=client)


def test_public_rejects_private_host_and_wrong_mime():
    png = picture("PNG", ["red"])
    private = "https://127.0.0.1/schematic.png"
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"Content-Type": "image/png"}, content=png))) as client:
        with pytest.raises(ExternalSchematicInvalidSource):
            render.fingerprint_public_schematic(private, "png", client=client)
        with pytest.raises(ExternalSchematicInvalidSource):
            render.fingerprint_public_schematic("https://assets.example.test/schematic.png", "pdf", client=client)


def test_public_pdf_fingerprint_is_single_page_only():
    pdf = picture("PDF", ["red"])
    url = "https://assets.example.test/schematic.pdf"

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"Content-Type": "application/pdf"}, content=pdf))) as client:
        digest, count = render.fingerprint_public_schematic(url, "pdf", client=client)
    assert len(digest) == 64 and count == 1


@pytest.mark.parametrize("url,title", [
    ("https://example.org/symbol-library/schematic/driver.png", "Adafruit MOSFET Driver"),
    ("https://example.org/symbol%2Dlibrary/schematic/driver.svg", "Adafruit MOSFET Driver"),
    ("https://example.org/schematic.png", "Adafruit MOSFET Driver module symbol"),
    ("https://example.org/pinout/driver-schematic.pdf", "Adafruit MOSFET Driver"),
    ("https://example.org/driver-schematic.pdf", "Adafruit MOSFET Driver block diagram"),
])
def test_symbol_asset_is_rejected_before_download(monkeypatch, url, title):
    monkeypatch.setattr(render, "_public_asset", lambda *a, **kw: pytest.fail("unexpected symbol download"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(url, "png", "Adafruit MOSFET Driver", title=title,
                                        source_file=url.rsplit("/", 1)[-1])


@pytest.mark.parametrize("html", [
    '<title>Adafruit MOSFET Driver schematic</title><h1>Schematic</h1><img src="/assets/driver.png">',
    '<h2>Downloads</h2><a href="/other.png">Schematic</a><img src="/assets/driver.png">',
    '<h2>Schematic</h2><h2>Product images</h2><img src="/assets/driver.png">',
])
def test_unmarked_image_requires_file_specific_schematic_evidence(html):
    png = schematic_picture()
    url = "https://example.org/assets/driver.png"
    requests = []
    def handle(request):
        requests.append(str(request.url))
        if str(request.url) == url:
            return httpx.Response(200, headers={"Content-Type": "image/png"}, content=png)
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=html)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ExternalSchematicInvalidSource):
            render.inspect_public_schematic(url, "png", "Adafruit MOSFET Driver",
                title="Adafruit MOSFET Driver schematic", page_url="https://example.org/driver", client=client)
    assert url not in requests


@pytest.mark.parametrize("kind,html", [
    ("png", '<h2>Schematic and Fab Print</h2><img src="/assets/driver.png">'),
    ("png", '<h2>Downloads</h2><a href="/assets/driver.png">Circuit diagram</a>'),
    ("svg", '<h2>Downloads</h2><img src="/assets/driver.svg" alt="Schematic">'),
])
def test_unmarked_normal_image_retains_exact_page_evidence(kind, html):
    data = schematic_picture() if kind == "png" else b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150"><path d="M10 10L100 100"/></svg>'
    url = "https://example.org/assets/driver." + kind
    def handle(request):
        if str(request.url) == url:
            return httpx.Response(200, headers={"Content-Type": "image/png" if kind == "png" else "image/svg+xml"}, content=data)
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text=html)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        digest, count = render.inspect_public_schematic(url, kind, "Adafruit MOSFET Driver",
            title="Adafruit MOSFET Driver", page_url="https://example.org/driver.md", client=client)
    assert len(digest) == 64 and count == 1


def test_image_page_rate_limit_is_not_hidden():
    from backend.projects.schematic_source import ExternalSchematicRateLimited
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "77"}))) as client:
        with pytest.raises(ExternalSchematicRateLimited) as error:
            render.inspect_public_schematic("https://example.org/assets/driver.png", "png", "Driver",
                page_url="https://example.org/driver", client=client)
    assert error.value.retry_after == 77


def test_image_direct_url_without_page_evidence_is_rejected(monkeypatch):
    monkeypatch.setattr(render, "_public_asset", lambda *a, **kw: pytest.fail("unexpected unverified image download"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic("https://example.org/driver.png", "png", "Driver",
                                        title="Driver schematic", page_url="https://example.org/driver.png")


def test_small_public_schematic_survives_symbol_guard():
    stream = io.BytesIO()
    Image.new("RGB", (333, 208), "white").save(stream, format="PNG")
    url = "https://circuitcanvas.b-cdn.net/projects/adafruit-mosfet-driver-circuit-schematic.png"
    def handle(request):
        if str(request.url) == url:
            return httpx.Response(200, headers={"Content-Type": "image/png"}, content=stream.getvalue())
        return httpx.Response(200, headers={"Content-Type": "text/html"},
                              text=f'<h2>Circuit diagram</h2><img src="{url}">')
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        digest, sheets = render.inspect_public_schematic(
            url, "png", "Adafruit MOSFET Driver",
            title="Adafruit MOSFET Driver complete circuit schematic with MOSFET symbols",
            source_file=url.rsplit("/", 1)[-1], page_url="https://circuitcanvas.b-cdn.net/projects/driver", client=client,
        )
    assert len(digest) == 64 and sheets == 1


@pytest.mark.parametrize("filename", ["pico-datasheet.pdf", "pico-product-brief.pdf",
                                      "pico-2-schematic.pdf", "pico-2-w-schematic.pdf"])
def test_incompatible_artifact_name_is_rejected_before_download(monkeypatch, filename):
    monkeypatch.setattr(render, "_public_asset", lambda *a, **kw: pytest.fail("unexpected download"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic("https://example.org/" + filename, "pdf", "Raspberry Pi Pico",
                                        source_file=filename)


def test_schematic_in_datasheets_directory_is_not_a_datasheet():
    render._verify_public_identity(
        "Sensor", title="Sensor schematic", page_url="https://example.org/board/",
        source_file="sensor-schematic.pdf", source_url="https://example.org/datasheets/sensor-schematic.pdf",
        kind="pdf", pdf_text="Sensor schematic",
    )


@pytest.mark.parametrize("requested", ["Pico", "Pico W", "Pico 2", "Pico 2 W"])
@pytest.mark.parametrize("artifact", ["Pico", "Pico W", "Pico 2", "Pico 2 W"])
def test_public_identity_distinguishes_pico_generations_and_wireless(requested, artifact):
    filename = artifact.replace(" ", "-") + "-schematic.pdf"
    kwargs = dict(title="Raspberry Pi " + requested,
                  page_url="https://www.raspberrypi.com/pico-series/",
                  source_file=filename, source_url="https://example.org/" + filename,
                  kind="pdf", pdf_text="Raspberry Pi " + artifact)
    if requested == artifact:
        render._verify_public_identity("Raspberry Pi " + requested, **kwargs)
    else:
        with pytest.raises(ExternalSchematicInvalidSource):
            render._verify_public_identity("Raspberry Pi " + requested, **kwargs)


def test_public_identity_rejects_wrong_board_variant_from_pdf_text(monkeypatch):
    pdf = picture("PDF", ["red"])
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (pdf, "application/pdf"))
    monkeypatch.setattr(render, "_pdf_identity_text", lambda data: "SparkFun RedBoard Artemis schematic")
    monkeypatch.setattr(render, "_bounded_pdf_schematic_pages", lambda data: (0,))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(
            "https://cdn.sparkfun.com/RedBoardArtemisSchematic.pdf", "pdf",
            "SparkFun RedBoard Artemis ATP", title="SparkFun RedBoard Artemis ATP",
        )


def test_atp_request_rejects_generic_redboard_file_even_if_pdf_mentions_atp(monkeypatch):
    pdf = picture("PDF", ["red"])
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (pdf, "application/pdf"))
    monkeypatch.setattr(render, "_pdf_identity_text", lambda data: "RedBoard Artemis ATP schematic")
    monkeypatch.setattr(render, "_bounded_pdf_schematic_pages", lambda data: (0,))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(
            "https://cdn.sparkfun.com/RedBoardArtemisSchematic.pdf", "pdf",
            "SparkFun RedBoard Artemis ATP schematic", title="RedBoard Artemis ATP",
        )


@pytest.mark.parametrize(("query", "url", "title"), [
    ("SparkFun TMP102 Breakout", "https://cdn.sparkfun.com/SparkFun_TMP102_Qwiic-Schematic.pdf", "TMP102 Qwiic"),
    ("Teensy 4.0", "https://download.example/click-shield-for-teensy-4-schematic.pdf", "Click shield for Teensy 4.0"),
    ("SparkFun Qwiic OLED Display", "https://cdn.sparkfun.com/zio_qwiic_oled_schematic.pdf", "Zio Qwiic OLED Display"),
    ("Raspberry Pi Zero 2 W", "https://example.org/raspberry-pi-zero-2-w-reduced-schematics.pdf", "Raspberry Pi Zero 2 W reduced schematics"),
    ("Teensy LC", "https://www.pjrc.com/teensy/schematic41.png", "Teensy schematic"),
    ("SparkFun TMP102", "https://cdn.sparkfun.com/TMP102-Qwiic-Schematic.pdf", "SparkFun TMP102"),
    ("Arduino Nano", "https://docs.arduino.cc/resources/schematics/Nano-Every-schematics.pdf", "Arduino Nano"),
])
def test_public_identity_rejects_observed_mismatches(monkeypatch, verified_image_page, query, url, title):
    png = picture("PNG", ["red"])
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(url, "png", query, title=title)


@pytest.mark.parametrize('query,url,title,text,accepted', [
    ('Pololu DRV8833 Dual Motor Driver', 'https://circuitdigest.com/DRV8833-with-Arduino-Circuit-Diagram.png', 'Interfacing DRV8833 with Arduino', '', False),
    ('Pololu DRV8833 Dual Motor Driver', 'https://a.pololu-files.com/picture/0J3872.png', 'Pololu DRV8833 schematic', '', True),
    ('Teensy 4.0', 'https://www.pjrc.com/teensy/schematic40.png', 'Teensy schematic', '', True),
    ('Raspberry Pi Pico', 'https://example.org/RPI-PICO-schematic.pdf', 'Pico schematic', 'RPI-PICO schematic', True),
    ('Adafruit MOSFET Driver', 'https://cdn-learn.adafruit.com/driver.png', 'MOSFET Driver schematic', '', True),
])
def test_requested_manufacturer_identity_is_preserved(query, url, title, text, accepted):
    kwargs = dict(title=title, page_url=url, source_url=url, source_file=url.rsplit('/', 1)[-1],
                  kind='pdf' if text else 'png', pdf_text=text)
    if accepted:
        render._verify_public_identity(query, **kwargs)
    else:
        with pytest.raises(ExternalSchematicInvalidSource):
            render._verify_public_identity(query, **kwargs)


def test_public_identity_accepts_matching_official_png(monkeypatch, verified_image_page):
    png = schematic_picture()
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    digest, count = render.inspect_public_schematic(
        "https://cdn-learn.adafruit.com/assets/adafruit_products_schem.png",
        "png", "Adafruit MOSFET Driver STEMMA", title="Adafruit MOSFET Driver STEMMA",
    )
    assert len(digest) == 64 and count == 1


@pytest.mark.parametrize(("query", "url", "title"), [
    ("Raspberry Pi Pico schematic", "https://example.org/raspberry-pico-w-schematics.pdf", "Raspberry Pi Pico W schematic"),
    ("Pololu DRV8833 Dual Motor Driver schematic", "https://example.org/DRB8833-schematic.png", "DRV8833 dual motor driver"),
    ("SparkFun RedBoard Artemis ATP schematic", "https://example.org/RedBoard-Artemis-Whitesheet.pdf", "SparkFun RedBoard Artemis ATP"),
])
def test_public_identity_rejects_live_false_positive_variants(monkeypatch, verified_image_page, query, url, title):
    png = picture("PNG", ["red"])
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(url, "png", query, title=title)


@pytest.mark.parametrize(("query", "url", "title"), [
    ("Raspberry Pi Pico W", "https://example.org/raspberry-pi-pico-schematic.png", "Raspberry Pi Pico schematic"),
    ("Raspberry Pi Pico", "https://example.org/raspberry-pi-pico-w-schematic.png", "Raspberry Pi Pico W schematic"),
    ("라즈베리파이 피코 W", "https://example.org/raspberry-pi-pico-schematic.png", "Raspberry Pi Pico schematic"),
    ("라즈베리 파이 피코 W", "https://example.org/raspberry-pi-pico-schematic.png", "Raspberry Pi Pico schematic"),
    ("라즈베리파이 피코", "https://example.org/raspberry-pi-pico-w-schematic.png", "Raspberry Pi Pico W schematic"),
])
def test_public_identity_rejects_opposite_pico_variant(monkeypatch, verified_image_page, query, url, title):
    png = schematic_picture()
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(url, "png", query, title=title,
                                        page_url=url, source_file=url.rsplit("/", 1)[-1])


@pytest.mark.parametrize(("query", "url"), [
    ("Raspberry Pi Pico", "https://example.org/raspberry-pi-pico-schematic.png"),
    ("Raspberry Pi Pico W", "https://example.org/raspberry-pi-pico-w-schematic.png"),
    ("라즈베리파이 피코", "https://example.org/raspberry-pi-pico-schematic.png"),
    ("라즈베리파이 피코 W", "https://example.org/raspberry-pi-pico-w-schematic.png"),
    ("라즈베리 파이 피코 W", "https://example.org/raspberry-pi-pico-w-schematic.png"),
])
def test_public_identity_accepts_matching_pico_variant(monkeypatch, verified_image_page, query, url):
    png = schematic_picture()
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    digest, count = render.inspect_public_schematic(url, "png", query)
    assert len(digest) == 64 and count == 1


@pytest.mark.parametrize(("query", "page_url", "source_file", "source_url", "pdf_text"), [
    ("Raspberry Pi Pico W", "https://example.org/pico-w/", "pico-schematic.pdf",
     "https://example.org/files/pico-schematic.pdf", "Raspberry Pi Pico schematic"),
    ("Raspberry Pi Pico W", "https://example.org/pico-w/", "schematic.pdf",
     "https://example.org/files/schematic.pdf", "Raspberry Pi Pico schematic"),
    ("Raspberry Pi Pico W", "https://example.org/pico-w/", "pico-w-schematic.pdf",
     "https://example.org/files/pico-w-schematic.pdf", "Raspberry Pi Pico schematic"),
    ("Raspberry Pi Pico", "https://example.org/pico/", "pico-schematic.pdf",
     "https://example.org/files/pico-schematic.pdf", "Raspberry Pi Pico W schematic"),
])
def test_public_identity_rejects_pico_conflict_with_pdf_artifact(
        query, page_url, source_file, source_url, pdf_text):
    with pytest.raises(ExternalSchematicInvalidSource):
        render._verify_public_identity(
            query, title=query, page_url=page_url, source_file=source_file,
            source_url=source_url, kind="pdf", pdf_text=pdf_text,
        )


def test_public_identity_accepts_pico_w_confirmed_by_pdf_body():
    render._verify_public_identity(
        "Raspberry Pi Pico W", title="Raspberry Pi Pico W schematic",
        page_url="https://example.org/pico/", source_file="schematic.pdf",
        source_url="https://example.org/files/schematic.pdf", kind="pdf",
        pdf_text="Raspberry Pi Pico W schematic",
    )


def test_public_identity_rejects_pico_page_only_variant(monkeypatch):
    png = schematic_picture()
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(
            "https://example.org/files/pico-schematic.png", "png", "Raspberry Pi Pico W",
            title="Raspberry Pi Pico W", page_url="https://example.org/pico-w/",
            source_file="pico-schematic.png",
        )


def test_public_identity_allows_qt_py_rp2040_filename_with_title_model(monkeypatch, verified_image_page):
    png = schematic_picture()
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    digest, count = render.inspect_public_schematic(
        "https://cdn-learn.adafruit.com/assets/adafruit_products_QTRP_sch.png",
        "png", "Adafruit QT Py RP2040 schematic", title="Adafruit QT Py RP2040 Schematic and Fab Print",
    )
    assert len(digest) == 64 and count == 1


@pytest.mark.parametrize(("query", "url", "title"), [
    ("Adafruit ItsyBitsy RP2040", "https://cdn.adafruit.com/itsybitsy/adafruit_products_QTRP_sch.png", "Adafruit ItsyBitsy RP2040"),
    ("SparkFun RedBoard Artemis ATP", "https://cdn.sparkfun.com/assets/RedBoardArtemisSchematic.pdf", "RedBoard Artemis schematic"),
    ("SparkFun OpenLog Artemis", "https://cdn.sparkfun.com/assets/OpenLog_Artemis_9DoF_IMU_Schematic.pdf", "SparkFun OpenLog Artemis 9DoF IMU"),
    ("SparkFun TMP102 Breakout", "https://cdn.sparkfun.com/assets/TMP102_Hookup_Guide_Web.pdf", "TMP102 Hookup Guide"),
])
def test_public_identity_rejects_artifact_variant_mismatch(monkeypatch, verified_image_page, query, url, title):
    png = picture("PNG", ["red"])
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (png, "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(url, "png", query, title=title)


def test_public_identity_rejects_tiny_png(monkeypatch, verified_image_page):
    tiny = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(tiny, format="PNG")
    monkeypatch.setattr(render, "_public_asset", lambda *args, **kwargs: (tiny.getvalue(), "image/png"))
    with pytest.raises(ExternalSchematicInvalidSource):
        render.inspect_public_schematic(
            "https://files.seeedstudio.com/assets/optimized.png", "png",
            "Seeed XIAO ESP32C3", title="Seeed XIAO ESP32C3 schematic",
        )


def test_cloud_renderer_uses_audience_bound_identity_token(monkeypatch):
    from backend.projects import schematic

    calls = []
    monkeypatch.setenv("K_SERVICE", "sojafit-api")
    monkeypatch.setattr(httpx, "get", lambda url, **options: calls.append((url, options))
                        or httpx.Response(200, text="test-id-token", request=httpx.Request("GET", url)))

    assert schematic._renderer_headers("https://renderer.example.run.app") == {
        "Authorization": "Bearer test-id-token"}
    assert calls[0][1]["params"] == {"audience": "https://renderer.example.run.app"}
    assert calls[0][1]["headers"] == {"Metadata-Flavor": "Google"}
    with pytest.raises(schematic.KicadServiceUnavailable):
        schematic._renderer_headers("http://renderer:8000")


def test_remote_renderer_checks_png_and_expected_sheet_count(monkeypatch):
    from backend.projects import schematic

    source = replace(SOURCE, asset_kind="kicad", asset_paths=())
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setenv("KICAD_RENDERER_URL", "http://renderer:8000")
    png = picture("PNG", ["white"])

    def call_with(sheets):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"sheets": sheets})))
        try:
            return schematic.render_remote_kicad(source, client=client)
        finally:
            client.close()

    assert call_with([base64.b64encode(png).decode()]) == (png,)
    with pytest.raises(schematic.KicadServiceUnavailable):
        call_with([base64.b64encode(b"not a PNG").decode()])
    with pytest.raises(schematic.KicadServiceUnavailable):
        call_with([base64.b64encode(png).decode()] * 2)


def test_selected_kicad_downloads_each_file_once_and_counts_reused_sheet_instances(tmp_path):
    root = b'(kicad_sch (sheet (property "Sheetfile" "child.kicad_sch")) (sheet (property "Sheetfile" "child.kicad_sch")))'
    files = {'board.kicad_sch': root, 'child.kicad_sch': b'(kicad_sch)'}
    calls = []
    source = replace(SOURCE, asset_kind='kicad', asset_paths=tuple(files), expected_sheets=3)
    path, count = render._selected_kicad(source, lambda name: calls.append(name) or files[name], tmp_path)
    assert count == 3
    assert calls == list(files)
    assert path.read_bytes() == root


def test_selected_kicad_has_a_total_download_budget(tmp_path, monkeypatch):
    root = b'(kicad_sch (sheet (property "Sheetfile" "child.kicad_sch")))'
    files = {'board.kicad_sch': root, 'child.kicad_sch': b'(kicad_sch)'}
    source = replace(SOURCE, asset_kind='kicad', asset_paths=tuple(files), expected_sheets=2)
    monkeypatch.setattr(render, 'MAX_ARCHIVE_BYTES', sum(map(len,files.values()))-1)
    with pytest.raises(ExternalSchematicInvalidSource):
        render._selected_kicad(source, files.__getitem__, tmp_path)


def test_selected_kicad_accepts_multiline_quoted_fields_without_altering_original(tmp_path):
    raw = b'(kicad_sch (title_block (comment 1 "line one\nline two")))'
    source = replace(SOURCE, asset_kind='kicad', asset_paths=('board.kicad_sch',), expected_sheets=1)
    root, count = render._selected_kicad(source, lambda name: raw, tmp_path)
    assert count == 1
    assert root.read_bytes() == raw


def test_selected_kicad_streams_large_sheet_beyond_sexpr_token_limit(tmp_path):
    raw = (b'(kicad_sch (lib_symbols (symbol "Device:D")) '
           b'(symbol (lib_id "Device:D") (property "Reference" "D1") '
           b'(property "Value" "BAT54")) '
           + b'(wire (pts (xy 1 1) (xy 2 2))) ' * 25_000 + b')')
    source = replace(SOURCE, asset_kind='kicad', asset_paths=('board.kicad_sch',), expected_sheets=1)
    root, count = render._selected_kicad(source, lambda name: raw, tmp_path)
    assert count == 1
    assert root.read_bytes() == raw


def test_large_kicad_cannot_bypass_balanced_structure_validation(tmp_path):
    raw = (b'(kicad_sch (lib_symbols (symbol "Device:D")) '
           b'(symbol (lib_id "Device:D")) (title_block (comment "'
           + b'x' * 1_100_000 + b'"))')
    source = replace(SOURCE, asset_kind='kicad', asset_paths=('board.kicad_sch',), expected_sheets=1)
    with pytest.raises((ExternalSchematicInvalidSource, ValueError)):
        render._selected_kicad(source, lambda name: raw, tmp_path)

@pytest.mark.parametrize('page,linked,voltage,accepted', [
    ('https://www.sparkfun.com/board', True, '3.3 V', True),
    ('https://unverified.example.org/board', True, '3.3 V', False),
    ('https://www.sparkfun.com/board', False, '3.3 V', False),
    ('https://www.sparkfun.com/board', True, '33 V', False),
    ('https://www.sparkfun.com/board', True, 'unknown', False),
])
def test_textless_pdf_requires_actual_official_product_link(monkeypatch, page, linked, voltage, accepted):
    import httpx
    url = 'https://cdn.sparkfun.com/datasheets/Kits/Breadboard%20Power%20Supply%20v10.pdf'
    query = 'SparkFun Breadboard Power Supply 5V 3.3V'
    title = f'SparkFun Breadboard Power Supply 5 V/{voltage}'
    monkeypatch.setattr(render, '_public_asset', lambda *args, **kwargs: (b'pdf-placeholder', 'application/pdf'))
    monkeypatch.setattr(render, '_pdf_identity_text', lambda data: '\n')
    monkeypatch.setattr(render, '_bounded_pdf_schematic_pages', lambda data: (0,))
    def handle(request):
        assert request.method == 'GET' and str(request.url) == page
        href = url if linked else url.replace('v10.pdf', 'v20.pdf')
        return httpx.Response(200, text=f'<title>{title}</title><a href="{href}">Schematic</a>',
                              headers={'content-type': 'text/html'})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        inspect = lambda: render.inspect_public_schematic(url, 'pdf', query,
            title=query + ' schematic', page_url=page, source_file='Breadboard Power Supply v10.pdf', client=client)
        if accepted:
            assert inspect()[1] == 1
        else:
            with pytest.raises(ExternalSchematicInvalidSource):
                inspect()


def test_voltage_decimal_is_not_removed_during_identity_check():
    with pytest.raises(ExternalSchematicInvalidSource):
        render._verify_public_identity('Board 3.3V', title='Board 3.3V', page_url='https://example.org/board',
            source_file='board-schematic.pdf', source_url='https://example.org/board-schematic.pdf',
            kind='pdf', pdf_text='Board 33V schematic')


@pytest.mark.parametrize('query', ['Board 5V 3.3V', 'Board 5 V 3.3 V'])
def test_voltage_spacing_and_datasheets_directory_are_supported(query):
    render._verify_public_identity(query, title=query, page_url='https://cdn.sparkfun.com/datasheets/board.pdf',
        source_file='board-schematic.pdf', source_url='https://cdn.sparkfun.com/datasheets/board-schematic.pdf',
        kind='pdf', pdf_text='Board 5 V / 3.3 V schematic')


def test_verified_voltage_link_does_not_override_revision_check():
    with pytest.raises(ExternalSchematicInvalidSource):
        render._verify_public_identity('SparkFun Pro Micro v13 5V', title='SparkFun Pro Micro v13 5V',
            page_url='https://www.sparkfun.com/board', source_file='Pro-Micro-v14-schematic.pdf',
            source_url='https://cdn.sparkfun.com/datasheets/Pro-Micro-v14-schematic.pdf', kind='pdf',
            linked_identity='SparkFun Pro Micro v13 5 V schematic')


@pytest.mark.parametrize('page,text,linked', [
    ('https://example.org/board-3.3V', '', ''),
    ('https://www.sparkfun.com/board', 'Board 33V schematic', 'Board 3.3V schematic'),
])
def test_voltage_is_not_proven_by_page_url_or_conflicting_body(page, text, linked):
    with pytest.raises(ExternalSchematicInvalidSource):
        render._verify_public_identity('Board 3.3V', title='Board 3.3V schematic', page_url=page,
            source_file='board-schematic.pdf', source_url='https://cdn.sparkfun.com/board-schematic.pdf',
            kind='pdf', pdf_text=text, linked_identity=linked)


def test_official_link_verification_preserves_rate_limit(monkeypatch):
    from backend.projects.schematic_source import ExternalSchematicRateLimited
    monkeypatch.setattr(render, '_public_asset', lambda *args, **kwargs: (b'pdf-placeholder', 'application/pdf'))
    monkeypatch.setattr(render, '_pdf_identity_text', lambda data: '')
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={'retry-after': '30'}))) as client:
        with pytest.raises(ExternalSchematicRateLimited) as error:
            render.inspect_public_schematic('https://cdn.sparkfun.com/board-schematic.pdf', 'pdf',
                'SparkFun Board 3.3V', page_url='https://www.sparkfun.com/board', client=client)
    assert error.value.retry_after == 30
