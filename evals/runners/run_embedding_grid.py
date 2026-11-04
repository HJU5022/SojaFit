"""임베딩 격자 본평가(evals/guides/preregister.md #16)의 검색 측정(실험용).

- 하는 일: v1 관련 문항 중 데이터시트 근거가 있는 19건을 질의 글 2종(input 전체, "질문:" 줄)으로
  임베딩 모델 × 검색 방식(dense, 하이브리드, 각각 + 리랭커 2종)과 BM25(+ 리랭커 2종)에 넣어
  문서 Recall@5, 문서 MRR, 쪽 적중@5, 다중 근거 Recall@5와 단계별 시간을 칸마다 잰다.
  dense는 실험 DB의 emb_<키> 표에서 pgvector 정확 검색(<=>)으로, BM25·RRF는 저장소 retrieve.py의 함수로 한다.
  리랭커는 Voyage에 후보 전부를 넣고 상위 5를 받는다. 리랭크 응답은 out/rerank_cache.jsonl에 남겨 다시 돌릴 때 재과금하지 않는다.
- 하지 않는 일: 카드 임베딩(embed_cards.py), 답변 채점, 비관련 문항
- 출처: evals/guides/preregister.md #16, backend/rag/retrieve.py(tokens, rrf, positive_top, N_CAND),
  evals/runners/run_retrieval.py(gold_locations)

실행(`embed_cards.py`와 같은 컨테이너, /work/out에 결과): cd /work/repo && python -m evals.runners.run_embedding_grid <결과 이름> [모델 키 ...]   (모델을 빼면 표가 다 찬 모델 전부)
"""
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from rank_bm25 import BM25Okapi

from backend.rag.retrieve import N_CAND, positive_top, rrf, tokens  # noqa: E402  저장소와 같은 BM25 토큰·RRF
from evals.runners.run_retrieval import gold_locations  # noqa: E402
from evals.runners.embed_cards import DB, MODELS, _retry, embed  # noqa: E402  카드와 같은 방식으로 질문을 임베딩

K = 5
DATASET = '/work/repo/evals/dataset_v1.jsonl'
RERANKERS = ['rerank-3', 'rerank-3-lite']
CACHE = '/work/out/rerank_cache.jsonl'


def load_questions():
    """관련 문항 중 데이터시트 gold가 있는 것을 (id, gold, {질의 글 종류: 글})로 돌려준다."""
    out = []
    for line in open(DATASET, encoding='utf-8'):
        it = json.loads(line)
        gold = gold_locations(it['gold_chunks']) if it['kind'] == 'relevant' else []
        if gold:
            q = re.search(r'^질문:\s*(.+)$', it['input'], re.M).group(1).strip()
            out.append((it['id'], gold, {'input': it['input'], 'question': q}))
    return out


class Reranker:
    """Voyage 리랭크. 같은 (모델, 질문, 후보 목록)은 캐시에서 꺼낸다."""

    def __init__(self):
        self.cache, self.tokens, self.calls = {}, 0, 0
        if os.path.exists(CACHE):
            for line in open(CACHE, encoding='utf-8'):
                r = json.loads(line)
                self.cache[r['key']] = r
        self.client = None

    def __call__(self, model, query, cands, texts):
        key = hashlib.sha256(json.dumps([model, query, cands]).encode()).hexdigest()
        if key not in self.cache:
            import voyageai
            self.client = self.client or voyageai.Client(max_retries=0)
            t0 = time.perf_counter()
            r = _retry(lambda: self.client.rerank(query, [texts[c] for c in cands], model=model, top_k=K, truncation=True))
            rec = {'key': key, 'order': [x.index for x in r.results], 'tokens': r.total_tokens,
                   'sec': round(time.perf_counter() - t0, 3)}
            with open(CACHE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + '\n')
            self.cache[key] = rec
            self.tokens += r.total_tokens
            self.calls += 1
        rec = self.cache[key]
        return [cands[i] for i in rec['order']], rec['sec']


def score(top, meta, gold):
    """상위 5 카드의 (정답 문서 순위, 쪽 적중, 모든 gold 쪽이 함께 들어왔는지). run_retrieval.py와 같은 기준."""
    found = [(meta[c][0], meta[c][1]) for c in top]
    docs, gold_set = {d for d, _ in gold}, set(gold)
    rank = next((i + 1 for i, (f, _) in enumerate(found) if f in docs), None)
    return rank, any(x in gold_set for x in found), gold_set <= set(found)


def p(values, q):
    return round(float(np.percentile(values, q)), 3) if values else None


def summarize(rows):
    n = len(rows)
    out = {'questions': n,
           f'doc_recall@{K}': round(sum(r['rank'] is not None for r in rows) / n, 3),
           'doc_mrr': round(sum(1 / r['rank'] for r in rows if r['rank']) / n, 3),
           f'page_hit@{K}': round(sum(r['page_hit'] for r in rows) / n, 3),
           f'multi_gold@{K}': round(sum(r['all_gold'] for r in rows) / n, 3)}
    for stage in ('embed_sec', 'search_sec', 'rerank_sec'):
        vals = [r[stage] for r in rows if r.get(stage) is not None]
        if vals:
            out[stage.replace('_sec', '') + '_p50_p95'] = [p(vals, 50), p(vals, 95)]
    return out


def ready_models(conn):
    ready = []
    for key in MODELS:
        if conn.execute('SELECT to_regclass(%s)', (f'emb_{key}',)).fetchone()[0]:
            if conn.execute(f'SELECT count(*) FROM emb_{key}').fetchone()[0] == 52244:
                ready.append(key)
    return ready


def main(name, keys):
    questions = load_questions()
    rerank = Reranker()
    with psycopg.connect(DB) as conn:
        register_vector(conn)
        rows = conn.execute('SELECT id, doc, page, text FROM cards ORDER BY id').fetchall()
        meta = {i: (d, pg) for i, d, pg, _ in rows}
        texts = {i: t for i, _, _, t in rows}
        ids = [i for i, _, _, _ in rows]
        keys = keys or ready_models(conn)
        # BM25Okapi: 질문 토큰이 카드에 몇 번 나오는지(tf)와 드문 정도(idf)로 점수를 매기고 카드 길이로 보정한다(retrieve.warmup과 같음)
        bm25 = BM25Okapi([tokens(t) for t in texts.values()])
        bm = {}
        for qid, _, variants in questions:
            for v, q in variants.items():
                t0 = time.perf_counter()
                bm[qid, v] = (positive_top(bm25.get_scores(tokens(q)), ids, N_CAND), round(time.perf_counter() - t0, 3))
        cells = []

        def add(model, method, reranker, variant, per_q):
            cell_rows = []
            for qid, gold, top, extra in per_q:
                rank, page_hit, all_gold = score(top, meta, gold)
                cell_rows.append({'id': qid, 'rank': rank, 'page_hit': page_hit, 'all_gold': all_gold, **extra,
                                  'top': [[meta[c][0], meta[c][1]] for c in top]})
            cells.append({'model': model, 'method': method, 'reranker': reranker, 'variant': variant,
                          'summary': summarize(cell_rows), 'rows': cell_rows})
            s = cells[-1]['summary']
            print(f'{model:8} {method:6} {reranker or "-":14} {variant:8} R@5={s[f"doc_recall@{K}"]:.3f}'
                  f' MRR={s["doc_mrr"]:.3f} page={s[f"page_hit@{K}"]:.3f} multi={s[f"multi_gold@{K}"]:.3f}', flush=True)

        # 모델과 무관한 BM25 칸
        for v in ('input', 'question'):
            add('-', 'bm25', None, v, [(qid, gold, bm[qid, v][0][:K], {'search_sec': bm[qid, v][1]})
                                         for qid, gold, _ in questions])
            for rr in RERANKERS:
                per_q = []
                for qid, gold, variants in questions:
                    top, sec = rerank(rr, variants[v], bm[qid, v][0], texts)
                    per_q.append((qid, gold, top, {'search_sec': bm[qid, v][1], 'rerank_sec': sec}))
                add('-', 'bm25', rr, v, per_q)

        for key in keys:
            table = f'emb_{key}'
            embed(key, ['warm up'], 'query')  # [왜] 첫 호출의 연결·모델 적재 시간을 질문 시간에서 뺀다
            conn.execute(f'SELECT card_id FROM {table} ORDER BY embedding <=> %s LIMIT 1',
                         (np.zeros(MODELS[key]['dim'], np.float32) + 1e-3,)).fetchall()  # 표를 캐시에 올린다
            for v in ('input', 'question'):
                dense, hybrid = {}, {}
                for qid, _, variants in questions:
                    t0 = time.perf_counter()
                    vec, _ = embed(key, [variants[v]], 'query')
                    e_sec = round(time.perf_counter() - t0, 3)
                    t0 = time.perf_counter()
                    # [왜] 인덱스가 없어 모든 카드와 코사인 거리를 비교하는 정확 검색이다(HNSW 누락 없음)
                    d = [r[0] for r in conn.execute(f'SELECT card_id FROM {table} ORDER BY embedding <=> %s LIMIT %s',
                                                    (vec[0], N_CAND)).fetchall()]
                    s_sec = round(time.perf_counter() - t0, 3)
                    dense[qid] = (d, {'embed_sec': e_sec, 'search_sec': s_sec})
                    # [왜] BM25 점수와 코사인 거리는 단위가 달라 순위만 RRF로 합친다(retrieve.py와 같음)
                    hybrid[qid] = ([c for c, _ in rrf(d, bm[qid, v][0])],
                                   {'embed_sec': e_sec, 'search_sec': round(s_sec + bm[qid, v][1], 3)})
                for method, cand in (('dense', dense), ('hybrid', hybrid)):
                    add(key, method, None, v, [(qid, gold, cand[qid][0][:K], cand[qid][1]) for qid, gold, _ in questions])
                    for rr in RERANKERS:
                        per_q = []
                        for qid, gold, variants in questions:
                            top, sec = rerank(rr, variants[v], cand[qid][0], texts)
                            per_q.append((qid, gold, top, {**cand[qid][1], 'rerank_sec': sec}))
                        add(key, method, rr, v, per_q)
        version = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
    logs = {k: json.load(open(f'/work/logs/embed_{k}.json')) for k in keys if os.path.exists(f'/work/logs/embed_{k}.json')}
    out = {'meta': {'preregister': '#16', 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    'repo_commit': open('/work/repo/COMMIT').read().strip(),
                    'dataset_sha256': hashlib.sha256(open(DATASET, 'rb').read()).hexdigest(),
                    'chunks_sha256': hashlib.sha256(open('/work/data/chunks.jsonl', 'rb').read()).hexdigest(),
                    'pgvector': version, 'k': K, 'n_cand': N_CAND, 'rerankers': RERANKERS,
                    'rerank_new_calls': rerank.calls, 'rerank_new_tokens': rerank.tokens, 'embed_logs': logs},
           'cells': cells}
    json.dump(out, open(f'/work/out/{name}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'칸 {len(cells)}개, 새 리랭크 {rerank.calls}회 {rerank.tokens}토큰 → out/{name}.json')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
