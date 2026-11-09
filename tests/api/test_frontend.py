"""SPA 화면 경로와 기존 API 경계의 같은 출처 제공을 확인한다."""
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest

from backend.main import app, http_error
from starlette.exceptions import HTTPException as StarletteHTTPException


@pytest.mark.parametrize("path", ["/api", "/api/not-a-route", "/api/not-a-route/nested"])
def test_api_404_stays_json(path):
    response = TestClient(app).get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize("path", ["/login", "/app", "/admin/users"])
def test_main_app_serves_frontend_routes(path):
    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["X-Request-ID"]


@pytest.fixture
def built_frontend(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('shell')", encoding="utf-8")
    fallback = tmp_path / "login.html"
    fallback.write_text("legacy login", encoding="utf-8")
    return dist, fallback


@pytest.fixture
def frontend_client(built_frontend):
    from backend.web.app import mount_frontend

    mounted = FastAPI()
    mounted.add_exception_handler(StarletteHTTPException, http_error)

    @mounted.get("/health")
    def health():
        return {"status": "ok"}

    mount_frontend(mounted, *built_frontend)
    return TestClient(mounted)


@pytest.mark.parametrize("path", ["/", "/login", "/app", "/admin/users", "/app/deep-link"])
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


def test_unbuilt_frontend_returns_legacy_login(tmp_path):
    from backend.web.app import mount_frontend

    fallback = tmp_path / "login.html"
    fallback.write_text("legacy login", encoding="utf-8")
    mounted = FastAPI()
    mount_frontend(mounted, tmp_path / "missing-dist", fallback)
    assert TestClient(mounted).get("/app").text == "legacy login"
