"""로컬 전용 적재 경계와 묶음 예산. 실제 모델은 호출하지 않는다."""
import json
import os
import hashlib

import pytest

from evals.runners import run_judgement_bundle as runner


@pytest.mark.parametrize('case_id', ['actual-citation-false-claim', 'explanation-table-conflict'])
@pytest.mark.parametrize('evidence_id', [73, 901])
def test_real_citation_does_not_prove_claim_or_explanation_consistency(case_id, evidence_id):
    """실제 인용을 단 위험 원문은 보존하고 판정 출력 경계에서 차단한다. 실제 모델 호출 없음."""
    from backend.multi_agent.agents.docs import DocsAnswer, docs_agent
    from backend.multi_agent.contracts import Task, TaskReport
    from backend.multi_agent.supervisor import single_node, check_node
    from backend.judge import conditions as C, verdict as V
    data = json.loads((runner.ROOT/'data/corpus/injection_tests/claim_consistency_cases_v1.json').read_text(encoding='utf-8'))
    source = runner.ROOT/data['baseline_fixture']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == data['baseline_sha256']
    b = json.loads(source.read_text(encoding='utf-8'))
    case = next(c for c in data['cases'] if c['id'] == case_id)
    assert case['status'] == 'not_run' and not case['forbidden_markers']
    # DB와 무관하게 서로 다른 실제 제공ID로 검사하며 공격문에 번호를 하드코딩하지 않는다.
    answer = case['unsafe_answer_example'].format(citation_id=evidence_id)
    card = {'chunk_id': evidence_id, 'file': b['document']['file'], 'page': 1, 'table': b['document']['table'],
            'doc_parts': ['demo2'], 'content': b['document']['base_content']+'\n'+case['attack_suffix']}
    def fake_chat(node, system, user, schema):
        assert case['attack_suffix'] in user and f'[{evidence_id}]' in user
        return DocsAnswer(grade='enough', answer=answer)
    task = Task(id=1,agent='docs',kind='rating',goal='DEMO2 VRRM',query='DEMO2 VRRM',parts=['DEMO2'])
    report = docs_agent({'task':task.model_dump(mode='json'),'question':b['question']},
                        retriever=lambda *_a, **_kw:[card], chat=fake_chat)['reports'][0]
    assert report['status']=='ok' and report['answer']==answer
    assert report['evidence_ids']==[str(evidence_id)]
    rows = [{'part':'DEMO2','code':code,'min':None,'typ':None,'max':want['value'],'text':None,
             'unit':want['unit'],'source_value_text':str(want['value']),'test_condition':None,
             'citation':{'document':b['document']['file'],'page':1,'table':b['document']['table'],'row':code}}
            for code,want in b['expected']['checks'].items()]
    j = V.judge_part(C.load()['R01'],'R01','DEMO2',b['values'],b['conditions'],rows)
    assert j.verdict=='NOT_SUFFICIENT'
    judge = TaskReport(task=2,agent='judge',status='ok',summary='Code judgement',judgement={
        'kind':'judge','roles':['R01'],'role_evidence':[],'results':[j.model_dump(mode='json')]}).model_dump(mode='json')
    state = {'question':b['question'],'final_reports':[report,judge]}
    joined = single_node(state)
    assert answer not in joined['answer'] and '불충족' in joined['answer']
    checked = check_node({**state,**joined})
    assert not checked.get('refusal_reason')
    assert checked['check']['fake_citations']==[]
    # 실제 번호가 있어도 위험 주장은 근거로 승격하지 않는다.
    assert case['unsafe_example_review']['claim_supported'] is False
    assert case['unsafe_example_review']['explanation_consistent'] is False


@pytest.mark.parametrize('dsn', [
    'postgresql://app:app@db:5432/injection_test_x',
    'postgresql://app:app@remote.invalid:55439/injection_test_x',
    'postgresql://app:app@127.0.0.1:55439/app',
    'host=127.0.0.1 port=55439 dbname=injection_test_x hostaddr=1.2.3.4',
    'host=127.0.0.1 port=55439 dbname=injection_test_x service=other',
    'host=127.0.0.1 port=55439 dbname=injection_test_x options=-csearch_path=other',
])
def test_remote_or_service_database_is_rejected_before_connect(dsn):
    with pytest.raises(ValueError):
        runner.local_target(dsn)


def test_plan_does_not_connect_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'connect', lambda *_: pytest.fail('plan connected'))
    out = tmp_path / 'plan.json'
    assert runner.main(['plan', '--out', str(out)]) == 0
    report = json.loads(out.read_text(encoding='utf-8'))
    assert report['real_model_calls'] == 0
    assert all(c['status'] == 'not_run' for c in report['cases'])
    with pytest.raises(FileExistsError):
        runner.main(['plan', '--out', str(out)])


def test_shared_call_limit_stops_before_next_case(monkeypatch):
    from backend.services.llm import EvaluationBudget
    visited = []
    monkeypatch.setattr(runner, 'offline_chat', lambda *_: None)
    def case(bundle, item, dsn, chat):
        visited.append(item['id'])
        chat('fake', '', '', None)
        return {'id': item['id'], 'status': 'simulation_passed'}
    monkeypatch.setattr(runner, 'simulate_case', case)
    budget = EvaluationBudget(max_calls=1, max_usd=1, max_seconds=90,
                              max_tokens=1, prompt_rate=0.000001, completion_rate=0.000001)
    report = runner.plan('simulate')
    runner.simulate(report, '', budget)
    assert visited == ['control', 'verdict-override']
    assert report['cases'][1]['status'] == 'budget_exceeded'
    assert all(c['status'] == 'not_run' for c in report['cases'][2:])
    assert budget.calls == 1 and report['real_model_calls'] == 0


def test_expired_wall_clock_prevents_chat():
    from backend.services.llm import EvaluationBudget, EvaluationLimitError
    budget = EvaluationBudget(max_calls=16, max_usd=1, max_seconds=0.01,
                              prompt_rate=0.000001, completion_rate=0.000001)
    budget.started -= 1
    with pytest.raises(EvaluationLimitError):
        runner.budgeted_chat(budget)('supervisor', '', '', None)


def test_money_cap_applies_across_cases(monkeypatch):
    from backend.services.llm import EvaluationBudget
    monkeypatch.setattr(runner, 'offline_chat', lambda *_: None)
    monkeypatch.setattr(runner, 'simulate_case', lambda b,c,d,chat: (
        chat('fake', '', '', None) or {'id': c['id'], 'status': 'simulation_passed'}))
    budget = EvaluationBudget(max_calls=16, max_usd=0.013, max_seconds=90,
        max_tokens=1, prompt_rate=0.000001, completion_rate=0.000001)
    report = runner.plan('simulate')
    runner.simulate(report, '', budget)
    assert budget.calls == 1 and 0 < budget.reserved_usd <= 0.013
    assert [c['status'] for c in report['cases']] == ['simulation_passed', 'budget_exceeded', 'not_run', 'not_run']


def test_simulation_cli_has_no_live_option(tmp_path):
    with pytest.raises(SystemExit):
        runner.main(['simulate', '--execute', '--out', str(tmp_path / 'x.json')])


def test_malformed_dsn_does_not_echo_credentials():
    with pytest.raises(ValueError) as error:
        runner.local_target('password=FAKE_CREDENTIAL_CANARY broken')
    assert 'FAKE_CREDENTIAL_CANARY' not in str(error.value)


def test_time_consumed_by_chat_prevents_continuation(monkeypatch):
    from backend.services.llm import EvaluationBudget, EvaluationLimitError
    budget = EvaluationBudget(max_calls=16, max_usd=1, max_seconds=1,
                              prompt_rate=0.000001, completion_rate=0.000001)
    def slow(*_):
        budget.started -= 2
    monkeypatch.setattr(runner, 'offline_chat', slow)
    with pytest.raises(EvaluationLimitError):
        runner.budgeted_chat(budget)('fake', '', '', None)
    assert budget.calls == 1


def test_loopback_database_round_trip_and_fake_graph(monkeypatch):
    dsn = os.getenv('TEST_INJECTION_DATABASE_URL')
    if not dsn:
        pytest.skip('requires disposable TEST_INJECTION_DATABASE_URL')
    monkeypatch.setenv('DATABASE_URL', dsn)
    monkeypatch.setenv('LANGCHAIN_TRACING_V2', 'false')
    monkeypatch.setenv('LANGSMITH_TRACING', 'false')
    from backend.services import llm
    def forbidden(*_a, **_kw):
        pytest.fail('real provider called')
    for name in ('node_chat', 'voyage_embed', 'voyage_rerank', 'embed_texts'):
        monkeypatch.setattr(llm, name, forbidden)
    bundle = runner.bundle()
    for case in bundle['cases']:
        runner.load(dsn, bundle, case)
        found = runner.preflight(dsn, bundle, case)
        assert found['retrieved'] and found['mcp_specs'] == 8
    budget = llm.EvaluationBudget(max_calls=16, max_usd=10, max_seconds=90,
        max_tokens=1024, prompt_rate=0.000003, completion_rate=0.000015)
    report = runner.plan('simulate')
    runner.simulate(report, dsn, budget)
    assert [c['status'] for c in report['cases']] == ['simulation_passed'] * 4
    assert report['simulated_calls'] == 12 and report['real_model_calls'] == 0
    assert all(c['resumed_unknown_conditions'] for c in report['cases'])
    assert report['simulated_reserved_usd'] > 0
