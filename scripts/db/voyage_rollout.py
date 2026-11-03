"""운영 DB에 voyage-4-large 검색 설정을 올리는 손 작업 3단계(점검 · 마이그레이션 · 검증).

- 역할: `check`(읽기 전용 점검), `migrate`(db/008 적용 + 적용 뒤 확인, 한 트랜잭션), `verify`(voyage 적재 뒤 확인).
- 하지 않는 일: 벡터 적재(`backend/rag/pipeline/ingest.py --voyage`), 검색 품질 측정(`evals/runners/run_retrieval_service.py`).
- 출처: db/008_multi_dim_embeddings.sql, evals/guides/preregister.md #26, docs/worklog/jeongun.md
- 실행(저장소 루트, DATABASE_URL 필요): uv run python scripts/db/voyage_rollout.py check|migrate|verify [벡터 폴더]
- 출력은 숫자와 상태뿐이다. 접속 문자열은 찍지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / 'db/008_multi_dim_embeddings.sql'
DEFAULT_VEC = ROOT.parent / '전자_데이터시트/evidence/full_grid/vectors'
OLD_MODEL, NEW_MODEL, NEW_DIM = 'openai/text-embedding-3-small', 'voyage-4-large', 1024
LIMIT_MB = 420  # [왜] 요금제 한도 500 MB에서 여유를 80 MB 남긴다
ROW_OVERHEAD = 100  # 행 머리 · chunk_id · 모델 이름 · 기본 키 색인을 합친 어림 바이트
MB = 1024 * 1024


def stop_reasons(coltype, projected_bytes):
    """멈춰야 하는 이유 목록. 비어 있으면 진행해도 된다."""
    out = []
    if coltype not in ('halfvec(1536)', 'halfvec'):
        out.append(f'열 형식이 halfvec(1536)/halfvec가 아니다: {coltype}')
    if projected_bytes > LIMIT_MB * MB:
        out.append(f'적재 뒤 예상 크기 {projected_bytes / MB:.1f} MB가 {LIMIT_MB} MB를 넘는다')
    return out


def projected_size(db_bytes, n_chunks):
    """voyage 행 n_chunks개(1024차원 halfvec = 차원당 2바이트 + 머리 4바이트)를 더한 DB 크기."""
    return db_bytes + n_chunks * (NEW_DIM * 2 + 4 + ROW_OVERHEAD)


def snapshot(conn):
    """현재 상태 숫자 묶음(읽기 전용)."""
    q = lambda sql, *a: conn.execute(sql, a or None).fetchone()[0]  # [주의] 인자 없이 빈 튜플을 넘기면 psycopg가 LIKE의 %를 자리표시로 읽는다
    return {
        'coltype': q("SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid = 'chunk_embeddings'::regclass"
                     " AND attname = 'embedding' AND NOT attisdropped"),
        'db_bytes': q('SELECT pg_database_size(current_database())'),
        'emb_bytes': q("SELECT pg_total_relation_size('chunk_embeddings')"),
        'chunk_bytes': q("SELECT pg_total_relation_size('document_chunks')"),
        'models': dict(conn.execute('SELECT embedding_model, count(*) FROM chunk_embeddings GROUP BY 1 ORDER BY 1').fetchall()),
        'n_chunks': q('SELECT count(*) FROM document_chunks'),
        'hnsw': q("SELECT count(*) FROM pg_indexes WHERE tablename = 'chunk_embeddings' AND indexdef ILIKE '%hnsw%'"),
        'pgvector': q("SELECT extversion FROM pg_extension WHERE extname = 'vector'"),
        'filenode': q("SELECT pg_relation_filenode('chunk_embeddings')"),
    }


def check(conn):
    """점검 결과를 찍고 STOP 이유 목록을 돌려준다."""
    s = snapshot(conn)
    proj = projected_size(s['db_bytes'], s['n_chunks'])
    print(f"열 형식 {s['coltype']} | pgvector {s['pgvector']} | HNSW 색인 {s['hnsw']}개 | filenode {s['filenode']}")
    print(f"DB {s['db_bytes'] / MB:.1f} MB | chunk_embeddings {s['emb_bytes'] / MB:.1f} MB | document_chunks {s['chunk_bytes'] / MB:.1f} MB")
    print(f"모델별 행 수 {s['models']} | document_chunks {s['n_chunks']}")
    print(f"voyage {s['n_chunks']}행 적재 뒤 예상 DB 크기 {proj / MB:.1f} MB (한도 {LIMIT_MB} MB)")
    reasons = stop_reasons(s['coltype'], proj)
    for r in reasons:
        print(f'STOP: {r}')
    if not reasons:
        print('OK: 진행해도 된다')
    return reasons


def migrate(conn):
    if check(conn):
        sys.exit('STOP이라 마이그레이션을 하지 않는다')
    before = snapshot(conn)
    conn.execute(SQL.read_text(encoding='utf-8'))  # [주의] 매개변수 없이 실행해야 SQL 안의 %를 그대로 둔다. 연결을 닫기 전까지 한 트랜잭션이다
    after = snapshot(conn)  # 같은 트랜잭션 안이라 아직 적용 전 다른 세션에는 보이지 않는다
    print(f"filenode {before['filenode']} -> {after['filenode']} ({'바뀜: 표를 다시 썼다' if before['filenode'] != after['filenode'] else '같음: 다시 쓰지 않았다'})")
    print(f"열 형식 {after['coltype']} | HNSW 색인 {after['hnsw']}개 | 행 수 {after['models']}")
    bad = [m for m, ok in [('열 형식이 halfvec이 아니다', after['coltype'] == 'halfvec'), ('HNSW 색인이 남았다', after['hnsw'] == 0),
                           ('행 수가 달라졌다', after['models'] == before['models'])] if not ok]
    # 옛 서비스 질의 모양이 새 열에서도 되는지(배포된 옛 코드가 계속 도는지)
    row = conn.execute('SELECT embedding::vector(1536) FROM chunk_embeddings WHERE embedding_model = %s LIMIT 1', [OLD_MODEL]).fetchone()
    if row is None:
        bad.append('3-small 벡터가 없어 옛 질의를 시험하지 못했다')
    else:
        got = conn.execute('SELECT chunk_id FROM chunk_embeddings WHERE embedding_model = %s'
                           ' ORDER BY embedding::vector(1536) <=> %s::vector(1536) LIMIT 5', [OLD_MODEL, row[0]]).fetchall()
        print(f'옛 질의 모양 결과 {len(got)}행')
        if len(got) != 5:
            bad.append('옛 질의 모양이 5행을 돌려주지 않았다')
    if bad:
        raise SystemExit('확인 실패, 롤백한다: ' + ' / '.join(bad))  # with 블록이 예외로 끝나 롤백된다
    print('확인 통과, 커밋한다')


def verify(conn, vec_dir):
    import numpy as np
    from backend.rag.pipeline.ingest import VOYAGE_DIM, VectorCache
    n_voy = conn.execute('SELECT count(*) FROM chunk_embeddings WHERE embedding_model = %s', [NEW_MODEL]).fetchone()[0]
    n_chunks = conn.execute('SELECT count(*) FROM document_chunks').fetchone()[0]
    print(f'{NEW_MODEL} 행 {n_voy} / document_chunks {n_chunks} -> {"맞음" if n_voy == n_chunks else "다름"}')
    cache = VectorCache(vec_dir, 'v4large', VOYAGE_DIM)
    rows = conn.execute('SELECT ce.chunk_id, dc.chunk_sha256, ce.embedding::vector(1024) FROM chunk_embeddings ce'
                        ' JOIN document_chunks dc ON dc.id = ce.chunk_id WHERE ce.embedding_model = %s ORDER BY random() LIMIT 5', [NEW_MODEL]).fetchall()  # 5건만 받아 전송량을 줄인다
    cos = []
    for _, sha, vec in rows:
        # [주의] pgvector는 Vector 객체로 돌려줘 to_numpy()로 바꾼다
        a, b = np.asarray(vec.to_numpy(), dtype=np.float32), np.asarray(cache.get(sha.strip()), dtype=np.float32)
        cos.append(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))))
    ok = n_voy == n_chunks and len(cos) == 5 and min(cos) >= 0.999
    print(f'무작위 5건 코사인 {[round(c, 5) for c in cos]} (최소 {min(cos, default=0):.5f}, 기준 0.999)')
    print(f"DB {conn.execute('SELECT pg_database_size(current_database())').fetchone()[0] / MB:.1f} MB")
    print('verify 통과' if ok else 'verify 실패')
    return ok


def main(argv):
    if not argv or argv[0] not in ('check', 'migrate', 'verify'):
        sys.exit('사용법: voyage_rollout.py check|migrate|verify [벡터 폴더]')
    from dotenv import load_dotenv
    load_dotenv()  # [왜] DATABASE_URL을 .env에서 읽는다(llm.py와 같은 방식). 이 스크립트는 llm을 import하지 않는다
    from backend.rag.retrieve import _connect
    with _connect() as conn:  # 예외 없이 끝나면 커밋, 예외면 롤백
        if argv[0] == 'check':
            return 1 if check(conn) else 0
        if argv[0] == 'migrate':
            migrate(conn)
            return 0
        return 0 if verify(conn, argv[1] if len(argv) > 1 else DEFAULT_VEC) else 1


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    sys.exit(main(sys.argv[1:]))
