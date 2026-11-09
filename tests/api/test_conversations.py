from fastapi.testclient import TestClient
from backend import auth
from backend.main import app


def test_thread_endpoint_requires_login():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/projects/1/threads')
    assert response.status_code == 401


def test_stream_commits_before_terminal_and_recovery_does_not_restart(monkeypatch):
    from contextlib import asynccontextmanager
    from backend.api.conversations import repository, service_factory
    from backend.services.d5 import RunEvent
    from uuid import uuid4
    thread, run = str(uuid4()), str(uuid4())
    calls = []
    class Repo:
        status = 'running'
        result = {}
        def start(self, user, thread_id, data):
            assert thread_id == thread
            return run, {'parts': [], 'nets': []}
        def finish(self, user, thread_id, run_id, status, result):
            calls.append('commit')
            self.status, self.result = status, result
        def get_run(self, user, run_id):
            return {'id': run, 'thread_id': thread, 'status': self.status, 'safe_result': self.result}
    repo = Repo()
    class Fake:
        async def start(self, thread_id, data):
            calls.append('start')
            yield RunEvent(type='status', stage='running')
            yield RunEvent(type='completed', stage='finished', state={'answer': 'ok', 'facts': 'secret'})
    @asynccontextmanager
    async def service():
        yield Fake()
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    app.dependency_overrides[repository] = lambda: repo
    app.dependency_overrides[service_factory] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers={'origin': 'http://testserver'})
            assert response.status_code == 200
            assert response.text.index('event: run_started') < response.text.index('event: status') < response.text.index('event: completed')
            assert 'secret' not in response.text
            recovered = client.get(f'/api/runs/{run}')
            assert recovered.json()['result']['answer'] == 'ok'
            assert recovered.json()['result']['status'] == 'completed'
            assert calls == ['start', 'commit']
    finally:
        app.dependency_overrides.clear()


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


def test_foreign_and_active_runs_return_safe_errors(monkeypatch):
    from backend.api.conversations import repository
    from backend.conversations.repository import ConversationNotFound, InvalidRunState
    from uuid import uuid4
    from contextlib import contextmanager
    import pytest
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    thread = str(uuid4())
    try:
        for exc, expected in [(ConversationNotFound(), 404), (InvalidRunState(), 409)]:
            class Repo:
                def start(self, *args): raise exc
            monkeypatch.setattr('backend.api.conversations.ConversationRepository', Repo)
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers={'origin': 'http://testserver'})
                assert response.status_code == expected
                assert response.json()['error']['request_id'] == response.headers['X-Request-ID']
    finally:
        app.dependency_overrides.clear()


def test_disconnected_stream_keeps_running_and_saves_terminal():
    import asyncio
    from contextlib import asynccontextmanager
    from backend.api.conversations import stream
    from backend.services.d5 import RunEvent, RunInput
    class Repo:
        def finish(self, *args): self.result = args
    repo = Repo()
    completed = asyncio.Event()
    @asynccontextmanager
    async def service():
        class Fake:
            async def start(self, *args):
                await asyncio.sleep(0.01)
                yield RunEvent(type='completed', state={'answer': 'ok'})
                completed.set()
        yield Fake()
    async def run():
        response = stream(repo, 1, 'thread', 'run', 'req', service, RunInput(question='hi', target_ref='', connections={}))
        iterator = response.body_iterator
        assert 'event: run_started' in await anext(iterator)
        await iterator.aclose()
        for _ in range(50):
            if hasattr(repo, 'result'): break
            await asyncio.sleep(0.01)
        assert repo.result[3] == 'completed'
        assert repo.result[4]['answer'] == 'ok'
    asyncio.run(run())


def test_resume_rejects_price_fields_before_service(monkeypatch):
    from uuid import uuid4
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for key in ['price', 'stock', 'product_url', 'fetched_at']:
                response = client.post(f'/api/runs/{uuid4()}/resume', json={'answers': {key: 'private'}}, headers={'origin': 'http://testserver'})
                assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_resume_stream_uses_same_owned_thread_and_run(monkeypatch):
    from contextlib import asynccontextmanager
    from backend.api.conversations import repository, service_factory
    from backend.services.d5 import RunEvent
    from uuid import uuid4
    thread, run = str(uuid4()), str(uuid4())
    calls = []
    class Repo:
        def get_run(self, user, run_id):
            return {'id': run_id, 'thread_id': thread, 'status': 'requires_input', 'safe_result': {}}
        def resume(self, user, thread_id, run_id): calls.append(('claim', thread_id, run_id))
        def finish(self, user, thread_id, run_id, status, result): calls.append(('commit', thread_id, run_id, status))
    class Fake:
        async def resume(self, thread_id, answers):
            calls.append(('resume', thread_id, answers))
            yield RunEvent(type='completed', state={'answer': 'done'})
    @asynccontextmanager
    async def service(): yield Fake()
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    app.dependency_overrides[repository] = lambda: Repo()
    app.dependency_overrides[service_factory] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in': '5 V'}}, headers={'origin': 'http://testserver'})
            assert response.status_code == 200
            assert 'event: completed' in response.text
            assert calls == [('claim', thread, run), ('resume', thread, {'v_in': '5 V'}), ('commit', thread, run, 'completed')]
    finally:
        app.dependency_overrides.clear()


def test_resume_passes_an_owned_interrupt_role_choice(monkeypatch):
    from contextlib import asynccontextmanager
    from backend.api.conversations import repository, service_factory
    from backend.services.d5 import RunEvent
    from uuid import uuid4
    thread, run = str(uuid4()), str(uuid4())
    calls = []
    class Repo:
        def get_run(self, user, run_id):
            return {'id': run_id, 'thread_id': thread, 'status': 'requires_input',
                    'safe_result': {'interrupt': {'role_choices': ['R01', 'R02']}}}
        def resume(self, user, thread_id, run_id): calls.append(('claim', thread_id, run_id))
        def finish(self, user, thread_id, run_id, status, result): calls.append(('commit', status))
    class Fake:
        async def resume(self, thread_id, answers, role=None):
            calls.append(('resume', thread_id, answers, role))
            yield RunEvent(type='completed', state={'answer': 'done'})
    @asynccontextmanager
    async def service(): yield Fake()
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    app.dependency_overrides[repository] = lambda: Repo()
    app.dependency_overrides[service_factory] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f'/api/runs/{run}/resume', json={'answers': {}, 'role': 'R02'},
                                   headers={'origin': 'http://testserver'})
            assert response.status_code == 200
            assert calls == [('claim', thread, run), ('resume', thread, {}, 'R02'), ('commit', 'completed')]
            missing = client.post(f'/api/runs/{run}/resume', json={'answers': {}},
                                  headers={'origin': 'http://testserver'})
            assert missing.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_terminal_commit_retries_a_transient_database_failure(monkeypatch):
    from contextlib import asynccontextmanager
    from backend.api.conversations import repository, service_factory
    from backend.services.d5 import RunEvent
    from uuid import uuid4
    import psycopg
    thread, run = str(uuid4()), str(uuid4())
    attempts = []
    class Repo:
        def start(self, user, thread_id, data): return run, {'parts': [], 'nets': []}
        def finish(self, user, thread_id, run_id, status, result):
            attempts.append(status)
            if len(attempts) == 1:
                raise psycopg.OperationalError('temporary test outage')
    class Fake:
        async def start(self, thread_id, data):
            yield RunEvent(type='completed', state={'answer': 'ok'})
    @asynccontextmanager
    async def service(): yield Fake()
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    app.dependency_overrides[repository] = lambda: Repo()
    app.dependency_overrides[service_factory] = lambda: service
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f'/api/threads/{thread}/runs',
                                   json={'question': 'hello', 'target_ref': 'D1'},
                                   headers={'origin': 'http://testserver'})
            assert response.status_code == 200
            assert 'event: completed' in response.text
            assert attempts == ['completed', 'completed']
    finally:
        app.dependency_overrides.clear()
