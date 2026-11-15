"""SPA 화면 경로와 기존 API 경계의 같은 출처 제공을 확인한다."""
from fastapi.testclient import TestClient
from fastapi import FastAPI
from pathlib import Path
import pytest

from backend.main import app, http_error
from starlette.exceptions import HTTPException as StarletteHTTPException


@pytest.mark.parametrize("path", ["/api", "/api/not-a-route", "/api/not-a-route/nested"])
def test_api_404_stays_json(path):
    response = TestClient(app).get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.fixture
def built_frontend(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('shell')", encoding="utf-8")
    (dist / "circuit-schematics").mkdir()
    schematic = Path(__file__).resolve().parents[2] / "frontend/public/circuit-schematics/mosfet_driver.png"
    (dist / "circuit-schematics/mosfet_driver.png").write_bytes(schematic.read_bytes())
    return dist


@pytest.fixture
def frontend_client(built_frontend):
    from backend.web.app import mount_frontend

    mounted = FastAPI()
    mounted.add_exception_handler(StarletteHTTPException, http_error)

    @mounted.get("/health")
    def health():
        return {"status": "ok"}

    mount_frontend(mounted, built_frontend)
    return TestClient(mounted)


# [왜] 백엔드가 보내는 주소(Google 콜백 /login?google=…, 메일 링크 /verify-email · /reset-password)와 화면 경로 전부가 index를 받아야 한다
@pytest.mark.parametrize("path", ["/", "/login", "/login?google=finish", "/signup", "/password-reset", "/verify-email",
                                  "/reset-password", "/privacy", "/app", "/app?project=1&thread=2", "/settings", "/approved",
                                  "/admin", "/admin/users", "/app/deep-link"])
def test_react_route_returns_index(frontend_client, path):
    response = frontend_client.get(path)
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_assets_are_served_and_missing_asset_is_not_html(frontend_client):
    response = frontend_client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('shell')"
    assert frontend_client.get("/assets/missing.js").status_code == 404


def test_schematic_returns_png_bytes_without_spa_fallback(frontend_client, built_frontend):
    response = frontend_client.get("/circuit-schematics/mosfet_driver.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == (built_frontend / "circuit-schematics/mosfet_driver.png").read_bytes()
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    missing = frontend_client.get("/circuit-schematics/missing.png")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")


def test_missing_schematic_directory_does_not_return_spa(tmp_path):
    from backend.web.app import mount_frontend

    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    mounted = FastAPI()
    mount_frontend(mounted, tmp_path)
    client = TestClient(mounted)
    assert client.get("/circuit-schematics/missing.png").status_code == 404
    assert client.get("/circuit-schematics").status_code == 404


def test_existing_routes_and_api_boundary_win_over_spa(frontend_client):
    assert frontend_client.get("/health").json() == {"status": "ok"}
    response = frontend_client.get("/api/not-a-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_head_screen_returns_html_headers_without_body(frontend_client):
    response = frontend_client.head("/app")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.content == b""


@pytest.mark.parametrize("path", ["/login", "/app", "/index.html"])
@pytest.mark.parametrize("method", ["get", "head"])
def test_html_is_not_cached(frontend_client, path, method):
    response = getattr(frontend_client, method)(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_fixed_assets_revalidate_even_after_304(frontend_client, built_frontend):
    (built_frontend / "assets/sojafit-icon.svg").write_text("<svg></svg>")
    response = frontend_client.get("/assets/sojafit-icon.svg")
    assert response.headers["cache-control"] == "no-cache"
    cached = frontend_client.get("/assets/sojafit-icon.svg", headers={"If-None-Match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.headers["cache-control"] == "no-cache"
    (built_frontend / "assets/sojafit-icon.svg").write_text("<svg>new deployment</svg>")
    updated = frontend_client.get("/assets/sojafit-icon.svg", headers={"If-None-Match": response.headers["etag"]})
    assert updated.status_code == 200
    assert "new deployment" in updated.text
    assert frontend_client.head("/assets/sojafit-icon.svg").headers["cache-control"] == "no-cache"
    assert "cache-control" not in frontend_client.get("/api/not-a-route").headers


def test_api_methods_keep_downstream_status(frontend_client):
    assert frontend_client.post("/api/not-a-route").status_code == 404
    assert frontend_client.head("/api/not-a-route").status_code == 404


def test_non_get_method_does_not_open_screen(frontend_client):
    assert frontend_client.post("/app").status_code == 404


def test_health_redirect_is_not_replaced(frontend_client):
    response = frontend_client.get("/health/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/health"
    assert frontend_client.post("/health").status_code == 405


@pytest.mark.parametrize("path", ["/login", "/app", "/admin/users"])
def test_unbuilt_frontend_keeps_common_404(tmp_path, path):
    """빌드가 없으면 대신 보일 화면 없이 공통 404 JSON이다(예전 로그인 템플릿은 11-10에 지움)."""
    from backend.web.app import mount_frontend

    mounted = FastAPI()
    mounted.add_exception_handler(StarletteHTTPException, http_error)
    mount_frontend(mounted, tmp_path / "missing-dist")
    response = TestClient(mounted).get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
