"""run_gate 결과(문항 행의 stages · llm_call_log · voyage)를 단계별 p50 · p95 · 호출당 비용 · 질문당 비용으로 모은다(D8 8장 표).

- 역할: 결과 파일(`set<N>.json`) 하나 이상을 읽어 표(마크다운)와 요약 JSON을 만든다. 모델 호출 없음, 읽기 전용.
- 통계 정의(한 가지로 통일): p50 = 진짜 중앙값(짝수 개면 가운데 두 값의 평균), p95 = 가장 가까운 순위(올림(0.95n)번째 값).
  실행기의 `summary.p50_s`는 `sorted(latency)[n//2]`(아래쪽 가운데가 아니라 위쪽 가운데 값)라 짝수 n에서 다르다. 이 모듈은 실행기 값을 `runner_p50_s`로 따로 적는다.
- 비용: LLM은 공급자(OpenRouter)가 응답에 실은 `cost` 합이고, 리랭크는 토큰 × RERANK_USD_PER_TOKEN이다. 임베딩 가격은 저장소에 없어 토큰만 적고 비용에 넣지 않는다.
- 하지 않는 일: 질문 · 답 본문 읽기(행의 `answer`는 건드리지 않는다), 실제 청구액 대조.
- 실행(저장소 루트): uv run python -m scripts.eval.stage_report <set1.json ...> [--retrieval <service_stages.json>] [--out <요약.json>]
"""
import argparse
import json
import math
import statistics
import sys
from collections import defaultdict

RERANK_USD_PER_TOKEN = 0.05 / 1_000_000  # rerank-3 가격표 100만 토큰당 0.05달러(EVAL_REPORT 8장과 같은 값, 저장소에 가격 파일 없음)


def median(values):
    return statistics.median(values) if values else None


def p95(values):
    """가장 가까운 순위: 정렬한 값의 올림(0.95n)번째(1부터)."""
    s = sorted(values)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)] if s else None


def dist(values, digits=3):
    return {'n': len(values), 'p50': None if not values else round(median(values), digits),
            'p95': None if not values else round(p95(values), digits)}


def summarize(rows):
    """결과 행 목록 → 요약 dict."""
    rows = [r for r in rows if 'latency_s' in r]
    lat = [r['latency_s'] for r in rows]
    stage_s, stopped = defaultdict(list), defaultdict(int)
    for r in rows:
        for s in r.get('stages') or []:
            if s['status'] == 'ok':  # [왜] 조건 질문으로 멈춘(interrupted) 호출은 끝까지 돈 시간이 아니라 횟수만 따로 센다
                stage_s[s['stage']].append(s['elapsed_ms'] / 1000)
            else:
                stopped[s['stage']] += 1
    llm = defaultdict(list)
    per_q_cost, missing_cost = [], 0
    for r in rows:
        cost = 0.0
        for c in r.get('llm_call_log') or []:
            llm[c['node']].append(c)
            if c['cost_usd'] is None:
                missing_cost += 1
            else:
                cost += c['cost_usd']
        rerank_tokens = sum(v['tokens'] or 0 for v in r.get('voyage') or [] if v['kind'] == 'rerank')
        per_q_cost.append({'llm': cost, 'rerank': rerank_tokens * RERANK_USD_PER_TOKEN})
    search = {'total': [], 'embed': [], 'rerank': [], 'db_bm25_rrf': []}
    for r in rows:
        total = sum(s['elapsed_ms'] for s in r.get('stages') or [] if s['stage'] == 'search') / 1000
        if not total:
            continue
        v = r.get('voyage') or []
        e, k = (sum(x['seconds'] for x in v if x['kind'] == kind) for kind in ('embed', 'rerank'))
        search['total'].append(total), search['embed'].append(e), search['rerank'].append(k)
        search['db_bm25_rrf'].append(total - e - k)
    node = lambda name: {  # noqa: E731
        'calls': len(llm[name]), 'questions': sum(any(c['node'] == name for c in r.get('llm_call_log') or []) for r in rows),
        'seconds': dist([c['seconds'] for c in llm[name]]),
        'usd_per_call': round(sum(c['cost_usd'] or 0 for c in llm[name]) / len(llm[name]), 6),
        'input_tokens_mean': round(statistics.mean(c['input_tokens'] or 0 for c in llm[name])),
        'output_tokens_mean': round(statistics.mean(c['output_tokens'] or 0 for c in llm[name])),
        'cached_tokens_mean': round(statistics.mean(c.get('cached_tokens') or 0 for c in llm[name])),
        'usd_total': round(sum(c['cost_usd'] or 0 for c in llm[name]), 6), 'models': sorted({c['model'] or '' for c in llm[name]})}
    q_total = [c['llm'] + c['rerank'] for c in per_q_cost]
    return {
        'questions': len(rows), 'passed': sum(bool(r.get('pass')) for r in rows), 'errors': sum('error' in r for r in rows),
        'latency_s': {**dist(lat, 2), 'p50_definition': 'true median', 'p95_definition': 'nearest rank ceil(0.95n)',
                      'runner_p50_s': round(sorted(lat)[len(lat) // 2], 2) if lat else None},
        'stages_s': {name: dist(v) for name, v in sorted(stage_s.items(), key=lambda kv: -len(kv[1]))},
        'stages_not_ok': dict(stopped),
        'latency_s_by_kind': {k: dist([r['latency_s'] for r in rows if r.get('kind') == k], 2) for k in ('relevant', 'irrelevant')},
        'search_s': {k: dist(v) for k, v in search.items()},
        'llm_by_node': {name: node(name) for name in sorted(llm)},
        'cost_usd': {'llm_total': round(sum(c['llm'] for c in per_q_cost), 5), 'rerank_total': round(sum(c['rerank'] for c in per_q_cost), 5),
                     'per_question_mean': round(statistics.mean(q_total), 6) if q_total else None,
                     'per_question_p50': round(median(q_total), 6) if q_total else None, 'per_question_p95': round(p95(q_total), 6) if q_total else None,
                     'llm_calls': sum(len(v) for v in llm.values()), 'llm_calls_without_reported_cost': missing_cost},
        'voyage_call_s': {kind: dist([v['seconds'] for r in rows for v in r.get('voyage') or [] if v['kind'] == kind]) for kind in ('embed', 'rerank')},
        'voyage': {'embed_tokens': sum(v['tokens'] or 0 for r in rows for v in r.get('voyage') or [] if v['kind'] == 'embed'),
                   'rerank_tokens': sum(v['tokens'] or 0 for r in rows for v in r.get('voyage') or [] if v['kind'] == 'rerank'),
                   'calls': sum(len(r.get('voyage') or []) for r in rows)}}


def markdown(s):
    out = [f"문항 {s['questions']}개, 통과 {s['passed']}, 오류 {s['errors']}", '',
           f"전체 응답 p50 {s['latency_s']['p50']}초 · p95 {s['latency_s']['p95']}초 (실행기 p50 정의 {s['latency_s']['runner_p50_s']}초)", '',
           '| 노드 단계 | 횟수 | p50(초) | p95(초) |', '|---|---|---|---|']
    out += [f"| {k} | {v['n']} | {v['p50']} | {v['p95']} |" for k, v in s['stages_s'].items()]
    out += ['', '| 검색 구간 | 횟수 | p50(초) | p95(초) |', '|---|---|---|---|']
    out += [f"| {k} | {v['n']} | {v['p50']} | {v['p95']} |" for k, v in s['search_s'].items()]
    out += ['', '| LLM 노드 | 호출 | 문항 | p50(초) | p95(초) | 호출당 USD | 입력 토큰 | 출력 토큰 | 캐시 토큰 |', '|---|---|---|---|---|---|---|---|---|']
    out += [f"| {k} | {v['calls']} | {v['questions']} | {v['seconds']['p50']} | {v['seconds']['p95']} | {v['usd_per_call']} | "
            f"{v['input_tokens_mean']} | {v['output_tokens_mean']} | {v['cached_tokens_mean']} |" for k, v in s['llm_by_node'].items()]
    out += ['', f"비용 {json.dumps(s['cost_usd'], ensure_ascii=False)}", f"Voyage {json.dumps(s['voyage'])}", f"Voyage 호출당 초 {json.dumps(s['voyage_call_s'])}", f"종류별 응답 {json.dumps(s['latency_s_by_kind'], ensure_ascii=False)}", f"멈춘(interrupted) 호출 {json.dumps(s['stages_not_ok'], ensure_ascii=False)}", f"대신한 행 {s.get('replaced_rows')}"]
    return '\n'.join(out)


def merge_rows(row_lists):
    """결과 파일 여러 개의 행을 합친다. 같은 문항 id가 여러 번 나오면 뒤 파일의 행이 앞 행을 대신한다(오류로 끝난 문항을 다시 돌려 채울 때). 대신된 id를 함께 돌려준다."""
    merged, replaced = {}, []
    for rows in row_lists:
        for r in rows:
            if r['id'] in merged:
                replaced.append(r['id'])
            merged[r['id']] = r
    return list(merged.values()), replaced


def retrieval_summary(raw):
    """`run_retrieval_service --stages`의 raw 배열(질문 임베딩 · 리랭크 · 전체 · 나머지 초, rerank 토큰)을 이 모듈의 p50 · p95 정의로 다시 센다."""
    tokens = raw['rerank_tokens']
    return {**{k: dist(raw[k]) for k in ('embed', 'rerank', 'db_bm25_rrf', 'total')}, 'rerank_tokens_per_call': dist(tokens, 0),
            'rerank_usd_per_question': round(sum(tokens) / len(tokens) * RERANK_USD_PER_TOKEN, 6)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('sets', nargs='+')
    ap.add_argument('--retrieval', help='run_retrieval_service --stages 결과 파일')
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    rows, replaced = merge_rows(json.load(open(path, encoding='utf-8'))['rows'] for path in args.sets)
    s = summarize(rows)
    s['replaced_rows'] = replaced
    if args.retrieval:
        s['retrieval_stages'] = retrieval_summary(json.load(open(args.retrieval, encoding='utf-8'))['raw'])
    print(markdown(s))
    if args.retrieval:
        print('검색 단계(retrieve만)', json.dumps(s['retrieval_stages'], ensure_ascii=False))
    if args.out:
        json.dump(s, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('요약', args.out)


if __name__ == '__main__':
    sys.exit(main())
