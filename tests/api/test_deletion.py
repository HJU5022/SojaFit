"""격리 PostgreSQL에서 삭제 범위를 확인한다(SPEC 8.5 "보관 · 삭제").

- 프로젝트 삭제: React 업무 행과 같은 UUID의 분석 thread · checkpoint · 메시지 · 분석 사건을 지우고, 같은 사용자의 다른 기록과 다른 사용자는 남긴다.
- 탈퇴(`DELETE /api/me`): 기록을 먼저, 계정을 마지막에 지운다. Store namespace 전부, 다시 요청하면 이어서 지움, 진행 중 분석과 서로 409, 관리자 409.
DB 시험은 `TEST_THREAD_DATABASE_URL`(public에 React 표 db/018~020이 있는 격리 DB)이 있을 때만 돈다. 외부 모델 · 원격 DB 호출은 없다.
"""
import os
import threading
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from langgraph.graph import END, START, StateGraph
from psycopg.types.json import Jsonb

from backend import auth
from backend.conversations.memory_service import Conversations, initialize
from backend.graph.nodes import read_input
from backend.graph.state import AgentState

NET = '(export (components (comp (ref "D1") (value "SS34"))) (nets (net (name "VCC") (node (ref "D1") (pin "1")))))'
PARTS = {'parts': [{'ref': 'D1', 'value': 'SS34'}], 'nets': [{'code': '1', 'name': 'VCC', 'nodes': [{'ref': 'D1', 'pin': '1'}]}]}
ORIGIN = {'Origin': 'http://testserver'}
GATE = {}  # 질문 '대기'가 오면 started를 켜고 release를 기다린다(진행 중 분석 흉내)


def fake_graph(saver, store):
    def judge(state):
        if '대기' in state['question']:
            GATE['started'].set()
            assert GATE['release'].wait(10)
        return {'answer': '역할상 충분 [1]', 'judgement': {'shown': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]}}
    graph = StateGraph(AgentState)
    graph.add_node('read', read_input)
    graph.add_node('judge', judge)
    graph.add_edge(START, 'read')
    graph.add_edge('read', 'judge')
    graph.add_edge('judge', END)
    return graph.compile(checkpointer=saver, store=store)


@pytest.fixture
def world(monkeypatch):
    dsn = os.getenv('TEST_THREAD_DATABASE_URL')
    if not dsn:
        pytest.skip('requires isolated TEST_THREAD_DATABASE_URL')
    with psycopg.connect(dsn) as conn:
        if not conn.execute("SELECT to_regclass('public.projects')").fetchone()[0]:
            pytest.skip('requires React tables (db/018~020) in the public schema of TEST_THREAD_DATABASE_URL')
    for key, value in {'ANALYSIS_MIN_INTERVAL_SECONDS': '0', 'DATABASE_URL': dsn, 'AUTH_ORIGIN': 'http://testserver',
                       'AUTH_SECRET': 'isolated-deletion-test-secret-32-bytes'}.items():
        monkeypatch.setenv(key, value)
    initialize(dsn)
    with psycopg.connect(dsn) as conn:
        users = [conn.execute("INSERT INTO public.users(login_id,password_hash,role) VALUES (%s,'test-only',%s) RETURNING id",
                              (f'deletion-{uuid4()}@example.test', role)).fetchone()[0] for role in ('user', 'user', 'admin')]
    app = Conversations(dsn, factory=fake_graph)
    try:
        yield app, users, dsn
    finally:
        app.close()
        with psycopg.connect(dsn) as conn:
            for user in users:
                conn.execute('DELETE FROM sojafit_agent.store WHERE prefix LIKE %s OR prefix LIKE %s OR prefix=%s',
                             (f'{user}.%', f'{user}0.%', f'memories.{user}'))
                conn.execute('DELETE FROM sojafit_agent.threads WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM sojafit_agent.circuits WHERE user_id=%s', (user,))
                conn.execute('DELETE FROM public.users WHERE id=%s', (user,))
            conn.execute("DELETE FROM sojafit_agent.analysis_service_usage WHERE day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date")


def seed(app, dsn, user, projects=1):
    """사용자 하나의 프로젝트(React 업무 행 전부 + 같은 UUID 분석 기록), /api/threads 직접 thread, 사실 3칸, 옛 승인 사본을 만든다."""
    made = {'projects': [], 'threads': []}
    with psycopg.connect(dsn) as conn:
        for index in range(projects):
            project = conn.execute("INSERT INTO public.projects(user_id,name,source_kind) VALUES (%s,%s,'upload') RETURNING id",
                                   (user, f'회로 {index}')).fetchone()[0]
            conn.execute("INSERT INTO public.circuits(project_id,connections,source_sha256,parser_version) VALUES (%s,%s,%s,'test')",
                         (project, Jsonb(PARTS), '0' * 64))
            thread, run = str(uuid4()), str(uuid4())
            conn.execute('INSERT INTO public.threads(id,project_id) VALUES (%s,%s)', (thread, project))
            conn.execute("INSERT INTO public.runs(id,thread_id,status) VALUES (%s,%s,'completed')", (run, thread))
            message = conn.execute("INSERT INTO public.messages(thread_id,run_id,role,content) VALUES (%s,%s,'assistant','ok') RETURNING id",
                                   (thread, run)).fetchone()[0]
            approval = conn.execute("INSERT INTO public.approvals(user_id,message_id,snapshot) VALUES (%s,%s,'{}') RETURNING id",
                                    (user, message)).fetchone()[0]
            conn.execute("INSERT INTO public.quotes(user_id,approval_id,part_number,quantity,snapshot) VALUES (%s,%s,'SS34',1,'{}')", (user, approval))
            conn.execute("INSERT INTO public.approved_cases(user_id,approval_id,snapshot) VALUES (%s,%s,'{}')", (user, approval))
            made['projects'].append(project)
            made['threads'].append(thread)
    for thread in made['threads']:
        app.ensure_thread(user, thread, '회로', PARTS, 'D1')
        app.message(user, thread, '판정')  # checkpoint · 분석 메시지 · 분석 사건 · 하루 사용량이 생긴다
        app.approve(user, thread, 1)
    made['direct'] = app.create(user, app.upload(user, 'direct.net', NET)['id'], 'D1')['id']
    app.message(user, made['direct'], '판정')
    app.profile.update(user, {'affiliation': '시험 소속', 'job_role': 'design', 'mounting_preference': 'smd'})
    app.store.put(('memories', str(user)), 'old', {'answer': '옛 승인 사본'})
    return made


def remaining(dsn, user, threads):
    """사용자 하나와 그 대화 · 분석 thread UUID들에 남은 행 수(표별)."""
    queries = {
        'users': 'SELECT count(*) FROM public.users WHERE id=%(u)s',
        'sessions': 'SELECT count(*) FROM public.auth_sessions WHERE user_id=%(u)s',
        'projects': 'SELECT count(*) FROM public.projects WHERE user_id=%(u)s',
        'react_threads': 'SELECT count(*) FROM public.threads WHERE id = ANY(%(t)s::uuid[])',
        'runs': 'SELECT count(*) FROM public.runs WHERE thread_id = ANY(%(t)s::uuid[])',
        'react_messages': 'SELECT count(*) FROM public.messages WHERE thread_id = ANY(%(t)s::uuid[])',
        'approvals': 'SELECT count(*) FROM public.approvals WHERE user_id=%(u)s',
        'quotes': 'SELECT count(*) FROM public.quotes WHERE user_id=%(u)s',
        'approved_cases': 'SELECT count(*) FROM public.approved_cases WHERE user_id=%(u)s',
        'analysis_threads': 'SELECT count(*) FROM sojafit_agent.threads WHERE id = ANY(%(t)s::uuid[])',
        'analysis_circuits': 'SELECT count(*) FROM sojafit_agent.circuits WHERE user_id=%(u)s',
        'analysis_messages': 'SELECT count(*) FROM sojafit_agent.messages WHERE thread_id = ANY(%(t)s::uuid[])',
        'analysis_approvals': 'SELECT count(*) FROM sojafit_agent.approvals WHERE thread_id = ANY(%(t)s::uuid[])',
        'analysis_events': 'SELECT count(*) FROM sojafit_agent.analysis_events WHERE thread_id = ANY(%(t)s::uuid[])',
        'analysis_usage': 'SELECT count(*) FROM sojafit_agent.analysis_usage WHERE user_id=%(u)s',
        'checkpoints': 'SELECT count(*) FROM sojafit_agent.checkpoints WHERE thread_id = ANY(%(t)s)',
        'checkpoint_blobs': 'SELECT count(*) FROM sojafit_agent.checkpoint_blobs WHERE thread_id = ANY(%(t)s)',
        'checkpoint_writes': 'SELECT count(*) FROM sojafit_agent.checkpoint_writes WHERE thread_id = ANY(%(t)s)',
        'store': 'SELECT count(*) FROM sojafit_agent.store WHERE prefix LIKE %(p)s OR prefix=%(m)s',
    }
    params = {'u': user, 't': [str(t) for t in threads], 'p': f'{user}.%', 'm': f'memories.{user}'}
    with psycopg.connect(dsn) as conn:
        return {name: conn.execute(query, params).fetchone()[0] for name, query in queries.items()}


def login(dsn, user):
    """시험 사용자의 세션 쿠키를 붙인 TestClient(실제 세션 검증을 거친다)."""
    from backend.main import app as api
    token = f'deletion-session-{uuid4()}'
    with psycopg.connect(dsn) as conn:
        conn.execute("INSERT INTO public.auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')",
                     (auth.session_token_hash(token), user))
    client = TestClient(api, raise_server_exceptions=False)
    client.cookies.set(auth.COOKIE, token)
    return client


@pytest.fixture
def served(world):
    from backend.main import app as api
    api.state.conversations = world[0]
    try:
        yield world
    finally:
        del api.state.conversations


def test_project_delete_removes_its_react_and_analysis_records_only(world):
    from backend.api.projects import delete_owned_with_checkpoints
    app, (a, b, _), dsn = world
    mine, other = seed(app, dsn, a, projects=2), seed(app, dsn, b)
    gone, kept = mine['threads'][0], [mine['threads'][1], mine['direct']]
    before_kept, before_other = remaining(dsn, a, kept), remaining(dsn, b, other['threads'] + [other['direct']])
    assert remaining(dsn, a, [gone])['checkpoints'] > 0 and remaining(dsn, a, [gone])['analysis_events'] > 0
    delete_owned_with_checkpoints(a, mine['projects'][0])
    after = remaining(dsn, a, [gone])
    for name in ('react_threads', 'runs', 'react_messages', 'analysis_threads', 'analysis_messages', 'analysis_approvals',
                 'analysis_events', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
        assert after[name] == 0, name
    kept_after = remaining(dsn, a, kept)
    assert kept_after['projects'] == 1 and kept_after['quotes'] == 1 and kept_after['analysis_circuits'] == 2  # 남은 프로젝트 · 직접 thread 회로
    assert {k: v for k, v in kept_after.items() if k not in ('projects', 'approvals', 'quotes', 'approved_cases', 'analysis_circuits')} == \
           {k: v for k, v in before_kept.items() if k not in ('projects', 'approvals', 'quotes', 'approved_cases', 'analysis_circuits')}
    assert remaining(dsn, b, other['threads'] + [other['direct']]) == before_other
    with pytest.raises(Exception):  # 다른 사용자의 프로젝트는 없는 것과 같다
        delete_owned_with_checkpoints(a, other['projects'][0])
    assert remaining(dsn, b, other['threads'] + [other['direct']]) == before_other


def test_account_delete_removes_everything_of_user_and_leaves_others(served):
    app, (a, b, _), dsn = served
    mine, other = seed(app, dsn, a, projects=2), seed(app, dsn, b)
    app.store.put((f'{a}0', 'profile'), 'affiliation', {'kind': 'affiliation'})  # 사용자 id가 접두사인 다른 namespace
    threads = mine['threads'] + [mine['direct']]
    before_other = remaining(dsn, b, other['threads'] + [other['direct']])
    client = login(dsn, a)
    assert client.delete('/api/me').status_code == 403  # Origin 없음: 아무것도 지우지 않는다
    assert remaining(dsn, a, threads)['analysis_threads'] == 3
    response = client.delete('/api/me', headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json() == {'deleted': {'analysis_threads': 3, 'analysis_circuits': 3, 'checkpoints': response.json()['deleted']['checkpoints'],
                                           'memory_items': 4, 'projects': 2, 'quotes': 2, 'account': 1}}
    assert response.json()['deleted']['checkpoints'] > 0
    assert set(remaining(dsn, a, threads).values()) == {0}
    assert 'sojafit_session=""' in response.headers['set-cookie'] or 'Max-Age=0' in response.headers['set-cookie']
    assert client.get('/api/auth/me').status_code == 401
    assert remaining(dsn, b, other['threads'] + [other['direct']]) == before_other
    assert app.store.get((f'{a}0', 'profile'), 'affiliation') is not None


def test_account_delete_rerun_after_partial_failure_finishes(served, monkeypatch):
    app, (a, _, _), dsn = served
    mine = seed(app, dsn, a)
    threads, batch, calls = mine['threads'] + [mine['direct']], app.store.batch, []
    def flaky(ops):
        calls.append(len(ops))
        if len(calls) == 1:
            raise psycopg.OperationalError('synthetic store outage')
        return batch(ops)
    monkeypatch.setattr(app.store, 'batch', flaky)
    client = login(dsn, a)
    failed = client.delete('/api/me', headers=ORIGIN)
    assert failed.status_code == 503 and failed.json()['error']['message'].startswith('계정 삭제를 끝내지 못했습니다.')
    half = remaining(dsn, a, threads)
    assert half['users'] == 1 and half['sessions'] == 1 and half['store'] == 4  # 계정은 남아 다시 요청할 수 있다
    assert half['analysis_threads'] == half['checkpoints'] == 0  # 앞 단계(분석 기록)는 이미 지웠다
    done = client.delete('/api/me', headers=ORIGIN)
    assert done.status_code == 200
    assert done.json()['deleted'] == {'analysis_threads': 0, 'analysis_circuits': 0, 'checkpoints': 0, 'memory_items': 4,
                                      'projects': 1, 'quotes': 1, 'account': 1}
    assert set(remaining(dsn, a, threads).values()) == {0}


def test_account_delete_and_running_analysis_exclude_each_other(served, monkeypatch):
    app, (a, b, _), dsn = served
    mine = seed(app, dsn, a)
    client = login(dsn, a)
    # 1) 분석이 도는 동안 탈퇴는 409이고 아무것도 지우지 않는다
    GATE.update(started=threading.Event(), release=threading.Event())
    running = threading.Thread(target=app.message, args=(a, mine['direct'], '대기'))
    running.start()
    try:
        assert GATE['started'].wait(10)
        busy = client.delete('/api/me', headers=ORIGIN)
        assert busy.status_code == 409 and busy.json()['error']['code'] == 'CONFLICT'
    finally:
        GATE['release'].set()
        running.join(10)
    assert remaining(dsn, a, mine['threads'])['analysis_threads'] == 1
    # 2) 탈퇴가 도는 동안 그 사용자의 새 분석 · 재개 입장 · 대화 연결 · 설정 저장은 409, 다른 사용자는 막지 않는다
    from backend.conversations import memory_service
    entered, release, delete_records = threading.Event(), threading.Event(), memory_service.delete_analysis_threads
    def slow_records(conn, user, ids=None):  # 배타 잠금을 잡은 뒤, 기록을 지우기 전에 멈춘다
        entered.set()
        assert release.wait(10)
        return delete_records(conn, user, ids)
    monkeypatch.setattr(memory_service, 'delete_analysis_threads', slow_records)
    result = {}
    deleting = threading.Thread(target=lambda: result.update(response=client.delete('/api/me', headers=ORIGIN)))
    deleting.start()
    try:
        assert entered.wait(10)
        for attempt in (lambda: app.message(a, mine['direct'], '판정'), lambda: app.admission(a), lambda: app.upload(a, 'new.net', NET),
                        lambda: app.ensure_thread(a, str(uuid4()), '회로', PARTS, 'D1'), lambda: app.account_writer(a).__enter__()):
            with pytest.raises(HTTPException) as error:
                attempt()
            assert error.value.status_code == 409 and error.value.detail == '계정 삭제를 처리하는 중입니다.'
        app.admission(b)
    finally:
        release.set()
        deleting.join(10)
    assert result['response'].status_code == 200
    assert set(remaining(dsn, a, mine['threads'] + [mine['direct']]).values()) == {0}


def test_admin_cannot_self_delete(served):
    app, (_, _, admin), dsn = served
    client = login(dsn, admin)
    response = client.delete('/api/me', headers=ORIGIN)
    assert response.status_code == 409 and response.json()['error']['code'] == 'CONFLICT'
    assert remaining(dsn, admin, [])['users'] == 1 and client.get('/api/auth/me').status_code == 200
    with pytest.raises(HTTPException) as error:  # 계정 단계도 관리자를 거절한다(역할이 도중에 바뀌어도)
        auth.delete_account(admin)
    assert error.value.status_code == 409
