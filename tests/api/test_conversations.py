from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import auth
from backend.main import app

ORIGIN = {'origin': 'http://testserver'}


class FakeAnalysis:
    """DB 없는 사용자 분석 서비스. 실제 서비스처럼 thread마다 대상 부품을 처음 값으로 고정한다."""
    def __init__(self, state=None, interrupt=None, error=None):
        self.calls, self.targets, self.version = [], {}, 1
        self.state, self.interrupt, self.error = state or {'answer': 'ok'}, interrupt, error
        self.graph = SimpleNamespace(get_state=lambda config: SimpleNamespace(values=self.state))
    def config(self, thread): return {'configurable': {'thread_id': thread}}
    def ensure_thread(self, user, thread, filename, connections, target):
        self.calls.append(('ensure', thread, filename, target))
        if self.targets.setdefault(thread, target) != target:
            raise HTTPException(409, '대상 부품을 바꾸려면 새 대화를 시작하세요.')
    def _run(self, *call):
        self.calls.append(call)
        if self.error:
            raise self.error
        return {'interrupt': self.interrupt, 'version': self.version}
    def message(self, user, thread, text, conditions='', request_id=''): return self._run('message', thread, text, conditions)
    def resume(self, user, thread, answers, role, version, request_id=''): return self._run('resume', thread, answers, role, version)
    def detail(self, user, thread): return {'version': self.version}


class FakeRepo:
    def __init__(self, thread, run, status='running', result=None):
        self.thread, self.run, self.status, self.result, self.calls = thread, run, status, result or {}, []
    def get_thread(self, user, thread_id):
        assert thread_id == self.thread
        return thread_id, 1, {'parts': [{'ref': 'D1'}], 'nets': []}, '프로젝트'
    def start(self, user, thread_id, data):
        self.calls.append('start')
        return self.run, {}
    def resume(self, user, thread_id, run_id): self.calls.append(('claim', thread_id, run_id))
    def finish(self, user, thread_id, run_id, status, result):
        self.calls.append(('commit', status))
        self.status, self.result = status, result
    def get_run(self, user, run_id):
        return {'id': self.run, 'thread_id': self.thread, 'status': self.status, 'safe_result': self.result}


@pytest.fixture
def web(monkeypatch):
    """로그인·Origin을 통과시키고, 넘긴 가짜 분석 서비스·저장소로 TestClient를 연다."""
    from backend.api.conversations import repository
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    def open_client(analysis, repo):
        app.dependency_overrides[auth.current_user_id] = lambda: 1
        if repo is not None:
            app.dependency_overrides[repository] = lambda: repo
        if analysis is not None:
            app.state.conversations = analysis
        return TestClient(app, raise_server_exceptions=False)
    yield open_client
    app.dependency_overrides.clear()
    if hasattr(app.state, 'conversations'):
        del app.state.conversations


def test_role_catalog_requires_login_and_exposes_only_code_and_name():
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/api/judge/roles').status_code == 401

    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get('/api/judge/roles')
        assert response.status_code == 200
        roles = response.json()
        assert {'code': 'R01', 'name': '역극성 보호(직렬)'} in roles
        assert roles == sorted(roles, key=lambda role: role['code'])
        assert all(set(role) == {'code', 'name'} for role in roles)
    finally:
        app.dependency_overrides.clear()


def test_thread_endpoint_requires_login():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/projects/1/threads')
    assert response.status_code == 401


def test_first_run_creates_analysis_thread_and_saves_before_completed(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis(state={'answer': 'ok', 'facts': 'secret', 'question_type': 'candidate_judge'})
    repo = FakeRepo(thread, run)
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers=ORIGIN)
        assert response.status_code == 200
        assert response.text.index('event: run_started') < response.text.index('event: status') < response.text.index('event: completed')
        assert 'secret' not in response.text
        recovered = client.get(f'/api/runs/{run}')
    assert recovered.json()['result']['answer'] == 'ok'
    assert recovered.json()['result']['status'] == 'completed'
    assert analysis.calls == [('ensure', thread, '프로젝트', 'D1'), ('message', thread, 'hello', '')]
    assert repo.calls == ['start', ('commit', 'completed')]


def test_changed_target_is_409_before_a_run_is_created(web):
    thread = str(uuid4())
    analysis, repo = FakeAnalysis(), FakeRepo(thread, str(uuid4()))
    with web(analysis, repo) as client:
        first = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        second = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D2'}, headers=ORIGIN)
    assert first.status_code == 200 and second.status_code == 409
    assert second.json()['error'] == {'code': 'CONFLICT', 'message': '대상 부품을 바꾸려면 새 대화를 시작하세요.',
                                      'request_id': second.headers['X-Request-ID']}
    assert repo.calls.count('start') == 1


def test_missing_analysis_service_is_503_before_stream(web):
    thread = str(uuid4())
    repo = FakeRepo(thread, str(uuid4()))
    with web(None, repo) as client:
        start = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        resume = client.post(f'/api/runs/{uuid4()}/resume', json={'answers': {}}, headers=ORIGIN)
    for response in (start, resume):
        assert response.status_code == 503
        assert response.headers['content-type'].startswith('application/json')
        assert response.json()['error']['code'] == 'SERVICE_UNAVAILABLE'
    assert repo.calls == []


def test_failed_frame_carries_public_error_code_and_logs_unexpected_exception(web, caplog):
    thread = str(uuid4())
    analysis = FakeAnalysis(error=RuntimeError('private exception marker'))
    repo = FakeRepo(thread, str(uuid4()))
    with caplog.at_level('ERROR', logger='backend.api.conversations'), web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert 'event: failed' in response.text and '"code": "INTERNAL_ERROR"' in response.text
    assert 'private exception marker' not in response.text
    request_id = response.text.split('"request_id": "', 1)[1].split('"', 1)[0]
    logged = [r for r in caplog.records if request_id in r.getMessage()]
    assert logged and logged[0].exc_info and 'private exception marker' in str(logged[0].exc_info[1])
    assert repo.calls == ['start', ('commit', 'failed')]


def test_budget_refusal_maps_to_common_code_without_traceback(web, caplog):
    thread = str(uuid4())
    analysis = FakeAnalysis(error=HTTPException(429, '하루 분석 예약 예산에 도달했습니다.'))
    with caplog.at_level('ERROR', logger='backend.api.conversations'), web(analysis, FakeRepo(thread, str(uuid4()))) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert '"error": {"code": "TOO_MANY_REQUESTS", "message": "하루 분석 예약 예산에 도달했습니다."}' in response.text
    assert not caplog.records


def test_project_delete_rejects_active_run_before_checkpoint_deletion(monkeypatch):
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import InvalidRunState
    import pytest
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params):
            class Result:
                def fetchone(self): return (1,)
            return Result()
    monkeypatch.setattr(auth, 'connection', lambda: Conn())
    def service():
        pytest.fail('active runs must prevent checkpoint deletion')
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(1, 1, service)


def test_foreign_and_active_runs_return_safe_errors(web, monkeypatch):
    from backend.conversations.repository import ConversationNotFound, InvalidRunState
    thread = str(uuid4())
    for failing, exc, expected in [('get_thread', ConversationNotFound(), 404), ('start', InvalidRunState(), 409)]:
        repo = FakeRepo(thread, str(uuid4()))
        setattr(repo, failing, lambda *args, exc=exc: (_ for _ in ()).throw(exc))
        # 저장소 의존성의 예외 → 공통 404·409 변환까지 보려고 의존성은 바꾸지 않고 클래스만 바꾼다
        monkeypatch.setattr('backend.api.conversations.ConversationRepository', lambda repo=repo: repo)
        with web(FakeAnalysis(), None) as client:
            response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        assert response.status_code == expected
        assert response.json()['error']['request_id'] == response.headers['X-Request-ID']


def test_project_delete_with_threads_needs_no_checkpoint_tables(monkeypatch):
    executed = []
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params):
            assert 'checkpoint' not in query
            executed.append(query.split()[0])
            rows = {'SELECT id FROM projects': [(1,)], 'SELECT 1 FROM runs': [], 'SELECT id FROM threads': [(str(uuid4()),)]}
            found = next((v for k, v in rows.items() if query.startswith(k)), [])
            return SimpleNamespace(fetchone=lambda: found[0] if found else None, fetchall=lambda: found)
    monkeypatch.setattr(auth, 'connection', lambda: Conn())
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.delete('/api/projects/1', headers=ORIGIN)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 204
    assert executed[-1] == 'DELETE'


def test_disconnected_stream_keeps_running_and_saves_terminal():
    import asyncio
    import time
    from backend.api.conversations import stream
    class Repo:
        def finish(self, *args): self.result = args
    repo = Repo()
    analysis = FakeAnalysis()
    def slow():
        time.sleep(0.05)
        return {'interrupt': None}
    async def run():
        response = stream(repo, 1, 'thread', 'run', 'req', analysis, slow)
        iterator = response.body_iterator
        assert 'event: run_started' in await anext(iterator)
        await iterator.aclose()
        for _ in range(100):
            if hasattr(repo, 'result'): break
            await asyncio.sleep(0.01)
        assert repo.result[3] == 'completed'
        assert repo.result[4]['answer'] == 'ok'
    asyncio.run(run())


def test_resume_rejects_price_fields_before_service(web):
    analysis = FakeAnalysis()
    with web(analysis, FakeRepo(str(uuid4()), str(uuid4()))) as client:
        for key in ['price', 'stock', 'product_url', 'fetched_at']:
            response = client.post(f'/api/runs/{uuid4()}/resume', json={'answers': {key: 'private'}}, headers=ORIGIN)
            assert response.status_code == 422
    assert analysis.calls == []


def test_resume_uses_same_thread_and_current_analysis_version(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis()
    analysis.version = 3
    repo = FakeRepo(thread, run, status='requires_input')
    with web(analysis, repo) as client:
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in': '5 V'}}, headers=ORIGIN)
    assert response.status_code == 200 and 'event: completed' in response.text
    assert analysis.calls == [('resume', thread, {'v_in': '5 V'}, '', 3)]
    assert repo.calls == [('claim', thread, run), ('commit', 'completed')]


def test_resume_passes_an_owned_interrupt_role_choice(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis()
    repo = FakeRepo(thread, run, status='requires_input', result={'interrupt': {'role_choices': ['R01', 'R02']}})
    with web(analysis, repo) as client:
        missing = client.post(f'/api/runs/{run}/resume', json={'answers': {}}, headers=ORIGIN)
        assert missing.status_code == 422
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {}, 'role': 'R02'}, headers=ORIGIN)
        assert response.status_code == 200
    assert analysis.calls == [('resume', thread, {}, 'R02', 1)]


def test_interrupt_is_saved_as_requires_input(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis(interrupt={'question': '최대 입력 전압?', 'missing': ['VIN_MAX'], 'role_choices': []})
    repo = FakeRepo(thread, run)
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert 'event: requires_input' in response.text
    assert repo.status == 'requires_input' and repo.result['interrupt']['missing'] == ['VIN_MAX']


def test_terminal_commit_retries_a_transient_database_failure(web):
    import psycopg
    thread = str(uuid4())
    attempts = []
    repo = FakeRepo(thread, str(uuid4()))
    def finish(user, thread_id, run_id, status, result):
        attempts.append(status)
        if len(attempts) == 1:
            raise psycopg.OperationalError('temporary test outage')
    repo.finish = finish
    with web(FakeAnalysis(), repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers=ORIGIN)
    assert response.status_code == 200
    assert 'event: completed' in response.text
    assert attempts == ['completed', 'completed']
