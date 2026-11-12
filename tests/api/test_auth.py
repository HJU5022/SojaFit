"""인증 단위·DB 통합 테스트: 비밀번호 해시, 세션, 로그인 잠금, 자기 가입, 관리자 API.

- 역할: 비밀번호 해시, 세션 HMAC, 로그인 실패 제한·잠금 경계, 유휴·절대 만료, 사용자 격리, 관리자 권한, scrypt 동시 검증 상한, 가입(중복 409·입력 미노출 422·출처 403·IP 하루 3회 429·Cloud Run IP 판단), IP당 15분 로그인 실패 30회 잠금을 확인한다.
- 하지 않는 일: DB 시험은 TEST_AUTH_DATABASE_URL이 있을 때만 돈다(없으면 건너뜀). 서비스 DB(Supabase)나 실제 사용자 데이터는 쓰지 않는다.
- 출처: SPEC 8.6(로그인 AC), docs/specs/login-auth.md, docs/research/auth-login-verification.md
"""
import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app


@pytest.fixture(autouse=True)
def clear_login_ip_attempts():
    """DB 시험마다 IP 로그인 실패 기록을 비운다."""
    # [왜] TestClient는 모든 요청을 같은 주소('testclient')로 보내므로 여러 시험의 로그인 실패가 한 IP에 쌓인다.
    # 15분 안에 30회를 넘으면 상관없는 뒤 시험이 IP 잠금(401)에 걸리므로 시험마다 비운다. 격리된 시험 DB에서만 돈다
    import os

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if url:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM auth_login_ip_attempts")


@pytest.mark.parametrize("http_impl", ["h11", "httptools"])
def test_google_callback_query_is_not_written_to_uvicorn_access_logs(http_impl):
    import os
    import socket
    import subprocess
    import sys
    import tempfile
    import time

    import httpx

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = os.environ.copy()
    env.update({"GOOGLE_AUTH_ENABLED": "1", "GOOGLE_CLIENT_ID": "synthetic-client", "GOOGLE_CLIENT_SECRET": "synthetic-secret", "DEMO_MODE": "1", "AUTH_SECRET": "test-only-secret-32-bytes-minimum"})
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port), "--http", http_impl],
            stdout=output, stderr=subprocess.STDOUT, env=env,
        )
        try:
            url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 15
            while True:
                try:
                    response = httpx.get(url + "/health?request=ordinary", timeout=1)
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    if server.poll() is not None or time.monotonic() >= deadline:
                        raise AssertionError("Uvicorn test server did not start")
                    time.sleep(0.05)
            assert response.status_code == 200
            for path in ("/api/auth/google/callback", "/api/auth/google/callback/", "/api/auth/google/call%62ack"):
                response = httpx.get(url + path + "?code=synthetic-code&state=synthetic-state", timeout=3, follow_redirects=False)
                assert response.status_code in (303, 307)
            assert httpx.get(url + "/api/auth/google/callback-other?request=ordinary", timeout=3).status_code == 404
        finally:
            server.terminate()
            server.wait(timeout=10)
        output.seek(0)
        logs = output.read()
    assert "synthetic-code" not in logs
    assert "synthetic-state" not in logs
    assert "/api/auth/google/callback" in logs
    # [왜] 쿼리 글은 Google 콜백뿐 아니라 모든 경로에서 가린다(backend/logs.py의 hide_query). 경로는 남는다
    assert "/api/auth/google/callback-other?<redacted>" in logs
    assert "/health?<redacted>" in logs
    assert "request=ordinary" not in logs


def test_google_auth_schema_restricts_public_access_and_duplicate_bindings():
    import os

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity, EXISTS (SELECT 1 FROM aclexplode(coalesce(relacl, acldefault('r', relowner))) a WHERE a.grantee = 0) "
            "FROM pg_class WHERE relname IN ('auth_google_states', 'auth_google_identities')"
        ).fetchall()
        assert len(rows) == 2  # auth_google_pending은 029가 지웠다
        assert all(rls and not public_select for _, rls, public_select in rows)
        user = conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES ('google-schema@example.test', 'fake', 'admin') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES ('issuer', 'subject', %s)", (user,))
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES ('issuer', 'other', %s)", (user,))
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES ('issuer', 'subject', %s)", (user,))
        conn.rollback()


def test_google_state_is_bound_to_browser_and_consumed_once(monkeypatch):
    import os

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    state, browser, verifier, nonce = auth.create_google_state()
    assert auth.consume_google_state(state, "another-browser") is None
    assert auth.consume_google_state(state, browser) == (verifier, nonce)
    assert auth.consume_google_state(state, browser) is None
    state, browser, _, _ = auth.create_google_state()
    with psycopg.connect(url) as conn:
        conn.execute("UPDATE auth_google_states SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'")
    assert auth.consume_google_state(state, browser) is None


def test_google_revocation_clears_the_link_and_sessions(monkeypatch):
    import os

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    with psycopg.connect(url) as conn:
        user_id = conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES ('oauth-admin@example.test', 'fake', 'admin') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES ('https://accounts.google.com', 'synthetic-subject', %s)", (user_id,))
    try:
        token, actual_id = auth.google_session("https://accounts.google.com", "synthetic-subject")
        assert actual_id == user_id
        assert auth.revoke_google_link(user_id)
        with psycopg.connect(url) as conn:
            assert conn.execute("SELECT 1 FROM auth_sessions WHERE token_hash=%s", (auth.session_token_hash(token),)).fetchone() is None
        assert auth.google_session("https://accounts.google.com", "synthetic-subject") is None
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM users WHERE id=%s", (user_id,))


def test_google_approval_flow_is_gone(monkeypatch):
    """2b: 승인 대기 코드가 없다. CLI 옵션은 거절되고 pending 라우트는 구글을 켜도 404이며 함수도 남지 않았다."""
    import sys

    for name in ("request_google_link", "google_pending_email", "approve_google_link"):
        assert not hasattr(auth, name)
    monkeypatch.setattr(sys, "argv", ["backend.auth", "--approve-google"])
    with pytest.raises(SystemExit) as exit_info:
        auth.provision()
    assert exit_info.value.code == 2  # argparse: 모르는 옵션
    monkeypatch.setenv("GOOGLE_AUTH_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    response = TestClient(app).get("/api/auth/google/pending", cookies={"sojafit_google_pending": "x"})
    assert response.status_code == 404


def test_admin_deactivation_revokes_sessions(monkeypatch):
    import os
    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    with psycopg.connect(url) as conn:
        ids = [row[0] for row in conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES ('deactivate-1@example.test', 'fake', 'admin'), ('deactivate-2@example.test', 'fake', 'admin') RETURNING id").fetchall()]
        conn.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '1 hour')", ("a" * 64, ids[0]))
    try:
        assert auth.deactivate_admin(ids[0])
        with psycopg.connect(url) as conn:
            assert conn.execute("SELECT is_active FROM users WHERE id=%s", (ids[0],)).fetchone() == (False,)
            assert conn.execute("SELECT 1 FROM auth_sessions WHERE user_id=%s", (ids[0],)).fetchone() is None
        # This test database may contain other admins from other tests.
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM users WHERE id = ANY(%s)", (ids,))


def test_google_id_token_verifies_signature_and_identity_claims():
    import time

    from joserfc import jwt
    from joserfc.jwk import RSAKey

    key = RSAKey.generate_key(2048, {"kid": "test-key"})
    jwks = {"keys": [key.as_dict()]}
    claims = {"iss": "https://accounts.google.com", "sub": "synthetic-subject", "aud": "test-client", "iat": int(time.time()), "exp": int(time.time()) + 60, "nonce": "expected-nonce", "email": "admin@example.test", "email_verified": True}

    def token(values, signing_key=key):
        return jwt.encode({"alg": "RS256", "kid": "test-key"}, values, signing_key)

    assert auth.verify_google_id_token(token(claims), jwks, "test-client", "expected-nonce") == ("https://accounts.google.com", "synthetic-subject", "admin@example.test")
    for field, value in (("iss", "https://evil.example"), ("aud", "other-client"), ("nonce", "wrong"), ("email_verified", False), ("exp", int(time.time()) - 60)):
        assert auth.verify_google_id_token(token({**claims, field: value}), jwks, "test-client", "expected-nonce") is None
    other_key = RSAKey.generate_key(2048, {"kid": "test-key"})
    assert auth.verify_google_id_token(token(claims, other_key), jwks, "test-client", "expected-nonce") is None


def test_google_token_exchange_sends_pkce_to_fixed_google_endpoint(monkeypatch):
    import time
    import httpx
    from joserfc import jwt
    from joserfc.jwk import RSAKey

    monkeypatch.setenv("AUTH_ORIGIN", "http://localhost:8000")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    key = RSAKey.generate_key(2048, {"kid": "test-key"})
    token = jwt.encode({"alg": "RS256", "kid": "test-key"}, {"iss": "https://accounts.google.com", "sub": "synthetic-subject", "aud": "synthetic-client", "iat": int(time.time()), "exp": int(time.time()) + 60, "nonce": "synthetic-nonce", "email": "admin@example.test", "email_verified": True}, key)

    def provider(url, *, data, **kwargs):
        assert url == "https://oauth2.googleapis.com/token"
        assert data["code_verifier"] == "synthetic-verifier"
        assert data["client_id"] == "synthetic-client"
        assert data["client_secret"] == "synthetic-secret"
        return httpx.Response(200, json={"access_token": "synthetic-access", "token_type": "Bearer", "id_token": token}, request=httpx.Request("POST", url))

    monkeypatch.setattr(auth.httpx, "post", provider)
    monkeypatch.setattr(auth.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"keys": [key.as_dict()]}, request=httpx.Request("GET", url)))
    assert auth.fetch_google_identity("synthetic-code", "synthetic-verifier", "synthetic-nonce") == ("https://accounts.google.com", "synthetic-subject", "admin@example.test")


def test_google_oauth_is_disabled_without_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_AUTH_ENABLED", raising=False)
    assert TestClient(app).get("/api/auth/google/start", follow_redirects=False).status_code == 404


def test_google_callback_requires_state_and_logs_in_the_account_with_the_same_email(monkeypatch):
    # [왜] 11-10 정운 결정: 이미 있는 이메일(관리자 · 비밀번호 계정)도 Google이 확인한 같은 이메일이면 운영자 승인 없이 연결해 로그인한다.
    #      연결할 수 없는 경우(비활성 · 이미 다른 Google 신원에 연결됨)는 승인 대기가 아니라 로그인 오류다
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setenv("GOOGLE_AUTH_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setattr(auth, "create_google_state", lambda: ("state-value", "browser-value", "verifier-value", "nonce-value"))
    monkeypatch.setattr(auth, "consume_google_state", lambda state, browser: ("verifier-value", "nonce-value") if (state, browser) == ("state-value", "browser-value") else None)
    monkeypatch.setattr(auth, "fetch_google_identity", lambda code, verifier, nonce: ("https://accounts.google.com", "synthetic-subject", "admin@example.test"))
    monkeypatch.setattr(auth, "google_session", lambda issuer, subject: None)
    outcome = {"signup": ("session-token", 4)}  # 이메일이 같은 기존 계정에 연결됨
    monkeypatch.setattr(auth, "google_signup", lambda issuer, subject, email, consent: outcome["signup"])
    client = TestClient(app)
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code == 303
    assert parse_qs(urlsplit(start.headers["location"]).query)["state"] == ["state-value"]
    assert "httponly" in start.headers["set-cookie"].lower()
    failed = client.get("/api/auth/google/callback?code=synthetic-code&state=wrong", follow_redirects=False)
    assert failed.status_code == 303
    assert failed.headers["location"] == "/login?google=error"
    client.get("/api/auth/google/start", follow_redirects=False)
    linked = client.get("/api/auth/google/callback?code=synthetic-code&state=state-value", follow_redirects=False)
    assert linked.status_code == 303 and linked.headers["location"] == "/login"  # 승인 대기 화면이 아니라 바로 로그인
    assert f"{auth.COOKIE}=session-token" in linked.headers["set-cookie"]
    assert linked.headers["cache-control"] == "no-store"
    outcome["signup"] = None  # 비활성 · 이미 다른 신원에 연결됨
    client.get("/api/auth/google/start", follow_redirects=False)
    refused = client.get("/api/auth/google/callback?code=synthetic-code&state=state-value", follow_redirects=False)
    assert refused.status_code == 303 and refused.headers["location"] == "/login?google=error"
    assert auth.COOKIE not in refused.headers.get("set-cookie", "")


def _google_callback_env(monkeypatch, signup):
    monkeypatch.setenv("GOOGLE_AUTH_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setattr(auth, "create_google_state", lambda: ("state-value", "browser-value", "verifier-value", "nonce-value"))
    monkeypatch.setattr(auth, "consume_google_state", lambda state, browser: ("verifier-value", "nonce-value") if (state, browser) == ("state-value", "browser-value") else None)
    monkeypatch.setattr(auth, "fetch_google_identity", lambda code, verifier, nonce: ("https://accounts.google.com", "new-subject", "new@example.test"))
    monkeypatch.setattr(auth, "google_session", lambda issuer, subject: None)
    monkeypatch.setattr(auth, "google_signup", signup)


def test_google_new_identity_creates_account_only_with_consent_cookie(monkeypatch):
    calls = []

    def signup(issuer, subject, email, consent):
        calls.append(consent)
        return ("session-token", 7) if consent else "consent"

    _google_callback_env(monkeypatch, signup)
    client = TestClient(app)
    client.get("/api/auth/google/start", follow_redirects=False)  # 동의 표시 없이 시작
    refused = client.get("/api/auth/google/callback?code=c&state=state-value", follow_redirects=False)
    assert refused.headers["location"] == "/login?google=consent"
    assert auth.COOKIE not in refused.headers.get("set-cookie", "")
    client.get("/api/auth/google/start?consent=1", follow_redirects=False)  # 로그인 화면의 동의 체크 뒤
    created = client.get("/api/auth/google/callback?code=c&state=state-value", follow_redirects=False)
    assert created.headers["location"] == "/login"
    assert f"{auth.COOKIE}=session-token" in created.headers["set-cookie"]
    assert calls == [False, True]
    assert "sojafit_google_consent" not in client.cookies  # 한 번 쓰고 지운다


@pytest.fixture
def google_db(monkeypatch):
    import os
    from pathlib import Path

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    yield url
    with psycopg.connect(url) as conn:
        conn.execute("DELETE FROM users WHERE login_id LIKE 'gt-%' OR login_id = 'demo-a@example.test'")


def _count(url, sql, *args):
    import psycopg

    with psycopg.connect(url) as conn:
        return conn.execute(sql, args).fetchone()[0]


ISSUER = "https://accounts.google.com"


def test_google_signup_without_consent_creates_no_user(google_db):
    assert auth.google_signup(ISSUER, "gt-sub-1", "gt-1@example.test", False) == "consent"
    assert _count(google_db, "SELECT count(*) FROM users WHERE login_id = 'gt-1@example.test'") == 0
    assert _count(google_db, "SELECT count(*) FROM auth_google_identities WHERE subject = 'gt-sub-1'") == 0


def test_google_signup_account_has_no_usable_password_and_second_login_reuses_it(google_db):
    token, user_id = auth.google_signup(ISSUER, "gt-sub-2", "GT-2@Example.test", True)  # 이메일은 소문자로 저장
    assert token and _count(google_db, "SELECT role FROM users WHERE id = %s", user_id) == "user"
    assert _count(google_db, "SELECT password_hash FROM users WHERE id = %s", user_id) == auth.GOOGLE_PASSWORD_HASH != auth.DEMO_PASSWORD_HASH
    again = auth.google_session(ISSUER, "gt-sub-2")  # 두 번째 로그인: 같은 계정, 행은 그대로
    assert again and again[1] == user_id
    assert _count(google_db, "SELECT count(*) FROM users WHERE login_id = 'gt-2@example.test'") == 1
    assert _count(google_db, "SELECT count(*) FROM auth_google_identities WHERE subject = 'gt-sub-2'") == 1
    # 비밀번호 로그인은 500이 아니라 평범한 401이다
    response = TestClient(app).post("/api/auth/login", json={"email": "gt-2@example.test", "password": auth.GOOGLE_PASSWORD_HASH}, headers={"origin": "http://testserver"})
    assert response.status_code == 401


def test_google_password_marker_never_matches_demo_button_login(google_db):
    assert auth.google_signup(ISSUER, "gt-sub-3", "demo-a@example.test", True)  # 데모 계정과 같은 이메일을 Google 가입이 먼저 차지한 경우
    assert auth.demo_session("a") is None


def _account(url, login_id, role="user", active=True, password_hash="fake"):
    import psycopg

    with psycopg.connect(url) as conn:
        return conn.execute("INSERT INTO users (login_id, password_hash, role, is_active) VALUES (%s, %s, %s, %s) RETURNING id", (login_id, password_hash, role, active)).fetchone()[0]


@pytest.mark.parametrize("role", ["user", "admin"])
def test_google_signup_links_the_active_account_with_the_same_email_without_approval(google_db, role):
    """11-10 결정: 같은 이메일의 활성 계정은 역할(관리자 포함)과 상관없이 승인 없이 연결 · 로그인한다. 동의는 필요 없고 사용자 행은 늘지 않는다."""
    account = _account(google_db, "gt-taken@example.test", role)
    token, user_id = auth.google_signup(ISSUER, "gt-sub-4", " GT-Taken@Example.test ", False)  # 대소문자 · 공백이 달라도 같은 이메일
    assert user_id == account and token
    assert _count(google_db, "SELECT count(*) FROM users WHERE lower(login_id) = 'gt-taken@example.test'") == 1
    assert _count(google_db, "SELECT user_id FROM auth_google_identities WHERE subject = 'gt-sub-4'") == account
    assert _count(google_db, "SELECT password_hash FROM users WHERE id = %s", account) == "fake"  # 기존 비밀번호 해시는 그대로
    client = TestClient(app)
    client.cookies.set(auth.COOKIE, token)
    assert client.get("/api/auth/me").json() == {"user_id": account, "role": role}  # 관리자는 관리자 세션을 받는다
    again = auth.google_session(ISSUER, "gt-sub-4")  # 두 번째 로그인: 같은 계정, 행은 그대로
    assert again and again[1] == account
    assert _count(google_db, "SELECT count(*) FROM auth_google_identities WHERE user_id = %s", account) == 1


def test_google_signup_does_not_link_an_email_that_differs_by_one_character(google_db):
    """이메일이 한 글자라도 다르면 기존 계정이 아니라 새 계정 경로다(동의가 있어야 만든다)."""
    account = _account(google_db, "gt-exact@example.test", "admin")
    for other in ("gt-exacy@example.test", "gt-exact@example.tes", "gt-exac@example.test", "xgt-exact@example.test", "gt-exact@example.test.kr"):
        assert auth.google_signup(ISSUER, "gt-sub-6", other, False) == "consent", other
    assert _count(google_db, "SELECT count(*) FROM auth_google_identities WHERE subject = 'gt-sub-6' OR user_id = %s", account) == 0
    other_token, other_id = auth.google_signup(ISSUER, "gt-sub-6", "gt-exac@example.test", True)
    assert other_id != account and other_token


def test_google_signup_never_links_or_signs_in_an_inactive_account(google_db):
    account = _account(google_db, "gt-off@example.test", "admin", active=False)
    assert auth.google_signup(ISSUER, "gt-sub-7", "gt-off@example.test", True) is None
    assert auth.google_session(ISSUER, "gt-sub-7") is None
    assert _count(google_db, "SELECT count(*) FROM auth_google_identities WHERE user_id = %s", account) == 0
    assert _count(google_db, "SELECT count(*) FROM auth_sessions WHERE user_id = %s", account) == 0


def test_google_signup_does_not_link_a_second_identity_to_an_already_linked_account(google_db):
    """이미 한 Google 신원에 연결된 계정에 다른 Google 신원이 같은 이메일로 와도 연결 · 로그인하지 않는다(user_id UNIQUE)."""
    account = _account(google_db, "gt-two@example.test", "user")
    assert auth.google_signup(ISSUER, "gt-sub-8", "gt-two@example.test", False)
    sessions = _count(google_db, "SELECT count(*) FROM auth_sessions WHERE user_id = %s", account)
    assert auth.google_signup(ISSUER, "gt-sub-9", "gt-two@example.test", True) is None
    assert auth.google_session(ISSUER, "gt-sub-9") is None
    assert _count(google_db, "SELECT subject FROM auth_google_identities WHERE user_id = %s", account) == "gt-sub-8"
    assert _count(google_db, "SELECT count(*) FROM auth_sessions WHERE user_id = %s", account) == sessions


def test_password_login_keeps_working_after_the_google_link(google_db, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-32-bytes-minimum")
    account = _account(google_db, "gt-pw@example.test", "user", password_hash=auth.hash_password("long enough password 1"))
    assert auth.google_signup(ISSUER, "gt-sub-10", "gt-pw@example.test", False)
    response = TestClient(app).post("/api/auth/login", json={"email": "gt-pw@example.test", "password": "long enough password 1"}, headers={"origin": "http://testserver"})
    assert response.status_code == 200 and response.json() == {"user_id": account}


def test_google_signup_rolls_back_the_user_when_the_identity_is_already_linked(google_db):
    assert auth.google_signup(ISSUER, "gt-sub-5", "gt-5@example.test", True)
    assert auth.google_signup(ISSUER, "gt-sub-5", "gt-5b@example.test", True) is None  # 같은 신원, 다른 이메일: 새 사용자 행도 남기지 않는다
    assert _count(google_db, "SELECT count(*) FROM users WHERE login_id = 'gt-5b@example.test'") == 0


def test_email_signup_is_closed_unless_demo_mode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    response = TestClient(app).post("/api/auth/signup", json={"email": "someone@example.test", "password": "long-enough-password", "consent": True},
                                    headers={"origin": "http://testserver"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"



def test_two_approved_google_admins_get_isolated_sessions(monkeypatch):
    import os
    from pathlib import Path

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("DEMO_MODE", "0")  # 공개 배포와 같은 설정: 이메일 가입은 닫혀도 연결된 관리자는 Google로 들어온다
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-32-bytes-minimum")
    monkeypatch.setenv("GOOGLE_AUTH_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setattr(auth, "fetch_google_identity", lambda code, verifier, nonce: ("https://accounts.google.com", code, f"{code}@example.test"))
    with psycopg.connect(url) as conn:
        ids = [conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES (%s, 'fake', 'admin') RETURNING id", (f"google-{i}@example.test",)).fetchone()[0] for i in (1, 2)]
        for index, user_id in enumerate(ids, 1):
            conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES (%s, %s, %s)", ("https://accounts.google.com", f"google-{index}", user_id))
    try:
        from urllib.parse import parse_qs, urlsplit

        clients = [TestClient(app), TestClient(app)]
        for index, client in enumerate(clients, 1):
            start = client.get("/api/auth/google/start", follow_redirects=False)
            state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
            assert client.get(f"/api/auth/google/callback?code=google-{index}&state={state}").status_code == 200
            assert client.get("/api/auth/me").json() == {"user_id": ids[index - 1], "role": "admin", "email": f"google-{index}@example.test"}
        assert clients[0].post("/api/auth/logout", headers={"origin": "http://testserver"}).status_code == 200
        assert clients[0].get("/api/auth/me").status_code == 401
        assert clients[1].get("/api/auth/me").json()["user_id"] == ids[1]
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM users WHERE id = ANY(%s)", (ids,))


def test_unlinked_google_admin_with_the_same_email_signs_in_through_the_callback_without_approval(monkeypatch):
    import os
    from pathlib import Path

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-32-bytes-minimum")
    monkeypatch.setenv("GOOGLE_AUTH_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setattr(auth, "fetch_google_identity", lambda code, verifier, nonce: ("https://accounts.google.com", code, f"{code}@example.test"))
    with psycopg.connect(url) as conn:
        admin = conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES ('gt-auto-admin@example.test', 'fake', 'admin') RETURNING id").fetchone()[0]
    try:
        from urllib.parse import parse_qs, urlsplit

        client = TestClient(app)
        start = client.get("/api/auth/google/start", follow_redirects=False)  # 동의 표시 없이: 기존 계정 연결에는 필요 없다
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        # code가 곧 subject이고 이메일은 {code}@example.test라서 로그인 이메일과 같게 맞춘다
        monkeypatch.setattr(auth, "fetch_google_identity", lambda code, verifier, nonce: ("https://accounts.google.com", "gt-auto-subject", "gt-auto-admin@example.test"))
        callback = client.get(f"/api/auth/google/callback?code=c&state={state}", follow_redirects=False)
        assert callback.status_code == 303 and callback.headers["location"] == "/login"
        assert client.get("/api/auth/me").json() == {"user_id": admin, "role": "admin"}
        with psycopg.connect(url) as conn:
            assert conn.execute("SELECT count(*) FROM auth_google_identities WHERE user_id = %s", (admin,)).fetchone()[0] == 1
            assert conn.execute("SELECT to_regclass('auth_google_pending')").fetchone()[0] is None  # 승인 대기 표가 없다(029)
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin,))


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


def test_me_exposes_only_the_authenticated_accounts_email(monkeypatch):
    calls = []
    app.dependency_overrides[auth.current_user] = lambda: (7, 'user')
    monkeypatch.setattr(auth, 'account_email', lambda user_id: calls.append(user_id) or 'signed-in@example.test')
    try:
        response = TestClient(app).get('/api/auth/me?user_id=8')
        assert response.status_code == 200
        assert response.json() == {'user_id': 7, 'role': 'user', 'email': 'signed-in@example.test'}
        assert response.headers['cache-control'] == 'no-store'
        assert calls == [7]
    finally:
        app.dependency_overrides.clear()


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
        assert client.get("/api/auth/me").json() == {"user_id": uid, "role": "user", "email": email}
    assert a.post("/api/auth/logout", headers=headers).status_code == 200
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").json() == {"user_id": id_b, "role": "user", "email": email_b}
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
    assert auth.authenticate(email, password, "testclient") is None
    with psycopg.connect(database_url) as conn:
        state = conn.execute("SELECT failed_count, window_started_at FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
        assert state == (5, None)


def test_https_login_cookie_and_cross_origin_logout(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "https://testserver")
    monkeypatch.setattr(auth, "authenticate", lambda email, password, ip: ("test-token", 42))
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/api/auth/login", headers={"origin": "https://testserver"}, json={"email": "test@example.test", "password": "test-only"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.post("/api/auth/logout", headers={"origin": "https://evil.example"}).status_code == 403


def test_login_database_error_does_not_expose_details(monkeypatch):
    import psycopg

    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    def fail(email, password, ip):
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
        conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - INTERVAL '1 hour 59 minutes 50 seconds' WHERE user_id=%s", (user_id,))
    assert client.get("/api/auth/me").status_code == 200
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - INTERVAL '2 hours 5 seconds' WHERE user_id=%s", (user_id,))
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
            auth.authenticate("busy@example.test", "test-only", "testclient")
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
    assert admin.get("/api/auth/me").json() == {"user_id": admin_id, "role": "admin", "email": admin_email}
    assert user.get("/api/auth/me").json() == {"user_id": user_id, "role": "user", "email": user_email}
    with psycopg.connect(database_url) as conn:
        conn.execute("UPDATE users SET role='admin' WHERE id=%s", (user_id,))
    assert user.get("/api/auth/me").json() == {"user_id": user_id, "role": "admin", "email": user_email}
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

@pytest.mark.parametrize("mode", ["1", "0", ""])
def test_demo_accounts_are_created_on_first_demo_login_only_in_demo_mode(mode, monkeypatch):
    """데모 모드에서만 첫 데모 로그인이 비밀번호 없는 일반 사용자 A · B를 만들고(다시 불러도 그 행 그대로), 저장소에 비밀번호 해시가 없다."""
    import os

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEMO_MODE", mode)
    emails = list(auth.DEMO_ACCOUNTS.values())
    with psycopg.connect(database_url) as conn:
        conn.execute("DELETE FROM users WHERE login_id = ANY(%s)", (emails,))
    try:
        results = [auth.demo_session(account) for account in ("a", "b", "a")]
        with psycopg.connect(database_url) as conn:
            rows = conn.execute("SELECT id, login_id, password_hash, role, is_active FROM users WHERE login_id = ANY(%s) ORDER BY login_id", (emails,)).fetchall()
        if mode == "1":
            assert all(results) and results[0][1] == results[2][1] != results[1][1]  # 두 번째 A는 같은 계정을 재사용한다
            assert [row[1:] for row in rows] == [(email, auth.DEMO_PASSWORD_HASH, "user", True) for email in emails]
            assert not auth.verify_password("", auth.DEMO_PASSWORD_HASH) and not auth.verify_password("demo-button-login-only", auth.DEMO_PASSWORD_HASH)
        else:
            assert results == [None, None, None] and rows == []
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE login_id = ANY(%s)", (emails,))


def test_session_issuing_paths_purge_expired_sessions(monkeypatch):
    """만료 세션 청소: 데모 로그인 · 구글 로그인 · 가입이 세션을 주기 전에 만료 행을 지우고, 안 만료된 행은 남긴다."""
    import os

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("AUTH_SECRET", "test-only-secret-32-bytes-minimum")
    with psycopg.connect(database_url) as conn:
        owner = conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES ('purge-owner@example.test', 'fake', 'user') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES ('https://accounts.google.com', 'purge-subject', %s)", (owner,))
    emails = list(auth.DEMO_ACCOUNTS.values()) + ["purge-signup@example.test"]

    def reset():
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash IN ('e' || repeat('0', 63), 'f' || repeat('0', 63))")
            conn.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES ('e' || repeat('0', 63), %s, CURRENT_TIMESTAMP - INTERVAL '1 second'), "
                         "('f' || repeat('0', 63), %s, CURRENT_TIMESTAMP + INTERVAL '1 hour')", (owner, owner))

    def counts():
        with psycopg.connect(database_url) as conn:
            return [conn.execute("SELECT count(*) FROM auth_sessions WHERE token_hash = %s", (h,)).fetchone()[0] for h in ("e" + "0" * 63, "f" + "0" * 63)]

    try:
        for issue in (lambda: auth.demo_session("a"), lambda: auth.google_session("https://accounts.google.com", "purge-subject"),
                      lambda: auth.google_signup("https://accounts.google.com", "purge-new", "purge-signup@example.test", True),
                      lambda: auth.signup("purge-signup2@example.test", "a-strong-demo-password", "purge-ip")):
            reset()
            assert issue()
            assert counts() == [0, 1]
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE id = %s OR login_id = ANY(%s) OR login_id = 'purge-signup2@example.test'", (owner, emails))
            conn.execute("DELETE FROM auth_signup_attempts")


def test_demo_login_routes_do_not_exist_outside_demo_mode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setattr(auth, "demo_session", lambda *args: pytest.fail("demo login must not run outside demo mode"))
    client = TestClient(app)
    for response in (client.get("/api/auth/demo"), client.post("/api/auth/demo-login", headers={"origin": "http://testserver"}, json={"account": "a"}),
                     client.post("/api/auth/demo-login", json={"account": "z"})):
        assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
    monkeypatch.setenv("DEMO_MODE", "1")
    assert client.get("/api/auth/demo").json() == {"enabled": True}
    assert client.post("/api/auth/demo-login", json={"account": "a"}).status_code == 403  # Origin 없음
    for body in ({"account": "c"}, {"account": "demo-a@example.test"}, {"account": "a", "user_id": 1}, {}):
        assert client.post("/api/auth/demo-login", headers={"origin": "http://testserver"}, json=body).status_code == 422


def test_database_demo_buttons_create_and_log_into_separate_users_only(monkeypatch):
    """버튼 로그인은 첫 로그인 때 만든 데모 계정 A · B(서로 다른 일반 사용자)에만 세션을 주고, 비밀번호 로그인은 늘 실패하며, 다른 계정에는 닿지 않는다."""
    import hashlib
    import os

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("DEMO_MODE", "1")
    headers = {"origin": "http://testserver"}
    emails = list(auth.DEMO_ACCOUNTS.values())
    with psycopg.connect(database_url) as conn:
        conn.execute("DELETE FROM users WHERE login_id = ANY(%s)", (emails,))
    try:
        clients = {account: TestClient(app) for account in auth.DEMO_ACCOUNTS}
        ids = {}
        for account, client in clients.items():
            response = client.post("/api/auth/demo-login", headers=headers, json={"account": account})
            assert response.status_code == 200 and "httponly" in response.headers["set-cookie"].lower()
            ids[account] = response.json()["user_id"]
            assert client.get("/api/auth/me").json() == {"user_id": ids[account], "role": "user", "email": auth.DEMO_ACCOUNTS[account]}
        assert ids["a"] != ids["b"]  # 두 창(쿠키가 따로)에서 서로 다른 사용자다
        for password in ("", "demo-button-login-only", auth.DEMO_PASSWORD_HASH):  # 비밀번호 로그인은 늘 실패
            response = TestClient(app).post("/api/auth/login", headers=headers, json={"email": emails[0], "password": password or "x"})
            assert response.status_code == 401
        # 같은 이메일이지만 비밀번호로 가입한 계정 · 관리자로 바뀐 계정 · 비활성 계정은 버튼으로 닿지 않는다
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE users SET password_hash=%s WHERE login_id=%s", (auth.hash_password("a-real-password-123"), emails[1]))
            conn.execute("UPDATE users SET role='admin' WHERE login_id=%s", (emails[0],))
        for account in auth.DEMO_ACCOUNTS:
            response = TestClient(app).post("/api/auth/demo-login", headers=headers, json={"account": account})
            assert response.status_code == 404 and "set-cookie" not in response.headers
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE users SET role='user', is_active=FALSE WHERE login_id=%s", (emails[0],))
        assert TestClient(app).post("/api/auth/demo-login", headers=headers, json={"account": "a"}).status_code == 404
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE login_id = ANY(%s)", (emails,))
            conn.execute("DELETE FROM auth_login_attempts WHERE login_hash = ANY(%s)", ([hashlib.sha256(email.encode()).hexdigest() for email in emails],))


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
        with pytest.raises(ValueError, match="(?i)administrator"):
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
    assert auth.authenticate("nobody@example.test", "x", "testclient") is None
    kinds = [s.split()[0] + " " + s.split()[2] for s in statements]
    assert kinds.index("DELETE auth_login_attempts") < kinds.index("INSERT auth_login_attempts")
    assert kinds.index("DELETE auth_login_ip_attempts") < kinds.index("INSERT auth_login_ip_attempts")
    assert any(s.startswith("DELETE FROM auth_sessions WHERE expires_at") for s in statements)


def test_question_endpoint_is_not_exposed(monkeypatch):
    class Graph:
        def invoke(self, state):
            return {"answer": "answer"}

    monkeypatch.setattr("backend.main.get_question_graph", lambda: Graph(), raising=False)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: (17, "user")
    try:
        response = TestClient(app).post(
            "/api/ask", json={"question": "What is SS34?"}, headers={"Origin": "http://testserver"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_signup_rejects_missing_or_cross_origin(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    client = TestClient(app)
    body = {"email": "new-person@example.test", "password": "synthetic-pass-123", "consent": True}
    assert client.post("/api/auth/signup", json=body).status_code == 403
    assert client.post("/api/auth/signup", json=body, headers={"origin": "https://evil.example"}).status_code == 403


@pytest.mark.parametrize("email, password", [("new-person@example.test", "short-7"), ("person@", "synthetic-pass-123"), ("@example.test", "synthetic-pass-123")])
def test_signup_validation_errors_do_not_echo_input(email, password, monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    response = TestClient(app).post("/api/auth/signup", headers={"origin": "http://testserver"}, json={"email": email, "password": password, "consent": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert email not in response.text and password not in response.text


@pytest.mark.parametrize("consent", ["missing", False, None, "true", 1])
def test_signup_requires_explicit_consent_before_touching_the_database(consent, monkeypatch):
    """처리방침 고지 동의(consent)가 정확히 true가 아니면 공통 422이고 가입 처리(DB)를 부르지 않는다."""
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setattr(auth, "signup", lambda *args: pytest.fail("signup must not run without consent"))
    body = {"email": "new-person@example.test", "password": "synthetic-pass-123"}
    if consent != "missing":
        body["consent"] = consent
    response = TestClient(app).post("/api/auth/signup", headers={"origin": "http://testserver"}, json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "synthetic-pass-123" not in response.text


@pytest.mark.parametrize("method, path, body, handler", [
    ("post", "/api/auth/login", {"email": "user@example.test", "password": "synthetic-pass-123"}, "authenticate"),
    ("post", "/api/auth/signup", {"email": "user@example.test", "password": "synthetic-pass-123", "consent": True}, "signup"),
    ("patch", "/api/admin/users/2", {"is_active": False}, "admin_set_active"),
])
def test_unknown_body_field_is_422_before_touching_the_database(method, path, body, handler, monkeypatch):
    """로그인 · 가입 · 계정 상태 본문에 모르는 칸(예: role)이 있으면 공통 422이고 인증 처리(DB)를 부르지 않는다."""
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setattr(auth, handler, lambda *args: pytest.fail(f"{handler} must not run with an unknown field"))
    app.dependency_overrides[auth.current_user_id] = lambda: 1  # 관리자 경로가 본문 검사까지 가게 한다
    try:
        response = TestClient(app).request(method, path, headers={"origin": "http://testserver"}, json={**body, "role": "admin"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "synthetic-pass-123" not in response.text


def test_client_ip_trusts_only_the_last_forwarded_entry_on_cloud_run(monkeypatch):
    from starlette.requests import Request

    def request(*forwarded: str) -> Request:
        return Request({"type": "http", "headers": [(b"x-forwarded-for", value.encode()) for value in forwarded], "client": ("169.254.1.1", 4321)})

    monkeypatch.delenv("K_SERVICE", raising=False)
    # 로컬·Compose: 클라이언트가 보낸 X-Forwarded-For는 무시하고 소켓 주소를 쓴다
    assert auth.client_ip(request("203.0.113.9")) == "169.254.1.1"
    monkeypatch.setenv("K_SERVICE", "sojafit-api")
    # Cloud Run: 앞의 값(클라이언트가 위조 가능)은 버리고 Google 프런트엔드가 덧붙인 마지막 값만 쓴다
    assert auth.client_ip(request("192.0.2.1, 198.51.100.2, 203.0.113.9")) == "203.0.113.9"
    assert auth.client_ip(request("192.0.2.1", "203.0.113.9")) == "203.0.113.9"
    assert auth.client_ip(request()) == "169.254.1.1"


def test_ip_limit_tables_are_not_public():
    import os

    import psycopg

    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity, EXISTS (SELECT 1 FROM aclexplode(coalesce(relacl, acldefault('r', relowner))) a WHERE a.grantee = 0) "
            "FROM pg_class WHERE relname IN ('auth_signup_attempts', 'auth_login_ip_attempts') ORDER BY relname"
        ).fetchall()
    assert rows == [("auth_login_ip_attempts", True, False), ("auth_signup_attempts", True, False)]


def test_database_signup_creates_user_session_and_rejects_duplicate(monkeypatch):
    import os
    import secrets

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("K_SERVICE", "sojafit-api")
    headers = {"origin": "http://testserver", "x-forwarded-for": f"2001:db8::{secrets.token_hex(2)}:{secrets.token_hex(2)}"}
    email, password = f"signup-{secrets.token_hex(6)}@example.test", "synthetic-pass-123"
    client = TestClient(app)
    try:
        response = client.post("/api/auth/signup", headers=headers, json={"email": email, "password": password, "consent": True})
        assert response.status_code == 200
        user_id = response.json()["user_id"]
        assert "httponly" in response.headers["set-cookie"].lower()
        assert client.get("/api/auth/me").json() == {"user_id": user_id, "role": "user", "email": email}
        assert TestClient(app).post("/api/auth/login", headers=headers, json={"email": email, "password": password}).json() == {"user_id": user_id}
        duplicate = TestClient(app).post("/api/auth/signup", headers=headers, json={"email": f"  {email.upper()} ", "password": "another-pass-456", "consent": True})
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "CONFLICT"
        with psycopg.connect(database_url) as conn:
            assert conn.execute("SELECT role, is_active FROM users WHERE login_id=%s", (email,)).fetchall() == [("user", True)]
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE login_id=%s", (email,))


def test_database_signup_limits_each_client_ip_to_three_per_day(monkeypatch):
    import os
    import secrets

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("K_SERVICE", "sojafit-api")
    ip_a, ip_b = (f"2001:db8::{secrets.token_hex(2)}:{secrets.token_hex(2)}" for _ in range(2))
    suffix = secrets.token_hex(6)
    emails = [f"limit-{n}-{suffix}@example.test" for n in range(4)] + [f"other-ip-{suffix}@example.test"]

    def signup(email: str, ip: str, spoofed: str):
        # [왜] 클라이언트가 앞에 넣은 값(spoofed)이 매번 달라도 마지막 값(Google 프런트엔드가 덧붙인 IP)으로 센다
        headers = {"origin": "http://testserver", "x-forwarded-for": f"{spoofed}, {ip}"}
        return TestClient(app).post("/api/auth/signup", headers=headers, json={"email": email, "password": "synthetic-pass-123", "consent": True}).status_code

    try:
        assert signup(emails[0], ip_a, "192.0.2.1") == 200
        assert signup(emails[1], ip_a, "192.0.2.2") == 200
        assert signup(emails[0], ip_a, "192.0.2.3") == 409  # 중복 이메일도 1회로 센다
        assert signup(emails[3], ip_a, "192.0.2.4") == 429
        assert signup(emails[4], ip_b, "192.0.2.1") == 200
        with psycopg.connect(database_url) as conn:
            created = {row[0] for row in conn.execute("SELECT login_id FROM users WHERE login_id = ANY(%s)", (emails,))}
        assert created == {emails[0], emails[1], emails[4]}
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE login_id = ANY(%s)", (emails,))
            conn.execute("DELETE FROM auth_signup_attempts WHERE ip_hash = ANY(%s)", ([auth.session_token_hash(ip) for ip in (ip_a, ip_b)],))


def test_database_login_ip_limit_blocks_after_thirty_failures_and_window_expires(monkeypatch):
    import hashlib
    import os
    import secrets

    import psycopg

    database_url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not database_url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    monkeypatch.setenv("K_SERVICE", "sojafit-api")
    ip_a, ip_b = (f"2001:db8::{secrets.token_hex(2)}:{secrets.token_hex(2)}" for _ in range(2))
    suffix = secrets.token_hex(6)
    email, password = f"ip-limit-{suffix}@example.test", "not-a-real-password-123"
    sprayed = [f"spray-{n}-{suffix}@example.test" for n in range(31)]
    ip_hash = auth.session_token_hash(ip_a)
    with psycopg.connect(database_url) as conn:
        conn.execute("INSERT INTO users (login_id, password_hash) VALUES (%s, %s)", (email, auth.hash_password(password)))

    def login(ip: str, login_email: str, secret: str) -> int:
        # [왜] 앞 값은 클라이언트가 넣은 가짜, 마지막 값이 Cloud Run이 덧붙인 IP다
        headers = {"origin": "http://testserver", "x-forwarded-for": f"192.0.2.1, {ip}"}
        return TestClient(app).post("/api/auth/login", headers=headers, json={"email": login_email, "password": secret}).status_code

    def ip_state():
        with psycopg.connect(database_url) as conn:
            return conn.execute("SELECT failed_count, locked_until IS NOT NULL FROM auth_login_ip_attempts WHERE ip_hash=%s", (ip_hash,)).fetchone()

    try:
        # [왜] 30번 모두 다른 이메일로 틀려 계정당 5회 잠금은 걸리지 않고 IP 한도만 닿게 한다(여러 계정 대입)
        for target in sprayed[:30]:
            assert login(ip_a, target, "wrong-password") == 401
        assert ip_state() == (30, True)
        assert login(ip_a, email, password) == 401  # 31번째는 비밀번호가 맞아도 거절(같은 401)
        assert login(ip_b, email, password) == 200  # 다른 IP는 막지 않는다
        assert login(ip_a, email, password) == 401  # 다른 IP의 성공이 A의 잠금·횟수를 되돌리지 않는다
        assert ip_state() == (30, True)
        with psycopg.connect(database_url) as conn:
            # 15분 창과 잠금이 끝난 것처럼 시각을 되돌린다
            conn.execute("UPDATE auth_login_ip_attempts SET window_started_at = CURRENT_TIMESTAMP - INTERVAL '16 minutes', locked_until = CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE ip_hash=%s", (ip_hash,))
        assert login(ip_a, sprayed[30], "wrong-password") == 401
        assert ip_state() == (1, False)  # 창이 끝난 실패는 다음 실패부터 1로 다시 센다
        assert login(ip_a, email, password) == 200
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute("DELETE FROM users WHERE login_id=%s", (email,))
            conn.execute("DELETE FROM auth_login_attempts WHERE login_hash = ANY(%s)", ([hashlib.sha256(e.encode()).hexdigest() for e in sprayed + [email]],))
            conn.execute("DELETE FROM auth_login_ip_attempts WHERE ip_hash = ANY(%s)", ([auth.session_token_hash(ip) for ip in (ip_a, ip_b)],))
