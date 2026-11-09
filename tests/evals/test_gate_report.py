"""기준표 집계기(evals/runners/gate_report.py) 시험: 옛 평가셋 판정 칸 채우기, 근거 위치 고르기, 기준 미달 찾기.

- 역할: v2처럼 verdict 칸이 없는 판정 문항에서 expected의 첫 판정 코드를 쓰는지, 문서 할 일 검색이 있으면 그것을 · 없으면 판정 표 근거 칸을
  근거 위치로 쓰는지, 비율 · 오탐 · p95 기준 미달을 빠짐없이 고르는지 본다. 그래프 · LLM 없음.
- 출처: evals/runners/gate_report.py, 정운 지시(11-07)
"""
from evals.runners import gate_report as G


def test_old_items_take_verdict_from_expected():
    it = {'question_type': 'candidate_judge', 'expected': '역할상 충분(ROLE_SUFFICIENT)이다. NOT_VERIFIED는 아니다.'}
    assert G.with_verdict(it)['verdict'] == 'ROLE_SUFFICIENT'
    assert G.with_verdict({'question_type': 'rating', 'expected': 'SAME_PART'}).get('verdict') is None


def test_found_locations_prefers_docs_search_then_judgement_table():
    row = {'tasks': [{'agent': 'judge', 'searches': []}, {'agent': 'docs', 'searches': [{'top': [['a.pdf', 1], ['b.pdf', 2]]}]}]}
    assert G.found_locations(row) == [('a.pdf', 1), ('b.pdf', 2)]
    table = '| VRRM >= | 18 | 1000 V | 표 기본 조건 | 통과 | 1N4001G SERIES_P2104.pdf 1쪽 ABSOLUTE |\n| IF | 1 | 1 A | x | 통과 | 1N4001G SERIES_P2104.pdf 2쪽 X |'
    assert G.found_locations({'tasks': [{'agent': 'judge'}], 'answer': table}) == [('1N4001G SERIES_P2104.pdf', 1), ('1N4001G SERIES_P2104.pdf', 2)]
    assert G.found_locations({'tasks': [], 'answer': '근거 없음'}) is None


def test_check_lists_every_metric_below_the_bar():
    m = {'relevant_correct': 0.96, 'irrelevant_refused': 0.94, 'doc_recall@5': 1.0, 'doc_mrr': None, 'page_recall@5': 0.9,
         'page_mrr': 0.95, 'made_up_answer': 0.06, 'wrong_answer': 0.0, 'over_refusal': 0.05, 'errors': 0, 'p95_s': 10.5}
    assert G.check(m, 0.95, 0.05, 10) == ['irrelevant_refused', 'page_recall@5', 'made_up_answer', 'p95_s']
