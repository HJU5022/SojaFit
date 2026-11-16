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
    def list_quotes(self, user, project): return [{'id': 5, 'approval_id': 3, 'part_number': 'SS34', 'quantity': 10, 'created_at': CREATED, 'thread_id': '0b1c2d3e-0000-4000-8000-000000000001'}]
    def list_cases(self, user): return [{'id': 4, 'approval_id': 3, 'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT', 'created_at': CREATED}]
    def delete_case(self, user, case): self.calls.append(('delete', user, case))
    def list_approvals(self, user, message):
        self.calls.append(('approvals', user, message))
        return [{'id': 3, 'message_id': message, 'candidate_part': 'SS34', 'part_number': 'SS34', 'verdict': 'ROLE_SUFFICIENT',
                 'case_id': None, 'created_at': CREATED, 'snapshot': {'answer': 'PRIVATE_SNAPSHOT'},
                 'quotes': [{'id': 5, 'approval_id': 3, 'part_number': 'SS34', 'quantity': 10, 'created_at': CREATED, 'price': '1.00'}]}]


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
    # [왜] 새로고침 뒤 승인 · 견적 복원용이다: case_id가 null이어도 200이고, 견적에 가격 칸이 새어 나가지 않는다
    assert response.json() == [{'id': 3, 'message_id': 9, 'candidate_part': 'SS34', 'part_number': 'SS34', 'verdict': 'ROLE_SUFFICIENT', 'case_id': None, 'created_at': '2026-11-10T09:00:00Z',
                                'quotes': [{'id': 5, 'approval_id': 3, 'part_number': 'SS34', 'quantity': 10, 'created_at': '2026-11-10T09:00:00Z'}]}]
    assert 'PRIVATE_SNAPSHOT' not in response.text and 'price' not in response.text
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
    # [왜] 같은 메시지에 활성 승인이 있으면 서비스가 InvalidApproval을 내 409다(032 이후 DB의 UNIQUE(message_id)는 없다). 옛 DB의 UniqueViolation도 같은 409로 받는다
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



def test_project_quote_list_names_the_thread_and_has_no_price_fields():
    with client(FakeQuotes()) as web:
        rows = web.get('/api/projects/1/quotes').json()
    assert rows[0]['thread_id'] == '0b1c2d3e-0000-4000-8000-000000000001' and rows[0]['quantity'] == 10
    assert not {'price', 'price_breaks', 'stock', 'availability'} & set(rows[0])


def test_case_detail_is_owner_only_and_shows_only_the_public_allowlist(monkeypatch):
    """승인 사례 상세(#22): 주인만 읽고(남 · 지운 사례는 404), 저장한 판정 · 근거는 화면 결과 허용 목록을 지난 칸만 나간다. DB 시험."""
    import os
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        import pytest
        pytest.skip('requires an isolated service test database (tests/db_schema.py)')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    cite = {'document': 'tsc-ss34.pdf', 'page': 2, 'table': 'Table 1', 'row': 'VRRM'}
    snapshot = {'answer': '역할상 충분합니다.', 'question_type': 'candidate_judge', 'evidence': [{**cite, 'secret': 'HIDDEN-E'}],
                'candidate': {'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT', 'part_number': 'SS34', 'internal': 'HIDDEN-C',
                              'checks': [{'code': 'VRRM', 'op': '>=', 'threshold': 15, 'value': 40, 'unit': 'V', 'result': 'pass',
                                          'citation': {**cite, 'internal': 'HIDDEN-K'}}]}}
    thread, run = str(uuid4()), str(uuid4())
    with psycopg.connect(url) as conn:
        owner, other = [conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,'test-only') RETURNING id",
                                     (f'case-{uuid4()}@example.test',)).fetchone()[0] for _ in range(2)]
        project = conn.execute("INSERT INTO projects(user_id,name,source_kind) VALUES (%s,'전원부','upload') RETURNING id", (owner,)).fetchone()[0]
        conn.execute("INSERT INTO circuits(project_id,connections,source_sha256,parser_version) VALUES (%s,%s,%s,'test')",
                     (project, Jsonb({'parts': [{'ref': 'D1', 'value': 'SS34'}], 'nets': []}), '0' * 64))
        conn.execute('INSERT INTO threads(id,project_id) VALUES (%s,%s)', (thread, project))
        agent = conn.execute("SELECT to_regclass('sojafit_agent.threads')").fetchone()[0] is not None
        if agent:
            conn.execute("INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES (%s,%s,'D1')", (thread, owner))
        conn.execute("INSERT INTO runs(id,thread_id,status) VALUES (%s,%s,'completed')", (run, thread))
        conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'user','D1을 SS34로 바꿔도 되나요?')", (thread, run))
        message = conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'assistant','ok') RETURNING id", (thread, run)).fetchone()[0]
        approval = conn.execute("INSERT INTO approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) VALUES (%s,%s,%s,'SS34','ROLE_SUFFICIENT','SS34') RETURNING id",
                                (owner, message, Jsonb(snapshot))).fetchone()[0]
        conn.execute("INSERT INTO quotes(user_id,approval_id,part_number,quantity) VALUES (%s,%s,'SS34',10)", (owner, approval))
        case = conn.execute('INSERT INTO approved_cases(user_id,approval_id) VALUES (%s,%s) RETURNING id', (owner, approval)).fetchone()[0]
    try:
        app.dependency_overrides[auth.current_user_id] = lambda: owner
        with TestClient(app) as web:
            mine = web.get(f'/api/approved-cases/{case}')
            assert mine.status_code == 200, mine.text
            body = mine.json()
            assert (body['project_id'], body['project_name'], body['thread_id'], body['message_id']) == (project, '전원부', thread, message)
            assert body['question'] == body['thread_title'] == 'D1을 SS34로 바꿔도 되나요?'
            assert (body['target_ref'], body['target_value']) == (('D1', 'SS34') if agent else (None, None))
            assert body['circuit_version'] == 1  # 회로를 올린 뒤 만든 대화는 그 버전을 읽는다(보고서 #44)
            assert body['candidate']['verdict'] == 'ROLE_SUFFICIENT' and body['candidate']['checks'][0]['result'] == 'pass'
            assert body['candidate']['checks'][0]['citation']['row'] == 'VRRM' and body['evidence'][0]['document'] == 'tsc-ss34.pdf'
            assert [q['quantity'] for q in body['quotes']] == [10] and mine.headers['cache-control'] == 'no-store'
            assert 'HIDDEN' not in mine.text and 'part_number' not in body['candidate']  # 허용 목록 밖 칸은 나가지 않는다
            app.dependency_overrides[auth.current_user_id] = lambda: other
            assert web.get(f'/api/approved-cases/{case}').status_code == 404  # 남의 사례
            app.dependency_overrides[auth.current_user_id] = lambda: owner
            assert web.delete(f'/api/approved-cases/{case}', headers={'origin': 'http://testserver'}).status_code == 204
            assert web.get(f'/api/approved-cases/{case}').status_code == 404  # 지운 사례
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DELETE FROM users WHERE id = ANY(%s)', ([owner, other],))
