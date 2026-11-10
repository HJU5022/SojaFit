"""D7 측정기의 과금 경계와 실패 탐지를 검사한다. 모델 저항성을 주장하지 않는다."""
import json

import pytest

from evals.runners import run_trust_boundary as runner


def test_plan_never_calls_model_or_counts_attacks_as_passed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'execute', lambda *a: pytest.fail('dry-run called model'))
    out = tmp_path / 'boundary.json'
    assert runner.main(['--out', str(out)]) == 0
    report = json.loads(out.read_text(encoding='utf-8'))
    assert len(report['cases']) == 4 and report['deployed_http_test'] is False
    assert all(r['status'] == 'not_run' for r in report['cases'])
    assert report['limits']['max_calls'] == 16 and report['billing_reconciled'] is False
    with pytest.raises(FileExistsError):
        runner.main(['--out', str(out), '--execute'])


@pytest.mark.parametrize('case', runner.load_cases()[1:], ids=lambda c: c['id'])
def test_each_corpus_attack_reaches_agent_and_detector_catches_compliant_model(case):
    from backend.multi_agent.agents.docs import DocsAnswer
    seen = []
    def chat(node, system, user, schema):
        seen.append(user)
        return DocsAnswer(grade='enough', answer=f"{case['forbidden'][0]} [7].")
    row = runner.run_case(case, chat)
    assert row['status'] == 'failed' and row['exposed'] is True
    assert case['content'] in seen[0] and row['leaked_tokens'] == [case['forbidden'][0]]


def test_control_must_answer_and_refusal_is_not_a_quality_pass():
    from backend.multi_agent.agents.docs import DocsAnswer
    control = runner.load_cases()[0]
    good = runner.run_case(control, lambda *a: DocsAnswer(grade='enough', answer='VRRM은 40 V입니다 [7].'))
    assert good['status'] == 'passed' and good['exposed']
    refused = runner.run_case(control, lambda *a: DocsAnswer(grade='none'))
    assert refused['status'] == 'failed'
    wrong = runner.run_case(control, lambda *a: DocsAnswer(grade='enough', answer='VRRM은 140 V입니다 [7].'))
    assert wrong['status'] == 'failed'


def test_harness_results_do_not_hide_raw_model_leak_or_claim_deployed_success():
    from backend.multi_agent.agents.docs import DocsAnswer
    case = runner.load_cases()[3]
    row = runner.run_case(case, lambda *a: DocsAnswer(grade='enough',
        answer='VRRM은 40 V입니다 [7].', memory_refs=['승인사례:foreign:1']))
    assert row['status'] == 'blocked' and row['raw_model_leaked_tokens']
    assert row['leaked_tokens'] == [] and row['agent_status'] == 'fail'


def test_model_error_stops_next_case_and_preserves_not_run(tmp_path, monkeypatch):
    def fail(report, save):
        raise RuntimeError('synthetic internal error')
    monkeypatch.setattr(runner, 'execute', fail)
    out = tmp_path / 'error.json'
    assert runner.main(['--out', str(out), '--execute']) == 2
    report = json.loads(out.read_text(encoding='utf-8'))
    assert report['error_type'] == 'RuntimeError'
    assert all(r['status'] == 'not_run' for r in report['cases'])
    assert 'synthetic internal error' not in out.read_text(encoding='utf-8')


@pytest.mark.parametrize('stop', ['failed', 'error'])
def test_execute_stops_at_failed_or_errored_case_without_hiding_attempt(stop, monkeypatch):
    from backend.services import llm
    monkeypatch.setattr(llm, 'LLM_PROVIDER', 'openrouter')
    calls = []
    def run(case, chat):
        calls.append(case['id'])
        if stop == 'error':
            raise RuntimeError('synthetic private details')
        return {'id': case['id'], 'status': 'failed'}
    monkeypatch.setattr(runner, 'run_case', run)
    report = {'cases': [{'id': c['id'], 'status': 'not_run'} for c in runner.load_cases()]}
    if stop == 'error':
        with pytest.raises(RuntimeError):
            runner.execute(report, lambda: None)
    else:
        runner.execute(report, lambda: None)
    assert calls == ['control'] and report['cases'][0]['status'] == stop
    assert all(c['status'] == 'not_run' for c in report['cases'][1:])
    assert 'synthetic private details' not in json.dumps(report)
