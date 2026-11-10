"""v3 평가셋(또는 같은 형식의 dev 파일)의 검색 지표를 에이전트 검색 길 그대로 잰다(ADR 0015 목표 지표: 문서 · 쪽 Recall@5 0.95, MRR 0.95).

- 역할: 데이터시트 정답이 있는 관련 문항마다 입력 읽기(`nodes.read_input`) → 재작성(`nodes.rewrite`, LLM 1번) →
  검색 노드와 같은 품번 필터(`nodes.search`)로 `retrieve(k=10)`를 부르고, 상위 결과에서 지표를 계산한다.
  - 정의는 `run_retrieval.py`와 같다: 문서 Recall@5 = 정답 문서가 상위 5개에 하나라도 든 문항 비율, 문서 MRR = 첫 정답 문서 순위 역수 평균,
    쪽 Recall@5 = 정답 (PDF, 쪽)이 상위 5개에 하나라도 든 문항 비율, 쪽 MRR = 첫 정답 쪽 순위 역수 평균(10위 밖 0).
  - 보조: 정답 쪽 중 상위 5개에 든 비율(page_frac@5), 재작성 + 검색 시간(top5_s) p50 · p95.
  - 후보 찾기는 정답 집합(`qualifying_parts`)의 문서 · 쪽이 gold_chunks에 모두 적혀 있어 다른 문항과 같이 센다. 회로 근거만 있는 문항(역할)은 뺀다.
- 하지 않는 일: 답 작성 · 채점 · 판정(그래프는 run_gate.py), 평가셋 수정.
- 출처: ADR 0015 목표 지표, evals/runners/run_retrieval.py(정의), backend/graph/nodes.py(검색 길)

실행(저장소 루트, DATABASE_URL · VOYAGE_API_KEY · ANTHROPIC_API_KEY 또는 OPENROUTER_API_KEY 필요):
  uv run python -m evals.runners.run_retrieval_v3 <평가셋 jsonl> <결과 json>
"""
import json
import sys
import time

from evals.runners.run_retrieval import gold_locations

K = 5


def score(found: list[tuple[str, int]], gold: list[tuple[str, int]]) -> dict:
    """상위 결과 (파일, 쪽) 목록 하나의 지표."""
    docs, pages = {d for d, _ in gold}, set(gold)
    drank = next((i + 1 for i, (f, _) in enumerate(found) if f in docs), None)
    prank = next((i + 1 for i, fp in enumerate(found) if fp in pages), None)
    return {'doc_rank': drank, 'page_rank': prank,
            'doc_recall@5': float(bool(drank and drank <= K)), 'page_recall@5': float(bool(prank and prank <= K)),
            'doc_mrr': 1 / drank if drank else 0.0, 'page_mrr': 1 / prank if prank else 0.0,
            'page_frac@5': len(pages & set(found[:K])) / len(pages)}


def p(vals: list[float], q: float) -> float:
    v = sorted(vals)
    return v[min(int(q * len(v)), len(v) - 1)] if v else 0.0


def main(dataset_path: str, out_path: str) -> dict:
    """문항마다 검색 길을 돌려 지표를 내고 결과 json을 쓴다. 요약을 돌려준다."""
    from backend.graph import nodes
    from backend.rag.retrieve import retrieve, warmup
    items = [json.loads(line) for line in open(dataset_path, encoding='utf-8') if line.strip()]
    targets = [(it, gold_locations(it.get('gold_chunks') or [])) for it in items if it['kind'] == 'relevant']
    targets = [(it, g) for it, g in targets if g]
    warmup()  # [왜] BM25 색인 만들기가 첫 문항 시간에 섞이지 않게 먼저 데운다
    rows = []
    for it, gold in targets:
        t0 = time.perf_counter()
        state = nodes.read_input({'input': it['input']})
        # [왜] 문항에 고정 검색어(query)가 있으면 재작성 LLM을 부르지 않는다. 청킹 · 검색만 바꾼 비교에서 재작성의 흔들림을 뺀다(R1 Q3)
        state.update({'query': it['query']} if it.get('query') else nodes.rewrite(state))
        got = nodes.search(state, lambda q, parts=None: retrieve(q, k=10, parts=parts))
        sec = time.perf_counter() - t0
        found = [(d['file'], d['page']) for d in got['docs']]
        rows.append({'id': it['id'], 'type': it.get('question_type'), 'query': got['query'], 'parts': got['parts'],
                     'gold': gold, 'top': found, 'top5_s': round(sec, 2), **score(found, gold)})
        r = rows[-1]
        print(f"{it['id']}\t{r['type']}\tdoc {r['doc_rank']}\tpage {r['page_rank']}\t{sec:.1f}s", flush=True)
    n = len(rows)
    keys = ('doc_recall@5', 'doc_mrr', 'page_recall@5', 'page_mrr', 'page_frac@5')
    summary = {'dataset': dataset_path, 'questions': n, **{k: round(sum(r[k] for r in rows) / n, 4) for k in keys},
               'top5_s_p50': p([r['top5_s'] for r in rows], 0.5), 'top5_s_p95': p([r['top5_s'] for r in rows], 0.95),
               'by_type': {t: {k: round(sum(r[k] for r in rows if r['type'] == t) / sum(r['type'] == t for r in rows), 4) for k in keys}
                           for t in sorted({r['type'] for r in rows})}}
    json.dump({'summary': summary, 'rows': rows}, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
