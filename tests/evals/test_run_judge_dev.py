"""판정 연습 문제 채점(evals/runners/run_judge_dev.py) 시험: 역할 · 판정 일치를 문항 하나씩 매기고 모은다.

- 역할: 판정 질문은 첫 후보의 판정, 찾기 질문은 보여 준 후보 집합이 기대와 같은지 본다.
- 하지 않는 일: 실제 그래프 실행.
- 출처: docs/specs/judge-agent.md Goal(역할 정답률 · 판정 일치율)
"""
from evals.runners import run_judge_dev as D


def test_judge_item_scores_role_and_verdict():
    item = {'id': 'judgedev-01', 'role': 'R01', 'verdict': 'NOT_SUFFICIENT', 'question_type': 'candidate_judge'}
    j = {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': 'X', 'verdict': 'NOT_SUFFICIENT'}], 'shown': []}
    assert D.score_item(item, j) == {'id': 'judgedev-01', 'role_ok': True, 'verdict_ok': True, 'role': 'R01', 'verdict': 'NOT_SUFFICIENT'}


def test_find_item_compares_shown_parts_and_verdicts():
    item = {'id': 'f1', 'role': 'R01', 'question_type': 'candidate_find',
            'expected_shown': [{'part': 'SS14', 'verdict': 'ROLE_SUFFICIENT'}]}
    j = {'kind': 'find', 'roles': ['R01'], 'results': [], 'shown': [{'part': 'SS14', 'verdict': 'ROLE_SUFFICIENT'}]}
    assert D.score_item(item, j)['verdict_ok'] is True


def test_missing_judgement_is_wrong_not_crash():
    assert D.score_item({'id': 'x', 'role': 'R01', 'verdict': 'IDENTICAL', 'question_type': 'candidate_judge'}, None)['role_ok'] is False


def test_summarize_rates():
    s = D.summarize([{'role_ok': True, 'verdict_ok': False}, {'role_ok': True, 'verdict_ok': True}])
    assert s == {'n': 2, 'role_rate': 1.0, 'verdict_rate': 0.5}
