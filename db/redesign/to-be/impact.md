# 영향 지도와 단계별 비용

- 숫자는 레포를 **정적으로 검색**한 값이다(`file:함수` 단위). 시간은 [추정]이고 일정은 정운이 정한다. 시험 수는 "고치거나 새로 쓰는 시험 함수"다.
- 단계의 뜻: **필수**(P1) = 효과 대비 비용이 가장 낮고 코드 변경이 작은 것, **권장**(P2 · M · D8 · 2b) = 효과가 있지만 시험이 많이 얽힌 것, **보류**(P3 · D10) = 동결 전에 하지 않는 것.
- 모든 단계는 **HTTP API 응답 모양 불변**이 조건이다. 프런트 수정은 0이다(§6).

## 1. 한눈에

| 단계 | 하는 일 | 코드 함수 | 시험 | SQL 파일 | 시간 [추정] | 위험 |
|---|---|---|---|---|---|---|
| **P1 필수** | 승인 스냅샷 단일화 + 승인 칸 3개, 검사 단순화, FK(대화) · 삭제 트리거, 세션 인덱스 · 만료 세션 청소, `display_name` 삭제, 이력 표 | **3~4** (`services/quote.py`) | 고침 약 6 + 새로 약 5 | `expand` + `contract_p1` | 5~6시간 | 낮음. 에이전트 · 화면 불변 |
| **P2 권장** | 분석 회로 사본 삭제, 죽은 승인 경로 삭제, 소유자 FK CASCADE, 청소 함수 교체 | **11** (`memory_service.py`) | 약 25 | `contract_p2` | 12~16시간 | 중간. 시험이 많이 얽힘, `detail()` 응답 키 확인 필요 |
| **D8 권장** | 데모 계정을 첫 데모 로그인 때 만든다(007 제거) | 1 (`auth.py demo_session`) | 2~3 | 007 삭제 | 2~3시간 | 낮음 |
| **2b 선택** | `auth_google_pending` 삭제와 승인 대기 코드 제거 | 3 + 라우트 1 + CLI 분기 1 | 약 5 | `2b` | 3~4시간 | 낮음 |
| **M 권장** | 기준선 교체: compose · CI · 시험이 `baseline_service.sql` 하나만 읽고, 앱이 시작 때 SQL을 적용하지 않음 | 1 (`memory_service.initialize` 제거) | 파일 약 7개의 하드코딩 → 헬퍼 | `baseline` | 8~10시간 | 중간. **P2 코드 완료 후에만 맞음**, 첫 기동 경로 변경 |
| **P3 보류** | 분석 대화 · 메시지 표를 `public`으로 완전 통합 | 약 22 | 60여 개 | 신규 | 3~4일 | 높음(데모 재생) |
| **D10 보류** | 서비스 표를 `public` 밖 비노출 스키마로 | SQL 정규화 이름 다수 | 스키마 설정 확인 | 신규 | 1일 | 중간 |

의존 관계: P1 → (P2) → M. P2는 P1 없이도 가능하지만 expand가 먼저여야 한다. M은 P2가 끝난 뒤. D8 · 2b는 독립.

## 2. P1 상세

### 코드 (`backend/services/quote.py`)

| 함수 | 바뀌는 것 |
|---|---|
| `QuoteService.approve` | `approvals` INSERT에 `candidate_part · verdict · part_number` 추가, `approved_cases` INSERT에서 snapshot 제거 |
| `QuoteService.create_quote` | 품번을 `approvals.part_number`에서 읽고(옛 승인 · NULL이면 `part_number()`로 계산), `quotes` INSERT에서 snapshot 제거 |
| `QuoteService.list_cases` | `approved_cases` JOIN `approvals`에서 `candidate_part · verdict`를 읽음(JSON 경로 대신 칸) |
| `approval_snapshot` | 변경 거의 없음(스냅샷 JSON은 그대로, 칸 3개 값을 돌려주는 모양만) |

`backend/api/quotes.py`의 응답 모델(`Approval` · `Quote` · `ApprovedCase`)은 **그대로**다.

### 시험

| 파일 | 변경 |
|---|---|
| `tests/conversations/test_dto.py::test_safe_judgement_fields_match_runs_sql_shape` | SQL 텍스트(019 · 025)를 파싱해 JSON 모양을 대조하던 시험 → 삭제하고 "필수 키 6개" 검사 시험으로 교체 |
| `tests/projects/test_project_repository.py::test_demo_catalog_matches_db_allow_list` | 데모 6개 목록 대조 시험 → "데모일 때만 `demo_id`" 검사 시험으로 교체 |
| `tests/services/test_quote_service.py` | 스냅샷 · 품번 시험 2~3개 조정 |
| `tests/api/test_full_service_flow.py` | 승인 → 견적 흐름 · 옛 승인 시험 2개 조정(snapshot 칸 없음) |
| 새로 | 삭제 연쇄(프로젝트 → 분석 대화 · 체크포인트), 트리거, FK 거부, 새 CHECK 거부 · 허용, 만료 세션 청소 — 약 5개. 기준은 `db/redesign/verify/rd_test2.sh`가 이미 일회용 DB로 확인한 항목 |

### SQL · 운영
`migrate_prod_1_expand.sql` → P1 코드 배포 → 스모크 → `migrate_prod_2_contract_p1.sql`. 이전 규모는 서비스 데이터 사용자 5 · 프로젝트 11 · 승인 3.

### 문서
`db/DB.md`(새 파일 · 순서), `db/schema/erd.md` · `table-definition.md`(이 폴더의 `to-be` 문서로 교체 또는 링크), `SPEC.md` 8.5(보관: 승인 스냅샷 1벌, 만료 세션 청소), `docs/specs/user-thread-memory.md`, `backend/services/SERVICES.md`.

## 3. P2 상세

### 코드 (`backend/conversations/memory_service.py`)

| 함수 | 바뀌는 것 |
|---|---|
| `Conversations.ensure_thread` | `sojafit_agent.circuits` INSERT 제거(스레드만 INSERT). 인자(`filename · connections`)는 데모 확인에 쓰이므로 시그니처 유지 |
| `Conversations._owned` | `public.threads → projects → circuits`를 JOIN해 `filename`(= 프로젝트 이름, 현재 `repo.get_thread`가 넘기는 값과 같다)과 `connections`를 읽음 |
| `Conversations.threads` | 같은 JOIN으로 목록 |
| `Conversations.detail` | `approvals` · `memories` 조회와 `related_memories · consulted_memories · referenced_memories · can_approve` 부분 제거. **응답 사전의 키는 빈 값으로 유지해 API 계층이 안 깨지게** 한다 |
| `Conversations.upload` · `create` | 시험 전용 → 삭제 |
| `delete_analysis_threads` | 회로 삭제 제거. **`DELETE /api/me` 응답의 `analysis_circuits` 키는 상수 0으로 유지**(응답 모양 불변) |
| `Conversations.approve` · `_approve` · `memories` · `_current_memories` | 옛 승인 경로 → 삭제 |

그 밖: `backend/api/projects.py::delete_owned_with_checkpoints`는 호출만 하므로 거의 그대로.

### 시험 (약 25개)

| 파일 | 변경 |
|---|---|
| `tests/api/test_threads.py`(31개) | 승인 관련 약 10개 삭제 · 재작성(`test_approval_*`, `test_old_approval_*`, `test_unapproved_*`, `test_new_threads_send_no_approved_cases_*` 등). 약 12개는 `ensure_thread`를 부르는 `runtime` fixture → **먼저 `public.projects/circuits/threads` 행을 만드는 헬퍼** 추가 필요(FK 때문) |
| `tests/api/test_deletion.py`(8개) | 6개 조정(분석 회로 개수 검증 제거, `analysis_circuits == 0`) |
| `tests/api/test_errors.py` · `test_conversations.py` · `tests/services/test_demo_replay.py` | `ensure_thread` 호출처 각 1~4곳에 헬퍼 적용 |
| `tests/conversations/test_profile.py` | `sojafit_agent` 참조 3개 확인 |

### 위험과 확인할 것
- `detail()` 반환 키를 API 계층(`backend/api/conversations.py`)이 어디까지 읽는지 **구현 때 코드로 확인**한다(이 조사는 파일 목록 수준).
- 키 없는 데모의 기록 재생: P2는 분석 **입력 문자열 · 문맥 구성(`message()`의 `messages` 조회)을 건드리지 않으므로** 재생은 그대로다. 구현 후 스모크 `--demo` 23 · 28단계로 확인.

### SQL · 운영
`migrate_prod_3_contract_p2.sql`: `sojafit_agent.circuits` · `approvals` 삭제, `circuit_id` 칸 삭제, `user_id` FK CASCADE, 청소 함수 교체. 전제: P2 코드가 100%이고 계정 삭제 · 프로젝트 삭제 점검이 통과.

## 4. P3(보류)가 큰 이유

분석 서비스의 대화 상태 · 문맥 · 승인을 `public`으로 합치면:
- `memory_service.py`: `ensure_thread · _owned · locked · threads · detail · message · resume · _invoke · _record_event · _finish · _reconcile · delete_analysis_threads · account_deletion · _purge_expired` 등 약 15개
- `backend/conversations/repository.py`: `create_thread · get_thread · start · finish · resume · thread_detail · get_run` 약 7개
- 시험: `test_threads`(31) · `test_conversations`(23) · `test_deletion`(8) · `conversations/test_repository`(14) · `services/test_demo_replay`(18)의 상당수 = 60여 개
- **분석 입력 문자열**: `message()`가 `messages` 행의 `content`(`'사용 조건: …\n' + 질문` 형식)로 이전 입력 문맥을 만든다. 합친 뒤 조건 칸을 따로 두면 이 문자열을 정확히 같게 재구성해야 키 없는 데모 재생이 유지된다. 한 글자라도 다르면 재생이 멈춘다(503).

## 5. M(기준선 교체)이 바꾸는 곳 — SQL 파일 이름을 부르는 곳 20개

조사 §6-1의 목록 중 서비스 표 관련만 정리했다(코퍼스 SQL 002 · 008 · 009 · 012를 부르는 곳은 그대로).

| 구분 | 곳 | 바뀌는 것 |
|---|---|---|
| CI | `.github/workflows/ci.yml` | `003 · 005 · 006 · 021` 4개 로드 → `baseline_service.sql` 1개 |
| compose | `docker-compose.yml`, `Dockerfile` | initdb 마운트는 그대로(`db/` 폴더). `thread-setup`은 LangGraph 표만 |
| 코드 | `backend/conversations/memory_service.py initialize`(013~017 · 022 · 023을 런타임에 적용), `backend/auth.py`(003 · 007 참조 주석), `evals/runners/run_judgement_bundle.py` | `initialize`의 SQL 파일 적용 제거(앱은 DDL을 안 돌린다) |
| 시험 | `tests/api/test_auth.py`(8) · `test_full_service_flow.py`(6) · `conversations/test_repository.py`(5) · `projects/test_project_repository.py`(5) · `api/test_projects.py`(5) · `conversations/test_dto.py`(2) · `services/test_quote_service.py`(1) | 파일 이름 하드코딩 → 헬퍼 `apply_baseline(conn)` 하나 |
| 문서 | 문서 18개 + 작업 기록 4개 | `db/DB.md` · `db/schema/*` · `SOJAFIT.md` · `SPEC.md` 등 필요한 것만 |

기준선은 P1 + P2 완료 상태다. **P2 코드가 끝나기 전에 교체하면 코드와 구조가 안 맞는다.** 그 전까지 새 DB는 `000 ~ 025` + `026`(보안) + `027`(expand + contract P1 이어 붙임) + `028`(contract P2)로 만든다(빈 DB에서는 expand · contract 구분이 필요 없다 — 위 시험의 순서로 이미 통과).

## 6. 프런트 · API 계약(불변 조건)

프런트가 표 칸에 직접 묶인 곳은 3곳뿐이다(조사 §2).

| 계약 | 지키는 방법 |
|---|---|
| `runs.safe_result` JSON = `GET /api/runs/{id}` 응답 | **저장 데이터를 안 바꾼다.** CHECK만 단순화(필수 키 6개). 응답을 만드는 `result_dto` · `SafeResult`는 그대로 |
| `quotes.part_number` | 칸 · 형식 CHECK 그대로 |
| `approved_cases.snapshot->candidate` → `ApprovedCase.candidate_part · verdict` | `approvals.candidate_part · verdict`를 JOIN해 **같은 값**을 줌. 응답 모델 불변 |
| `DELETE /api/me`의 `deleted.analysis_circuits` | P2 뒤에도 키 유지, 값은 0 |
| `Approval.case_id` | `approved_cases.id` 그대로 |

OpenAPI 경로 · 모델 목록은 `tests/api/test_openapi.py`가 고정하고 있어 어긋나면 시험이 잡는다.

## 7. 검증 계획(구현 때)

| 단계 | 확인 |
|---|---|
| 일회용 DB | `bash db/redesign/verify/run_all.sh`: Postgres 16 · 17에서 이전 · 되돌리기 · 동작을 반복(이미 통과) |
| 로컬 | 키 없는 전체 시험, DB 연결 시험(`TEST_AUTH_DATABASE_URL`, 스킵 0), `docker compose up` 한 줄 기동 + 스모크 `--demo --refusal` |
| 배포 | 0% 점검 → 100% → 배포 주소 스모크 28단계(실제 모델) |
| 평가 | 에이전트 코드가 바뀌지 않으므로 v3 재측정은 필수가 아니다(P3를 하면 필요) |
| 되돌리기 | 단계마다 `migrate_prod_4_rollback.sql`의 해당 절 + Cloud Run 이전 리비전. **contract 뒤에는 코드를 되돌리기 전에 DB 되돌리기가 먼저**(옛 코드가 지운 칸을 읽으므로) |

## 8. ADR 후보(주요 문서라 정운이 정한다)

1. 이중 저장은 최소안(FK + 회로 사본 삭제)으로 한다 — P3는 보류
2. 승인 스냅샷은 `approvals` 한 곳, 칸으로 꺼낸 값은 `approvals`에
3. DB CHECK는 불변식만, 앱 JSON 모양은 앱이 정본
4. 마이그레이션은 우리 이력 표 `app_migrations` + 증분 파일, 기준선은 P2 뒤
5. 삭제 정합성은 DB 트리거(체크포인트)와 FK CASCADE로 보장
6. 서비스 표는 기준선이 RLS ON을 명시, 권한은 026
