"""여러 개를 묻는 질문 부분별 채점(evals/runners/score_compound.py) 시험: 답할 부분의 근거 · 판정, 답하면 안 되는 부분의 거절 말.

- 출처: evals/runners/score_compound.py
"""
from evals.runners import score_compound as SC

TABLE = '| VRRM >= | 18 | 1000 V | 표 기본 조건 | 통과 | 1N4001G SERIES_P2104.pdf 1쪽 ABSOLUTE |'


def state(answer, verdict='ROLE_SUFFICIENT', path=('답 검사', '끝')):
    j = {'kind': 'judge', 'results': [{'part': 'TSC 1N4007G', 'verdict': verdict}]}
    return {'answer': answer, 'path': list(path), 'docs': [], 'passed': [], 'judgement': j, 'check': {'judgement': True},
            'final_reports': [{'agent': 'judge', 'judgement': j}]}


ITEM = {'id': 'c', 'kind': 'relevant', 'question_type': 'candidate_judge', 'parts': [
    {'type': 'candidate_judge', 'answerable': True, 'verdict': 'ROLE_SUFFICIENT', 'candidate_part': 'TSC 1N4007G',
     'gold_chunks': ['1N4001G SERIES_P2104.pdf, 1쪽, ABSOLUTE MAXIMUM RATINGS']},
    {'type': 'unanswerable', 'answerable': False, 'ask': 'TSC 1N4007X의 VRRM도 알려 줘'}]}


def test_each_part_is_scored_by_its_own_rule():
    ok = SC.score_parts(ITEM, state(f'1N4007G는 역할상 충분합니다.\n{TABLE}\n1N4007X는 코퍼스에서 찾을 수 없어 확인하지 못했어요.'))
    assert [p['pass'] for p in ok] == [True, True]
    # 답하면 안 되는 부분에 값을 지어내면(거절 말이 그 품번 문장에 없으면) 실패
    made_up = SC.score_parts(ITEM, state(f'1N4007G는 역할상 충분합니다.\n{TABLE}\n1N4007X의 VRRM은 1000 V입니다.'))
    assert [p['pass'] for p in made_up] == [True, False]
    # 판정이 다르면 근거를 인용해도 실패, 답 전체를 거절하면 답할 부분은 실패
    assert SC.score_parts(ITEM, state(f'{TABLE}', verdict='NOT_VERIFIED'))[0]['pass'] is False
    assert SC.score_parts(ITEM, state('거절', path=('거절',)))[0]['pass'] is False


def test_ask_tokens_pick_part_numbers_or_latin_words():
    assert SC.ask_tokens('발주 메모의 TSC ES1DQ의 VRRM') == ['ES1DQ']
    assert SC.ask_tokens('Q1 IRF3808 대체 MOSFET도 골라 줘') == ['Q1', 'IRF3808']
    assert SC.ask_tokens('보드 실측 온도를 알려 줘') == []
