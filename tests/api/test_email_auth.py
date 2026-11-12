"""메일 인증 가입·재설정: 가짜 SMTP와 격리 PostgreSQL만 사용한다."""
import os
from urllib.parse import parse_qs, urlsplit

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app

ORIGIN = {'origin': 'http://testserver'}
PASSWORD = 'safe-word-12'


@pytest.mark.parametrize('path', ['/api/auth/signup', '/api/auth/password-reset'])
def test_email_requests_fail_closed_without_smtp(path, monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    monkeypatch.delenv('SMTP_PASSWORD', raising=False)
    monkeypatch.setattr(auth, 'connection', lambda: pytest.fail('no DB without mail config'))
    response = TestClient(app).post(path, json={'email': 'new@example.test'}, headers=ORIGIN)
    assert response.status_code == 503
    assert 'set-cookie' not in response.headers


@pytest.fixture
def email_db(monkeypatch):
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires isolated email_security_test DB')
    info = psycopg.conninfo.conninfo_to_dict(url)
    assert info.get('host') == '127.0.0.1' and info.get('dbname') in ('email_security_test', 'ci_auth')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    monkeypatch.setenv('AUTH_SECRET', 'test-only-email-secret-at-least-32-bytes')
    monkeypatch.setenv('DEMO_MODE', '1')
    monkeypatch.setenv('SMTP_USERNAME', 'sender@example.test')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-only-smtp-password')
    from backend.services import mail
    deliveries = []
    monkeypatch.setattr(mail, 'send_link', lambda email, purpose, token: deliveries.append((email, purpose, token)))
    with psycopg.connect(url) as conn:
        from pathlib import Path
        for migration in ['027_google_user_login.sql', '029_email_account_security.sql']:
            conn.execute(Path('db', migration).read_text(encoding='utf-8'))
        conn.execute('TRUNCATE users,auth_email_challenges,auth_email_send_limits,auth_signup_attempts,auth_login_attempts,auth_login_ip_attempts RESTART IDENTITY CASCADE')
    return TestClient(app), url, deliveries


def count(url, table):
    from psycopg import sql
    with psycopg.connect(url) as conn:
        return conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]


def test_cutover_preserves_legacy_and_blocks_old_revision_signup(email_db):
    from pathlib import Path
    client, url, sent = email_db
    legacy = seed_user(url)
    migration = Path('db/manual/email_signup_cutover.sql').read_text(encoding='utf-8')
    try:
        with psycopg.connect(url) as conn:
            conn.execute(migration)
        with psycopg.connect(url) as conn:
            definition = conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='users_email_signup_cutover'").fetchone()[0]
            conn.execute(migration)
            assert conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='users_email_signup_cutover'").fetchone()[0] == definition
            assert conn.execute('SELECT email_verified_at FROM users WHERE id=%s', (legacy,)).fetchone() == (None,)
        with pytest.raises(psycopg.errors.CheckViolation):
            seed_user(url, 'old-revision@example.test')
        assert client.post('/api/auth/login', json={'email': 'old@example.test', 'password': 'legacy-8'}, headers=ORIGIN).status_code == 200
        assert client.post('/api/auth/signup', json={'email': 'verified@example.test'}, headers=ORIGIN).status_code == 200
        assert client.post('/api/auth/signup/confirm', json={'token': sent[-1][2], 'password': PASSWORD}, headers=ORIGIN).status_code == 200
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_signup_cutover')


def seed_user(url, email='old@example.test', password='legacy-8', active=True):
    with psycopg.connect(url) as conn:
        return conn.execute("INSERT INTO users(login_id,password_hash,role,is_active) VALUES(%s,%s,'user',%s) RETURNING id",
                            (email, auth.hash_password(password) if password else None, active)).fetchone()[0]


def test_legacy_google_marker_does_not_receive_password_reset(email_db):
    client, url, sent = email_db
    with psycopg.connect(url) as conn:
        conn.execute("INSERT INTO users(login_id,password_hash) VALUES('google-marker@example.test','google-login-only')")
    assert client.post('/api/auth/password-reset', json={'email': 'google-marker@example.test'}, headers=ORIGIN).status_code == 200
    assert not sent and count(url, 'auth_email_challenges') == 0


def test_signup_requires_email_proof_and_only_stores_token_hash(email_db):
    client, url, sent = email_db
    response = client.post('/api/auth/signup', json={'email': ' New@Example.Test '}, headers=ORIGIN)
    assert response.status_code == 200 and response.json() == {'ok': True}
    assert count(url, 'users') == count(url, 'auth_sessions') == 0
    token = sent[0][2]
    with psycopg.connect(url) as conn:
        stored = conn.execute('SELECT token_hash FROM auth_email_challenges').fetchone()[0]
    assert stored == auth.session_token_hash(token) and token not in response.text
    completed = client.post('/api/auth/signup/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN)
    assert completed.status_code == 200 and 'set-cookie' not in completed.headers
    with psycopg.connect(url) as conn:
        role, verified = conn.execute('SELECT role,email_verified_at IS NOT NULL FROM users').fetchone()
    assert (role, verified) == ('user', True) and count(url, 'auth_sessions') == 0
    assert client.post('/api/auth/signup/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN).status_code == 400
    assert client.post('/api/auth/login', json={'email': 'new@example.test', 'password': PASSWORD}, headers=ORIGIN).status_code == 200


def test_reset_revokes_only_owners_sessions_and_old_password(email_db):
    client, url, sent = email_db
    seed_user(url)
    seed_user(url, 'other@example.test')
    other = TestClient(app)
    assert client.post('/api/auth/login', json={'email': 'old@example.test', 'password': 'legacy-8'}, headers=ORIGIN).status_code == 200
    assert other.post('/api/auth/login', json={'email': 'other@example.test', 'password': 'legacy-8'}, headers=ORIGIN).status_code == 200
    for _ in range(5):
        assert client.post('/api/auth/login', json={'email': 'old@example.test', 'password': 'wrong'}, headers=ORIGIN).status_code == 401
    assert client.post('/api/auth/password-reset', json={'email': 'old@example.test'}, headers=ORIGIN).status_code == 200
    token = sent[-1][2]
    assert client.post('/api/auth/signup/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN).status_code == 400
    assert client.post('/api/auth/password-reset/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN).status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    assert other.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/login', json={'email': 'old@example.test', 'password': 'legacy-8'}, headers=ORIGIN).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'old@example.test', 'password': PASSWORD}, headers=ORIGIN).status_code == 200
    assert client.post('/api/auth/password-reset/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN).status_code == 400


def test_nonexistent_inactive_and_google_only_accounts_have_same_response(email_db):
    client, url, sent = email_db
    seed_user(url, 'inactive@example.test', active=False)
    seed_user(url, 'google@example.test', password=None)
    for email in ['missing@example.test', 'inactive@example.test', 'google@example.test']:
        response = client.post('/api/auth/password-reset', json={'email': email}, headers=ORIGIN)
        assert response.status_code == 200 and response.json() == {'ok': True}
    assert not sent and count(url, 'users') == 2


def test_expired_replaced_and_tampered_tokens_do_not_create_accounts(email_db):
    client, url, sent = email_db
    body = {'email': 'new@example.test'}
    client.post('/api/auth/signup', json=body, headers=ORIGIN)
    first = sent[-1][2]
    client.post('/api/auth/signup', json=body, headers=ORIGIN)
    assert len(sent) == 1
    with psycopg.connect(url) as conn:
        conn.execute("UPDATE auth_email_challenges SET created_at=CURRENT_TIMESTAMP-INTERVAL '61 seconds'")
    client.post('/api/auth/signup', json=body, headers=ORIGIN)
    second = sent[-1][2]
    assert first != second
    for token in [first, 'x' * 43]:
        assert client.post('/api/auth/signup/confirm', json={'token': token, 'password': PASSWORD}, headers=ORIGIN).status_code == 400
    with psycopg.connect(url) as conn:
        conn.execute("UPDATE auth_email_challenges SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second'")
    assert client.post('/api/auth/signup/confirm', json={'token': second, 'password': PASSWORD}, headers=ORIGIN).status_code == 400
    assert count(url, 'users') == 0


def test_email_request_limits_are_shared_across_purposes(email_db):
    client, url, sent = email_db
    for i in range(10):
        assert client.post('/api/auth/signup', json={'email': f'user{i}@example.test'}, headers=ORIGIN).status_code == 200
    assert client.post('/api/auth/password-reset', json={'email': 'missing@example.test'}, headers=ORIGIN).status_code == 429
    assert len(sent) == 10 and count(url, 'users') == 0


def test_service_mail_limit_and_email_cooldown_cannot_be_bypassed(email_db):
    client, url, sent = email_db
    with psycopg.connect(url) as conn:
        conn.execute("INSERT INTO auth_email_send_limits(key_hash,window_start,request_count) VALUES(%s,date_trunc('day',CURRENT_TIMESTAMP),200)",
                     (auth.session_token_hash('mail-service'),))
    for path in ['/api/auth/signup', '/api/auth/password-reset']:
        assert client.post(path, json={'email': 'new@example.test'}, headers=ORIGIN).status_code == 429
    assert not sent


def test_token_consumption_is_atomic_for_concurrent_requests(email_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, url, sent = email_db
    client.post('/api/auth/signup', json={'email': 'new@example.test'}, headers=ORIGIN)
    body = {'token': sent[-1][2], 'password': PASSWORD}
    barrier = Barrier(2)
    def complete():
        barrier.wait(timeout=5)
        return TestClient(app).post('/api/auth/signup/confirm', json=body, headers=ORIGIN).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(complete) for _ in range(2)]
        codes = sorted(f.result(timeout=15) for f in futures)
    assert codes == [200, 400] and count(url, 'users') == 1


def test_completion_rejects_weak_password_and_cross_origin_before_consumption(email_db):
    client, url, sent = email_db
    client.post('/api/auth/signup', json={'email': 'new@example.test'}, headers=ORIGIN)
    token = sent[-1][2]
    for path in ['/api/auth/signup/confirm', '/api/auth/password-reset/confirm']:
        assert client.post(path, json={'token': token, 'password': ' ' * 15}, headers=ORIGIN).status_code == 422
        assert client.post(path, json={'token': token, 'password': PASSWORD}).status_code == 403
    assert count(url, 'auth_email_challenges') == 1 and count(url, 'users') == 0


def test_smtp_errors_never_escape_in_response_or_logs(email_db, monkeypatch, caplog):
    client, url, sent = email_db
    from backend.services import mail
    def broken(*args):
        raise RuntimeError('private-smtp-error-do-not-log')
    monkeypatch.setattr(mail, 'send_link', broken)
    response = client.post('/api/auth/signup', json={'email': 'new@example.test'}, headers=ORIGIN)
    assert response.status_code == 200 and 'private-smtp' not in response.text + caplog.text
    assert count(url, 'users') == 0


def test_additive_migration_preserves_accounts_and_locks_down_token_tables(email_db):
    from pathlib import Path
    client, url, sent = email_db
    seed_user(url)
    with psycopg.connect(url) as conn:
        before = conn.execute('SELECT id,login_id,password_hash,role,is_active,email_verified_at FROM users').fetchall()
        migration = Path('db/029_email_account_security.sql').read_text(encoding='utf-8')
        conn.execute(migration)
        conn.execute(migration)
        assert conn.execute('SELECT id,login_id,password_hash,role,is_active,email_verified_at FROM users').fetchall() == before
        rows = conn.execute("SELECT relname,relrowsecurity,EXISTS(SELECT 1 FROM aclexplode(coalesce(relacl,acldefault('r',relowner))) a WHERE a.grantee=0) FROM pg_class WHERE relname IN ('auth_email_challenges','auth_email_send_limits') ORDER BY relname").fetchall()
        assert rows == [('auth_email_challenges', True, False), ('auth_email_send_limits', True, False)]


def test_gmail_transport_uses_verified_tls_and_fragment(monkeypatch):
    from backend.services import mail
    calls = []
    class SMTP:
        def __init__(self, host, port, **kwargs):
            assert host == 'smtp.gmail.com' and port == 465 and kwargs['timeout'] == 10
            assert kwargs['context'].check_hostname
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def login(self, user, password): calls.append(('login', user))
        def send_message(self, message): calls.append(('message', message))
    monkeypatch.setenv('SMTP_USERNAME', 'sender@example.test')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-only-smtp-password')
    monkeypatch.setenv('AUTH_ORIGIN', 'https://service.example.test')
    monkeypatch.setattr(mail.smtplib, 'SMTP_SSL', SMTP)
    mail.send_link('recipient@example.test', 'signup', 'x' * 43)
    message = calls[-1][1]
    url = next(line for line in message.get_content().splitlines() if line.startswith('https://'))
    parsed = urlsplit(url)
    assert parsed.path == '/verify-email' and not parsed.query
    assert parse_qs(parsed.fragment)['token'] == ['x' * 43]


@pytest.mark.parametrize('email', ['a@example.test,b', 'Name<a@example.test>', 'a@example.test\nBcc:victim@example.test'])
def test_email_requests_reject_ambiguous_recipient_headers(email, monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    monkeypatch.setattr(auth, 'connection', lambda: pytest.fail('validate before DB'))
    response = TestClient(app).post('/api/auth/signup', json={'email': email}, headers=ORIGIN)
    assert response.status_code == 422 and email not in response.text


@pytest.mark.parametrize('path', ['/api/auth/signup/confirm', '/api/auth/password-reset/confirm'])
def test_password_length_boundary_is_twelve_on_both_completion_routes(path, monkeypatch):
    from backend import auth_email
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    calls = []
    monkeypatch.setattr(auth_email, 'complete', lambda *args: calls.append(args))
    client = TestClient(app)
    for password, status in [('safe-word-1', 422), ('safe-word-12', 200)]:
        response = client.post(path, json={'token': 'x' * 43, 'password': password}, headers=ORIGIN)
        assert response.status_code == status
    assert len(calls) == 1 and calls[0][1] == 'safe-word-12'
    auth.validate_new_password('safe-word-12')
