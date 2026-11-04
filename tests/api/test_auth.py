"""인증 단위·DB 통합 테스트: 비밀번호 해시, 세션, 로그인 잠금, 관리자 API.

- 역할: 비밀번호 해시, 세션 HMAC, 로그인 실패 제한·잠금 경계, 유휴·절대 만료, 사용자 격리, 관리자 권한, scrypt 동시 검증 상한을 확인한다.
- 하지 않는 일: DB 시험은 TEST_AUTH_DATABASE_URL이 있을 때만 돈다(없으면 건너뜀). 서비스 DB(Supabase)나 실제 사용자 데이터는 쓰지 않는다.
- 출처: SPEC 8.6(로그인 AC), docs/specs/login-auth.md, docs/research/auth-login-verification.md
"""
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


def test_login_validation_errors_do_not_echo_credentials(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    client = TestClient(app)
    password = "synthetic-secret-" * 70
    response = client.post("/api/auth/login", headers={"origin": "http://testserver"}, json={"email": "person@example.test", "password": password})
    assert response.status_code == 422
    assert password not in response.text


def test_admin_users_masks_email_local_part(monkeypatch):
    monkeypatch.setattr(auth, "admin_users", lambda _user_id: [{"id": 1, "email": "alice@example.test", "role": "user", "is_active": True}])
    app.dependency_overrides[auth.current_user_id] = lambda: 99
    try:
        response = TestClient(app).get("/api/admin/users")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["users"][0]["email"] == "a***@example.test"


def test_admin_users_masks_malformed_email_without_failing(monkeypatch):
    monkeypatch.setattr(auth, "admin_users", lambda _user_id: [{"id": 1, "email": "person@", "role": "user", "is_active": True}])
    app.dependency_overrides[auth.current_user_id] = lambda: 99
    try:
        response = TestClient(app).get("/api/admin/users")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["users"][0]["email"] == "***"


@pytest.mark.parametrize("email", ["person@", "@example.test", "first@@example.test", "person example@test.test", f"{'a' * 90}@example.test"])
def test_login_rejects_malformed_email_without_echoing(email, monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    response = TestClient(app).post("/api/auth/login", headers={"origin": "http://testserver"}, json={"email": email, "password": "synthetic-secret"})
    assert response.status_code == 422
    assert email not in response.text


def test_account_creation_rejects_malformed_email_before_database(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["backend.auth"])
    monkeypatch.setattr("builtins.input", lambda _prompt: "person@")
    monkeypatch.setattr(auth.getpass, "getpass", lambda _prompt: "a-strong-demo-password")
    with pytest.raises(SystemExit):
        auth.provision()


def test_account_deletion_cli_requires_exact_id_confirmation(monkeypatch):
    import builtins
    import sys

    deleted = []
    monkeypatch.setattr(sys, "argv", ["backend.auth", "--delete-user-id", "42"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: "41")
    monkeypatch.setattr(auth, "delete_provisioned_user", lambda user_id: deleted.append(user_id), raising=False)
    auth.provision()
    assert deleted == []


def test_account_deletion_cli_rejects_admin_role(monkeypatch):
    import builtins
    import sys

    deleted = []
    monkeypatch.setattr(sys, "argv", ["backend.auth", "--role", "admin", "--delete-user-id", "42"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: "42")
    monkeypatch.setattr(auth, "delete_provisioned_user", lambda user_id: deleted.append(user_id), raising=False)
    with pytest.raises(SystemExit):
        auth.provision()
    assert deleted == []


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
        assert client.get("/api/auth/me").json() == {"user_id": uid, "role": "user"}
    assert a.post("/api/auth/logout", headers=headers).status_code == 200
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").json() == {"user_id": id_b, "role": "user"}
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
        conn.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (auth.session_token_hash(token), user_id))
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


def test_admin_account_management_and_session_revocation(monkeypatch):
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    suffix = secrets.token_hex(6)
    admin_email, user_email = f"admin-{suffix}@example.test", f"user-{suffix}@example.test"
    password = "test-only-password-123"
    password_hash = auth.hash_password(password)
    with psycopg.connect(database_url) as conn:
        admin_id = conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES (%s,%s,'admin') RETURNING id", (admin_email, password_hash)).fetchone()[0]
        user_id = conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id", (user_email, password_hash)).fetchone()[0]
    admin, user, anonymous = TestClient(app), TestClient(app), TestClient(app)
    headers = {"origin": "http://testserver"}
    assert anonymous.get("/api/admin/users").status_code == 401
    for client, email in ((admin, admin_email), (user, user_email)):
        assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 200
    assert admin.get("/api/auth/me").json() == {"user_id": admin_id, "role": "admin"}
    assert user.get("/api/auth/me").json() == {"user_id": user_id, "role": "user"}
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE users SET role='admin' WHERE id=%s", (user_id,))
    assert user.get("/api/auth/me").json() == {"user_id": user_id, "role": "admin"}
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE users SET role='user' WHERE id=%s", (user_id,))
    assert user.get("/api/admin/users").status_code == 403
    assert user.patch(f"/api/admin/users/{user_id}", headers=headers, json={"is_active": False}).status_code == 403
    users = admin.get("/api/admin/users")
    assert users.status_code == 200
    assert any(item["id"] == user_id and item["role"] == "user" and item["is_active"] for item in users.json()["users"])
    assert admin.patch(f"/api/admin/users/{user_id}", headers={"origin": "https://evil.example"}, json={"is_active": False}).status_code == 403
    assert admin.patch(f"/api/admin/users/{admin_id}", headers=headers, json={"is_active": False}).status_code == 403
    assert admin.patch(f"/api/admin/users/{user_id}", headers=headers, json={"is_active": False}).status_code == 200
    assert user.get("/api/auth/me").status_code == 401
    assert admin.patch(f"/api/admin/users/{user_id}", headers=headers, json={"is_active": True}).status_code == 200
    assert user.get("/api/auth/me").status_code == 401
    assert user.post("/api/auth/login", headers=headers, json={"email": user_email, "password": password}).status_code == 200


def test_hash_only_cli_prints_a_scrypt_hash(monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys, "argv", ["backend.auth", "--hash-only"])
    monkeypatch.setattr(auth.getpass, "getpass", lambda _prompt: "a-strong-demo-password")
    auth.provision()
    encoded = capsys.readouterr().out.strip()
    assert encoded.startswith("scrypt$")
    assert auth.verify_password("a-strong-demo-password", encoded)

@pytest.mark.parametrize("mode,config,expected", [
    ("1", ("", "", "", ""), "default"),
    ("1", ("custom-admin@example.test", "valid", "custom-user@example.test", "valid"), "custom"),
    ("1", ("custom-admin@", "valid", "custom-user@example.test", "valid"), "invalid"),
    ("1", ("partial@example.test", "", "", ""), "invalid"),
    ("0", ("", "", "", ""), "none"),
    ("0", ("custom-admin@example.test", "valid", "custom-user@example.test", "valid"), "custom"),
])
def test_demo_seed_configuration(mode, config, expected):
    import os
    from pathlib import Path
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    seed = Path("db/007_demo_accounts.sql").read_text(encoding="utf-8")
    statement = seed[seed.index("DO $$"):]
    password_hash = auth.hash_password("custom-test-password") if "valid" in config else ""
    values = [password_hash if value == "valid" else value for value in config]
    with psycopg.connect(database_url) as conn:
        with conn.transaction(force_rollback=True):
            conn.execute("CREATE TEMP TABLE users (login_id text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL) ON COMMIT DROP")
            for key, value in zip(("demo_admin_email", "demo_admin_password_hash", "demo_user_email", "demo_user_password_hash"), values):
                conn.execute("SELECT set_config(%s, %s, true)", ("sojafit." + key, value))
            conn.execute("SELECT set_config('sojafit.demo_mode', %s, true)", (mode,))
            if expected == "invalid":
                with pytest.raises(psycopg.errors.RaiseException):
                    conn.execute(statement)
                return
            conn.execute(statement)
            rows = conn.execute("SELECT login_id, password_hash, role FROM users ORDER BY role").fetchall()
            if expected == "none":
                assert rows == []
            elif expected == "custom":
                assert rows == [(config[0], password_hash, "admin"), (config[2], password_hash, "user")]
            else:
                assert [(row[0], row[2]) for row in rows] == [("demo-admin@example.test", "admin"), ("demo-user@example.test", "user")]
                assert auth.verify_password("demo-admin-1234", rows[0][1])
                assert auth.verify_password("demo-user-1234", rows[1][1])
            conn.execute(statement)
            assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == len(rows)


def test_session_token_hash_uses_key_when_provided(monkeypatch):
    import hashlib
    import hmac

    token = "test-session-token"
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    assert auth.session_token_hash(token) == hashlib.sha256(token.encode()).hexdigest()
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    assert auth.session_token_hash(token) == hmac.new(b"x" * 32, token.encode(), hashlib.sha256).hexdigest()
    assert auth.session_token_hash(token) != hashlib.sha256(token.encode()).hexdigest()


def test_production_requires_valid_auth_secret(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        auth.validate_auth_configuration()
    monkeypatch.setenv("AUTH_SECRET", "short")
    with pytest.raises(RuntimeError):
        auth.validate_auth_configuration()
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    auth.validate_auth_configuration()


def test_keyed_session_login_rotation_and_logout(monkeypatch):
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    email = f"keyed-{secrets.token_hex(6)}@example.test"
    password = "test-only-password-123"
    with psycopg.connect(database_url) as conn:
        user_id = conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id", (email, auth.hash_password(password))).fetchone()[0]
    client = TestClient(app)
    headers = {"origin": "http://testserver"}
    assert client.post("/api/auth/login", headers=headers, json={"email": email, "password": password}).status_code == 200
    token = client.cookies.get(auth.COOKIE)
    with psycopg.connect(database_url) as conn:
        stored = conn.execute("SELECT token_hash FROM auth_sessions WHERE user_id=%s", (user_id,)).fetchone()[0]
    assert stored == auth.session_token_hash(token)
    assert client.get("/api/auth/me").status_code == 200
    monkeypatch.setenv("AUTH_SECRET", "y" * 32)
    assert client.get("/api/auth/me").status_code == 401
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM auth_sessions WHERE user_id=%s", (user_id,)).fetchone()[0] == 0


def test_delete_provisioned_user_removes_only_its_auth_rows(monkeypatch):
    import hashlib
    import os
    import secrets
    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    suffix = secrets.token_hex(6)
    emails = [f"remove-{suffix}@example.test", f"keep-{suffix}@example.test", f"admin-{suffix}@example.test"]
    password_hash = auth.hash_password("test-only-password-123")
    ids = []
    hashes = [hashlib.sha256(email.encode()).hexdigest() for email in emails]
    try:
        with psycopg.connect(database_url) as conn:
            ids = [row[0] for row in conn.execute(
                "INSERT INTO users(login_id,password_hash,is_active,role) VALUES (%s,%s,FALSE,'user'),(%s,%s,TRUE,'user'),(%s,%s,FALSE,'admin') RETURNING id",
                (emails[0], password_hash, emails[1], password_hash, emails[2], password_hash),
            ).fetchall()]
            conn.execute(
                "INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour'),(%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')",
                (secrets.token_hex(32), ids[0], secrets.token_hex(32), ids[1]),
            )
            conn.execute("INSERT INTO auth_login_attempts(login_hash,failed_count) VALUES (%s,1),(%s,2)", (hashes[0], hashes[1]))

        assert auth.delete_provisioned_user(ids[0]) is True
        assert auth.delete_provisioned_user(ids[0]) is False
        with pytest.raises(ValueError, match="administrator"):
            auth.delete_provisioned_user(ids[2])

        with psycopg.connect(database_url) as conn:
            assert conn.execute("SELECT count(*) FROM users WHERE id=%s", (ids[0],)).fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM auth_sessions WHERE user_id=%s", (ids[0],)).fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM auth_login_attempts WHERE login_hash=%s", (hashes[0],)).fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM users WHERE id=%s", (ids[1],)).fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM auth_sessions WHERE user_id=%s", (ids[1],)).fetchone()[0] == 1
            assert conn.execute("SELECT failed_count FROM auth_login_attempts WHERE login_hash=%s", (hashes[1],)).fetchone()[0] == 2
            assert conn.execute("SELECT count(*) FROM users WHERE id=%s AND role='admin'", (ids[2],)).fetchone()[0] == 1
    finally:
        if ids:
            with psycopg.connect(database_url) as conn:
                conn.execute("DELETE FROM users WHERE id = ANY(%s)", (ids,))
                conn.execute("DELETE FROM auth_login_attempts WHERE login_hash = ANY(%s)", (hashes,))


def test_app_startup_requires_key_outside_demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        with TestClient(app):
            pass
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    monkeypatch.delenv("AUTH_SECRET")
    monkeypatch.setenv("DEMO_MODE", "1")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_login_purges_expired_attempts_and_sessions_before_recording(monkeypatch):
    """로그인 때 만료된 시도·세션 행을 지워 무작위 이메일 공격으로 표가 끝없이 커지지 않게 한다(DB 없이 SQL 순서만 확인)."""
    statements = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def execute(self, sql, params=None): statements.append(sql)
        def fetchone(self):
            last = statements[-1]
            if "pg_try_advisory" in last:
                return (True,)
            if "failed_count, locked_until" in last:
                return (0, False, True)
            return None  # 없는 계정

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def cursor(self): return Cursor()

    monkeypatch.setattr(auth, "connection", lambda: Conn())
    assert auth.authenticate("nobody@example.test", "x") is None
    kinds = [s.split()[0] + " " + s.split()[2] for s in statements]
    assert kinds.index("DELETE auth_login_attempts") < kinds.index("INSERT auth_login_attempts")
    assert any(s.startswith("DELETE FROM auth_sessions WHERE expires_at") for s in statements)
