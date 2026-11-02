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


def test_failed_attempt_window_expires(monkeypatch):
    import hashlib
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    email = f"window-{secrets.token_hex(6)}@example.test"
    key = hashlib.sha256(email.encode()).hexdigest()
    password = "test-only-password-123"
    with psycopg.connect(database_url) as conn:
        conn.execute("INSERT INTO users(login_id, password_hash) VALUES (%s,%s)", (email, auth.hash_password(password)))
    client = TestClient(app)
    headers = {"origin": "http://testserver"}
    body = {"email": email, "password": "wrong"}
    assert client.post("/api/auth/login", headers=headers, json=body).status_code == 401
    with psycopg.connect(database_url) as conn:
        count, until = conn.execute("SELECT failed_count, window_started_at FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
        assert count == 1 and until is not None
        conn.execute("UPDATE auth_login_attempts SET window_started_at=CURRENT_TIMESTAMP - INTERVAL '16 minutes' WHERE login_hash=%s", (key,))
    assert client.post("/api/auth/login", headers=headers, json=body).status_code == 401
    with psycopg.connect(database_url) as conn:
        count, until = conn.execute("SELECT failed_count, window_started_at FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
        assert count == 1 and until is not None
    for _ in range(4):
        assert client.post("/api/auth/login", headers=headers, json=body).status_code == 401
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 401
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_login_attempts SET locked_until=CURRENT_TIMESTAMP + INTERVAL '5 seconds' WHERE login_hash=%s", (key,))
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 401
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_login_attempts SET window_started_at=CURRENT_TIMESTAMP - INTERVAL '16 minutes', locked_until=CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE login_hash=%s", (key,))
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 200


def test_existing_active_lock_remains_after_schema_update(monkeypatch):
    import hashlib
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    email = f"legacy-{secrets.token_hex(6)}@example.test"
    password = "not-a-real-password-123"
    key = hashlib.sha256(email.encode()).hexdigest()
    with psycopg.connect(database_url) as conn:
        conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s)", (email, auth.hash_password(password)))
        conn.execute("INSERT INTO auth_login_attempts(login_hash,failed_count,locked_until) VALUES (%s,5,CURRENT_TIMESTAMP + INTERVAL '5 minutes')", (key,))
    assert auth.authenticate(email, password) is None
    with psycopg.connect(database_url) as conn:
        state = conn.execute("SELECT failed_count, window_started_at FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
        assert state == (5, None)


def test_https_login_cookie_and_cross_origin_logout(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "https://testserver")
    monkeypatch.setattr(auth, "authenticate", lambda email, password: ("test-token", 42))
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/api/auth/login", headers={"origin": "https://testserver"}, json={"email": "test@example.test", "password": "test-only"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.post("/api/auth/logout", headers={"origin": "https://evil.example"}).status_code == 403


def test_login_database_error_does_not_expose_details(monkeypatch):
    import psycopg

    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    def fail(email, password):
        raise psycopg.OperationalError("test-sensitive-detail")
    monkeypatch.setattr(auth, "authenticate", fail)
    response = TestClient(app).post("/api/auth/login", headers={"origin": "http://testserver"}, json={"email": "test@example.test", "password": "test-only"})
    assert response.status_code == 503
    assert "test-sensitive-detail" not in response.text
    assert "set-cookie" not in response.headers


def test_inactive_user_and_existing_session_are_rejected(monkeypatch):
    import hashlib
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    email = f"inactive-{secrets.token_hex(6)}@example.test"
    token = secrets.token_urlsafe(32)
    with psycopg.connect(database_url) as conn:
        user_id = conn.execute("INSERT INTO users(login_id,password_hash,is_active) VALUES (%s,%s,FALSE) RETURNING id", (email, auth.hash_password("test-only-password"))).fetchone()[0]
        conn.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (hashlib.sha256(token.encode()).hexdigest(), user_id))
    client = TestClient(app, cookies={auth.COOKIE: token})
    headers = {"origin": "http://testserver"}
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": "test-only-password"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_idle_and_absolute_session_expiry_boundaries(monkeypatch):
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    email = f"expiry-{secrets.token_hex(6)}@example.test"
    password = "test-only-password-123"
    with psycopg.connect(database_url) as conn:
        user_id = conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id", (email, auth.hash_password(password))).fetchone()[0]
    client = TestClient(app)
    headers = {"origin": "http://testserver"}
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - INTERVAL '29 minutes 50 seconds' WHERE user_id=%s", (user_id,))
    assert client.get("/api/auth/me").status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - INTERVAL '30 minutes 5 seconds' WHERE user_id=%s", (user_id,))
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at=CURRENT_TIMESTAMP + INTERVAL '5 seconds', last_seen_at=CURRENT_TIMESTAMP WHERE user_id=%s", (user_id,))
    assert client.get("/api/auth/me").status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at=CURRENT_TIMESTAMP - INTERVAL '5 seconds', last_seen_at=CURRENT_TIMESTAMP WHERE user_id=%s", (user_id,))
    assert client.get("/api/auth/me").status_code == 401


def test_auth_database_rejects_login_when_both_scrypt_slots_are_busy(monkeypatch):
    import os
    import psycopg
    from fastapi import HTTPException

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    lock_a, lock_b = psycopg.connect(database_url), psycopg.connect(database_url)
    try:
        assert lock_a.execute("SELECT pg_try_advisory_xact_lock(736125,1)").fetchone()[0]
        assert lock_b.execute("SELECT pg_try_advisory_xact_lock(736125,2)").fetchone()[0]
        with pytest.raises(HTTPException) as error:
            auth.authenticate("busy@example.test", "test-only")
        assert error.value.status_code == 503
    finally:
        lock_a.rollback()
        lock_b.rollback()
        lock_a.close()
        lock_b.close()
