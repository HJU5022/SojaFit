"""voyage 적용 스크립트(scripts/db/voyage_rollout.py)와 db/008의 오프라인 시험.

- 역할: STOP 규칙(열 형식 · 예상 크기), 예상 크기 계산, `migrate`가 STOP이면 SQL을 실행하지 않는 것, 008 SQL이 halfvec(n)에는 USING 없이,
  vector(n)에만 USING을 쓰는지 SQL 글로 확인한다.
- 하지 않는 일: DB를 부르지 않는다(가짜 연결). 실제 적용은 `voyage_rollout.py migrate`를 손으로 돌린다.
- 출처: db/008_multi_dim_embeddings.sql, evals/guides/preregister.md #26
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('voyage_rollout', ROOT / 'scripts/db/voyage_rollout.py')
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def test_008_sql_drops_typmod_without_using_for_halfvec():
    sql = (ROOT / 'db/008_multi_dim_embeddings.sql').read_text(encoding='utf-8')
    halfvec = re.search(r"LIKE 'halfvec\(%'\s+THEN\s+(.*?);", sql, re.S).group(1)
    vector = re.search(r"LIKE 'vector\(%'\s+THEN\s+(.*?);", sql, re.S).group(1)
    assert 'TYPE halfvec' in halfvec and 'USING' not in halfvec  # [왜] 표를 다시 쓰지 않는다
    assert 'USING embedding::halfvec' in vector
    assert 'DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw' in sql


def test_stop_rule():
    mb = V.MB
    assert V.stop_reasons('halfvec(1536)', 300 * mb) == [] and V.stop_reasons('halfvec', 300 * mb) == []
    assert len(V.stop_reasons('vector(1536)', 300 * mb)) == 1
    assert len(V.stop_reasons('halfvec(1536)', 421 * mb)) == 1
    assert len(V.stop_reasons('halfvec(1024)', 421 * mb)) == 2


def test_projected_size_for_current_production():
    proj = V.projected_size(int(266.6 * V.MB), 52244)
    assert 370 * V.MB < proj < 390 * V.MB and not V.stop_reasons('halfvec(1536)', proj)


def test_migrate_refuses_when_stopped(monkeypatch):
    executed = []

    class Conn:
        def execute(self, sql, args=None):
            executed.append(sql)
            raise AssertionError('STOP이면 DB를 건드리면 안 된다')
    monkeypatch.setattr(V, 'check', lambda conn: ['STOP'])
    with pytest.raises(SystemExit):
        V.migrate(Conn())
    assert executed == []
