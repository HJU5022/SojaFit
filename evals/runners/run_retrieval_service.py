"""서비스 경로 재측정(사전 등록 #26): 실제 `backend.rag.retrieve.retrieve()`로 R1 84문항과 v2 19문항을 잰다.

- 하는 일
  - R1 84문항(고정 Q3 질의, 품번은 find_parts)과 v2 채점 19문항(run_retrieval_d3의 qrels · 고정 Q3 · 같은 품번 규칙)을 `retrieve(질의, k=20, parts)`로 부른다(DEMO_MODE=0).
  - 돌려받은 (파일, 쪽)으로 Page Hit · Page Recall · Full Recall(k = 1 · 3 · 5 · 10 · 20)와 Page MRR을 계산한다(정의는 run_retrieval_d3.metrics와 같다).
  - R1 1위 칸(`r1_2026-11-03.json`)의 문항별 상위 5개 (문서, 쪽)과 견줘 같은 문항 수와 다른 문항 목록을 낸다.
  - retrieve() 한 번의 시간(p50 · p95 · 최대)과, R1 질문 20개에 실제 `rewrite()`를 한 번씩 부른 시간. OpenRouter 지출은 키 사용액 차이로 잰다(상한 1달러).
  - `--out`으로 결과 파일 경로를, `--prereg`로 meta에 적을 사전 등록 번호를 바꾼다(비트 후보 검색 측정 #27). 기본은 그대로.
  - `--compare A B`: DB · API 없이 결과 파일 둘(정확 검색 A, 비트 후보 B)의 문항별 상위 5개 (문서, 쪽) 같음, Page Recall@5 합계, retrieve() 시간 p50 · p95를 견줘 찍는다.
- 하지 않는 일: 검색 코드 · 평가셋 수정, 칸 비교(그건 run_retrieval_r1.py).
- 출처: evals/guides/preregister.md #26 · #27, evals/runners/run_retrieval_r1.py(spent), run_retrieval_d3.py(metrics · v2_questions)
- 실행(저장소 루트, DATABASE_URL · VOYAGE_API_KEY · OPENROUTER_API_KEY 필요): uv run python -m evals.runners.run_retrieval_service
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

from evals.runners import run_retrieval_d3 as D3

ROOT = D3.ROOT
KS = (1, 3, 5, 10, 20)
WINNER = 'C|v4large|hybrid|bm25|T0|60|50|Q3|part+kind|rerank-3'  # 사전 등록 #25 1위 칸
R1_DATA, R1_REWRITE = ROOT / 'evals/samples/retrieval_r1.jsonl', ROOT / 'evals/samples/retrieval_r1_rewrite_q3.json'
R1_RESULT = ROOT / 'evals/results/retrieval/r1_2026-11-03.json'
V2_REF = 0.8246  # 사람 판정 19문항 Page Recall@5(전자_데이터시트/evidence/r1/v2check/v2check_2026-11-03.json)
CAP = 1.0  # [주의] 사전 등록 #26 예산 · 중단: OpenRouter는 이 측정 합계 1달러를 넘기지 않는다
KEYS = [f'{m}@{k}' for m in ('page_hit', 'page_recall', 'all_evidence') for k in KS] + ['page_mrr']


def metrics(found, gold, rec=None):
    """돌려받은 (파일, 쪽) 목록 하나의 지표. 정의는 D3.metrics와 같다(rec가 있으면 회수 가능 쪽만 센 `_rec`도)."""
    G = set(gold)
    first = next((i + 1 for i, f in enumerate(found) if f in G), None)
    m = {'page_mrr': 1 / first if first and first <= 10 else 0.0}  # D3.metrics처럼 10위 밖은 0
    for k in KS:
        hit = {f for f in found[:k] if f in G}
        m[f'page_hit@{k}'], m[f'page_recall@{k}'], m[f'all_evidence@{k}'] = float(bool(hit)), len(hit) / len(G), float(hit == G)
        if rec is not None:
            RG = set(rec)
            m[f'page_recall_rec@{k}'] = len(hit & RG) / len(RG) if RG else None
    return m


def mean(rows, keys):
    ok = [r for r in rows if 'error' not in r]
    return {k: round(sum(r[k] for r in ok if r.get(k) is not None) / max(1, sum(r.get(k) is not None for r in ok)), 4) for k in keys}


def pct(vals, p):
    """가까운 순위(nearest rank) 백분위. 값이 없으면 None."""
    s = sorted(vals)
    return round(s[max(0, math.ceil(p / 100 * len(s)) - 1)], 3) if s else None


def latency(vals):
    return {'n': len(vals), 'p50': pct(vals, 50), 'p95': pct(vals, 95), 'max': round(max(vals), 3) if vals else None}


def parity(rows, r1_rows):
    """문항마다 상위 5개 (문서, 쪽) 목록을 R1 1위 칸의 top과 견준다. 같은 순서까지 같으면 같음으로 센다."""
    r1 = {r['id']: [(t[2], t[3]) for t in r['top'][:5]] for r in r1_rows}
    same, diff = 0, []
    for r in rows:
        if 'error' in r:
            continue
        if r['top'][:5] == r1[r['id']]:
            same += 1
        else:
            diff.append({'id': r['id'], 'service': r['top'][:5], 'r1': r1[r['id']], 'same_set': set(r['top'][:5]) == set(r1[r['id']])})
    n = same + len(diff)
    return {'n': n, 'same': same, 'different': len(diff), 'same_rate': round(same / n, 4) if n else None, 'differences': diff}


def compare(a, b):
    """결과 파일 둘(dict)을 견준다. 문항마다 상위 5개 (문서, 쪽)이 같은지, Page Recall@5 합계, retrieve() 시간 p50 · p95."""
    rows = lambda o: {r['id']: [tuple(t) for t in r['top'][:5]] for r in o['r1']['rows'] + o['v2']['rows'] if 'error' not in r}
    ra, rb = rows(a), rows(b)
    ids = sorted(ra.keys() & rb.keys())
    diff = [i for i in ids if ra[i] != rb[i]]
    agg = lambda o: {'r1_dev': o['r1']['dev']['page_recall@5'], 'r1_test': o['r1']['test']['page_recall@5'], 'v2': o['v2']['summary']['page_recall@5']}
    lat = lambda o: {k: o['latency']['retrieve'][k] for k in ('p50', 'p95')}
    return {'n': len(ids), 'same': len(ids) - len(diff), 'same_rate': round(1 - len(diff) / len(ids), 4) if ids else None, 'different_ids': diff,
            'only_in_one': sorted(ra.keys() ^ rb.keys()), 'page_recall@5': {'a': agg(a), 'b': agg(b)}, 'retrieve_sec': {'a': lat(a), 'b': lat(b)}}


def doc_name(res, names, keymap):
    """돌려받은 file이 정답 페이지 이름 집합에 없고 document_key가 대응되면 그 이름으로 바꾼다. (이름, 바꿨는지)."""
    if res['file'] in names or res['document_key'] not in keymap:
        return res['file'], False
    return keymap[res['document_key']], True


def run_questions(qs, retrieve, names, keymap):
    """질문마다 retrieve()를 한 번 부르고 시간과 지표를 적는다. 오류는 그 문항만 건너뛴다(종류 이름만 남김, 접속 정보 방지)."""
    rows = []
    for q in qs:
        t = time.perf_counter()
        try:
            res = retrieve(q['text'], k=20, parts=q['parts'] or None)
        except Exception as e:
            rows.append({'id': q['id'], 'error': type(e).__name__})
            continue
        sec = time.perf_counter() - t
        named = [doc_name(r, names, keymap) for r in res]
        found = [(n, r['page']) for (n, _), r in zip(named, res)]
        rows.append({'id': q['id'], 'sec': round(sec, 3), 'n_results': len(res), 'name_mapped': sum(m for _, m in named),
                     'top': found[:10], **metrics(found, q['gold'], q.get('rec'))})
    return rows


def usage():
    """OpenRouter 키 누적 사용액(달러). 키가 없으면 None."""
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        return None
    import httpx
    return float(httpx.get('https://openrouter.ai/api/v1/key', timeout=20, headers={'Authorization': f'Bearer {key}'}).json()['data']['usage'])


def over_cap(spent, cap=CAP):
    return spent is not None and spent >= cap


def time_rewrites(questions, rewrite, start):
    """R1 질문마다 실제 rewrite()를 부른 시간. 호출 전마다 지출을 보고 상한이면 거기서 멈춘다."""
    secs, stopped = [], False
    for q in questions:
        now = usage()
        if over_cap(None if now is None or start is None else now - start):
            stopped = True
            break
        t = time.perf_counter()
        rewrite({'question': q})
        secs.append(time.perf_counter() - t)
    return secs, stopped


def r1_questions(find_parts):
    rw = json.load(open(R1_REWRITE, encoding='utf-8'))['queries']
    return [{'id': r['id'], 'split': r['split'], 'question': r['question'], 'text': rw[r['id']], 'parts': find_parts(r['question'], set()),
             'gold': [tuple(g) for g in r['gold']]} for r in (json.loads(l) for l in open(R1_DATA, encoding='utf-8') if l.strip())]


def summary_line(label, got, want):
    return f'{label}: ' + ' | '.join(f'{k} {got[k]:.4f} (R1 {want[k]:.4f}, {got[k] - want[k]:+.4f})' for k in want)


def main(out_path=None, prereg='#26'):
    os.environ['DEMO_MODE'] = '0'  # [주의] llm이 import 때 읽으므로 backend를 부르기 전에 정한다. 모듈 최상단에서 하면 import만 해도 다른 시험이 바뀐다
    from backend.graph.nodes import find_parts, rewrite
    from backend.rag import retrieve as R
    from backend.rag.pipeline.chunk import doc_key
    from backend.services import llm
    if llm.DEMO_MODE:
        sys.exit('DEMO_MODE가 꺼지지 않았다')
    r1 = json.load(open(R1_RESULT, encoding='utf-8'))
    win = {s: next(c for c in r1[f'{s}_cells'] if c['name'] == WINNER) for s in ('dev', 'test')}
    qs = r1_questions(find_parts)
    v2 = [{'id': q['id'], 'text': q['text']['Q3'], 'parts': q['parts'], 'gold': q['gold'], 'rec': q['rec']} for q in D3.v2_questions()]
    names = {g[0] for q in qs + v2 for g in q['gold']} | {t[2] for c in win.values() for r in c['rows'] for t in r['top']}
    keymap = {doc_key(n): n for n in names}
    start = usage()
    t = time.perf_counter()
    R.warmup()  # [왜] 첫 호출이 BM25 색인을 만드느라 느리다. 시간 측정에서 빼고 따로 적는다
    warm = round(time.perf_counter() - t, 2)
    out = {'meta': {'preregister': prereg, 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'config': WINNER, 'k': 20, 'warmup_sec': warm,
                    'commit': subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()}}
    r1_rows = run_questions(qs, R.retrieve, names, keymap)
    v2_rows = run_questions(v2, R.retrieve, names, keymap)
    split = {q['id']: q['split'] for q in qs}
    agg = {'dev': mean([r for r in r1_rows if split[r['id']] == 'dev'], KEYS), 'test': mean([r for r in r1_rows if split[r['id']] == 'test'], KEYS),
           'v2': mean(v2_rows, KEYS)}
    out['r1'] = {'rows': r1_rows, 'dev': agg['dev'], 'test': agg['test']}
    out['v2'] = {'rows': v2_rows, 'summary': agg['v2'], 'summary_rec': mean(v2_rows, [f'page_recall_rec@{k}' for k in KS])}
    out['parity'] = parity(r1_rows, win['dev']['rows'] + win['test']['rows'])
    out['errors'] = {'r1': sum('error' in r for r in r1_rows), 'v2': sum('error' in r for r in v2_rows)}
    out['name_mapped'] = sum(r.get('name_mapped', 0) for r in r1_rows + v2_rows)
    out['latency'] = {'retrieve': latency([r['sec'] for r in r1_rows + v2_rows if 'sec' in r])}
    secs, stopped = time_rewrites([q['question'] for q in qs[::4][:20]], rewrite, start)
    out['latency']['rewrite'] = latency(secs) | {'stopped_by_cap': stopped}
    end = usage()
    out['openrouter_spent_usd'] = None if start is None or end is None else round(end - start, 4)
    path = ROOT / (out_path or f'evals/results/retrieval/service_r1_{time.strftime("%Y-%m-%d")}.json')
    D3.jdump(out, path)
    show = ('page_recall@5', 'page_hit@5', 'all_evidence@5')
    print(summary_line('R1 dev 46', agg['dev'], {k: win['dev']['summary'][k] for k in show}))
    print(summary_line('R1 test 38', agg['test'], {k: win['test']['summary'][k] for k in show}))
    print(f"v2 19: page_recall@5 {agg['v2']['page_recall@5']:.4f} (사람 판정 R1 {V2_REF})")
    p = out['parity']
    print(f"같음: {p['same']}/{p['n']} ({p['same_rate']}), 다른 문항 {[d['id'] for d in p['differences']]} | 오류 {out['errors']} | 이름 대응 {out['name_mapped']}")
    print(f"retrieve {out['latency']['retrieve']} | rewrite {out['latency']['rewrite']} | OpenRouter {out['openrouter_spent_usd']}달러 | 결과 {path.relative_to(ROOT)}")


def stages(n, out_path):
    """사전 등록 #28: R1 앞 n문항의 retrieve()를 재며 Voyage 질문 임베딩 · rerank-3 호출 시간을 나눠 재고 rerank 토큰을 센다.
    나머지(전체 − 임베딩 − 리랭크)는 DB 검색(비트 후보 + 정확 재정렬) · BM25 · RRF · 본문 읽기다."""
    os.environ['DEMO_MODE'] = '0'
    from backend.graph.nodes import find_parts
    from backend.rag import retrieve as R
    from backend.services import llm
    qs = r1_questions(find_parts)[:n]
    R.warmup()
    sec, tokens, post = {'embed': [], 'rerank': [], 'total': []}, [], llm._voyage_post

    def timed_post(path, payload):
        """[왜] voyage_embed · voyage_rerank가 모두 _voyage_post를 지나므로 여기서 호출 시간과 usage를 잡는다."""
        t = time.perf_counter()
        d = post(path, payload)
        sec['embed' if path == 'embeddings' else 'rerank'].append(time.perf_counter() - t)
        if path == 'rerank':
            tokens.append((d.get('usage') or {}).get('total_tokens'))
        return d
    llm._voyage_post = timed_post
    try:
        for q in qs:
            t = time.perf_counter()
            R.retrieve(q['text'], k=20, parts=q['parts'] or None)
            sec['total'].append(time.perf_counter() - t)
    finally:
        llm._voyage_post = post
    assert len(sec['embed']) == len(sec['rerank']) == len(sec['total']) == n, {k: len(v) for k, v in sec.items()}
    sec['db_bm25_rrf'] = [a - b - c for a, b, c in zip(sec['total'], sec['embed'], sec['rerank'])]
    out = {'meta': {'preregister': '#28', 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'n': n, 'config': WINNER,
                    'commit': subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()},
           'latency': {k: latency(v) for k, v in sec.items()}, 'rerank_tokens': {'per_call': latency(tokens), 'total': sum(tokens)},
           'raw': {k: [round(x, 4) for x in v] for k, v in sec.items()} | {'rerank_tokens': tokens}}
    path = ROOT / (out_path or f'evals/results/retrieval/service_stages_{time.strftime("%Y-%m-%d")}.json')
    D3.jdump(out, path)
    for k, v in out['latency'].items():
        print(f'{k:12s} {v}')
    print('rerank 토큰', out['rerank_tokens'], '| 결과', path.relative_to(ROOT))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', type=int, help='R1 앞 N문항으로 단계별 시간(질문 임베딩 · 리랭크 · 나머지)과 rerank 토큰만 잰다(사전 등록 #28)')
    ap.add_argument('--out', help='결과 JSON 경로(저장소 루트 기준). 기본 evals/results/retrieval/service_r1_<날짜>.json')
    ap.add_argument('--prereg', default='#26', help='meta에 적을 사전 등록 번호')
    ap.add_argument('--compare', nargs=2, metavar=('EXACT', 'BITS'), help='측정하지 않고 결과 파일 둘만 견준다(DB · API 안 씀)')
    args = ap.parse_args()
    if args.compare:
        print(json.dumps(compare(*(json.load(open(f, encoding='utf-8')) for f in args.compare)), ensure_ascii=False, indent=1))
    elif args.stages:
        stages(args.stages, args.out)
    else:
        main(args.out, args.prereg)
