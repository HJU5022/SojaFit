"""Approved baseline adapter. Imported only after the runner's approval/commit checks."""
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from uuid import uuid4

from evals.runners import run_injection_baseline as runner
from evals.runners import run_injection_preflight as pre


def verify_corpus(conn,bundle):
    from backend.rag.pipeline.chunk import doc_key
    expected={(doc_key(c['doc']),c['idx']):(c['text'],c['sha256'],c['page'],c['table'],c['row']) for c in bundle['chunks']}
    rows=conn.execute('SELECT d.document_key,c.chunk_index,c.content,trim(c.chunk_sha256),c.page_number,c.table_name,c.row_label '
                      'FROM source_documents d JOIN document_chunks c ON c.document_id=d.id').fetchall()
    actual={(r[0],r[1]):tuple(r[2:]) for r in rows}
    if actual!=expected or any(pre.sha(r[2])!=r[3] for r in rows):
        raise ValueError('Stored corpus variant or hash mismatch')
    missing=conn.execute("SELECT count(*) FROM document_chunks c LEFT JOIN chunk_embeddings e "
                         "ON e.chunk_id=c.id AND e.embedding_model='voyage-4-large' WHERE e.chunk_id IS NULL").fetchone()[0]
    if missing:
        raise ValueError('Missing voyage-4-large vectors')


def prepare_corpora(data,mapping,cache):
    """Fresh DBs only; immutable content-hash vector cache is shared across variants."""
    import psycopg
    from backend.rag.pipeline import ingest
    bundles={}
    jobs=runner.plan.jobs(data)
    for key,dsn in mapping.items():
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            pre.require_empty(conn,conn.info.dbname)
        case,variant=key.split(':')
        bundles[key]=runner.corpus_bundle(data,next(j for j in jobs if j['case']==case and j['variant']==variant))
    union=cache/'union.jsonl'
    texts={c['sha256']:c for b in bundles.values() for c in b['chunks']}
    union.write_text('\n'.join(json.dumps(c,ensure_ascii=False) for c in texts.values()),encoding='utf-8')
    ingest.fill_voyage(union,cache)
    for key,dsn in mapping.items():
        bundle=bundles[key]
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            pre.require_empty(conn,conn.info.dbname)
            for sql in ('000_init.sql','002_rag_corpus.sql','008_multi_dim_embeddings.sql',
                        '009_chunk_embedding_bits.sql','012_document_category.sql'):
                conn.execute((runner.plan.ROOT/'db'/sql).read_text(encoding='utf-8'))
        manifest,chunks=cache/'manifest.jsonl',cache/'chunks.jsonl'
        for path,rows in ((manifest,bundle['manifest']),(chunks,bundle['chunks'])):
            path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows),encoding='utf-8')
        with patch.dict(os.environ,{'DATABASE_URL':dsn,'RAG_VECTOR_TYPE':'halfvec'}):
            ingest.main(manifest,chunks,cache,chunks_only=True)
            ingest.load_voyage(cache)
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            verify_corpus(conn,bundle)
    return bundles


def effective_rates(data):
    rates={}
    for model in data['pricing_snapshot']['models']:
        p=model['pricing']
        tiers=tuple(dict(min_prompt_tokens=t['min_prompt_tokens'],
                         prompt=max(float(t['prompt']),float(t.get('input_cache_write',t['prompt']))),
                         completion=float(t['completion'])) for t in p.get('overrides',[]))
        rates[model['id']]=(max(float(p['prompt']),float(p.get('input_cache_write',p['prompt']))),
                            float(p['completion']),tiers)
    return rates


def validate_prices(data,catalog):
    current={m['id']:m['pricing'] for m in catalog['data']}
    for model in data['pricing_snapshot']['models']:
        actual=current.get(model['id'])
        if actual is None or actual!=model['pricing']:
            raise ValueError('Official model pricing changed; recalculate and obtain approval')


def bounded_chat(data):
    from backend.services import llm
    def chat(node,system,user,schema,**kwargs):
        cap=data['budget_assumptions']['request_byte_caps'].get(node,24000)
        if len((system+user+json.dumps(schema.model_json_schema())).encode())>cap:
            raise ValueError('Model input exceeds the approved byte cap')
        return llm.node_chat(node,system,user,schema,**kwargs)
    return chat


def fixed_t2_context(conn,data,job):
    """Read the fixed public/protected evidence from the verified, dedicated trial database."""
    from backend.rag.pipeline.chunk import doc_key
    filenames=(data['common']['document'],data['protected_note']['document'])
    expected={(doc_key(c['doc']),c['sha256']) for c in runner.corpus_bundle(data,job)['chunks']
              if c['doc'] in filenames and c['page'] is not None}
    rows=conn.execute('SELECT c.id,d.title,c.page_number,c.table_name,c.row_label,c.content,trim(c.chunk_sha256),d.document_key'
        ' FROM document_chunks c JOIN source_documents d ON d.id=c.document_id'
        ' WHERE d.document_key=ANY(%s) AND c.page_number IS NOT NULL ORDER BY c.id',
        ([doc_key(f) for f in filenames],)).fetchall()
    if len(rows)!=len(expected) or {(r[7],r[6]) for r in rows}!=expected or any(pre.sha(r[5])!=r[6] for r in rows):
        raise ValueError('Fixed T2 evidence differs from the registered corpus')
    return [dict(chunk_id=i,file=f,page=p,table=t,row=r,content=c,document_key=k,
                 doc_parts=data['protected_note']['parts'] if f==filenames[1] else data['common']['parts'])
            for i,f,p,t,r,c,h,k in rows]


def execute_approved(data,out):
    import httpx
    import psycopg
    from psycopg.rows import dict_row
    from urllib.request import urlopen
    from backend.rag import retrieve as rag,card_find,card_specs
    from backend.multi_agent.facts import make_lookup
    from backend.services import llm
    variable={'exposure_t1_t3_v1':'INJECTION_EXPOSURE_DATABASES',
              't3_smoke_v1':'INJECTION_T3_SMOKE_DATABASES',
              't7_smoke_v1':'INJECTION_T7_SMOKE_DATABASES',
              'remaining_smoke_v1':'INJECTION_REMAINING_SMOKE_DATABASES'}.get(data.get('scope'),'INJECTION_BASELINE_DATABASES')
    mapping=runner.database_map(data,json.loads(os.environ[variable]))
    if llm.LLM_PROVIDER!='openrouter' or any(llm.node_model(n)!=m for n,m in (
            ('supervisor','anthropic/claude-haiku-5.5'),('judge_read','anthropic/claude-haiku-5.5'),
            ('docs_answer','anthropic/claude-haiku-5.5'),('card_read','anthropic/claude-haiku-5.5'),
            ('synth','anthropic/claude-sonnet-5.5'))):
        raise ValueError('Effective model configuration differs from the approved plan')
    with urlopen(data['pricing_snapshot']['openrouter_source'],timeout=15) as response:
        validate_prices(data,json.load(response))
    a=data['budget_assumptions']
    budget=llm.EvaluationBudget(max_usd=a['proposed_shared_reservation_usd'],max_calls=a['proposed_shared_max_calls'],
                                max_seconds=a['proposed_max_seconds'],max_tokens=a['max_output_tokens'],
                                prompt_rate=.000003,completion_rate=.000015,
                                embedding_rate=a['embedding_reservation_rate'],per_model_rates=True)
    global_observer=pre.Observer(llm.node_chat)
    post=httpx.post
    def transport(url,**kwargs):
        payload=kwargs.get('json',{})
        cap=a['rerank_payload_byte_cap'] if url.endswith('/rerank') else a['query_byte_cap']
        if payload.get('input_type')!='document' and len(json.dumps(payload).encode())>cap:
            raise ValueError('Search payload exceeds the approved byte cap')
        return post(url,**kwargs)
    bundles=None
    out=Path(out)
    ledger=out.with_suffix('.budget.json')
    if out.exists() or out.with_suffix('.meta.json').exists() or ledger.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open('x',encoding='utf-8'):
        pass
    try:
        with tempfile.TemporaryDirectory(prefix='sojafit-injection-') as tmp, \
                patch.dict(llm.MODEL_RATES,effective_rates(data)),patch.object(httpx,'post',transport), \
                patch.object(rag,'_bm25',None),patch.object(rag,'_parts',None),patch.object(rag,'_nocover',None), \
                patch.object(llm,'DEMO_MODE',False),pre.observed_budget(budget,global_observer):
            def trial(job):
                nonlocal bundles
                if bundles is None:
                    token=pre._CALL.set(str(uuid4()))
                    try:
                        bundles=prepare_corpora(data,mapping,Path(tmp))
                    finally:
                        pre._CALL.reset(token)
                key=f"{job['case']}:{job['variant']}"
                dsn=mapping[key]
                with psycopg.connect(dsn,connect_timeout=5) as check:
                    verify_corpus(check,bundles[key])
                start,end=len(global_observer.requests),len(global_observer.reservations)
                try:
                    with patch.dict(os.environ,{'DATABASE_URL':dsn}):
                        rag.warmup()
                        known,revisions=rag.corpus_known()
                        def lookup(state):
                            return make_lookup(lambda ps,rs:dict(parts={p:p.lower() in known for p in ps},
                                revisions={r:r in revisions for r in rs}))(state)
                        case=next(c for c in data['cases'] if c['id']==job['case'])
                        retrieve=rag.retrieve
                        fixed=data.get('t2_context_policy')=='fixed_database_evidence_v1' and job['case']=='T2'
                        if fixed:
                            with psycopg.connect(dsn,connect_timeout=5) as context:
                                cards=fixed_t2_context(context,data,job)
                            retrieve=lambda *a,**k:cards
                        with psycopg.connect(dsn,connect_timeout=5,row_factory=dict_row) as history:
                            record=runner.graph_trial(data,job,bounded_chat(data),retrieve,
                                card_find.load_cards,card_find.doc_meta,card_specs.part_docs_index(),history,budget,lookup=lookup)
                        if fixed:
                            record['context_policy']='fixed_database_evidence_v1'
                            record['automatic']['exposure_valid']=any(n['node']=='docs_answer' and n['status']=='returned'
                                and n.get('protected_evidence_exposed') and n.get('protected_exposed')
                                and (job['variant']=='normal' or n.get('exposed')) for n in record['nodes'])
                    record.update(status='completed',simulation=False,
                                  history_scope='actual_message_method_postgres_temp_history',
                                  provider_attempts=global_observer.requests[start:],
                                  reservations=global_observer.reservations[end:])
                    return record
                except runner.TrialFailure as error:
                    error.record.update(provider_attempts=global_observer.requests[start:],
                                        reservations=global_observer.reservations[end:])
                    raise
                finally:
                    # Ledger always keeps attempts, including preparation and a partially failed trial.
                    ledger.write_text(json.dumps(dict(calls=budget.calls,reserved_usd=budget.reserved_usd,
                        attempts=global_observer.requests,reservations=global_observer.reservations),
                        ensure_ascii=False,indent=2),encoding='utf-8')
            return runner.run(data,out,'live',trial)
    finally:
        ledger.write_text(json.dumps(dict(calls=budget.calls,reserved_usd=budget.reserved_usd,
            attempts=global_observer.requests,reservations=global_observer.reservations),ensure_ascii=False,indent=2),encoding='utf-8')
