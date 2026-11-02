# 코퍼스 범위와 halfvec 저장 용량 검증

## Why

- SojaFit 운영 담당자가 전체 DB를 250,000,000바이트 이하로 줄이려 한다. 다른 조원이 보고한 837MB(벡터 표 786MB, HNSW 363MB)는 이 환경에서 재측정한 값이 아니다.
- 현재 저장소에는 문서 1,360건·카드 52,244개 목록만 있고 전체 카드·벡터 캐시·적재 DB는 없다. 전체 검색 품질이나 실제 축소 용량을 합성 데이터 시험으로 대신 입증하지 않는다.
- 측정은 DB 전체, 표 본문·TOAST·인덱스, 문서·카드·서로 다른 본문 수, vector/halfvec의 top-5 겹침으로 나눈다.

## Goal

- 사용자가 선택한 우선 목표는 전체 DB(인덱스 포함) 250MB 이하이다. 카드 5만 개는 별도 필수 상한으로 두지 않는다.
- 평가에 쓰는 회로 5종을 모두 유지하고, 그 다이오드 종류에 해당하는 문서만 별도 축소 사본으로 만든다.
- halfvec 저장·적재·검색 전환을 지원하고 로컬 실제 PostgreSQL에서 검증한다. 도입의 최종 품질 게이트는 동결 평가셋으로 vector 대비 Recall@5·MRR 하락 없음이다.
- Out of Scope: 원격 DB 변경, 원본 코퍼스 삭제, 평가 문항 재작성(요청 4번), 원격 게시(요청 5번), API 임베딩 재생성, 동결 전 공식 평가 실행.

## What

- 현재 완료된 사람 리뷰는 코퍼스 버전과 함께 '변경 보류'로 기록하고 n01·n02·h03 및 n21·n22는 별도 대기한다. 숫자형 7건의 기계 대조와 사람 판정 기록은 구분한다. FROZEN.json은 만들지 않는다.
- 축소 후보 분류는 Schottky Rectifier(1N5817~19·SS34), Schottky Diode(BAS70), Switching Diode(1N4148), Zener Diode(BZT52·BZX84), Standard Rectifier(기존 회로 1N400x)를 포함한다. 실제 제조사 분류 목록 csv로만 선택하고 파일명 접두사로 분류를 추측하지 않는다.
- 관련 정답 PDF를 선택 범위가 누락하면 축소를 실패 처리한다. 수량·용량이 작아져도 정답 근거가 사라진 것을 성공으로 보고하지 않는다. 문서 50건·서로 다른 본문 1만 개의 G3도 실제 카드에서 별도 확인한다.
- 원본 manifest·카드는 보존하고 새 출력 폴더에 선택 manifest·카드·용량 추정·평가 영향 보고서를 쓴다. 용량 추정은 실제 PostgreSQL 크기와 구분한다.
- halfvec은 숫자 저장 정밀도만 바꾼다. 모델·차원(1536)·코퍼스·질문·BM25·거리·검색 후보 수는 고정한다. 인덱스 제거는 별도 실험이다.
- 전체 DB가 없으면 도구·전환 SQL·재현 명령과 실제 DB 계약 시험까지만 검증하고 전체 목표 달성은 미확인으로 남긴다.

## How

- `backend/rag/subset.py`: `python -m backend.rag.subset --manifest PATH --catalog CSV --chunks PATH --dataset PATH --out-dir NEW_DIR`. 분류 목록은 모듈의 고정 후보 집합, catalog의 `file`, `categories`(; 구분)로 대조. 정확한 PDF 이름으로 manifest·카드를 연결한다. 출력 경로는 새 폴더만 허용하며 입력 덮어쓰기는 금지한다. 필수 입력·분류·카드가 없거나 관련 gold가 누락되면 실패한다.
- `backend/rag/storage.py`: DATABASE_URL은 읽기 전용 점검에만 사용. `inspect`는 확장 버전·embedding 형식·DB 전체/표별 크기를 JSON으로 출력한다. `compare --samples 1000 --max-seconds 120`는 기존 vector 표에서 원본 거리와 halfvec 캐스트 거리를 비교한다. 한 번에 하나만 실행하고 시간 상한을 둔다. 외부 API 호출 없음.
- 비교는 카드 id 순서의 고정 seed 표본, 자기 자신과 동일 본문 해시를 제외하고 정확 검색만 쓴다. 같은 모델 행만 비교하며 동점은 chunk_id로 정렬한다. 표본 부족·후보 부족·timeout은 성공률 100%로 숨기지 않는다. 반정밀 저장 자체의 효과와 HNSW 근사 오차를 섞지 않는다.
- 새 서버 설정 `RAG_VECTOR_TYPE=vector|halfvec`(기본 vector)은 적재 이진 COPY 타입과 질의 캐스트를 함께 고른다. 캐시는 float32 원본을 유지하고 halfvec COPY 때만 변환한다. 잘못된 설정은 오류로 처리한다.
- 축소 사본은 빈 별도 DB에 적재한다. 기존 전체 DB에 ingest를 재실행해도 행을 지우지 않으므로 축소가 되지 않는다. float32 캐시도 복사본을 쓰고 `ingest --cache-only`로 API 호출을 금지한다. 필요한 캐시가 없으면 오류로 멈춘다.
- `db/halfvec.sql.manual`: 자동 초기화 대상이 아닌 명시적 실행 SQL. pgvector halfvec 지원·기존 1536차원 표를 확인하고, 한 트랜잭션에서 HNSW를 제거한 뒤 열 변환 및 halfvec_cosine_ops 인덱스 재생성. 중복 실행은 안전하고 데이터 행·키는 유지한다. 원본 float32 캐시/DB 백업을 확보한 별도 복제 DB에만 먼저 적용한다. 역변환은 원본 정밀도를 복구하지 못한다.
- 인덱스가 실제로 사용되지 않는 현 정확 검색의 기본 동작은 유지한다. HNSW 제거 시 용량 이득은 precision 전환과 별개로 보고한다.
- 작업 순서: 검수 확정 표시 → 분류 선택 도구·시험 → halfvec 전환·적재·검색 시험 → 실제 DB 크기 보고·API 없는 비교 도구 → 문서·작업 기록·독립 검토. 기존 jaehun에서 범위만 수정하며 푸시·브랜치 추가·원본 삭제는 하지 않는다.

### 실제 원본을 확보한 뒤 실행

현재 이 환경에는 전체 catalog·카드·벡터가 없다. 아래 경로는 원본 보유자가 전달한 파일 경로로 바꾼다. 출력은 새 폴더이며 입력 PDF·manifest·카드·float32 캐시는 보존한다.

```bash
uv run python -m backend.rag.subset --manifest data/manifest.jsonl --catalog /path/tsc_datasheet_list.csv --chunks /path/chunks.jsonl --dataset evals/draft_50.jsonl --out-dir /path/tsc-subset-new
```

DATABASE_URL이 별도 복제 DB의 환경변수로 설정된 상태에서만 다음을 실행한다. 접속 문자열이나 비밀값은 결과 파일·채팅에 남기지 않는다.

축소 후보용 DB는 `db/000_init.sql`·`02_rag_corpus.sql`로 만든 빈 DB여야 한다. 여기에 `uv run python -m backend.rag.ingest /path/tsc-subset-new/manifest.jsonl /path/tsc-subset-new/chunks.jsonl /path/vector-cache-copy --cache-only`로 먼저 vector 기준선을 적재한다. 이미 전체 행이 있는 DB에 이 명령을 실행해 축소됐다고 보고하지 않는다. 정밀도 전환은 그 기준선 DB의 별도 복제본에서 진행한다.

```bash
uv run python -m backend.rag.storage inspect > /tmp/storage-vector-before.json
uv run python -m backend.rag.storage compare --samples 1000 --max-seconds 120 > /tmp/storage-precision-compare.json
```

원본 float32 보관과 비교 결과 확인 후 복제 DB에 `psql -f db/halfvec.sql.manual`을 명시적으로 적용하고 `RAG_VECTOR_TYPE=halfvec`로 적재·검색을 시험한다. init SQL은 여전히 vector를 만든다. 전환 후 inspect로 전체 DB·표·인덱스 크기를 다시 재며, 250MB 여부는 이 값으로 판단한다. 현재 정확 검색이 쓰지 않는 HNSW를 없애는 경우는 별도 복제 DB 조건으로 재고 정밀도 전환 효과와 합산해 보고하지 않는다.

### 현재 확인 범위

- 전용 로컬 PostgreSQL의 pgvector 0.8.6에서 수동 SQL·반복 실행·halfvec COPY·질의·설정 일치·API 없는 재적재를 확인했다. 대상 Supabase 확장 버전은 아직 확인하지 못했다.
- 합성 64행(1536차원)의 평균 pg_column_size는 6148→3076바이트였다. 이는 실제 전체 DB 용량이나 검색 품질의 개선 점수가 아니다. 16개 합성 질의는 실제 벡터 1,000개 사전 등록 게이트를 충족하지 않는다.
- 원시 확인 기록: `evals/results/storage_contract_2026-11-02.json`. 실제 축소·공식 품질·250MB 달성은 미확인이다.

## AC

- Given 52건 검토표, When 완료 표시, Then 명시적 사람 O 기록과 기계 대조만 있는 문항을 구분하고 보류 5건의 합의를 꾸미지 않는다.
- Given 분류 csv·manifest·cards, When subset 실행, Then 허용 분류의 문서만 새 폴더에 남고 입력 바이트는 유지되며 관련 gold 누락은 오류다.
- Given 잘못된 분류/기존 출력/불완전 카드, When 실행, Then 일부 결과를 성공이라고 출력하지 않고 오류로 끝난다.
- Given vector(1536) 시험 DB와 기존 캐시, When halfvec SQL·설정 후 적재·검색, Then 열·인덱스·이진 COPY·질의 타입이 일치하고 API 호출 없이 재실행 가능하다.
- Given 반정밀 전환 DB, When 다시 SQL 실행, Then 행 수·키가 보존되며 재실행이 실패하지 않는다.
- Given 합성 DB 계약 시험, When 보고, Then 실제 52,244개 코퍼스의 용량·Recall·MRR을 검증했다고 주장하지 않는다.
- Given 실제 원본 vector DB, When API 없는 비교, Then 같은 원본 표본·같은 corpus에서만 비교하고 표본·후보·제외·실패 수와 설정·크기를 남긴다.
