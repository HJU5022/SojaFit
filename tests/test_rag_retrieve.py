"""검색 규칙(docs/specs/rag-pipeline.md AC-05~11)을 지킨다. 맨 아래 실제 DB 시험은 TEST_DATABASE_URL에 코퍼스가 적재돼 있을 때만 돈다.

[주의] DATABASE_URL은 .env의 서비스 DB(Supabase)를 가리킬 수 있어 시험에 쓰지 않는다. 로컬 compose DB 주소만 TEST_DATABASE_URL로 준다.
"""
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from backend.rag import retrieve as R
from backend.rag.retrieve import allowed_chunks, part_index, positive_top, rrf, tokens
from backend.services import llm
from evals import run_retrieval
from evals.run_retrieval import gold_locations


def test_rrf_puts_cards_in_both_lists_first():
    assert rrf([1, 2, 3], [3, 4])[0][0] == 3


def test_tokens_drop_korean_particle():
    assert tokens('TSC 1N5819는') == ['tsc', '1n5819']


def test_gold_locations_skip_netlist():
    gold = ['1N5817 SERIES_H2104.pdf, 2쪽, ELECTRICAL SPECIFICATIONS, VF 행',
            'data/circuits/collected/samples/pro_micro/converted/circuit.net, D2 핀 A']
    assert gold_locations(gold) == [('1N5817 SERIES_H2104.pdf', 2)]


# (카드 id, 문서 id, 본문): 문서 1은 SS34, 문서 2는 SS34L만 표지에 적혀 있다
ROWS = [(1, 1, '[SS32 SERIES_Q2412.pdf] 이 데이터시트의 품번: SS310, SS32, SS34'), (2, 1, '[SS32 SERIES_Q2412.pdf · 2쪽 · RATINGS] VRRM: 40'),
        (3, 2, '[SS34L SERIES_A1.pdf] 이 데이터시트의 품번: SS34L'), (4, 2, '[SS34L SERIES_A1.pdf · 1쪽 · RATINGS] SS34 VRRM: 40')]


def test_part_index_reads_cover_cards():
    part_docs, doc_chunks = part_index(ROWS)
    assert part_docs == {'ss310': {1}, 'ss32': {1}, 'ss34': {1}, 'ss34l': {2}}
    assert doc_chunks == {1: [1, 2], 2: [3, 4]}


def test_parts_filter_matches_whole_part_only():
    assert allowed_chunks(part_index(ROWS), ['ss34']) == {1, 2}


def test_unknown_part_allows_nothing():
    assert allowed_chunks(part_index(ROWS), ['NOPE123']) == set()


def test_bm25_zero_scores_are_not_candidates():
    assert positive_top(np.array([0.0, 2.0, 0.0, 1.0, -np.inf]), [10, 11, 12, 13, 14], 50) == [11, 13]
    assert positive_top(np.zeros(3), [1, 2, 3], 50) == []  # 질문 단어가 하나도 안 맞으면 빈 목록


def test_demo_mode_skips_embedding_api(monkeypatch):
    def boom(texts):
        raise AssertionError('데모 모드에서 임베딩 API를 불렀다')
    monkeypatch.setattr(llm, 'DEMO_MODE', True)
    monkeypatch.setattr(llm, 'embed_texts', boom)
    assert R._dense(None, 'SS34 정격') == []


class _CardDB:
    """retrieve()가 끝에 부르는 카드 조회 한 번만 ROWS로 흉내 낸다."""
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args):
        rows = [(i, f'doc{d}', f'https://x/doc{d}.pdf', 1, None, c, d) for i, d, c in ROWS if i in args[0]]
        return SimpleNamespace(fetchall=lambda: rows)


def test_bm25_method_skips_embedding_api(monkeypatch):
    def boom(texts):
        raise AssertionError("method='bm25'에서 임베딩 API를 불렀다")
    monkeypatch.setattr(llm, 'DEMO_MODE', False)  # 키가 있어도 부르지 않아야 한다
    monkeypatch.setattr(llm, 'embed_texts', boom)
    monkeypatch.setattr(R, '_bm25', (BM25Okapi([tokens(c) for _, _, c in ROWS]), [i for i, _, _ in ROWS]))
    monkeypatch.setattr(R, '_parts', part_index(ROWS))
    monkeypatch.setattr(R, '_connect', _CardDB)
    found = R.retrieve('SS310 정격', method='bm25')  # ss310은 카드 1에만 있다
    assert [(r['chunk_id'], r['dense_rank'], r['bm25_rank']) for r in found] == [(1, None, 1)]


def test_unknown_method_raises():
    with pytest.raises(ValueError, match='method'):
        R.retrieve('SS34 정격', method='rerank')


def test_eval_with_no_targets_says_why(tmp_path):
    path = tmp_path / 'd.jsonl'
    path.write_text(json.dumps({'id': 'x', 'kind': 'irrelevant', 'gold_chunks': [], 'question': 'q'}) + '\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='평가할 문항이 없습니다'):
        run_retrieval.main(str(path), str(tmp_path / 'out.json'))


def _has_corpus():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        return False
    import psycopg
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT to_regclass('document_chunks') IS NOT NULL").fetchone()[0] and \
            conn.execute('SELECT EXISTS (SELECT 1 FROM document_chunks)').fetchone()[0]


@pytest.mark.skipif(not _has_corpus(), reason='TEST_DATABASE_URL에 코퍼스가 적재돼 있을 때만 돈다')
def test_real_db_demo_mode_bm25_only(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_DATABASE_URL'])
    monkeypatch.setattr(R, '_bm25', None)  # 시험 DB로 색인을 새로 만든다
    monkeypatch.setattr(llm, 'DEMO_MODE', True)  # 키 없는 데모: API 없이 BM25만
    found = R.retrieve('SS34 정격이 어떻게 돼?', parts=['SS34'])
    assert found and {r['file'] for r in found} == {'SS32 SERIES_Q2412.pdf'}
    assert all(r['dense_rank'] is None for r in found)
    assert all('ss34' in r['doc_parts'] for r in found)  # 문서 표지 품번 목록(소문자)
    assert R.retrieve('이 보드에서 이건 왜 필요해?') == []  # 영문·숫자 단어가 없으면 BM25 후보도 없다
    assert R.retrieve('SS34 정격', parts=['NOPE123']) == []
