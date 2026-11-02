# STH 작업 기록

## 2026-10-30 Migration 1 SQL 초안
- 한 일: 최신 `db/table-definition.md`의 5.1~5.14를 기준으로 업무 테이블 14개, 기본키·CHECK·외래키·UNIQUE 및 정의서의 해시 인덱스를 담은 초안을 작성했다. 벡터 임베딩 Migration 2는 차원과 확장 스키마가 결정되지 않아 제외했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: 로컬 `STH`를 `main`까지 fast-forward했다(원격 변경 없음). 이력 결과 `STH`는 `origin/STH`보다 9개 커밋 앞섰다. SQL은 아직 DB에 적용하지 않았다.
- 확인 못 한 것: `db/ERD.md` 승인, migration runner 및 이력 테이블 선택, Supabase/Compose 양쪽 실행, IDENTITY 방식, `updated_at` 갱신 주체, 일부 가정 제약조건.
- 다음 할 일: 초안과 위 결정 항목을 검토·확정한 뒤 선택한 runner에 맞는 migration 경로로 옮겨 빈 로컬 DB 및 개발 DB에서 검증한다.

## 2026-10-30 Langfuse Cloud 연결 확인
- 한 일: `STH` 브랜치에서 Langfuse SDK v5 환경변수 호환과 자격증명 확인 함수를 추가했다. 자동 프롬프트·응답 계측은 보류했다.
- 바꾼 파일: `backend/services/llm.py`, `.env.example`, `backend/services/SERVICES.md`, `SPEC.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: `.env` 자격증명 값을 출력하지 않고 Cloud `GET /api/public/projects`를 호출해 인증 성공과 프로젝트 1개를 확인했다.
- 확인 못 한 것: Python SDK 함수 실행과 모델 trace는 검증하지 않았다. 현재 `.env`에 `OPENROUTER_API_KEY`가 없고, 이 셸에서 `uv`와 프로젝트 `.venv`를 찾지 못했다.
- 다음 할 일: 프롬프트·응답을 Cloud에 저장할지 결정되면 실제 LLM 계측을 추가한다.

## 2026-10-30 Migration 초기화 SQL 순서 정렬
- 한 일: Docker Compose 초기화 SQL에서 pgvector 확장이 업무 스키마보다 먼저 실행되도록 세 자리 파일명 규칙을 적용했다.
- 바꾼 파일: `db/01_init.sql`을 `db/000_init.sql`로 이동하고 `db/DB.md`, `docs/worklog/STH.md`를 갱신했다.
- 실행한 명령과 결과: 파일명 정렬과 Git diff를 확인했다. 실제 DB 초기화는 실행하지 않았다.
- 확인 못 한 것: 빈 DB에서 Compose 초기화, Supabase 적용, Migration 1/2 실행 이력은 검증하지 않았다.
- 다음 할 일: 피드백 2번의 `thread_id` 생성 규칙을 확정한 뒤 초안에 반영한다.

## 2026-11-02 Migration 1 코퍼스 정의 중복 정리
- 한 일: Migration 1 초안에서 PR #17 코퍼스 SQL과 중복된 문서·청크 표 및 청크 해시 인덱스 생성 정의를 제거하고 선행 조건을 기록했다. 기존 외래 키는 유지했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/table-definition.md`, 이 파일.
- 실행과 결과: 격리된 Compose PostgreSQL에서 pgvector 확장, PR #17 코퍼스 SQL, 수정된 초안을 순서대로 적용했다. 전체 15개 표와 문서·청크 참조 외래 키 6개를 확인했다. 원본 초안은 같은 조건에서 `source_documents` 중복으로 실패했고 트랜잭션이 롤백됐다. 검증 중 중지된 테스트 컨테이너를 재시작하고 동일 검증을 다시 수행했다.
- 확인 못 한 것: 실제 코퍼스 데이터가 있는 DB, Supabase, 마이그레이션 이력 도구와 자동 초기화 순서. PR #17은 현재 STH에 아직 반영되지 않았다.
- 다음 할 일: 팀의 최신 변경을 반영하고 ERD 및 SQL 실행 순서·이력 방식을 확정한 뒤 데이터가 있는 환경을 검증한다.
