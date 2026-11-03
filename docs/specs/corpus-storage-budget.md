# 원본 코퍼스 유지와 halfvec 저장 검증

## Why

전체 코퍼스를 유지하면서 저장 정밀도가 검색 결과와 DB 용량에 미치는 영향을 확인한다. PR #23의 237.8MiB는 별도 환경의 보고이며 이번 로컬 재구축과 구분한다.

## Goal

- 원본 13분류·1,360문서와 평가 회로 5종을 유지한다. 축소 도구는 적용하지 않는다.
- 같은 모델·코퍼스·질문에서 카드1,000개의 top-5를 비교하고 동결 질문 Recall@5·MRR 무하락을 확인한다. 최초 기대와 시간 상한 변경은 `evals/PREREGISTER.md`에 보존한다.
- Out of Scope: 운영 DB·서비스 전환, 원본 삭제, 코퍼스 축소, 벡터 중복 제거 스키마. 250MB 달성 여부는 실측으로 보고한다.

## What

- halfvec(1536)로 저장하고 읽을 때 vector(1536)로 변환해 float32 질문과 정확 코사인 거리를 계산한다. 양쪽 HNSW는 없다.
- 2026-11-02 재구축본은52,933카드다. 검증된 두 문서 외 품번 표지는 제외했으므로 원래52,244카드나 운영 품번 필터 검증과 같지 않다.
- 팀 재현은 고정 카드·float32 캐시·질문 캐시를 사용한다. 추가 API를 호출하지 않고, 필요한 캐시가 없거나 해시가 다르면 실패한다.

## How

- 기존 `backend.rag.ingest`의 cache-only 적재, `storage.compare`, `evals.run_retrieval`을 사용한다. 재현 실행기는 `evals/reproduce_halfvec.py`다.
- 모델: `openai/text-embedding-3-small`,1536차원. 동결 `dataset_v1.jsonl`의 전체 input을 질의로 사용한다. PDF 근거19건, 회로 전용6건 제외이며 답변·거절은 채점하지 않는다.
- 같은 질문 벡터를 양쪽에 재사용한다. 카드 비교는 seed42·자기/동일본문 제외·k5·동점chunk_id, 상한600초(#13)다. 최초120초 timeout 기록은 결과에 남긴다.
- 원본 캐시·카드와 동결셋을 보존한다. 재현 DB는 별도 localhost PostgreSQL이며 연결 설정은 공유하지 않는다. DB 초기화는 기존 `db/002_rag_corpus.sql`, 전환은 `db/manual/halfvec.sql.manual`을 따른다.
- 이번 비교 결과와 남은 한계는 [EVAL_REPORT](../../EVAL_REPORT.md#1-4-전체-pdf-재구축의-halfvec-비교-2026-11-02)를 본다. 같은 값을 여기 반복하지 않는다.

### 재현

고정 입력은 저장소 밖 `halfvec-inputs-20261102.tar.gz`로 별도 전달한다. 별도 전달 파일이며 다운로드 URL은 아직 등록하지 않았다. 번들 SHA256·파일별 해시·크기는 [입력 목록](../../evals/results/halfvec_inputs_2026-11-02.json)에 기록한다. PDF·모델 캐시·접속 설정은 번들에 넣지 않는다.

1. 번들을 새 작업 디렉토리에 풀고 의존성을 `uv sync --locked`로 설치한다. 읽기 전용 검증부터 실행한다.

```bash
uv run python -m evals.reproduce_halfvec verify --inputs /path/to/inputs
```

2. 별도 로컬 DB 두 개를 준비한다. vector DB에는 vector 확장과 `db/002_rag_corpus.sql`을 적용하고 HNSW를 제거한다. 두 DB 설정 파일은 각각 `DATABASE_URL` 하나를 담은 로컬 파일이다. 빈 vector DB에 고정 캐시로 적재한다.

```bash
uv run python -m evals.reproduce_halfvec load --inputs /path/to/inputs --db-env /path/to/vector.env
```

3. 연결을 종료한 vector DB를 복제해 halfvec DB를 만들고 `db/manual/halfvec.sql.manual`을 그 복제본에 적용한다. 원본 DB에서 전환하지 않는다. SQL 실행 예시는 아래와 같다. `createdb` 접속 옵션은 해당 로컬 설정을 사용한다.

```bash
createdb --template=sojafit_vector sojafit_halfvec
uv run --env-file /path/to/halfvec.env python -c "import os, psycopg; from pathlib import Path; c=psycopg.connect(os.environ['DATABASE_URL'],autocommit=True); c.execute(Path('db/manual/halfvec.sql.manual').read_text()); c.close()"
```

4. 두 DB를 비교한다. 출력 디렉토리는 새 경로를 지정한다. 질문 임베딩은 번들에서 읽으며 API를 호출하지 않는다.

```bash
uv run python -m evals.reproduce_halfvec compare --inputs /path/to/inputs --vector-env /path/to/vector.env --halfvec-env /path/to/halfvec.env --out /path/to/new-results --max-seconds 600
```

본문·캐시·질문 해시는 고정되지만 PostgreSQL 물리 파일 크기와 실행 시간은 환경에 따라 달라질 수 있다. 동일 결과의 기준은 표본 완료 여부·행 수·검색 순위와 지표다.

## AC

- Given 기본 서비스·초기화·적재, When 실행, Then subset을 호출하지 않고 원본 코퍼스를 유지한다.
- Given 고정 입력 번들, When verify, Then 카드·캐시·동결 질문 해시를 대조하고 누락/손상은 실패한다.
- Given localhost 시험 DB와 캐시, When load, Then 원본 캐시를 바꾸거나 API를 호출하지 않고 적재한다.
- Given 필요한 질문 캐시 누락, When compare, Then 검색/API 호출 전에 실패한다.
- Given 같은 카드·질문 벡터의 vector/halfvec DB, When compare, Then 형식·행·HNSW 부재를 확인하고 같은 질문으로 Recall@5·MRR을 기록한다.
- Given timeout/표본부족, When 보고, Then 불완전 결과를 성공으로 보고하지 않는다.
