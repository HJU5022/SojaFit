"""프로젝트 HTTP 계약: 세션·Origin·공통 오류·실제 DB 소유권."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from backend import auth
from backend.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/projects", None), ("POST", "/api/projects", {"demo_id": "breadboard_supply", "name": "회로"}),
    ("GET", "/api/projects/1", None), ("PATCH", "/api/projects/1", {"name": "수정"}),
    ("DELETE", "/api/projects/1", None), ("GET", "/api/demo-circuits", None),
])
def test_projects_require_session(client, method, path, body):
    response = client.request(method, path, json=body, headers={"origin": "http://testserver"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("origin", [None, "https://evil.example"])
@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/projects", {"demo_id": "breadboard_supply", "name": "회로"}),
    ("PATCH", "/api/projects/1", {"name": "수정"}), ("DELETE", "/api/projects/1", None),
])
def test_project_mutations_check_origin(client, origin, method, path, body):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.request(method, path, json=body, headers={"origin": origin} if origin else {})
    assert response.status_code == 403
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_demo_catalog_and_invalid_creation(client):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.get("/api/demo-circuits")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {
        "breadboard_supply", "mosfet_driver", "attiny85_dev", "pro_micro", "franzininho_diy",
    }
    for body in ({"demo_id": "../../secret", "name": "회로"}, {"demo_id": "breadboard_supply", "name": " "},
                 {"demo_id": "breadboard_supply", "name": "x" * 201},
                 {"demo_id": "breadboard_supply", "name": "회로", "user_id": 2}):
        result = client.post("/api/projects", json=body, headers={"origin": "http://testserver"})
        assert result.status_code == 422
        assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_database_errors_use_safe_common_response(client, monkeypatch):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    def unavailable():
        raise psycopg.OperationalError("private database connection detail")
    monkeypatch.setattr(auth, "connection", unavailable)
    response = client.get("/api/projects")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "private" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_owned_crud_and_foreign_admin_404_use_real_database(client, monkeypatch):
    url = os.getenv("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    schema = "projects_api_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f"-csearch_path={schema}")
        monkeypatch.setattr(auth, "connection", connect)
        try:
            with connect() as conn:
                for name in ("003_auth.sql", "005_auth_attempt_window.sql", "006_user_roles.sql", "013_projects.sql"):
                    conn.execute(Path("db", name).read_text(encoding="utf-8-sig"))
                users = [row[0] for row in conn.execute("INSERT INTO users (login_id,password_hash,role) VALUES ('a@example.test','fake','user'),('b@example.test','fake','admin') RETURNING id").fetchall()]
                for token, user_id in zip(("owner-token", "admin-token"), users):
                    conn.execute("INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (auth.session_token_hash(token), user_id))
            client.cookies.set(auth.COOKIE, "owner-token")
            response = client.post("/api/projects", json={"demo_id": "breadboard_supply", "name": "전원 회로"}, headers={"origin": "http://testserver"})
            assert response.status_code == 201
            project = response.json()
            project_id = project["id"]
            assert project["source_kind"] == "demo"
            assert project["connections"]["components"][3]["ref"] == "D1"
            assert "user_id" not in project and "netlist_content" not in project
            assert [p["id"] for p in client.get("/api/projects").json()] == [project_id]
            assert client.get(f"/api/projects/{project_id}").json() == project
            renamed = client.patch(f"/api/projects/{project_id}", json={"name": "名前変更"}, headers={"origin": "http://testserver"})
            assert renamed.status_code == 200 and renamed.json()["name"] == "名前変更"
            client.cookies.set(auth.COOKIE, "admin-token")
            assert client.get("/api/projects").json() == []
            for method, body in (("GET", None), ("PATCH", {"name": "stolen"}), ("DELETE", None)):
                errors = []
                for target in (project_id, project_id + 10000):
                    result = client.request(method, f"/api/projects/{target}", json=body, headers={"origin": "http://testserver"})
                    assert result.status_code == 404
                    error = result.json()["error"]
                    assert error.pop("request_id") == result.headers["X-Request-ID"]
                    errors.append(error)
                assert errors[0] == errors[1] == {"code": "NOT_FOUND", "message": "프로젝트를 찾을 수 없습니다."}
            client.cookies.set(auth.COOKIE, "owner-token")
            assert client.delete(f"/api/projects/{project_id}", headers={"origin": "http://testserver"}).status_code == 204
            assert client.get(f"/api/projects/{project_id}").status_code == 404
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
