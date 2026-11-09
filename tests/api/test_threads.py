"""격리 PostgreSQL에서 사용자 분석 서비스(`Conversations`)의 thread · 체크포인트 · 예산 · 승인 기록 · 사용자 사실 참고(profile_hints)를 검증한다.

React run · 재개가 거치는 `ensure_thread` · `message` · `resume` · `admission`과, React 대화 HTTP가 이 서비스로 이어지는지 본다.
React 이전 화면(`/workspace`)의 HTTP 경로 시험은 11-10에 경로와 함께 지웠다. `make_thread`의 `upload` · `create`와 `approve`는
HTTP 경로가 없는 서비스 메서드로, 옛 직접 thread · 승인 기록 행을 만드는 데만 쓴다.
"""
import os
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.conversations.memory_service import Conversations, initialize
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
def runtime(monkeypatch):
    monkeypatch.setenv('ANALYSIS_MIN_INTERVAL_SECONDS', '0')
    dsn = os.getenv('TEST_THREAD_DATABASE_URL')
    if not dsn:
        pytest.skip('requires isolated TEST_THREAD_DATABASE_URL')
    if os.getenv('TEST_THREAD_BACKUP_CONTAINER'):
        from psycopg.conninfo import conninfo_to_dict
        info = conninfo_to_dict(dsn)
        if info.get('host') not in ('127.0.0.1', 'localhost') or not info.get('dbname', '').startswith('thread_test'):
            pytest.fail('Backup drill requires a disposable loopback thread_test DB before initialization', pytrace=False)
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
                conn.execute('DELETE FROM sojafit_agent.store WHERE prefix LIKE %s', (f'{user}.%',))  # 사용자 사실(namespace 첫 칸 = 사용자)
                conn.execute('DELETE FROM sojafit_agent.threads WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM sojafit_agent.circuits WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM public.users WHERE id=%s', (user,))
            # [왜] 서비스 전체 하루 토큰 카운터는 사용자와 무관한 한 행이다. 격리 시험 DB에서 시험마다 비워 다음 시험이 상한에 걸리지 않게 한다
            conn.execute("DELETE FROM sojafit_agent.analysis_service_usage WHERE day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date")


def make_thread(app, user):
    circuit = app.upload(user, 'my.net', NET)
    return app.create(user, circuit['id'], 'D1')['id']


def test_demo_scenarios_use_real_graph_and_storage_without_external_calls(runtime, monkeypatch):
    from backend.services import demo, llm
    from backend.graph.mcp_retriever import StdioMcpRetriever
    app, (a, b), dsn = runtime
    monkeypatch.setenv('DEMO_SCENARIOS', '1'); monkeypatch.setenv('DEMO_MODE', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'must-not-be-used')
    monkeypatch.setattr(llm, '_chat_model', lambda *a: pytest.fail('paid model called'))
    monkeypatch.setattr(StdioMcpRetriever, '__enter__', lambda *a: pytest.fail('external MCP called'))
    app.graph = app._graph()
    fixture = demo.configuration()
    circuit = app.upload(a, 'demo.net', fixture['netlist'])
    thread = app.create(a, circuit['id'], 'D1')['id']
    first = app.message(a, thread, fixture['questions']['judge'])
    assert first['status'] == 'WAITING' and first['mode'] == 'demo'
    result = app.resume(a, thread, {'v_in_max':'12V', 'i_max':'0.1A', 'v_drop_allowed':'모름'}, '', 1)
    assert result['can_approve'] and '합성' in result['answer']
    assert app.approve(a, thread, 1)['ok'] and len(app.memories(a)) == 1
    with pytest.raises(HTTPException) as error:
        app.detail(b, thread)
    assert error.value.status_code == 404 and app.memories(b) == []
    second = app.create(a, circuit['id'], 'D1')['id']
    role = app.message(a, second, fixture['questions']['role'])
    assert role['referenced_memories'] == role['consulted_memories'] == [] and role['mode'] == 'demo'
    with pytest.raises(HTTPException) as error:
        app.message(a, second, '지원하지 않는 질문')
    assert error.value.status_code == 422 and app.detail(a, second)['version'] == 1
    with pytest.raises(HTTPException):
        app.upload(a, 'other.net', NET)


def test_live_graph_uses_card_tools_and_keeps_their_attributes(monkeypatch):
    """[왜] 사양 표를 버리고 카드 도구가 기본이다(ADR 0016). timed_tool로 감싸도 판정이 getattr로 찾는 prefetch · also_read가 남아야 한다."""
    from contextlib import ExitStack
    from backend.graph import mcp_retriever
    from backend.multi_agent import build
    from backend.rag import card_find, card_specs
    from backend.services import demo

    class Mcp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def check(self, parts, revisions): return {'parts': {}, 'revisions': {}}
    def specs(part, codes=None): return ['row']
    specs.prefetch, specs.doc_rows = (lambda parts, codes: None), (lambda part, codes=None: [])
    def find(*a, **k): return ['part']
    find.also_read = lambda codes: None
    seen = {}
    monkeypatch.setattr(demo, 'enabled', lambda: False)
    monkeypatch.setattr(mcp_retriever, 'StdioMcpRetriever', Mcp)
    monkeypatch.setattr(card_specs, 'default_specs', lambda: specs)
    monkeypatch.setattr(card_find, 'default_find', lambda: find)
    monkeypatch.setattr(build, 'build_graph', lambda **kw: seen.update(kw) or 'graph')
    app = Conversations.__new__(Conversations)  # [왜] DB 없이 조립만 본다
    app.stack, app.saver, app.store = ExitStack(), None, None
    assert app._graph() == 'graph'
    assert seen['specs']('SS34') == ['row'] and seen['specs'].prefetch is specs.prefetch
    assert seen['find']() == ['part'] and seen['find'].also_read is find.also_read


def test_demo_mode_is_explicit_and_never_enables_replay_for_real_evaluations(monkeypatch):
    from backend.services import demo
    monkeypatch.setenv('DEMO_MODE', '1'); monkeypatch.delenv('DEMO_SCENARIOS', raising=False)
    assert not demo.enabled()
    monkeypatch.setenv('DEMO_SCENARIOS', '1'); monkeypatch.setenv('DEMO_MODE', '0')
    with pytest.raises(ValueError):
        demo.enabled()


def test_analysis_events_are_owned_content_free_and_separate_resume_wait(runtime, monkeypatch):
    from backend.services import langfuse_prompts
    app, (a, b), dsn = runtime
    monkeypatch.setattr(langfuse_prompts, 'publish_analysis_trace', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('private-key')))
    thread = make_thread(app, a)
    app.message(a, thread, '조건 질문', request_id='request-1')
    app.resume(a, thread, {'VIN_MAX':'12'}, '', 1, request_id='request-2')
    events = app.detail(a, thread)['events']
    assert len(events) == 2 and {e['status'] for e in events} == {'WAITING','DONE'}
    assert {e['request_id'] for e in events} == {'request-1','request-2'}
    assert all(e['version'] == 1 and e['elapsed_ms'] >= 0 and e['trace_delivery'] == 'failed' for e in events)
    assert all(e['stages'] for e in events)
    assert '조건 질문' not in str(events) and 'private-key' not in str(events)
    with pytest.raises(HTTPException):
        app.detail(b, thread)


def test_approved_cases_are_not_sent_to_new_analysis_or_resume(runtime):
    from backend.graph.memory import memory_context, memory_sources
    app, (a, _), _ = runtime
    original = make_thread(app, a); app.message(a, original, '판정'); app.approve(a, original, 1)
    seen = []
    def interrupted(state):
        interrupt({'missing':['VIN_MAX'],'role_choices':[]})
        seen.append((memory_context(state['approved_memories']), memory_sources(state['approved_memories'])))
        return {'answer':'재개됨','judgement':{}}
    graph = StateGraph(AgentState); graph.add_node('read', read_input); graph.add_node('work',interrupted)
    graph.add_edge(START,'read'); graph.add_edge('read','work'); graph.add_edge('work',END)
    app.graph = graph.compile(checkpointer=app.saver, store=app.store)
    thread = make_thread(app, a); app.message(a, thread, '조건 질문')
    assert app.graph.get_state(app.config(thread)).values['approved_memories'] == []
    app.resume(a, thread, {'VIN_MAX':'12'}, '', 1)
    assert seen == [('',set())] and len(app.memories(a)) == 1


def test_readiness_checks_current_schema_and_permissions(runtime, monkeypatch):
    from psycopg.conninfo import make_conninfo
    app, _, _ = runtime
    app.readiness()
    monkeypatch.setattr(app, 'dsn', make_conninfo(app.dsn, options='-c search_path=pg_catalog'))
    with pytest.raises(psycopg.errors.UndefinedTable):
        app.readiness()


def test_react_thread_maps_to_one_owned_analysis_thread_with_fixed_target(runtime):
    """React 정규화 회로(parts)로 같은 UUID의 분석 thread를 만들고, 대상 고정 · 소유권 · 원본 미저장을 지킨다."""
    app, (a, b), dsn = runtime
    thread = str(uuid4())
    react = {'parts': [{'ref': 'D1', 'value': 'SS34', 'footprint': ''}, {'ref': 'D2', 'value': 'SS14', 'footprint': ''}],
             'nets': [{'code': '1', 'name': 'VCC', 'nodes': [{'ref': 'D1', 'pin': '1'}, {'ref': 'D2', 'pin': '1'}]}]}
    with pytest.raises(HTTPException) as error:
        app.ensure_thread(a, thread, '프로젝트', react, 'U9')
    assert error.value.status_code == 422
    for _ in range(2):  # 같은 대상의 다음 run은 행을 더 만들지 않는다
        app.ensure_thread(a, thread, '프로젝트', react, 'D1')
    with pytest.raises(HTTPException) as error:
        app.ensure_thread(a, thread, '프로젝트', react, 'D2')
    assert error.value.status_code == 409 and error.value.detail == '대상 부품을 바꾸려면 새 대화를 시작하세요.'
    with pytest.raises(HTTPException) as error:
        app.ensure_thread(b, thread, '프로젝트', react, 'D1')
    assert error.value.status_code == 404
    result = app.message(a, thread, '판정')
    assert result['status'] == 'DONE' and result['can_approve']
    with psycopg.connect(dsn) as conn:
        rows = conn.execute('SELECT c.id, c.netlist, c.connections FROM sojafit_agent.circuits c WHERE c.user_id=%s', (a,)).fetchall()
    assert rows == [(UUID(thread), '', {'components': react['parts'], 'nets': react['nets']})]


def test_react_run_and_resume_go_through_analysis_service(runtime, monkeypatch):
    """React run · 재개 HTTP가 실제 분석 서비스(가짜 그래프)의 checkpoint · 버전으로 이어진다."""
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.api.conversations import repository
    from backend.main import app as api
    app, (a, _), _ = runtime
    thread, run, saved = str(uuid4()), str(uuid4()), {}
    class Repo:
        def get_thread(self, user, thread_id):
            return thread_id, 1, {'parts': [{'ref': 'D1', 'value': 'SS34'}], 'nets': [{'code': '1', 'name': 'VCC', 'nodes': [{'ref': 'D1', 'pin': '1'}]}]}, 'react'
        def start(self, user, thread_id, data): return run, {}
        def get_run(self, user, run_id): return {'id': run, 'thread_id': thread, 'status': saved['status'], 'safe_result': saved['result']}
        def resume(self, *args): pass
        def finish(self, user, thread_id, run_id, status, result): saved.update(status=status, result=result)
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    api.state.conversations = app
    api.dependency_overrides[auth.current_user_id] = lambda: a
    api.dependency_overrides[repository] = lambda: Repo()
    origin = {'Origin': 'http://localhost:8000'}
    try:
        with TestClient(api) as client:
            first = client.post(f'/api/threads/{thread}/runs', headers=origin, json={'question': '조건 질문', 'target_ref': 'D1'})
            assert 'event: requires_input' in first.text and saved['result']['interrupt']['missing'] == ['VIN_MAX']
            done = client.post(f'/api/runs/{run}/resume', headers=origin, json={'answers': {'VIN_MAX': '12'}})
            assert 'event: completed' in done.text and saved['result']['answer'] == '역할상 충분 [1]'
    finally:
        api.dependency_overrides.clear()
        del api.state.conversations
    detail = app.detail(a, thread)
    assert detail['version'] == 1 and detail['can_approve']


def test_other_user_cannot_access_circuit_thread_resume_or_approval(runtime):
    app, (a, b), _ = runtime
    circuit = app.upload(a, 'my.net', NET)
    thread = app.create(a, circuit['id'], 'D1')['id']
    assert app.threads(b) == []
    for call in (lambda: app.create(b, circuit['id'], 'D1'), lambda: app.detail(b, thread),
                 lambda: app.message(b, thread, '판정해줘'), lambda: app.resume(b, thread, {}, '', 0),
                 lambda: app.approve(b, thread, 0)):
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


def test_approval_keeps_original_without_store_copy(runtime, monkeypatch):
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    version = app.message(a, thread, '판정')['version']
    monkeypatch.setattr(app.store, 'put', lambda *args, **kwargs: pytest.fail('approved case written to Store'))
    monkeypatch.setattr(app.store, 'batch', lambda *args, **kwargs: pytest.fail('approved case written to Store'))
    assert app.approve(a, thread, version)['ok']
    assert len(app.memories(a)) == 1


def test_approval_snapshot_preserves_final_conditions_and_is_immutable(runtime):
    app, (a, _), dsn = runtime
    thread = make_thread(app, a)
    pending = app.message(a, thread, '조건 질문', conditions='현재 입력은 아직 모름')
    app.resume(a, thread, {'VIN_MAX': '12'}, '', pending['version'])
    app.approve(a, thread, pending['version'])
    with psycopg.connect(dsn) as conn:
        snapshot = conn.execute('SELECT snapshot FROM sojafit_agent.approvals WHERE thread_id=%s AND version=1', (thread,)).fetchone()[0]
    record = snapshot['context']['input_record']
    assert record['question'] == '조건 질문' and record['conditions'] == '현재 입력은 아직 모름'
    assert record['resumes'] == [{'answers': {'VIN_MAX': '12'}, 'role': ''}]
    app.message(a, thread, '새 질문', conditions='다른 조건 24V')
    app.approve(a, thread, 1)
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT snapshot FROM sojafit_agent.approvals WHERE thread_id=%s AND version=1', (thread,)).fetchone()[0] == snapshot


def test_approval_history_shows_status_and_input_record(runtime, monkeypatch):
    app, (a, _), _ = runtime
    thread = make_thread(app, a)
    app.message(a, thread, '판정')
    app.approve(a, thread, 1)
    app.message(a, thread, '다른 질문')
    monkeypatch.setattr(app.store, 'get', lambda *args: pytest.fail('approval state read from Store'))
    row = app.detail(a, thread)['approvals'][0]
    assert row['version'] == 1 and row['memory_state'] == 'active'
    assert row['input_record']['question'] == '판정'
    assert app.approve(a, thread, row['version'])['ok']


@pytest.mark.parametrize('legacy_snapshot', [False, True])
def test_old_approval_is_idempotent_after_new_question(runtime, legacy_snapshot):
    app, (a, b), dsn = runtime
    thread = make_thread(app, a)
    version = app.message(a, thread, '판정')['version']
    app.approve(a, thread, version)
    with psycopg.connect(dsn) as conn:
        if legacy_snapshot:
            conn.execute("UPDATE sojafit_agent.approvals SET snapshot=snapshot-'part' WHERE thread_id=%s", (thread,))
        original = conn.execute('SELECT snapshot,approved_at FROM sojafit_agent.approvals WHERE thread_id=%s', (thread,)).fetchone()
        if not legacy_snapshot:
            assert original[0]['part'] == 'SS34'
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


def test_new_threads_send_no_approved_cases_to_models(runtime, monkeypatch):
    """[왜] 승인 사례는 장기 기억이 아니라 승인 기록이다(11-09). 새 분석의 모델 입력에 어느 사용자 사례도 들어가지 않는다."""
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.contracts import Plan, Task
    from backend.services import llm
    app, (a, b), _ = runtime
    for user, marker in ((a, 'PRIVATE_A_CASE'), (b, 'PRIVATE_B_CASE')):
        thread = make_thread(app, user)
        app.message(user, thread, '판정', conditions='과거 조건 12V')
        app.graph.update_state(app.config(thread), {'answer': marker})
        app.approve(user, thread, 1)
    prompts = []
    def chat(node, system, user, schema, **kwargs):
        prompts.append(user)
        if node == 'supervisor':
            return Plan(next='tasks', question_type='role', tasks=[Task(id=1, agent='docs', kind='role', goal='explain role')])
        return schema(grade='enough', answer='현재 회로에서 다시 확인합니다 [넷리스트].', memory_refs=[])
    monkeypatch.setattr(llm, 'node_chat', chat)
    app.graph = build_graph(chat=chat, retriever=lambda *args, **kwargs: [], checkpointer=app.saver, store=app.store)
    thread = make_thread(app, a)
    result = app.message(a, thread, 'D1 역할과 과거 사례를 설명해줘')
    assert prompts and all('PRIVATE_' not in prompt and '과거 조건 12V' not in prompt for prompt in prompts)
    assert result['consulted_memories'] == result['referenced_memories'] == []
    assert app.graph.get_state(app.config(thread)).values['approved_memories'] == []
    assert len(app.memories(a)) == 1 and len(app.memories(b)) == 1


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


def test_daily_reservations_are_atomic_across_requests_and_users(runtime, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    app, (a, b), dsn = runtime
    monkeypatch.setenv('ANALYSIS_DAILY_USD', '0.03')
    budgets = [app._budget(a), app._budget(a)]
    def reserve(budget):
        try:
            budget.reserve('x', output_tokens=0)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, budgets)) == [False, True]
    assert reserve(app._budget(b))
    with psycopg.connect(dsn) as conn:
        rows = conn.execute('SELECT reserved_usd FROM sojafit_agent.analysis_usage WHERE user_id IN (%s,%s)', (a, b)).fetchall()
    assert len(rows) == 2 and all(0 < float(row[0]) <= 0.03 for row in rows)


def test_daily_token_caps_per_user_and_service_reject_before_external_call(runtime, monkeypatch):
    """하루 토큰 상한(사용자 200,000 · 서비스 2,000,000): USD 예약과 같은 위쪽 경계 토큰을 두 행에 원자적으로 더하고, 넘으면 호출 전 429다."""
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.api.conversations import repository
    from backend.conversations import memory_service as ms
    from backend.main import app as api
    from backend.services import llm
    app, (a, b), dsn = runtime
    external, per_call = [], 100 + ms.TOKEN_MARGIN + 50
    def node(state):
        for _ in range(2):
            llm._evaluation_budget.get().reserve('x' * 100, output_tokens=50)
            external.append(state['question'])  # 실제 모델 호출 자리. 예약이 막히면 여기에 오지 않는다
        return {'answer': '역할상 충분 [1]', 'judgement': {}}
    graph = StateGraph(AgentState)
    graph.add_node('read', read_input)
    graph.add_node('call', node)
    graph.add_edge(START, 'read')
    graph.add_edge('read', 'call')
    graph.add_edge('call', END)
    app.graph = graph.compile(checkpointer=app.saver)
    today = "(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"
    def usage(user):
        with psycopg.connect(dsn) as conn:
            return conn.execute(f'SELECT reserved_tokens,reserved_usd FROM sojafit_agent.analysis_usage WHERE user_id=%s AND day={today}', (user,)).fetchone()
    def service(value=None):
        with psycopg.connect(dsn) as conn:
            if value is not None:
                conn.execute(f'INSERT INTO sojafit_agent.analysis_service_usage(day,reserved_tokens) VALUES ({today},%s) '
                             'ON CONFLICT(day) DO UPDATE SET reserved_tokens=EXCLUDED.reserved_tokens', (value,))
            return conn.execute(f'SELECT reserved_tokens FROM sojafit_agent.analysis_service_usage WHERE day={today}').fetchone()[0]
    def refused(user, question, text):
        with pytest.raises(HTTPException) as error:
            app.message(user, make_thread(app, user), question)
        assert error.value.status_code == 429 and text in error.value.detail

    # 정상: 호출 2번의 예약 토큰이 사용자 · 서비스 행에 같게 쌓이고, USD 예약은 같은 위쪽 경계(입력 바이트 + 여유)로 계산된다
    before = service(0)
    assert app.message(b, make_thread(app, b), '정상')['status'] == 'DONE'
    tokens, usd = usage(b)
    assert tokens == 2 * per_call and service() == before + 2 * per_call
    assert abs(float(usd) - 2 * ((per_call - 50) * 0.000003 + 50 * 0.000015)) < 1e-9

    # 사용자 상한: 한 번 자리만 남으면 첫 호출만 나가고 둘째는 호출 전 429, 서비스 행은 첫 호출만큼만 오른다
    with psycopg.connect(dsn) as conn:
        conn.execute(f"INSERT INTO sojafit_agent.analysis_usage(user_id,day,next_allowed,reserved_tokens) VALUES (%s,{today},CURRENT_TIMESTAMP,%s)",
                     (a, ms.USER_DAILY_TOKENS - per_call))
    before, external[:] = service(), []
    refused(a, '사용자 상한 도중', '200,000 토큰')
    assert external == ['사용자 상한 도중'] and usage(a)[0] == ms.USER_DAILY_TOKENS and service() == before + per_call
    refused(a, '사용자 상한 입장', '200,000 토큰')  # 다 찬 뒤에는 입장에서 막아 질문 버전도 오르지 않는다
    assert external == ['사용자 상한 도중'] and app.threads(a)[0]['version'] == 0
    app.admission(b)  # 다른 사용자는 막지 않는다

    # 서비스 상한: 사용자 자리는 있어도 서비스 행이 넘치면 429이고, 그 호출의 사용자 행 차감도 되돌린다
    service(ms.SERVICE_DAILY_TOKENS - per_call - 100)
    mine = usage(b)[0]
    refused(b, '서비스 상한 도중', '2,000,000 토큰')
    assert external[-1] == '서비스 상한 도중' and external.count('서비스 상한 도중') == 1
    assert usage(b)[0] == mine + per_call and service() == ms.SERVICE_DAILY_TOKENS - 100
    refused(b, '서비스 상한 입장', '2,000,000 토큰')
    assert '서비스 상한 입장' not in external

    # React run은 스트림 · run 행 전에 공통 오류 429로 끝난다
    class Repo:
        def __getattr__(self, name):
            pytest.fail('token cap must refuse before the repository is used')
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    api.state.conversations = app
    api.dependency_overrides[auth.current_user_id] = lambda: b
    api.dependency_overrides[repository] = lambda: Repo()
    try:
        with TestClient(api) as client:
            response = client.post(f'/api/threads/{uuid4()}/runs', headers={'Origin': 'http://localhost:8000'},
                                   json={'question': '서비스 상한 React', 'target_ref': 'D1'})
    finally:
        api.dependency_overrides.clear()
        del api.state.conversations
    assert response.status_code == 429 and response.json()['error']['code'] == 'LIMIT_EXCEEDED'
    assert '2,000,000 토큰' in response.json()['error']['message']


def test_rate_limit_rejects_before_changing_thread_version(runtime, monkeypatch):
    app, (a, _), _ = runtime
    monkeypatch.setenv('ANALYSIS_MIN_INTERVAL_SECONDS', '60')
    thread = make_thread(app, a)
    app.message(a, thread, '판정')
    with pytest.raises(HTTPException) as error:
        app.message(a, thread, '새 질문')
    assert error.value.status_code == 429
    assert app.detail(a, thread)['version'] == 1


def test_eight_parallel_threads_share_daily_budget_without_mixing(runtime, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.services import llm
    app, (a, b), dsn = runtime
    monkeypatch.setenv('ANALYSIS_DAILY_USD', '0.08')
    threads = [make_thread(app, a) for _ in range(8)]
    barrier, invoke = Barrier(8), app.graph.invoke
    def charged(inputs, config):
        llm._evaluation_budget.get().reserve('x', output_tokens=0)
        return invoke(inputs, config)
    monkeypatch.setattr(app.graph, 'invoke', charged)
    def send(thread):
        barrier.wait(timeout=10)
        try:
            return app.message(a, thread, thread)['status']
        except HTTPException as error:
            assert error.status_code == 429
            return 'LIMIT'
    with ThreadPoolExecutor(max_workers=8) as pool:
        states = list(pool.map(send, threads))
    assert 1 <= states.count('DONE') <= 3 and set(states) <= {'DONE', 'LIMIT'}
    for thread, status in zip(threads, states):
        detail = app.detail(a, thread)
        assert all(m['content'] not in set(threads)-{thread} for m in detail['messages'])
        if status == 'DONE':
            assert detail['status'] == 'DONE' and detail['messages'][0]['content'] == thread
        elif not detail['messages']:
            assert detail['version'] == 0  # 입장 단계의 429는 질문 저장 전에 거부한다.
    with psycopg.connect(dsn) as conn:
        reserved = conn.execute('SELECT reserved_usd FROM sojafit_agent.analysis_usage WHERE user_id=%s', (a,)).fetchone()[0]
    assert 0 < float(reserved) <= 0.08
    assert app.threads(b) == [] and app.memories(b) == []


def test_dump_restore_preserves_owned_memory_and_pending_resume(runtime):
    import json, subprocess, time
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg import sql
    container = os.getenv('TEST_THREAD_BACKUP_CONTAINER')
    if not container:
        pytest.skip('requires explicit disposable local TEST_THREAD_BACKUP_CONTAINER')
    app, (a, b), dsn = runtime
    info = conninfo_to_dict(dsn)
    assert info['host'] in ('127.0.0.1', 'localhost') and info['dbname'].startswith('thread_test')
    ports = json.loads(subprocess.check_output(['docker','inspect','--format','{{json .NetworkSettings.Ports}}',container], timeout=10))
    assert any(p['HostIp']=='127.0.0.1' and p['HostPort']==info['port'] for p in ports['5432/tcp'])
    approved, waiting = make_thread(app, a), make_thread(app, a)
    app.message(a, approved, '승인 원본'); app.approve(a, approved, 1)
    app.message(a, waiting, '조건 질문')
    before = app.memories(a)
    start = time.monotonic()
    dump = subprocess.run(['docker','exec',container,'pg_dump','-U',info['user'],'-d',info['dbname'],'-Fc','--no-owner','--no-acl'], capture_output=True, timeout=30)
    assert dump.returncode == 0 and 0 < len(dump.stdout) < 256*1024*1024
    dump_seconds = time.monotonic()-start
    target = 'thread_restore_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target)))
        try:
            start = time.monotonic()
            restored = subprocess.run(['docker','exec','-i',container,'pg_restore','-U',info['user'],'-d',target,'--no-owner','--no-acl','--exit-on-error'], input=dump.stdout, capture_output=True, timeout=60)
            assert restored.returncode == 0
            restore_seconds = time.monotonic()-start
            copy = Conversations(make_conninfo(dsn, dbname=target), factory=fake_graph)
            try:
                assert copy.memories(a) == before and copy.memories(b) == []
                with pytest.raises(HTTPException) as error:
                    copy.detail(b, approved)
                assert error.value.status_code == 404
                assert copy.detail(a, approved)['approvals'][0]['memory_state'] == 'active'
                assert copy.detail(a, waiting)['status'] == 'WAITING'
                assert copy.resume(a, waiting, {'VIN_MAX':'12'}, '', 1)['status'] == 'DONE'
                copy.approve(a, waiting, 1)
                assert len(copy.memories(a)) == 2
                assert app.detail(a, waiting)['status'] == 'WAITING'
            finally:
                copy.close()
            print(json.dumps({'backup_bytes':len(dump.stdout),'dump_seconds':round(dump_seconds,3),'restore_seconds':round(restore_seconds,3)}))
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(target)))


def test_deadline_rejects_result_and_logs_only_safe_metadata(runtime, caplog):
    from backend.services import llm
    app, (a, _), _ = runtime
    def expire(state):
        budget = llm._evaluation_budget.get()
        budget.started -= budget.max_seconds + 1
        return {'answer': 'synthetic result', 'judgement': {'shown':[{'part':'SS34'}]}}
    graph = StateGraph(AgentState)
    graph.add_node('read', read_input)
    graph.add_node('expire', expire)
    graph.add_edge(START, 'read')
    graph.add_edge('read', 'expire')
    graph.add_edge('expire', END)
    app.graph = graph.compile(checkpointer=app.saver)
    thread = make_thread(app, a)
    with pytest.raises(HTTPException) as error:
        app.message(a, thread, 'PRIVATE_CONDITION', request_id='synthetic-request-id')
    detail=app.detail(a,thread)
    assert detail['status']=='FAILED' and not detail['can_approve'] and not detail['answer']
    with pytest.raises(HTTPException) as denied:
        app.approve(a,thread,1)
    assert denied.value.status_code==409
    assert error.value.status_code == 504
    record = next(r for r in caplog.records if r.name == 'backend.conversations' and r.getMessage() == 'analysis_failed')
    assert record.request_id == 'synthetic-request-id' and record.error_type == 'EvaluationLimitError'
    assert 'PRIVATE_CONDITION' not in str(vars(record))


def test_planned_judge_subgraph_resumes_from_postgres_without_approved_cases(runtime):
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
        assert 'MEMORY_FOR_JUDGE' not in user
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


def test_private_schema_is_closed_to_other_roles(runtime):
    from psycopg import sql
    _, _, dsn = runtime
    with psycopg.connect(dsn) as conn:
        role = 'probe_' + uuid4().hex
        conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
        assert not conn.execute("SELECT has_schema_privilege(current_user,'sojafit_agent','USAGE')").fetchone()[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute('SELECT * FROM sojafit_agent.threads')
        conn.rollback()


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


def test_message_sends_no_approved_cases_and_returns_profile_hints():
    """DB 없이 분석 서비스의 질문 한 번: 승인 사례를 찾지 않고 빈 목록을 넘기며, 그 질문으로 찾은 사용자 사실을 결과에 붙인다."""
    from contextlib import contextmanager
    from types import SimpleNamespace
    from langgraph.store.memory import InMemoryStore
    from backend.conversations.profile import ProfileMemory
    app = Conversations.__new__(Conversations)  # [왜] DB 없이 message의 입력 조립만 본다
    app.mode, seen = 'live', {}
    app.profile = ProfileMemory(InMemoryStore(), indexed=False)
    app.profile.update(7, {'mounting_preference': 'smd'})
    app.profile.update(8, {'affiliation': '다른 사용자 회사'})

    class Conn:
        def execute(self, *args): return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)
        @contextmanager
        def transaction(self): yield
    @contextmanager
    def locked(user, thread):
        yield Conn(), {'version': 0, 'target': 'D1', 'filename': 'my.net', 'connections': {'components': [{'ref': 'D1', 'value': 'SS34'}]}}
    app.locked, app._reconcile, app._budget, app._purge_expired = locked, lambda conn, row: None, lambda user: 'budget', lambda: None
    app.graph = SimpleNamespace(get_state=lambda config: SimpleNamespace(next=()))
    app.memories = lambda *args, **kwargs: pytest.fail('approved cases looked up for a new analysis')
    app._invoke = lambda conn, thread, inputs, budget, request_id='': seen.update(inputs)
    app.detail = lambda user, thread, hints=(): {'profile_hints': list(hints)}
    result = app.message(7, 'thread-1', 'SMD로 바꿀 수 있나요?')
    assert seen['approved_memories'] == []
    assert result['profile_hints'] == [{'kind': 'mounting_preference', 'value': 'smd', 'text': '이 사용자는 SMD 실장을 선호한다.'}]


def test_profile_hints_are_owned_and_follow_update_and_delete(runtime):
    """색인 없이(키 없음) 실제 Store: 질문 결과의 참고(내 설정)는 자기 사실만, 고친 값 · 지운 칸을 바로 따른다."""
    app, (a, b), _ = runtime
    app.profile.update(a, {'mounting_preference': 'smd', 'affiliation': 'A회사'})
    app.profile.update(b, {'affiliation': 'B회사'})
    thread, other = make_thread(app, a), make_thread(app, b)
    assert {h['value'] for h in app.message(a, thread, '판정')['profile_hints']} == {'smd', 'A회사'}
    assert [h['value'] for h in app.message(b, other, '판정')['profile_hints']] == ['B회사']
    app.profile.update(a, {'mounting_preference': 'through_hole'})
    app.profile.delete(a, 'affiliation')
    pending = app.message(a, thread, '조건 질문')
    expected = [{'kind': 'mounting_preference', 'value': 'through_hole', 'text': '이 사용자는 스루홀 실장을 선호한다.'}]
    assert pending['profile_hints'] == expected
    assert app.resume(a, thread, {'VIN_MAX': '12'}, '', pending['version'])['profile_hints'] == expected
    assert app.detail(a, thread)['profile_hints'] == []  # GET 상세는 다시 찾지 않는다
    assert app.profile.facts(a)[0]['version'] == 2 and [f['value'] for f in app.profile.facts(b)] == ['B회사']
    app.profile.delete(a)
    assert app.message(a, thread, '판정')['profile_hints'] == [] and app.profile.facts(b)


def test_indexed_profile_ranks_paraphrase_reembeds_and_isolates_users(runtime, monkeypatch):
    """pgvector 색인 + 가짜 Voyage: 다른 말로 물어도 맞는 사실이 먼저, 고치면 새 벡터, 지우면 벡터도 사라지고, 사용자끼리 섞이지 않는다."""
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app as api
    from backend.services import llm
    _, (a, b), dsn = runtime
    with psycopg.connect(dsn) as conn:
        if not conn.execute("SELECT to_regclass('sojafit_agent.store_vectors')").fetchone()[0]:
            pytest.skip('requires the vector extension in the test DB before setup')
    concepts, kinds = [('smd', '표면실장'), ('스루홀', '리드 부품'), ('구매', '발주'), ('소속', '회사')], []
    def fake(texts, input_type):
        kinds.append(input_type)
        return [[0.01 + sum(t.lower().count(w) for w in concepts[i]) if i < len(concepts) else 0.01 for i in range(1024)] for t in texts]
    monkeypatch.setattr(llm, 'voyage_embed', fake)
    monkeypatch.setenv('VOYAGE_API_KEY', 'test-not-used'); monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    app = Conversations(dsn, factory=fake_graph)
    try:
        assert app.profile.indexed
        app.profile.update(a, {'affiliation': '한빛전자', 'job_role': 'purchasing', 'mounting_preference': 'smd'})
        app.profile.update(b, {'affiliation': '다른회사', 'mounting_preference': 'through_hole'})
        assert set(kinds) == {'document'}
        kinds.clear()
        assert app.profile.facts(a, '표면실장 부품으로 바꿀 수 있나요?')[0]['kind'] == 'mounting_preference'
        assert app.profile.facts(a, '발주 담당자 기준으로')[0]['kind'] == 'job_role'
        assert app.profile.facts(a, '어느 회사인가요')[0]['kind'] == 'affiliation'
        assert set(kinds) == {'query'}
        thread = make_thread(app, a)
        hints = app.message(a, thread, '표면실장으로 바꿔도 되나요')['profile_hints']
        assert hints[0]['value'] == 'smd' and all(h['value'] not in ('다른회사', 'through_hole') for h in hints)
        api.state.conversations = app
        api.dependency_overrides[auth.current_user_id] = lambda: b
        client = TestClient(api)
        found = client.get('/api/me/memory', params={'q': '한빛전자 구매 표면실장'}).json()
        assert {f['value'] for f in found} == {'다른회사', 'through_hole'}
        api.dependency_overrides[auth.current_user_id] = lambda: a
        updated = client.patch('/api/me/memory', json={'mounting_preference': 'through_hole'}, headers={'Origin': 'http://localhost:8000'})
        assert updated.status_code == 200
        top = client.get('/api/me/memory', params={'q': '리드 부품도 괜찮나요'}).json()[0]
        assert top['kind'] == 'mounting_preference' and top['version'] == 2 and top['text'] == '이 사용자는 스루홀 실장을 선호한다.'
        assert client.delete('/api/me/memory', params={'kind': 'mounting_preference'}, headers={'Origin': 'http://localhost:8000'}).status_code == 204
        assert 'mounting_preference' not in {f['kind'] for f in client.get('/api/me/memory', params={'q': '리드 부품'}).json()}
        assert all(h['kind'] != 'mounting_preference' for h in app.message(a, thread, '리드 부품으로')['profile_hints'])
        with psycopg.connect(dsn) as conn:
            rows = conn.execute("SELECT prefix, key FROM sojafit_agent.store_vectors WHERE prefix IN (%s,%s) ORDER BY prefix, key",
                                (f'{a}.profile', f'{b}.profile')).fetchall()
        assert rows == sorted([(f'{a}.profile', 'affiliation'), (f'{a}.profile', 'job_role'),
                               (f'{b}.profile', 'affiliation'), (f'{b}.profile', 'mounting_preference')])
    finally:
        api.dependency_overrides.clear()
        if hasattr(api.state, 'conversations'):
            del api.state.conversations
        app.close()
