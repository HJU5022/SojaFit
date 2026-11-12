# 원본 코퍼스 유지와 halfvec 저장 검증

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(저장 형식 전환 도구의 계약과 수동 재현 절차). 결정의 정본은 [ADR 0005](../adr/0005-supabase-한-프로젝트와-halfvec-코퍼스.md)
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [data/DATA.md](../../data/DATA.md)(청크 수 정본), 사전 등록 #9, #10 [preregister.md](../../evals/guides/preregister.md)

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 코퍼스를 줄이지 않고 HNSW 제거와 halfvec 저장으로 용량을 줄일 수 있는가 | ADR 0005 |
| 결정 | 코퍼스 축소는 보류, 전체 원본 유지. 코퍼스 벡터는 `halfvec`, HNSW 없음 | ADR 0005, [SPEC.md](../../SPEC.md) 6절 |
| 코퍼스 합계(로컬 실측, 1,360문서·52,244청크, v1 청킹 기준) | 829.5MiB → HNSW 제거 466.7MiB → halfvec 258.0MiB → 같은 본문 벡터 한 번만 237.8MiB | ADR 0005 "결정" 절 |
| 이 저장소에서 재현한 값 | 합성 64행 계약 시험의 평균 열 크기 6148 → 3076바이트. 전체 코퍼스 값은 재현하지 못함 | `scripts/results/storage/storage_contract_2026-11-02.json` |
| 사전 등록 | #9 최초 기대 보존, #10 축소 실험은 적용 보류 | `preregister.md:75`, `:89` |

## 2. 가설과 범위

- 가설: HNSW를 지우고 `halfvec`으로 저장하면 정확 검색 순위가 유지되면서 용량이 준다.
- 최초 목표는 전체 DB 250,000,000바이트와 5분류 축소였다. 이 값은 최초 진단 기준으로만 남기고, 코퍼스를 버리지 않는다. ADR 0005의 400MB 분리 검토 기준과 별개다.
- 범위 밖: 운영·원격 DB 변경, 원본 삭제, 코퍼스 축소 적용, 동일 본문 벡터 중복 제거 스키마, API 재생성, 동결 전 공식 평가.

## 3. 조건과 구현

| 항목 | 규칙 | 근거 |
|---|---|---|
| 축소 도구 | `backend/rag/pipeline/subset.py`는 수동 CLI로만 쓴다. 서비스·초기화·적재에서 호출하지 않는다. `--manifest --catalog --chunks --dataset --out-dir NEW_DIR`를 명시해야 실행되고 입력 덮어쓰기, 관련 gold 누락, 불완전 청크를 거부한다 | `tests/rag/test_rag_subset.py` |
| 저장 형식 | `RAG_VECTOR_TYPE`(`vector` 또는 `halfvec`, 기본 vector)이 이진 COPY 저장 형식을 고른다. float32 캐시는 보존하고 halfvec COPY에서만 변환한다. 검색은 `embedding::vector(1536) <=> 질문::vector(1536)`, 질문은 float32 유지 | `backend/rag/storage.py:25`, `tests/rag/test_rag_storage.py` |
| 수동 SQL | `db/manual/halfvec.sql.manual`이 HNSW를 지우고 열만 전환한다. 행·키를 보존하고 인덱스를 재생성하지 않는다. 반복 실행해도 같다. 이름 확장자 `.manual`이라 DB 초기화에서 자동 실행되지 않는다 | 파일 머리 주석 |
| 적재 | `ingest --cache-only`는 캐시가 없으면 API 호출 전에 실패한다. HNSW가 있을 때만 재색인한다 | `backend/rag/pipeline/ingest.py:214`, `:221` |
| 진단 | `python -m backend.rag.storage inspect`는 DB 전체·표 본문/TOAST·인덱스·확장 버전·열 형식을 보고한다. `compare --samples 1000 --max-seconds 120`은 vector 원본과 halfvec으로 반올림한 값의 top-5 겹침을 seed 42 표본(자기 자신·동일 본문 제외, chunk_id 동점 정렬)으로 비교한다. 표본·후보 부족과 timeout을 숨기지 않는다. API 호출 없음 | `backend/rag/storage.py:62` |
| 현재 서비스 | 새 DB는 `db/008_multi_dim_embeddings.sql`로 차원 없는 `halfvec`을 쓰고 검색 때 1024차원 vector로 변환해 정확 거리를 계산한다 | [SPEC.md](../../SPEC.md) 6절 |

## 4. 결과

| 측정 | 값 | 근거 |
|---|---|---|
| halfvec 변환 시 값 동일성 | `embedding::halfvec::vector = embedding`이 52,244/52,244 | ADR 0005 |
| 청크 1,000개를 질의로 쓴 정확 검색 top-5 | 집합 100% 일치, 순서 999/1000 일치(다른 1건은 거리 차 6.6e-8) | ADR 0005 |
| 정확 검색 시간(로컬 Docker, 질의 30개 중앙값) | float32 230.5ms, halfvec 140.2ms, 본문 중복 제거 119.6ms | ADR 0005 |
| HNSW | 한국어 질문에서 가까운 청크를 놓침(11-01). 11-02에 halfvec HNSW는 질의 30개 중 4개에서 정확 검색 top-5를 놓침 | ADR 0005 |
| 합성 계약 시험 | 64행, 1536차원, seed 42, 임베딩 API 0회, 평균 열 크기 6148 → 3076바이트, `full_corpus_reduced` false | `storage_contract_2026-11-02.json` |

## 5. 수동 재현 순서

전용 복제 DB의 `DATABASE_URL`이 환경변수로 있을 때만 실행한다. 접속 문자열은 출력하지 않는다. 시작 전 전체 원본의 DB 덤프 또는 청크와 float32 캐시, 표본 ID를 확보한다.

1. 전체 원본의 inspect와 파일·행 수·해시를 기록한다. 축소 출력은 입력으로 쓰지 않는다.
2. 별도 복제본에서 `DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw`만 실행해 HNSW 제거 용량과 정확 검색 기준선을 기록한다.
3. `uv run python -m backend.rag.storage compare --samples 1000 --max-seconds 120`을 실행한다. 조건이 다르면 별도 비교라고 표시한다.
4. 별도 복제본에 `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/manual/halfvec.sql.manual`을 적용한다. 열 형식·행 수·키·HNSW 부재를 확인하고 `RAG_VECTOR_TYPE=halfvec`으로 적재·검색을 검증한다. float32 캐시와 DB 백업을 보관한다.
5. inspect로 전체 DB·코퍼스 표·인덱스 바이트를 다시 기록한다.

## 6. 수용 기준

| 조건 | 기대 |
|---|---|
| 기본 서비스·초기화·적재 실행 | subset을 호출하지 않고 원본 코퍼스 유지 |
| 명시적 subset CLI | 새 사본만 만들고 gold 누락, 입력 덮어쓰기, 불완전 청크를 거부 |
| halfvec SQL 반복 | 행·키 보존, HNSW 없음, halfvec 열 |
| HNSW 없는 halfvec DB와 float32 캐시에 cache-only 적재 | API 없이 성공, HNSW 미생성 |
| halfvec 반올림 시 동점인 질문 벡터 | float32 질문 정밀도로 순서 결정 |
| compare의 timeout 또는 표본·후보 부족 | 100% 성공으로 보고하지 않음 |
| 합성 DB 시험 보고 | 실제 코퍼스의 용량·Recall·MRR을 확인했다고 쓰지 않음 |

## 7. 한계

- 237.8MiB(동일 본문 벡터 한 번만)는 로컬 실측이며 이 저장소에서 재현하지 못했다. `halfvec.sql.manual`은 중복 제거를 하지 않으므로 이 값의 재현을 주장하지 않는다.
- 위 용량 값은 v1 청킹(52,244청크) 기준이다. 현재 청크 수는 [data/DATA.md](../../data/DATA.md)가 정본이고, 현재 청크 목록과 벡터는 저장소 밖 산출물이다.
- 실제 코퍼스의 Supabase 확장 버전, 전체 DB 용량, 검색 품질은 별도 확인이 필요하다. 합성 계약 시험은 이를 입증하지 않는다.
- Supabase 서버 시간은 측정하지 않았다.
