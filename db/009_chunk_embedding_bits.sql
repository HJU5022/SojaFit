-- voyage-4-large 임베딩의 1비트 부호 코드. retrieve.py가 dense 1단계(Hamming 거리로 후보 N_BIT장 거르기)에 쓴다(사전 등록 #27).
-- [왜] 정확 코사인은 카드 5만 장 전체를 재서 느리다. 부호 비트만 비교하면 순차 스캔도 약 40 ms다(운영 DB 실측, ../전자_데이터시트/evidence/bq_exp).
-- [주의] 인덱스를 만들지 않는다. 약 5만 행 × 128바이트라 순차 스캔이 충분하고, 근사 인덱스는 정확 검색보다 후보를 더 놓칠 수 있다.
-- [주의] 모델마다 차원이 달라 이 표는 voyage-4-large(1024차원) 전용이다. 다시 실행해도 있는 행은 건드리지 않는다. 이후 적재는 ingest.py --voyage가 채운다.
CREATE TABLE IF NOT EXISTS chunk_embedding_bits (
    chunk_id BIGINT NOT NULL,
    embedding_model VARCHAR(200) NOT NULL,
    bits BIT(1024) NOT NULL,
    CONSTRAINT pk_chunk_embedding_bits PRIMARY KEY (chunk_id, embedding_model),
    CONSTRAINT fk_chunk_embedding_bits_chunk FOREIGN KEY (chunk_id) REFERENCES document_chunks (id) ON DELETE RESTRICT
);

-- [주의] 질문 쪽도 같은 변환(binary_quantize(vector(1024)))이라 halfvec을 vector로 바꾼 뒤 부호를 뽑는다(0 초과면 1)
INSERT INTO chunk_embedding_bits (chunk_id, embedding_model, bits)
SELECT chunk_id, embedding_model, binary_quantize(embedding::vector(1024))::bit(1024)
FROM chunk_embeddings WHERE embedding_model = 'voyage-4-large'
ON CONFLICT (chunk_id, embedding_model) DO NOTHING;
