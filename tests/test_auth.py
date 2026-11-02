import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app


def test_password_hash_is_salted_and_rejects_bad_password():
    first = auth.hash_password("sample password 123")
    second = auth.hash_password("sample password 123")
    assert first != second
    assert auth.verify_password("sample password 123", first)
    assert not auth.verify_password("wrong password", first)
    assert not auth.verify_password("sample password 123", "broken")


def test_protected_endpoint_requires_authentication():
    response = TestClient(app).get("/api/auth/me")
    assert response.status_code == 401


def test_login_rejects_cross_origin():
    response = TestClient(app).post("/api/auth/login", json={"email": "a@example.test", "password": "x"}, headers={"origin": "https://evil.example"})
    assert response.status_code == 403


def test_database_sessions_are_isolated_and_revoked(monkeypatch):
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    suffix = secrets.token_hex(6)
    email_a, email_b = f"a-{suffix}@example.test", f"b-{suffix}@example.test"
    password = "not-a-real-password-123"
    hashed = auth.hash_password(password)
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (login_id, password_hash) VALUES (%s, %s), (%s, %s) RETURNING id", (email_a, hashed, email_b, hashed))
        id_a, id_b = (row[0] for row in cur.fetchall())
    a, b = TestClient(app), TestClient(app)
    headers = {"origin": "http://testserver"}
    for client, email, uid in ((a, email_a, id_a), (b, email_b, id_b)):
        assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": "incorrect"}).status_code == 401
        response = client.post("/api/auth/login", headers=headers, json={"email": email, "password": password})
        assert response.status_code == 200
        assert response.json() == {"user_id": uid}
        assert "httponly" in response.headers["set-cookie"].lower()
        assert client.get("/api/auth/me").json() == {"user_id": uid}
    assert a.post("/api/auth/logout", headers=headers).status_code == 200
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").json() == {"user_id": id_b}
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("UPDATE auth_sessions SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute' WHERE user_id = %s", (id_b,))
    assert b.get("/api/auth/me").status_code == 401


def test_database_login_throttling(monkeypatch):
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    email = f"limit-{secrets.token_hex(6)}@example.test"
    password = "not-a-real-password-123"
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (login_id, password_hash) VALUES (%s, %s)", (email, auth.hash_password(password)))
    client = TestClient(app)
    for _ in range(5):
        assert client.post("/api/auth/login", headers={"origin": "http://testserver"}, json={"email": email, "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", headers={"origin": "http://testserver"}, json={"email": email, "password": password}).status_code == 401
