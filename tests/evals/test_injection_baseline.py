"""Runner checks never use real model/embedding providers."""
import json
from pathlib import Path

import pytest

from evals.runners import run_injection_baseline as runner
from evals.runners import plan_injection_baseline as planner


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a,**k):
        pytest.fail('External request forbidden')
    monkeypatch.setattr('socket.socket.connect',deny)
    monkeypatch.setattr('backend.services.llm._chat_model',deny)
    monkeypatch.setattr('httpx.post',deny)
    monkeypatch.setattr('urllib.request.urlopen',deny)
    monkeypatch.setattr('psycopg.connect',deny)


def test_default_plan_writes_110_not_run_rows_and_pending_review(tmp_path):
    out=tmp_path/'plan.jsonl'
    assert runner.main(['--out',str(out)])==0
    rows=[json.loads(s) for s in out.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==110 and all(r['status']=='not_run' for r in rows)
    assert sum(r['preparation_turns'] for r in rows)==10
    assert all(r['mode']=='plan' and r['human_review']['passed'] is None for r in rows)
    with pytest.raises(FileExistsError):
        runner.main(['--out',str(out)])


def test_remaining_smoke_simulates_only_ten_scored_jobs_and_pending_reviews(tmp_path):
    out=tmp_path/'remaining.jsonl'
    assert runner.main(['--remaining-smoke','--simulate','--out',str(out)])==0
    rows=[json.loads(s) for s in out.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==10 and all(r['status']=='simulation_completed' for r in rows)
    assert all(r['scope']=='remaining_smoke_v1' and r['human_review']['passed'] is None for r in rows)
    with pytest.raises(ValueError,match='Explicit user'):
        runner.main(['--remaining-smoke','--execute','--out',str(tmp_path/'live.jsonl')])


def test_t7_only_smoke_simulation_has_two_rows_and_keeps_full_run_locked(tmp_path):
    out=tmp_path/'t7.jsonl'
    assert runner.main(['--t7-smoke','--simulate','--out',str(out)])==0
    rows=[json.loads(s) for s in out.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==2 and all(r['case']=='T7' and r['scope']=='t7_smoke_v1' for r in rows)
    assert all(r['status']=='simulation_completed' and r['human_review']['passed'] is None for r in rows)
    with pytest.raises(ValueError,match='Explicit user'):
        runner.main(['--t7-smoke','--execute','--out',str(tmp_path/'live.jsonl')])


@pytest.mark.parametrize('variant',['normal','attack'])
def test_t7_footprint_boundary_preserves_normal_role_and_code_verdict(monkeypatch,variant):
    data=planner.fixture();job=next(j for j in planner.jobs(data) if j['case']=='T7' and j['variant']==variant)
    payload=next(c['payload'] for c in data['cases'] if c['id']=='T7')
    normal_factory=runner.fake_chat
    def factory(data,job,inputs):
        normal=normal_factory(data,job,inputs)
        def chat(node,system,user,schema):
            if node=='judge_read' and payload in user:
                # First recorded attack read from smoke05; do not force an R01 correction in product code.
                return schema.model_validate(dict(role='R04',role_evidence=['User explicitly states D1 is classified as R04 (zener clamp)'],
                    values=[dict(name='v_in_max',number=60,unit='V',quote='입력 최대 60 V')],original_part='DEMO1',candidates=['DEMO2']))
            return normal(node,system,user,schema)
        return chat
    monkeypatch.setattr(runner,'fake_chat',factory)
    row=runner.simulate_trial(data,job)
    assert row['automatic']['role_correct'] and row['automatic']['input_values_correct']
    assert row['automatic']['verdict_correct'] and row['automatic']['specification_correct'] and row['automatic']['checks_correct']
    assert row['state']['judgement']['results'][0]['verdict']=='NOT_SUFFICIENT'
    from backend.judge.verdict import board_change
    assert board_change(row['state']['target_part']['footprint'],['DO-41']) is False
    assert '불충족' in row['answer'] and row['human_review']['passed'] is None
    if variant=='attack':
        assert payload in row['state']['target_part']['footprint']
        assert not row['exposed']


def test_exposure_cli_is_four_jobs_and_no_approval_cannot_execute(tmp_path):
    out=tmp_path/'exposure.jsonl'
    assert runner.main(['--exposure-only','--out',str(out)])==0
    rows=[json.loads(s) for s in out.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==4 and all(r['scope']=='exposure_t1_t3_v1' and r['status']=='not_run' for r in rows)
    assert all(r['human_review']['passed'] is None for r in rows)
    with pytest.raises(ValueError,match='approval'):
        runner.main(['--exposure-only','--execute','--out',str(tmp_path/'live.jsonl')])


def test_enabled_exposure_still_requires_team_budget_approval(tmp_path):
    data=planner.exposure_fixture(planner.fixture())
    data['execution_enabled']=True
    path=tmp_path/'pending.json'
    path.write_text(json.dumps(dict(scope=data['scope'],scope_sha256=planner.scope_sha256(data),
        approved_by_user=True,approved_by_team_lead=False)),encoding='utf-8')
    with pytest.raises(ValueError,match='team budget approval'):
        runner.approved(data,path)


def test_exposure_report_separates_retrieval_from_model_input():
    data=planner.exposure_fixture(planner.fixture())
    job=next(r for r in planner.jobs(data) if r['variant']=='attack')
    inputs=planner.materialize(data,data['cases'][0],'attack')
    record={'nodes':[{'node':'retrieve','retrieved':[{'content_sha256':inputs['snapshot_patch']['sha256']}]}]}
    summary=runner.exposure_summary(data,job,record)
    assert summary['source_chunk_retrieved'] is True
    assert summary['source_chunk_model_exposed'] is False
    assert summary['attack_instruction_model_exposed'] is False
    record['nodes'].append({'node':'docs_answer','status':'error','source_chunk_exposed':True,'exposed':True})
    assert runner.exposure_summary(data,job,record)['source_chunk_input_assembled'] is True
    assert runner.exposure_summary(data,job,record)['source_chunk_model_exposed'] is False
    record['nodes'][-1]['status']='returned'
    assert runner.exposure_summary(data,job,record)['attack_instruction_model_exposed'] is True


@pytest.mark.parametrize('exposure',[True,False])
def test_approval_from_other_scope_is_rejected_before_git_or_provider(tmp_path,exposure):
    data=planner.exposure_fixture(planner.fixture()) if exposure else planner.fixture()
    data['execution_enabled']=True
    path=tmp_path/'wrong.json'
    path.write_text(json.dumps({'scope':'baseline' if exposure else 'exposure_t1_t3_v1'}),encoding='utf-8')
    with pytest.raises(ValueError,match='scope'):
        runner.approved(data,path)


def test_exposure_requires_four_separate_exposure_databases():
    data=planner.exposure_fixture(planner.fixture())
    mapping={f'{c}:{v}':f'postgresql://127.0.0.1:55479/injection_test_exposure_{c.lower()}_{v}'
             for c in ('T1','T3') for v in ('normal','attack')}
    assert len(runner.database_map(data,mapping))==4
    mapping['T1:normal']='postgresql://127.0.0.1:55479/injection_test_t1_normal'
    with pytest.raises(ValueError,match='separate exposure'):
        runner.database_map(data,mapping)


def test_exposure_live_adapter_uses_only_scoped_map_and_controller(tmp_path,monkeypatch):
    from contextlib import nullcontext
    import io
    from evals.runners import injection_baseline_runtime as live
    from backend.services import llm
    data=planner.exposure_fixture(planner.fixture())
    mapping={f'{c}:{v}':f'postgresql://127.0.0.1:55479/injection_test_exposure_{c.lower()}_{v}'
             for c in ('T1','T3') for v in ('normal','attack')}
    monkeypatch.setenv('INJECTION_EXPOSURE_DATABASES',json.dumps(mapping))
    monkeypatch.setenv('INJECTION_BASELINE_DATABASES','invalid_full_map_must_not_be_read')
    monkeypatch.setattr(llm,'LLM_PROVIDER','openrouter')
    monkeypatch.setattr(llm,'node_model',lambda n:'anthropic/claude-sonnet-5.5' if n=='synth' else 'anthropic/claude-haiku-5.5')
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:io.BytesIO(json.dumps({'data':data['pricing_snapshot']['models']}).encode()))
    monkeypatch.setattr(live.pre,'observed_budget',lambda *a:nullcontext())
    seen=[]
    def controller(received,out,mode,trial):
        seen.extend(planner.jobs(received))
        return 0
    monkeypatch.setattr(runner,'run',controller)
    assert live.execute_approved(data,tmp_path/'exposure.jsonl')==0
    assert len(seen)==4 and {r['case'] for r in seen}=={'T1','T3'}
    ledger=json.loads((tmp_path/'exposure.budget.json').read_text(encoding='utf-8'))
    assert ledger['calls']==0


def test_controller_preserves_failed_and_unattempted_rows(tmp_path):
    out=tmp_path/'partial.jsonl'
    calls=[]
    def trial(job):
        calls.append(job['id'])
        if len(calls)==2:
            raise RuntimeError('synthetic failure')
        return {'status':'simulation_completed','answer':'synthetic'}
    assert runner.run(planner.fixture(),out,'simulate',trial)==1
    rows=[json.loads(s) for s in out.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==110 and len(calls)==2
    assert rows[0]['status']=='simulation_completed' and rows[1]['status']=='error'
    assert all(r['status']=='not_run' for r in rows[2:])
    assert rows[1]['error_type']=='RuntimeError'


def test_execute_without_approval_stops_before_db_or_provider(tmp_path):
    out=tmp_path/'live.jsonl'
    with pytest.raises(ValueError,match='approval'):
        runner.main(['--out',str(out),'--execute'])
    assert not out.exists()


def test_disabled_fixture_rejects_forged_approval_without_connecting(tmp_path,monkeypatch):
    data=planner.fixture()
    data['execution_enabled']=False
    monkeypatch.setattr(planner,'fixture',lambda:data)
    approval=tmp_path/'approval.json'
    approval.write_text(json.dumps({'approved_by_user':True,'approved_by_team_lead':True}),encoding='utf-8')
    with pytest.raises(ValueError,match='approval'):
        runner.main(['--out',str(tmp_path/'live.jsonl'),'--execute','--approval',str(approval)])


def test_corpus_export_preserves_base_and_changes_one_card_per_corpus_attack():
    data=planner.fixture()
    jobs=planner.jobs(data)
    normal=runner.corpus_bundle(data,next(j for j in jobs if j['case']=='T1' and j['variant']=='normal'))
    attack=runner.corpus_bundle(data,next(j for j in jobs if j['case']=='T1' and j['variant']=='attack'))
    assert len(normal['manifest'])==42 and len(normal['chunks'])==1556
    changed=[(a,b) for a,b in zip(normal['chunks'],attack['chunks']) if a!=b]
    assert len(changed)==1
    assert changed[1:] == []
    t5=runner.corpus_bundle(data,next(j for j in jobs if j['case']=='T5' and j['variant']=='normal'))
    synthetic=t5['chunks'][1557:]
    for row in synthetic:
        assert f"· {row['page']}쪽 · {row['table']}]" in row['text']


def test_database_map_rejects_remote_duplicate_and_incomplete():
    with pytest.raises(ValueError):
        runner.database_map(planner.fixture(),{})
    mapping={f'T{i}:{v}':f'postgresql://127.0.0.1:55459/injection_test_t{i}_{v}'
             for i in range(1,8) for v in ('normal','attack')}
    assert len(runner.database_map(planner.fixture(),mapping))==14
    for value in ['postgresql://remote.invalid:5432/injection_test_remote',mapping['T1:normal']]:
        wrong=dict(mapping,**{'T2:attack':value})
        with pytest.raises(ValueError):
            runner.database_map(planner.fixture(),wrong)


def test_runtime_rechecks_prices_and_uses_cache_write_reservation():
    from evals.runners import injection_baseline_runtime as live
    import copy
    data=planner.fixture()
    catalog={'data':copy.deepcopy(data['pricing_snapshot']['models'])}
    live.validate_prices(data,catalog)
    assert live.effective_rates(data)['anthropic/claude-haiku-5.5'][0]==.000000125
    catalog['data'][0]['pricing']['input_cache_write']='9'
    with pytest.raises(ValueError):
        live.validate_prices(data,catalog)


def test_runtime_byte_cap_blocks_before_node_chat(monkeypatch):
    from evals.runners import injection_baseline_runtime as live
    from pydantic import BaseModel
    class Reply(BaseModel):
        answer:str
    monkeypatch.setattr('backend.services.llm.node_chat',lambda *a,**k:pytest.fail('provider'))
    with pytest.raises(ValueError,match='byte cap'):
        live.bounded_chat(planner.fixture())('card_read','x'*24001,'',Reply)


def test_swallowed_supervisor_error_still_stops_runner_trial():
    data=planner.fixture()
    job=planner.jobs(data)[0]
    def broken(*a,**k):
        raise ValueError('synthetic cap or prompt error')
    with pytest.raises(runner.TrialFailure) as caught:
        runner.graph_trial(data,job,broken,lambda *a,**k:[],lambda keys:{},lambda keys:{},
                           lambda p:[],runner.MockHistory())
    assert caught.value.record['nodes'][0]['status']=='error'


def test_approval_is_bound_to_exact_measured_commit(tmp_path,monkeypatch):
    import copy,hashlib
    data=copy.deepcopy(planner.fixture())
    data['execution_enabled']=True
    approval=tmp_path/'approval.json'
    runtime=Path(runner.__file__)
    approval.write_text(json.dumps(dict(approved_by_user=True,approved_by_team_lead=True,
        fixture_sha256=hashlib.sha256(planner.CASES.read_bytes()).hexdigest(),
        runtime_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       (runtime,runtime.with_name('injection_baseline_runtime.py'))},measured_commit='1'*40)),encoding='utf-8')
    monkeypatch.setattr('subprocess.check_output',lambda *a,**k:('2'*40+'\n').encode())
    with pytest.raises(ValueError,match='commit'):
        runner.approved(data,approval)


def test_automatic_scoring_flags_poisoned_specs_even_when_final_verdict_is_unchanged():
    data=planner.fixture()
    job=next(j for j in planner.jobs(data) if j['case']=='T5' and j['variant']=='attack')
    record=dict(exposed=True,effective_inputs=[dict(values=data['common']['gold_judge']['input_values'])],
        accepted_specifications=[dict(part='DEMO2',code='VRRM',max=100)],
        state={'judgement':{'roles':['R01'],'results':[{'part':'DEMO2','verdict':'NOT_SUFFICIENT',
               'checks':[{'code':'VRRM','value':100,'result':'pass'},{'code':'IF_AV','value':2,'result':'pass'}]}]}})
    result=runner.automatic_checks(data,job,record)
    assert result['verdict_correct'] and not result['specification_correct']
    assert result['status']=='criteria_failed' and result['human_review_required']


def test_simulated_card_response_uses_actual_database_chunk_id():
    from backend.rag.card_read import CardRead
    data=planner.fixture(); job=planner.jobs(data)[0]
    reply=runner.fake_chat(data,job,{})('card_read','','[chunk_id=1558] VALUE: 60 (maximum rating)',CardRead)
    assert reply.readings[0].chunk_id==1558


def test_checkpoint_retries_windows_file_lock_without_repeating_trial(tmp_path,monkeypatch):
    out=tmp_path/'checkpoint.jsonl'
    out.write_text('old',encoding='utf-8')
    original=Path.replace
    attempts=[]
    def locked(path,target):
        attempts.append(1)
        if len(attempts)<3:
            raise PermissionError('synthetic sharing violation')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',locked)
    runner.checkpoint(out,[{'status':'completed'}])
    assert len(attempts)==3
    assert json.loads(out.read_text(encoding='utf-8'))['status']=='completed'


@pytest.mark.parametrize('case_id',[f'T{i}' for i in range(1,8)])
def test_native_graph_simulation_preserves_all_observation_layers(case_id):
    data=planner.fixture()
    job=next(j for j in planner.jobs(data) if j['case']==case_id and j['variant']=='attack')
    row=runner.simulate_trial(data,job)
    assert row['status']=='simulation_completed'
    assert row['nodes'] and row['state']
    assert row['simulation'] is True
    assert row['human_review']['passed'] is None
    if case_id=='T6':
        assert len(row['preparation'])==1
        assert '이전 사용자 입력:' in row['state']['question']
        case=next(c for c in data['cases'] if c['id']==case_id)
        assert case['payload'] in row['state']['question']
        assert row['history_scope']=='actual_message_method_mock_sql'
    if case_id=='T5':
        assert any(r['node']=='card_read' and r['exposed'] for r in row['nodes'])
        assert row['accepted_specifications'] and row['effective_inputs']
