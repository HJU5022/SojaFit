# 운영 DB 인덱스 행 수 조회 (2026-11-13)

G3 증거. 운영 DB의 코퍼스 표 행 수를 읽기 전용으로 센 기록이다.

## 조회 결과

- 대상: Supabase 프로젝트 `SojaFit_2`, 브랜치 `main`(PRODUCTION), DB `postgres`
- 시각: 2026-11-13 01:07:40 UTC (10:07 KST)
- 실행: 하정운이 Supabase SQL Editor에서 아래 쿼리를 그대로 실행했다. 읽기 전용 트랜잭션이라 쓰기는 없다.

| documents | chunks | distinct_chunks | chunkers | embeddings | embedding_bits |
|---|---|---|---|---|---|
| 1360 | 51967 | 51967 | tsc-v4h-2026-11-08 | 51967 | 51967 |

- `distinct_chunks`는 DB에 저장된 `chunk_sha256` 열의 서로 다른 값 수다. 본문(`content`)에서 sha256을 다시 계산한 값은 아니다.
- 청크 51,967개는 청킹 산출물의 [`chunk_sha256.tsv`](../chunking/v4h-2026-11-08/chunk_sha256.tsv)(51,967행), [`corpus_v4h_fingerprint_2026-11-12.md`](corpus_v4h_fingerprint_2026-11-12.md)의 `cards`와 수가 같다.

## 다시 보는 방법

Supabase 대시보드 → `SojaFit_2` → SQL Editor에 붙여 넣고 Run. `psql "$DATABASE_URL"`에서도 같다.

```sql
BEGIN READ ONLY;
SELECT
  (SELECT count(*) FROM source_documents)                          AS documents,
  (SELECT count(*) FROM document_chunks)                           AS chunks,
  (SELECT count(DISTINCT chunk_sha256) FROM document_chunks)       AS distinct_chunks,
  (SELECT string_agg(DISTINCT chunker_version, ',') FROM document_chunks) AS chunkers,
  (SELECT count(*) FROM chunk_embeddings WHERE embedding_model = 'voyage-4-large') AS embeddings,
  (SELECT count(*) FROM chunk_embedding_bits)                      AS embedding_bits,
  now() AS queried_at, current_database() AS db;
ROLLBACK;
```

## 52,244에서 51,967로 바뀐 날짜와 이유

- **날짜**: 2026-11-09 05:12~05:13 KST. 옛 운영 Supabase의 코퍼스 표를 비우고 v4h 청킹 결과로 다시 넣었다.
- **이유**: 청킹을 v1(`data/manifest.jsonl`, 52,244청크)에서 `tsc-v4h-2026-11-08`(51,967청크)로 바꿨다. v4h는 표 한 행을 카드 하나로 만들고, 병합 칸·머리행과 표 주석을 카드에 붙인다([ADR 0015](../../../docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md), [SPEC.md](../../../SPEC.md) 청킹 절).
- **교체 전후 행 수 원본**: [`corpus_swap_2026-11-09/check.log.txt`](corpus_swap_2026-11-09/check.log.txt)(교체 전 `document_chunks` 52,244행), [`corpus_swap_2026-11-09/verify.log.txt`](corpus_swap_2026-11-09/verify.log.txt)(교체 뒤 51,967행, `chunker_version`=`tsc-v4h-2026-11-08`). 조장 개인 기록에서 옮겨 왔다(2026-11-13).
- 2026-11-11 04:25에 운영 DB를 새 프로젝트 `SojaFit_2`로 옮길 때 코퍼스 표는 그대로 복사했다. 위 조회가 그 상태다.
- Checkpoint 대시보드의 52,244는 저장소 `data/manifest.jsonl`(v1)의 합계다.
