"""db/026_revoke_public_grants_and_rls.sql 시험: 공개 역할(anon · authenticated) 권한 회수와 앱 표 RLS ON을 격리 PostgreSQL에서 확인한다.

- 역할: ① 일부러 준 표 · 시퀀스 · 함수 · 기본 권한이 모두 0이 되고 ② 두 번 돌려도 오류가 없고 ③ anon · authenticated 역할이 없는 DB에서도 통과하고
  ④ BYPASSRLS 없는 일반 소유자 역할은 RLS ON 뒤에도 읽기 · 쓰기 · 함수 호출이 되고(서버 동작 그대로) ⑤ anon은 코퍼스 표를 읽지 못하고
  ⑥ LangGraph 체크포인트 · Store 표도 RLS ON 뒤 setup · put · get이 된다.
- 하지 않는 일: 운영 DB 적용(운영은 조장이 한 줄 명령으로 적용), Supabase Data API 호출.
- 출처: db/026_revoke_public_grants_and_rls.sql, 11-10 운영 DB 점검.
[주의] anon · authenticated는 서버 전체(클러스터) 역할이라 시험이 만든 것만 끝에 지운다. 시험 DB는 시험마다 새로 만들고 지운다.
"""
import os
import secrets
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.errors import InsufficientPrivilege

SQL_FILE = Path(__file__).resolve().parents[2] / 'db' / '026_revoke_public_grants_and_rls.sql'
PUBLIC_ROLES = ('anon', 'authenticated')


class Env:
    """시험 DB 하나: 일반 소유자 역할이 소유하고, 슈퍼유저 연결(admin)과 소유자 연결(owner)을 만든다."""

    def __init__(self, base, db, owner_role):
        self.base, self.db, self.owner_role = base, db, owner_role

    def dsn(self, options=None):
        extra = {'options': options} if options else {}
        return make_conninfo(self.base, user=self.owner_role, password='owner_pw', dbname=self.db, **extra)

    def owner(self, options=None, **connect_kwargs):
        return psycopg.connect(self.dsn(options), autocommit=True, **connect_kwargs)

    def admin(self):
        return psycopg.connect(make_conninfo(self.base, dbname=self.db), autocommit=True)


@pytest.fixture
def base_url():
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires isolated PostgreSQL')
    return url


def make_env(base_url, with_public_roles):
    suffix = secrets.token_hex(4)
    db, owner_role = f'grants_{suffix}', f'grants_owner_{suffix}'
    created_roles = []
    with psycopg.connect(base_url, autocommit=True) as admin:
        if with_public_roles:
            for role in PUBLIC_ROLES:
                if not admin.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (role,)).fetchone():
                    admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
                    created_roles.append(role)
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD 'owner_pw' NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(owner_role)))
        admin.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(db), sql.Identifier(owner_role)))
    return Env(base_url, db, owner_role), created_roles


def drop_env(env, created_roles):
    with psycopg.connect(env.base, autocommit=True) as admin:
        admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(env.db)))
        admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(env.owner_role)))
        for role in created_roles:
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(role)))


@pytest.fixture
def env_with_roles(base_url):
    env, created = make_env(base_url, True)
    try:
        yield env
    finally:
        drop_env(env, created)


@pytest.fixture
def env_without_roles(base_url):
    with psycopg.connect(base_url, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_roles WHERE rolname IN ('anon', 'authenticated')").fetchone():
            pytest.skip('이 서버에는 anon · authenticated 역할이 이미 있다')
    env, created = make_env(base_url, False)
    try:
        yield env
    finally:
        drop_env(env, created)


SCHEMA_SQL = """
CREATE SCHEMA sojafit_agent;
CREATE TABLE source_documents (id serial PRIMARY KEY, title text);
CREATE TABLE document_chunks (id serial PRIMARY KEY, content text);
CREATE TABLE projects (id serial PRIMARY KEY, name text);
CREATE TABLE sojafit_agent.analysis_usage (day date PRIMARY KEY);
CREATE FUNCTION public.conversation_json_matches(value jsonb, shape jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS 'SELECT true';
CREATE FUNCTION public.quote_snapshot_has_forbidden_key(value jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS 'SELECT false';
"""
# Supabase 기본값과 같게: 공개 역할이 public의 모든 표 · 시퀀스 · 함수에 권한을 받고, 앞으로 만드는 표에도 자동으로 받는다. sojafit_agent까지 일부러 연다
OPEN_SQL = """
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated;
GRANT USAGE ON SCHEMA sojafit_agent TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA sojafit_agent TO anon, authenticated;
"""
GRANT_ROWS = """SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
    WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p', 'S') AND (a.grantee = 0 OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated'))"""
NO_RLS_ROWS = """SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity"""


def apply_twice(conn):
    text = SQL_FILE.read_text(encoding='utf-8')
    conn.execute(text)
    conn.execute(text)  # 멱등: 두 번째도 오류 없이 같은 결과


def test_revokes_every_public_grant_and_turns_on_rls(env_with_roles):
    with env_with_roles.owner() as owner:
        owner.execute(SCHEMA_SQL)
        owner.execute(OPEN_SQL)
        assert owner.execute(GRANT_ROWS).fetchall(), '시험 준비: 일부러 준 권한이 있어야 한다'
        apply_twice(owner)
        assert owner.execute(GRANT_ROWS).fetchall() == []  # 표 · 시퀀스 권한 0(PUBLIC 포함)
        assert owner.execute(NO_RLS_ROWS).fetchall() == []  # 모든 앱 표 RLS ON(sojafit_agent 포함)
        for role in PUBLIC_ROLES:
            for function in ('conversation_json_matches(jsonb, jsonb)', 'quote_snapshot_has_forbidden_key(jsonb)'):
                assert not owner.execute('SELECT has_function_privilege(%s, %s::regprocedure, %s)', (role, f'public.{function}', 'EXECUTE')).fetchone()[0]
        # 앞으로 만드는 표는 공개 역할 권한을 자동으로 받지 않는다(기본 권한 회수)
        owner.execute('CREATE TABLE later_table (id int)')
        assert not any(owner.execute('SELECT has_table_privilege(%s, %s, %s)', (role, 'public.later_table', 'SELECT')).fetchone()[0] for role in PUBLIC_ROLES)
        # 서버(소유자) 동작은 그대로: RLS가 켜져도 읽기 · 쓰기 · 함수 호출이 된다
        owner.execute("INSERT INTO source_documents (title) VALUES ('x')")
        assert owner.execute('SELECT count(*) FROM source_documents').fetchone()[0] == 1
        assert owner.execute("SELECT public.conversation_json_matches('{}'::jsonb, '{}'::jsonb)").fetchone()[0] is True
    # 공개 역할은 코퍼스 표를 읽지 못한다
    with env_with_roles.admin() as admin:
        for role in PUBLIC_ROLES:
            admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            with pytest.raises(InsufficientPrivilege):
                admin.execute('SELECT * FROM source_documents')
            admin.execute('RESET ROLE')


def test_runs_without_public_roles_and_keeps_owner_access(env_without_roles):
    with env_without_roles.owner() as owner:
        owner.execute(SCHEMA_SQL)
        apply_twice(owner)  # anon · authenticated가 없어도 오류 없이 RLS만 켠다
        assert owner.execute(NO_RLS_ROWS).fetchall() == []
        owner.execute("INSERT INTO projects (name) VALUES ('p')")
        assert owner.execute('SELECT count(*) FROM projects').fetchone()[0] == 1


def test_langgraph_tables_work_with_rls_on_for_a_plain_owner(env_with_roles):
    """BYPASSRLS 없는 일반 소유자 역할로 체크포인트 · Store 표가 RLS ON 뒤에도 setup · put · get이 된다(서버가 켜질 때마다 setup을 다시 부른다)."""
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    with env_with_roles.owner() as owner:
        owner.execute('CREATE SCHEMA sojafit_agent')
        agent = '-c search_path=sojafit_agent'
        with env_with_roles.owner(agent, prepare_threshold=0) as conn:
            PostgresSaver(conn).setup()
        with PostgresStore.from_conn_string(env_with_roles.dsn(agent)) as store:
            store.setup()
        owner.execute(SQL_FILE.read_text(encoding='utf-8'))
        assert owner.execute(NO_RLS_ROWS).fetchall() == []
        with env_with_roles.owner(agent, prepare_threshold=0) as conn:
            saver = PostgresSaver(conn)
            saver.setup()
            saved = saver.put({'configurable': {'thread_id': 't1', 'checkpoint_ns': ''}}, empty_checkpoint(), {'source': 'input', 'step': 0, 'parents': {}}, {})
            assert saver.get_tuple(saved).checkpoint['id'] == saved['configurable']['checkpoint_id']
        with PostgresStore.from_conn_string(env_with_roles.dsn(agent)) as store:
            store.setup()
            store.put(('u1', 'profile'), 'k', {'v': 1})
            assert store.get(('u1', 'profile'), 'k').value == {'v': 1}
