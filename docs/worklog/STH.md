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

## 2026-11-02 로그인 및 사용자 식별 1차 구현
- 한 일: 기존 로그인 시안을 FastAPI에 연결하고 PostgreSQL 사용자·서버 세션, scrypt 비밀번호 해시, 동일 출처 확인, 계정별 로그인 실패 제한을 추가했다. 사전 생성 계정은 대화형 명령으로 준비한다. Migration 1 초안의 users 중복 정의를 인증 SQL로 이동했다.
- 바꾼 파일: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `backend/web/WEB.md`, `db/03_auth.sql`, `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/ERD.md`, `db/table-definition.md`, `docs/specs/login-auth.md`, `docs/specs/SPECS.md`, `tests/test_auth.py`, `tests/TESTS.md`, `SPEC.md`, `.env.example`, `README.md`, 이 파일.
- 검증: 테스트 전용 PostgreSQL 컨테이너에 인증 SQL을 적용하고 `TEST_AUTH_DATABASE_URL`을 지정해 `.venv/Scripts/python.exe -m pytest -q`를 실행했다: 30 passed, 2 skipped. 두 계정의 로그인·세션·로그아웃·만료와 5회 실패 제한을 확인했다. 브라우저에서 테스트 계정 로그인과 로그아웃을 확인했다. `uv` 실행 파일은 현재 셸에서 찾지 못해 기존 프로젝트 가상환경의 Python을 사용했다.
- 미구현·미검증: 기존 DB·Supabase·Cloud Run에 스키마 적용 및 배포, 사용자별 회로·대화·기억·견적 접근 제어, 계정 생성 자동화·비밀번호 재설정, 대규모 악용 방어와 운영 보안 검토, 실제 평가 계정 준비, 평가셋 재측정. CI에서는 인증 통합 DB가 제공되지 않으면 해당 테스트를 건너뛴다.
- 다음 할 일: 팀과 기존 DB 마이그레이션 이력·실행 순서를 확정하고, AUTH_ORIGIN과 쿠키·자원 한도를 배포 환경에서 검증하며, 각 기능 구현 시 사용자 소유권 검사를 연결한다.

## 2026-11-02 최신 main 반영 및 로그인 작업 복원
- 한 일: 미커밋 로그인 변경을 untracked 파일까지 stash에 보관하고 `main`을 `git pull --ff-only`로 갱신했다. `STH`에 최신 main을 fast-forward한 뒤 보관한 변경을 다시 적용했다. `SPEC.md`와 `tests/TESTS.md`는 자동 병합됐으며 미해결 충돌은 없다. 보관본은 유지했다.
- 확인: 새 로그인 파일 4개의 Git 해시가 보관본과 일치하고 `git diff --check`에 오류가 없다. 격리 인증 DB를 사용해 `.venv/Scripts/python.exe -m pytest -q`를 다시 실행한 결과 31 passed, 2 skipped. 테스트 DB 컨테이너는 정지했다.
- 남은 일: 기존 DB 마이그레이션, 실제 사용자별 업무 데이터 접근 제어, 배포 보안 확인 및 평가셋 재측정은 수행하지 않았다.

## 2026-11-02 DB 폴더 안내 중복 정리
- 한 일: `db/DB.md`에서 중복된 Migration 1 목록과 존재하지 않는 `01_init.sql` 항목을 제거하고 현재 SQL 파일 및 실행 순서와 대조했다. 기존 볼륨에 초기화 SQL이 자동 재실행되지 않는 점과 볼륨 삭제 시 데이터가 사라지는 점을 명시했다.
- 확인: `db/` 파일 목록 및 SQL 초안의 선행 조건과 문서를 대조했다. DB 실행이나 볼륨 삭제는 하지 않았다.

## 2026-11-02 DB SQL 파일 번호 정리
- 한 일: 실행 순서에 맞춰 `02_rag_corpus.sql` → `002_rag_corpus.sql`, `03_auth.sql` → `003_auth.sql`, 업무 초안 `001_create_business_tables.sql.draft` → `004_create_business_tables.sql.draft`로 이름을 정리했다. 관련 코드·테스트·문서 경로를 갱신하고 `001`은 비워 뒀다. 코퍼스·임베딩 SQL은 삭제하지 않았다.
- 확인: Git 이력에서 별도의 `db/002*` SQL 삭제 기록은 찾지 못했다. 기존 두 자리 `02_rag_corpus.sql`이 코퍼스 및 임베딩을 생성한다. 각 SQL의 실행문은 변경 전과 같고 주석·파일명만 바뀌었다.
- 검증: 테스트 컨테이너의 별도 빈 DB에서 `000` → `002` → `003` → `004` 초안을 순서대로 수동 적용해 테이블 17개를 확인했다. 별도 DB에 `TEST_DATABASE_URL`, `TEST_AUTH_DATABASE_URL`을 지정하고 `.venv/Scripts/python.exe -m pytest -q` 실행: 32 passed, 1 skipped. 적재 테스트는 테스트 전용 DB에서 임시 스키마를 만들고 삭제했다.
- 확인 못 한 것: 실제 Compose 신규 볼륨 자동 초기화, 기존 팀원 DB·Supabase의 파일명 기반 이력과 데이터, 평가셋 재측정. 파일명 변경이 기존 마이그레이션 도구의 이력에 미치는 영향은 도구와 환경 확정 후 확인한다.
