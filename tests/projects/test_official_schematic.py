"""공개 웹 회로도 검색과 출처 분류를 검증한다."""
import json

import httpx
import pytest


@pytest.fixture(autouse=True)
def isolated_provider_limits(monkeypatch):
    from backend.projects import schematic_source
    monkeypatch.setattr(schematic_source, '_RATE_LIMITS', {})


def _enabled(monkeypatch):
    monkeypatch.setenv("EXA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("EXA_API_KEY", "test-secret-not-for-output")


def test_heading_download_link_uses_visible_schematic_label():
    from backend.projects.external_circuit_search import _page_assets
    def handle(request):
        return httpx.Response(200,text='<h1>555 Theremin</h1><h3 data-href="/555 Theremin.pdf">555 Theremin Schematic.pdf</h3>',headers={'content-type':'text/html'})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assets=_page_assets('https://example.org/project',client=client,required=True,require_schematic_context=True)
    assert len(assets)==1 and assets[0][0]=='https://example.org/555%20Theremin.pdf'


def test_pdf_result_keeps_later_publishing_page_evidence(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics
    url='https://example.org/555-theremin-schematic.pdf';page='https://example.org/555-theremin'
    def handle(request):
        if request.method=='POST':
            return httpx.Response(200,json={'results':[{'url':url,'title':'555 Theremin schematic'},
                {'url':page,'title':'555 Theremin schematic'}]})
        return httpx.Response(200,text=f'<h1>555 Theremin</h1><a href="{url}">Schematic</a>',headers={'content-type':'text/html'})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=search_public_schematics('555 Theremin',client=client)
    assert len(result)==1 and result[0].page_url==page


def test_search_diagnostics_distinguish_raw_results_from_filtered_candidates(monkeypatch, caplog):
    _enabled(monkeypatch)
    from backend.projects import external_circuit_search as search
    def handle(request):
        return httpx.Response(200, json={'results': [{
            'title': 'private Board 5V', 'url': 'https://example.org/private.pdf',
        }]})
    with caplog.at_level('INFO', logger=search.__name__):
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            assert search.search_public_schematics('private Board 5V', client=client) == ()
    record = next(record for record in caplog.records if record.message == 'schematic_search_candidates')
    assert (record.raw_result_count, record.candidate_count) == (1, 0)
    assert 'private' not in str(vars(record))
    assert 'test-secret-not-for-output' not in str(vars(record))


@pytest.mark.parametrize("url,label", [
    ("https://circuitcanvas.b-cdn.net/symbol-library/schematic/Adafruit_MOSFET_Driver_STEMMA_Breakout_s-1792873508598-4a536548.png", "Schematic"),
    ("https://example.org/symbol%2Dlibrary/schematic/driver.png", "Schematic"),
    ("https://example.org/assets/driver-schematic.svg", "Module symbol"),
    ("https://example.org/pinout/driver-schematic.png", "Schematic"),
    ("https://example.org/assets/driver-schematic.pdf", "Block diagram"),
    ("https://example.org/footprints/driver-schematic.svg", "Schematic"),
    ("https://example.org/symbol-library/schematic/driver", "Schematic"),
])
def test_search_excludes_symbol_assets_even_with_schematic_markers(monkeypatch, url, label):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_public_schematics

    good = "https://cdn-learn.adafruit.com/downloads/pdf/adafruit-mosfet-driver.pdf"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"results": [
                {"title": "Adafruit MOSFET Driver " + label, "url": "https://example.org/adafruit-mosfet-driver",
                 "highlights": ["schematic"], "extras": {"imageLinks": [url]}},
                {"title": "Adafruit MOSFET Driver", "url": good, "highlights": ["Schematic and Fab Print"]},
            ]})
        return httpx.Response(200, content=f'<a href="{url}">{label}</a>'.encode(),
                              headers={"Content-Type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_public_schematics("Adafruit MOSFET Driver", client=client)
    assert [candidate.source_url for candidate in result] == [good]


def test_community_subdomain_is_not_manufacturer_evidence():
    from backend.projects.external_circuit_search import _manufacturer_for

    assert _manufacturer_for("https://forum.seeedstudio.com/t/board/1") is None
    assert _manufacturer_for("https://community.sparkfun.com/t/board/1") is None
    assert _manufacturer_for("https://forums.raspberrypi.com/viewtopic.php?t=1") is None
    assert _manufacturer_for("https://wiki.seeedstudio.com/board/") == "Seeed Studio"


def test_official_design_archive_can_be_discovered_without_model_url_registration():
    from backend.projects.external_circuit_search import _page_assets
    url = 'https://pip-assets.raspberrypi.com/board/RPi-Pico-R3-PUBLIC-20200119.zip'
    html = f'<title>Raspberry Pi Pico</title><a href="{url}">Download design files</a>'
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(
            200, headers={'Content-Type':'text/html'}, text=html))) as client:
        assert [u for u,_ in _page_assets('https://pip.raspberrypi.com/board', client=client)] == [url]


@pytest.mark.parametrize("html,expected", [
    ('<h1>Teensy 4.0 Schematic</h1><img src="schematic40.png"><img src="parts_placement_teensy40_top.png">', ['schematic40.png']),
    ('<h2>Schematic</h2><h3>Downloads</h3><img src="drawing.png"><h2>Photos</h2><img src="other.png">', ['drawing.png']),
    ('<table><tr><td><img src="drawing.png"></td></tr><tr><th><h1>DRV8833 schematic diagram</h1></th></tr></table>', ['drawing.png']),
    ('<figure><img src="drawing.png"><figcaption>DRV8833 circuit diagram</figcaption></figure>', ['drawing.png']),
    ('<figure><img src="one.png"><img src="two.png"><figcaption>Schematic</figcaption></figure>', []),
    ('<figure><img src="one.png"></figure><figure><figcaption>Schematic</figcaption></figure>', []),
    ('<figure><img src="one.png"><h2>Schematic</h2></figure><img src="other.png">', []),
    ('<figure><img src="one.png"><figcaption><h2>Schematic</h2></figcaption></figure><img src="other.png">', ['one.png']),
    ('<title>Board schematic</title><h1>Schematic</h1><img src="drawing.png">', []),
])
def test_file_specific_schematic_context_supports_real_page_structures(html, expected):
    from backend.projects.external_circuit_search import _page_assets
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"Content-Type": "text/html"}, text=html))) as client:
        assets = _page_assets('https://example.org/board/', client=client, require_schematic_context=True)
    assert [url.rsplit('/', 1)[-1] for url, _ in assets] == expected


def test_image_context_nesting_is_bounded():
    from backend.projects.external_circuit_search import _page_assets
    html = '<figure>' * 9 + '<img src="drawing.png"><figcaption>Schematic</figcaption>' + '</figure>' * 9
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"Content-Type": "text/html"}, text=html))) as client:
        assert _page_assets('https://example.org/board/', client=client, require_schematic_context=True) == ()


def test_page_parser_accepts_image_without_alt_attribute():
    from backend.projects.external_circuit_search import _SchematicPageParser

    parser = _SchematicPageParser()
    parser.feed('<title>Board schematic</title><img src="https://example.org/board_sch.png">')
    assert parser.links == [("https://example.org/board_sch.png", "Board schematic")]


def test_page_title_in_link_evidence_is_bounded():
    from backend.projects.external_circuit_search import _SchematicPageParser
    parser = _SchematicPageParser()
    parser.feed('<title>' + 'x' * 10000 + '</title><a href="board.pdf">Schematic</a>')
    assert len(parser.links[0][1]) <= 210


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
        if request.method == 'GET':
            return httpx.Response(200, headers={'Content-Type':'text/html'}, text='<html></html>')
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


def test_official_portal_matches_exact_category_without_registered_model_id():
    from backend.projects.external_circuit_search import _raspberrypi_portal_schematics
    calls=[]
    archive='https://pip-assets.raspberrypi.com/documents/RPi-Pico-PUBLIC.zip'
    def handle(request):
        calls.append(str(request.url))
        if request.url.path=='/search':
            assert request.url.params['q']=='Raspberry Pi Pico'
            html='<a href="/categories/99-raspberry-pi-pico-w">Other model</a><a href="/categories/123-raspberry-pi-pico">Pico</a>'
        else:
            assert request.url.path=='/categories/123-raspberry-pi-pico'
            html=f'<title>Raspberry Pi Pico</title><a href="{archive}">Design files</a>'
        return httpx.Response(200,headers={'Content-Type':'text/html'},text=html)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result=_raspberrypi_portal_schematics('Raspberry Pi Pico',client=client)
    assert len(calls)==2 and result[0].source_url==archive and result[0].source_type=='manufacturer_official'


def test_official_portal_preserves_rate_limit():
    from backend.projects.external_circuit_search import _raspberrypi_portal_schematics
    from backend.projects.schematic_source import ExternalSchematicRateLimited
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(429,headers={'Retry-After':'77'}))) as client:
        with pytest.raises(ExternalSchematicRateLimited) as error:
            _raspberrypi_portal_schematics('Raspberry Pi Pico',client=client)
    assert error.value.retry_after==77


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
            assert b'downloads schematic design files learn.adafruit.com' in body
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


def test_tsc_search_is_datasheet_only_and_matches_exact_model_family(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_tsc_schematics
    good = "https://services.taiwansemi.com/storage/resources/datasheet/TSCR420_421CX6_B1708.pdf"
    unrelated = "https://services.taiwansemi.com/storage/resources/datasheet/TS19605CA20H_A2108.pdf"
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "services.taiwansemi.com"
        assert request.url.path == "/api/products_v2"
        assert request.url.params["keyword"] == "TSCR420CX6"
        return httpx.Response(200, json={"data": {"records": [
            {"name": "TSCR420CX6", "status": "Active", "datasheet": good},
            {"name": "TS19605CA20H", "status": "Active", "datasheet": unrelated},
        ]}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_tsc_schematics("TSC TSCR420CX6", client=client)

    assert [item.source_url for item in result] == [good]
    assert result[0].source_type == "manufacturer_official"
    assert result[0].manufacturer == "Taiwan Semiconductor"


def test_tsc_query_does_not_use_github_fallback(monkeypatch):
    _enabled(monkeypatch)
    import backend.projects.external_schematic as schematic
    import backend.projects.external_circuit_search as search
    calls = []
    monkeypatch.setattr(search, "search_tsc_schematics", lambda *args, **kwargs: ())
    monkeypatch.setattr(search, "search_github_repositories", lambda *args, **kwargs: calls.append("github") or ())
    assert schematic._search("Taiwan Semiconductor TS19503CB10H", 5) == ()
    assert calls == []


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


def test_tsc_legacy_part_uses_only_official_pdf_search_when_catalogue_is_empty(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_tsc_schematics
    calls = []
    good = 'https://services.taiwansemi.com/storage/resources/datasheet/TS19371CX6_J1708.pdf'
    def handle(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'data':{'records':[]}})
        assert request.url.host == 'api.exa.ai'
        body = json.loads(request.content)
        assert body['includeDomains'] == ['services.taiwansemi.com/storage/resources/datasheet/']
        return httpx.Response(200, json={'results':[{'url':good},
            {'url':'https://services.taiwansemi.com/storage/resources/datasheet/TS19605CA20H_A2108.pdf'},
            {'url':'https://evil.test/TS19371CX6_J1708.pdf'}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_tsc_schematics('TSC TS19371CX6',client=client)
    assert [r.source_url for r in result] == [good]
    assert len(calls) == 2


@pytest.mark.parametrize('url', [
    'https://services.taiwansemi.com@evil.test/storage/resources/datasheet/TS19503CB10H.pdf',
    'https://services.taiwansemi.com:8443/storage/resources/datasheet/TS19503CB10H.pdf',
    'https://services.taiwansemi.com/storage/resources/datasheet/TS19503CB10H-htmlpdf',
])
def test_tsc_catalogue_rejects_unsafe_pdf_links(monkeypatch,url):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_tsc_schematics
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={
            'data':{'records':[{'name':'TS19503CB10H','datasheet':url}]}}))) as client:
        assert search_tsc_schematics('TSC TS19503CB10H',client=client) == ()


@pytest.mark.parametrize('part', [
    'TS19503CB10H', 'TS19371CX6', 'TSCR420CX6', 'TSCR400CX6', 'TS19605CA20H',
    'TS34063CS', 'TS2596', 'TS2596S', 'TSL9A12V', 'TQL821CSV50',
])
def test_bare_tsc_parts_use_official_lookup_without_generic_or_github_search(monkeypatch,part):
    _enabled(monkeypatch)
    from backend.projects import external_circuit_search as search, external_schematic as schematic
    calls=[]
    monkeypatch.setattr(search,'search_tsc_schematics',lambda q,limit: calls.append(q) or ())
    def unexpected(*args,**kwargs):
        pytest.fail('TSC part must not reach generic/community search')
    for name in ('search_public_schematics','search_manufacturer_schematics','search_github_repositories','search_component_repositories'):
        monkeypatch.setattr(search,name,unexpected)
    assert schematic._search(part,5) == ()
    assert calls == [part]
    assert schematic._search_community(part,5) == ()


@pytest.mark.parametrize('query',['SS33','1N4148','BAT54','TS100','Raspberry Pi Pico','My TS19371CX6 board','https://example.org/TS19371CX6.pdf'])
def test_bare_tsc_recognition_preserves_other_search_intents(query):
    from backend.projects.external_circuit_search import is_tsc_query
    assert not is_tsc_query(query)


def test_tsc_route_diagnostic_records_provider_without_part_or_url(monkeypatch,caplog):
    from backend.projects import external_circuit_search as search, external_schematic as schematic
    monkeypatch.setattr(search,'search_tsc_schematics',lambda *args:())
    with caplog.at_level('INFO',logger=schematic.__name__):
        assert schematic._search('TS19371CX6',5)==()
    record=next(record for record in caplog.records if record.message=='schematic_search_route')
    assert record.phase=='tsc_official' and record.candidate_count==0
    assert 'TS19371' not in str(vars(record)) and 'https://' not in str(vars(record))


@pytest.mark.parametrize("query,manufacturer", [
    ("TI LM2596", "Texas Instruments"),
    ("ST L7805", "STMicroelectronics"),
    ("Analog Devices LT1763", "Analog Devices"),
    ("onsemi NSVR351SDSA3 diode", "onsemi"),
    ("Infineon BAT62-02V diode", "Infineon"),
    ("Vishay SiC diode PFC", "Vishay"),
])
def test_semiconductor_manufacturer_queries_are_official_reference_scope(query, manufacturer):
    from backend.projects.external_circuit_search import automatic_schematic_context, semiconductor_manufacturer
    assert automatic_schematic_context(query) == "reference"
    assert semiconductor_manufacturer(query) == manufacturer


def test_semiconductor_search_accepts_long_datasheet_reference(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        payload = json.loads(request.content)
        assert "TI" in payload["query"] and "LM2596" in payload["query"]
        return httpx.Response(200, json={"results": [{
            "title": "LM2596 datasheet typical application schematic",
            "url": "https://www.ti.com/lit/ds/symlink/lm2596.pdf",
        }]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_semiconductor_schematics("TI LM2596", client=client)
    assert len(result) == 1
    assert result[0].source_type == "manufacturer_official"
    assert result[0].manufacturer == "Texas Instruments"
    assert result[0].asset_kind == "pdf"


def test_rf_diode_evidence_does_not_reject_official_application_note():
    from backend.projects.external_circuit_search import component_evidence_matches
    text = "Infineon BAT62-02V RF power detection application note schematic"
    assert component_evidence_matches("BAT62-02V diode", text)
    assert not component_evidence_matches("SS33 diode", "Ranger SS33 radio transceiver schematic")


def test_rf_diode_exception_requires_the_requested_part_in_the_source():
    from backend.projects.external_circuit_search import component_evidence_matches
    assert not component_evidence_matches(
        "SS33 diode", "BAT54 radio application note diode detector schematic",
    )
    assert not component_evidence_matches(
        "NSVR351SDSA3 diode", "NSVR351SDSA4 radio application note diode detector schematic",
    )


def test_semiconductor_search_propagates_provider_failure(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import ExternalCircuitSearchError, search_semiconductor_schematics
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(429, headers={"Retry-After": "77"}),
    )) as client:
        with pytest.raises(ExternalCircuitSearchError):
            search_semiconductor_schematics("TI LM2596", client=client)


def test_radio_product_with_incidental_diode_is_not_an_rf_application():
    from backend.projects.external_circuit_search import component_evidence_matches
    assert not component_evidence_matches('SS33 diode', 'Ranger SS33 radio transceiver schematic with diode D1')
    assert component_evidence_matches('NSVR351SDSA3 diode', 'onsemi NSVR351SDSA3 diode detector circuit radio APPLICATION NOTE')


def test_semiconductor_pdf_urls_do_not_require_schematic_words_in_the_title():
    from backend.projects.external_circuit_search import _asset_kind
    assert _asset_kind('https://www.ti.com/lit/pdf/TIDM908', 'Schematic') == 'pdf'
    assert _asset_kind('https://www.ti.com/lit/ds/symlink/lm2596.pdf', 'LM2596 datasheet') == 'pdf'
    assert _asset_kind('https://www.onsemi.com/download/application-notes/pdf/and9482-d.pdf', 'Diode Detector Circuit') == 'pdf'
    assert _asset_kind('https://untrusted.example/lm2596.pdf', 'LM2596 datasheet') is None


def test_named_official_search_uses_direct_pdf_before_crawling_product_pages(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        if request.method == 'POST':
            return httpx.Response(200,json={'results':[
                {'url':'https://www.st.com/en/evaluation-tools/nucleo-mb1136.html','title':'NUCLEO MB1136 C05 schematic'},
                {'url':'https://www.st.com/resource/en/schematic_pack/mb1136-default-c05_schematic.pdf','title':'NUCLEO MB1136 C05 schematic'},
            ]})
        pytest.fail('direct official PDF makes product-page crawling unnecessary')
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        found=search_semiconductor_schematics('ST NUCLEO MB1136 C05',client=client)
    assert len(found)==1 and found[0].asset_kind=='pdf'


def test_official_application_note_can_identify_its_part_in_pdf_body(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        return httpx.Response(200,json={'results':[{
            'url':'https://www.onsemi.com/download/application-notes/pdf/and9482-d.pdf',
            'title':'Diode Detector Circuit',
        }]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs=search_semiconductor_schematics('onsemi NSVR351SDSA3 diode',client=client)
    assert len(refs)==1 and refs[0].source_file=='and9482-d.pdf'


def test_explicit_datasheet_query_prefers_datasheet_over_application_note(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        return httpx.Response(200,json={'results':[
            {'url':'https://www.ti.com/lit/an/snva003b/snva003b.pdf','title':'LM2596 application note schematic'},
            {'url':'https://www.ti.com/lit/ds/symlink/lm2596.pdf','title':'LM2596 datasheet'},
        ]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs=search_semiconductor_schematics('TI LM2596 datasheet',client=client)
    assert refs[0].source_url=='https://www.ti.com/lit/ds/symlink/lm2596.pdf'


def test_datasheet_search_does_not_mix_application_note_intent(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        query=json.loads(request.content)['query'].casefold()
        assert 'application note' not in query and 'reference design' not in query
        assert 'l7805' in query and 'datasheet' in query
        return httpx.Response(200,json={'results':[{'url':'https://www.st.com/resource/en/datasheet/l78.pdf','title':'Datasheet - L78'}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs=search_semiconductor_schematics('ST L7805 datasheet',client=client)
    assert refs[0].source_file=='l78.pdf'


@pytest.mark.parametrize('suffix', ['', '?language=zh', '?locale=zh-CN#page=23'])
def test_ti_translated_part_symlink_selects_english_original(monkeypatch, suffix):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={'results': [{
            'url': 'https://www.ti.com/cn/lit/ds/symlink/lm2596.pdf' + suffix,
            'title': 'LM2596 电源转换器 降压稳压器 datasheet (Rev. G)',
        }]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs = search_semiconductor_schematics('TI LM2596 datasheet', client=client)
    assert len(refs) == 1
    assert refs[0].source_url == 'https://www.ti.com/lit/ds/symlink/lm2596.pdf'
    assert refs[0].page_url == refs[0].source_url
    assert refs[0].manufacturer == 'Texas Instruments' and refs[0].evidence_grade == 2
    assert len(requests) == 1
    assert 'english' in json.loads(requests[0].content)['query'].casefold()


@pytest.mark.parametrize('query,foreign,english', [
    ('TI LM2596 datasheet', 'https://www.ti.com/cn/lit/ds/zhcsku0g/zhcsku0g.pdf',
     'https://www.ti.com/lit/ds/symlink/lm2596.pdf'),
    ('ST L7805 datasheet', 'https://www.st.com/resource/zh/datasheet/l78.pdf',
     'https://www.st.com/resource/en/datasheet/l78.pdf'),
    ('Analog Devices LT1763', 'https://www.analog.com/media/jp/technical-documentation/data-sheets/LT1763.pdf',
     'https://www.analog.com/media/en/technical-documentation/data-sheets/LT1763.pdf'),
    ('onsemi NSVR351SDSA3 diode', 'https://www.onsemi.com/download/application-notes/pdf/and9482-d.pdf?lang=zh',
     'https://www.onsemi.com/download/application-notes/pdf/and9482-d.pdf'),
    ('Infineon BAT62-02V diode', 'https://www.infineon.com/dgdl/an1807.pdf?language=de',
     'https://www.infineon.com/dgdl/an1807.pdf'),
    ('Vishay SiC diode PFC', 'https://www.vishay.com/docs/86537/pfc.pdf?locale=zh-CN',
     'https://www.vishay.com/docs/86537/pfc.pdf'),
])
def test_official_search_keeps_english_provider_but_not_translated_document(monkeypatch, query, foreign, english):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    def handle(request):
        return httpx.Response(200, json={'results': [
            {'url': foreign, 'title': query}, {'url': english, 'title': query},
        ]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs = search_semiconductor_schematics(query, client=client)
    assert [ref.source_url for ref in refs] == [english]


def test_translated_only_document_does_not_gain_official_reference_grade(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        'results': [{'url': 'https://www.ti.com/cn/lit/an/zhca123/zhca123.pdf',
                     'title': 'TI LM2596 application circuit'}],
    }))) as client:
        assert search_semiconductor_schematics('TI LM2596', client=client) == ()


def test_bare_part_search_checks_official_hosts_without_guessing_a_manufacturer(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert set(payload['includeDomains']) == {'ti.com', 'st.com', 'analog.com', 'onsemi.com', 'infineon.com', 'vishay.com'}
        assert 'english' in payload['query'].casefold()
        return httpx.Response(200, json={'results': [
            {'url': 'https://www.ti.com/cn/lit/ds/symlink/lm2596.pdf', 'title': 'LM2596 datasheet'},
            {'url': 'https://www.onsemi.com/pdf/datasheet/lm2596-d.pdf', 'title': 'LM2596 datasheet'},
            {'url': 'https://example.org/LM2596-schematic.pdf', 'title': 'LM2596 schematic'},
        ]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        refs = search_semiconductor_schematics('LM2596', client=client)
    assert len(calls) == 1
    assert {ref.manufacturer for ref in refs} == {'Texas Instruments', 'onsemi'}
    assert refs[0].source_url == 'https://www.ti.com/lit/ds/symlink/lm2596.pdf'


def test_bare_part_does_not_hide_second_manufacturer_behind_duplicate_provider_docs(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    rows=[{'url':f'https://www.ti.com/lit/an/doc{i}/lm2596-{i}.pdf','title':'LM2596 schematic'} for i in range(5)]
    rows.append({'url':'https://www.onsemi.com/pdf/datasheet/lm2596-d.pdf','title':'LM2596 schematic'})
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'results':rows}))) as client:
        refs=search_semiconductor_schematics('LM2596',client=client)
    assert {ref.manufacturer for ref in refs}=={'Texas Instruments','onsemi'}


def test_bare_part_discovery_keeps_one_candidate_from_each_of_six_official_providers(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    hosts=['ti.com','st.com','analog.com','onsemi.com','infineon.com','vishay.com']
    rows=[{'url':f'https://www.{host}/lm2596.pdf','title':'LM2596 schematic'} for host in hosts]
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'results':rows}))) as client:
        refs=search_semiconductor_schematics('LM2596',client=client)
    assert len({ref.manufacturer for ref in refs})==6


def test_bare_part_provider_query_preserves_identifier_casing_after_cache_normalization(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    sent=[]
    def handle(request):
        sent.append(json.loads(request.content)['query'])
        return httpx.Response(200,json={'results':[]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        search_semiconductor_schematics('l7805 datasheet',client=client)
    assert sent==['L7805 datasheet English PDF']


@pytest.mark.parametrize('query', ['LM2596', 'L7805', 'LT1763', 'NSVR351SDSA3', 'BAT62-02V', 'VEML7700'])
def test_bare_parts_do_not_require_model_prefix_in_search_metadata(monkeypatch, query):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_semiconductor_schematics
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,json={
        'results': [{'url': 'https://www.onsemi.com/download/application-notes/pdf/and9482-d.pdf',
                     'title': 'Diode Detector Circuit'}],
    }))) as client:
        refs = search_semiconductor_schematics(query,client=client)
    assert len(refs)==1  # The body, not discovery metadata, must prove the exact part.
