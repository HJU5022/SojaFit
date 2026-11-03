# 원본 코퍼스 유지와 halfvec 저장 검증

## Why

- 최초 목표는 전체 DB 250,000,000바이트와 5분류 축소였으나, 2026-11-02 조장 결정(ADR 0005: 용량 때문에 코퍼스를 줄이지 않는다)에 따라 PR #23의 전체 코퍼스 유지 방향에 맞춘다. 축소는 보류한다.
- PR #23은 HNSW 제거 → halfvec → 동일 본문 벡터 중복 제거 후 코퍼스 237.8MiB를 보고한다(조장 로컬 실측, ADR 0005). 이 작업서를 쓸 때는 원본 DB가 없어 재현하지 못했고, Supabase 측정값도 아니다. 동일 본문 벡터 중복 제거는 구현하지 않았다.
- 현재 저장소에는 1,360문서·52,244카드 목록만 있고 전체 카드·벡터 캐시·적재 DB는 없다. 합성 시험으로 실제 검색 품질과 용량을 입증하지 않는다.

## Goal

- 원본 13분류·1,360문서와 평가 회로 5종을 유지한다. 서비스·초기화·적재에서 축소 도구를 호출하지 않는다.
- 선택 전환 경로는 halfvec(1536) 저장, float32 거리 계산, HNSW 없음이다. 모델·차원은 임시 ADR 0004를 따르고, 실제 품질 검증 전 기본 설정은 vector다.
- 원본 DB의 복제본에서 한 번에 하나씩 HNSW 제거와 저장 정밀도 변경을 비교한다. 동결 뒤 같은 코퍼스의 Recall@5·MRR 무하락을 최종 품질 게이트로 둔다.
- Out of Scope: 운영·원격 DB 변경, 원본 삭제, 코퍼스 축소 적용, 중복 벡터 스키마 설계, API 재생성, 동결 전 공식 평가. 250MB는 최초 검토 목표로만 보존하며 이를 위해 문서를 버리지 않는다.

## What

- `subset.py`는 수동 CLI로 남긴다. 조 결정 전에는 축소 사본 생성·적재를 진행하지 않는다. 원본 보존·관련 gold 누락·불완전 카드 거부 계약은 유지한다.
- 수동 halfvec SQL은 HNSW를 제거하고 열만 전환한다. 행·키를 보존하고 인덱스를 재생성하지 않는다. ingest는 HNSW 없는 DB에서도 동작한다.
- 읽을 때 저장된 halfvec을 vector로 변환하고 질문은 float32를 유지한다. 이미 반올림된 저장값이 원본으로 복구된다는 뜻은 아니다.
- 전체 원본이 없으면 도구·SQL·실제 PostgreSQL 계약 시험까지만 검증하고 전체 용량·1,000개 순위·공식 품질은 미확인으로 남긴다.

## How

- `backend/rag/pipeline/subset.py`: 독립 수동 CLI. `--manifest PATH --catalog CSV --chunks PATH --dataset PATH --out-dir NEW_DIR`를 명시해야 실행된다. catalog의 정확한 PDF 이름·5분류 집합으로만 선택하며 입력 덮어쓰기를 금지한다. 기본 실행 경로에는 연결하지 않는다.
- `RAG_VECTOR_TYPE=vector|halfvec`(기본 vector)은 이진 COPY 저장 형식을 고른다. float32 캐시는 보존하며 halfvec COPY에서만 변환한다. halfvec 검색은 `embedding::vector(1536) <=> 질문::vector(1536)`이다.
- `ingest --cache-only`는 캐시가 없으면 API 호출 전에 실패한다. 기존 DB에 ingest를 반복해도 코퍼스가 삭제·축소되지 않는다. 기존 HNSW가 있을 때만 재색인한다.
- `storage inspect`는 DB 전체·표 본문/TOAST·인덱스·확장 버전·열 형식을 보고한다. JSON의 250MB 목표는 최초 진단 기준이며 ADR 0005의 400MB 분리 검토 기준과 별개다.
- `storage compare --samples 1000 --max-seconds 120`는 원본 vector 표에서 저장값만 halfvec으로 반올림한 뒤 float32로 읽는 거리를 비교한다. 모델·코퍼스·질문은 고정한다. seed 42 표본, 자기 자신·동일 본문 제외, chunk_id 동점 정렬, 정확 검색이다. 표본·후보 부족과 timeout을 숨기지 않는다. API 호출은 없다.
- 사전 등록 #9의 최초 기대는 보존하고 아래 새 거리 계산 조건을 추가 기록한다. #10 축소 실험은 보류한다. 이미 보고된 조원 결과를 사전 기대처럼 소급해서 적지 않는다.

### 원본을 확보한 뒤의 수동 재현 순서

변환 전 DB 덤프 또는 전체 카드와 원본 float32 캐시, 실험 SQL·표본 ID·동점/중복 처리 조건을 먼저 확보한다. 저장소 초기화 SQL은 여전히 vector와 HNSW를 만들므로 이후 명시적 전환이 필요하다. 아래 명령은 원본을 보존한 전용 복제 DB의 DATABASE_URL이 환경변수로 설정됐을 때만 실행한다. 접속 문자열은 출력하지 않는다.

1. 전체 원본의 inspect와 파일·행 수·해시를 기록한다. 축소 출력은 입력으로 쓰지 않는다.
2. 별도 복제본에서 `DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw`만 실행해 HNSW 제거 용량과 정확 검색 기준선을 기록한다.
3. 그 기준선에서 `uv run python -m backend.rag.storage compare --samples 1000 --max-seconds 120`을 실행한다. 실제 조건과 제한 시간이 원본 보고와 다르면 별도 비교라고 표시한다.
4. 별도 복제본에 `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/manual/halfvec.sql.manual`을 직접 적용한다. 열 형식·행 수·키·HNSW 부재를 확인하고 RAG_VECTOR_TYPE=halfvec으로 적재·검색을 검증한다. 원본 float32 캐시/DB 백업은 보관한다.
5. inspect로 전체 DB·코퍼스 표·인덱스 바이트를 다시 기록한다. 동일 본문 벡터 중복 제거는 `db/manual/halfvec.sql.manual`이 하지 않으므로 237.8MiB 재현을 주장하지 않는다.

### 확인 경계

- 기존 `scripts/results/storage/storage_contract_2026-11-02.json`은 이전 HNSW 재생성·halfvec 거리 경로의 합성 64행 기록이다. 평균 열 크기 6148→3076바이트이며 현재 경로의 재현 증거로 재사용하지 않는다.
- 현재 경로는 전용 PostgreSQL 계약 시험으로 확인한다. 실제 코퍼스·Supabase 확장 버전·전체 DB 용량·검색 품질은 별도 확인이 필요하다.

## AC

- Given 기본 서비스·초기화·적재, When 실행, Then subset을 호출하지 않고 원본 코퍼스가 유지된다.
- Given 명시적 subset CLI, When 실행, Then 새 사본만 만들며 관련 gold 누락·입력 덮어쓰기·불완전 카드를 거부한다.
- Given vector 시험 DB, When halfvec SQL 반복 실행, Then 행·키를 보존하고 HNSW가 없으며 halfvec 열로 전환된다.
- Given HNSW 없는 halfvec DB와 float32 캐시, When cache-only 적재, Then API 없이 성공하고 HNSW를 만들지 않는다.
- Given halfvec 반올림 시 동점이 되는 질문 벡터, When dense 검색, Then float32 질문 정밀도를 유지한 거리로 순서를 정한다.
- Given 원본 비교, When timeout 또는 표본/후보 부족, Then 불완전 결과를 100% 성공으로 보고하지 않는다.
- Given 합성 DB 시험, When 보고, Then 실제 52,244카드의 용량·Recall·MRR을 확인했다고 주장하지 않는다.
