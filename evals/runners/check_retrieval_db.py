# 0층: Supabase(읽기만)와 맥 로컬 사본이 같은지 본다. ① 카드 ② 벡터 ③ 저장해 둔 정확 검색 상위 50 ④ 서비스 경로 상위 5.
# 하지 않는 일: Supabase 쓰기, 레포 수정. 결과 전체는 out/layer0.json, 화면에는 요약 20줄 이하만 찍는다.
# 근거: docs/research/retrieval-layered-rerun-2026-11-03.md 0층, scripts/bit_search/bit_search_exp.py(connect), 레포 backend/rag/retrieve.py·backend/graph/nodes.py(search)
# 실행(저장소 루트, DATABASE_URL 필요): uv run python -m evals.runners.check_retrieval_db   (입출력 폴더는 LAYERS_WORK, run_retrieval_layers.py와 같음)
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np

# [주의] llm.DEMO_MODE 기본값이 "1"이라 .env에 DEMO_MODE=0이 없으면 retrieve()가 dense를 건너뛰고 BM25만 쓴다
# (11-03 0층 첫 실행에서 Supabase 쪽 dense 후보 0장으로 확인). llm을 import하기 전에 끈다
os.environ['DEMO_MODE'] = '0'
sys.path.insert(0, os.getcwd())  # [왜] backend·evals 패키지를 cwd(조 저장소)에서 찾게 한다
from backend.graph.nodes import find_parts, read_input  # noqa: E402
from backend.rag import retrieve as R  # noqa: E402
from evals.runners.run_retrieval import gold_locations  # noqa: E402

WORK = Path(os.environ.get('LAYERS_WORK', '../전자_데이터시트/evidence/full_grid'))
CORPUS = Path('../corpus/tsc')
DATASET = 'evals/dataset_v1.jsonl'
SHA = {'dataset': '2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b', 'chunks': '9e62fb6a'}
TOL = 1e-5  # 거리 차가 이 안이면 같은 거리로 본다(halfvec 저장·float32 계산 차이)
MODEL = 'openai/text-embedding-3-small'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def connect():
    """bit_search_exp.py와 같은 연결. DATABASE_URL이 Supabase가 아니면 멈춘다."""
    import psycopg
    from dotenv import load_dotenv
    from pgvector.psycopg import register_vector
    load_dotenv('.env')
    url = os.environ['DATABASE_URL']
    if 'supabase' not in (urlparse(url).hostname or ''):
        raise SystemExit('DATABASE_URL이 Supabase가 아니어서 멈춘다')
    conn = psycopg.connect(url, connect_timeout=15, autocommit=True)
    register_vector(conn)
    conn.execute('SET default_transaction_read_only = on')  # [왜] 이 점검은 읽기만 한다. 실수로 쓰는 SQL이 나가도 DB가 거절한다
    return conn


def load_local():
    """로컬 카드와 벡터. 카드마다 벡터 행 번호(card_row)를 붙인다."""
    raw = open(CORPUS / 'chunks/chunks.jsonl', 'rb').read()
    cards = [json.loads(line) for line in raw.decode().splitlines()]
    V = np.fromfile(CORPUS / 'embeddings/vectors.f32', dtype=np.float32).reshape(-1, 1536)
    row_of = {s: i for i, s in enumerate(open(CORPUS / 'embeddings/vectors.sha.txt').read().split())}
    assert len(row_of) == len(V), (len(row_of), len(V))
    card_row = np.array([row_of[c['sha256']] for c in cards])
    return cards, hashlib.sha256(raw).hexdigest(), V / np.linalg.norm(V, axis=1, keepdims=True), card_row


def cos_dist(q, Vn, card_row):
    """질문 하나와 모든 카드의 코사인 거리(pgvector <=>와 같은 뜻). 같은 본문 카드는 같은 거리다."""
    return (1 - Vn @ (q / np.linalg.norm(q)))[card_row]


def top_stable(d, n):
    return [int(i) for i in np.argsort(d, kind='stable')[:n]]


def same_ranked(sup, loc):
    """(본문 sha, 거리) 두 목록이 같은지. 순위마다 거리 차 TOL 이하이고, 경계 동점을 뺀 본문 여러 벌 집합이 같으면 같다."""
    if len(sup) != len(loc) or any(abs(a[1] - b[1]) > TOL for a, b in zip(sup, loc)):
        return False
    edge = sup[-1][1] - TOL  # [왜] 마지막 순위와 거리가 같은 카드는 어느 쪽이 잘려 나가도 맞다
    return Counter(s for s, d in sup if d < edge) == Counter(s for s, d in loc if d < edge)


def main():
    out = {}
    cards, chunks_sha, Vn, card_row = load_local()
    ds_sha = hashlib.sha256(open(DATASET, 'rb').read()).hexdigest()
    if ds_sha != SHA['dataset'] or not chunks_sha.startswith(SHA['chunks']):
        raise SystemExit(f'입력 해시가 다르다: dataset {ds_sha[:8]} chunks {chunks_sha[:8]}')
    conn = connect()

    # ① 카드: (파일, 쪽, 본문 sha)의 여러 벌 집합 비교
    rows = conn.execute('SELECT dc.id, sd.source_url, dc.page_number, dc.content FROM document_chunks dc'
                        ' JOIN source_documents sd ON sd.id = dc.document_id').fetchall()
    sup_sha = {i: sha(c) for i, _, _, c in rows}
    sup_set = Counter((unquote(os.path.basename(urlparse(u).path)), p, sup_sha[i]) for i, u, p, _ in rows)
    loc_set = Counter((c['doc'], c['page'], c['sha256']) for c in cards)
    out['1_cards'] = {'supabase': len(rows), 'local': len(cards), 'only_supabase': sum((sup_set - loc_set).values()),
                      'only_local': sum((loc_set - sup_set).values())}
    out['1_cards']['pass'] = out['1_cards']['only_supabase'] == out['1_cards']['only_local'] == 0 and len(rows) == len(cards)

    # ② 벡터: chunk_embeddings 전 행을 로컬 벡터와 코사인으로 비교
    cur = conn.cursor(binary=True)  # [왜] 11-02 안 D와 같이 바이너리로 받아 글자 변환을 피한다
    emb = cur.execute('SELECT chunk_id, embedding_model, embedding FROM chunk_embeddings').fetchall()
    ids = [r[0] for r in emb]
    dims = Counter(len(r[2].to_list()) if hasattr(r[2], 'to_list') else len(r[2]) for r in emb[:100])
    E = np.array([np.asarray(r[2].to_numpy() if hasattr(r[2], 'to_numpy') else r[2], np.float32) for r in emb])
    row_of_sha = {s: card_row[k] for k, s in enumerate(c['sha256'] for c in cards)}
    L = Vn[[row_of_sha[sup_sha[i]] for i in ids]]
    cos = (E * L).sum(1) / np.linalg.norm(E, axis=1)
    out['2_vectors'] = {'rows': len(emb), 'models': dict(Counter(r[1] for r in emb)), 'dims_sample': dict(dims),
                        'missing': len(set(sup_sha) - set(ids)), 'duplicate': len(ids) - len(set(ids)),
                        'cos_min': round(float(cos.min()), 6), 'below_0.9999': int((cos < 0.9999).sum())}
    v = out['2_vectors']
    v['pass'] = (v['missing'] == v['duplicate'] == v['below_0.9999'] == 0 and v['models'] == {MODEL: len(cards)}
                 and set(v['dims_sample']) == {1536})
    del E, L

    # ③ 저장해 둔 Supabase 정확 검색 상위 50(11-03, input 전체) vs 로컬 numpy
    bq = WORK.parent / 'bq_exp'
    qv = dict(zip((q['id'] for q in json.load(open(bq / 'q_ids.json'))), np.load(bq / 'q_vectors.npy')))
    res, bad3 = json.load(open(bq / 'result_2026-11-03.json'))['questions'], []
    for q in res:
        d = cos_dist(qv[q['id']], Vn, card_row)
        loc = [(cards[j]['sha256'], float(d[j])) for j in top_stable(d, 50)]
        if not same_ranked([(sup_sha[c], dist) for c, dist in q['exact']], loc):
            bad3.append(q['id'])
    out['3_exact_top50'] = {'questions': len(res), 'same': len(res) - len(bad3), 'differ': bad3, 'pass': not bad3}

    # ④ 서비스 경로(질문 줄 + 품번 필터) 상위 5: Supabase retrieve() vs 로컬 같은 계산. 질문 벡터는 같은 것을 쓴다
    from backend.services import llm
    from rank_bm25 import BM25Okapi
    targets = []
    for line in open(DATASET, encoding='utf-8'):
        it = json.loads(line)
        if it['kind'] == 'relevant' and gold_locations(it['gold_chunks']):
            st = read_input({'input': it['input']})
            part = st.get('target_part') or {}
            # [왜] 검색 노드 search()와 같은 refs·parts 규칙(대상 기호와 주변 넷 부품은 품번이 아니다)
            refs = {part.get('ref', '')} | {n.split('.')[0] for net in part.get('nets', []) for n in net['nodes']}
            parts = find_parts(st['question'], refs) or find_parts(part.get('value', ''), refs)
            targets.append({'id': it['id'], 'question': st['question'], 'parts': parts})
    qpath = WORK / 'inputs/q2_vectors.npy'
    if qpath.exists():  # [왜] 다시 돌릴 때 같은 질문 벡터를 써서 유료 호출을 되풀이하지 않는다
        vecs, n_tok = np.load(qpath).tolist(), 0
    else:
        vecs, n_tok, provider, model = llm.embed_texts([t['question'] for t in targets])  # 유료 호출 1번(19문장)
        assert model == MODEL, model
        np.save(qpath, np.asarray(vecs, np.float32))
    cache = {t['question']: v for t, v in zip(targets, vecs)}
    llm.embed_texts = lambda texts: ([cache[texts[0]]], 0, 'cache', MODEL)  # [왜] DB 쪽과 로컬 쪽이 같은 질문 벡터를 쓴다

    local_rows = [(k, c['doc'], c['text']) for k, c in enumerate(cards)]
    pindex = R.part_index(local_rows)
    bm25 = BM25Okapi([R.tokens(c['text']) for c in cards])
    all_ids = list(range(len(cards)))
    hits, bad4 = 0, []
    for t in targets:
        allowed = R.allowed_chunks(pindex, t['parts']) if t['parts'] else None
        hits += bool(allowed)
        t['allowed_cards'] = len(allowed) if allowed is not None else None
        t['compare'] = len({p.lower() for p in t['parts'] if p.lower() in pindex[0]}) >= 2  # 코퍼스 품번 2개 이상이면 비교 질문
        sup = R.retrieve(t['question'], k=5, parts=t['parts'] or None)
        d = cos_dist(np.asarray(cache[t['question']], np.float32), Vn, card_row)
        if allowed is not None:
            d = np.where(np.isin(all_ids, list(allowed)), d, np.inf)
        dense = [j for j in top_stable(d, R.N_CAND) if np.isfinite(d[j])]
        s = bm25.get_scores(R.tokens(t['question']))
        if allowed is not None:
            s = np.where(np.isin(all_ids, list(allowed)), s, -np.inf)
        loc = [i for i, _ in R.rrf(dense, R.positive_top(s, all_ids, R.N_CAND))[:5]]
        t['supabase_top5'] = [[r['file'], r['page'], sha(r['content'])[:12]] for r in sup]
        t['local_top5'] = [[cards[j]['doc'], cards[j]['page'], cards[j]['sha256'][:12]] for j in loc]
        # [왜] 본문이 같은 카드는 dense 거리와 BM25 점수가 같아 어느 쪽이 먼저 나와도 맞다. 그래서 본문 sha 순서로 비교한다
        if [x[2] for x in t['supabase_top5']] != [x[2] for x in t['local_top5']]:
            bad4.append(t['id'])
    out['4_service_top5'] = {'questions': len(targets), 'filter_hit': hits, 'same_by_text': len(targets) - len(bad4),
                             'same_by_file_page': sum(t['supabase_top5'] == t['local_top5'] for t in targets),
                             'differ': bad4, 'embed_tokens': n_tok, 'pass': not bad4 and hits == len(targets)}
    json.dump([{k: t[k] for k in ('id', 'question', 'parts', 'compare', 'allowed_cards')} for t in targets],
              open(WORK / 'inputs/parts.json', 'w'), ensure_ascii=False, indent=1)
    out['meta'] = {'dataset_sha256': ds_sha, 'chunks_sha256': chunks_sha, 'compare_questions': [t['id'] for t in targets if t['compare']]}
    json.dump({'summary': out, 'service_rows': targets}, open(WORK / 'out/layer0.json', 'w'), ensure_ascii=False, indent=1)
    for key in ('1_cards', '2_vectors', '3_exact_top50', '4_service_top5'):
        print(key, json.dumps(out[key], ensure_ascii=False))
    print('compare', out['meta']['compare_questions'])


if __name__ == '__main__':
    main()
