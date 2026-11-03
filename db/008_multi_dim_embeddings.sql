-- 임베딩 열을 차원 없는 halfvec으로 바꿔 3-small(1536차원, 되돌릴 때 쓸 기존 행)과 voyage-4-large(1024차원) 행을 한 표에 둔다
-- (ADR 0004 갱신 2026-11-03, ADR 0005 halfvec 저장). 기존 열이 vector(1536)이든 halfvec(1536)이든 되고, 다시 실행해도 된다.
-- [주의] 차원 없는 열에는 HNSW 인덱스를 걸 수 없다. backend/rag/retrieve.py는 인덱스를 쓰지 않고 정확 검색을 하므로(002 주석) 인덱스를 지운다.
-- [왜] halfvec(n)이면 USING 없이 차원 표시만 뗀다. 같은 타입이라 표를 다시 쓰지 않아 500 MB 요금제에서 표가 잠시 두 배가 되지 않을 것으로 본다(실측: scripts/db/voyage_rollout.py migrate의 filenode 전후).
-- [주의] vector(n)이면 halfvec으로 바꾸며 표를 다시 쓴다. 쓰는 동안 옛 표와 새 표가 함께 디스크를 차지하므로 DB 여유 용량을 먼저 확인한다.
DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw;

DO $$
DECLARE
    col text;
BEGIN
    SELECT format_type(atttypid, atttypmod) INTO col FROM pg_attribute
    WHERE attrelid = 'chunk_embeddings'::regclass AND attname = 'embedding' AND NOT attisdropped;
    IF col LIKE 'halfvec(%' THEN
        ALTER TABLE chunk_embeddings ALTER COLUMN embedding TYPE halfvec;
    ELSIF col LIKE 'vector(%' THEN
        ALTER TABLE chunk_embeddings ALTER COLUMN embedding TYPE halfvec USING embedding::halfvec;
    END IF;
END $$;
