"""검색: 하이브리드(BM25 + 벡터)를 RRF로 합친다. 품번 필터(parts)와 검색 방식(method)을 검색 인자로 받는다. 리랭킹은 사전 등록 뒤 더한다.

- 역할: 서버와 평가 도구가 import하는 검색 함수 `retrieve`. 질문을 embed_texts로 숫자로 바꿔 pgvector 코사인 거리 상위 50장을, 같은 질문의 BM25 상위 50장을 구해
  RRF(카드마다 1/(60 + 순위)의 합)로 합치고 상위 k장을 돌려준다. parts를 주면 그 품번이 표지에 적힌 문서의 카드 안에서만 찾는다.
  method='dense'면 dense 목록만, 'bm25'면 BM25 목록만 쓰고 임베딩 API를 부르지 않는다(기본 'hybrid').
  DEMO_MODE=1(키 없는 데모)이면 임베딩 API를 부르지 않고 BM25만으로 찾는다(SPEC 7절).
- 하지 않는 일: 리랭킹, 품번 밖 메타데이터 필터(분류·패키지 등), 질문에서 품번 뽑기(에이전트가 parts로 준다, `backend/graph/nodes.py`), 답변 생성, 판정(`backend/judge/`).
- 출처: docs/specs/rag-pipeline.md What 6·How·AC-05~AC-11·EC-06~EC-08, EVAL_REPORT.md 1장 하이브리드 검색 비교·HNSW 개선 실험 B,
  evals/guides/preregister.md #6·#16, SPEC.md 7절

[주의] 대상 필터(품번 등)는 결과를 받은 뒤 거르지 않고 검색 단계의 인자로 받는다. 후처리로 거르면 결과가 0~2개로 굶어
"우연한 거절"이 생기고 점수가 실제보다 좋게 나온다. score의 뜻과 범위는 검색 방식마다 달라 거절 임계값도 방식마다 따로 정한다.
"""
import os
import re
from urllib.parse import unquote, urlparse

# [왜] FastMCP 요청 worker에서 처음 import하면 첫 search_corpus가 멈출 수 있어 서버 시작 스레드에서 미리 읽는다.
import numpy as np

from backend.rag.storage import vector_type

N_CAND = 50  # 방식마다 합치기 전에 가져오는 후보 수
# RRF 점수 1/(RRF_K + 순위)의 상수. 클수록 1위와 10위의 점수 차가 줄어 순위 차이를 덜 따진다
RRF_K = 60   # [왜] RRF 원 논문(Cormack 외 2009)의 기본값
EMBED_MODEL = 'openai/text-embedding-3-small'  # chunk_embeddings.embedding_model과 같아야 한다
_bm25 = None  # (BM25Okapi, 카드 id 목록). warmup()이 한 번 만든다
_parts = None  # (품번 소문자 → 문서 id 집합, 문서 id → 카드 id 목록). warmup()이 같이 만든다
COVER = re.compile(r'\[.+?\] 이 데이터시트의 품번: (.*)')  # chunk.py doc_cards가 만드는 표지 카드(chunk_index 0)


def tokens(text):
    """영문·숫자 연속을 소문자 토큰으로 자른다."""
    # [주의] "1N5819는" → "1n5819"처럼 한국어 조사가 떨어진다. 대신 한국어 단어는 BM25에서 빠진다(데이터시트가 영문이라)
    return re.findall(r'[a-z0-9]+', text.lower())


def rrf(*rankings):
    """순위 목록 여러 개를 카드마다 1/(RRF_K + 순위)의 합으로 합쳐 (id, 점수)를 높은 순으로 돌려준다(AC-05).

    RRF(Reciprocal Rank Fusion): 두 목록 모두에 높은 순위로 든 카드가 한쪽에만 든 카드보다 위로 간다.
    """
    # [왜] BM25 점수와 코사인 거리는 단위가 달라 더할 수 없다. 순위만 쓰면 가중치를 정하지 않아도 된다
    score = {}
    for ranking in rankings:
        for r, key in enumerate(ranking, 1):  # 순위는 1부터 센다
            score[key] = score.get(key, 0) + 1 / (RRF_K + r)
    return sorted(score.items(), key=lambda kv: kv[1], reverse=True)


def part_index(rows):
    """(카드 id, 문서 id, 본문) 목록에서 (품번 소문자 → 문서 id 집합, 문서 id → 카드 id 목록)을 만든다."""
    part_docs, doc_chunks = {}, {}
    for chunk_id, doc_id, content in rows:
        doc_chunks.setdefault(doc_id, []).append(chunk_id)
        m = COVER.match(content)
        if m:  # [왜] 품번 목록은 표지 카드에만 있다. 표지가 문서의 모든 품번을 쉼표로 나열한다
            for part in m.group(1).split(', '):
                part_docs.setdefault(part.strip().lower(), set()).add(doc_id)
    return part_docs, doc_chunks


def allowed_chunks(index, parts):
    """parts 중 하나라도 표지에 적힌 문서의 카드 id 집합을 돌려준다(AC-08·AC-09). 코퍼스에 없는 품번뿐이면 빈 집합이다."""
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
    # [주의] 첫 retrieve() 때 한 번 불린다. 서버 기동 때 미리 부르는 연결은 아직 없어 첫 질문이 느리다
    global _bm25, _parts
    from rank_bm25 import BM25Okapi
    with _connect() as conn:
        rows = conn.execute('SELECT id, document_id, content FROM document_chunks ORDER BY id').fetchall()
    # BM25Okapi: 질문 토큰이 카드에 몇 번 나오는지(tf)와 그 토큰이 드문 정도(idf)로 점수를 매기고 카드 길이로 보정한다
    # [주의] 적재 전 빈 DB에서는 BM25Okapi가 0으로 나눈다. 카드가 없으면 키워드 후보 없이 dense만 쓴다
    _bm25 = (BM25Okapi([tokens(c) for _, _, c in rows]) if rows else None, [i for i, _, _ in rows])
    _parts = part_index(rows)


def positive_top(scores, ids, n):
    """BM25 점수가 0보다 큰 카드 id를 높은 순으로 n개까지 돌려준다. 질문 단어가 하나도 안 맞으면 빈 목록이다(AC-10)."""
    # [왜] 점수 0인 카드까지 넣으면 질문과 상관없는 카드 50장이 RRF 후보로 들어간다(허용 밖 -inf도 같이 빠진다)
    return [ids[j] for j in np.argsort(-np.asarray(scores), kind='stable')[:n] if scores[j] > 0]


def _dense(conn, question, allowed=None):
    """질문 벡터와 코사인 거리가 가까운 카드 id를 N_CAND개까지 가까운 순으로 돌려준다(벡터 검색, dense)."""
    # allowed가 있으면 그 카드 안에서만 잰다. DEMO_MODE면 빈 목록(AC-11)
    from backend.services import llm
    if llm.DEMO_MODE:  # [왜] 평가자에게는 키가 없다. 데모 모드는 임베딩 API 없이 BM25만 쓴다(SPEC 7절)
        return []
    kind = vector_type()
    vec = np.asarray(llm.embed_texts([question])[0][0], dtype=np.float32)  # 질문 하나를 임베딩해 첫 벡터를 꺼낸다
    sql, args = 'SELECT chunk_id FROM chunk_embeddings WHERE embedding_model = %s', [EMBED_MODEL]
    if allowed is not None:  # 품번 필터: 허용한 카드 안에서만 거리를 잰다(검색 단계에서 거름)
        sql, args = sql + ' AND chunk_id = ANY(%s)', args + [list(allowed)]
    # [왜] HNSW 인덱스는 한국어 질문처럼 먼 질의에서 가까운 카드를 놓쳤다(11-01 실측: ef_search 1000에서도 m03 질문의
    # 정확 검색 1위 거리 0.4177을 놓치고 0.4777을 1위로 냄). 카드 5만 장은 정확 검색이 질문당 0.3~0.6초라 인덱스를 끄고 잰다
    # shortcut: 정확 검색은 카드 수에 비례해 느려진다. 카드가 수십만 장이 되면 HNSW 설정을 사전 등록 실험으로 다시 정한다
    conn.execute('SET enable_indexscan = off')
    try:
        # 저장만 halfvec으로 줄이고, 읽을 때와 질문 벡터는 float32로 거리를 잰다.
        column = 'embedding::vector(1536)' if kind == 'halfvec' else 'embedding'
        rows = conn.execute(sql + f' ORDER BY {column} <=> %s::vector(1536) LIMIT %s', args + [vec, N_CAND]).fetchall()
    finally:
        conn.execute('RESET enable_indexscan')
    return [r[0] for r in rows]


def _keyword(question, allowed=None):
    """질문의 BM25(키워드 검색) 상위 카드 id를 N_CAND개까지 돌려준다. allowed가 있으면 그 카드 안에서만 찾는다."""
    # [주의] _bm25는 warmup()이 만든다. retrieve()가 먼저 부르므로 여기서는 만들지 않는다
    index, ids = _bm25
    if index is None:
        return []
    scores = index.get_scores(tokens(question))
    if allowed is not None:  # 허용 밖 카드는 점수를 -inf로 바꿔 후보에서 뺀다
        scores = np.where(np.isin(ids, list(allowed)), scores, -np.inf)
    return positive_top(scores, ids, N_CAND)


def retrieve(question: str, *, k: int = 5, parts: list[str] | None = None, method: str = 'hybrid') -> list[dict]:
    """질문과 가까운 카드 k장을 method(기본 하이브리드)로 찾는다. 키·parts·method의 뜻은 docs/specs/rag-pipeline.md How를 따른다.

    입력: question, k(돌려줄 장수), parts(품번 필터. 주면 그 품번 문서 안에서만 찾고, 코퍼스에 없는 품번뿐이면 []), method('hybrid'|'dense'|'bm25').
    출력: {chunk_id, document_key, file, page, table, content, score, doc_parts, dense_rank, bm25_rank} 목록(RRF 점수 높은 순).
    주의: parts=None은 필터 없음(코퍼스 전체), parts=[]는 필터는 있되 허용 카드가 없으므로 []이다. method가 셋 밖이면 ValueError.
    """
    # [왜] 방식별 기준선(dense만·BM25만, evals/guides/preregister.md #16)을 같은 함수로 재려고 둔다
    if method not in ('hybrid', 'dense', 'bm25'):
        raise ValueError(f"method는 'hybrid', 'dense', 'bm25' 중 하나입니다: {method!r}")
    if _bm25 is None:
        warmup()
    allowed = None if parts is None else allowed_chunks(_parts, parts)
    if allowed is not None and not allowed:
        # [왜] 전체 코퍼스로 넘어가면 다른 부품의 수치를 인용하게 된다. 빈 결과를 받은 쪽이 "문서로 확인 안 됨"으로 판정한다
        return []
    with _connect() as conn:
        # [주의] DEMO_MODE=1에서 method='dense'는 dense 목록이 비어 늘 []를 돌려준다
        dense = _dense(conn, question, allowed) if method != 'bm25' else []
        keyword = _keyword(question, allowed) if method != 'dense' else []
        top = rrf(dense, keyword)[:k]  # 목록 하나만 있으면 RRF는 그 목록 순서를 그대로 둔다. [:k]로 상위 k장만 남긴다
        rows = conn.execute(
            'SELECT dc.id, sd.document_key, sd.source_url, dc.page_number, dc.table_name, dc.content, dc.document_id'
            ' FROM document_chunks dc JOIN source_documents sd ON sd.id = dc.document_id WHERE dc.id = ANY(%s)',
            ([i for i, _ in top],)).fetchall()
    found = {r[0]: r for r in rows}  # SQL의 ANY(...)는 순서를 보장하지 않아 id로 찾을 사전을 만든다
    out = []  # top의 RRF 순서대로 채운다
    for chunk_id, score in top:
        _, key, url, page, table, content, doc_id = found[chunk_id]
        out.append({'chunk_id': chunk_id, 'document_key': key, 'file': unquote(os.path.basename(urlparse(url).path)), 'page': page, 'table': table,
                    'content': content, 'score': score,
                    # [왜] 한 문서에 형제 품번(1N5817·1N5819) 줄이 섞여 있다. 채점이 다른 품번 줄을 거를 때 이 목록과 대조한다
                    'doc_parts': sorted(p for p, docs in _parts[0].items() if doc_id in docs),
                    'dense_rank': dense.index(chunk_id) + 1 if chunk_id in dense else None,
                    'bm25_rank': keyword.index(chunk_id) + 1 if chunk_id in keyword else None})
    return out
