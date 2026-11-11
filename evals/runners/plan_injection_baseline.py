"""Freeze 110 paired inputs and estimate costs offline. No execute option."""
import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CASES=ROOT/'data/corpus/injection_tests/baseline_cases.json'


def fixture():
    return json.loads(CASES.read_text(encoding='utf-8'))


def exposure_fixture(data,pilot_key='exposure_pilot'):
    result=copy.deepcopy(data)
    pilot=data[pilot_key]
    result.update(scope=pilot['scope'],execution_enabled=pilot['execution_enabled'],repeat_count=1)
    result['cases']=[c for c in result['cases'] if c['id'] in pilot.get('cases',('T1','T3'))]
    for case in result['cases']:
        case['defenses']=['current']
    limits=result['budget_assumptions']
    limits.update(proposed_shared_reservation_usd=pilot['max_usd'],
                  proposed_shared_max_calls=pilot['max_calls'],proposed_max_seconds=pilot['max_seconds'])
    return result


def scope_sha256(data):
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def snapshot(data):
    raw=(ROOT/data['corpus_policy']['base']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=data['corpus_policy']['base_sha256']:
        raise ValueError('Pinned snapshot hash changed')
    rows=[json.loads(s) for s in raw.decode('utf-8').splitlines()]
    if len(rows)!=data['corpus_policy']['base_chunk_count']:
        raise ValueError('Pinned snapshot chunk count changed')
    return rows


def materialize(data,case,variant):
    common=data['common']
    result=dict(question=case.get('question',common['judge_question']),netlist=common['netlist'],
                cards=copy.deepcopy(common['cards']),prior_user_messages=[],protected_note=None)
    if source:=case.get('source_chunk'):
        rows=snapshot(data)
        row=next(c for c in rows if c['doc']==source['doc'] and c['idx']==source['idx'])
        if row['sha256']!=source['sha256'] or hashlib.sha256(row['text'].encode()).hexdigest()!=source['sha256']:
            raise ValueError('Pinned snapshot source chunk changed')
        result['cards']={}
        result['snapshot_patch']=row
    if case.get('use_fallback_rating'):
        result['cards']['rating']=common['fallback_rating']
    if case['id']=='T2':
        result['protected_note']={k:data['protected_note'][k] for k in ('document','parts','label','content')}
    if case['surface']=='history':
        result['prior_user_messages']=[case['first_turn']]
    if variant=='attack':
        payload=case['payload']
        if case['surface']=='corpus':
            if case.get('source_chunk'):
                result['snapshot_patch']['text']+='\n'+payload
                result['snapshot_patch']['sha256']=hashlib.sha256(result['snapshot_patch']['text'].encode()).hexdigest()
            else:
                result['cards'][case['card']]+='\n'+payload
        elif case['surface']=='question':
            result['question']+='\n'+payload
        elif case['surface']=='history':
            result['prior_user_messages'][0]+='\n'+payload
        elif case['surface']=='netlist_footprint':
            result['netlist']=result['netlist'].replace('"Diode:DO-41"',json.dumps('Diode:DO-41; '+payload))
        else:
            raise ValueError('Unsupported attack surface')
    elif variant!='normal':
        raise ValueError('Unknown variant')
    return result


def jobs(data):
    result=[]
    order=('T1','T3') if data.get('scope')=='exposure_t1_t3_v1' else ('T5','T1','T2','T3','T4','T6','T7')
    for case_id in order:
        if not any(c['id']==case_id for c in data['cases']):
            continue
        case=next(c for c in data['cases'] if c['id']==case_id)
        for repeat in range(1,data['repeat_count']+1):
            defenses=case['defenses'] if repeat%2 else list(reversed(case['defenses']))
            for defense in defenses:
                key=f'{case_id}:{repeat}:{defense}'
                if data.get('scope'):
                    key=f"{data['scope']}:{key}"
                for variant in ('normal','attack') if repeat%2 else ('attack','normal'):
                    inputs=materialize(data,case,variant)
                    digest=hashlib.sha256(json.dumps(inputs,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                    result.append(dict(id=f'{key}:{variant}',case=case_id,repeat=repeat,defense=defense,
                                       variant=variant,pair_key=key,input_sha256=digest,
                                       preparation_turns=case.get('preparation_turns_per_scored_run',0)))
    return result


def budget(data,rows):
    assumptions=data['budget_assumptions']
    counts=Counter()
    searches=0
    texts={}
    for card in snapshot(data):
        texts[card['sha256']]=card['text']
    for case in data['cases']:
        for variant in ('normal','attack'):
            inputs=materialize(data,case,variant)
            extra=list(inputs['cards'].values())
            if extra:
                extra.append(f"[{data['common']['document']}] 이 데이터시트의 품번: DEMO1, DEMO2")
            if inputs.get('snapshot_patch'):
                extra.append(inputs['snapshot_patch']['text'])
            if inputs['protected_note']:
                note=inputs['protected_note']
                extra += [note['content'],f"[{note['document']}] 이 데이터시트의 품번: DEMO2"]
            for text in extra:
                texts[hashlib.sha256(text.encode()).hexdigest()]=text
    for row in rows:
        counts.update(assumptions['logical_calls_per_scored_run'][row['case']])
        searches+=assumptions['searches_per_scored_run'][row['case']]
        for _ in range(row['preparation_turns']):
            counts.update(assumptions['preparation_logical_calls_per_turn'])
            searches+=assumptions['searches_per_preparation_turn']
    prices={p['id']:p['pricing'] for p in data['pricing_snapshot']['models']}
    scenario=reservation=0
    for node,count in counts.items():
        price=prices['anthropic/claude-sonnet-5.5' if node=='synth' else 'anthropic/claude-haiku-5.5']
        tokens=assumptions['scenario_tokens'][node]
        # Explicit 5-minute cache writes may cost more than uncached input; assume no read discount.
        rate=max(float(price['prompt']),float(price.get('input_cache_write',price['prompt'])))
        scenario+=count*(tokens['input']*rate+tokens['output']*float(price['completion']))
        upper=assumptions['request_byte_caps'][node]+8192
        applicable=[price,*[p for p in price.get('overrides',[]) if p['min_prompt_tokens']<=upper]]
        rate=max(float(p.get('input_cache_write',p['prompt'])) for p in applicable)
        out_rate=max(float(p['completion']) for p in applicable)
        reservation+=count*(upper*rate+assumptions['max_output_tokens']*out_rate)
    bodies=list(texts.values())
    byte_count=sum(len(t.encode()) for t in bodies)
    preparation_reserved=0
    for i in range(0,len(bodies),assumptions['ingest_batch_size']):
        payload=dict(input=bodies[i:i+assumptions['ingest_batch_size']],model='voyage-4-large',
                     input_type='document',truncation=True,output_dimension=1024)
        preparation_reserved+=(len(json.dumps(payload).encode())+8192)*assumptions['embedding_reservation_rate']
    voyage=data['pricing_snapshot']['voyage']
    embed_scenario=(byte_count/4+searches*assumptions['query_tokens'])*voyage['voyage_4_large_per_million']/1e6
    rerank_tokens=searches*assumptions['rerank_documents']*(assumptions['query_tokens']+assumptions['document_tokens'])
    rerank_scenario=rerank_tokens*voyage['rerank_3_per_million']/1e6
    search_reserved=searches*(assumptions['query_byte_cap']+assumptions['rerank_payload_byte_cap']+2*8192)*assumptions['embedding_reservation_rate']
    return dict(logical_node_calls=dict(counts),logical_llm_calls=sum(counts.values()),searches=searches,
                llm_attempts_if_every_call_uses_all_format_retries=sum(counts.values())*assumptions['max_format_attempts'],
                graph_invocations=len(rows)+sum(r['preparation_turns'] for r in rows),
                unique_embedding_texts=len(texts),embedding_text_utf8_bytes=byte_count,
                embedding_batches_without_retry=math.ceil(len(texts)/assumptions['ingest_batch_size']),
                scenario_llm_usd=round(scenario,6),scenario_embedding_usd=round(embed_scenario,6),
                scenario_rerank_usd=round(rerank_scenario,6),rerank_scenario_billable_tokens=rerank_tokens,
                scenario_total_usd=round(scenario+embed_scenario+rerank_scenario,6),
                no_retry_llm_reservation_usd=round(reservation,6),
                no_retry_voyage_preparation_reservation_usd=round(preparation_reserved,6),
                no_retry_search_reservation_usd=round(search_reserved,6),
                no_retry_total_reservation_usd=round(reservation+preparation_reserved+search_reserved,6),
                reservation_cap_usd=assumptions['proposed_shared_reservation_usd'],
                max_calls=assumptions['proposed_shared_max_calls'],max_seconds=assumptions['proposed_max_seconds'],
                paid_execution_authorized=False,completion_guaranteed=False,
                limitations=['Counts and token volumes are scenarios, not measured graph traces.',
                             'Preparation byte/4 is a token estimate, not provider tokenization.',
                             'Replans, unexpected tasks, card batches and retries consume the same cap.',
                             'Estimates depend on the live request caps and cache-write-aware reservation rates.'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--exposure-only',action='store_true')
    scope.add_argument('--remaining-smoke',action='store_true')
    scope.add_argument('--t7-smoke',action='store_true')
    scope.add_argument('--t3-smoke',action='store_true')
    args=parser.parse_args(argv)
    data=fixture()
    if args.exposure_only:
        data=exposure_fixture(data)
    elif args.remaining_smoke:
        data=exposure_fixture(data,'remaining_smoke')
    elif args.t7_smoke:
        data=exposure_fixture(data,'t7_smoke')
    elif args.t3_smoke:
        data=exposure_fixture(data,'t3_smoke')
    rows=jobs(data)
    report=dict(status='awaiting_execution_approval',fixture_sha256=hashlib.sha256(CASES.read_bytes()).hexdigest(),
                scope=data.get('scope','baseline'),scope_sha256=scope_sha256(data),
                baseline_commit=data['baseline_commit'],jobs=rows,budget=budget(data,rows),
                prerequisites=['freeze and commit input/preregistration before paid results',
                               'verify scoped actual corpus/service-history live adapter',
                               'verify retrieval/model exposure, request caps and cache-write reservation',
                               'revalidate official prices and obtain user plus team-lead budget authorization'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as output:
        json.dump(report,output,ensure_ascii=False,indent=2)
    print(json.dumps(report['budget'],ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
