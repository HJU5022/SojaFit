# bit_search

## 역할
- 이 폴더: 비트 후보(1비트 사본 Hamming) + pgvector 정확 재정렬이 검색 속도와 recall을 얼마나 바꾸는지 운영 DB에서 재는 실험 스크립트를 둡니다.
- 넣는 것: 실험 표(`exp_bq`)를 만들어 재고 지우는 스크립트. 저장소 루트에서 `DATABASE_URL`을 준 채 실행합니다.
- 넣지 않는 것: 원시 결과(`scripts/results/bit_search/`), 해석([bit-search-measurement-2026-11-03.md](../../docs/research/bit-search-measurement-2026-11-03.md)), 서비스에 들어간 비트 검색 코드(`backend/rag/`), 비트 사본 표의 마이그레이션(`db/009_chunk_embedding_bits.sql`).
- 담당: 서비스·운영

## 파일
- `BIT_SEARCH.md` — 이 문서
- `bit_search_exp.py` — `embed`(질문 벡터 50개 만들기) → `setup`(`exp_bq` 만들기) → `measure`(정확 검색과 비트 N=400·800·1,600·3,200 시간·recall) → `warm`(비트 검색만 이어서) → `final`(v1 관련 19문항 최종 점수 확인) → `report` → `drop`. 입출력 폴더는 `BIT_SEARCH_WORK`(기본 `../전자_데이터시트/evidence/bq_exp`)

## 주의
- 측정 당시(11-03) 운영 DB는 `text-embedding-3-small` `halfvec(1536)`이었습니다. 11-04부터 운영 DB는 voyage-4-large만 있어 이 스크립트는 그대로는 돌지 않습니다. 다시 재려면 모델 이름과 차원을 바꿔야 합니다.
- `setup`은 운영 DB에 실험 표를 만들므로 `drop`까지 하루 안에 끝냅니다(DB 크기 한도 500MB).
