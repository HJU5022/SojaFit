# 사용자별 분석 thread와 사용자 사실 기억

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 8.5 사용자 사실 기억, 4절 대화 API, 토큰 한도는 8.6)
- 관련 문서: [evaluator-demo-readiness.md](evaluator-demo-readiness.md), [thread-memory-operations-review.md](../research/thread-memory-operations-review.md), [thread-memory-operations.md](../experiments/thread-memory-operations.md), `backend/conversations/CONVERSATIONS.md`

## Why

- 로그인 사용자가 자기 회로의 특정 부품 분석을 대화 단위로 이어가야 한다. 다른 사용자의 접근은 막아야 한다.
- 검증 지표: 다른 사용자 접근 허용 0건, 재접속·저장소 재연결 후 상태 유실 0건.

## Goal

- 분석 한 건 = 대화(thread) 하나. 사용자 한 명은 여러 대화를 소유한다. 대화 UUID가 LangGraph checkpoint의 `thread_id`다.
- 대화 생성·질문·중단 재개·삭제를 대화 API로 제공한다([SPEC.md](../../SPEC.md) 4절).
- 기존 비밀번호·Google 로그인과 세션을 그대로 사용한다.
- 다음 대화에서도 유효한 사람에 대한 사실 3칸을 설정 API로만 저장·조회·삭제한다.
- Out of Scope: 한 대화 안의 여러 분석, 대화에서 기억 자동 학습, 승인한 판정 사례를 새 분석에 넘기는 일(`approved_memories`는 항상 빈 목록, `memory_service.py:442`), 견적서 발행·가격 저장.

## What

- 대화는 프로젝트(회로 + 대상 부품) 아래에 만들고, 같은 UUID로 분석 thread(`sojafit_agent.threads`)가 생긴다. 질문마다 `POST /api/threads/{id}/runs`, 조건 질문 재개는 `POST /api/runs/{id}/resume`다.
- 조건 질문(`interrupt`)은 같은 대화에서 재개한다. 다른 회로·대상 분석은 새 대화를 만든다.
- 다른 사용자의 대화·run은 404, 미인증은 401, 같은 대화에 동시 실행은 409다.
- 승인은 `POST /api/messages/{id}/approvals`가 `public.approvals`에 남긴다(견적 승인, 이 서비스 밖). Store에는 쓰지 않는다.
- DB 실패를 성공으로 응답하지 않는다. 사용자 입력·토큰·접속 문자열을 오류·로그에 노출하지 않는다.

## How

### 신뢰 경계

- `auth.current_user_id`가 검증한 정수 `users.id`만 소유자로 쓴다. 대화 ID는 서버가 UUID로 발급한다.
- 읽기·쓰기·재개 전에 대화의 소유권을 확인한다(`memory_service._owned`). 관리자도 다른 사용자의 분석을 읽지 못한다.
- 쿠키 기반 상태 변경 API는 `auth.check_origin`을 쓴다. 응답에 `Cache-Control: no-store`를 붙인다.
- 같은 대화의 동시 실행은 DB advisory lock으로 거부한다(`Conversations.locked`, 409).

### 분석 한도

- 실행 한 번: 호출 16회, 예약 USD 0.50, 90초, 출력 4096토큰, 입장 간격 2초, 사용자별 하루 예약 USD 3. 기본값은 환경변수 `ANALYSIS_MAX_CALLS`·`ANALYSIS_MAX_USD`·`ANALYSIS_MAX_SECONDS`·`ANALYSIS_MAX_TOKENS`·`ANALYSIS_MIN_INTERVAL_SECONDS`·`ANALYSIS_DAILY_USD`로 바꾼다(`memory_service.py:171-182`).
- 하루 토큰 상한(사용자·서비스)은 [SPEC.md](../../SPEC.md) 8.6, 값의 근거는 `backend/conversations/memory_service.py`.
- 예약액은 공급자 청구액이 아니다. 오류 코드는 [api-error-contract.md](api-error-contract.md).

## 사용자 사실 기억

칸 · 저장 · 검색 · 활용 · 고치기 · 지우기 · 한계 · 수용 기준의 정본은 [SPEC 8.5](../../SPEC.md)다. 여기에는 구현 위치와 세부를 둔다.

- 결정: 체크포인터는 이번 대화의 상태, Store는 다음 대화에서도 유효한 사람에 대한 사실이다. namespace의 첫 칸(사용자 id)이 격리 단위이고, 노드는 LangGraph가 넣어 주는 Store를 받는다(멀티 그래프 `기억 읽기`, 11-10). namespace는 접근 권한 검사가 아니다. 칸은 소속(`affiliation`) · 직무(`job_role`) · 선호 실장 방식(`mounting_preference`) 3개다.
- 코드: `backend/conversations/profile.py`(칸 검사 `clean`, 틀 문장 `sentence`, `VoyageEmbeddings`, `ProfileMemory.facts · update · delete`), `backend/api/profile.py`(`/api/me/memory`), `memory_service.Conversations.profile`과 `_profile_hints`, `dto.result_dto(profile_hints=...)`.
- 저장 모양: Store `(str(user_id), "profile")` / key = 칸 이름 / 값 `{kind, value, text, version, updated_at, source: "user_settings"}`. 여러 칸을 한 번에 고치면 `PutOp`을 한 `batch`로 보내 임베딩도 한 번 부른다.
- 색인: `PostgresStore(index={'dims': 1024, 'embed': VoyageEmbeddings(), 'fields': ['text'], 'ann_index_config': {'kind': 'flat'}})`. LangGraph 동기 `PostgresStore`는 검색 질문도 `embed_documents`로 임베딩하므로, 검색하는 동안만 입력 종류를 `query`로 바꾼다(`contextvars`). 근사 색인(HNSW)은 namespace 조건과 함께 쓰면 다른 사용자 벡터에 밀려 결과가 빌 수 있어 만들지 않는다.
- 켜는 조건: `VOYAGE_API_KEY`가 있고 `DEMO_MODE`가 1이 아니며 `sojafit_agent.store_vectors`가 있을 때. 셋 중 하나라도 아니면 색인 없는 Store로 쓰고 읽는다. 키가 있는데 표가 없으면 시작 때 경고 로그(`profile_index_unavailable`)를 남긴다.
- 스키마 경로: 준비 명령과 색인을 켠 서비스 연결은 `search_path`를 `sojafit_agent, <vector 확장 스키마>`로 둔다. 색인 표의 `vector(1024)` 형과 검색의 `::vector` · `<=>`가 이름으로 찾히기 때문이다. 표는 첫 스키마인 `sojafit_agent`에 생긴다. 확장 스키마는 `pg_extension`에서 읽는다(로컬 Compose `public`, Supabase `extensions`). 준비 명령은 확장을 설치하지 않는다.
- 활용: `Conversations.message`(그 질문 글)와 `resume`(그 버전의 질문 글)이 그래프를 돌리기 전에 사실을 찾고, 응답의 `profile_hints`에 칸 · 값 · 문장만 담는다. 찾기가 실패하면 빈 목록이고 분석은 계속한다. React run은 완료 · 거절 frame에만 싣고 `public.runs`에는 저장하지 않는다. 에이전트 연결: 멀티 그래프의 `기억 읽기` 노드(`backend/graph/memory.py` `read_profile`)가 선호 실장 방식 한 칸만 읽어 `mount_preference`로 두고, Spec 에이전트가 찾기 후보 순서에만 쓴다(질문이 실장 방식을 말하면 질문이 이김, 판정 · 거르기 · 프롬프트는 그대로, 결과 `preferred_mount`). 소속 · 직무는 그래프 상태 · 프롬프트에 넣지 않는다. 승인 사례 프롬프트 문단("Historical approved cases")과 늘 빈 `approved_memories` · `memory_refs` 길의 제거는 아직 하지 않았다.
- 시험: `tests/conversations/test_profile.py`(칸 검사 · 틀 문장 · version · 지우기 · 의미 순위 · 입력 종류 · 대체 경로 · API 422 · 403 · 401 · 503, DB: 색인 표 위치, `extensions` 스키마), `tests/api/test_threads.py`(승인 사례 미전달, 질문 · 재개의 참고, A/B 격리, 색인 DB에서 다시 임베딩 · 지운 벡터), `tests/api/test_conversations.py`(React frame의 참고, run 기록 미저장), `tests/multi_agent/test_build.py` · `test_judge.py` · `tests/judge/test_judge_verdict.py`(기억 읽기 격리, 찾기 순서, 질문 우선, Store 없으면 예전 순서).

### 보관 · 삭제
- 사용자 사실은 자동 만료가 없다. 사용자가 지우거나 계정을 지울 때 지운다.
- 프로젝트와 거기에 딸린 것(대화, checkpoint, 승인, 견적)은 마지막 활동 뒤 60일에 자동으로 지운다.
- 기록 종류(분석 사건, 로그인 · 가입 시도, 하루 사용량)는 30일 뒤에 지운다.
- 사용자가 직접 지우면 숨기지 않고 바로 지운다.
- 정리는 스케줄러 없이 새 분석을 시작할 때 작은 묶음으로 한다.

#### 자동 정리(`db/020_service_baseline.sql`)
- 규칙 하나 = SQL 함수 하나(`sojafit_agent` 스키마, 공개 역할 EXECUTE 회수). 분석 서비스가 새 질문(`Conversations.message`)마다 그 thread를 잠그기 전에 `SELECT purge_inactive_projects(), purge_log_records()`를 따로 연결로 부른다(`_purge_expired`). 실패하면 `backend.conversations.retention` 경고(`retention_purge_failed`)만 남기고 분석은 계속한다. 시작 때 두 함수가 없으면 서비스가 뜨지 않는다(규칙이 조용히 꺼지지 않게).
- `purge_inactive_projects(keep_days DEFAULT 60, batch_size DEFAULT 20)`: ① React 프로젝트의 마지막 활동 = 프로젝트 `updated_at`(이름 변경) · 대화 생성 · run `updated_at`(시작 · 끝 · 재개) · 승인 · 견적 중 가장 늦은 시각. 지난 것을 최대 batch_size개 `FOR UPDATE SKIP LOCKED`로 골라 사용자가 지울 때와 같은 순서(같은 UUID의 checkpoint → 분석 thread → 빈 분석 회로 → 프로젝트 cascade)로 지운다 ② React 대화에 딸리지 않은 분석 thread(`/api/threads`로 직접 만든 것, 예전 규칙으로 프로젝트만 지워져 남은 것)는 자기 마지막 활동(생성 · 메시지 · 분석 사건 · 승인 · 승인 기록 관리)으로 본다 ③ thread가 없는 분석 회로(업로드 넷리스트 원문)는 올린 뒤 60일. React 표가 없는 DB에서는 아무것도 지우지 않는다.
- `purge_log_records(keep_days DEFAULT 30, batch_size DEFAULT 200)`: 분석 사건(`created_at`), 하루 사용량(사용자 · 서비스 전체, UTC 날짜), 가입 시도(UTC 날짜), 로그인 시도(계정 · IP: 15분 창 시작이 30일 지났고 잠금이 없거나 끝난 행만)를 표마다 최대 batch_size개(ctid 묶음) 지운다.
- 두 함수 모두 트랜잭션 advisory lock(`736128` · `736129`)으로 동시에 한 곳만 청소하고 나머지는 기다리지 않고 0을 돌려준다. Supabase pg_cron으로 하루 한 번 같은 함수를 부를 수 있다(지금은 켜지 않음, SQL 머리 주석에 예).
- 60일 · 30일의 이유: 회로는 몇 주 뒤에 다시 여는 일이 많아 한 달보다 넉넉히 둔다. 기록은 최근 디버깅과 남용 한도 확인에만 쓴다.

#### 규칙과 개인정보 보호법 조항

| 규칙 | 구현 | 조항 |
|---|---|---|
| 보관 기간이 지나면 자동으로 지운다(프로젝트 · 분석 대화 60일, 기록 30일) | `db/020_service_baseline.sql`의 청소 함수 2개, 새 분석 때 작은 묶음 | 21조(파기): 보유기간이 지나 불필요해진 개인정보는 지체 없이 파기 |
| 사용자가 프로젝트 · 내 설정을 지우면 바로 실제로 지운다 | `DELETE /api/projects/{id}`(같은 UUID 분석 기록 · checkpoint 포함), `DELETE /api/me/memory` | 36조(삭제 요구) |
| 탈퇴하면 계정과 모든 기록을 지운다 | `DELETE /api/me`(기록 먼저, 계정 마지막, 다시 요청하면 이어서) | 37조(처리정지 요구 · 동의 철회) |
| 가입·로그인 화면에서 처리방침을 알린다 | 공개 `/privacy`(`frontend/src/pages/PrivacyPage.tsx`: 처리 항목 · 보관 기간 · 삭제 · 외부 서비스)로 가는 링크. 별도 동의 체크와 동의값 저장은 없고 서버 `consent`는 호환용 선택 필드다(`backend/api/auth.py:193,260`) | 15조 2항(동의를 받을 때 알릴 사항) |

#### 사용자가 지울 때(구현)
- 프로젝트 삭제 `DELETE /api/projects/{id}`(`backend/api/projects.py:184` `delete_owned_with_checkpoints`): 프로젝트 행을 잠근 같은 트랜잭션에서 그 프로젝트 대화 UUID의 분석 checkpoint 표 3개(`checkpoint_writes` · `checkpoint_blobs` · `checkpoints`, thread_id 글자) → 분석 thread(메시지 · 승인 기록 · 분석 사건은 FK cascade) → 남은 thread가 없는 같은 UUID 분석 회로 → 프로젝트(회로 · 대화 · run · 메시지 · 승인 · 견적 · 승인 사례는 FK cascade) 순서로 지운다(`memory_service.delete_analysis_threads`, 사용자 조건으로만 고름). 하나라도 실패하면 모두 되돌린다. 사용자 사실(Store)은 프로젝트에 딸리지 않아 남는다.
- 탈퇴 `DELETE /api/me`(`backend/main.py`): Origin 확인, 관리자는 409(운영자 CLI `--delete-user-id`도 관리자는 지우지 않음). 순서는 기록 먼저, 계정 마지막이다. ① 계정 배타 잠금 ② 그 사용자의 분석 thread · 회로 · checkpoint 전부(한 트랜잭션) ③ Store를 namespace 접두사로 찾아 지우는 반복(`(user_id,)` 아래 전부와 옛 `("memories", user_id)`, 한 번에 100개 · 최대 1만 개) ④ 계정 행(세션 · 프로젝트 · 견적 · 승인 사례 · 하루 사용량은 FK cascade, 그 이메일의 로그인 실패 행도 지움). 응답은 `{"deleted": {analysis_threads, analysis_circuits, checkpoints, memory_items, projects, quotes, account}}`이고 세션 쿠키를 지운다.
- 멱등: 계정을 먼저 지우면 기록 삭제가 실패했을 때 다시 요청할 방법이 없다. 그래서 계정을 마지막에 지우고, 중간 실패는 503(`계정 삭제를 끝내지 못했습니다. 다시 요청하면 남은 기록부터 이어서 지웁니다.`)이며 다시 요청하면 남은 것만 지운다(이미 지운 것은 0건).
- 잠금(선택: advisory lock, 표 없음): 키 `hashtextextended('account:<user_id>', 0)`. 분석 실행(`locked`) · 대화 연결(`ensure_thread`) · 업로드 · thread 만들기 · 설정 저장(`account_writer`)은 공유로, 탈퇴는 배타로 잡는다. 공유끼리는 서로 막지 않고 탈퇴와만 막으므로 그 사용자의 분석이 도는 동안 탈퇴는 409(`진행 중인 분석이나 저장이 끝난 뒤 다시 시도하세요.`), 탈퇴가 도는 동안 그 사용자의 새 분석 · 재개 · 설정 저장은 409(`계정 삭제를 처리하는 중입니다.`)다. React run · 재개는 스트림을 열기 전(`admission`)에도 확인한다. 표식 표 대신 잠금을 고른 이유: DB 세션 잠금이라 프로세스가 죽어도 연결과 함께 풀려 남는 표식이 없고, 탈퇴가 실패해도 계정이 남아 있어 다시 요청하면 된다. 공유 public 업무 표의 쓰기(프로젝트 · 대화 · 견적)는 계정 행 삭제의 FK cascade가 지우므로 잠그지 않는다.
- 화면: 내 설정(`/settings`)의 "계정 삭제"(일반 계정만 보임)는 확인 뒤에만 `DELETE /api/me`를 보낸다. 로그아웃 · 탈퇴 · 세션 만료로 로그인 상태를 잃으면 React가 화면 메모리(React Query 캐시)와 sessionStorage를 비우고 보호 화면은 `/login`으로 바꾼다(replace). 로그인 URL에 회로 식별자는 남기지 않는다. 직접 로그아웃·탈퇴는 복귀도 막으며, 세션 만료·비로그인 대화 링크만 내부 `/app` 주소를 탭에 임시 보관해 로그인 성공 후 복원·제거한다([login-auth.md](login-auth.md)). 대화 본문·판정·자격 증명은 보관하지 않는다.
- 한계: 분석 서비스(`THREADS_ENABLED=1`)가 없으면 탈퇴는 503이다(분석 기록 · Store를 지울 수 없으므로). React run 행이 `running`으로 남은 상태(서버가 실행 도중 죽음)는 잠금이 없어 탈퇴를 막지 않는다.

## AC

| AC | Given-When-Then | 시험 |
|---|---|---|
| AC-01 | 사용자 B가 사용자 A의 run을 조회하면 404다 | `tests/api/test_errors.py::test_other_users_run_is_not_found` |
| AC-02 | 미인증 요청이면 401이고 그래프·Store를 호출하지 않는다 | `tests/api/test_conversations.py` |
| AC-03 | 조건 질문에서 멈춘 분석을 서버 재시작 뒤에도 같은 대화에서 재개한다 | `tests/api/test_http_restart.py`, `tests/api/test_full_service_flow.py` |
| AC-04 | 사용자 사실은 A/B가 서로 보이지 않고 칸 검사·고정 문장 틀을 따른다 | `tests/conversations/test_profile.py` |
| AC-05 | 새 분석을 시작하면 60일 지난 프로젝트와 30일 지난 기록만 작은 묶음으로 지우고, 청소 실패는 분석을 막지 않는다 | `tests/api/test_deletion.py::test_purge_inactive_projects_deletes_only_past_60_days_in_bounded_batches`, `test_purge_log_records_deletes_only_past_30_days_and_keeps_active_locks`, `test_new_analysis_runs_cleanup_and_cleanup_failure_does_not_block` |
| AC-06 | 프로젝트 삭제는 같은 UUID의 분석 기록·checkpoint를 함께 지우고 다른 프로젝트는 남긴다 | `tests/api/test_deletion.py::test_project_delete_removes_its_react_and_analysis_records_only` |
| AC-07 | 탈퇴는 본인 기록만 지우고, 중간 실패 뒤 다시 요청하면 이어서 지운다 | `tests/api/test_deletion.py::test_account_delete_removes_everything_of_user_and_leaves_others`, `test_account_delete_rerun_after_partial_failure_finishes` |
| AC-08 | 탈퇴와 진행 중 분석은 서로 배제한다(409) | `tests/api/test_deletion.py::test_account_delete_and_running_analysis_exclude_each_other` |
| AC-09 | 관리자 계정은 탈퇴 API로 지워지지 않는다 | `tests/api/test_deletion.py::test_admin_cannot_self_delete` |

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 대화 단위 분석 thread, checkpoint 재개 | 구현 | `backend/conversations/memory_service.py`, `backend/api/conversations.py` |
| 사용자 사실 3칸 | 구현 | `backend/conversations/profile.py`, `backend/api/profile.py` |
| 자동 정리·삭제·탈퇴 | 구현 | `db/020_service_baseline.sql`, `backend/api/projects.py:184`, `backend/api/profile.py` |
| 승인 사례의 새 분석 전달 | 하지 않음(`approved_memories` 빈 목록) | `memory_service.py:442` |
| 승인 사례 프롬프트 문단과 `memory_refs` 경로 제거 | 미실시 | 본문 "사용자 사실 기억" 활용 항목 |

## 한계

- 이 문서의 이전 판(분석 thread 전용 `/api/threads/*` 경로, 업로드 `/workspace` 화면, 승인 사례 기억)은 삭제된 경로를 전제하며 현재 코드에 대응하지 않는다. 현재 경로는 [SPEC.md](../../SPEC.md) 4절.
- 시험 AC-02·AC-03의 시험은 DB가 있을 때만 실행되는 것이 있다(`TEST_THREAD_DATABASE_URL`, `.github/workflows/ci.yml:30`). 이 문서 작성 때 실행해 확인하지 않았다.
- 삭제 후 클라우드 로그·외부 추적·백업 사본의 보관 기간은 이 저장소로 확인할 수 없다([처리방침 화면](../../frontend/src/pages/PrivacyPage.tsx)이 같은 한계를 적는다).

