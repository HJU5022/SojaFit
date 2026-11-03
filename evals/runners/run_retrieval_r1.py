"""R1 검색 측정(사전 등록 #25): 문서 구조로 정답을 정한 100문항(고르기용 50 · 확인용 50)으로 임베딩 × 필터 × 리랭커 × 질의를 전부 곱해 잰다.

하는 일
  - 검색 · 지표 · 짝 비교는 run_retrieval_d3.py(#24)의 search · metrics · run_cell · compare를 그대로 쓴다(k만 1·3·5·10·20).
  - 고르기용 50문항에서만 264칸을 줄 세워 상위 3칸을 고르고, 확인용 50문항에서 그 3칸과 지금 서비스 설정을 한 번 비교한다.
하지 않는 일: 정답 고치기, 확인용 문항으로 고르기, 청킹 · BM25 토큰 · RRF 바꾸기(#24에서 같음 · 악화로 끝남).
명령(저장소 루트에서 python -m evals.runners.run_retrieval_r1 <명령>)
  rewrite     서비스 재작성 노드로 Q3를 한 번 만들어 고정(OpenRouter, 상한 $5)
  qvec-api    API 임베딩 6종의 질문 벡터(OpenRouter · Voyage)
  gpu-qvec    GPU 임베딩 5종의 질문 벡터와 #24 벡터와의 일치 검사(desktop-gpu)
  requests    칸마다 리랭크할 후보 묶음을 모으고 Voyage는 병렬로 미리 부르고, Qwen 요청 파일을 쓴다
  gpu-rerank  Qwen3-Reranker-0.6B 요청을 GPU에서 처리(desktop-gpu)
  run         264칸 고르기 → 확인용 비교 → 결과 JSON
"""
import argparse
import ast
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals.runners import run_retrieval_d3 as D3

ROOT, OUTSIDE = D3.ROOT, D3.OUTSIDE
DATA = ROOT / 'evals/samples/retrieval_r1.jsonl'
REWRITE = ROOT / 'evals/samples/retrieval_r1_rewrite_q3.json'
WORK = OUTSIDE / '전자_데이터시트/evidence/r1'
MODELS = ['te3s', 'te3l', 'te3l1536', 'v4lite', 'v4', 'v4large', 'kure', 'qwen06', 'bgem3', 'qwen4b', 'qwen8b']
FILTERS = [None, 'part', 'part+kind']
RERANKS = [None, 'rerank-3', 'rerank-3-lite', 'Qwen/Qwen3-Reranker-0.6B']
QWEN_RR = 'Qwen/Qwen3-Reranker-0.6B'
BASE = dict(chunk='C', model='te3s', S='hybrid', kw='bm25', T='T0', rrf_k=60, n=50, Q='Q2', F='part', rerank=None)  # 지금 서비스
CAP = 5.0  # [주의] 정운 11-03 결정: OpenRouter는 이번 실험 전체 5달러를 넘기지 않는다
GPU = {'kure': ('nlpai-lab/KURE-v1', '8b418a58414668e75532ed045c22d9ca018ae2b2'),
       'qwen06': ('Qwen/Qwen3-Embedding-0.6B', '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'),
       'bgem3': ('BAAI/bge-m3', '5617a9f61b028005a4858fdac845db406aefb181'),
       'qwen4b': ('Qwen/Qwen3-Embedding-4B', '5cf2132abc99cad020ac570b19d031efec650f2b'),
       'qwen8b': ('Qwen/Qwen3-Embedding-8B', '1d8ad4ca9b3dd8059ad90a75d4983776a23d44af')}  # #24 카드 벡터를 만든 revision
D3.KS = (1, 3, 5, 10, 20)  # [왜] k는 곱하지 않고 한 번에 곡선으로 본다(#25)


def items(split=None):
    rows = [json.loads(l) for l in open(DATA, encoding='utf-8') if l.strip()]
    return [r for r in rows if split in (None, r['split'])]


def texts():
    """질문 줄(Q2)과 고정 재작성(Q3) 전부."""
    rw = json.load(open(REWRITE, encoding='utf-8'))['queries'] if REWRITE.exists() else {}
    return [r['question'] for r in items()] + [rw[r['id']] for r in items() if r['id'] in rw]


# ---------- OpenRouter 지출 ----------
def spent():
    """이번 실험을 시작한 뒤 OpenRouter 지출(달러). 시작 값은 r1/spend_start.json에 한 번 적는다."""
    import httpx
    usage = float(httpx.get('https://openrouter.ai/api/v1/key', timeout=20,
                            headers={'Authorization': f'Bearer {os.environ["OPENROUTER_API_KEY"]}'}).json()['data']['usage'])
    path = WORK / 'spend_start.json'
    if not path.exists():
        D3.jdump({'usage': usage, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}, path)
    return round(usage - json.load(open(path))['usage'], 4)


def guard():
    s = spent()
    if s >= CAP:
        raise SystemExit(f'OpenRouter 지출 {s}달러가 상한 {CAP}달러에 닿아 멈춘다')
    return s


# ---------- 1. 재작성 · 질문 벡터 ----------
def rewrite(args):
    from backend.graph.nodes import rewrite as node
    guard()
    rows = items()
    with ThreadPoolExecutor(8) as ex:
        out = dict(zip((r['id'] for r in rows), ex.map(lambda r: node({'question': r['question']})['query'], rows)))
    D3.jdump({'meta': {'node': 'backend.graph.nodes.rewrite', 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}, 'queries': out}, REWRITE)
    print('재작성', len(out), '지출', spent())


def qvec_api(args):
    import numpy as np
    from backend.services import llm
    qdir, T = Path(args.qvec_dir), list(dict.fromkeys(texts()))
    qdir.mkdir(parents=True, exist_ok=True)
    vec = D3.Vectors(args)
    for t in T:  # te3s: 서비스와 같은 embed_texts 경로(D3 Vectors.query가 없으면 불러 저장)
        vec.query('te3s', t)
    guard()
    client, provider, _ = llm._embedding_client()  # [왜] 키를 직접 다루지 않고 레포 클라이언트로 모델 이름만 바꾼다(full_grid/local.py와 같음)
    r = client.embeddings.create(model='openai/text-embedding-3-large' if provider == 'openrouter' else 'text-embedding-3-large', input=T)
    np.savez(qdir / 'qvec_te3l.npz', **{D3.sha(t)[:20]: np.asarray(x.embedding, np.float32) for t, x in zip(T, r.data)})
    import httpx
    for key, name in (('v4lite', 'voyage-4-lite'), ('v4', 'voyage-4'), ('v4large', 'voyage-4-large')):
        d = httpx.post('https://api.voyageai.com/v1/embeddings', timeout=180, headers={'Authorization': f'Bearer {os.environ["VOYAGE_API_KEY"]}'},
                       json={'input': T, 'model': name, 'input_type': 'query', 'truncation': True, 'output_dimension': 1024}).json()
        np.savez(qdir / f'qvec_{key}.npz', **{D3.sha(t)[:20]: np.asarray(x['embedding'], np.float32)
                                              for t, x in zip(T, sorted(d['data'], key=lambda x: x['index']))})
    print('API 질문 벡터', len(T), '개 × 6종, 지출', spent())


def gpu_qvec(args):
    """GPU 임베딩 5종의 질문 벡터. #24에서 쓴 질문 3개를 다시 만들어 저장된 벡터와 코사인을 재 계약(지시문 · revision)이 같은지 본다."""
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer
    tree = ast.parse((ROOT / 'evals/runners/benchmark_embeddings.py').read_text(encoding='utf-8'))
    prompt = ast.literal_eval(next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'QWEN_QUERY_PROMPT').value)
    old_dir = OUTSIDE / '전자_데이터시트/evidence/full_grid/inputs'
    old_texts = [json.loads(l)['text'] for l in open(old_dir / 'query_texts.jsonl', encoding='utf-8')] if (old_dir / 'query_texts.jsonl').exists() else []
    T, qdir, log = list(dict.fromkeys(texts())), Path(args.qvec_dir), {}
    for key, (name, rev) in GPU.items():
        try:
            kw = {'torch_dtype': torch.bfloat16}
            if key == 'qwen8b':  # [주의] 8B bf16은 16GB라 12GB GPU에 안 들어간다. 남는 층은 CPU로 나눈다(값은 같은 bf16)
                kw.update(device_map='auto', max_memory={0: '10GiB', 'cpu': '13GiB'})
            m = SentenceTransformer(name, revision=rev, device=None if key == 'qwen8b' else 'cuda', model_kwargs=kw)
            m.max_seq_length = min(m.max_seq_length, 1024)
            p = prompt if key.startswith('qwen') else None
            V = m.encode(T, prompt=p, batch_size=8, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
            np.savez(qdir / f'qvec_{key}.npz', **{D3.sha(t)[:20]: v.astype(np.float32) for t, v in zip(T, V)})
            old = dict(np.load(old_dir / f'qvec_{key}.npz')) if (old_dir / f'qvec_{key}.npz').exists() else {}
            pairs = [(t, old[D3.sha(t)[:20]]) for t in old_texts if D3.sha(t)[:20] in old][:3]
            cos = [float(np.dot(m.encode([t], prompt=p, normalize_embeddings=True)[0], o / np.linalg.norm(o))) for t, o in pairs]
            log[key] = {'model': name, 'revision': rev, 'n': len(T), 'contract_cos': [round(c, 5) for c in cos]}
            del m
            torch.cuda.empty_cache()
        except Exception as e:  # noqa: BLE001  [왜] 정운 결정: 한 모델이 안 되면 그 모델만 빼고 계속한다
            log[key] = {'skipped': f'{type(e).__name__}: {str(e)[:200]}'}
        print(key, log[key], flush=True)
    D3.jdump(log, qdir / 'gpu_qvec_log.json')


# ---------- 2. 리랭크 요청 ----------
class SortedReranker(D3.Reranker):
    """같은 후보 묶음은 순서가 달라도 한 번만 리랭크한다. [왜] 점수는 (질문, 카드) 쌍마다 따로 매겨 넣는 순서와 무관하다."""

    def order(self, model, text, cands, index):
        return super().order(model, text, sorted(cands), index)


def context(args, split=None):
    from backend.graph.nodes import find_parts
    rw = json.load(open(REWRITE, encoding='utf-8'))['queries'] if REWRITE.exists() else {}
    qs = [{'id': r['id'], 'pdf': r['doc'], 'group': r['group'], 'gold': [tuple(g) for g in r['gold']], 'rec': [tuple(g) for g in r['gold']],
           'parts': find_parts(r['question'], set()),  # 서비스 search()와 같이 질문에서 품번을 읽는다(G4는 빈 목록 → 필터 없음)
           'text': {'Q2': r['question'], 'Q3': rw.get(r['id'], r['question'])}} for r in items(split)]
    index = D3.Index(args.cards, 'C')
    kw = index.keyword

    def keyword(kind, T):
        """BM25 점수를 같은 질문 토큰이면 한 번만 계산한다. [왜] 264칸이 같은 질문 168개를 되풀이해 수십 분이 걸린다(값은 같음)."""
        bm, memo = kw(kind, T), index.__dict__.setdefault('_memo', {})
        if not hasattr(bm, '_r1_memo'):
            raw = bm.get_scores
            def get_scores(toks, raw=raw):
                key = (kind, T, tuple(toks))
                if key not in memo:  # [주의] setdefault(key, raw(toks))는 매번 raw를 계산해 버려 쓰지 않는다
                    memo[key] = raw(toks)
                return memo[key]
            bm.get_scores = get_scores
            bm._r1_memo = True
        return bm
    index.keyword = keyword
    return {'qs': qs, 'index': {'C': index}, 'vec': D3.Vectors(args), 'rr': SortedReranker(args.rerank_cache)}


def cells(rerank=True):
    out = []
    for model in MODELS:
        for F in FILTERS:
            for Q in ('Q2', 'Q3'):
                for rr in (RERANKS if rerank else [None]):
                    out.append(dict(BASE, model=model, F=F, Q=Q, rerank=rr))
    return out


def requests(args):
    """리랭크 전 후보 묶음(정렬)을 모아 Voyage는 8개씩 병렬로 미리 부르고, Qwen은 GPU 요청 파일로 쓴다."""
    ctx = context(args)
    index, rr, need = ctx['index']['C'], ctx['rr'], {}
    for cfg in cells(rerank=False):
        for q in ctx['qs']:
            try:
                top, _, _, _ = D3.search(cfg, q, ctx)
            except KeyError:  # 질문 벡터가 없는 모델(예: GPU에서 빠진 qwen8b)은 건너뛴다
                break
            if top:
                text, c = q['text'][cfg['Q']], sorted(top)
                for m in RERANKS[1:]:
                    key = D3.sha(json.dumps([m, text, [index.cards[i]['sha256'] for i in c]]))
                    if key not in rr.cache:
                        need[key] = (m, text, c)
    lock, fails = threading.Lock(), []

    def call(item):
        key, (m, text, c) = item
        try:
            rec = rr.voyage(m, text, [index.cards[i]['text'] for i in c])
        except BaseException as e:  # noqa: BLE001  [왜] 한 묶음 실패는 그 칸만 빠지게 하고 나머지는 계속한다
            fails.append(f'{type(e).__name__}: {str(e)[:120]}')
            return
        with lock:
            rr.cache[key] = {**rec, 'key': key}
            with open(rr.path, 'a') as f:
                f.write(json.dumps(rr.cache[key]) + '\n')

    voy = [(k, v) for k, v in need.items() if v[0] != QWEN_RR]
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(call, voy))
    qwen = [(k, v) for k, v in need.items() if v[0] == QWEN_RR]
    with open(WORK / 'qwen_requests.jsonl', 'w', encoding='utf-8') as f:
        for k, (m, text, c) in qwen:
            f.write(json.dumps({'key': k, 'model': m, 'text': text, 'docs': [index.cards[i]['text'] for i in c]}, ensure_ascii=False) + '\n')
    print('Voyage 새 호출', len(voy) - len(fails), '실패', len(fails), fails[:3], '토큰', rr.new_tokens, '| Qwen 요청', len(qwen))


def gpu_rerank(args):
    rr = D3.Reranker(args.rerank_cache)
    reqs = [json.loads(l) for l in open(WORK / 'qwen_requests.jsonl', encoding='utf-8')]
    t0 = time.time()
    with open(rr.path, 'a') as f:
        for k, r in enumerate(reqs):
            if r['key'] in rr.cache:
                continue
            rec = {**rr.qwen3(r['model'], r['text'], r['docs']), 'key': r['key']}
            f.write(json.dumps(rec) + '\n')
            if k % 200 == 0:
                print(k, len(reqs), round(time.time() - t0), 's', flush=True)
    print('Qwen 끝', len(reqs), round(time.time() - t0), 's')


# ---------- 3. 고르기 · 확인 ----------
def slim(cell):
    """결과 파일 크기를 줄인다: 문항별 후보 목록 · 순위 사전은 빼고 지표 · 상위 10만 남긴다."""
    for r in cell['rows']:
        r.pop('candidates', None)
        r['search'] = {k: v for k, v in r['search'].items() if k not in ('dense_rank', 'kw_rank')}
    return cell


def rank_key(c):
    s = c['summary']
    return (-s['page_recall@5'], -s['all_evidence@5'], -s['page_mrr'], c['name'])  # 사전 등록 #25 고르는 기준


def groups(cell):
    out = {}
    for g in ('G1', 'G2', 'G3', 'G4'):
        rows = [r for r, q in zip(cell['rows'], cell['qs_group']) if q == g]
        out[g] = {m: round(sum(r[m] for r in rows) / len(rows), 4) for m in ('page_hit@5', 'page_recall@5', 'all_evidence@5', 'page_mrr')} if rows else None
    return out


def run(args):
    import hashlib
    meta = {'preregister': '#25', 'dataset_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
            'rewrite_sha256': hashlib.sha256(REWRITE.read_bytes()).hexdigest() if REWRITE.exists() else None,
            'k': list(D3.KS), 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    res, skipped = {'meta': meta}, []
    for split in ('dev', 'test'):
        ctx = context(args, split)
        todo = cells() + [dict(BASE, S='bm25', F=None)] if split == 'dev' else [BASE] + [c['cfg'] for c in res['picked']]
        out = []
        for cfg in todo:
            try:
                c = D3.run_cell(cfg, ctx)
            except Exception as e:  # noqa: BLE001  [왜] 정운 결정: 그 칸만 건너뛰고 이유를 결과 맨 위에 적는다
                skipped.append({'split': split, 'cell': D3.name(cfg), 'reason': f'{type(e).__name__}: {str(e)[:160]}'})
                continue
            c['qs_group'] = [q['group'] for q in ctx['qs']]
            c['groups'] = groups(c)
            out.append(slim(c))
        if split == 'dev':
            oracle = next(c for c in out if c['cfg']['S'] == 'bm25')  # 답안지 검사: 단어 일치 검색만
            grid = sorted((c for c in out if c['cfg']['S'] == 'hybrid'), key=rank_key)
            res.update({'dev_cells': grid, 'dev_oracle_bm25': oracle, 'picked': grid[:3]})
            print('고르기용 1~5위')
            for c in grid[:5]:
                print(' ', c['name'], c['summary']['page_recall@5'], c['summary']['all_evidence@5'], c['summary']['page_mrr'])
            print('  답안지 검사(BM25만, 필터 없음)', oracle['summary']['page_hit@5'], oracle['summary']['page_recall@5'])
        else:
            base = out[0]
            res['test_cells'] = out
            res['test_compare'] = [{'cell': c['name'], **{m: D3.compare(base, c, m) for m in ('page_recall@5', 'page_hit@5', 'all_evidence@5')}}
                                   for c in out[1:]]
            for c, cmp in zip(out[1:], res['test_compare']):
                r = cmp['page_recall@5']
                print('확인용', c['name'], base['summary']['page_recall@5'], '→', c['summary']['page_recall@5'], r['W'], r['L'], r['T'], r['ci95'], r['verdict'])
    res['skipped'] = skipped
    D3.jdump(res, args.out)
    print('건너뜀', len(skipped), skipped[:3], '| 결과', args.out)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('cmd', choices=['rewrite', 'qvec-api', 'gpu-qvec', 'requests', 'gpu-rerank', 'run'])
    p.add_argument('--cards', default=str(OUTSIDE / 'corpus/tsc/chunks/chunks.jsonl'))
    p.add_argument('--vectors', default=str(OUTSIDE / '전자_데이터시트/evidence/full_grid/vectors'))
    p.add_argument('--qvec-dir', default=str(WORK / 'qvec'))
    p.add_argument('--chunk-dir', default=str(OUTSIDE / 'corpus/tsc/chunks/variants'))
    p.add_argument('--rerank-cache', default=str(WORK / 'rerank_cache.jsonl'))
    p.add_argument('--out', default=str(ROOT / f'evals/results/retrieval/r1_{time.strftime("%Y-%m-%d")}.json'))
    a = p.parse_args()
    os.environ.setdefault('DEMO_MODE', '0')  # [주의] 기본값 1이면 서비스 설정이 데모 모드가 된다(#24와 같음)
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    {'rewrite': rewrite, 'qvec-api': qvec_api, 'gpu-qvec': gpu_qvec, 'requests': requests, 'gpu-rerank': gpu_rerank, 'run': run}[a.cmd](a)


if __name__ == '__main__':
    main()
