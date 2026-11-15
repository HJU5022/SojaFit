import psycopg
from fastapi.testclient import TestClient

from backend import auth
from backend.api.quotes import service
from backend.main import app
from backend.services.quote import InvalidApproval, QuoteNotFound

CREATED = '2026-11-10T09:00:00+00:00'  # 실제 서비스(backend/services/quote.py)처럼 DB의 created_at을 함께 돌려준다


class FakeQuotes:
    def __init__(self): self.calls = []
    def approve(self, user, message, part, verdict): self.calls.append(('approve', user, message, part, verdict)); return {'id': 3, 'message_id': message, 'candidate_part': part, 'part_number': part, 'verdict': verdict, 'case_id': 4, 'created_at': CREATED}
    def create_quote(self, user, approval, quantity): self.calls.append(('quote', user, approval, quantity)); return {'id': 5, 'approval_id': approval, 'part_number': 'SS34', 'quantity': quantity, 'created_at': CREATED}
    def list_quotes(self, user, project): return []
    def list_cases(self, user): return [{'id': 4, 'approval_id': 3, 'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT', 'created_at': CREATED}]
    def delete_case(self, user, case): self.calls.append(('delete', user, case))
    def list_approvals(self, user, message):
        self.calls.append(('approvals', user, message))
        return [{'id': 3, 'message_id': message, 'candidate_part': 'SS34', 'part_number': 'SS34', 'verdict': 'ROLE_SUFFICIENT',
                 'case_id': None, 'created_at': CREATED, 'snapshot': {'answer': 'PRIVATE_SNAPSHOT'}}]


def client(fake):
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    app.dependency_overrides[service] = lambda: fake
    return TestClient(app, raise_server_exceptions=False)


def teardown_function(): app.dependency_overrides.clear()


def test_persisted_approval_read_is_owned_metadata_without_origin_or_snapshot():
    fake = FakeQuotes()
    with client(fake) as web:
        response = web.get('/api/messages/9/approvals')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == [{'id': 3, 'message_id': 9, 'candidate_part': 'SS34', 'part_number': 'SS34', 'verdict': 'ROLE_SUFFICIENT',
                                'case_id': None, 'created_at': '2026-11-10T09:00:00Z'}]
    assert 'PRIVATE_SNAPSHOT' not in response.text
    assert fake.calls == [('approvals', 7, 9)]


def test_approval_read_requires_login():
    with TestClient(app, raise_server_exceptions=False) as web:
        assert web.get('/api/messages/9/approvals').status_code == 401


def test_approval_read_uses_safe_not_found_error(monkeypatch):
    class Missing(FakeQuotes):
        def list_approvals(self, *args): raise QuoteNotFound
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    monkeypatch.setattr('backend.api.quotes.QuoteService', Missing)
    with TestClient(app, raise_server_exceptions=False) as web:
        response = web.get('/api/messages/9/approvals')
    assert response.status_code == 404 and response.json()['error']['code'] == 'NOT_FOUND'


def test_approval_and_quote_accept_only_minimal_inputs(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    fake = FakeQuotes()
    with client(fake) as web:
        approved = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}, headers={'origin': 'http://testserver'})
        missing_verdict = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34'}, headers={'origin': 'http://testserver'})
        quote = web.post('/api/approvals/3/quotes', json={'quantity': 10}, headers={'origin': 'http://testserver'})
        forbidden = web.post('/api/approvals/3/quotes', json={'quantity': 10, 'price': '1.00'}, headers={'origin': 'http://testserver'})
    assert approved.status_code == quote.status_code == 201
    assert forbidden.status_code == 422
    assert missing_verdict.status_code == 422
    assert fake.calls == [('approve', 7, 9, 'SS34', 'ROLE_SUFFICIENT'), ('quote', 7, 3, 10)]


def test_mutations_require_origin_and_case_delete_is_explicit(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    fake = FakeQuotes()
    with client(fake) as web:
        assert web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}).status_code == 403
        assert web.delete('/api/approved-cases/4', headers={'origin': 'http://testserver'}).status_code == 204
    assert fake.calls == [('delete', 7, 4)]


def test_foreign_and_invalid_resources_use_safe_errors(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    # [왜] 같은 메시지를 두 번 승인하면 DB의 UNIQUE(message_id)가 UniqueViolation을 내고, 승인은 한 건으로 남은 채 409다(db/020)
    # [왜] 409 둘 다 ALREADY_APPROVED라 화면은 승인을 다시 보내지 않는다(ADR 0019)
    for error, status, code in [(QuoteNotFound(), 404, 'NOT_FOUND'), (InvalidApproval('no'), 409, 'ALREADY_APPROVED'),
                                (psycopg.errors.UniqueViolation(), 409, 'ALREADY_APPROVED')]:
        class Broken(FakeQuotes):
            def approve(self, *args): raise error
        app.dependency_overrides.clear()
        app.dependency_overrides[auth.current_user_id] = lambda: 7
        monkeypatch.setattr('backend.api.quotes.QuoteService', Broken)
        with TestClient(app, raise_server_exceptions=False) as web:
            response = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}, headers={'origin': 'http://testserver'})
        assert response.status_code == status and response.json()['error']['code'] == code
        assert response.json()['error']['request_id'] == response.headers['X-Request-ID']


def test_approval_accepts_the_name_the_judgement_showed_but_not_control_characters(monkeypatch):
    """판정 결과가 보여 준 이름('TSC 1N4007G')은 공백이 있어도 받는다(11-10 점검의 422). 제어 문자 · 빈 값은 422다."""
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    fake = FakeQuotes()
    origin = {'origin': 'http://testserver'}
    with client(fake) as web:
        shown = web.post('/api/messages/9/approvals', json={'candidate_part': 'TSC 1N4007G', 'verdict': 'ROLE_SUFFICIENT'}, headers=origin)
        control = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34\n', 'verdict': 'ROLE_SUFFICIENT'}, headers=origin)
        blank = web.post('/api/messages/9/approvals', json={'candidate_part': '   ', 'verdict': 'ROLE_SUFFICIENT'}, headers=origin)
    assert shown.status_code == 201 and control.status_code == blank.status_code == 422
    assert fake.calls == [('approve', 7, 9, 'TSC 1N4007G', 'ROLE_SUFFICIENT')]

