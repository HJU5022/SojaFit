"""격리 PostgreSQL에서 삭제 범위를 확인한다(SPEC 8.5 "보관 · 삭제").

- 프로젝트 삭제: React 업무 행과 같은 UUID의 분석 thread(FK cascade) · checkpoint(삭제 트리거) · 메시지 · 분석 사건을 지우고, 같은 사용자의 다른 기록과 다른 사용자는 남긴다.
- DB 규칙(028): 분석 thread는 화면 thread에 FK로 묶이고, 화면 thread · 사용자 행이 어떤 경로로 지워져도 분석 기록과 checkpoint가 고아로 남지 않는다.
- 탈퇴(`DELETE /api/me`): 기록을 먼저, 계정을 마지막에 지운다. Store namespace 전부, 다시 요청하면 이어서 지움, 진행 중 분석과 서로 409, 관리자 409.
DB 시험은 `TEST_THREAD_DATABASE_URL`(tests/db_schema.py의 apply_service_schema(agent=True)를 적용한 격리 DB)이 있을 때만 돈다. 외부 모델 · 원격 DB 호출은 없다.
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
            pytest.skip('requires service tables (tests/db_schema.py apply_service_schema(agent=True)) in the public schema of TEST_THREAD_DATABASE_URL')
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
                conn.execute('DELETE FROM public.users WHERE id=%s', (user,))
            conn.execute("DELETE FROM sojafit_agent.analysis_service_usage WHERE day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date")


def seed(app, dsn, user, projects=1):
    """사용자 하나의 프로젝트(React 업무 행 전부 + 같은 UUID 분석 기록), 사실 3칸, 옛 승인 사본을 만든다.

    [왜] 분석 thread는 화면 thread에 FK라 화면 행(projects → circuits → threads)을 먼저 만들고 ensure_thread가 분석 쪽을 잇는다. 직접 thread(upload · create)는 지웠다."""
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
            approval = conn.execute("INSERT INTO public.approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) "
                                    "VALUES (%s,%s,'{}','SS34','IDENTICAL','SS34') RETURNING id", (user, message)).fetchone()[0]
            conn.execute("INSERT INTO public.quotes(user_id,approval_id,part_number,quantity) VALUES (%s,%s,'SS34',1)", (user, approval))
            conn.execute("INSERT INTO public.approved_cases(user_id,approval_id) VALUES (%s,%s)", (user, approval))
            made['projects'].append(project)
            made['threads'].append(thread)
    for thread in made['threads']:
        app.ensure_thread(user, thread, '회로', PARTS, 'D1')
        app.message(user, thread, '판정')  # checkpoint · 분석 메시지 · 분석 사건 · 하루 사용량이 생긴다
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
        'analysis_messages': 'SELECT count(*) FROM sojafit_agent.messages WHERE thread_id = ANY(%(t)s::uuid[])',
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
    gone, kept = mine['threads'][0], [mine['threads'][1]]
    before_kept, before_other = remaining(dsn, a, kept), remaining(dsn, b, other['threads'])
    assert remaining(dsn, a, [gone])['checkpoints'] > 0 and remaining(dsn, a, [gone])['analysis_events'] > 0
    delete_owned_with_checkpoints(a, mine['projects'][0])
    after = remaining(dsn, a, [gone])
    for name in ('react_threads', 'runs', 'react_messages', 'analysis_threads', 'analysis_messages',
                 'analysis_events', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
        assert after[name] == 0, name
    kept_after = remaining(dsn, a, kept)
    assert kept_after['projects'] == 1 and kept_after['quotes'] == 1 and kept_after['analysis_threads'] == 1  # 남은 프로젝트의 분석 thread
    assert {k: v for k, v in kept_after.items() if k not in ('projects', 'approvals', 'quotes', 'approved_cases')} == \
           {k: v for k, v in before_kept.items() if k not in ('projects', 'approvals', 'quotes', 'approved_cases')}
    assert remaining(dsn, b, other['threads']) == before_other
    with pytest.raises(Exception):  # 다른 사용자의 프로젝트는 없는 것과 같다
        delete_owned_with_checkpoints(a, other['projects'][0])
    assert remaining(dsn, b, other['threads']) == before_other


def test_account_delete_removes_everything_of_user_and_leaves_others(served):
    app, (a, b, _), dsn = served
    mine, other = seed(app, dsn, a, projects=2), seed(app, dsn, b)
    app.store.put((f'{a}0', 'profile'), 'affiliation', {'kind': 'affiliation'})  # 사용자 id가 접두사인 다른 namespace
    threads = mine['threads']
    before_other = remaining(dsn, b, other['threads'])
    client = login(dsn, a)
    assert client.delete('/api/me').status_code == 403  # Origin 없음: 아무것도 지우지 않는다
    assert remaining(dsn, a, threads)['analysis_threads'] == 2
    response = client.delete('/api/me', headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert response.json() == {'deleted': {'analysis_threads': 2, 'analysis_circuits': 0, 'checkpoints': response.json()['deleted']['checkpoints'],
                                           'memory_items': 4, 'projects': 2, 'quotes': 2, 'account': 1}}
    assert response.json()['deleted']['checkpoints'] > 0
    assert set(remaining(dsn, a, threads).values()) == {0}
    assert 'sojafit_session=""' in response.headers['set-cookie'] or 'Max-Age=0' in response.headers['set-cookie']
    assert client.get('/api/auth/me').status_code == 401
    assert remaining(dsn, b, other['threads']) == before_other
    assert app.store.get((f'{a}0', 'profile'), 'affiliation') is not None


def test_account_delete_rerun_after_partial_failure_finishes(served, monkeypatch):
    app, (a, _, _), dsn = served
    mine = seed(app, dsn, a)
    threads, batch, calls = mine['threads'], app.store.batch, []
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
    running = threading.Thread(target=app.message, args=(a, mine['threads'][0], '대기'))
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
        for attempt in (lambda: app.message(a, mine['threads'][0], '판정'), lambda: app.admission(a),
                        lambda: app.ensure_thread(a, str(uuid4()), '회로', PARTS, 'D1'), lambda: app.account_writer(a).__enter__()):
            with pytest.raises(HTTPException) as error:
                attempt()
            assert error.value.status_code == 409 and error.value.detail == '계정 삭제를 처리하는 중입니다.'
        app.admission(b)
    finally:
        release.set()
        deleting.join(10)
    assert result['response'].status_code == 200
    assert set(remaining(dsn, a, mine['threads']).values()) == {0}


def test_admin_cannot_self_delete(served):
    app, (_, _, admin), dsn = served
    client = login(dsn, admin)
    response = client.delete('/api/me', headers=ORIGIN)
    assert response.status_code == 409 and response.json()['error']['code'] == 'CONFLICT'
    assert remaining(dsn, admin, [])['users'] == 1 and client.get('/api/auth/me').status_code == 200
    with pytest.raises(HTTPException) as error:  # 계정 단계도 관리자를 거절한다(역할이 도중에 바뀌어도)
        auth.delete_account(admin)
    assert error.value.status_code == 409


def age(dsn, days, projects=(), threads=()):
    """프로젝트(React 행 전부)와 분석 thread(메시지 · 사건)의 활동 시각을 days일 전으로 옮긴다."""
    when = {'w': days}
    with psycopg.connect(dsn) as conn:
        for project in projects:
            when['p'] = project
            conn.execute("UPDATE public.projects SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day', updated_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' WHERE id=%(p)s", when)
            conn.execute("UPDATE public.threads SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' WHERE project_id=%(p)s", when)
            conn.execute("UPDATE public.runs r SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day', updated_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' "
                         "FROM public.threads t WHERE t.id=r.thread_id AND t.project_id=%(p)s", when)
            conn.execute("UPDATE public.approvals a SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' FROM public.messages m JOIN public.threads t ON t.id=m.thread_id "
                         "WHERE m.id=a.message_id AND t.project_id=%(p)s", when)
            conn.execute("UPDATE public.quotes q SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' FROM public.approvals a JOIN public.messages m ON m.id=a.message_id "
                         "JOIN public.threads t ON t.id=m.thread_id WHERE a.id=q.approval_id AND t.project_id=%(p)s", when)
        when['t'] = [str(t) for t in threads]
        conn.execute("UPDATE sojafit_agent.threads SET created_at=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' WHERE id = ANY(%(t)s::uuid[])", when)
        for table, column in (('messages', 'created_at'), ('analysis_events', 'created_at')):
            conn.execute(f"UPDATE sojafit_agent.{table} SET {column}=CURRENT_TIMESTAMP - %(w)s * INTERVAL '1 day' WHERE thread_id = ANY(%(t)s::uuid[])", when)


def test_purge_inactive_projects_deletes_only_past_60_days_in_bounded_batches(world):
    app, (a, b, _), dsn = world
    mine, other = seed(app, dsn, a, projects=3), seed(app, dsn, b)
    old, recent_run = mine['projects'][:2], mine['threads'][2]
    age(dsn, 61, projects=mine['projects'], threads=mine['threads'])  # 셋째 프로젝트는 아래에서 run만 어제로
    age(dsn, 59, projects=other['projects'], threads=other['threads'])  # 60일이 안 됨
    with psycopg.connect(dsn) as conn:
        conn.execute("UPDATE public.runs SET updated_at=CURRENT_TIMESTAMP - INTERVAL '1 day' WHERE thread_id=%s", (recent_run,))
    before_other = remaining(dsn, b, other['threads'])
    def projects_left():
        with psycopg.connect(dsn) as conn:
            return {row[0] for row in conn.execute('SELECT id FROM public.projects WHERE id = ANY(%s)', (mine['projects'],))}
    with psycopg.connect(dsn, autocommit=True) as conn:
        first = conn.execute('SELECT sojafit_agent.purge_inactive_projects(60, 1)').fetchone()[0]
        assert 1 <= first <= 3 and len(set(old) & projects_left()) >= 1  # 한 번에 단계마다 1개까지만
        for _ in range(5):
            if not conn.execute('SELECT sojafit_agent.purge_inactive_projects(60, 1)').fetchone()[0]:
                break
    assert projects_left() == {mine['projects'][2]}  # 이름 변경은 61일 전이어도 어제 run이 있으면 남는다
    gone = remaining(dsn, a, mine['threads'][:2])
    for name in ('react_threads', 'runs', 'react_messages', 'analysis_threads', 'analysis_messages', 'analysis_events', 'checkpoints', 'checkpoint_writes'):
        assert gone[name] == 0, name
    assert remaining(dsn, a, [recent_run])['analysis_threads'] == 1 and remaining(dsn, a, [recent_run])['checkpoints'] > 0
    assert remaining(dsn, b, other['threads']) == before_other
    assert remaining(dsn, a, [])['store'] == 4  # 사용자 사실은 자동 만료가 없다


def test_purge_log_records_deletes_only_past_30_days_and_keeps_active_locks(world):
    app, (a, _, _), dsn = world
    thread = seed(app, dsn, a)['threads'][0]
    key = lambda: uuid4().hex + uuid4().hex
    signup_old, signup_new, login_old, login_locked, login_new, ip_old, ip_locked, ip_new = (key() for _ in range(8))
    ago = "CURRENT_TIMESTAMP - %s * INTERVAL '1 day'"
    day = "(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - %s"
    with psycopg.connect(dsn) as conn:
        for days in (31, 31, 31, 29):
            conn.execute(f"INSERT INTO sojafit_agent.analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery,created_at) "
                         f"VALUES (%s,%s,1,%s,'live','DONE',1,'[]','t','skipped',{ago})", (uuid4(), thread, f'log-{days}', days))
        for days in (31, 29):
            conn.execute(f"INSERT INTO sojafit_agent.analysis_usage(user_id,day,next_allowed) VALUES (%s,{day},CURRENT_TIMESTAMP)", (a, days))
            conn.execute(f'INSERT INTO sojafit_agent.analysis_service_usage(day) VALUES ({day}) ON CONFLICT DO NOTHING', (days,))
        conn.execute(f'INSERT INTO public.auth_signup_attempts(ip_hash,day) VALUES (%s,{day}),(%s,{day})', (signup_old, 31, signup_new, 0))
        for table, column, old, locked, new in (('auth_login_attempts', 'login_hash', login_old, login_locked, login_new),
                                                ('auth_login_ip_attempts', 'ip_hash', ip_old, ip_locked, ip_new)):
            conn.execute(f"INSERT INTO public.{table}({column},failed_count,window_started_at,locked_until) VALUES "
                         f"(%s,3,{ago},NULL),(%s,5,{ago},CURRENT_TIMESTAMP + INTERVAL '10 minutes'),(%s,1,CURRENT_TIMESTAMP,NULL)",
                         (old, 31, locked, 31, new))
    def left():
        with psycopg.connect(dsn) as conn:
            return {
                'events': [r[0] for r in conn.execute('SELECT request_id FROM sojafit_agent.analysis_events WHERE thread_id=%s AND request_id LIKE %s ORDER BY 1', (thread, 'log-%'))],
                'usage': conn.execute(f'SELECT count(*) FROM sojafit_agent.analysis_usage WHERE user_id=%s AND day < {day}', (a, 30)).fetchone()[0],
                'service': conn.execute(f'SELECT count(*) FROM sojafit_agent.analysis_service_usage WHERE day < {day}', (30,)).fetchone()[0],
                'auth': {h for h in (signup_old, signup_new, login_old, login_locked, login_new, ip_old, ip_locked, ip_new)
                         if conn.execute('SELECT 1 FROM public.auth_signup_attempts WHERE ip_hash=%(h)s UNION ALL SELECT 1 FROM public.auth_login_attempts '
                                         'WHERE login_hash=%(h)s UNION ALL SELECT 1 FROM public.auth_login_ip_attempts WHERE ip_hash=%(h)s', {'h': h}).fetchone()}}
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            assert conn.execute('SELECT sojafit_agent.purge_log_records(30, 2)').fetchone()[0] >= 2
            assert len([e for e in left()['events'] if e == 'log-31']) == 1  # 표마다 한 번에 2개까지만
            for _ in range(5):
                if not conn.execute('SELECT sojafit_agent.purge_log_records(30, 2)').fetchone()[0]:
                    break
        result = left()
        assert result['events'] == ['log-29'] and result['usage'] == 0 and result['service'] == 0
        assert result['auth'] == {signup_new, login_locked, login_new, ip_locked, ip_new}  # 아직 걸린 잠금과 15분 창 안의 행은 남는다
        with psycopg.connect(dsn) as conn:
            assert conn.execute(f'SELECT count(*) FROM sojafit_agent.analysis_usage WHERE user_id=%s AND day = {day}', (a, 29)).fetchone()[0] == 1
    finally:
        with psycopg.connect(dsn) as conn:
            for table, column in (('auth_signup_attempts', 'ip_hash'), ('auth_login_attempts', 'login_hash'), ('auth_login_ip_attempts', 'ip_hash')):
                conn.execute(f'DELETE FROM public.{table} WHERE {column} = ANY(%s)', ([signup_new, login_locked, login_new, ip_locked, ip_new],))
            conn.execute(f'DELETE FROM sojafit_agent.analysis_service_usage WHERE day = {day}', (29,))


def test_new_analysis_runs_cleanup_and_cleanup_failure_does_not_block(world, monkeypatch, caplog):
    app, (a, b, _), dsn = world
    mine = seed(app, dsn, a)
    age(dsn, 61, projects=mine['projects'], threads=mine['threads'])
    thread = seed(app, dsn, b)['threads'][0]
    assert app.message(b, thread, '판정')['status'] == 'DONE'  # 다른 사용자의 새 분석이 청소를 부른다
    assert remaining(dsn, a, mine['threads'])['projects'] == 0 and remaining(dsn, a, mine['threads'])['analysis_threads'] == 0
    def down():
        raise psycopg.OperationalError('synthetic outage')
    monkeypatch.setattr(app, 'connection', down)
    with caplog.at_level('WARNING', logger='backend.conversations.retention'):
        app._purge_expired()
    assert [r.message for r in caplog.records if r.name == 'backend.conversations.retention'] == ['retention_purge_failed']


# --- 028의 DB 규칙: 소유자 FK CASCADE · 화면 thread FK · 체크포인트 삭제 트리거(D9) ---

def test_deleting_a_react_thread_row_removes_analysis_records_and_checkpoints_by_trigger(world):
    """[왜] 앱 코드가 아니라 DB가 보장한다: 어떤 경로(운영자의 직접 DELETE 포함)로 화면 thread가 지워져도 질문 · 답이 든 checkpoint가 안 남는다."""
    app, (a, b, _), dsn = world
    mine, other = seed(app, dsn, a, projects=2), seed(app, dsn, b)
    gone, kept = mine['threads'][0], [mine['threads'][1]]
    before_kept, before_other = remaining(dsn, a, kept), remaining(dsn, b, other['threads'])
    before = remaining(dsn, a, [gone])
    assert before['checkpoints'] > 0 and before['checkpoint_blobs'] + before['checkpoint_writes'] > 0 and before['analysis_messages'] > 0
    with psycopg.connect(dsn) as conn:
        conn.execute('DELETE FROM public.threads WHERE id=%s', (gone,))
    after = remaining(dsn, a, [gone])
    for name in ('react_threads', 'analysis_threads', 'analysis_messages', 'analysis_events', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
        assert after[name] == 0, name
    skip = ('approvals', 'quotes', 'approved_cases')  # 사용자 단위 개수라 지운 thread의 승인이 빠진다
    assert {k: v for k, v in remaining(dsn, a, kept).items() if k not in skip} == {k: v for k, v in before_kept.items() if k not in skip}  # 다른 thread의 checkpoint는 그대로
    assert remaining(dsn, b, other['threads']) == before_other


def test_analysis_thread_requires_its_react_thread(world):
    _, (a, _, _), dsn = world
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute("INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES (%s,%s,'D1')", (uuid4(), a))


def test_deleting_a_user_row_cascades_to_every_owned_record_without_orphans(world):
    """사용자 행 하나를 지우면 FK CASCADE만으로 서비스 기록이 전부 사라진다(Store는 FK가 없어 따로 지운다)."""
    app, (a, b, _), dsn = world
    mine, other = seed(app, dsn, a, projects=2), seed(app, dsn, b)
    before_other = remaining(dsn, b, other['threads'])
    assert remaining(dsn, a, mine['threads'])['checkpoints'] > 0
    with psycopg.connect(dsn) as conn:
        conn.execute('DELETE FROM public.users WHERE id=%s', (a,))
    left = remaining(dsn, a, mine['threads'])
    assert {k: v for k, v in left.items() if k != 'store'} == {k: 0 for k in left if k != 'store'}
    assert remaining(dsn, b, other['threads']) == before_other
    with psycopg.connect(dsn) as conn:
        orphans = conn.execute('SELECT count(*) FROM sojafit_agent.threads t WHERE NOT EXISTS (SELECT 1 FROM public.threads p WHERE p.id=t.id) '
                               'OR NOT EXISTS (SELECT 1 FROM public.users u WHERE u.id=t.user_id)').fetchone()[0]
    assert orphans == 0
def test_single_thread_delete_removes_its_records_but_preserves_project_and_siblings(world):
    from backend.conversations.repository import ConversationRepository
    analysis, (owner, other, _), dsn = world
    mine, theirs = seed(analysis, dsn, owner, projects=2), seed(analysis, dsn, other)
    gone, sibling = mine['threads']
    other_before = remaining(dsn, other, theirs['threads'])
    before = remaining(dsn, owner, [gone])
    assert before['checkpoints'] > 0 and before['quotes'] == 2
    ConversationRepository().delete_thread(owner, gone)
    after = remaining(dsn, owner, [gone])
    for name in ('react_threads', 'runs', 'react_messages', 'analysis_threads', 'analysis_messages',
                 'analysis_events', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
        assert after[name] == 0, name
    assert after['projects'] == before['projects'] == 2
    assert after['quotes'] == after['approvals'] == after['approved_cases'] == 1
    assert after['store'] == before['store']
    assert remaining(dsn, owner, [sibling])['checkpoints'] > 0
    assert remaining(dsn, other, theirs['threads']) == other_before
