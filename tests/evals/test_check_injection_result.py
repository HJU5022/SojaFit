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


def _write(tmp_path, rows):
    path = tmp_path / 'rows.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
    return path


def test_empty_final_answer_is_reported_as_violation():
    rows = copy.deepcopy(ROWS)
    rows[0]['answer'] = ''
    assert C.problems(rows) == [f'{rows[0]["id"]}: 최종 답 비어 있음']


def test_main_exits_1_on_violation_and_0_otherwise(tmp_path, capsys):
    assert C.main([str(_write(tmp_path, ROWS))]) == 0
    broken = copy.deepcopy(ROWS)
    broken[0]['answer'] = ''
    assert C.main([str(_write(tmp_path, broken))]) == 1
    assert '위반 1건' in capsys.readouterr().out
