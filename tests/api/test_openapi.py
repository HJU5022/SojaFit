"""HTTP API 계약(`/openapi.json` · `/docs`) 시험. DB · 바깥 호출 없음.

- 역할: 요청 본문 모델마다 예시가 있고 그 예시가 실제로 통과하는지, 모르는 칸 금지, 업로드의 multipart 칸 문서,
  SSE 두 경로의 `text/event-stream` 설명, 204 · SSE가 아닌 성공 응답의 스키마가 비지 않았는지,
  응답 모델(`response_model`)이 화면이 읽는 칸(frontend/src/api/*.ts의 타입)을 지우지 않는지 본다.
  동작 40개(메서드, 경로)를 고정하고, 모두 `backend/api/` 라우터에 태그와 함께 있는지(`backend/main.py`에 경로 함수가 없는지) 본다.
- 하지 않는 일: 오류 응답 모양(test_health.py · test_errors.py), 가격 응답의 실제 칸(test_prices.py),
  업로드 수신 상한 · 오류 코드(test_projects.py), Swagger 화면 자체(서버를 띄우지 않는다).
- 출처: SPEC.md 4절 엔드포인트 표, backend/api/API.md.
"""
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from backend import auth
from backend.api import admin, conversations, profile, projects, quotes
from backend.api import auth as auth_api  # [주의] 위 auth는 세션 로직(backend/auth.py), 이것은 로그인 경로 라우터다
from backend.conversations.profile import ProfileMemory
from backend.main import app

ORIGIN = {'origin': 'http://testserver'}
# 요청 본문 모델 전부. 새 본문 모델을 만들면 여기에 넣어야 아래 시험이 예시 · 모르는 칸 금지를 본다
BODY_MODELS = [auth_api.Login, auth_api.Signup, auth_api.DemoLogin, admin.AccountState, projects.CreateProject, projects.RenameProject,
               quotes.ApproveBody, quotes.QuoteBody, conversations.StartRun, conversations.ResumeRun, profile.ProfileUpdate]


def openapi():
    return TestClient(app).get('/openapi.json').json()


def test_every_json_body_model_has_a_valid_example_and_forbids_unknown_fields():
    paths = openapi()['paths']
    refs = {op['requestBody']['content']['application/json']['schema']['$ref'].rsplit('/', 1)[-1]
            for item in paths.values() for op in item.values() if 'application/json' in op.get('requestBody', {}).get('content', {})}
    assert refs == {model.__name__ for model in BODY_MODELS}  # 목록에서 빠진 본문 모델이 없다
    for model in BODY_MODELS:
        schema = model.model_json_schema()
        assert schema['additionalProperties'] is False, model.__name__
        (example,) = schema['examples']
        model.model_validate(example)  # [왜] /docs의 "Try it out"이 그대로 보내도 422가 나지 않는다
        assert '@' not in str(example) or 'example.com' in str(example)  # 실제 이메일을 적지 않는다


def test_upload_documents_file_and_name_fields():
    body = openapi()['paths']['/api/projects/upload']['post']['requestBody']
    schema = body['content']['multipart/form-data']['schema']
    assert body['required'] is True and schema['required'] == ['file', 'name']
    assert schema['properties']['file']['contentMediaType'] == 'application/octet-stream'


def test_sse_routes_document_event_stream_and_every_event_name():
    paths = openapi()['paths']
    for path in ('/api/threads/{thread_id}/runs', '/api/runs/{run_id}/resume'):
        ok = paths[path]['post']['responses']['200']
        assert list(ok['content']) == ['text/event-stream']
        for event in ('run_started', 'status', 'requires_input', 'completed', 'refused', 'failed'):
            assert f'`{event}`' in ok['description'], (path, event)


def test_no_success_response_has_an_empty_schema():
    empty = []
    for path, item in openapi()['paths'].items():
        for method, op in item.items():
            for status, response in op['responses'].items():
                content = response.get('content', {})
                if not status.startswith('2') or status == '204' or 'text/event-stream' in content:
                    continue
                if not content.get('application/json', {}).get('schema'):
                    empty.append(f'{method.upper()} {path} {status}')
    assert empty == []


# (메서드, 경로) 40개. `/docs`에 싣지 않는 Google 관리자 로그인 4개도 센다. 경로를 더하거나 빼면 SPEC 4절 표와 함께 고친다
ROUTES = {
    ('POST', '/api/runs/{run_id}/recover'),
    ('GET', '/health'),
    ('POST', '/api/auth/login'), ('POST', '/api/auth/signup'), ('GET', '/api/auth/demo'), ('POST', '/api/auth/demo-login'),
    ('GET', '/api/auth/me'), ('POST', '/api/auth/logout'), ('GET', '/api/auth/google/status'), ('GET', '/api/auth/google/start'),
    ('GET', '/api/auth/google/callback'), ('GET', '/api/auth/google/pending'),
    ('GET', '/api/admin/users'), ('PATCH', '/api/admin/users/{target_id}'),
    ('GET', '/api/prices'),
    ('DELETE', '/api/me'), ('GET', '/api/me/memory'), ('PATCH', '/api/me/memory'), ('DELETE', '/api/me/memory'),
    ('GET', '/api/demo-circuits'), ('GET', '/api/projects'), ('POST', '/api/projects'), ('POST', '/api/projects/upload'),
    ('GET', '/api/projects/{project_id}'), ('PATCH', '/api/projects/{project_id}'), ('DELETE', '/api/projects/{project_id}'),
    ('POST', '/api/messages/{message_id}/approvals'), ('POST', '/api/approvals/{approval_id}/quotes'),
    ('GET', '/api/projects/{project_id}/quotes'), ('GET', '/api/approved-cases'), ('DELETE', '/api/approved-cases/{case_id}'),
    ('GET', '/api/judge/roles'), ('GET', '/api/demo-questions'), ('GET', '/api/projects/{project_id}/threads'),
    ('POST', '/api/projects/{project_id}/threads'), ('GET', '/api/runs/{run_id}'), ('POST', '/api/threads/{thread_id}/runs'),
    ('POST', '/api/runs/{run_id}/resume'), ('GET', '/api/threads/{thread_id}'), ('DELETE', '/api/threads/{thread_id}'),
}


def test_routes_are_pinned_and_live_only_in_api_routers():
    """동작(메서드, 경로) 40개가 그대로 있고, 모두 backend/api/ 라우터에 태그와 함께 있다(main.py는 경로 함수 없이 앱을 조립만 한다)."""
    # [왜] main.py에 @app.get 같은 경로를 두면 app.routes에 APIRoute로 바로 들어온다
    assert [r.path for r in app.routes if isinstance(r, APIRoute)] == []
    # [주의] FastAPI 0.162는 include_router한 라우터를 `original_router`를 가진 묶음 하나로 app.routes에 둔다
    routes = [r for group in app.routes if hasattr(group, 'original_router') for r in group.original_router.routes]
    assert sorted((method, r.path) for r in routes for method in r.methods) == sorted(ROUTES)
    # 라우터마다 태그가 있어야 /docs가 묶음(auth · admin · prices · health …)으로 보이고 이름 없는 default 묶음이 생기지 않는다
    assert all(r.tags and r.endpoint.__module__.startswith('backend.api.') for r in routes)


class Conn:
    """execute()마다 미리 넣은 결과를 차례로 돌려주는 가짜 연결(fetchone · fetchall · 반복)."""

    def __init__(self, *results): self.results = list(results)
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def execute(self, *args): self.result = self.results.pop(0); return self
    def fetchone(self): return self.result
    def fetchall(self): return self.result
    def __iter__(self): return iter(self.result)


NOW = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
THREAD, RUN = str(uuid4()), str(uuid4())
JUDGED = {'answer': '대체할 수 있습니다.', 'question_type': 'candidate_judge',
          'judgement': {'kind': 'judge', 'results': [{'part': '1N5819', 'verdict': 'SPEC_EQUIVALENT'}]}}
SNAPSHOT = {'candidate': {'part': '1N5819', 'verdict': 'SPEC_EQUIVALENT'}}
# 화면이 읽는 칸(frontend/src/api/*.ts의 타입). 응답 모델이 칸을 지우면 아래 시험이 깨진다
USER_ID, ENABLED, OK = {'user_id'}, {'enabled'}, {'ok'}
ACCOUNT = {'id', 'email', 'role', 'is_active'}
APPROVAL = {'id', 'message_id', 'candidate_part', 'verdict', 'case_id', 'created_at'}
QUOTE = {'id', 'approval_id', 'part_number', 'quantity', 'created_at'}
CASE = {'id', 'approval_id', 'candidate_part', 'verdict', 'created_at'}
RESULT = {'answer', 'status', 'stage', 'question_type', 'evidence', 'judgement', 'price_parts', 'refusal', 'interrupt',
          'request_id', 'profile_hints'}
FACT = {'kind', 'value', 'text', 'version', 'updated_at', 'source'}

# (메서드, 경로, 본문, auth를 바꿀 함수 이름 → 값, 가짜 연결이 돌려줄 결과, 화면이 읽는 칸)
CASES = [
    ('get', '/health', None, {}, None, {'status'}),
    ('post', '/api/auth/login', {'email': 'user@example.com', 'password': 'x'}, {'authenticate': lambda *a: ('t', 7)}, None, USER_ID),
    ('post', '/api/auth/signup', {'email': 'user@example.com', 'password': 'example-pass', 'consent': True},
     {'signup': lambda *a: ('t', 7)}, None, USER_ID),
    ('get', '/api/auth/demo', None, {}, None, ENABLED),
    ('post', '/api/auth/demo-login', {'account': 'a'}, {'demo_session': lambda *a: ('t', 7)}, None, USER_ID),
    ('get', '/api/auth/me', None, {'account_email': lambda uid: 'user@example.test'}, None, {'user_id', 'role', 'email'}),
    ('post', '/api/auth/logout', None, {'logout': lambda *a: None}, None, OK),
    ('patch', '/api/admin/users/8', {'is_active': False}, {'admin_set_active': lambda *a: None}, None, OK),
    ('get', '/api/demo-circuits', None, {}, None, {'id', 'name'}),
    ('post', '/api/messages/9/approvals', {'candidate_part': '1N5819', 'verdict': 'SPEC_EQUIVALENT'}, {},
     [('completed', JUDGED), (3, NOW), (4,)], APPROVAL),
    ('post', '/api/approvals/3/quotes', {'quantity': 100}, {}, [(SNAPSHOT,), (5, NOW)], QUOTE),
    ('get', '/api/projects/1/quotes', None, {}, [(1,), [(5, 3, '1N5819', 100, NOW)]], QUOTE),
    ('get', '/api/approved-cases', None, {}, [[(4, 3, SNAPSHOT, NOW)]], CASE),
    ('get', '/api/projects/1/threads', None, {}, [(1,), [(THREAD, NOW, '저장 질문', RUN, 'completed', NOW)]], {'id', 'project_id', 'title', 'created_at', 'last_activity_at', 'latest_run_id', 'status'}),
    ('post', '/api/projects/1/threads', None, {}, [(1,), (THREAD,)], {'id', 'project_id'}),
    ('get', f'/api/runs/{RUN}', None, {}, [(RUN, THREAD, 'completed', JUDGED, 12)], {'id', 'thread_id', 'message_id', 'result'}),
]


@pytest.fixture
def web(monkeypatch):
    """로그인 사용자 7 · 같은 Origin · 데모 모드. 끝나면 의존성 바꿔치기와 분석 서비스를 지운다."""
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    monkeypatch.setenv('DEMO_MODE', '1')
    app.dependency_overrides[auth.current_user] = lambda: (7, 'user')
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    yield TestClient(app)
    app.dependency_overrides.clear()
    if hasattr(app.state, 'conversations'):
        del app.state.conversations


@pytest.mark.parametrize('method, path, body, patches, rows, fields', CASES, ids=[f'{c[0]} {c[1]}' for c in CASES])
def test_response_model_keeps_every_field_the_screen_reads(web, monkeypatch, method, path, body, patches, rows, fields):
    for name, fake in patches.items():
        monkeypatch.setattr(auth, name, fake)
    if rows is not None:  # [왜] 저장소 · 서비스는 진짜를 쓰고 연결만 바꿔, 실제 코드가 만든 dict가 응답 모델을 지나게 한다
        monkeypatch.setattr(auth, 'connection', lambda: Conn(*rows))
    response = web.request(method, path, json=body, headers=ORIGIN)
    assert response.status_code in (200, 201), response.text
    data = response.json()
    item = data[0] if isinstance(data, list) else data
    assert set(item) == fields
    if path.startswith('/api/runs/'):
        assert set(item['result']) == RESULT and item['result']['judgement']['results'][0]['part'] == '1N5819'


def test_admin_users_and_account_deletion_keep_nested_fields(web, monkeypatch):
    monkeypatch.setattr(auth, 'admin_users', lambda actor: [{'id': 1, 'email': 'admin@example.com', 'role': 'admin', 'is_active': True}])
    users = web.get('/api/admin/users').json()
    assert set(users) == {'users'} and set(users['users'][0]) == ACCOUNT and users['users'][0]['email'] != 'admin@example.com'

    @contextmanager
    def account_deletion(user):
        yield {'analysis_threads': 1, 'analysis_circuits': 1, 'checkpoints': 3, 'memory_items': 2}
    app.state.conversations = SimpleNamespace(account_deletion=account_deletion)
    monkeypatch.setattr(auth, 'delete_account', lambda user: {'projects': 1, 'quotes': 0, 'account': 1})
    deleted = web.delete('/api/me', headers=ORIGIN).json()
    assert deleted == {'deleted': {'analysis_threads': 1, 'analysis_circuits': 1, 'checkpoints': 3, 'memory_items': 2,
                                   'projects': 1, 'quotes': 0, 'account': 1}}


def test_profile_facts_keep_every_field_the_screen_reads(web):
    memory = ProfileMemory(InMemoryStore(), indexed=False)  # 진짜 사실 기억(색인 없음)
    app.state.conversations = SimpleNamespace(profile=memory, account_writer=lambda user: nullcontext())
    patched = web.patch('/api/me/memory', json={'mounting_preference': 'smd'}, headers=ORIGIN)
    read = web.get('/api/me/memory')
    assert patched.status_code == read.status_code == 200
    assert patched.json() == read.json() == memory.facts(7) and set(read.json()[0]) == FACT
