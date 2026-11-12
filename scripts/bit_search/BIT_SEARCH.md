# bit_search

## 역할
- 이 폴더: 비트 후보(1비트 사본 Hamming) + pgvector 정확 재정렬이 검색 속도와 recall을 얼마나 바꾸는지 운영 DB에서 재는 실험 스크립트를 둔다.
- 넣는 것: 실험 표(`exp_bq`)를 만들어 재고 지우는 스크립트. 저장소 루트에서 `DATABASE_URL`을 준 채 실행한다.
- 넣지 않는 것: 원시 결과(`scripts/results/bit_search/`), 해석([bit-search-measurement-2026-11-03.md](../../docs/research/bit-search-measurement-2026-11-03.md)), 서비스에 들어간 비트 검색 코드(`backend/rag/`), 비트 사본 표의 마이그레이션(`db/009_chunk_embedding_bits.sql`).
- 담당: 서비스·운영

## 파일

| 파일 | 분류 | 분류 근거 | 설명과 명령 |
|---|---|---|---|
| `BIT_SEARCH.md` | | | 이 문서 |
| `bit_search_exp.py` | 재현용 | `scripts/results/bit_search/`의 원시 결과 3건을 만든 스크립트. 운영 DB가 `voyage-4-large`만 가져 모델 이름·차원을 바꾸지 않으면 지금은 돌지 않음(아래 한계). 호출처는 `tests/evals/test_bit_search.py`·문서 | `embed`(질문 벡터 50개) → `setup`(`exp_bq` 만들기) → `measure`(정확 검색과 비트 N=400·800·1,600·3,200 시간·recall) → `warm`(비트 검색만 이어서) → `final`(v1 관련 19문항 최종 점수 확인) → `report` → `drop`. 입출력 폴더는 `BIT_SEARCH_WORK`(기본 `../전자_데이터시트/evidence/bq_exp`) |

## 한계

- 이 스크립트는 `text-embedding-3-small` `halfvec(1536)` 운영 DB를 가정한다. 운영 DB는 이후 `voyage-4-large`만 가지므로 모델 이름과 차원을 바꿔야 다시 잴 수 있다.
- `setup`은 운영 DB에 실험 표를 만들므로 `drop`까지 하루 안에 끝내야 한다(DB 크기 한도 500MB).
