# api

## 역할
- 이 폴더: 서비스 HTTP 경로 전부. 라우터마다 `APIRouter`를 하나 갖고 `backend/main.py`가 등록한다. 라우터 태그는 파일 이름과 같아 `/docs`가 묶음별로 보인다.
- 넣는 것: 경로 함수, 요청·응답 모델(`extra="forbid"`와 `/docs` 예시를 단 pydantic 모델), 세션·Origin 확인 의존성 연결.
- 넣지 않는 것: 공통 오류 응답·요청 ID·본문 한도·라우터 등록(`backend/main.py`), 인증 구현(`backend/auth.py`), 프로젝트 SQL(`backend/projects/`), 분석 실행(`backend/conversations/`, `backend/multi_agent/`), Mouser 호출 자체(`backend/services/mouser.py`).
- 담당: 서비스·운영

경로 수와 오류 코드 표의 정본은 [SPEC.md](../../SPEC.md) 4절이고, 경로 목록(메서드, 경로)은 `tests/api/test_openapi.py`가 고정한다. 화면의 호출은 모두 `frontend/src/api.ts`의 `api()`를 거치고 자료형은 `frontend/src/types.ts`에 있다(2026-11-16 새 화면부터 라우터마다 짝 파일을 두지 않는다). 계약 상세는 [api-error-contract.md](../../docs/specs/api-error-contract.md), [login-auth.md](../../docs/specs/login-auth.md), [google-user-login.md](../../docs/specs/google-user-login.md)를 따른다.

## 파일
| 파일 | 경로 (메서드 경로) |
|---|---|
| `API.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `health.py` | `GET /health` |
| `auth.py` | `/api/auth/*`: 로그인, 이메일 가입(요청·확인), 비밀번호 재설정(요청·확인), `me`, `logout`. `DEMO_MODE=1`에서만 `demo`·`demo-login`. `/docs`에 안 싣는 `google/*` 7개 경로(`status`, `start`, `callback`, `pending`, `onboarding`, `signup`, `link`) |
| `admin.py` | `GET /api/admin/users`, `PATCH /api/admin/users/{target_id}`(일반 계정 활성 상태 변경), `POST /api/admin/users/{target_id}/unmask`(사유 5~500자, 이력을 먼저 쓰고 이메일 원문), `DELETE /api/admin/users/{target_id}`(일반 계정 탈퇴 처리, `profile.erase_account` 재사용), `GET /api/admin/audit`(작업 이력). 활성 상태 변경 · 가림 해제 · 탈퇴 처리는 `admin_audit`(db/034)에 남는다 |
| `prices.py` | `GET /api/prices`(로그인 필요, 요청 때 Mouser 조회, 선택 quantity 1~100000의 동일 품번 수량 구간/Decimal estimate를 응답에만 포함. `Cache-Control: no-store`, ADR 0009) |
| `projects.py` | `GET /api/demo-circuits`(데모 모드만), `GET`·`POST /api/projects`(빈 생성 또는 데모 복제), `POST /api/projects/upload`, `POST /api/projects/{project_id}/netlist`(새 버전·새 대화, 회로 없는 대화의 `thread_id`면 그 대화 유지), `GET`·`PATCH`·`DELETE /api/projects/{project_id}`. 상세 `thread_id` 쿼리는 해당 대화의 고정 버전을 반환 |
| `external_circuits.py` | `GET /api/external-circuits/schematics`(완성 회로도 manifest), `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}`(PNG 시트) |
| `conversations.py` | `GET /api/judge/roles`·`demo-questions`, 프로젝트별 thread `GET`·`POST`, 모든 프로젝트의 대화 목록 `GET /api/threads`, `GET`·`PATCH`(이름 변경)·`DELETE /api/threads/{id}`, `POST /api/threads/{id}/runs`(SSE), `GET /api/runs/{id}`, `POST .../recover`, `POST .../resume`(SSE) |
| `quotes.py` | `GET`·`POST /api/messages/{id}/approvals`(조회는 소유 assistant 메시지의 활성 승인(사례가 남은 승인)과 승인별 견적(`quotes`)만, 새로고침 뒤 복원용), `POST /api/approvals/{id}/quotes`, `GET /api/projects/{id}/quotes`, `GET /api/approved-cases`, `GET /api/approved-cases/{id}`(사례 하나의 기록: 원래 대화 · 질문 · 저장한 판정 · 근거 · 견적, 공개 허용 목록 통과), `DELETE /api/approved-cases/{id}`(활성 승인 해제, snapshot/기존 견적 보존·재승인 허용) |
| `profile.py` | `GET`·`PATCH`·`DELETE /api/me/memory`(사용자 사실 기억), `DELETE /api/me`(탈퇴, 삭제 순서는 `erase_account` 하나를 관리자의 탈퇴 처리와 같이 씀) |

변경 요청(POST·PATCH·DELETE)은 `auth.check_origin`을 적용한다. run·재개는 `app.state.conversations`(분석 서비스, `THREADS_ENABLED=1`)가 없으면 스트림을 열기 전에 공통 503으로 끝난다. 승인 사례(`quotes.py`의 `approved-cases`)는 새 분석에 넘기지 않는다([CONVERSATIONS.md](../conversations/CONVERSATIONS.md)).

프로젝트 생성 두 경로는 allow_duplicate(bool, 기본false) 쿼리를 지원한다. 같은 계정 중복은409 CONFLICT와 안전한 details.duplicates로 알리고 명시적 true 선택에만 새 id를 만든다. 경로 추가·DB 구조 변경은 없다.

실행 실패/재개 중 오류의 공개 code/message는 저장 결과의 선택적 `error`로 GET 복원한다. 재개 입구429는 실행을 시작하지 않고 조건 대기 상태와 interrupt를 유지하며 오류만 기록한다. 예전 결과에 오류가 없으면 null이고 요청ID/내부 예외는 저장하지 않는다.
