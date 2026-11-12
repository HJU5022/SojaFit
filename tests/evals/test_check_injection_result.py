"""저장한 인젝션 실측 결과가 기준을 통과하고, 기준 미달 변이는 실패로 바뀐다(키 없음)."""
import copy
import json

from evals.runners import check_injection_result as C

ROWS = [json.loads(line) for line in C.DEFAULT.read_text(encoding='utf-8').splitlines()]


def test_saved_run_03_meets_preregistered_criteria():
    assert C.problems(ROWS) == []


def test_mutations_fail():
    for edit in (lambda r: r.pop(),
                 lambda r: r[0].update(status='not_run'),
                 lambda r: next(x for x in r if x['case'] == 'T5')['automatic'].update(verdict_correct=False),
                 lambda r: next(x for x in r if x['case'] == 'T2')['automatic'].update(exposed=False) or
                           next(x for x in r if x['case'] == 'T2').update(protected_exposed=False)):
        rows = copy.deepcopy(ROWS)
        edit(rows)
        assert C.problems(rows), edit
