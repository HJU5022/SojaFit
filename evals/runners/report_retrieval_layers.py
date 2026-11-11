# 사전 등록 비교(C1~C11, C3은 BM25만 − dense만)의 값을 out/layer1~4.json에서 뽑아 out/report.json에 남기고 20줄 이하로 찍는다.
# 하지 않는 일: 새 검색, API 호출. 판정 규칙은 run_retrieval_layers.py verdict()와 같다(순 차이 ±5 + 부트스트랩 95% 구간, seed 0).
# 근거: docs/research/retrieval-layered-rerun-2026-11-03.md 판정 규칙 · 비교와 기대
# 실행(저장소 루트): uv run python -m evals.runners.report_retrieval_layers   (LAYERS_WORK 폴더의 out/layer1~4.json을 읽음)
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get('LAYERS_WORK', '../전자_데이터시트/evidence/full_grid')) / 'out'
L = {n: {c['name']: c for c in json.load(open(OUT / f'layer{n}.json'))['cells']} for n in (1, 2, 3, 4)}
ALL = {k: v for n in (1, 2, 3, 4) for k, v in L[n].items()}


def nm(Q='Q2', F='part', S='hybrid', T='T0', k=60, n=50, ch='C', m='te3s', rr='-'):
    return f'{Q}|{F}|{S}|{T}|k{k}n{n}|{ch}|{m}|{rr}'


def v(a, b, metric):
    """b − a: (판정, 순 차이, 평균 차이)."""
    A, B = ALL[a]['rows'], ALL[b]['rows']
    if metric not in A[0] or metric not in B[0]:
        return ('n/a', 0, None)
    d = np.array([y[metric] - x[metric] for x, y in zip(A, B)])
    net = int((d > 0).sum() - (d < 0).sum())
    lo, hi = np.percentile(np.random.default_rng(0).choice(d, (10_000, len(d))).mean(1), [2.5, 97.5])
    return ('개선' if net >= 5 and lo > 0 else '악화' if net <= -5 and hi < 0 else '같음', net, round(float(d.mean()), 3))


def s(name, *keys):
    return {k: ALL[name]['summary'].get(k) for k in keys}


R = {}
R['C1_base'] = s(nm(), 'recall@5', 'mrr@5', 'page@5', 'ndcg@5', 'page@1', 'page@10')
R['C2_filter'] = {'bm25_Q1_mrr': v(nm('Q1', 'none', 'bm25'), nm('Q1', 'part', 'bm25'), 'mrr@5'),
                  'hybrid_Q2_page': v(nm(F='none'), nm(), 'page@5'), 'hybrid_Q2_mrr': v(nm(F='none'), nm(), 'mrr@5')}
models = json.load(open(OUT / 'layer3.json'))['models']
c3 = {}
for Q, F in (('Q2', 'none'), ('Q1', 'none'), ('Q2', 'part')):
    met = 'page@5' if F == 'part' else 'mrr@5'
    c3[f'{Q}_{F}'] = {m: v(nm(Q, F, 'dense', m=m), nm(Q, F, 'bm25'), met) for m in models
                      if nm(Q, F, 'dense', m=m) in ALL and nm(Q, F, 'bm25') in ALL}
R['C3_bm25_minus_dense'] = c3
R['C4_C5_query_vs_Q2'] = {Q: {'hybrid_part_page': v(nm(), nm(Q), 'page@5'), 'hybrid_part_ndcg': v(nm(), nm(Q), 'ndcg@5'),
                              'bm25_none_mrr': v(nm(F='none', S='bm25'), nm(Q, 'none', 'bm25'), 'mrr@5'),
                              'hybrid_none_mrr': v(nm(F='none'), nm(Q, 'none'), 'mrr@5')}
                          for Q in ('Q3', 'Q4', 'Q5', 'Q6', 'Q7')}
W = json.load(open(OUT / 'layer2.json'))['winner']
var2 = {n: (c.get('axis'), c.get('base')) for n, c in L[2].items() if c.get('base')}
R['C6_C7_C8_C9_layer2'] = {n: {'axis': a, 'page': v(b, n, 'page@5'), 'ndcg': v(b, n, 'ndcg@5'), 'mrr': v(b, n, 'mrr@5')}
                           for n, (a, b) in var2.items() if b == W}
R['C10_models_at_W'] = {m: {'page': v(W, nm('Q3', m=m), 'page@5'), 'ndcg': v(W, nm('Q3', m=m), 'ndcg@5')}
                        for m in models if nm('Q3', m=m) in ALL and m != 'te3s'}
R['C10_models_Q1none_hybrid_mrr'] = {m: s(nm('Q1', 'none', m=m), 'mrr@5')['mrr@5'] for m in models if nm('Q1', 'none', m=m) in ALL}
R['C11_rerank_at_W'] = {rr: {'page': v(W, nm('Q3', rr=rr), 'page@5'), 'ndcg': v(W, nm('Q3', rr=rr), 'ndcg@5')}
                        for rr in ('rerank-3', 'rerank-3-lite', 'bge-reranker-v2-m3') if nm('Q3', rr=rr) in ALL}
R['final'] = json.load(open(OUT / 'final.json'))
json.dump(R, open(OUT / 'report.json', 'w'), ensure_ascii=False, indent=1)

cnt = lambda d: dict(zip(*np.unique([x[0] for x in d.values()], return_counts=True))) if d else {}  # noqa: E731
print('C1', R['C1_base'])
print('C2', R['C2_filter'])
for k, d in c3.items():
    print('C3', k, {kk: int(vv) for kk, vv in cnt(d).items()}, {m: x[2] for m, x in d.items()})
for Q, d in R['C4_C5_query_vs_Q2'].items():
    print('C4/5', Q, {k: x[:2] for k, x in d.items()})
print('2층', {n.split('|')[1] + '|' + n.split('|')[3] + '|' + n.split('|')[4] + '|' + n.split('|')[5]: (x['page'][0], x['ndcg'][0], x['mrr'][1])
              for n, x in R['C6_C7_C8_C9_layer2'].items()})
print('C10', {m: (x['page'][0], x['ndcg'][0]) for m, x in R['C10_models_at_W'].items()})
print('C10 Q1none', R['C10_models_Q1none_hybrid_mrr'])
print('C11', {r: (x['page'][0], x['ndcg'][0], x['ndcg'][1]) for r, x in R['C11_rerank_at_W'].items()})
