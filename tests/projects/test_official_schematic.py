"""제조사 공식 회로도 후보가 등록 원본과 일치하는지 검증한다."""
import json
import hashlib
import io

import httpx


def _enabled(monkeypatch):
    monkeypatch.setenv("EXA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("EXA_API_KEY", "test-secret-not-for-output")


def test_official_search_accepts_only_registered_manufacturer_asset(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_official_schematics

    url = "https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro_Micro_v13b.pdf"
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [{"title": "Pro Micro schematic", "url": url}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_official_schematics("SparkFun Pro Micro v13", client=client)

    assert len(result) == 1
    source = result[0]
    assert source.source_type == "manufacturer_official"
    assert source.evidence_grade == 2
    assert source.manufacturer == "SparkFun Electronics"
    assert source.source_url == url
    body = json.loads(requests[0].content)
    assert body["includeDomains"] == ["cdn.sparkfun.com"]


def test_official_search_rejects_same_host_unregistered_asset(monkeypatch):
    _enabled(monkeypatch)
    from backend.projects.external_circuit_search import search_official_schematics

    def handle(request):
        return httpx.Response(200, json={"results": [{
            "title": "fake official schematic",
            "url": "https://cdn.sparkfun.com/not-in-verified-catalog.pdf",
        }]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert search_official_schematics("SparkFun Pro Micro v13", client=client) == ()


def test_official_renderer_checks_hash_before_serving_png():
    from PIL import Image
    from backend.projects.schematic_render import render_official_schematic
    from backend.projects.schematic_source import VerifiedSchematicSource

    buffer = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(buffer, format="PNG")
    png = buffer.getvalue()
    source = VerifiedSchematicSource(
        "", "", "CC-BY-4.0", "SparkFun Electronics", "https://cdn.sparkfun.com/",
        "https://cdn.sparkfun.com/test.png", "test.png", "png", (), "test.png", 1,
        "manufacturer_official", 2, "SparkFun Electronics", "Test", None,
        hashlib.sha256(png).hexdigest(), "https://github.com/sparkfun/Pro_Micro/blob/main/LICENSE.md",
    )
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=png, headers={"content-type": "image/png"}))) as client:
        result = render_official_schematic(source, client=client)
    assert result and result[0].startswith(b"\x89PNG")
