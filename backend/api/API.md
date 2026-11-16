# api

## 역할
- 이 폴더: 서비스 HTTP 경로 전부. 라우터마다 `APIRouter`를 하나 갖고 `backend/main.py`가 등록한다. 라우터 태그는 파일 이름과 같아 `/docs`가 묶음별로 보인다.
- 넣는 것: 경로 함수, 요청·응답 모델(`extra="forbid"`와 `/docs` 예시를 단 pydantic 모델), 세션·Origin 확인 의존성 연결.
- 넣지 않는 것: 공통 오류 응답·요청 ID·본문 한도·라우터 등록(`backend/main.py`), 인증 구현(`backend/auth.py`), 프로젝트 SQL(`backend/projects/`. 예외: `projects.py`의 `delete_owned_with_checkpoints`는 프로젝트와 같은 UUID 분석 기록을 한 트랜잭션에서 지우고, `datasheets.py`는 코퍼스 표를 읽기만 하는 SQL을 직접 둔다), 분석 실행(`backend/conversations/`, `backend/multi_agent/`), Mouser 호출 자체(`backend/services/mouser.py`).
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
| `datasheets.py` | `GET /api/datasheets`(로그인 필요, 읽기만): 데이터시트 서재(#67). 폐기하지 않은 코퍼스 문서를 품번(표지 청크의 품번 목록) · 제목 · 제조사 부분 일치와 분류로 찾아 50건씩, 전체 수와 서재 전체의 분류별 수를 함께 돌려줌 |
| `prices.py` | `GET /api/prices`(로그인 필요, 요청 때 Mouser 조회, 선택 quantity 1~100000의 동일 품번 수량 구간/Decimal estimate를 응답에만 포함. `Cache-Control: no-store`, ADR 0009) |
| `projects.py` | `GET /api/demo-circuits`(데모 모드만), `GET`·`POST /api/projects`(빈 생성 또는 데모 복제), `POST /api/projects/upload`, `POST /api/projects/{project_id}/netlist`(새 버전·새 대화, 회로 없는 대화의 `thread_id`면 그 대화 유지. 둘 다 `.kicad_sch`도 받아 렌더러가 내보낸 넷리스트로 같은 경로를 거치고 원문을 그 버전에 저장, #52), `GET`·`PATCH`·`DELETE /api/projects/{project_id}`, `GET /api/projects/{project_id}/schematic`(올린 회로도의 PNG, 소유자만, `circuit_version` 필수), `GET /api/projects/{project_id}/parts`(부품 점검표: 부품마다 종류 · 판정 지원 · 데이터시트 유무와 종류별 개수, 소유자만, `circuit_version` 필수, #68). 상세 `thread_id` 쿼리는 해당 대화의 고정 버전을 반환하고 `schematic_file`은 그 버전에 올린 회로도 파일 이름 |
| `external_circuits.py` | `GET /api/external-circuits/schematics`(완성 회로도 manifest, `auto_search=true`는 소유권·버전 확인 뒤 품번 포함 원본/참고 자동 구분), `POST /api/external-circuits/schematics/dialogue`(검증된 후보 설명·선택 질문·전체 소개), `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}`(PNG 시트). 제조사 없는 품번에서 복수 공식 제조사가 검증되면 404 `SCHEMATIC_NOT_FOUND`와 `X-Schematic-Failure: ambiguous_manufacturer`로 제조사 명시 필요를 알림. `DEMO_MODE=0`, `EXA_WEB_SEARCH_ENABLED=1`, `EXA_API_KEY`, 32바이트 이상 `AUTH_SECRET`이 모두 있어야 열리고 아니면 503(`external_schematic.py`) |
| `conversations.py` | `GET /api/judge/roles`·`demo-questions`, 프로젝트별 thread `GET`·`POST`, 모든 프로젝트의 대화 목록 `GET /api/threads`, `GET`·`PATCH`(이름 변경)·`DELETE /api/threads/{id}`, `POST /api/threads/{id}/runs`(SSE), `GET /api/runs/{id}`, `POST .../recover`, `POST .../resume`(SSE) |
| `quotes.py` | `GET`·`POST /api/messages/{id}/approvals`(조회는 소유 assistant 메시지의 활성 승인(사례가 남은 승인)과 승인별 견적(`quotes`)만, 새로고침 뒤 복원용), `POST /api/approvals/{id}/quotes`, `GET /api/projects/{id}/quotes`, `GET /api/approved-cases`, `GET /api/approved-cases/{id}`(사례 하나의 기록: 원래 대화 · 질문 · 회로 버전 · 저장한 판정 · 근거 · 견적, 공개 허용 목록 통과. 화면 보고서 `/approved/{id}/report`도 이 응답만 쓴다), `DELETE /api/approved-cases/{id}`(활성 승인 해제, snapshot/기존 견적 보존·재승인 허용) |
| `profile.py` | `GET`·`PATCH`·`DELETE /api/me/memory`(사용자 사실 기억), `DELETE /api/me`(탈퇴, 삭제 순서는 `erase_account` 하나를 관리자의 탈퇴 처리와 같이 씀) |

변경 요청(POST·PATCH·DELETE)은 `auth.check_origin`을 적용한다. run·재개는 `app.state.conversations`(분석 서비스, `THREADS_ENABLED=1`)가 없으면 스트림을 열기 전에 공통 503으로 끝난다. 승인 사례(`quotes.py`의 `approved-cases`)는 새 분석에 넘기지 않는다([CONVERSATIONS.md](../conversations/CONVERSATIONS.md)).

### 회로도 후보 대화

`POST /api/external-circuits/schematics/dialogue`는 로그인·Origin 확인과 분석 서비스의 일일 예약 예산을 사용한다. 기존 GET/PNG 경로는 LLM을 호출하지 않는다.

| 구분 | 계약 |
|---|---|
| 요청 | `question` 1~2000자, `queries` 1~3개(각 trim 후 2~200자), `reference_only` 기본 true. 프로젝트 원본 조회에는 `project_id/circuit_version`, 선택적 `thread_id`와 `reference_only=false`를 함께 지정 |
| 후보 | 서버가 검색·검증한 `candidates` 전체와 `count`. 번호, ID, 검색어, 제목, 제조사·모델·판본, 파일·출처·등급·해시, 기존 GET 선택 주소를 제공. 중복 원본은 검색어 목록을 합침 |
| 대화 | `dialogue.mode`는 `select/all/single`. `message`, 선택적 `question`, 후보 ID별 `descriptions`, `selection_required`, `clarification_fields` 제공. 후보 추가·누락·사실 불일치 출력은 채택하지 않음 |
| 부분 실패 | 검색별 `failures`에 query·HTTP 상태·공개 오류 코드·문구·Retry-After. 정상 후보는 유지하며 전체 검색 실패 시 기존 검색 오류 반환 |
| 생성 실패 | `dialogue.status=unavailable`, 문장은 null, 후보 상세는 유지. 한 번에 소개하는 후보가 24개를 초과해도 후보 목록 자체는 자르지 않음 |
| 상한 | Haiku 5.5, 모델 최대3호출·45초·출력2048토큰·예약 USD0.10. 사용자·서비스의 기존 일일 예약 한도 공유. 한도 거부는 검색 전에429, 분석 서비스 없음은503 |

검색어 추출과 화면 연결은 호출 측이 맡는다. 이 API가 임의로 검색어를 늘리거나 선택 URL을 LLM에게 만들게 하지는 않는다. 루트 SPEC 4절의 경로·개수 변경은 조장 검토 대상으로 남긴다.

프로젝트 생성 두 경로는 allow_duplicate(bool, 기본false) 쿼리를 지원한다. 같은 계정 중복은409 CONFLICT와 안전한 details.duplicates로 알리고 명시적 true 선택에만 새 id를 만든다. 경로 추가·DB 구조 변경은 없다.

실행 실패/재개 중 오류의 공개 code/message는 저장 결과의 선택적 `error`로 GET 복원한다. 재개 입구429는 실행을 시작하지 않고 조건 대기 상태와 interrupt를 유지하며 오류만 기록한다. 예전 결과에 오류가 없으면 null이고 요청ID/내부 예외는 저장하지 않는다.
