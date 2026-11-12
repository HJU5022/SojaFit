"""서비스 표 재설계(db/027~029)의 DB 규칙을 일회용 데이터베이스에서 확인한다: 삭제 연쇄 · 체크포인트 삭제 트리거 · FK 거부 · 새 CHECK.

- [왜] sojafit_agent 쪽(028)은 격리 스키마에 못 넣는다(진짜 sojafit_agent · public 이름을 부른다). 그래서 TEST_AUTH_DATABASE_URL의 서버에
  이 시험 전용 데이터베이스를 만들어 `apply_service_schema(conn, agent=True)`로 적용하고 끝나면 지운다(다른 시험의 public을 건드리지 않는다).
- [주의] LangGraph 체크포인트 표 3개는 앱이 `--setup` 때 만든다. 트리거 시험은 thread_id가 글자(text)인 같은 모양의 표를 직접 만든다.
"""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from tests.db_schema import apply_service_schema

CHECKPOINT_TABLES = ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes')


@pytest.fixture(scope='module')
def db():
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires an isolated authentication test database')
    name = 'svc_schema_' + uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE {name}')
    try:
        dsn = make_conninfo(url, dbname=name)
        with psycopg.connect(dsn) as conn:
            apply_service_schema(conn, agent=True)
            for table in CHECKPOINT_TABLES:
                conn.execute(f'CREATE TABLE sojafit_agent.{table} (thread_id text NOT NULL, payload text)')
        yield dsn
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')


@pytest.fixture
def conn(db):
    with psycopg.connect(db) as c:
        yield c
        c.rollback()  # 시험이 넣은 행은 남기지 않는다


def make_user(conn):
    return conn.execute("INSERT INTO public.users(login_id,password_hash,role) VALUES (%s,'fake','user') RETURNING id", (f'{uuid4()}@t.test',)).fetchone()[0]


def make_project(conn, user):
    return conn.execute("INSERT INTO public.projects(user_id,name,source_kind) VALUES (%s,'p','upload') RETURNING id", (user,)).fetchone()[0]


def make_thread(conn, project):
    """화면 대화 + 같은 UUID의 분석 대화 + 체크포인트 3벌."""
    thread = uuid4()
    conn.execute('INSERT INTO public.threads(id,project_id) VALUES (%s,%s)', (thread, project))
    user = conn.execute('SELECT user_id FROM public.projects WHERE id=%s', (project,)).fetchone()[0]
    conn.execute("INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES (%s,%s,'D1')", (thread, user))
    for table in CHECKPOINT_TABLES:
        conn.execute(f'INSERT INTO sojafit_agent.{table}(thread_id) VALUES (%s)', (str(thread),))
    return thread


def count(conn, table, thread):
    column = 'id' if table.endswith('.threads') else 'thread_id'
    value = thread if column == 'id' else str(thread)
    return conn.execute(f'SELECT count(*) FROM {table} WHERE {column}=%s', (value,)).fetchone()[0]


ALL = ('public.threads', 'sojafit_agent.threads', 'sojafit_agent.checkpoints', 'sojafit_agent.checkpoint_blobs', 'sojafit_agent.checkpoint_writes')


def test_deleting_a_project_removes_analysis_thread_and_checkpoints(conn):
    user = make_user(conn)
    project, other = make_project(conn, user), make_project(conn, user)
    gone, kept = make_thread(conn, project), make_thread(conn, other)
    conn.execute('DELETE FROM public.projects WHERE id=%s', (project,))
    assert [count(conn, t, gone) for t in ALL] == [0] * 5
    assert [count(conn, t, kept) for t in ALL] == [1] * 5  # 다른 프로젝트의 대화는 그대로


def test_deleting_a_user_cascades_through_projects_to_checkpoints(conn):
    user = make_user(conn)
    thread = make_thread(conn, make_project(conn, user))
    conn.execute('DELETE FROM public.users WHERE id=%s', (user,))
    assert [count(conn, t, thread) for t in ALL] == [0] * 5


def test_trigger_purges_checkpoints_when_a_thread_row_is_deleted_directly(conn):
    # [왜] 보관 기간 청소나 운영자의 직접 DELETE도 체크포인트를 남기지 않아야 한다(체크포인트는 thread_id가 글자라 FK로는 못 건다)
    thread = make_thread(conn, make_project(conn, make_user(conn)))
    conn.execute('DELETE FROM public.threads WHERE id=%s', (thread,))
    assert [count(conn, t, thread) for t in ALL] == [0] * 5


def test_agent_thread_requires_a_screen_thread(conn):
    user = make_user(conn)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute("INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES (%s,%s,'D1')", (uuid4(), user))


def test_dropped_tables_and_columns_are_gone(conn):
    gone = conn.execute("""SELECT to_regclass('sojafit_agent.circuits'), to_regclass('sojafit_agent.approvals'), to_regclass('public.auth_google_pending'),
                                  (SELECT count(*) FROM information_schema.columns WHERE table_schema='sojafit_agent' AND table_name='threads' AND column_name='circuit_id'),
                                  (SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='display_name')""").fetchone()
    assert gone == (None, None, "auth_google_pending", 0, 0)  # 030 adds active onboarding; dead business copies remain absent


def full_result(**extra):
    base = {'answer': '', 'question_type': '', 'price_parts': [], 'interrupt': {}, 'judgement': None, 'evidence': []}
    return base | extra


def test_runs_safe_result_check_needs_the_six_keys_only(conn):
    project = make_project(conn, make_user(conn))
    thread = uuid4()
    conn.execute('INSERT INTO public.threads(id,project_id) VALUES (%s,%s)', (thread, project))

    def insert(result):
        with conn.transaction():
            conn.execute("INSERT INTO public.runs(id,thread_id,status,safe_result) VALUES (%s,%s,'completed',%s)", (uuid4(), thread, Jsonb(result)))
    insert(full_result())
    insert(full_result(judgement={'anything': 'the app model checks the shape'}, unknown_extra=1))  # 모양은 앱이 본다: 키 6개만 있으면 통과
    for missing in ('answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence'):
        with pytest.raises(psycopg.errors.CheckViolation):
            insert({k: v for k, v in full_result().items() if k != missing})
    with pytest.raises(psycopg.errors.CheckViolation):
        insert([full_result()])  # 객체가 아니면 거부


def test_demo_id_only_for_demo_projects(conn):
    user = make_user(conn)
    def insert(kind, demo_id):
        with conn.transaction():
            conn.execute("INSERT INTO public.projects(user_id,name,source_kind,demo_id) VALUES (%s,'p',%s,%s)", (user, kind, demo_id))
    insert('demo', 'any_new_demo_id')  # 허용 목록이 없으니 새 데모 id도 DB 변경 없이 저장된다
    insert('upload', None)
    for kind, demo_id in (('demo', None), ('upload', 'breadboard_supply')):
        with pytest.raises(psycopg.errors.CheckViolation):
            insert(kind, demo_id)


def test_approval_columns_are_required_and_checked(conn):
    # approvals의 승인 칸 3개는 NOT NULL + 형식 CHECK, quotes · approved_cases에는 snapshot 칸이 없다
    user = make_user(conn)
    project = make_project(conn, user)
    thread, run = uuid4(), uuid4()
    conn.execute('INSERT INTO public.threads(id,project_id) VALUES (%s,%s)', (thread, project))
    conn.execute("INSERT INTO public.runs(id,thread_id,status) VALUES (%s,%s,'completed')", (run, thread))
    message = conn.execute("INSERT INTO public.messages(thread_id,run_id,role,content) VALUES (%s,%s,'assistant','a') RETURNING id", (thread, run)).fetchone()[0]

    def approve(part, verdict, number, msg=None):
        with conn.transaction():
            return conn.execute('INSERT INTO public.approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                                (user, msg or message, Jsonb({}), part, verdict, number)).fetchone()[0]
    for args in ((None, 'IDENTICAL', 'SS34'), ('SS34', None, 'SS34'), ('SS34', 'IDENTICAL', None)):
        with pytest.raises(psycopg.errors.NotNullViolation):
            approve(*args)
    for args in (('', 'IDENTICAL', 'SS34'), ('SS34', 'NOT_SUFFICIENT', 'SS34'), ('SS34', 'IDENTICAL', 'bad number')):
        with pytest.raises(psycopg.errors.CheckViolation):
            approve(*args)
    approval = approve('TSC 1N4007G', 'ROLE_SUFFICIENT', '1N4007G')
    # 승인당 견적은 DB가 하나로 막지 않는다(approved_cases만 승인당 하나)
    for _ in range(2):
        conn.execute('INSERT INTO public.quotes(user_id,approval_id,part_number,quantity) VALUES (%s,%s,%s,1)', (user, approval, '1N4007G'))
    conn.execute('INSERT INTO public.approved_cases(user_id,approval_id) VALUES (%s,%s)', (user, approval))
    with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute('INSERT INTO public.approved_cases(user_id,approval_id) VALUES (%s,%s)', (user, approval))
