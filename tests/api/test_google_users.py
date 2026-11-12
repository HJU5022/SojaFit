"""Google 일반 가입·기존 계정 연결. 실 Google 대신 검증된 합성 신원, DB는 새 로컬 시험 DB만 사용."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from backend import auth
from backend.main import app

ORIGIN = {'origin': 'http://testserver'}
ISSUER = 'https://accounts.google.com'


def configured(monkeypatch):
    monkeypatch.setenv('GOOGLE_AUTH_ENABLED', '1')
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'synthetic-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'synthetic-secret')
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')


def test_passwordless_google_account_cannot_authenticate_with_a_password():
    assert auth.verify_password('anything', None) is False


def test_unlinked_callback_enters_browser_bound_completion(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setattr(auth, 'consume_google_state', lambda *_: ('verifier', 'nonce'))
    monkeypatch.setattr(auth, 'fetch_google_identity', lambda *_: (ISSUER, 'synthetic-sub', 'person@example.test'))
    monkeypatch.setattr(auth, 'google_admin_session', lambda *_: None)
    monkeypatch.setattr(auth, 'google_session', lambda *_: None, raising=False)
    monkeypatch.setattr(auth, 'request_google_link', lambda *_: 'synthetic-pending')
    response = TestClient(app).get('/api/auth/google/callback?state=s&code=c', follow_redirects=False)
    assert response.headers['location'] == '/login?google=finish'
    cookies = response.headers.get_list('set-cookie')
    assert any('sojafit_google_pending=synthetic-pending' in c and 'Path=/api/auth/google;' in c and 'HttpOnly' in c for c in cookies)


@pytest.mark.parametrize('body', [{'consent': 'true'}, {'consent': True, 'role': 'admin'}])
def test_google_signup_rejects_invalid_legacy_fields(monkeypatch, body):
    configured(monkeypatch)
    monkeypatch.setattr(auth, 'complete_google_user', lambda *_a, **_k: pytest.fail('must validate before DB'), raising=False)
    assert TestClient(app).post('/api/auth/google/signup', headers=ORIGIN, json=body).status_code == 422


@pytest.mark.parametrize('path,body', [('signup', {'consent': True}), ('link', {'email': 'person@example.test', 'password': 'pass'})])
def test_google_completion_checks_origin_before_database(monkeypatch, path, body):
    configured(monkeypatch)
    monkeypatch.setattr(auth, 'connection', lambda: pytest.fail('must check origin before DB'))
    assert TestClient(app).post('/api/auth/google/'+path, json=body).status_code == 403


def test_google_link_rechecks_password_and_does_not_issue_session_first(monkeypatch):
    configured(monkeypatch)
    seen = []
    def authenticate(*args, **kwargs):
        seen.append(kwargs)
        return None
    monkeypatch.setattr(auth, 'authenticate', authenticate)
    response = TestClient(app).post('/api/auth/google/link', headers=ORIGIN, json={'email': 'person@example.test', 'password': 'wrong'})
    assert response.status_code == 401
    assert seen == [{'issue_session': False}]


@pytest.fixture
def db(monkeypatch):
    url = os.getenv('TEST_GOOGLE_DATABASE_URL') or os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires new isolated local OAuth test database')
    info = conninfo_to_dict(url)
    assert info.get('host') in ('127.0.0.1', 'localhost') and (info['dbname'].startswith('oauth_test_') or info['dbname'] == 'ci_auth')
    schema = 'google_users_'+uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA {schema}')
    scoped = make_conninfo(url, options=f'-c search_path={schema}')
    monkeypatch.setenv('DATABASE_URL', scoped)
    monkeypatch.setenv('DEMO_MODE', '1')
    monkeypatch.setattr(auth, 'N', 2**10)
    configured(monkeypatch)
    try:
        with psycopg.connect(scoped) as conn:
            for name in ('003_auth.sql', '005_auth_attempt_window.sql', '006_user_roles.sql', '010_google_auth.sql', '021_auth_ip_limits.sql', '027_google_user_login.sql'):
                conn.execute(Path('db', name).read_text(encoding='utf-8'))
            conn.execute('ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ')
        yield scoped
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA {schema} CASCADE')


def existing(db, *, role='user', active=True, email='person@example.test'):
    with psycopg.connect(db) as conn:
        return conn.execute('INSERT INTO users(login_id,password_hash,role,is_active) VALUES (%s,%s,%s,%s) RETURNING id',
                            (email, auth.hash_password('synthetic-password'), role, active)).fetchone()[0]


def pending(email='person@example.test', subject='synthetic-sub'):
    return auth.request_google_link(ISSUER, subject, email)


def test_new_google_user_has_no_password_and_reuses_same_identity(db):
    request = pending()
    token, uid = auth.complete_google_user(request, 'test-ip')
    with psycopg.connect(db) as conn:
        assert conn.execute('SELECT role,password_hash FROM users WHERE id=%s', (uid,)).fetchone() == ('user', None)
        assert conn.execute('SELECT email_verified_at IS NOT NULL FROM users WHERE id=%s', (uid,)).fetchone() == (True,)
    assert auth.google_session(ISSUER, 'synthetic-sub')[1] == uid
    assert auth.google_admin_session(ISSUER, 'synthetic-sub') is None
    assert auth.authenticate('person@example.test', 'anything', 'other-ip') is None
    with pytest.raises(HTTPException):
        auth.complete_google_user(request, 'test-ip')


def test_same_email_never_auto_links_but_password_verified_user_can_link(db):
    uid = existing(db)
    request = pending()
    with pytest.raises(HTTPException) as error:
        auth.complete_google_user(request, 'test-ip')
    assert error.value.status_code == 409
    assert auth.google_session(ISSUER, 'synthetic-sub') is None
    proof = auth.authenticate('person@example.test', 'synthetic-password', 'test-ip', issue_session=False)
    with psycopg.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0] == 0
    assert auth.complete_google_user(request, 'test-ip', user_id=proof[1])[1] == uid
    assert auth.google_session(ISSUER, 'synthetic-sub')[1] == uid


@pytest.mark.parametrize('role,active', [('admin', True), ('user', False)])
def test_admin_or_disabled_account_is_not_self_linked(db, role, active):
    uid = existing(db, role=role, active=active)
    request = pending()
    with pytest.raises(HTTPException):
        auth.complete_google_user(request, 'test-ip', user_id=uid)
    assert auth.google_session(ISSUER, 'synthetic-sub') is None
    if role == 'admin':
        assert auth.approve_google_link(request, uid, 'person@example.test')
        assert auth.google_admin_session(ISSUER, 'synthetic-sub')[1] == uid


def test_expiry_and_existing_binding_never_create_new_session(db):
    uid = existing(db)
    auth.complete_google_user(pending(), 'test-ip', user_id=uid)
    with pytest.raises(HTTPException):
        auth.complete_google_user(pending(subject='other-subject'), 'test-ip', user_id=uid)
    request = pending('another@example.test', 'another-sub')
    with psycopg.connect(db) as conn:
        conn.execute('UPDATE auth_google_pending SET expires_at=now()-interval \'1 second\' WHERE request_id=%s', (request,))
    with pytest.raises(HTTPException):
        auth.complete_google_user(request, 'test-ip')
    with psycopg.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0] == 1


def test_google_and_password_signup_share_ip_limit(db):
    assert auth.signup('password@example.test', 'synthetic-password', 'same-ip')
    for i in range(2):
        auth.complete_google_user(pending(f'person-{i}@example.test', f'sub-{i}'), 'same-ip')
    with pytest.raises(HTTPException) as error:
        auth.complete_google_user(pending('fourth@example.test', 'fourth-sub'), 'same-ip')
    assert error.value.status_code == 429


def test_http_signup_masks_identity_and_sets_existing_session_cookie(db):
    client = TestClient(app)
    client.cookies.set('sojafit_google_pending', pending())
    data = client.get('/api/auth/google/onboarding')
    assert data.status_code == 200 and data.json() == {'email': 'p***@example.test'}
    response = client.post('/api/auth/google/signup', headers=ORIGIN, json={'consent': True})
    assert response.status_code == 200 and auth.COOKIE in client.cookies
    assert client.get('/api/auth/me').json()['role'] == 'user'
    assert client.post('/api/auth/google/signup', headers=ORIGIN, json={'consent': True}).status_code == 400


def test_http_link_requires_password_and_keeps_existing_account(db):
    uid = existing(db)
    client = TestClient(app)
    request = pending('different-google@example.test')
    client.cookies.set('sojafit_google_pending', request)
    body = {'email': 'person@example.test', 'password': 'wrong'}
    assert client.post('/api/auth/google/link', headers=ORIGIN, json=body).status_code == 401
    with psycopg.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0] == 0
    body['password'] = 'synthetic-password'
    response = client.post('/api/auth/google/link', headers=ORIGIN, json=body)
    assert response.status_code == 200 and response.json() == {'user_id': uid}
    assert client.get('/api/auth/me').json()['user_id'] == uid
    assert auth.google_session(ISSUER, 'synthetic-sub')[1] == uid


def test_concurrent_signup_cannot_bind_same_google_identity_twice(db):
    from concurrent.futures import ThreadPoolExecutor
    requests = [pending(), pending()]
    def signup(request):
        try:
            return auth.complete_google_user(request, 'test-ip')[1]
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(signup, requests))
    with psycopg.connect(db) as conn:
        uid = conn.execute('SELECT id FROM users').fetchone()[0]
        assert sorted(results) == sorted([uid, 409])
        assert conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM auth_google_identities').fetchone()[0] == 1


def test_migration_preserves_passwords_is_repeatable_and_requires_admin_password(db):
    uid = existing(db)
    with psycopg.connect(db) as conn:
        before = conn.execute('SELECT password_hash FROM users WHERE id=%s', (uid,)).fetchone()[0]
        conn.execute(Path('db/027_google_user_login.sql').read_text(encoding='utf-8'))
        assert conn.execute('SELECT password_hash FROM users WHERE id=%s', (uid,)).fetchone()[0] == before
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(db) as conn:
        conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES ('admin-null@example.test',NULL,'admin')")


def test_disabled_google_user_cannot_get_session(db):
    uid = existing(db)
    auth.complete_google_user(pending(), 'test-ip', user_id=uid)
    with psycopg.connect(db) as conn:
        conn.execute('UPDATE users SET is_active=FALSE WHERE id=%s', (uid,))
    assert auth.google_session(ISSUER, 'synthetic-sub') is None
