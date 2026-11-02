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

## 2026-11-02 인증·DB 적용·CI 1차 보강
- 한 일: 인증된 사용자 ID와 thread·Store·업무 데이터 소유권의 연결 계약 및 교차 접근 테스트 초안을 기록했다(팀 검토 필요). 실제 그래프·업무 API는 아직 없어 소유권 기능은 구현하지 않았다. 기존 DB의 인증 스키마를 읽기 전용으로 대조하는 절차를 추가했다.
- 한 일: PR CI에 격리 PostgreSQL과 인증 SQL 초기화를 추가했다. 로그인 실패 집계를 15분으로 한정하고 5회 실패 후 15분 잠금 정책을 유지했다. 기존 잠금 의미를 보존하기 위해 새 `005_auth_attempt_window.sql`로 집계 시작 컬럼을 추가했다.
- 검증: 실패 집계 시간이 없는 기존 코드에서 테스트 실패를 확인한 뒤 수정 후 통과했다. 격리 PostgreSQL 16에서 CI와 같은 인증 SQL 초기화 후 전체 테스트 33 passed, 2 skipped(코퍼스 DB 미설정). 기존 사용자·세션·활성 잠금이 있는 별도 모의 DB의 데이터 보존을 확인했다. DB 점검 SQL과 CI YAML 구조를 확인했다. GitHub Actions 실행은 아직 확인하지 않았다.
- 로컬 개발 DB: 대상 스키마와 제약을 격리 기준 DB와 읽기 전용 비교한 뒤 `005`만 트랜잭션으로 적용했다. 적용 전후 users 4건·sessions 1건·login attempts 0건이 유지됐고, 기존 로컬 테스트 계정 두 개로 변경된 코드의 로그인·식별·로그아웃을 확인했다. 공유 DB와 Cloud에는 적용하지 않았다.
- 남은 일: 실제 업무 데이터의 소유권 적용·교차 접근 테스트, 팀의 thread/Store ID 계약, 계정 잠금 악용·분산 요청·실패 기록 보존 대책, 실제 GitHub Actions 및 Cloud 배포 검증, 기존 DB 마이그레이션 이력 방식 확정, 평가셋 재측정. 과거 실패 기록 중 집계 시작 시간이 없는 비잠금 기록은 다음 실패부터 새 구간을 시작하며 활성 잠금은 유지된다.

## 2026-11-02 인증 리뷰 경계·동시 제한 검증 보강
- 한 일: 비활성 계정 및 비활성 사용자의 기존 세션 거부, 30분 유휴·8시간 절대 만료 경계 전후, 15분 잠금 중 차단과 잠금 종료 후 허용, 두 PostgreSQL advisory 슬롯 점유 시 503 테스트를 추가했다. HTTPS Secure 쿠키·교차 Origin 로그아웃·DB 오류 상세 미노출 테스트도 포함했다.
- 검증: 별도 CI 전용 PostgreSQL 16 (`sojafit-ci-auth-check`, 127.0.0.1:55434)에서 `TEST_AUTH_DATABASE_URL` 지정 후 `.venv/Scripts/python.exe -m pytest -q tests/test_auth.py`: 12 passed. 기존 로컬 개발 DB와 계정은 사용하지 않았다.
- 제한: 만료 경계는 DB 시각을 기준보다 5초 안팎 앞/뒤로 설정해 시험했으며 8시간을 실제 기다린 시험은 아니다. 두 advisory 잠금 점유 테스트는 초과 요청의 503 제한을 검증하지만, Cloud Run 프로세스의 실제 RSS나 scrypt 병렬 메모리는 측정하지 않았다.

## 2026-11-02 관리자·사용자 계정 권한
- 한 일: `006_user_roles.sql`로 기존 계정 기본 역할 `user`를 추가하고 신뢰된 명령줄에서 `admin` 생성 옵션을 제공했다. 관리자 전용 계정 조회·일반 계정 활성화 API와 로그인 화면을 추가했다. 일반 사용자의 관리자 API 접근과 관리자 계정의 상태 변경은 거부한다. 사용자 비활성화와 세션 삭제를 한 트랜잭션에서 처리하고 로그인과 비활성화가 사용자 행 잠금으로 경합하도록 했다.
- 변경: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `db/006_user_roles.sql`, CI 초기화, 인증 테스트, `SPEC.md`, 인증 작업서·DB 안내·ERD·README·테스트 안내.
- 검증: 새 역할 컬럼이 없는 상태에서 새 관리자 테스트가 실패하는 것을 확인한 후 구현했다. 격리 PostgreSQL에서 전체 테스트 39 passed, 2 skipped. 새로 만든 임시 테스트 DB에 003→005→006 적용 후 인증 테스트 13 passed, 임시 DB만 삭제했다. 기존 `.venv` Python을 사용했으며 `uv` 명령은 PATH에서 찾지 못했다.
- 로컬 개발 DB: 사전 상태 사용자 4명·세션 2건을 확인하고 006을 적용했으며 기존 계정은 `user`로 유지했다. 별도 로컬 관리자·사용자 테스트 계정 2개를 생성하고 HTTP로 관리자 조회 200·일반 사용자 거부 403·비활성 세션 거부 401·재활성화 후 이전 세션 거부 401을 확인했다. 기존 세션 두 건은 유지했다. 테스트 비밀번호는 저장소 밖 이 PC의 로컬 `.env`에만 보관했다.
- 미검증: 관리자 화면의 직접 브라우저 조작, 공유 DB·Cloud Run 마이그레이션과 배포, GitHub Actions, 업무 데이터 소유권과 전체 평가셋. 기존 DB에서는 앱 업데이트 전 006을 한 번만 적용해야 한다.

## 2026-11-02 최신 main 병합과 로그인 작업 복원
- 한 일: PR #22의 head가 기존 STH 커밋 `d981455`와 같음을 Git 참조로 확인했다. 미커밋 관리자 작업을 untracked 파일 포함 stash로 보관한 뒤 `origin/main`을 STH에 병합했다. `db/DB.md`와 `db/ERD.md`의 코퍼스 halfvec 안내와 인증 SQL 명명·역할 안내를 함께 보존했다.
- 후속 수정: main에서 들어온 RAG 저장소 테스트가 옛 `db/02_rag_corpus.sql` 경로를 사용하는 부분을 `db/002_rag_corpus.sql`로 맞추고, Windows SQL 파일 UTF-8 읽기 및 비밀번호가 생략되는 `db.info.dsn` 재연결을 수정했다.
- 검증: 테스트 전용 PostgreSQL 16과 별도 임시 pgvector DB를 사용했다. 첫 실행은 임시 DB의 확장 미설치 및 Windows 기본 인코딩, 두 번째 실행은 잠금 테스트의 비밀번호 없는 DSN으로 실패해 각각 원인을 수정했다. pgvector 확장 및 UTF-8 환경에서 동일 전체 검사 재실행: 73 passed, 1 skipped. 임시 DB는 삭제했다.
- 제한: GitHub 연결 도구는 PR #22에 404를 반환하고 gh CLI는 사용할 수 없어 PR 메타데이터는 확인하지 못했다. 원격 PR 상태·GitHub Actions·배포는 확인하지 않았으며 push하지 않았다. 기존 stash와 이번 보관 stash는 유지했다.

## 2026-11-02 인증 리뷰 실측 기록
- 한 일: STH `8dc9630` 기준으로 격리 PostgreSQL 16.15에서 두 계정의 로그인·세션 분리·로그아웃, 잠금·세션 만료 경계, 실제 scrypt 동시 실행과 프로세스 메모리를 측정하고 `docs/auth-login-verification.md`에 기록했다. `docs/DOCS.md`에 파일을 등록했다.
- 환경과 결과: Windows Python 3.12.10, FastAPI TestClient, 로컬 테스트 DB. 고정된 트랜잭션 시각에서 잠금 900초와 절대 만료 28,800초 및 경계 전·동일·후 상태가 기대와 같았다. 2개 scrypt 호출이 343.11ms 겹친 동안 세 번째 요청은 503이었다. Windows 프로세스 working set은 단일 요청 54.11→183.43MiB, 동시 2개 55.39→312.13MiB였다. 각 결과는 단일 실행이다.
- 실행: 프로젝트 `.venv/Scripts/python.exe`로 로컬 실측 스크립트 `auth_boundary_after_merge.py`, `measure_scrypt_concurrent.py`를 각각 격리 DB에 대해 실행했다. 실측 스크립트와 원시 JSON은 로컬 작업 폴더에만 보관했고 테스트 데이터는 롤백 또는 삭제했다.
- 제한: 메모리는 Windows Python 프로세스 표본이며 PostgreSQL·OS 메모리는 제외, Cloud Run·실제 경과 시간 대기·분산 인스턴스는 미검증. 반복 부하 및 GitHub Actions 결과도 별도 확인이 필요하다.
