"""검색 규칙을 지킨다.

- 역할: RRF 순서, BM25 토큰(한국어 조사), gold_chunks에서 정답 문서·쪽 읽기, 표지 청크 -> 품번 색인과 품번 전체 일치 필터, BM25 0점 제외, 표지 청크 제외, 리랭크 순서 뒤 상위 k개(가짜 llm), 데모 모드·method='bm25'에서 임베딩 API 안 부름, 없는 method의 ValueError, dense 1단계(비트 후보)가 허용 청크 > N_BIT일 때만 쓰이고 품번 필터 없을 때 아이디 목록을 보내지 않는지(가짜 연결)를 확인한다. 맨 아래 실제 DB 시험은 TEST_DATABASE_URL에 코퍼스가 적재돼 있을 때만 돈다.
- 하지 않는 일: 검색 품질(Recall@k 등)은 재지 않는다(evals/runners/run_retrieval.py).
- 출처: docs/specs/rag-pipeline.md AC-05~11, EC-06~08
- [주의] DATABASE_URL은 .env의 서비스 DB(Supabase)를 가리킬 수 있어 시험에 쓰지 않는다. 로컬 compose DB 주소만 TEST_DATABASE_URL로 준다.
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
from evals.runners import run_retrieval
from evals.runners.run_retrieval import gold_locations


def test_rrf_puts_cards_in_both_lists_first():
    assert rrf([1, 2, 3], [3, 4])[0][0] == 3


def test_tokens_drop_korean_particle():
    assert tokens('TSC 1N5819는') == ['tsc', '1n5819']


def test_gold_locations_skip_netlist():
    gold = ['1N5817 SERIES_H2104.pdf, 2쪽, ELECTRICAL SPECIFICATIONS, VF 행',
            'data/circuits/collected/samples/pro_micro/converted/circuit.net, D2 핀 A']
    assert gold_locations(gold) == [('1N5817 SERIES_H2104.pdf', 2)]


# (청크 id, 문서 id, 본문): 문서 1은 SS34, 문서 2는 SS34L만 표지에 적혀 있다
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
    """retrieve()가 끝에 부르는 청크 조회 한 번만 ROWS로 흉내 낸다."""
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
    monkeypatch.setattr(R, '_nocover', {2, 4})  # 청크 1·3은 표지
    monkeypatch.setattr(R, '_connect', _CardDB)
    found = R.retrieve('SS310 2', method='bm25')  # ss310은 표지 청크 1에만, 2는 청크 2에만 있다(청크가 4장뿐이라 흔한 낱말은 idf가 0이다)
    assert [(r['chunk_id'], r['dense_rank'], r['bm25_rank']) for r in found] == [(2, None, 1)]  # 표지 청크 1은 빠진다


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


def _fake_index(monkeypatch):
    """청크 1·3은 표지(page_number 없음), 2·4는 본문 청크인 색인을 꽂는다."""
    monkeypatch.setattr(R, '_bm25', (BM25Okapi([tokens(c) for _, _, c in ROWS]), [i for i, _, _ in ROWS]))
    monkeypatch.setattr(R, '_parts', part_index(ROWS))
    monkeypatch.setattr(R, '_nocover', {2, 4})
    monkeypatch.setattr(R, '_connect', _CardDB)


def test_cover_cards_are_always_excluded(monkeypatch):
    _fake_index(monkeypatch)
    monkeypatch.setattr(llm, 'DEMO_MODE', True)
    assert [r['chunk_id'] for r in R.retrieve('SS310 2 1')] == [2, 4]  # 품번 필터가 없어도 표지 1·3은 안 나온다
    assert [r['chunk_id'] for r in R.retrieve('SS310 2', parts=['SS32'])] == [2]  # 품번 필터와 함께여도 표지 1은 뺀다
    assert R.retrieve('A1', parts=['SS34L']) == []  # 표지에만 있는 말이면 빈 결과


def test_rerank_order_applied_then_top_k(monkeypatch):
    _fake_index(monkeypatch)
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    monkeypatch.setattr(R, '_dense', lambda conn, q, allowed=None, **kw: [4, 2])  # DB·API 없이 dense 후보만 정한다
    monkeypatch.setattr(llm, 'voyage_embed', lambda texts, kind: [[0.1] * 1024])  # retrieve()가 임베딩을 미리 띄우므로 가짜로 막는다
    calls = []

    def fake_rerank(query, docs, model='rerank-3'):
        calls.append((query, docs))
        return [1, 0]  # 정렬한 후보의 두 번째가 1위

    monkeypatch.setattr(llm, 'voyage_rerank', fake_rerank)
    found = R.retrieve('SS310 2', k=1)
    assert calls == [('SS310 2', [ROWS[1][2], ROWS[3][2]])]  # 청크 id 오름차순(2, 4)으로 본문을 보낸다
    assert [r['chunk_id'] for r in found] == [4]  # 리랭크 순서(4, 2)에서 k=1장만 남는다


def test_demo_mode_does_not_rerank(monkeypatch):
    _fake_index(monkeypatch)
    monkeypatch.setattr(llm, 'DEMO_MODE', True)

    def boom(*args, **kwargs):
        raise AssertionError('데모 모드에서 리랭크 API를 불렀다')

    monkeypatch.setattr(llm, 'voyage_rerank', boom)
    assert R.retrieve('SS310 2')


class _SqlLog:
    """_dense가 보내는 SQL과 인자를 적고, 비트 후보 질의에는 [7, 8], 그 밖에는 [8]을 돌려주는 가짜 연결."""
    def __init__(self):
        self.calls = []

    def execute(self, sql, args=None):
        self.calls.append((sql, args))
        rows = [(7,), (8,)] if 'chunk_embedding_bits' in sql else [(8,)]
        return SimpleNamespace(fetchall=lambda: rows)

    def queries(self):
        return [(s, a) for s, a in self.calls if s.startswith('SELECT')]


def _dense_with(monkeypatch, allowed, n_bit=3, **kw):
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    monkeypatch.setattr(llm, 'voyage_embed', lambda texts, kind: [[0.1] * 1024])
    monkeypatch.setattr(R, 'N_BIT', n_bit)
    conn = _SqlLog()
    return R._dense(conn, 'q', allowed, **kw), conn.queries()


def test_bit_stage_runs_only_above_n_bit(monkeypatch):
    got, q = _dense_with(monkeypatch, {1, 2, 3, 4})  # 4장 > N_BIT 3: 1단계 + 2단계
    assert got == [8] and len(q) == 2
    assert 'binary_quantize' in q[0][0] and '<~>' in q[0][0] and 'chunk_embedding_bits' in q[0][0] and q[0][1][-1] == R.N_BIT
    assert sorted(q[0][1][1]) == [1, 2, 3, 4]  # 품번 필터의 허용 아이디는 1단계에도 건다
    assert 'binary_quantize' not in q[1][0] and '<=>' in q[1][0] and q[1][1][1] == [7, 8]  # 2단계는 1단계 후보 안에서만 정확 코사인
    got, q = _dense_with(monkeypatch, {1, 2, 3})  # 3장 <= N_BIT: 오늘의 정확 검색 한 번
    assert got == [8] and len(q) == 1 and 'binary_quantize' not in q[0][0] and 'chunk_embedding_bits' not in q[0][0]
    assert q[0][1][1] == [1, 2, 3]


def test_no_part_filter_excludes_cover_in_sql_without_id_list(monkeypatch):
    got, q = _dense_with(monkeypatch, set(range(1, 51)), nocover_all=True)  # 허용 50장이지만 아이디는 보내지 않는다
    assert len(q) == 2 and 'page_number IS NOT NULL' in q[0][0] and 'page_number' not in q[1][0]
    assert not any(isinstance(a, list) for a in q[0][1]) and q[1][1][1] == [7, 8]  # 1단계에 목록 인자 없음, 2단계는 후보 아이디만
    _, q = _dense_with(monkeypatch, set(range(1, 51)), n_bit=100, nocover_all=True)  # 허용 <= N_BIT: 정확 검색 한 번이지만 표지는 SQL로 뺀다
    assert len(q) == 1 and 'page_number IS NOT NULL' in q[0][0] and 'chunk_embedding_bits' not in q[0][0]


def test_concurrent_first_reads_publish_all_indexes_together(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    import threading
    import time
    rows = [(1, 1, '[sample.pdf] 이 데이터시트의 품번: UF4007', None),
            (2, 1, '[sample.pdf · 1쪽] reverse voltage 1000 V', 1)]
    reads = []
    class Connection:
        def execute(self, sql, *_):
            self.sql = sql
            reads.append(1)
            time.sleep(.02)
            return self
        def fetchall(self):
            return [('https://x/sample.pdf',)] if 'source_documents' in self.sql else rows
    @contextmanager
    def connect():
        yield Connection()
    monkeypatch.setattr(R, '_connect', connect)
    for key in ('_bm25', '_parts', '_nocover', '_runs'):
        monkeypatch.setattr(R, key, None)
    start = threading.Barrier(4)
    def first_read(_):
        start.wait()
        R.warmup()
        assert R._bm25 is not None and R._parts is not None and R._nocover == {2}
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(first_read, range(4)))
    assert len(reads) == 2  # 청크 읽기 1번 + 파일 이름 읽기 1번(스레드 4개가 불러도 한 번만)


def test_retrieve_with_threaded_embed_equals_sequential_reference(monkeypatch):
    """임베딩을 스레드로 미리 띄운 retrieve()가 순차로 부르는 기준 구현(_dense가 직접 임베딩)과 같은 결과를 낸다. 컨텍스트 변수도 넘어간다."""
    import contextvars
    _fake_index(monkeypatch)
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    seen = contextvars.ContextVar('seen', default=None)
    def embed(texts, kind):
        assert seen.get() == 'ctx'  # 작업 스레드에도 호출한 쪽 컨텍스트가 보인다
        return [[float(len(texts[0]))] * 1024]
    def dense(conn, q, allowed=None, *, nocover_all=False, embedding=None):
        assert embedding.result()[0][0] == len(q)  # 미리 띄운 임베딩이 들어온다
        return [4, 2]
    monkeypatch.setattr(llm, 'voyage_embed', embed)
    monkeypatch.setattr(llm, 'voyage_rerank', lambda q, docs, model='rerank-3': list(range(len(docs)))[::-1])
    monkeypatch.setattr(R, '_dense', dense)
    seen.set('ctx')
    got = R.retrieve('SS310 2')
    # 순차 기준: dense=[4, 2]를 직접 구하고, 같은 키워드 순위로 RRF → 오름차순 id를 뒤집는 가짜 리랭크
    keyword = R._keyword('SS310 2', R._nocover)
    fused = dict(rrf([4, 2], keyword))
    expected = [(c, fused[c]) for c in sorted(fused)][::-1]
    assert [(r['chunk_id'], r['score']) for r in got] == expected[:5]
    assert [(r['dense_rank'], r['bm25_rank']) for r in got] == [([4, 2].index(c) + 1 if c in (4, 2) else None, keyword.index(c) + 1 if c in keyword else None) for c, _ in expected[:5]]


def test_embed_error_surfaces_from_retrieve(monkeypatch):
    _fake_index(monkeypatch)
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    def boom(texts, kind):
        raise llm.UpstreamError('Voyage error 500')
    monkeypatch.setattr(llm, 'voyage_embed', boom)
    with pytest.raises(llm.UpstreamError, match='Voyage error 500'):
        R.retrieve('SS310 2', method='dense')


def test_corpus_known_is_computed_once_and_returns_copies(monkeypatch):
    from contextlib import contextmanager
    reads = []
    class Conn:
        def execute(self, sql):
            reads.append(sql)
            return self
        def fetchall(self):
            return [('https://x/a/SS32%20SERIES_Q2412.pdf',), ('https://x/b/none.pdf',)]
    @contextmanager
    def connect():
        yield Conn()
    monkeypatch.setattr(R, '_connect', connect)
    monkeypatch.setattr(R, '_parts', part_index(ROWS))
    monkeypatch.setattr(R, '_corpus', None)
    first = R.corpus_known()
    first[0].clear()
    assert R.corpus_known() == ({'ss310', 'ss32', 'ss34', 'ss34l'}, {'Q2412'}) and len(reads) == 1


def test_pool_connection_releases_and_reset_runs_even_on_error(monkeypatch):
    from backend.rag import db_pool
    events = []
    class Conn:
        def execute(self, sql, args=None):
            events.append(sql)
            if sql.startswith('SELECT'):
                raise RuntimeError('db down')
    class Pool:
        def connection(self):
            from contextlib import contextmanager
            @contextmanager
            def cm():
                try:
                    yield Conn()
                    events.append('commit')
                except BaseException:
                    events.append('rollback')
                    raise
            return cm()
    monkeypatch.setattr(db_pool, '_pool', lambda: Pool())
    monkeypatch.setattr(llm, 'DEMO_MODE', False)
    monkeypatch.setattr(llm, 'voyage_embed', lambda texts, kind: [[0.1] * 1024])
    with pytest.raises(RuntimeError, match='db down'):
        with db_pool.connection() as conn:
            R._dense(conn, 'q', {1})
    assert [e if not e.startswith('SELECT') else 'SELECT' for e in events] == ['SET enable_indexscan = off', 'SELECT', 'RESET enable_indexscan', 'rollback']  # 실패해도 RESET이 돌고 연결은 rollback으로 반납된다


def test_part_may_pass_exact_is_false_only_when_no_card_can_name_it(monkeypatch):
    """표지·본문·파일 이름 어디에도 없을 때만 False. 영문·숫자 밖 글자가 든 품번이나 색인 없음·다른 DSN은 True."""
    monkeypatch.setenv('DATABASE_URL', 'dsn')
    monkeypatch.setattr(R, '_runs', ('dsn', {'SS34'}, {'TS4148', 'F15'}))
    assert [R.part_may_pass_exact(p) for p in ('ss34', 'TS4148', 'F15', '1N5408X', 'SS3')] == [True, True, True, False, False]
    assert R.part_may_pass_exact('SMAJ6.5A') is True
    monkeypatch.setenv('DATABASE_URL', 'other')
    assert R.part_may_pass_exact('1N5408X') is True
    monkeypatch.setattr(R, '_runs', None)
    assert R.part_may_pass_exact('1N5408X') is True
