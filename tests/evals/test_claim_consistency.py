"""실제모델 실행기의 호출/예산/결과 경계. 이 파일에서는 외부 모델을 부르지 않는다."""
import json

import pytest

from evals.runners import run_claim_consistency as runner


def test_plan_has_no_provider_access_or_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'execute', lambda *_: pytest.fail('paid call in plan'))
    out=tmp_path/'plan.json'
    assert runner.main(['--out',str(out)])==0
    result=json.loads(out.read_text(encoding='utf-8'))
    assert len(result['cases'])==3 and all(c['status']=='not_run' for c in result['cases'])
    with pytest.raises(FileExistsError):
        runner.main(['--out',str(out),'--execute'])


@pytest.mark.parametrize('case_index',[0,1,2])
def test_forced_bad_answer_records_raw_and_contains_final(case_index):
    from backend.multi_agent.agents.docs import DocsAnswer
    b, cases=runner.inputs()
    def fake(node,system,user,schema):
        assert node=='docs_answer'
        return DocsAnswer(grade='enough',answer='DEMO2는 이 회로에서 적합합니다 [73].')
    result=runner.measure_case(b,cases[case_index],fake)
    assert result['exposed'] and result['status']=='pipeline_completed'
    assert result['code_verdict']=='NOT_SUFFICIENT'
    assert '적합합니다' in result['raw'][0]['output']['answer']
    assert '적합합니다' not in result['answer'] and '불충족' in result['answer']
    assert result['semantic_review']=='pending_manual_review'


def test_budget_error_stops_followups_and_keeps_attempt(tmp_path,monkeypatch):
    from backend.services import llm
    monkeypatch.setattr(runner,'preflight',lambda: {'synthetic':True})
    def fail(*_a,**_kw):
        raise llm.EvaluationLimitError('synthetic cap')
    monkeypatch.setattr(llm,'node_chat',fail)
    out=tmp_path/'cap.json'
    assert runner.main(['--out',str(out),'--execute'])==2
    result=json.loads(out.read_text(encoding='utf-8'))
    assert result['cases'][0]['status']=='budget_exceeded'
    assert all(c['status']=='not_run' for c in result['cases'][1:])
    assert result['cases'][0]['raw'][0]['status']=='attempted'
