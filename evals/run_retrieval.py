"""평가셋의 관련 문항으로 검색 지표(문서 Recall@k, MRR, 쪽 적중@k)를 잰다.

- 하는 일: 데이터시트 근거가 있는 관련 문항마다 backend.rag.retrieve.retrieve(question, k)를 부르고,
  정답 문서(gold_chunks의 PDF 이름)가 몇 위에 나왔는지, 정답 쪽까지 맞혔는지 센다. 결과를 json으로 남긴다.
- 하지 않는 일: 답변 채점, 비관련 문항의 거절 판정. 회로 근거만 있는 관련 문항은 세지 않고 수만 적는다.
- 출처: docs/specs/rag-pipeline.md What 7·AC-07, evals/EVALS.md(gold_chunks 뜻)
- 필요한 것: DATABASE_URL(적재한 코퍼스), 임베딩 키(.env)

실행(저장소 루트에서): python -m evals.run_retrieval <평가셋 jsonl> <결과 json> [k]
"""
import json
import re
import sys
import time


def gold_locations(gold_chunks):
    """gold_chunks 글자에서 (PDF 이름, 쪽) 목록을 뽑는다. 넷리스트 같은 회로 근거는 뺀다."""
    out = []
    for g in gold_chunks:
        m = re.match(r'(.+?\.pdf),\s*(\d+)쪽', g)
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


def main(dataset_path, out_path, k=5):
    from backend.rag.retrieve import retrieve, warmup
    items = [json.loads(line) for line in open(dataset_path, encoding='utf-8') if line.strip()]
    warmup()
    rows, skipped = [], []
    for it in items:
        gold = gold_locations(it['gold_chunks']) if it['kind'] == 'relevant' else []
        if not gold:
            if it['kind'] == 'relevant':
                skipped.append(it['id'])  # 회로 근거만 있는 문항
            continue
        t0 = time.perf_counter()
        found = retrieve(it.get('question') or it['input'], k=k)
        sec = time.perf_counter() - t0
        docs = {d for d, _ in gold}
        rank = next((i + 1 for i, r in enumerate(found) if r['file'] in docs), None)
        page_hit = any((r['file'], r['page']) in set(gold) for r in found)
        rows.append({'id': it['id'], 'rank': rank, 'page_hit': page_hit, 'sec': round(sec, 3), 'gold': gold,
                     'top': [{'file': r['file'], 'page': r['page'], 'score': round(r['score'], 5),
                              'dense_rank': r['dense_rank'], 'bm25_rank': r['bm25_rank'],
                              'content': r['content'][:120]} for r in found]})
    n = len(rows)
    summary = {'dataset': dataset_path, 'k': k, 'questions': n, 'circuit_only_skipped': skipped,
               f'doc_recall@{k}': round(sum(r['rank'] is not None for r in rows) / n, 3),
               'doc_mrr': round(sum(1 / r['rank'] for r in rows if r['rank']) / n, 3),
               f'page_hit@{k}': round(sum(r['page_hit'] for r in rows) / n, 3),
               'sec_p50': sorted(r['sec'] for r in rows)[n // 2]}
    json.dump({'summary': summary, 'rows': rows}, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) == 4 else 5)
