"""DB 용량 점검(inspect)과 vector→halfvec 정확 검색 비교(compare)를 하는 오프라인 도구. 운영 DB를 변경하지 않는다.

- 역할: 오프라인 CLI(`python -m backend.rag.storage`)와, `vector_type`만 서버·다른 도구가 import한다.
  - vector_type: 환경변수 RAG_VECTOR_TYPE(vector|halfvec)을 읽어 돌려준다. ingest.py·retrieve.py가 server와 도구에서 import한다.
  - snapshot(inspect): DB 전체 크기, pgvector 버전, 임베딩 열 형식, RAG 표 세 개의 크기(250MB 목표 대비).
  - compare: 원본 vector(1536)와 halfvec으로 줄인 값의 가까운 청크 상위 5개이 얼마나 겹치는지 시료 1000개까지 잰다.
    읽기 전용 트랜잭션을 롤백하고, 시간 예산(max_seconds)을 넘으면 중간 결과에 timed_out을 달아 돌려준다.
- 하지 않는 일: 임베딩 API 호출, 표·인덱스 변경, 본문·벡터·DSN(DB 접속 주소) 출력. 검색은 `retrieve.py`, 적재는 `ingest.py`.
- 출처: docs/experiments/corpus-storage-budget.md, ADR 0005(halfvec 코퍼스), SPEC.md 6절
- 필요한 것: DATABASE_URL, uv 그룹의 psycopg·pgvector

실행: python -m backend.rag.storage inspect | compare [--samples 1000] [--max-seconds 120]
"""
import argparse
import json
import os
import random
import time

MODEL = 'openai/text-embedding-3-small'
DIM = 1536


def vector_type():
    """RAG_VECTOR_TYPE(기본 'vector')을 검사해 'vector' 또는 'halfvec'을 돌려준다. 그 밖의 값이면 ValueError."""
    kind = os.getenv('RAG_VECTOR_TYPE', 'vector')
    if kind not in {'vector', 'halfvec'}:
        raise ValueError('RAG_VECTOR_TYPE must be vector or halfvec')
    return kind


def _query(conn, sql, args=None, deadline=None):
    """SQL 하나를 실행한다. deadline(time.monotonic 기준)이 있으면 남은 시간만큼(최대 5초) statement_timeout을 건다."""
    # [주의] 이미 deadline이 지났으면 TimeoutError. compare가 이를 잡아 timed_out으로 중간 결과를 돌려준다
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('comparison time budget exhausted')
        # set_config의 세 번째 인자 true: 이 트랜잭션 안에서만 적용한다
        conn.execute("SELECT set_config('statement_timeout',%s,true)",
                     (str(max(1, min(5000, int(remaining * 1000)))),))
    return conn.execute(sql, args)


def snapshot(conn, deadline=None):
    """DB 전체 크기, pgvector 버전, 임베딩 열 형식, RAG 표 세 개의 크기를 사전으로 돌려준다."""
    # [주의] DSN·본문·벡터는 결과에 넣지 않는다
    version = _query(conn, "SELECT extversion FROM pg_extension WHERE extname='vector'", deadline=deadline).fetchone()
    typ = _query(conn, "SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
                       "WHERE attrelid=to_regclass('chunk_embeddings') AND attname='embedding' AND NOT attisdropped", deadline=deadline).fetchone()
    size = _query(conn, 'SELECT pg_database_size(current_database())', deadline=deadline).fetchone()[0]
    tables = _query(conn, "SELECT relname,pg_table_size(c.oid),pg_indexes_size(c.oid),pg_total_relation_size(c.oid) "
                          "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                          "WHERE n.nspname=current_schema() AND relname=ANY(%s) ORDER BY relname",
                          (['source_documents', 'document_chunks', 'chunk_embeddings'],), deadline=deadline).fetchall()
    return {'pgvector_version': version[0] if version else None, 'embedding_type': typ[0] if typ else None,
            'database_bytes': size, 'target_bytes': 250_000_000, 'within_target': size <= 250_000_000,
            'tables': [{'table': n, 'body_and_toast_bytes': b, 'index_bytes': i, 'total_bytes': t}
                       for n, b, i, t in tables]}


def compare(conn, samples=1000, max_seconds=120):
    """같은 원본 vector와 halfvec으로 줄인 값의 상위 5개 겹침을 시료 질의마다 재서 요약 사전으로 돌려준다."""
    # [왜] 질의 청크 자기 자신과 같은 본문(chunk_sha256)은 거리 0으로 늘 1위라 비교에서 뺀다
    if not 1 <= samples <= 1000 or not 0 < max_seconds <= 600:
        raise ValueError('samples must be 1..1000 and max_seconds must be >0 and <=600')
    deadline, rows, timed_out = time.monotonic() + max_seconds, [], False
    ids, selected, initialized = [], [], False
    import psycopg
    try:
        with conn.transaction(force_rollback=True):  # 읽기 전용 비교의 SET LOCAL도 호출자에게 남기지 않는다
            _query(conn, 'SET LOCAL enable_indexscan=off', deadline=deadline)
            if snapshot(conn, deadline)['embedding_type'] != 'vector(1536)':
                raise ValueError('comparison requires original vector(1536), not an already rounded halfvec table')
            ids = [r[0] for r in _query(conn, 'SELECT chunk_id FROM chunk_embeddings WHERE embedding_model=%s ORDER BY chunk_id',
                                        (MODEL,), deadline).fetchall()]
            initialized = True
            if not ids:
                raise ValueError('no original vectors for the configured embedding model')
            selected = sorted(random.Random(42).sample(ids, min(samples, len(ids))))
            for cid in selected:
                sha, query = _query(conn, 'SELECT dc.chunk_sha256,ce.embedding FROM document_chunks dc '
                                          'JOIN chunk_embeddings ce ON ce.chunk_id=dc.id '
                                          'WHERE ce.chunk_id=%s AND ce.embedding_model=%s', (cid, MODEL), deadline).fetchone()
                prefix = ('SELECT ce.chunk_id FROM chunk_embeddings ce JOIN document_chunks dc ON dc.id=ce.chunk_id '
                          'WHERE ce.embedding_model=%s AND dc.chunk_sha256<>%s ORDER BY ')
                ranks = []
                for distance in ['ce.embedding <=> %s::vector(1536)',
                                 'ce.embedding::halfvec(1536)::vector(1536) <=> %s::vector(1536)']:
                    ranks.append([r[0] for r in _query(conn, prefix + distance + ',ce.chunk_id LIMIT 5',
                                                      (MODEL, sha, query), deadline).fetchall()])
                rows.append({'query_id': cid, 'vector_top5': ranks[0], 'halfvec_top5': ranks[1],
                             'overlap': len(set(ranks[0]) & set(ranks[1])) / 5})
    except (psycopg.errors.QueryCanceled, TimeoutError):
        timed_out = True
    n = len(rows)
    complete = n == samples and not timed_out and all(len(r['vector_top5']) == len(r['halfvec_top5']) == 5 for r in rows)
    return {'model': MODEL, 'seed': 42, 'requested_samples': samples,
            'available_vectors': len(ids) if initialized else None, 'initialization_complete': initialized,
            'queries': n, 'sample_shortfall': max(0, samples - len(selected)) if initialized else None, 'timed_out': timed_out,
            'complete': complete, 'top5_overlap': sum(r['overlap'] for r in rows) / n if n else None,
            'exact_order_fraction': sum(r['vector_top5'] == r['halfvec_top5'] for r in rows) / n if n else None,
            'max_seconds': max_seconds, 'self_and_same_body_excluded': True, 'approximate_index_used': False,
            'halfvec_distance': 'float32', 'query_precision': 'float32',
            'official_eval': False, 'adoption_approved': False, 'rows': rows}


def main():
    """명령줄 인자(inspect|compare, --samples, --max-seconds)를 읽어 읽기 전용으로 DB에 연결하고 결과를 JSON으로 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'compare'])
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--max-seconds', type=float, default=120)
    args = parser.parse_args()
    import psycopg
    from pgvector.psycopg import register_vector
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        register_vector(conn)
        conn.execute('SET TRANSACTION READ ONLY')
        result = snapshot(conn) if args.command == 'inspect' else compare(conn, args.samples, args.max_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
