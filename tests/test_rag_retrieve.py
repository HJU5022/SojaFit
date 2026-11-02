"""검색 규칙(docs/specs/rag-pipeline.md AC-05~11)을 지킨다. 맨 아래 실제 DB 시험은 TEST_DATABASE_URL에 코퍼스가 적재돼 있을 때만 돈다.

[주의] DATABASE_URL은 .env의 서비스 DB(Supabase)를 가리킬 수 있어 시험에 쓰지 않는다. 로컬 compose DB 주소만 TEST_DATABASE_URL로 준다.
"""
import json
import os

import numpy as np
import pytest

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
