"""검색: 하이브리드(BM25 + 벡터)를 RRF로 합친다. 리랭킹과 메타데이터 필터는 사전 등록 뒤 더한다.

- 하는 일: 질문을 embed_texts로 숫자로 바꿔 pgvector 코사인 거리 상위 50장을, 같은 질문의 BM25 상위 50장을 구해
  RRF(카드마다 1/(60 + 순위)의 합)로 합치고 상위 k장을 돌려준다.
- 하지 않는 일: 리랭킹, 메타데이터 필터, 답변 생성. 판정(backend/judge/)
- 출처: docs/specs/rag-pipeline.md What 6·How·AC-05·AC-06, EVAL_REPORT.md 1장 하이브리드 검색 비교

인터페이스 권고:
  - 대상 필터(예: 기업이나 문서 종류)는 검색 결과를 받은 뒤 거르지 말고 검색 단계의 인자로 받는다.
    후처리로 거르면 결과가 0~2개로 굶어 "우연한 거절"이 생기고 점수가 실제보다 좋게 나온다.
  - 모델을 쓴다면 warmup()을 두고 서버 기동 때 한 번 부른다(첫 질문이 느려지지 않게).
  - 검색 방식(BM25, 벡터, 하이브리드, 리랭킹)마다 score의 뜻과 범위가 다르다. 거절 임계값은 방식마다 따로 정한다.
"""
import os
import re
from urllib.parse import unquote, urlparse

N_CAND = 50  # 방식마다 합치기 전에 가져오는 후보 수
RRF_K = 60   # [왜] RRF 원 논문(Cormack 외 2009)의 기본값
EMBED_MODEL = 'openai/text-embedding-3-small'  # chunk_embeddings.embedding_model과 같아야 한다
_bm25 = None  # (BM25Okapi, 카드 id 목록). warmup()이 한 번 만든다


def tokens(text):
    """영문·숫자 연속을 소문자 토큰으로 자른다."""
    # [주의] "1N5819는" → "1n5819"처럼 한국어 조사가 떨어진다. 대신 한국어 단어는 BM25에서 빠진다(데이터시트가 영문이라)
    return re.findall(r'[a-z0-9]+', text.lower())


def rrf(*rankings):
    """순위 목록 여러 개를 카드마다 1/(RRF_K + 순위)의 합으로 합쳐 (id, 점수)를 높은 순으로 돌려준다."""
    # [왜] BM25 점수와 코사인 거리는 단위가 달라 더할 수 없다. 순위만 쓰면 가중치를 정하지 않아도 된다
    score = {}
    for ranking in rankings:
        for r, key in enumerate(ranking, 1):
            score[key] = score.get(key, 0) + 1 / (RRF_K + r)
    return sorted(score.items(), key=lambda kv: kv[1], reverse=True)


def _connect():
    import psycopg
    from pgvector.psycopg import register_vector
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    register_vector(conn)
    return conn


def warmup():
    """document_chunks 본문으로 BM25 색인을 메모리에 만든다. 서버 기동 때 한 번 부른다."""
    global _bm25
    from rank_bm25 import BM25Okapi
    with _connect() as conn:
        rows = conn.execute('SELECT id, content FROM document_chunks ORDER BY id').fetchall()
    # BM25Okapi: 질문 토큰이 카드에 몇 번 나오는지(tf)와 그 토큰이 드문 정도(idf)로 점수를 매기고 카드 길이로 보정한다
    # [주의] 적재 전 빈 DB에서는 BM25Okapi가 0으로 나눈다. 카드가 없으면 키워드 후보 없이 dense만 쓴다
    _bm25 = (BM25Okapi([tokens(c) for _, c in rows]) if rows else None, [i for i, _ in rows])


def _dense(conn, question):
    import numpy as np
    from backend.services.llm import embed_texts
    vec = np.asarray(embed_texts([question])[0][0], dtype=np.float32)
    # [왜] HNSW 인덱스는 한국어 질문처럼 먼 질의에서 가까운 카드를 놓쳤다(11-01 실측: ef_search 1000에서도 m03 질문의
    # 정확 검색 1위 거리 0.4177을 놓치고 0.4777을 1위로 냄). 카드 5만 장은 정확 검색이 질문당 0.3~0.6초라 인덱스를 끄고 잰다
    # shortcut: 정확 검색은 카드 수에 비례해 느려진다. 카드가 수십만 장이 되면 HNSW 설정을 사전 등록 실험으로 다시 정한다
    conn.execute('SET enable_indexscan = off')
    rows = conn.execute('SELECT chunk_id FROM chunk_embeddings WHERE embedding_model = %s'
                        ' ORDER BY embedding <=> %s LIMIT %s', (EMBED_MODEL, vec, N_CAND)).fetchall()
    conn.execute('RESET enable_indexscan')
    return [r[0] for r in rows]


def _keyword(question):
    import numpy as np
    if _bm25 is None:
        warmup()
    index, ids = _bm25
    if index is None:
        return []
    scores = index.get_scores(tokens(question))
    return [ids[j] for j in np.argsort(-scores, kind='stable')[:N_CAND]]


def retrieve(question: str, *, k: int = 5) -> list[dict]:
    """질문과 가까운 카드 k장을 하이브리드로 찾는다. 키는 docs/specs/rag-pipeline.md How를 따른다."""
    with _connect() as conn:
        dense, keyword = _dense(conn, question), _keyword(question)
        top = rrf(dense, keyword)[:k]
        rows = conn.execute(
            'SELECT dc.id, sd.document_key, sd.source_url, dc.page_number, dc.table_name, dc.content'
            ' FROM document_chunks dc JOIN source_documents sd ON sd.id = dc.document_id WHERE dc.id = ANY(%s)',
            ([i for i, _ in top],)).fetchall()
    found = {r[0]: r for r in rows}
    out = []
    for chunk_id, score in top:
        _, key, url, page, table, content = found[chunk_id]
        out.append({'chunk_id': chunk_id, 'document_key': key, 'file': unquote(os.path.basename(urlparse(url).path)), 'page': page, 'table': table,
                    'content': content, 'score': score,
                    'dense_rank': dense.index(chunk_id) + 1 if chunk_id in dense else None,
                    'bm25_rank': keyword.index(chunk_id) + 1 if chunk_id in keyword else None})
    return out
