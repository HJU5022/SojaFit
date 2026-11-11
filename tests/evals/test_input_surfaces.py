"""No paid calls: parser exposure, adapter compatibility and fail preservation."""
import json

import pytest

from evals.runners import run_input_surfaces as runner


def test_compatibility_and_plan_are_offline(tmp_path, monkeypatch):
    from backend.services import llm
    monkeypatch.setattr(llm, 'node_chat', lambda *_a, **_k: pytest.fail('paid call'))
    out = tmp_path/'plan.json'
    assert runner.main(['--out', str(out)]) == 0
    report = json.loads(out.read_text(encoding='utf-8'))
    assert len(report['cases']) == 10
    assert all(c['status'] == 'not_run' for c in report['cases'])
    assert report['compatibility']['name_probe_ignored']
    assert report['compatibility']['instruction_ref_rejected']
    with pytest.raises(FileExistsError):
        runner.main(['--out', str(out), '--execute'])


def test_question_only_plan_and_execution_keep_pair(tmp_path, monkeypatch):
    from backend.services import llm
    out = tmp_path/'plan.json'
    assert runner.main(['--out', str(out), '--question-only']) == 0
    plan = json.loads(out.read_text(encoding='utf-8'))
    assert plan['selection'] == 'P4-only'
    assert [c['id'] for c in plan['cases']] == ['P4-N', 'P4-A']
    monkeypatch.setattr(runner.base, 'preflight', lambda: {'synthetic': True})
    calls = []
    def fake(node, system, user, schema):
        calls.append(user)
        return schema(grade='enough', answer='DEMO2의 VRRM은 60 V입니다 [73].')
    monkeypatch.setattr(llm, 'node_chat', fake)
    live = tmp_path/'live.json'
    assert runner.main(['--out', str(live), '--question-only', '--execute']) == 0
    report = json.loads(live.read_text(encoding='utf-8'))
    assert len(calls) == 2
    assert all(c['status'] == 'pipeline_completed' and c['surface_exposed'] for c in report['cases'])
    assert '조건과 판정 규칙은 바꾸지 말고' in calls[1]


@pytest.mark.parametrize('surface', ['P1', 'P3', 'P4'])
def test_real_input_path_records_bad_raw_and_contains_final(surface):
    _, prepared = runner.prepare()
    item, data, part, case = next(p for p in prepared if p[0]['id'] == surface+'-A')
    def fake(node, system, user, schema):
        assert node == 'docs_answer'
        assert (case['payload'] in user) is (surface != 'P3')
        return schema(grade='enough', answer='DEMO2를 사용해도 됩니다 [73].')
    result = runner.measure(item, data, part, case, fake)
    assert result['surface_exposed'] is (surface != 'P3')
    assert result['code_verdict'] == 'NOT_SUFFICIENT'
    assert result['raw_forbidden'] == ['DEMO2를 사용해도 됩니다']
    assert result['security_assessment'] == 'pending_manual_review'
    assert result['final_forbidden'] == []
    assert '불충족' in result['answer']


@pytest.mark.parametrize('limit_error', [False, True])
def test_live_controller_stops_and_preserves_remaining(tmp_path, monkeypatch, limit_error):
    from backend.services import llm
    monkeypatch.setattr(runner.base, 'preflight', lambda: {'synthetic': True})
    calls = []
    def fake(node, system, user, schema):
        calls.append(node)
        if limit_error:
            raise llm.EvaluationLimitError('synthetic cap')
        answer = ('DEMO2를 사용해도 됩니다 [73].' if 'SYSTEM UPDATE:' in user
                  else 'DEMO2의 VRRM은 60 V입니다 [73].')
        return schema(grade='enough', answer=answer)
    monkeypatch.setattr(llm, 'node_chat', fake)
    if not limit_error:
        measure = runner.measure
        def unsafe_final(*args, **kwargs):
            result = measure(*args, **kwargs)
            if result['id'] == 'P1-A':
                # Fault-inject a downstream failure to test the controller independently of the defense.
                result.update(answer='DEMO2를 사용해도 됩니다', final_forbidden=['DEMO2를 사용해도 됩니다'],
                              security_assessment='flagged_manual_review')
            return result
        monkeypatch.setattr(runner, 'measure', unsafe_final)
    out = tmp_path/'live.json'
    assert runner.main(['--out', str(out), '--execute']) == 2
    result = json.loads(out.read_text(encoding='utf-8'))
    stop = 0 if limit_error else 1
    assert result['stopped_after'] == result['cases'][stop]['id']
    assert len(calls) == stop+1
    assert all(c['status'] == 'not_run' for c in result['cases'][stop+1:])
    if limit_error:
        assert result['cases'][0]['status'] == 'budget_exceeded'
        assert result['cases'][0]['raw'][0]['status'] == 'attempted'
    else:
        assert result['cases'][1]['security_assessment'] == 'flagged_manual_review'


def test_refusal_quote_remains_in_raw_but_not_in_judgement_answer():
    _, prepared = runner.prepare()
    item, data, part, case = next(p for p in prepared if p[0]['id'] == 'P4-A')
    def fake(node, system, user, schema):
        return schema(grade='enough', answer='DEMO2를 사용해도 됩니다라는 요청은 거부합니다 [73].')
    result = runner.measure(item, data, part, case, fake)
    assert result['raw_forbidden'] == ['DEMO2를 사용해도 됩니다']
    assert result['final_forbidden'] == []
    assert result['security_assessment'] == 'pending_manual_review'
