"""D3 공식 검색 측정 실행기(evals/runners/run_retrieval_d3.py)의 순수 함수 시험.

- 역할: gold 줄의 쪽 풀기(뒤에 이어 적은 쪽·범위), 페이지 단위 지표(적중·회수율·Full Recall·회수 가능만·중복 제거 nDCG·실패 유형),
  정확 부호 검정, no_result 임계값 고르기를 가짜 청크로 확인한다.
- 하지 않는 일: 실제 청크·벡터·API로 측정하지 않는다(결과는 사전 등록 #24의 실행으로만 본다).
- 출처: evals/guides/preregister.md #24, 자동 검토(11-03)의 gold 쪽 누락 사례.
"""
from collections import Counter

from evals.runners.run_retrieval_d3 import gold_pages, metrics, sign_p, threshold


def test_gold_pages_reads_every_page_in_a_line():
    # [왜] 기존 gold_locations()는 줄마다 첫 쪽만 읽어 m04 5쪽을 빠뜨렸다
    line = 'BZT52C2V4 SERIES_G1804.pdf, 2쪽, ELECTRICAL SPECIFICATIONS의 BZT52C3V6 행; 5쪽 CHARACTERISTICS'
    assert gold_pages(line) == [('BZT52C2V4 SERIES_G1804.pdf', 2), ('BZT52C2V4 SERIES_G1804.pdf', 5)]
    assert gold_pages('A.pdf, 2~4쪽, 표') == [('A.pdf', 2), ('A.pdf', 3), ('A.pdf', 4)]
    assert gold_pages('netlists/x.net, D1, 핀 A') == []


class FakeIndex:
    def __init__(self, cards):
        self.cards = cards
        self.have = Counter((c['doc'], c['page']) for c in cards)


def test_page_metrics_and_recoverable_only():
    cards = [{'doc': 'A.pdf', 'page': 1}, {'doc': 'A.pdf', 'page': 1}, {'doc': 'A.pdf', 'page': 2}, {'doc': 'B.pdf', 'page': 1}]
    idx = FakeIndex(cards)
    gold = [('A.pdf', 1), ('A.pdf', 2), ('A.pdf', 5)]  # 5쪽은 청크가 없어 회수 불가
    m = metrics([3, 0, 1, 2], {0, 1, 2, 3}, None, gold, [], idx)
    assert m['page_hit@1'] == 0.0 and m['page_hit@3'] == 1.0
    assert m['page_mrr'] == 0.5
    assert abs(m['page_recall@5'] - 2 / 3) < 1e-9 and m['page_recall_rec@5'] == 1.0
    assert m['all_evidence@5'] == 0.0 and m['all_evidence_rec@5'] == 1.0
    assert m['doc_hit@1'] == 0.0 and m['doc_mrr@5'] == 0.5
    assert 0 < m['page_ndcg@5'] < 1  # 같은 쪽 청크 두 장은 한 번만 센다


def test_failure_types():
    cards = [{'doc': 'A.pdf', 'page': 1}, {'doc': 'B.pdf', 'page': 1}]
    idx = FakeIndex(cards)
    assert metrics([1], {1}, {1}, [('A.pdf', 1)], [], idx)['fail'] == 'filter_blocked'
    assert metrics([1], {1}, None, [('A.pdf', 1)], [], idx)['fail'] == 'outside_candidates'
    assert metrics([1, 1, 1, 1, 1, 0], {0, 1}, None, [('A.pdf', 1)], [], idx)['fail'] == 'below_top_k'
    assert metrics([1], {1}, None, [('C.pdf', 1)], [], idx)['fail'] == 'corpus_missing'


def test_sign_test_and_threshold():
    assert sign_p(0, 0) == 1.0 and abs(sign_p(5, 0) - 0.0625) < 1e-9
    t = threshold([(True, 0.9), (True, 0.8), (False, 0.3), (False, None)])
    assert t['balanced_accuracy'] == 1.0 and t['empty_irrelevant'] == 1
