"""원본 회로도 API 계약 테스트."""
from importlib import import_module
from types import SimpleNamespace
import logging
import pytest
from fastapi.testclient import TestClient
from backend import auth
from backend.main import app


@pytest.mark.parametrize('reason,message', [
    ('no_candidates', '검색 결과가 없습니다'), ('validation_failed', '후보를 찾았지만'),
])
def test_schematic_failure_reason_keeps_error_contract(client, schematic_boundary, reason, message):
    from backend.projects.schematic_source import ExternalSchematicNotFound
    schematic_boundary.error = ExternalSchematicNotFound(reason=reason)
    response = client.get('/api/external-circuits/schematics', params={'q': 'test board'})
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'SCHEMATIC_NOT_FOUND'
    assert message in response.json()['error']['message']
    assert response.headers['X-Schematic-Failure'] == reason
    assert response.headers['cache-control'] == 'private, no-store'

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def schematic_boundary(monkeypatch):
    api = import_module("backend.api.external_circuits")
    state = SimpleNamespace(
        manifest=SimpleNamespace(project="owner/repo", commit="a" * 40, license="MIT",
            attribution="owner/repo contributors", repository_url="https://github.com/owner/repo",
            source_url=f"https://github.com/owner/repo/tree/{'a' * 40}",
            source_file="hardware/board.kicad_sch", token="signed-token", sheet_count=2,
            source_type="community", evidence_grade=3, manufacturer=None, model=None,
            revision=None, source_sha256=None, license_evidence_url=None, choices=()),
        queries=[], sheet_calls=[], png=b"\x89PNG\r\n\x1a\nfixture", error=None,
    )

    def find(query):
        state.queries.append(query)
        if state.error:
            raise state.error
        return state.manifest

    def load(token, sheet):
        state.sheet_calls.append((token, sheet))
        if state.error:
            raise state.error
        if sheet >= state.manifest.sheet_count:
            raise api.ExternalSchematicInvalidToken("invalid sheet")
        return state.png

    monkeypatch.setattr(api, "find_external_schematic", find)
    monkeypatch.setattr(api, "load_external_schematic_sheet", load)
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    return state


@pytest.mark.parametrize("path", ["/api/external-circuits/schematics?q=ATtiny85",
                                  "/api/external-circuits/schematics/signed-token/0"])
def test_external_schematic_requires_session(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["cache-control"] == "private, no-store"


def test_external_schematic_manifest_returns_all_sheet_urls(client, schematic_boundary):
    response = client.get("/api/external-circuits/schematics", params={"q": "  ATtiny85  "})
    assert response.status_code == 200
    assert schematic_boundary.queries == ["ATtiny85"]
    assert response.json() == {
        **{key: value for key, value in vars(schematic_boundary.manifest).items()
           if key not in {"token", "sheet_count"}},
        "images": [{"sheet": i, "url": f"/api/external-circuits/schematics/signed-token/{i}"} for i in range(2)],
        "choices": [],
    }
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("query", ["ab", "x" * 200, " " + "x" * 200 + " "])
def test_external_schematic_accepts_trimmed_query_boundaries(client, schematic_boundary, query):
    response = client.get("/api/external-circuits/schematics", params={"q": query})
    assert response.status_code == 200
    assert schematic_boundary.queries == [query.strip()]


@pytest.mark.parametrize("query", ["x", " x ", " ", "x" * 201])
def test_external_schematic_rejects_query_before_service(client, schematic_boundary, query):
    response = client.get("/api/external-circuits/schematics", params={"q": query})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "private, no-store"
    assert schematic_boundary.queries == []


def test_external_schematic_sheet_returns_hardened_png(client, schematic_boundary):
    response = client.get("/api/external-circuits/schematics/signed-token/0")
    assert response.status_code == 200
    assert response.content == schematic_boundary.png
    assert schematic_boundary.sheet_calls == [("signed-token", 0)]
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("sheet", [-1, 2])
def test_external_schematic_sheet_invalid_index_is_not_found(client, schematic_boundary, sheet):
    response = client.get(f"/api/external-circuits/schematics/signed-token/{sheet}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCHEMATIC_NOT_FOUND"
    assert response.headers["cache-control"] == "private, no-store"
    if sheet < 0:
        assert schematic_boundary.sheet_calls == []


@pytest.mark.parametrize("path", ["/api/external-circuits/schematics?q=ATtiny85",
                                  "/api/external-circuits/schematics/signed-token/0"])
@pytest.mark.parametrize("exception_name,status,code", [
    ("ExternalSchematicNotFound", 404, "SCHEMATIC_NOT_FOUND"),
    ("ExternalSchematicInvalidToken", 404, "SCHEMATIC_NOT_FOUND"),
    ("ExternalSchematicConfigurationError", 503, "UNAVAILABLE"),
    ("ExternalCircuitSearchDisabled", 503, "UNAVAILABLE"),
    ("ExternalCircuitSearchConfigurationError", 503, "UNAVAILABLE"),
    ("ExternalSchematicRateLimited", 503, "UNAVAILABLE"),
    ("ExternalSchematicUpstreamError", 502, "UPSTREAM_ERROR"),
    ("ExternalCircuitSearchError", 502, "UPSTREAM_ERROR"),
])
def test_external_schematic_safe_errors(client, schematic_boundary, path, exception_name, status, code):
    api = import_module("backend.api.external_circuits")
    schematic_boundary.error = getattr(api, exception_name)(
        17 if exception_name == "ExternalSchematicRateLimited" else "private credential marker")
    response = client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "private, no-store"
    assert "credential" not in response.text
    if exception_name == "ExternalSchematicRateLimited":
        assert response.headers["retry-after"] == "17"
    else:
        assert "retry-after" not in response.headers


@pytest.mark.parametrize("suffix", ["", "?q=private-query"])
def test_external_schematic_access_log_redacts_signed_token_without_query(suffix):
    import logging
    from backend.logs import hide_query
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/api/external-circuits/schematics/private-signed-token/0" + suffix, "1.1", 200), None)
    assert hide_query(record)
    assert "private-signed-token" not in record.getMessage()
    assert "private-query" not in record.getMessage()
    assert "/schematics/<redacted>/0" in record.getMessage()


def test_manifest_rejects_grade_two_without_a_sha256():
    from backend.api.external_circuits import ExternalSchematicResponse
    payload = {
        "project": None, "commit": None, "license": "CC-BY-4.0", "attribution": "SparkFun Electronics",
        "repository_url": "https://cdn.sparkfun.com/test.pdf", "source_url": "https://cdn.sparkfun.com/test.pdf", "source_file": "test.pdf",
        "source_type": "manufacturer_official", "evidence_grade": 2,
        "manufacturer": "SparkFun Electronics", "model": "Pro Micro", "revision": "v13b",
        "source_sha256": "short", "license_evidence_url": "https://github.com/sparkfun/Pro_Micro/blob/main/LICENSE.md",
        "images": [{"sheet": 0, "url": "/api/external-circuits/schematics/token/0"}],
    }
    with pytest.raises(ValueError):
        ExternalSchematicResponse.model_validate(payload)


def test_manifest_rejects_unknown_provenance_literal():
    from backend.api.external_circuits import ExternalSchematicResponse
    payload = {
        "project": "owner/repo", "commit": "a" * 40, "license": "MIT", "attribution": "owner/repo contributors",
        "repository_url": "https://github.com/owner/repo", "source_url": "https://github.com/owner/repo/tree/" + "a" * 40,
        "source_file": "hardware/board.kicad_sch", "source_type": "official", "evidence_grade": 2,
        "manufacturer": "Unknown", "model": "Board", "revision": None, "source_sha256": "a" * 64,
        "license_evidence_url": "https://github.com/owner/repo/blob/main/LICENSE",
        "images": [{"sheet": 0, "url": "/api/external-circuits/schematics/token/0"}],
    }
    with pytest.raises(ValueError):
        ExternalSchematicResponse.model_validate(payload)


def test_manifest_allows_public_web_without_claiming_verified_grade():
    from backend.api.external_circuits import ExternalSchematicResponse

    payload = {
        "project": None, "commit": None, "license": "미확인", "attribution": "Publisher",
        "repository_url": "https://example.org/board",
        "source_url": "https://example.org/schematic.png", "source_file": "schematic.png",
        "source_type": "public_web", "evidence_grade": None, "manufacturer": None,
        "model": "Board", "revision": None, "source_sha256": "a" * 64,
        "license_evidence_url": None,
        "images": [{"sheet": 0, "url": "/api/external-circuits/schematics/token/0"}],
    }
    assert ExternalSchematicResponse.model_validate(payload).evidence_grade is None
    payload["evidence_grade"] = 2
    with pytest.raises(ValueError):
        ExternalSchematicResponse.model_validate(payload)
