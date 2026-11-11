"""C1/C2의 실제 모델 기준선. --execute만 유료, 보호 코드/DB/배포는 변경하지 않는다."""
import argparse
import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from evals.runners.run_judgement_bundle import ROOT, BUNDLE, bundle

FOCUS = ROOT/'data/corpus/injection_tests/claim_consistency_cases_v1.json'
LIMITS = {'max_usd':0.50, 'max_calls':16, 'max_seconds':90, 'max_tokens':1024}


def inputs():
    focus=json.loads(FOCUS.read_text(encoding='utf-8'))
    if hashlib.sha256(BUNDLE.read_bytes()).hexdigest()!=focus['baseline_sha256']:
        raise ValueError('Baseline fixture changed')
    return bundle(), [{'id':'control','attack_suffix':''}, *focus['cases']]


def preflight():
    from backend.services import llm
    if llm.LLM_PROVIDER!='openrouter':
        raise ValueError('OpenRouter required')
    catalog=json.load(urlopen('https://openrouter.ai/api/v1/models',timeout=15))['data']
    models={node:llm.node_model(node) for node in ('docs_answer','synth')}
    pricing={}
    for model in set(models.values()):
        p=next(m['pricing'] for m in catalog if m['id']==model)
        tiers=[p,*p.get('overrides',[])]
        if any(not math.isfinite(float(t[k])) or not 0<float(t[k])<=limit
               for t in tiers for k,limit in (('prompt',0.000003),('completion',0.000015))):
            raise ValueError('Model rates exceed reservation rates')
        pricing[model]=p
    key=os.environ['OPENROUTER_API_KEY']
    req=Request('https://openrouter.ai/api/v1/credits',headers={'Authorization':'Bearer '+key})
    credit=json.load(urlopen(req,timeout=15))['data']
    if credit['total_credits']-credit['total_usage']<LIMITS['max_usd']:
        raise ValueError('Insufficient credit for the registered cap')
    return {'models':models,'pricing':pricing,'credits_at_least_budget':True,
            'source':'https://openrouter.ai/api/v1/models'}


def measure_case(b,case,chat,record=None,*,target_part=None):
    from backend.multi_agent.agents.docs import docs_agent
    from backend.multi_agent.contracts import Task, TaskReport
    from backend.multi_agent.supervisor import collect_node,single_node,synth_node,check_node
    from backend.judge import conditions as C, verdict as V
    row=record if record is not None else {'id':case['id'],'raw':[]}
    content=b['document']['base_content']+('\n'+case['attack_suffix'] if case['attack_suffix'] else '')
    card={'chunk_id':73,'file':b['document']['file'],'page':1,'table':b['document']['table'],
          'doc_parts':['demo2'],'content':content}
    def observed(node,system,user,schema):
        attempt={'node':node,'status':'attempted','exposed':content in user,
                 'input_sha256':hashlib.sha256(user.encode()).hexdigest()}
        row['raw'].append(attempt)
        response=chat(node,system,user,schema)
        attempt.update(status='returned',output=response.model_dump(mode='json'))
        return response
    task=Task(id=1,agent='docs',kind='rating',goal='DEMO2 VRRM',query='DEMO2 VRRM',parts=['DEMO2'])
    doc=docs_agent({'task':task.model_dump(mode='json'),'question':b['question'],'target_part':target_part},
                   retriever=lambda *_a,**_kw:[card],chat=observed)['reports'][0]
    rows=[{'part':'DEMO2','code':code,'min':None,'typ':None,'max':want['value'],'text':None,
           'unit':want['unit'],'source_value_text':str(want['value']),'test_condition':None,
           'citation':{'document':b['document']['file'],'page':1,'table':b['document']['table'],'row':code}}
          for code,want in b['expected']['checks'].items()]
    j=V.judge_part(C.load()['R01'],'R01','DEMO2',b['values'],b['conditions'],rows)
    for code,want in b['expected']['checks'].items():
        c=next(c for c in j.checks if c.code==code)
        if not (c.result==want['result'] and math.isclose(c.threshold,want['threshold']) and c.value==want['value']):
            raise ValueError('Code baseline mismatch')
    if j.verdict!=b['expected']['verdict']:
        raise ValueError('Code verdict mismatch')
    judge=TaskReport(task=2,agent='judge',status='ok',summary='Code judgement',judgement={
        'kind':'judge','roles':['R01'],'role_evidence':[],'results':[j.model_dump(mode='json')]}).model_dump(mode='json')
    state={'question':b['question'],'target_part':target_part,'reports':[doc,judge],'plan':{'next':'tasks'},'round':1,
           'counters':{'hops':0,'replans':0,'agents':0,'searches':0}}
    state.update(collect_node(state))
    outcome=state['outcome']
    row.update(exposed=bool(row['raw']) and all(r['exposed'] for r in row['raw'] if r['node']=='docs_answer'),
        document_report=doc,code_verdict=j.verdict,judgement=judge['judgement'],assembly=outcome,
        semantic_review='pending_manual_review',evidence_id=73,card_sha256=hashlib.sha256(content.encode()).hexdigest())
    if outcome not in ('single','synth'):
        row.update(status='assembly_unmeasured',answer=None)
        return row
    state.update(single_node(state) if outcome=='single' else synth_node(state,chat=observed))
    state.update(check_node(state))
    row.update(status='pipeline_refused' if state.get('refusal_reason') else 'pipeline_completed',
        answer=state.get('answer'),synth_text=state.get('synth_text'),check=state.get('check'),
        refusal_reason=state.get('refusal_reason'),
        control_valid=bool(re.search(r'(?<![\d.])60(?:\.0)?\s*V(?![A-Za-z])',doc['answer'],re.I)
                           and '73' in doc['evidence_ids']))
    return row


def execute(report,save):
    from backend.services import llm
    from langchain_core.tracers.context import collect_runs
    from evals.runners.run_thread_validation import usage_rows,cost_total
    report['preflight']=preflight()
    save()
    budget=llm.EvaluationBudget(**LIMITS,prompt_rate=0.000003,completion_rate=0.000015)
    b,cases=inputs()
    with collect_runs() as traced:
        try:
            with llm.evaluation_limits(budget):
                for i,case in enumerate(cases):
                    record={'id':case['id'],'status':'attempted','raw':[]}
                    report['cases'][i]=record
                    save()
                    try:
                        budget.remaining()
                        measure_case(b,case,llm.node_chat,record)
                        budget.remaining()
                    except Exception as error:
                        record.update(status='budget_exceeded' if isinstance(error,llm.EvaluationLimitError) else 'error',
                                      error_type=type(error).__name__)
                    save()
                    if record['status']!='pipeline_completed' or not record.get('exposed') or (i==0 and not record.get('control_valid')):
                        break
        finally:
            usage=usage_rows(traced.traced_runs)
            report.update(reserved_calls=budget.calls,reserved_usd=budget.reserved_usd,
                elapsed_s=round(time.monotonic()-budget.started,3),provider_usage=usage,
                provider_reported_cost_usd=cost_total(usage),actual_billed_cost_usd=None,billing_reconciled=False)
            save()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    _,cases=inputs()
    os.environ['LANGCHAIN_TRACING_V2']='false'
    os.environ['LANGSMITH_TRACING']='false'
    files=[BUNDLE,FOCUS,Path(__file__).resolve(),ROOT/'backend/multi_agent/agents/docs.py',
           ROOT/'backend/multi_agent/supervisor.py',ROOT/'backend/multi_agent/messages.py',
           ROOT/'backend/judge/verdict.py',ROOT/'backend/judge/rules/roles.yaml',ROOT/'backend/services/llm.py',
           ROOT/'backend/prompts/docs_answer.md',ROOT/'backend/prompts/synth.md']
    report={'mode':'live-model' if args.execute else 'plan','ran_at':datetime.now(timezone.utc).isoformat(),
        'scope':'fixed docs task + code judge + current collect/single/synth/check; no DB, Supervisor planning or HTTP',
        'limits':LIMITS,'implementation':'runtime snapshot; defense assessment requires separate raw/final review',
        'runtime_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'cases':[{'id':c['id'],'status':'not_run'} for c in cases], 'semantic_summary':'pending_manual_review'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as output:
        def save():
            output.seek(0); json.dump(report,output,ensure_ascii=False,indent=2); output.truncate(); output.flush()
        save()
        if args.execute:
            try:
                execute(report,save)
            except Exception as error:
                report['error_type']=type(error).__name__
            save()
    return 2 if args.execute and (report.get('error_type') or any(c['status']!='pipeline_completed' for c in report['cases'])) else 0


if __name__=='__main__':
    raise SystemExit(main())
