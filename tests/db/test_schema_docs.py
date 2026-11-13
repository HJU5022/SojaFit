"""scripts/db/gen_schema_docs.py 시험: 일회용 PostgreSQL에 서비스 스키마를 적용하고 생성한 표 정의서 · ERD를 확인한다.

- 역할: ① 서비스 표 24개가 모두 문서에 있고 FK 선 · 제약이 DB와 같고(승인당 견적 UNIQUE는 없고 approvals.message_id UNIQUE는 있음)
  ② `--out-dir`로 임시 위치에 쓰고 `--check`가 같은 DB에서 0 · 칸 기본값을 바꾼 DB에서 1을 내고
  ③ 설명이 없는 새 칸이 생기면 멈추고 ④ 커밋된 db/schema 문서가 생성물이면 DB와 글자까지 같아야 한다(어긋남 시험).
- 하지 않는 일: 운영 DB 접속(DATABASE_URL은 시험이 만든 DB로만 둔다), 코퍼스 · LangGraph 표 확인.
- 출처: scripts/db/gen_schema_docs.py, tests/db_schema.py, db/027~029.
[주의] ④는 db/schema 문서에 자동 생성 표시(MARKER)가 있을 때만 검사한다. 손으로 쓴 옛 문서는 건너뛴다 — 통합 단계가 처음 생성해 넣은 뒤부터 강제된다.
시험 DB는 시험 모듈마다 새로 만들고 지운다.
"""
import importlib.util
import os
import re
import secrets
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from tests.db_schema import apply_service_schema

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('gen_schema_docs', ROOT / 'scripts' / 'db' / 'gen_schema_docs.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


@pytest.fixture(scope='module')
def dsn():
    """새 DB 하나에 서비스 스키마(sojafit_agent 포함)를 적용한 접속 문자열. 끝나면 DB를 지운다."""
    base = os.getenv('TEST_AUTH_DATABASE_URL')
    if not base:
        pytest.skip('requires isolated PostgreSQL')
    name = f'schemadocs_{secrets.token_hex(4)}'
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    url = make_conninfo(base, dbname=name)
    with psycopg.connect(url, autocommit=True) as conn:
        apply_service_schema(conn, agent=True)
    yield url
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def docs_of(url):
    with psycopg.connect(url) as conn:
        return gen.generate(conn)


def test_every_service_table_is_documented(dsn):
    docs = docs_of(dsn)
    erd, definition = docs['erd.md'], docs['table-definition.md']
    assert len(gen.TABLES) == 24
    for table in gen.TABLES:
        assert f'## `{table}`' in definition
        assert f'    {gen.entity(table)} {{' in erd
    for table in gen.EXCLUDED['public'] + gen.EXCLUDED['sojafit_agent']:  # 범위 밖 표는 별도 절에 이름만
        assert f'`{table}`' in erd and f'## `public.{table}`' not in definition and f'## `sojafit_agent.{table}`' not in definition
    assert erd.startswith('# DB ERD') and gen.MARKER in erd and gen.MARKER in definition


def test_constraints_come_from_the_database(dsn):
    docs = docs_of(dsn)
    erd, definition = docs['erd.md'], docs['table-definition.md']
    approvals = definition.split('## `public.approvals`')[1].split('## `')[0]
    quotes = definition.split('## `public.quotes`')[1].split('## `')[0]
    assert '`approvals_message_id_key` | UNIQUE | `UNIQUE (message_id)`' in approvals  # 승인 중복을 막는 유일한 제약
    assert '| UNIQUE |' not in quotes  # 정정(11-11): 견적은 승인당 여러 건이 허용된다. 승인당 견적 1개 제약은 없다
    assert 'FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE' in quotes
    assert '`ix_quotes_approval` | `btree (approval_id)`' in quotes
    assert 'approvals ||--o{ quotes : "approval_id+user_id (CASCADE)"' in erd  # 견적은 여러 건(o{)
    assert 'messages ||--o| approvals : "message_id (CASCADE)"' in erd  # 승인은 메시지당 하나(o|)
    assert 'threads ||--o| agent_threads : "id (CASCADE)"' in erd  # 두 스키마의 같은 id 연결
    assert 'trg_threads_purge_checkpoints' in definition  # 체크포인트 삭제 트리거


def test_unique_index_keeps_unique_mark(dsn):
    definition = docs_of(dsn)['table-definition.md']
    assert '`ix_runs_active` | `UNIQUE btree' in definition and '`agent_messages_checkpoint` | `UNIQUE btree' in definition
    quotes = definition.split('## `public.quotes`')[1].split('## `')[0]
    assert [l for l in quotes.splitlines() if 'UNIQUE btree' in l and 'quotes_pkey' not in l] == []  # PK 외에 quotes의 UNIQUE 인덱스는 없다


def test_unique_index_turned_plain_is_detected(dsn, tmp_path, monkeypatch):
    """변이 확인: UNIQUE 인덱스를 같은 열의 일반 인덱스로 바꾸면 --check가 실패한다."""
    monkeypatch.setenv('DATABASE_URL', dsn)
    assert gen.main(['--out-dir', str(tmp_path)]) == 0
    with psycopg.connect(dsn, autocommit=True) as conn:
        want = conn.execute("SELECT pg_get_indexdef(indexrelid) FROM pg_index WHERE indexrelid = 'ix_runs_active'::regclass").fetchone()[0]
        conn.execute('DROP INDEX ix_runs_active')
        conn.execute(want.replace('CREATE UNIQUE INDEX', 'CREATE INDEX'))
        try:
            assert gen.main(['--out-dir', str(tmp_path), '--check']) == 1
        finally:
            conn.execute('DROP INDEX ix_runs_active')
            conn.execute(want)
    assert gen.main(['--out-dir', str(tmp_path), '--check']) == 0


def test_cardinality_follows_unique_columns(dsn):
    erd = docs_of(dsn)['erd.md']
    assert 'approvals ||--o| approved_cases : "approval_id+user_id (CASCADE)"' in erd  # 단독 UNIQUE(approval_id)가 복합 FK 칸에 들어 있음
    assert 'approvals ||--o{ quotes : "approval_id+user_id (CASCADE)"' in erd  # quotes는 UNIQUE 없음


def test_one_per_claims_need_a_unique_constraint(dsn):
    """칸 설명이 '당 1건 · 고유'를 말하면 그 칸 하나에 PK/UNIQUE 제약이 있어야 한다."""
    with psycopg.connect(dsn) as conn:
        found = gen.read_catalog(conn)
    for table, (_, meaning) in gen.TABLES.items():
        info = found[table]
        unique = [c['cols'] for c in info['cons'] if c['kind'] in ('PK', 'UNIQUE')]
        for col, text in meaning.items():
            if re.search(r'당 1(건|개)|고유', text):
                assert [col] in unique, f'{table}.{col}: "{text}"인데 이 칸의 UNIQUE가 없음'


def test_out_dir_and_check(dsn, tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', dsn)
    assert gen.main(['--out-dir', str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ['erd.md', 'table-definition.md']
    assert gen.main(['--out-dir', str(tmp_path), '--check']) == 0
    assert gen.main(['--out-dir', str(tmp_path / 'nothing'), '--check']) == 1  # 문서가 없으면 어긋남


def test_changed_column_default_is_detected(dsn, tmp_path, monkeypatch):
    """변이 확인: 문서를 만든 뒤 DB의 칸 하나를 바꾸면 --check가 실패한다. 되돌리면 다시 통과한다."""
    monkeypatch.setenv('DATABASE_URL', dsn)
    assert gen.main(['--out-dir', str(tmp_path)]) == 0
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute('ALTER TABLE quotes ALTER COLUMN quantity SET DEFAULT 1')
        try:
            assert gen.main(['--out-dir', str(tmp_path), '--check']) == 1
        finally:
            conn.execute('ALTER TABLE quotes ALTER COLUMN quantity DROP DEFAULT')
    assert gen.main(['--out-dir', str(tmp_path), '--check']) == 0


def test_undocumented_column_stops_generation(dsn):
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute('ALTER TABLE quotes ADD COLUMN note_extra TEXT')
        try:
            with pytest.raises(SystemExit, match='public.quotes: 설명이 없는 칸 note_extra'):
                docs_of(dsn)
        finally:
            conn.execute('ALTER TABLE quotes DROP COLUMN note_extra')


def test_committed_docs_match_the_database(dsn):
    """커밋된 db/schema 문서가 DB(db/*.sql 적용 결과)와 어긋나면 실패한다. SQL을 고치고 문서를 안 고친 PR을 잡는다."""
    docs = docs_of(dsn)
    for name, text in docs.items():
        path = ROOT / 'db' / 'schema' / name
        committed = path.read_text(encoding='utf-8')
        if gen.MARKER not in committed:
            pytest.skip(f'{name}은 아직 자동 생성물이 아니다(통합 단계에서 생성)')
        assert committed == text, f'db/schema/{name}이 DB와 다릅니다: uv run python scripts/db/gen_schema_docs.py 로 다시 생성하세요'
