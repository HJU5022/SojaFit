"""격리 PostgreSQL에서 사용자별 업로드·thread·체크포인트·승인 기억을 검증한다."""
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.conversations import Conversations, initialize
from backend.graph.nodes import read_input
from backend.graph.state import AgentState

NET = '(export (components (comp (ref "D1") (value "SS34"))) (nets (net (name "VCC") (node (ref "D1") (pin "1")))))'


def fake_graph(saver, store):
    def judge(state):
        if '조건 질문' in state['question']:
            reply = interrupt({'question': '최대 입력 전압을 알려주세요.', 'missing': ['VIN_MAX'], 'role_choices': []})
            assert reply['answers']['VIN_MAX'] == '12'
        if '거절' in state['question']:
            return {'answer': '근거 없음', 'judgement': {}, 'refusal': {'code': 'not_found'}}
        return {'answer': '역할상 충분 [1]', 'judgement': {'roles': ['REVERSE_POLARITY'],
            'shown': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]}}
    graph = StateGraph(AgentState)
    graph.add_node('read', read_input)
    graph.add_node('judge', judge)
    graph.add_edge(START, 'read')
    graph.add_edge('read', 'judge')
    graph.add_edge('judge', END)
    return graph.compile(checkpointer=saver, store=store)


@pytest.fixture
def runtime():
    dsn = os.getenv('TEST_THREAD_DATABASE_URL')
    if not dsn:
        pytest.skip('requires isolated TEST_THREAD_DATABASE_URL')
    initialize(dsn)
    with psycopg.connect(dsn) as conn:
        users = [conn.execute("INSERT INTO public.users(login_id,password_hash) VALUES (%s,'test-only') RETURNING id",
                 (f'thread-{uuid4()}@example.test',)).fetchone()[0] for _ in range(2)]
    app = Conversations(dsn, factory=fake_graph)
    try:
        yield app, users, dsn
    finally:
        app.close()
        with psycopg.connect(dsn) as conn:
            for user in users:
                conn.execute('DELETE FROM sojafit_agent.threads WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM sojafit_agent.circuits WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM public.users WHERE id=%s', (user,))


def make_thread(app, user):
    circuit = app.upload(user, 'my.net', NET)
    return app.create(user, circuit['id'], 'D1')['id']


def test_other_user_cannot_access_circuit_thread_resume_or_approval(runtime):
    app, (a, b), _ = runtime
    circuit = app.upload(a, 'my.net', NET)
    thread = app.create(a, circuit['id'], 'D1')['id']
    assert app.circuits(b) == [] and app.threads(b) == []
    for call in (lambda: app.create(b, circuit['id'], 'D1'), lambda: app.detail(b, thread),
                 lambda: app.message(b, thread, '판정해줘'), lambda: app.resume(b, thread, {}, '', 0),
                 lambda: app.approve(b, thread, 0), lambda: app.retry(b, thread, 0)):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 404
    assert app.detail(a, thread)['version'] == 0


def test_checkpoint_history_and_interrupt_survive_runtime_reconnection(runtime):
    app, (a, _), dsn = runtime
    thread = make_thread(app, a)
    other = make_thread(app, a)
    pending = app.message(a, thread, '조건 질문')
    assert pending['interrupt']['missing'] == ['VIN_MAX']
    app.close()
    reopened = Conversations(dsn, factory=fake_graph)
    try:
        assert reopened.detail(a, thread)['interrupt']['question']
        with pytest.raises(HTTPException) as stale:
            reopened.resume(a, thread, {'VIN_MAX': '12'}, '', pending['version'] + 1)
        assert stale.value.status_code == 409
        result = reopened.resume(a, thread, {'VIN_MAX': '12'}, '', pending['version'])
        assert result['answer'] == '역할상 충분 [1]' and result['can_approve']
        assert reopened.detail(a, other)['messages'] == []
        assert len(reopened.detail(a, thread)['messages']) >= 2
    finally:
        reopened.close()


def test_approval_is_owned_versioned_and_idempotent(runtime):
    app, (a, b), _ = runtime
    thread = make_thread(app, a)
    result = app.message(a, thread, 'SS34로 판정해줘')
    version = result['version']
    app.approve(a, thread, version)
    app.approve(a, thread, version)
    memories = app.memories(a)
    assert len(memories) == 1 and app.memories(b) == []
    next_thread = make_thread(app, a)
    related = app.message(a, next_thread, 'SS34로 판정해줘')['related_memories']
    assert related[0]['thread_id'] == thread
    newer = app.message(a, thread, '다시 SS34로 판정해줘')
    assert app.approve(a, thread, version)['ok']
    app.approve(a, thread, newer['version'])
    assert len(app.memories(a)) == 2
    assert app.memories(a)[0]['judgement']['shown'][0]['part'] == 'SS34'


def test_store_failure_can_be_retried_without_losing_approval(runtime, monkeypatch):
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    version = app.message(a, thread, '판정')['version']
    put = app.store.put
    monkeypatch.setattr(app.store, 'put', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('synthetic')))
    with pytest.raises(HTTPException) as error:
        app.approve(a, thread, version)
    assert error.value.status_code == 503
    monkeypatch.setattr(app.store, 'put', put)
    app.approve(a, thread, version)
    assert len(app.memories(a)) == 1


@pytest.mark.parametrize('legacy_snapshot', [False, True])
def test_old_approval_store_recovers_after_new_question(runtime, monkeypatch, legacy_snapshot):
    app, (a, b), dsn = runtime
    thread = make_thread(app, a)
    version = app.message(a, thread, '판정')['version']
    put = app.store.put
    monkeypatch.setattr(app.store, 'put', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('synthetic')))
    with pytest.raises(HTTPException) as error:
        app.approve(a, thread, version)
    assert error.value.status_code == 503
    with psycopg.connect(dsn) as conn:
        if legacy_snapshot:
            conn.execute("UPDATE sojafit_agent.approvals SET snapshot=snapshot-'part' WHERE thread_id=%s", (thread,))
        original = conn.execute('SELECT snapshot,approved_at FROM sojafit_agent.approvals WHERE thread_id=%s', (thread,)).fetchone()
        if not legacy_snapshot:
            assert original[0]['part'] == 'SS34'
    monkeypatch.setattr(app.store, 'put', put)
    assert app.memories(a) == []
    assert app.message(a, thread, '거절')['version'] == version + 1
    # 현재 상태의 품번을 복구 원본으로 잘못 쓰지 않는지 확인한다.
    app.graph.update_state(app.config(thread), {'target_part': {'value': 'DIFFERENT'}})
    with pytest.raises(HTTPException) as denied:
        app.approve(b, thread, version)
    assert denied.value.status_code == 404
    for _ in range(2):
        assert app.approve(a, thread, version) == {'ok': True, 'version': version}
    memories = app.memories(a)
    assert len(memories) == 1 and app.memories(b) == []
    assert memories[0]['part'] == 'SS34' and memories[0]['version'] == version
    assert memories[0]['summary'] == original[0]['answer']
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT snapshot,approved_at FROM sojafit_agent.approvals WHERE thread_id=%s', (thread,)).fetchall() == [original]
    assert app.detail(a, thread)['version'] == version + 1


def test_unapproved_old_version_still_cannot_be_approved(runtime):
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    version = app.message(a, thread, '판정')['version']
    app.message(a, thread, '다시 판정')
    with pytest.raises(HTTPException) as error:
        app.approve(a, thread, version)
    assert error.value.status_code == 409
    assert app.memories(a) == []


def test_http_recovers_old_approval_after_new_question(runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app as api
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    api.state.conversations = app
    api.dependency_overrides[auth.current_user_id] = lambda: a
    client = TestClient(api)
    origin = {'Origin': 'http://localhost:8000'}
    try:
        version = client.post(f'/api/threads/{thread}/messages', headers=origin, json={'text': '판정'}).json()['version']
        put = app.store.put
        monkeypatch.setattr(app.store, 'put', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('synthetic')))
        assert client.post(f'/api/threads/{thread}/approve', headers=origin, json={'version': version}).status_code == 503
        monkeypatch.setattr(app.store, 'put', put)
        newer = client.post(f'/api/threads/{thread}/messages', headers=origin, json={'text': '거절'})
        assert newer.status_code == 200 and newer.json()['version'] == version + 1
        recovered = client.post(f'/api/threads/{thread}/approve', headers=origin, json={'version': version})
        assert recovered.status_code == 200 and recovered.json() == {'ok': True, 'version': version}
        memories = client.get('/api/memories').json()
        assert len(memories) == 1 and memories[0]['version'] == version and memories[0]['part'] == 'SS34'
    finally:
        api.dependency_overrides.clear()
        del api.state.conversations


def test_new_threads_pass_only_owned_approved_memories_to_models(runtime, monkeypatch):
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.contracts import Plan, Task
    from backend.services import llm
    app, (a, b), dsn = runtime
    sources = {}
    for user, marker in ((a, 'PRIVATE_A_CASE'), (b, 'PRIVATE_B_CASE')):
        thread = make_thread(app, user)
        app.message(user, thread, '판정', conditions='과거 조건 12V')
        app.graph.update_state(app.config(thread), {'answer': marker})
        app.approve(user, thread, 1)
        sources[user] = thread
    # 같은 사용자의 무관 품번과, 자기 namespace에 잘못 들어간 타인 포인터도 제외한다.
    unrelated = app.upload(a, 'other.net', NET.replace('SS34', '1N4148'))
    unrelated_thread = app.create(a, unrelated['id'], 'D1')['id']
    app.message(a, unrelated_thread, '판정')
    app.graph.update_state(app.config(unrelated_thread), {'answer': 'UNRELATED_CASE'})
    app.approve(a, unrelated_thread, 1)
    from backend.graph.memory import namespace
    app.store.put(namespace(str(a)), 'foreign-pointer', {'thread_id': sources[b], 'version': 1,
                  'part': 'SS34', 'roles': [], 'summary': 'FORGED_CASE'})
    calls = []
    def chat(node, system, user, schema, **kwargs):
        calls.append((node, system, user))
        if node == 'supervisor':
            return Plan(next='tasks', question_type='role', tasks=[Task(id=1, agent='docs', kind='role', goal='explain prior case')])
        assert node == 'docs_answer'
        marker = 'PRIVATE_A_CASE' if 'PRIVATE_A_CASE' in user else 'PRIVATE_B_CASE' if 'PRIVATE_B_CASE' in user else 'NO_MEMORY'
        return schema(grade='enough', answer=f'{marker} 사례를 참고하되 현재 회로에서 다시 확인합니다 [넷리스트].')
    monkeypatch.setattr(llm, 'node_chat', chat)
    app.graph = build_graph(chat=chat, retriever=lambda *args, **kwargs: [], checkpointer=app.saver, store=app.store)
    for owner, own, foreign in ((a, 'PRIVATE_A_CASE', 'PRIVATE_B_CASE'), (b, 'PRIVATE_B_CASE', 'PRIVATE_A_CASE')):
        calls.clear()
        thread = make_thread(app, owner)
        result = app.message(owner, thread, 'D1 역할과 과거 사례를 설명해줘')
        assert own in result['answer'] and foreign not in result['answer']
        assert {c[0] for c in calls} == {'supervisor', 'docs_answer'}
        for _, system, prompt in calls:
            assert own in prompt and foreign not in prompt and '과거 조건 12V' in prompt
            assert 'UNRELATED_CASE' not in prompt and 'FORGED_CASE' not in prompt
            assert sources[owner] in prompt and 'historical' in system.lower()
        state = app.graph.get_state(app.config(thread)).values
        assert len(state['approved_memories']) == 1
        assert state['approved_memories'][0]['thread_id'] == sources[owner]
        # 사용자 소유권을 확인할 수 없는 Store 항목과 무관 품번은 모델에 전달하지 않는다.
        with psycopg.connect(dsn) as conn:
            conn.execute('DELETE FROM sojafit_agent.approvals WHERE thread_id=%s', (sources[owner],))
        calls.clear()
        assert 'NO_MEMORY' in app.message(owner, thread, '다시 설명해줘')['answer']
        assert all(own not in prompt and foreign not in prompt for _, _, prompt in calls)
        assert app.graph.get_state(app.config(thread)).values['approved_memories'] == []


def test_thread_lock_rejects_concurrent_write_and_refusal_cannot_be_approved(runtime):
    app, (a, _), dsn = runtime
    thread = make_thread(app, a)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))', (thread,))
        try:
            with pytest.raises(HTTPException) as error:
                app.message(a, thread, '판정')
            assert error.value.status_code == 409
        finally:
            conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (thread,))
    result = app.message(a, thread, '거절')
    assert not result['can_approve']
    with pytest.raises(HTTPException):
        app.approve(a, thread, result['version'])


def test_planned_judge_subgraph_preserves_memory_and_resumes_from_postgres(runtime):
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.contracts import Plan, Task
    app, (a, _), dsn = runtime
    source = make_thread(app, a)
    app.message(a, source, '판정')
    app.graph.update_state(app.config(source), {'answer': 'MEMORY_FOR_JUDGE'})
    app.approve(a, source, 1)
    calls = []
    def chat(node, system, user, schema):
        calls.append(node)
        assert 'MEMORY_FOR_JUDGE' in user
        if node == 'supervisor':
            return Plan(next='tasks', question_type='candidate_judge', tasks=[
                Task(id=1, agent='judge', kind='candidate_judge', goal='judge SS34')])
        assert node == 'judge_read'
        return schema(role='R01', original_part='SS34', candidates=['SS34'])
    def factory(saver, store):
        return build_graph(chat=chat, retriever=lambda *args, **kwargs: [], judge_enabled=True,
                           specs=lambda *args, **kwargs: [], find=lambda *args, **kwargs: [],
                           checkpointer=saver, store=store)
    app.graph = factory(app.saver, app.store)
    thread = make_thread(app, a)
    pending = app.message(a, thread, 'SS34를 판정해줘')
    assert pending['status'] == 'WAITING' and pending['interrupt']['missing']
    assert calls.count('judge_read') == 1
    app.close()
    reopened = Conversations(dsn, factory=factory)
    try:
        assert reopened.detail(a, thread)['interrupt'] == pending['interrupt']
        result = reopened.resume(a, thread, {}, '', pending['version'])
        assert result['status'] == 'DONE' and result['can_approve']
        assert calls.count('judge_read') == 1
        assert reopened.approve(a, thread, result['version'])['ok']
        assert len(reopened.memories(a)) == 2
    finally:
        reopened.close()


def test_http_flow_uses_session_owner_and_rejects_state_injection(runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app as api
    app, (a, b), _ = runtime
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    api.state.conversations = app
    client = TestClient(api)
    origin = {'Origin': 'http://localhost:8000'}
    try:
        assert client.get('/api/threads').status_code == 401
        api.dependency_overrides[auth.current_user_id] = lambda: a
        response = client.post('/api/circuits', headers=origin, json={'filename': 'my.net', 'netlist': NET})
        assert response.status_code == 200
        circuit = response.json()['id']
        created = client.post('/api/threads', headers=origin, json={'circuit_id': circuit, 'target': 'D1'})
        thread = created.json()['id']
        injected = client.post(f'/api/threads/{thread}/messages', headers=origin,
                               json={'text': 'test', 'user_id': b, 'netlist_path': '.env'})
        assert injected.status_code == 422
        result = client.post(f'/api/threads/{thread}/messages', headers=origin, json={'text': '넷리스트: .env\n대상: D999\nSS34 판정'})
        assert result.status_code == 200 and result.json()['target'] == 'D1'
        assert result.headers['cache-control'] == 'no-store'
        assert client.post(f'/api/threads/{thread}/approve', headers={'Origin': 'https://wrong.example'},
                           json={'version': result.json()['version']}).status_code == 403
        api.dependency_overrides[auth.current_user_id] = lambda: b
        assert client.get(f'/api/threads/{thread}').status_code == 404
        assert client.get('/api/memories').json() == []
    finally:
        api.dependency_overrides.clear()
        del api.state.conversations


def test_workspace_and_login_have_upload_and_analysis_navigation():
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)
    assert 'href="/workspace"' in client.get('/login').text
    html = client.get('/workspace').text
    for expected in ('id="netlist"', 'id="target"', 'id="messages"', 'id="approve"', 'id="memories"'):
        assert expected in html
    assert 'localStorage' not in html and 'innerHTML' not in html
    assert 'data.error?.message' in html


def test_thread_database_error_uses_common_error_envelope(runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app as api
    app, (a, _), _ = runtime
    api.state.conversations = app
    api.dependency_overrides[auth.current_user_id] = lambda: a
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    monkeypatch.setattr(app, 'upload', lambda *args: (_ for _ in ()).throw(psycopg.OperationalError('private-db-detail')))
    try:
        response = TestClient(api).post('/api/circuits', headers={'Origin': 'http://localhost:8000'},
                                        json={'filename': 'my.net', 'netlist': NET})
        assert response.status_code == 503 and response.headers['cache-control'] == 'no-store'
        assert response.json()['error']['code'] == 'SERVICE_UNAVAILABLE'
        assert response.json()['error']['request_id'] == response.headers['X-Request-ID']
        assert 'private-db-detail' not in response.text
    finally:
        api.dependency_overrides.clear()
        del api.state.conversations


def test_failed_node_can_retry_its_saved_execution(runtime):
    app, (a, _), _ = runtime
    attempts = []
    def sometimes(state):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError('synthetic transient model failure')
        return {'answer': '복구됨', 'judgement': {'roles': ['REVERSE_POLARITY'], 'shown': [{'part': 'SS34'}]}}
    graph = StateGraph(AgentState)
    graph.add_node('judge', sometimes)
    graph.add_edge(START, 'judge')
    graph.add_edge('judge', END)
    app.graph = graph.compile(checkpointer=app.saver, store=app.store)
    thread = make_thread(app, a)
    with pytest.raises(HTTPException) as error:
        app.message(a, thread, '판정')
    assert error.value.status_code == 503
    detail = app.detail(a, thread)
    assert detail['can_retry'] and not detail['interrupt']
    recovered = app.retry(a, thread, detail['version'])
    assert recovered['answer'] == '복구됨' and recovered['can_approve']
    assert len([m for m in recovered['messages'] if m['role'] == 'user']) == 1


def test_completed_checkpoint_reconciles_failed_metadata_without_duplicate_answer(runtime, monkeypatch):
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    finish = app._finish
    calls = []
    def fail_once(*args):
        calls.append(1)
        if len(calls) == 1:
            raise psycopg.OperationalError('synthetic metadata failure')
        return finish(*args)
    monkeypatch.setattr(app, '_finish', fail_once)
    with pytest.raises(HTTPException):
        app.message(a, thread, '판정')
    detail = app.detail(a, thread)
    assert detail['status'] == 'DONE' and detail['can_approve']
    assert sum(m['role'] == 'assistant' for m in detail['messages']) == 1
    assert app.detail(a, thread)['messages'] == detail['messages']
    assert app.approve(a, thread, detail['version'])['ok']


def test_retry_limit_and_private_schema_permissions(runtime):
    from psycopg import sql
    app, (a, _), dsn = runtime
    def fail(state):
        raise RuntimeError('synthetic persistent failure')
    graph = StateGraph(AgentState)
    graph.add_node('fail', fail)
    graph.add_edge(START, 'fail')
    graph.add_edge('fail', END)
    app.graph = graph.compile(checkpointer=app.saver)
    thread = make_thread(app, a)
    with pytest.raises(HTTPException):
        app.message(a, thread, '판정')
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            app.retry(a, thread, 1)
        assert error.value.status_code == 503
    assert not app.detail(a, thread)['can_retry']
    with pytest.raises(HTTPException) as error:
        app.retry(a, thread, 1)
    assert error.value.status_code == 409
    with psycopg.connect(dsn) as conn:
        role = 'probe_' + uuid4().hex
        conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
        assert not conn.execute("SELECT has_schema_privilege(current_user,'sojafit_agent','USAGE')").fetchone()[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('SELECT * FROM sojafit_agent.threads')
        conn.rollback()


def test_http_body_size_and_resume_values_are_bounded(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app
    client = TestClient(app)
    try:
        app.dependency_overrides[auth.current_user_id] = lambda: 1
        monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
        response = client.post('/api/circuits', content=b'x' * (7 * 1024 * 1024 + 1))
        assert response.status_code == 413 and response.headers['cache-control'] == 'no-store'
        response = client.post(f'/api/threads/{uuid4()}/resume', headers={'Origin': 'http://localhost:8000'},
                               json={'version': 1, 'answers': {'VIN_MAX': 'x' * 201}})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_enabled_app_lifespan_opens_and_closes_real_persistence(runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    _, _, dsn = runtime
    monkeypatch.setenv('DATABASE_URL', dsn)
    monkeypatch.setenv('THREADS_ENABLED', '1')
    monkeypatch.setenv('DEMO_MODE', '1')
    monkeypatch.setenv('AUTH_SECRET', 'local-lifespan-test-secret-32-bytes-long')
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert app.state.conversations.graph.store is app.state.conversations.store
    assert not hasattr(app.state, 'conversations')
