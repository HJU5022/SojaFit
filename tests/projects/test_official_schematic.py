"""공개 웹 회로도 검색과 출처 분류를 검증한다."""
import json

import httpx
import pytest


def _enabled(monkeypatch):
    monkeypatch.setenv("EXA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("EXA_API_KEY", "test-secret-not-for-output")


def test_community_subdomain_is_not_manufacturer_evidence():
    from backend.projects.external_circuit_search import _manufacturer_for

    assert _manufacturer_for("https://forum.seeedstudio.com/t/board/1") is None
    assert _manufacturer_for("https://community.sparkfun.com/t/board/1") is None
    assert _manufacturer_for("https://forums.raspberrypi.com/viewtopic.php?t=1") is None
    assert _manufacturer_for("https://wiki.seeedstudio.com/board/") == "Seeed Studio"


def test_page_parser_accepts_image_without_alt_attribute():
    from backend.projects.external_circuit_search import _SchematicPageParser

    parser = _SchematicPageParser()
    parser.feed('<title>Board schematic</title><img src="https://example.org/board_sch.png">')
    assert parser.links == [("https://example.org/board_sch.png", "Board schematic")]


def test_public_search_discovers_unregistered_official_pdf(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    source_url = "https://cdn-learn.adafruit.com/downloads/pdf/adafruit-mosfet-driver.pdf"

    def handle(request):
        assert request.method == "POST"
        return httpx.Response(200, json={"results": [{
            "title": "Adafruit MOSFET Driver",
            "url": source_url,
            "highlights": ["Schematic and Fab Print"],
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit MOSFET Driver", client=client)

    assert len(result) == 1
    source = result[0]
    assert source.source_url == source_url
    assert source.page_url == source_url
    assert source.asset_kind == "pdf"
    assert source.source_type == "manufacturer_official"
    assert source.evidence_grade == 2
    assert source.manufacturer == "Adafruit Industries"


@pytest.mark.parametrize("query", ["Raspberry Pi Pico", "라즈베리파이 피코", "라즈베리 파이 피코"])
def test_public_search_matches_korean_pico_name_to_english_candidate(monkeypatch, query):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    source_url = "https://www.raspberrypi.com/documentation/microcontrollers/pico-schematic.pdf"

    def handle(request):
        assert request.method == "POST"
        assert "Raspberry Pi Pico" in json.loads(request.content)["query"]
        return httpx.Response(200, json={"results": [{
            "title": "Raspberry Pi Pico schematic",
            "url": source_url,
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics(query, client=client)

    assert len(result) == 1
    assert result[0].source_url == source_url
    assert result[0].source_type == "manufacturer_official"


@pytest.mark.parametrize("query", ["라즈베리파이 피코", "라즈베리 파이 피코"])
def test_manufacturer_search_matches_korean_pico_name(monkeypatch, query):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    source_url = "https://www.raspberrypi.com/documentation/microcontrollers/pico-schematic.pdf"

    def handle(request):
        body = json.loads(request.content)
        assert body["includeDomains"] == ["raspberrypi.com"]
        assert "Raspberry Pi Pico" in body["query"]
        return httpx.Response(200, json={"results": [{
            "title": "Raspberry Pi Pico schematic",
            "url": source_url,
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics(query, client=client)

    assert len(result) == 1
    assert result[0].source_url == source_url
    assert result[0].evidence_grade == 2


def test_public_search_does_not_replace_requested_revision(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [{
            "title": "SparkFun Pro Micro v14 schematic",
            "url": "https://cdn.sparkfun.com/pro-micro-v14-schematic.pdf",
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert search_public_schematics("SparkFun Pro Micro v13", client=client) == ()


def test_public_search_accepts_model_joined_with_filename_words(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [{
            "title": "Fan Control schematic",
            "url": "https://example.org/tiny85fancontrol-schematic.png",
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Tiny85 Fan Control", client=client)
    assert len(result) == 1


def test_public_search_returns_public_image_without_official_allowlist(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        assert request.method == "POST"
        return httpx.Response(200, json={"results": [{
            "title": "My Sensor Circuit Schematic",
            "url": "https://example.org/projects/my-sensor",
            "highlights": ["complete circuit schematic"],
            "extras": {"imageLinks": ["https://example.org/projects/my-sensor/schematic.png"]},
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("My Sensor Circuit", client=client)

    assert len(result) == 1
    source = result[0]
    assert source.source_url.endswith("/schematic.png")
    assert source.page_url == "https://example.org/projects/my-sensor"
    assert source.source_type == "public_web"
    assert source.evidence_grade is None
    assert source.license == "미확인"


def test_official_page_does_not_promote_third_party_image_to_grade_two(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [{
            "title": "Adafruit Example Board schematic",
            "url": "https://learn.adafruit.com/example-board/downloads",
            "extras": {"imageLinks": ["https://example.org/example-board-schematic.png"]},
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit Example Board", client=client)

    assert len(result) == 1
    assert result[0].source_type == "public_web"
    assert result[0].evidence_grade is None


def test_public_search_extracts_schematic_srcset_from_manufacturer_page(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    page = "https://learn.adafruit.com/example-board/downloads"
    schematic = "https://cdn-learn.adafruit.com/assets/example_board_schematic.png"
    product = "https://cdn-learn.adafruit.com/assets/example_board_product.png"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Adafruit Example Board",
                "url": page,
                "highlights": ["Schematic and Fab Print"],
            }]})
        return httpx.Response(200, content=(
            f'<img srcset="{product} 640w, {schematic} 1024w" alt="board downloads">'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit Example Board", client=client)

    assert len(result) == 1
    assert result[0].source_url == schematic
    assert result[0].page_url == page


def test_public_search_extracts_link_text_and_sch_filename(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    page = "https://learn.adafruit.com/example-board/downloads"
    schematic = "https://cdn-learn.adafruit.com/assets/example_board_sch.png"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Adafruit Example Board",
                "url": page,
                "highlights": ["Schematic and Fab Print"],
            }]})
        return httpx.Response(200, content=(
            f'<h1>Schematic and Fab Print</h1><a href="{schematic}">Download PNG</a>'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit Example Board", client=client)

    assert len(result) == 1
    assert result[0].source_url == schematic
    assert result[0].source_type == "manufacturer_official"
    assert result[0].evidence_grade == 2


def test_public_search_extracts_pdf_from_schematic_link_text(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    page = "https://learn.sparkfun.com/tutorials/example/resources"
    schematic = "https://cdn.sparkfun.com/assets/example-board.pdf"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "SparkFun Example Board",
                "url": page,
                "highlights": ["Resources and Schematic"],
            }]})
        return httpx.Response(200, content=(
            f'<a href="{schematic}">Schematic (PDF)</a>'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("SparkFun Example Board", client=client)

    assert len(result) == 1
    assert result[0].source_url == schematic
    assert result[0].asset_kind == "pdf"
    assert result[0].evidence_grade == 2


def test_manufacturer_search_scopes_exa_to_known_domains(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    page = "https://learn.adafruit.com/example-board/downloads"
    schematic = "https://cdn-learn.adafruit.com/assets/example_board_sch.png"
    requests = []

    def handle(request):
        requests.append(request)
        if request.method == "POST":
            body = request.read()
            assert b'"includeDomains":["adafruit.com"]' in body or b'"includeDomains": ["adafruit.com"]' in body
            assert b'downloads schematic learn.adafruit.com' in body
            assert b'schematic downloads schematic' not in body
            return httpx.Response(200, json={"results": [{
                "title": "Adafruit Example Board",
                "url": page,
                "highlights": ["Schematic and Fab Print"],
            }]})
        return httpx.Response(200, content=(
            f'<h1>Schematic and Fab Print</h1><img src="{schematic}" alt="schematic">'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics("Adafruit Example Board schematic", client=client)

    assert len(result) == 1
    assert result[0].source_url == schematic
    assert any(request.method == "POST" for request in requests)


def test_official_downloads_page_uses_model_in_url_when_search_title_is_generic(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    markdown_page = "https://learn.adafruit.com/adafruit-qt-py-2040/downloads.md"
    html_page = markdown_page[:-3]
    image = "https://cdn-learn.adafruit.com/assets/adafruit_products_QTRP_sch.png"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Downloads", "url": markdown_page, "highlights": [],
            }]})
        if str(request.url) == markdown_page:
            return httpx.Response(200, content=b"# Downloads", headers={"content-type": "text/plain"})
        assert str(request.url) == html_page
        return httpx.Response(200, content=(
            f'<title>Adafruit QT Py RP2040</title><h1>Schematic and Fab Print</h1>'
            f'<img src="{image}" alt="schematic">'
        ).encode(), headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics("Adafruit QT Py RP2040 schematic", client=client)
    assert result and result[0].source_url == image
    assert result[0].evidence_grade == 2


@pytest.mark.parametrize(
    ("query", "page", "asset", "domain"),
    [
        ("Seeed XIAO ESP32C3", "https://wiki.seeedstudio.com/xiao_esp32c3_getting_started/", "https://files.seeedstudio.com/wiki/XIAO_WiFi/Resources/Seeeduino-XIAO-ESP32C3-SCH.pdf", "seeedstudio.com"),
        ("Arduino Nano Every", "https://docs.arduino.cc/hardware/nano-every/", "https://docs.arduino.cc/resources/schematics/ABX00028-schematics.pdf", "arduino.cc"),
        ("Raspberry Pi Zero 2 W", "https://pip.raspberrypi.com/categories/584", "https://pip-assets.raspberrypi.com/categories/584-raspberry-pi-zero-2-w/documents/RP-008360-DS-1-raspberry-pi-zero-2-w-reduced-schematics.pdf", "raspberrypi.com"),
        ("Teensy LC", "https://www.pjrc.com/teensy/schematic.html", "https://www.pjrc.com/teensy/schematic_lc.png", "pjrc.com"),
    ],
)
def test_manufacturer_search_supports_known_official_publishers(monkeypatch, query, page, asset, domain):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    def handle(request):
        if request.method == "POST":
            body = request.read().decode()
            assert f'"includeDomains":["{domain}"]' in body
            return httpx.Response(200, json={"results": [{
                "title": f"{query} schematic", "url": page,
                "highlights": ["official schematic"],
                "extras": {"imageLinks": [asset]} if asset.endswith((".png", ".svg")) else {},
            }]})
        return httpx.Response(200, content=(
            f'<a href="{asset}">Schematic (PDF)</a>'
            if asset.endswith(".pdf") else f'<img src="{asset}" alt="schematic">'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics(query, client=client)

    assert len(result) == 1
    assert result[0].source_url == asset
    assert result[0].source_type == "manufacturer_official"
    assert result[0].evidence_grade == 2


def test_manufacturer_search_accepts_olimex_linked_github_pdf(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    page = "https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/"
    asset = "https://github.com/OLIMEX/ESP32-POE/blob/master/HARDWARE/ESP32-PoE-hardware-revision-M1/ESP32-PoE_Rev_M1.pdf"
    raw_asset = "https://raw.githubusercontent.com/OLIMEX/ESP32-POE/master/HARDWARE/ESP32-PoE-hardware-revision-M1/ESP32-PoE_Rev_M1.pdf"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Olimex ESP32-POE", "url": page,
                "highlights": ["latest schematic"],
            }]})
        return httpx.Response(200, content=f'<a href="{asset}">latest schematic</a>'.encode(),
                              headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics("Olimex ESP32-POE", client=client)

    assert len(result) == 1
    assert result[0].source_url == raw_asset
    assert result[0].source_type == "manufacturer_official"


def test_manufacturer_search_rejects_untrusted_github_owner(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    page = "https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/"
    asset = "https://github.com/attacker/ESP32-POE/blob/main/schematic.pdf"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Olimex ESP32-POE", "url": page,
                "highlights": ["latest schematic"],
            }]})
        return httpx.Response(200, content=f'<a href="{asset}">latest schematic</a>'.encode(),
                              headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert search_manufacturer_schematics("Olimex ESP32-POE", client=client) == ()


def test_manufacturer_search_accepts_pololu_extensionless_schematic_image(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_manufacturer_schematics

    page = "https://www.pololu.com/picture/view/0J3872"
    asset = "https://a.pololu-files.com/picture/0J3872.1200.png?abc=1"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "title": "Schematic diagram of the DRV8833 dual motor driver carrier",
                "url": page, "highlights": ["schematic diagram"],
            }]})
        return httpx.Response(200, content=f'<title>Schematic diagram of the DRV8833 dual motor driver carrier</title><a href="{page}">Schematic</a><img src="{asset}" alt="">'.encode(),
                              headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_manufacturer_schematics("Pololu DRV8833 Dual Motor Driver", client=client)

    assert len(result) == 1
    assert result[0].source_url == asset
    assert result[0].asset_kind == "png"
    assert result[0].source_type == "manufacturer_official"
    assert result[0].source_url != page


def test_public_search_rejects_datasheet_without_schematic_marker(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [{
            "title": "Adafruit Example Board datasheet",
            "url": "https://cdn-learn.adafruit.com/downloads/pdf/example-board.pdf",
            "highlights": ["electrical characteristics and application notes"],
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert search_public_schematics("Adafruit Example Board", client=client) == ()


def test_public_search_skips_result_without_public_url(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [
            {"title": "missing URL", "highlights": ["schematic"]},
            {"title": "Adafruit Example", "url": "https://cdn-learn.adafruit.com/example-schematic.pdf",
             "highlights": ["schematic"]},
        ]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit Example", client=client)
    assert result and result[0].source_url.endswith("example-schematic.pdf")


def test_public_search_prefers_official_schematic_png_to_guide_pdf(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    guide = "https://cdn-learn.adafruit.com/downloads/pdf/example-board.pdf"
    markdown = "https://learn.adafruit.com/example-board/downloads.md"
    large = "https://cdn-learn.adafruit.com/assets/example_board_schematic_large1024.png"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [
                {"title": "Adafruit Example Board", "url": guide,
                 "highlights": ["Schematic and Fab Print"]},
                {"title": "Adafruit Example Board", "url": markdown,
                 "highlights": ["Schematic and Fab Print"]},
            ]})
        return httpx.Response(200, content=(
            f'<img srcset="https://cdn-learn.adafruit.com/assets/example_board_schematic_small360.png 360w, {large} 1024w">'
        ).encode(), headers={"content-type": "text/html; charset=utf-8"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit Example Board", client=client)

    assert result
    assert result[0].source_url == large
    assert result[0].asset_kind == "png"


@pytest.mark.parametrize("query", ["Raspberry Pi Pico", "라즈베리파이 피코", "RPi Pico"])
def test_public_search_keeps_abbreviated_pico_drawing_within_candidate_limit(monkeypatch, query):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    drawing = "https://files.waveshare.com/upload/e/ed/RPI-PICO-R3-PUBLIC-SCHEMATIC.pdf"

    def handle(request):
        assert request.method == "POST"
        return httpx.Response(200, json={"results": [
            {"title": "SCHEMATIC1 : PAGE1", "url": drawing,
             "highlights": ["RPI-PICO 3 Raspberry Pi Pico schematic"]},
            *({"title": f"Raspberry Pi Pico accessory {index} schematic",
               "url": f"https://example.org/raspberry-pi-pico-accessory-{index}-schematic.pdf"}
              for index in range(5)),
        ]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics(query, limit=5, client=client)

    assert result[0].source_url == drawing
    assert result[0].source_type == "public_web"
    assert result[0].evidence_grade is None
    assert len(result) == 5


def test_public_search_prefers_exact_model_name_over_partial_match(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    exact = "https://raw.githubusercontent.com/Colahall/tiny85fancontrol/abc/schematic/tiny85fancontrol.png"
    wrong = "https://gitlab.com/example/attiny85_pwm_fan_controller_schematic.png"

    def handle(request):
        return httpx.Response(200, json={"results": [
            {"title": "ATtiny85 PWM Fan Controller", "url": wrong,
             "highlights": ["fan controller schematic"]},
            {"title": "Tiny85 Fan Control", "url": exact,
             "highlights": ["complete schematic"]},
        ]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Tiny85 Fan Control", client=client)

    assert result
    assert result[0].source_url == exact
