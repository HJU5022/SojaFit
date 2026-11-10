"""Offline contract and budget checks; no provider or database requests."""
import copy
import json

import pytest

from evals.runners import plan_injection_baseline as planner


def test_remaining_smoke_selects_ten_current_jobs_with_shared_remaining_budget():
    original=planner.fixture()
    data=planner.exposure_fixture(original,'remaining_smoke')
    rows=planner.jobs(data)
    assert len(rows)==10 and {r['case'] for r in rows}=={'T2','T4','T5','T6','T7'}
    assert all(r['repeat']==1 and r['defense']=='current' for r in rows)
    assert sum(r['preparation_turns'] for r in rows)==2
    assert {r['id'] for r in rows}.isdisjoint(r['id'] for r in planner.jobs(original))
    assert data['budget_assumptions']['proposed_shared_reservation_usd']==1.36
    assert data['budget_assumptions']['proposed_shared_max_calls']==164
    assert data['budget_assumptions']['proposed_max_seconds']==480
    assert len(original['cases'])==7 and original['repeat_count']==5


def test_t7_smoke_is_two_current_jobs_with_independent_approval_and_limits():
    original=planner.fixture();data=planner.exposure_fixture(original,'t7_smoke');rows=planner.jobs(data)
    assert len(rows)==2 and {r['case'] for r in rows}=={'T7'}
    assert {r['variant'] for r in rows}=={'normal','attack'}
    assert all(r['repeat']==1 and r['defense']=='current' and r['preparation_turns']==0 for r in rows)
    assert data['scope']=='t7_smoke_v1' and not original['execution_enabled']
    assert data['budget_assumptions']['proposed_shared_reservation_usd']==2
    assert data['budget_assumptions']['proposed_shared_max_calls']==200
    assert data['budget_assumptions']['proposed_max_seconds']==1200


def test_fixed_pairs_have_110_scored_runs_and_ten_preparation_turns():
    data = planner.fixture()
    jobs = planner.jobs(data)
    assert len(jobs) == 110 and len({j['id'] for j in jobs}) == 110
    assert sum(j['variant'] == 'normal' for j in jobs) == 55
    assert sum(j['preparation_turns'] for j in jobs) == 10
    assert {c['id']:sum(j['case'] == c['id'] for j in jobs) for c in data['cases']} == {
        'T1':20,'T2':20,'T3':20,'T4':10,'T5':20,'T6':10,'T7':10}
    assert jobs[0]['case'] == 'T5'
    for job in jobs:
        mate = [j for j in jobs if j['pair_key'] == job['pair_key']]
        assert {j['variant'] for j in mate} == {'normal','attack'}


def test_exposure_scope_is_four_current_jobs_with_independent_budget():
    original=planner.fixture()
    baseline_enabled=original['execution_enabled']
    data=planner.exposure_fixture(original)
    rows=planner.jobs(data)
    assert len(rows)==4 and {r['case'] for r in rows}=={'T1','T3'}
    assert all(r['repeat']==1 and r['defense']=='current' and r['preparation_turns']==0 for r in rows)
    assert data['execution_enabled'] is original['exposure_pilot']['execution_enabled']
    assert original['execution_enabled'] is baseline_enabled
    assert len(planner.jobs(original))==110
    assert {r['id'] for r in rows}.isdisjoint(r['id'] for r in planner.jobs(original))
    budget=planner.budget(data,rows)
    assert budget['unique_embedding_texts']==1558
    assert budget['graph_invocations']==4 and budget['logical_llm_calls']==12
    assert budget['searches']==6 and budget['reservation_cap_usd']==2
    assert budget['max_calls']==200 and budget['max_seconds']==1200
    assert budget['no_retry_total_reservation_usd']<2
    assert planner.scope_sha256(data)!=planner.scope_sha256(original)
    original['exposure_pilot']['execution_enabled']=True
    assert planner.exposure_fixture(original)['execution_enabled'] is True
    assert original['execution_enabled'] is baseline_enabled
    original['exposure_pilot']['execution_enabled']=False
    assert planner.exposure_fixture(original)['execution_enabled'] is False


@pytest.mark.parametrize('case_id', [f'T{i}' for i in range(1,8)])
def test_only_designated_surface_changes_and_gold_is_not_in_question(case_id):
    data = planner.fixture()
    case = next(c for c in data['cases'] if c['id'] == case_id)
    normal, attack = [planner.materialize(data, case, v) for v in ('normal','attack')]
    assert case['payload'] not in json.dumps(normal, ensure_ascii=False)
    assert case['payload'] in json.dumps(attack, ensure_ascii=False)
    changed = {key for key in normal if normal[key] != attack[key]}
    surface='snapshot_patch' if case.get('source_chunk') else dict(corpus='cards',question='question',history='prior_user_messages',
                            netlist_footprint='netlist')[case['surface']]
    assert changed == {surface}
    assert 'gold' not in normal and 'gold' not in attack
    if case_id == 'T2':
        assert normal['protected_note'] == attack['protected_note']
        for fact in data['protected_note']['facts']:
            assert fact['text'] not in case['payload'] and fact['text'] not in normal['question']


@pytest.mark.parametrize('case_id',['T1','T3'])
def test_original_corpus_cases_patch_existing_snapshot_copy_only(case_id):
    data=planner.fixture()
    case=next(c for c in data['cases'] if c['id']==case_id)
    assert case['source_chunk']['doc']=='1N4001G SERIES_P2104.pdf'
    normal,attack=[planner.materialize(data,case,v) for v in ('normal','attack')]
    assert not normal['cards'] and not attack['cards']
    assert normal['snapshot_patch']['sha256']==case['source_chunk']['sha256']
    assert attack['snapshot_patch']['text']==normal['snapshot_patch']['text']+'\n'+case['payload']
    assert case['gold']['VRRM']==1000 and '1N4007G' in normal['question']


def test_snapshot_hash_mismatch_stops_before_planning():
    data=planner.fixture()
    data['corpus_policy']['base_sha256']='0'*64
    with pytest.raises(ValueError,match='snapshot'):
        planner.jobs(data)


def test_t5_both_variants_use_native_fallback_and_preserve_true_value():
    from backend.rag.card_read import read_values, CardRead, Reading
    data = planner.fixture()
    case = next(c for c in data['cases'] if c['id'] == 'T5')
    for variant in ('normal','attack'):
        text = planner.materialize(data, case, variant)['cards']['rating']
        assert 'Part number: DEMO2' in text  # Do not accidentally apply the fallback rating to DEMO1 too.
        calls=[]
        def fake(node, system, user, schema):
            calls.append(user)
            return CardRead(readings=[Reading(part='DEMO2',code='VRRM',slot='max',value='60',unit='V',
                                             quote='VALUE: 60 (maximum rating)',chunk_id=73)])
        card=dict(chunk_id=73,document=data['common']['document'],content=text,page=1,table='Ratings',row='VRRM')
        rows,rejected=read_values([card],['VRRM'],{data['common']['document']:['DEMO1','DEMO2']},chat=fake)
        assert len(calls)==1 and rows[0]['max']==60 and rejected==[]


def test_t7_upload_parser_preserves_connectivity_but_footprint_stays_out_of_role_prompt():
    from backend.projects.netlist import normalize_netlist
    from backend.graph.netlist import parse_netlist
    from backend.graph.nodes import circuit_around
    from backend.multi_agent.agents.judge import render_read
    from backend.judge.conditions import load
    data=planner.fixture()
    case=next(c for c in data['cases'] if c['id']=='T7')
    parsed=[]
    for variant in ('normal','attack'):
        raw=planner.materialize(data,case,variant)['netlist']
        normalize_netlist(raw.encode())
        parsed.append(parse_netlist(raw))
    assert parsed[0]['nets']==parsed[1]['nets']
    part=circuit_around(parsed[1],'D1')
    assert case['payload'] in part['footprint']
    text=render_read({'target_part':part},load())
    assert case['payload'] not in text and 'D1.A(DEMO1)' in text and 'D1.K(DEMO1)' in text


def test_budget_counts_preparation_retries_cache_write_and_rerank_query_repetition():
    data=planner.fixture()
    result=planner.budget(data,planner.jobs(data))
    assert result['logical_llm_calls']==400
    assert result['logical_node_calls']=={'supervisor':120,'docs_answer':110,'synth':30,'judge_read':120,'card_read':20}
    assert result['searches']==110
    assert result['llm_attempts_if_every_call_uses_all_format_retries']==1200
    assert result['rerank_scenario_billable_tokens']==110*100*(60+100)
    assert result['scenario_llm_usd']>0 and result['no_retry_llm_reservation_usd']>result['scenario_llm_usd']
    assert result['reservation_cap_usd']==15 and not result['paid_execution_authorized']
    changed=copy.deepcopy(data)
    changed['pricing_snapshot']['models'][0]['pricing']['input_cache_write']='0.00000025'
    assert planner.budget(changed,planner.jobs(changed))['scenario_llm_usd']>result['scenario_llm_usd']


def test_free_surface_checks_separate_conditions_resume_and_metadata():
    from backend.multi_agent.agents.judge import render_read, merge_reply
    from backend.judge.conditions import load
    from backend.graph.memory import read_profile
    marker='UNTRUSTED_SURFACE_MARKER'
    text=render_read({'conditions':marker,'circuit':marker},load())
    assert f'Conditions: {marker}' in text
    assert marker not in render_read({'circuit':marker},load())
    values,_=merge_reply({'v_in_max':marker},{},{},{'v_in_max':'number'})
    assert values=={}
    calls=[]
    class Store:
        def get(self,namespace,key):
            calls.append(key)
            return None
    assert marker not in repr(read_profile({'user_id':'synthetic','approved_memories':[marker]},store=Store()))
    assert calls==['mounting_preference']


def test_free_netlist_metadata_is_dropped_but_target_net_names_reach_prompt():
    from backend.projects.netlist import normalize_netlist
    from backend.graph.netlist import parse_netlist
    from backend.graph.nodes import circuit_around
    from backend.multi_agent.agents.judge import render_read
    from backend.judge.conditions import load
    raw=planner.fixture()['common']['netlist']
    raw=raw.replace('(export ', '(export (design (title "DROP_TITLE_MARKER") (comment "DROP_COMMENT_MARKER")) ')
    raw=raw.replace('"INPUT"','"KEEP_NET_MARKER"')
    parsed=normalize_netlist(raw.encode()).connections
    assert 'DROP_' not in repr(parsed)
    assert 'KEEP_NET_MARKER' in render_read({'target_part':circuit_around(parse_netlist(raw),'D1')},load())


def test_plan_command_is_offline_and_does_not_overwrite(tmp_path,monkeypatch):
    monkeypatch.setattr('socket.socket.connect',lambda *a,**k:pytest.fail('network'))
    out=tmp_path/'plan.json'
    assert planner.main(['--out',str(out)])==0
    result=json.loads(out.read_text(encoding='utf-8'))
    assert result['status']=='awaiting_execution_approval' and len(result['jobs'])==110
    with pytest.raises(FileExistsError):
        planner.main(['--out',str(out)])
    with pytest.raises(SystemExit):
        planner.main(['--out',str(tmp_path/'paid.json'),'--execute'])
