# 비트 후보(bit(1536) Hamming) + pgvector 재정렬을 운영 Supabase에서 잰다. 운영 표는 읽기만 하고, 실험 표 exp_bq만 만들고 지운다.
# 하지 않는 일: 운영 표 변경, 서비스 코드(retrieve.py) 변경, BM25·RRF까지 합친 최종 점수 계산.
# 근거: 조사 보고서 "pgvector 유지하며 검색 속도 높이기"의 "bit 컬럼" 절과 "결정 전에 우리 Supabase에서 잴 것" 4·5번, docs/research/bit-search-measurement-2026-11-03.md.
# 실행(저장소 루트, DATABASE_URL 필요): uv run python scripts/bit_search/bit_search_exp.py <embed|setup|measure|warm|final|report|drop>
# 입출력은 BIT_SEARCH_WORK 폴더(기본 ../전자_데이터시트/evidence/bq_exp)의 q_vectors.npy · q_ids.json · result_*.json이다.
# [주의] 측정 당시 운영 DB(embedding_model = text-embedding-3-small, halfvec(1536))용이다. 11-04부터 운영 DB는 voyage-4-large만 있어 그대로는 돌지 않는다.
import json
import os
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

HERE = Path(os.environ.get('BIT_SEARCH_WORK', '../전자_데이터시트/evidence/bq_exp'))
sys.path.insert(0, os.getcwd())  # [왜] 저장소 루트에서 실행해 backend·evals 패키지를 cwd에서 찾게 한다
MODEL = 'openai/text-embedding-3-small'
NS = [400, 800, 1600, 3200]
EPS = 1e-9  # 같은 내용 카드는 거리가 같다. 이 차이 안이면 같은 순위로 본다

EXACT = ('SELECT chunk_id, embedding::vector(1536) <=> %(q)s::vector(1536) AS d FROM chunk_embeddings '
         'WHERE embedding_model = %(m)s ORDER BY d LIMIT 50')
# binary_quantize: 1536개 값을 0보다 크면 1, 아니면 0으로 바꾼다. <~>는 두 비트열에서 다른 자리 수(Hamming 거리)
STAGE1 = 'SELECT chunk_id FROM exp_bq ORDER BY bq <~> binary_quantize(%(q)s::vector(1536))::bit(1536) LIMIT %(n)s'
# [왜] MATERIALIZED: 후보 N개를 먼저 확정하게 해서, 코사인 거리는 후보에만 재도록 한다(보고서 SQL과 같은 모양)
BQ = ('WITH cand AS MATERIALIZED (' + STAGE1 + ') '
      'SELECT e.chunk_id, e.embedding::vector(1536) <=> %(q)s::vector(1536) AS d FROM cand '
      'JOIN chunk_embeddings e ON e.chunk_id = cand.chunk_id AND e.embedding_model = %(m)s ORDER BY d LIMIT 50')


def connect():
    import psycopg
    from dotenv import load_dotenv
    from pgvector.psycopg import register_vector
    load_dotenv('.env')
    url = os.environ['DATABASE_URL']
    if 'supabase' not in (urlparse(url).hostname or ''):
        raise SystemExit('DATABASE_URL이 Supabase가 아니어서 멈춘다')
    conn = psycopg.connect(url, connect_timeout=15, autocommit=True)
    register_vector(conn)
    return conn


def timed(conn, sql, args):
    t0 = time.perf_counter()
    rows = conn.execute(sql, args).fetchall()
    return rows, (time.perf_counter() - t0) * 1000


def embed():
    from dotenv import load_dotenv
    load_dotenv('.env')
    from backend.services import llm
    items = [json.loads(l) for l in open('evals/dataset_v1.jsonl', encoding='utf-8')]
    vecs, tokens, provider, model = llm.embed_texts([it['input'] for it in items])
    assert model.endswith('text-embedding-3-small') and len(vecs) == 50, (model, len(vecs))
    np.save(HERE / 'q_vectors.npy', np.asarray(vecs, dtype=np.float32))
    json.dump([{'id': it['id'], 'kind': it['kind']} for it in items], open(HERE / 'q_ids.json', 'w'), ensure_ascii=False)
    print(f'질문 {len(vecs)}개, 토큰 {tokens}, {provider}/{model}')


def size(conn):
    return conn.execute('SELECT pg_database_size(current_database())').fetchone()[0] / 2**20


def setup():
    with connect() as conn:
        print('pgvector', conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0])
        print('embedding 타입', conn.execute("SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                                            "WHERE attrelid='chunk_embeddings'::regclass AND attname='embedding'").fetchone()[0])
        if conn.execute("SELECT to_regclass('exp_bq')").fetchone()[0]:
            raise SystemExit('exp_bq가 이미 있다. drop 뒤 다시 실행')
        before = size(conn)
        t0 = time.perf_counter()
        conn.execute('SET statement_timeout = 300000')
        conn.execute('CREATE TABLE exp_bq AS SELECT chunk_id, binary_quantize(embedding)::bit(1536) AS bq '
                     'FROM chunk_embeddings WHERE embedding_model = %s', [MODEL])
        conn.execute('ALTER TABLE exp_bq ADD PRIMARY KEY (chunk_id)')
        conn.execute('ANALYZE exp_bq')
        n = conn.execute('SELECT count(*) FROM exp_bq').fetchone()[0]
        rel = conn.execute("SELECT pg_total_relation_size('exp_bq')").fetchone()[0] / 2**20
        print(f'exp_bq {n}행, {rel:.1f} MiB, 만들기 {time.perf_counter() - t0:.1f}초, DB {before:.1f} → {size(conn):.1f} MiB')


def measure():
    qs = np.load(HERE / 'q_vectors.npy')
    ids = json.load(open(HERE / 'q_ids.json'))
    out = {'rtt_ms': [], 'questions': []}
    with connect() as conn:
        for _ in range(5):
            out['rtt_ms'].append(timed(conn, 'SELECT 1', None)[1])
        a = {'q': qs[0], 'm': MODEL, 'n': 800}
        out['plan_bq800'] = conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + BQ, a).fetchone()[0]
        for i, (q, meta) in enumerate(zip(qs, ids)):
            a = {'q': q, 'm': MODEL}
            # [왜] _dense와 같은 조건: HNSW가 없어도 인덱스 경로를 끈 정확 검색
            conn.execute('SET enable_indexscan = off')
            exact, t_exact = timed(conn, EXACT, a)
            conn.execute('RESET enable_indexscan')
            rec = {**meta, 'exact_ms': t_exact, 'exact': [[c, float(d)] for c, d in exact]}
            rec['stage1_800_ms'] = timed(conn, STAGE1, {**a, 'n': 800})[1]
            for n in NS:
                rows, t = timed(conn, BQ, {**a, 'n': n})
                rec[f'bq{n}_ms'], rec[f'bq{n}'] = t, [[c, float(d)] for c, d in rows]
            out['questions'].append(rec)
            print(f"{i + 1:2d}/50 {meta['id']} 정확 {t_exact:.0f}ms 1단계 {rec['stage1_800_ms']:.0f}ms "
                  + ' '.join(f'N{n} {rec[f"bq{n}_ms"]:.0f}ms' for n in NS), flush=True)
    json.dump(out, open(HERE / 'result_2026-11-03.json', 'w'), ensure_ascii=False)


def warm():
    """정확 검색 없이 비트 검색만 이어서 잰다(서비스에서는 정확 검색이 캐시를 밀어내지 않는다)."""
    # [왜] measure에서는 매 질문 정확 검색(벡터 206MiB를 훑음) 바로 뒤에 1단계를 재서, 1단계가 1+2단계보다 느리게 나왔다
    qs = np.load(HERE / 'q_vectors.npy')
    out = {}
    with connect() as conn:
        for q in qs[:5]:  # 캐시를 채우는 예열. 기록하지 않는다
            conn.execute(BQ, {'q': q, 'm': MODEL, 'n': 3200}).fetchall()
        for name, sql, n in [('stage1_800', STAGE1, 800), ('bq1600', BQ, 1600), ('bq3200', BQ, 3200)]:
            out[name] = [timed(conn, sql, {'q': q, 'm': MODEL, 'n': n})[1] for q in qs]
        out['plan_stage1_800'] = conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + STAGE1,
                                              {'q': qs[0], 'm': MODEL, 'n': 800}).fetchone()[0]
    json.dump(out, open(HERE / 'result_warm_2026-11-03.json', 'w'))
    for name in ('stage1_800', 'bq1600', 'bq3200'):
        xs = out[name]
        print(f'{name:11s} p50 {np.percentile(xs, 50):5.0f}  p95 {np.percentile(xs, 95):5.0f}  최대 {max(xs):5.0f} ms')
    p = out['plan_stage1_800'][0]
    print(f"1단계 계획 서버 {p['Execution Time']:.0f} ms, shared hit {p['Plan'].get('Shared Hit Blocks')} read {p['Plan'].get('Shared Read Blocks')}")


def final():
    """같은 실행에서 하이브리드 상위 5를 지금 dense와 비트 N=3,200 dense로 각각 잰다(run_retrieval 채점 그대로)."""
    connect().close()  # Supabase 주소인지 먼저 확인한다
    os.environ['DEMO_MODE'] = '0'  # [왜] 기본값이 데모 모드(1)라 dense가 빈 목록이 된다. 질문 벡터는 캐시에서 주므로 키는 쓰지 않는다
    os.environ['RAG_VECTOR_TYPE'] = 'halfvec'  # [왜] 운영 Supabase의 embedding 열이 halfvec(1536)이다(setup 출력)
    from backend.services import llm
    from backend.rag import retrieve as rag
    from evals.runners import run_retrieval
    items = [json.loads(l) for l in open('evals/dataset_v1.jsonl', encoding='utf-8')]
    cache = dict(zip((it['input'] for it in items), np.load(HERE / 'q_vectors.npy')))
    # [주의] 캐시에 없는 질문이면 KeyError로 멈춘다. API로 새로 만들지 않는다
    llm.embed_texts = lambda texts: ([cache[t].tolist() for t in texts], 0, 'cache', MODEL)

    def bit_dense(conn, question, allowed=None):
        assert allowed is None  # parts를 주지 않으므로 품번 필터는 없다
        return [c for c, _ in conn.execute(BQ, {'q': cache[question], 'm': MODEL, 'n': 3200}).fetchall()]

    assert rag.N_CAND == 50  # [주의] BQ는 LIMIT 50이라 retrieve의 dense 후보 수와 같아야 한다
    exact_dense, out = rag._dense, {}
    # [왜] retrieve()는 모듈의 _dense를 부를 때 찾으므로, 이 자리만 바꾸면 BM25 · RRF · 채점은 그대로다
    for name, dense in [('exact', exact_dense), ('bit3200', bit_dense)]:
        rag._dense = dense
        path = HERE / f'_final_{name}.json'
        run_retrieval.main('evals/dataset_v1.jsonl', str(path), 5, 'hybrid')
        out[name] = json.load(open(path))
        path.unlink()
    rag._dense = exact_dense
    top = lambda r: [(t['file'], t['page'], t['content']) for t in r['top']]
    bit = {r['id']: r for r in out['bit3200']['rows']}
    differ = [[r['id'], r['rank'], bit[r['id']]['rank']] for r in out['exact']['rows'] if top(r) != top(bit[r['id']])]
    json.dump({'summary': {k: v['summary'] for k, v in out.items()}, 'differ_id_rank_exact_bit': differ,
               'rows': {k: v['rows'] for k, v in out.items()}},
              open(HERE / 'result_final_2026-11-03.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('상위 5가 다른 문항 [id, 정확 순위, 비트 순위]:', differ)


def scores(exact, got):
    """recall@50(거리 기준: 정확 50위 거리 안에 든 비율)과 상위 5 일치(거리 기준)."""
    d50 = exact[-1][1]
    recall = sum(d <= d50 + EPS for _, d in got) / len(exact)
    top5 = all(abs(g[1] - e[1]) <= EPS for g, e in zip(got[:5], exact[:5]))
    return recall, top5


def report():
    res = json.load(open(HERE / 'result_2026-11-03.json'))
    qs = res['questions']
    pct = lambda xs, p: float(np.percentile(xs, p))
    line = lambda name, xs: print(f'{name:14s} p50 {pct(xs, 50):7.0f}  p95 {pct(xs, 95):7.0f}  최소 {min(xs):7.0f}  최대 {max(xs):7.0f} ms')
    print(f"왕복 SELECT 1 중앙값 {statistics.median(res['rtt_ms']):.0f} ms, 질문 {len(qs)}개")
    line('정확 검색', [q['exact_ms'] for q in qs])
    line('1단계만 N800', [q['stage1_800_ms'] for q in qs])
    for n in NS:
        line(f'1+2단계 N{n}', [q[f'bq{n}_ms'] for q in qs])
    for kind in (None, 'relevant'):
        sub = [q for q in qs if kind is None or q['kind'] == kind]
        print(f"\n[{kind or '전체'} {len(sub)}문항]")
        for n in NS:
            r = [scores(q['exact'], q[f'bq{n}']) for q in sub]
            rec = [x for x, _ in r]
            print(f'N{n:5d} recall@50 평균 {np.mean(rec):.3f} 최소 {min(rec):.2f} | 상위50 완전 일치 {sum(x == 1 for x in rec)}/{len(sub)}'
                  f' | 상위5 일치 {sum(t for _, t in r)}/{len(sub)}')
    print('\nN800 계획:', json.dumps(res['plan_bq800'][0]['Plan']['Node Type']), f"서버 {res['plan_bq800'][0]['Execution Time']:.0f} ms")


def drop():
    with connect() as conn:
        before = size(conn)
        conn.execute('DROP TABLE IF EXISTS exp_bq')
        left = conn.execute("SELECT to_regclass('exp_bq')").fetchone()[0]
        print(f'exp_bq 삭제. 남은 표: {left}, DB {before:.1f} → {size(conn):.1f} MiB')


if __name__ == '__main__':
    # 스스로 확인: 같은 거리면 같은 순위로 본다
    assert scores([[1, 0.1], [2, 0.2]], [[3, 0.1], [2, 0.2]]) == (1.0, True)
    assert scores([[1, 0.1], [2, 0.2]], [[1, 0.1], [9, 0.3]]) == (0.5, False)
    {'embed': embed, 'setup': setup, 'measure': measure, 'warm': warm, 'final': final, 'report': report, 'drop': drop}[sys.argv[1]]()
