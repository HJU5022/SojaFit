from fastapi.testclient import TestClient

from backend import auth
from backend.api.quotes import service
from backend.main import app
from backend.services.quote import InvalidApproval, QuoteNotFound


class FakeQuotes:
    def __init__(self): self.calls = []
    def approve(self, user, message, part): self.calls.append(('approve', user, message, part)); return {'id': 3, 'message_id': message, 'candidate_part': part, 'verdict': 'ROLE_SUFFICIENT', 'case_id': 4}
    def create_quote(self, user, approval, quantity): self.calls.append(('quote', user, approval, quantity)); return {'id': 5, 'approval_id': approval, 'part_number': 'SS34', 'quantity': quantity}
    def list_quotes(self, user, project): return []
    def list_cases(self, user): return [{'id': 4, 'approval_id': 3, 'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]
    def delete_case(self, user, case): self.calls.append(('delete', user, case))


def client(fake):
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    app.dependency_overrides[service] = lambda: fake
    return TestClient(app, raise_server_exceptions=False)


def teardown_function(): app.dependency_overrides.clear()


def test_approval_and_quote_accept_only_minimal_inputs(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    fake = FakeQuotes()
    with client(fake) as web:
        approved = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34'}, headers={'origin': 'http://testserver'})
        quote = web.post('/api/approvals/3/quotes', json={'quantity': 10}, headers={'origin': 'http://testserver'})
        forbidden = web.post('/api/approvals/3/quotes', json={'quantity': 10, 'price': '1.00'}, headers={'origin': 'http://testserver'})
    assert approved.status_code == quote.status_code == 201
    assert forbidden.status_code == 422
    assert fake.calls == [('approve', 7, 9, 'SS34'), ('quote', 7, 3, 10)]


def test_mutations_require_origin_and_case_delete_is_explicit(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    fake = FakeQuotes()
    with client(fake) as web:
        assert web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34'}).status_code == 403
        assert web.delete('/api/approved-cases/4', headers={'origin': 'http://testserver'}).status_code == 204
    assert fake.calls == [('delete', 7, 4)]


def test_foreign_and_invalid_resources_use_safe_errors(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    for error, status in [(QuoteNotFound(), 404), (InvalidApproval('no'), 409)]:
        class Broken(FakeQuotes):
            def approve(self, *args): raise error
        app.dependency_overrides.clear()
        app.dependency_overrides[auth.current_user_id] = lambda: 7
        monkeypatch.setattr('backend.api.quotes.QuoteService', Broken)
        with TestClient(app, raise_server_exceptions=False) as web:
            response = web.post('/api/messages/9/approvals', json={'candidate_part': 'SS34'}, headers={'origin': 'http://testserver'})
        assert response.status_code == status
        assert response.json()['error']['request_id'] == response.headers['X-Request-ID']
