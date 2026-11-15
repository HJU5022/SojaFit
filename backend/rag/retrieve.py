"""검색: 하이브리드(BM25 + 벡터)를 RRF로 합치고 rerank-3로 다시 세운다. 품번 필터(parts)와 검색 방식(method)을 검색 인자로 받는다.

- 역할: 서버와 평가 도구가 import하는 검색 함수 `retrieve`. 질문을 voyage-4-large(1024차원)로 숫자로 바꿔 pgvector 코사인 거리 상위 50개을(허용 청크가 3,200장보다 많으면 1비트 Hamming 거리로 3,200장을 먼저 거른 뒤 그 안에서 정확 코사인, 사전 등록 #27), 같은 질문의 BM25 상위 50개을 구해
  RRF(청크마다 1/(60 + 순위)의 합)로 합친다. 합친 후보 전부를 Voyage rerank-3로 다시 세우고 상위 k개을 돌려준다.
  parts를 주면 그 품번이 표지에 적힌 문서의 청크 안에서만 찾고, 표지 청크(page_number 없음)는 언제나 뺀다.
  method='dense'면 dense 목록만, 'bm25'면 BM25 목록만 쓰고 임베딩·리랭크 API를 부르지 않는다(기본 'hybrid').
  DEMO_MODE=1(키 없는 데모)이면 임베딩·리랭크 API를 부르지 않고 BM25만으로 찾는다(SPEC 7절).
- 하지 않는 일: 품번 밖 메타데이터 필터(분류·패키지 등), 질문에서 품번 뽑기(에이전트가 parts로 준다, `backend/graph/nodes.py`), 답변 생성, 판정(`backend/judge/`).
- 출처: docs/specs/rag-pipeline.md What 6·How·AC-05~AC-11·EC-06~EC-08, EVAL_REPORT.md 1장 하이브리드 검색 비교·HNSW 개선 실험 B,
  evals/guides/preregister.md #6·#16·#25·#27, ADR 0004(갱신 2026-11-03), SPEC.md 7절

[주의] 대상 필터(품번 등)는 결과를 받은 뒤 거르지 않고 검색 단계의 인자로 받는다. 후처리로 거르면 결과가 0~2개로 굶어
"우연한 거절"이 생기고 점수가 실제보다 좋게 나온다. score의 뜻과 범위는 검색 방식마다 달라 거절 임계값도 방식마다 따로 정한다.
"""
import os
import re
from threading import Lock
from urllib.parse import unquote, urlparse

# [왜] FastMCP 요청 worker에서 처음 import하면 첫 search_corpus가 멈출 수 있어 서버 시작 스레드에서 미리 읽는다.
import numpy as np


N_CAND = 50  # 방식마다 합치기 전에 가져오는 후보 수
# dense 1단계가 Hamming 거리로 거르는 후보 수. 허용 청크가 이보다 많을 때만 1단계를 쓴다(사전 등록 #27)
N_BIT = 3200  # [왜] 3-small 1536차원 운영 DB 실측(전자_데이터시트/evidence/bq_exp): 3,200장이면 recall@50 0.980, 최종 상위 5개 19/19문항 같고 retrieve() 중앙값 6.22초 → 0.89초
# RRF 점수 1/(RRF_K + 순위)의 상수. 클수록 1위와 10위의 점수 차가 줄어 순위 차이를 덜 따진다
RRF_K = 60   # [왜] RRF 원 논문(Cormack 외 2009)의 기본값
EMBED_MODEL = 'voyage-4-large'  # chunk_embeddings.embedding_model과 같아야 한다
DIM = 1024  # voyage-4-large의 출력 차원(llm.voyage_embed가 output_dimension 1024로 부른다)
_warmup_lock = Lock()
_bm25 = None  # (BM25Okapi, 청크 id 목록). warmup()이 한 번 만든다
_parts = None  # (품번 소문자 → 문서 id 집합, 문서 id → 청크 id 목록). warmup()이 같이 만든다
_nocover = None  # 표지 청크가 아닌 청크 id 집합. warmup()이 같이 만든다
COVER = re.compile(r'\[.+?\] 이 데이터시트의 품번: (.*)')  # chunk.py doc_cards가 만드는 표지 청크(chunk_index 0)


def tokens(text):
    """영문·숫자 연속을 소문자 토큰으로 자른다."""
    # [주의] "1N5819는" → "1n5819"처럼 한국어 조사가 떨어진다. 대신 한국어 단어는 BM25에서 빠진다(데이터시트가 영문이라)
    return re.findall(r'[a-z0-9]+', text.lower())


def rrf(*rankings):
    """순위 목록 여러 개를 청크마다 1/(RRF_K + 순위)의 합으로 합쳐 (id, 점수)를 높은 순으로 돌려준다(AC-05).

    RRF(Reciprocal Rank Fusion): 두 목록 모두에 높은 순위로 든 청크가 한쪽에만 든 청크보다 위로 간다.
    """
    # [왜] BM25 점수와 코사인 거리는 단위가 달라 더할 수 없다. 순위만 쓰면 가중치를 정하지 않아도 된다
    score = {}
    for ranking in rankings:
        for r, key in enumerate(ranking, 1):  # 순위는 1부터 센다
            score[key] = score.get(key, 0) + 1 / (RRF_K + r)
    return sorted(score.items(), key=lambda kv: kv[1], reverse=True)


def part_index(rows):
    """(청크 id, 문서 id, 본문) 목록에서 (품번 소문자 → 문서 id 집합, 문서 id → 청크 id 목록)을 만든다."""
    part_docs, doc_chunks = {}, {}
    for chunk_id, doc_id, content in rows:
        doc_chunks.setdefault(doc_id, []).append(chunk_id)
        m = COVER.match(content)
        if m:  # [왜] 품번 목록은 표지 청크에만 있다. 표지가 문서의 모든 품번을 쉼표로 나열한다
            for part in m.group(1).split(', '):
                part_docs.setdefault(part.strip().lower(), set()).add(doc_id)
    return part_docs, doc_chunks


def allowed_chunks(index, parts):
    """parts 중 하나라도 표지에 적힌 문서의 청크 id 집합을 돌려준다(AC-08·AC-09). 코퍼스에 없는 품번뿐이면 빈 집합이다."""
    part_docs, doc_chunks = index
    # [주의] 품번 전체가 같아야 걸린다(대소문자만 무시). SS34는 SS34L 문서를, 1N4148은 1N4148W 문서를 고르지 않는다
    docs = set().union(*(part_docs.get(p.strip().lower(), set()) for p in parts))
    return {c for d in docs for c in doc_chunks[d]}


def _connect():
    """DATABASE_URL로 DB에 연결하고 pgvector 형식을 등록한 연결을 돌려준다(호출한 쪽이 닫는다)."""
    import psycopg
    from pgvector.psycopg import register_vector
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    register_vector(conn)
    return conn


def warmup():
    """document_chunks 본문으로 BM25 색인과 품번 → 문서 색인을 메모리에 만든다."""
    # [주의] 첫 retrieve() 때 한 번 불린다. 분석 서비스를 켠 서버는 기동 직후 Conversations.warm()이 데몬 스레드로 미리 부른다
    global _bm25, _parts, _nocover
    with _warmup_lock:
        if _bm25 is not None and _parts is not None and _nocover is not None:
            return
        from rank_bm25 import BM25Okapi
        with _connect() as conn:
            rows = conn.execute('SELECT id, document_id, content, page_number FROM document_chunks ORDER BY id').fetchall()
        # BM25Okapi: 질문 토큰이 청크에 몇 번 나오는지(tf)와 그 토큰이 드문 정도(idf)로 점수를 매기고 청크 길이로 보정한다
        # [주의] 적재 전 빈 DB에서는 BM25Okapi가 0으로 나눈다. 청크가 없으면 키워드 후보 없이 dense만 쓴다
        index = (BM25Okapi([tokens(r[2]) for r in rows]) if rows else None, [r[0] for r in rows])
        _parts = part_index([r[:3] for r in rows])
        _nocover = {r[0] for r in rows if r[3] is not None}  # [왜] 표지 청크는 품번 목록뿐이라 품번 질문에 BM25로 1위가 되고 근거 페이지가 없다(page_number가 없는 청크)
        _bm25 = index  # Publish readiness only after the part and page indexes are ready.


def corpus_known():
    """코퍼스에 있는 (품번 소문자 집합, 개정 코드 집합)을 돌려준다. 개정 코드는 문서 파일 이름 끝(`..._H2104.pdf`)에서 읽는다."""
    if _parts is None:
        warmup()
    with _connect() as conn:
        urls = [r[0] for r in conn.execute('SELECT source_url FROM source_documents').fetchall()]
    names = (unquote(os.path.basename(urlparse(u).path)) for u in urls)
    return set(_parts[0]), {m.group(1) for m in map(re.compile(r'_([A-Z]\d{4})\.pdf$').search, names) if m}


def positive_top(scores, ids, n):
    """BM25 점수가 0보다 큰 청크 id를 높은 순으로 n개까지 돌려준다. 질문 단어가 하나도 안 맞으면 빈 목록이다(AC-10)."""
    # [왜] 점수 0인 청크까지 넣으면 질문과 상관없는 청크 50개이 RRF 후보로 들어간다(허용 밖 -inf도 같이 빠진다)
    return [ids[j] for j in np.argsort(-np.asarray(scores), kind='stable')[:n] if scores[j] > 0]


def _dense(conn, question, allowed=None, *, nocover_all=False):
    """질문 벡터와 코사인 거리가 가까운 청크 id를 N_CAND개까지 가까운 순으로 돌려준다(벡터 검색, dense)."""
    # allowed가 있으면 그 청크 안에서만 잰다. nocover_all이면 allowed 대신 표지 아닌 청크 전체(SQL로 거름, 아이디 5만 개를 보내지 않음). DEMO_MODE면 빈 목록(AC-11)
    # 허용 청크가 N_BIT장보다 많으면 1비트 Hamming 거리로 N_BIT장을 먼저 거르고(chunk_embedding_bits, db/009) 그 후보만 정확 코사인으로 세운다
    from backend.services import llm
    if llm.DEMO_MODE:  # [왜] 평가자에게는 키가 없다. 데모 모드는 임베딩 API 없이 BM25만 쓴다(SPEC 7절)
        return []
    vec = np.asarray(llm.voyage_embed([question], 'query')[0], dtype=np.float32)  # 질문 하나를 임베딩해 첫 벡터를 꺼낸다
    # [주의] nocover_all은 retrieve()가 allowed=_nocover일 때만 켠다. 이 JOIN의 표지 제외 규칙이 _nocover(page_number가 있는 청크)와 같아야 한다
    join = ' JOIN document_chunks dc ON dc.id = t.chunk_id AND dc.page_number IS NOT NULL' if nocover_all else ''
    by_id, by_id_args = (' AND t.chunk_id = ANY(%s)', [list(allowed)]) if allowed is not None and not nocover_all else ('', [])
    # [왜] HNSW 인덱스는 한국어 질문처럼 먼 질의에서 가까운 청크를 놓쳤다(11-01 실측: ef_search 1000에서도 m03 질문의
    # 정확 검색 1위 거리 0.4177을 놓치고 0.4777을 1위로 냄). 청크 5만 장은 정확 검색이 질문당 0.3~0.6초라 인덱스를 끄고 잰다
    # shortcut: 정확 검색은 청크 수에 비례해 느려진다. 청크가 수십만 장이 되면 HNSW 설정을 사전 등록 실험으로 다시 정한다
    conn.execute('SET enable_indexscan = off')
    try:
        if allowed is not None and len(allowed) > N_BIT:
            # [주의] 질문 쪽도 저장 쪽(db/009)과 같은 binary_quantize(vector(DIM))::bit(DIM)이어야 한다. <~>는 Hamming 거리다
            cand = conn.execute(f'SELECT t.chunk_id FROM chunk_embedding_bits t{join} WHERE t.embedding_model = %s{by_id}'
                                f' ORDER BY t.bits <~> binary_quantize(%s::vector({DIM}))::bit({DIM}) LIMIT %s',
                                [EMBED_MODEL, *by_id_args, vec, N_BIT]).fetchall()
            join, by_id, by_id_args = '', ' AND t.chunk_id = ANY(%s)', [[r[0] for r in cand]]  # 2단계는 후보 안에서만(후보는 이미 표지 아닌 청크)
        # 저장만 halfvec으로 줄이고, 읽을 때와 질문 벡터는 float32로 거리를 잰다.
        # [주의] 열은 모델마다 차원이 다르도록 차원을 적지 않은 halfvec이다(db/008). 모델 행만 거른 뒤 DIM 차원 vector로 바꿔 잰다
        rows = conn.execute(f'SELECT t.chunk_id FROM chunk_embeddings t{join} WHERE t.embedding_model = %s{by_id}'
                            f' ORDER BY t.embedding::vector({DIM}) <=> %s::vector({DIM}) LIMIT %s', [EMBED_MODEL, *by_id_args, vec, N_CAND]).fetchall()
    finally:
        conn.execute('RESET enable_indexscan')
    return [r[0] for r in rows]


def _keyword(question, allowed=None):
    """질문의 BM25(키워드 검색) 상위 청크 id를 N_CAND개까지 돌려준다. allowed가 있으면 그 청크 안에서만 찾는다."""
    # [주의] _bm25는 warmup()이 만든다. retrieve()가 먼저 부르므로 여기서는 만들지 않는다
    index, ids = _bm25
    if index is None:
        return []
    scores = index.get_scores(tokens(question))
    if allowed is not None:  # 허용 밖 청크는 점수를 -inf로 바꿔 후보에서 뺀다
        scores = np.where(np.isin(ids, list(allowed)), scores, -np.inf)
    return positive_top(scores, ids, N_CAND)


def retrieve(question: str, *, k: int = 5, parts: list[str] | None = None, method: str = 'hybrid') -> list[dict]:
    """질문과 가까운 청크 k개을 method(기본 하이브리드)로 찾는다. 키·parts·method의 뜻은 docs/specs/rag-pipeline.md How를 따른다.

    입력: question, k(돌려줄 장수), parts(품번 필터. 주면 그 품번 문서 안에서만 찾고, 코퍼스에 없는 품번뿐이면 []), method('hybrid'|'dense'|'bm25').
    출력: {chunk_id, document_key, file, page, table, content, score, doc_parts, dense_rank, bm25_rank} 목록(리랭크한 순서, DEMO_MODE·dense·bm25 방식은 RRF 점수 높은 순). score는 RRF 점수다.
    주의: parts=None은 품번 필터 없음(표지 청크를 뺀 코퍼스 전체), parts=[]는 필터는 있되 허용 청크가 없으므로 []이다. method가 셋 밖이면 ValueError.
    """
    # [왜] 방식별 기준선(dense만·BM25만, evals/guides/preregister.md #16)을 같은 함수로 재려고 둔다
    env_method = os.getenv('RETRIEVE_METHOD', '').strip()
    if env_method:
        method = env_method  # [왜] 속도 A/B용. 비우면 호출 인자(기본 hybrid)를 쓴다
    if method not in ('hybrid', 'dense', 'bm25'):
        raise ValueError(f"method는 'hybrid', 'dense', 'bm25' 중 하나입니다: {method!r}")
    from backend.services import llm
    if _bm25 is None:
        warmup()
    # [왜] 표지 청크는 언제나 뺀다(사전 등록 #25의 part+kind). parts가 없으면 표지 아닌 청크 전체가 허용 범위다
    allowed = _nocover if parts is None else allowed_chunks(_parts, parts) & _nocover
    if not allowed:
        # [왜] 전체 코퍼스로 넘어가면 다른 부품의 수치를 인용하게 된다. 빈 결과를 받은 쪽이 "문서로 확인 안 됨"으로 판정한다
        return []
    with _connect() as conn:
        # [주의] DEMO_MODE=1에서 method='dense'는 dense 목록이 비어 늘 []를 돌려준다
        dense = _dense(conn, question, allowed, nocover_all=parts is None) if method != 'bm25' else []
        keyword = _keyword(question, allowed) if method != 'dense' else []
        fused = rrf(dense, keyword)  # 목록 하나만 있으면 RRF는 그 목록 순서를 그대로 둔다
        # [왜] hybrid만 리랭크. RETRIEVE_RERANK=0이면 RRF 상위 k만(Voyage rerank API 생략, 속도 A/B용)
        rerank = method == 'hybrid' and not llm.DEMO_MODE and os.getenv('RETRIEVE_RERANK', '1') != '0'
        top = fused if rerank else fused[:k]  # 리랭크는 합친 후보 전부를 본문과 함께 넘기므로 k장으로 자르지 않는다
        rows = conn.execute(
            'SELECT dc.id, sd.document_key, sd.source_url, dc.page_number, dc.table_name, dc.content, dc.document_id'
            ' FROM document_chunks dc JOIN source_documents sd ON sd.id = dc.document_id WHERE dc.id = ANY(%s)',
            ([i for i, _ in top],)).fetchall()
    found = {r[0]: r for r in rows}  # SQL의 ANY(...)는 순서를 보장하지 않아 id로 찾을 사전을 만든다
    if rerank and top:
        # [왜] 후보 id를 오름차순으로 정렬해 넘긴다. 점수는 (질문, 청크) 쌍마다 따로 매겨져 순서와 무관하고, 동점 순서만 고정된다(측정 설정 SortedReranker)
        ids = sorted(i for i, _ in top)
        rrf_score = dict(top)
        order = llm.voyage_rerank(question, [found[i][5] for i in ids])
        top = [(ids[j], rrf_score[ids[j]]) for j in order]
    top = top[:k]  # 리랭크 뒤에 상위 k개만 남긴다
    out = []  # top 순서대로 채운다
    for chunk_id, score in top:
        _, key, url, page, table, content, doc_id = found[chunk_id]
        out.append({'chunk_id': chunk_id, 'document_key': key, 'file': unquote(os.path.basename(urlparse(url).path)), 'page': page, 'table': table,
                    'content': content, 'score': score,
                    # [왜] 한 문서에 형제 품번(1N5817·1N5819) 줄이 섞여 있다. 채점이 다른 품번 줄을 거를 때 이 목록과 대조한다
                    'doc_parts': sorted(p for p, docs in _parts[0].items() if doc_id in docs),
                    'dense_rank': dense.index(chunk_id) + 1 if chunk_id in dense else None,
                    'bm25_rank': keyword.index(chunk_id) + 1 if chunk_id in keyword else None})
    return out
