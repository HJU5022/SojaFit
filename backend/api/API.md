# api

- 판정 공개 결과의 선택 input_conditions는 검증·단위 변환·추가 입력 반영 후 사용 조건 `{code,value}` 목록이다. 현재 SSE 완료 응답에만 포함하고 runs 저장·GET에서는 복원하지 않는다. DB 형식 변경이나 추가 마이그레이션은 필요 없다. 원시 읽기/질문/보고는 새 항목으로 내보내지 않는다.

## 2026-11-11 실행 복구·재개 오류 보완

- `POST /api/runs/{run_id}/recover`: 기존 로그인·Origin·소유권 검사, Run DTO와 no-store, 없는/타 사용자 404. 오래되고 분석 잠금이 없는 running만 failed로 정리한다. 질문·재개·모델 호출은 하지 않는다. 경로는 총 40개다. GET은 읽기 전용으로 유지한다.
- 재개 답의 요청되지 않은 키는 상태 전이 전에 422다. 400/409/422/429 뒤 현재 checkpoint에 interrupt가 남아 있으면 requires_input을 보존하고 SSE에 공개 error를 함께 전달한다. 시스템 오류나 이미 진행된 그래프에 옛 입력 폼을 복원하지 않는다.
- 자세한 상한·AC와 조장 SPEC 4절 반영 대상은 `docs/specs/api-error-contract.md`에 기록했다.

## 역할
- `/api/auth/me`는 기존 세션의 user_id·role에 본인의 users.login_id(email)을 더해 no-store로 반환한다. 로그인·가입·데모 로그인 성공 응답 및 세션 검증 계약은 그대로다.
- 넣는 것: 서비스 HTTP 경로 전부(health · 로그인 · 관리자 · 가격 · 내 설정 · 프로젝트 · 견적 · 대화). 공통 오류 DTO·요청 ID·본문 한도 처리와 라우터 등록은 `backend/main.py`에 맡긴다(11-10 조장 결정: `main.py`는 앱 조립만).
- 넣지 않는 것: DB SQL(`backend/projects/`), 인증 구현(`backend/auth.py`), 업로드 파싱, D5 실행, Mouser 호출 자체(`backend/services/mouser.py`).
- 담당: 서비스·운영

## 파일
- external_circuits.py — 인증된 공개 저장소 완성 회로도 manifest와 PNG 시트 API
- `API.md` — 이 문서
- `__init__.py` — 패키지 표시
- `admin.py` — 관리자 계정 목록(`GET /api/admin/users`, 이메일 사용자명 가림) · 일반 계정 활성 상태 변경(`PATCH /api/admin/users/{target_id}`)
- `auth.py` — `POST /api/auth/login` · `POST /api/auth/signup` · `GET /api/auth/demo` · `POST /api/auth/demo-login`(둘 다 `DEMO_MODE=1`에서만) · `GET /api/auth/me` · `POST /api/auth/logout`, `/docs`에 싣지 않는 Google 관리자 로그인 `GET /api/auth/google/status|start|callback|pending`
- `conversations.py` — 대화·실행·SSE API, 키 없는 데모의 기록 질문 목록(`GET /api/demo-questions`), 로그인/Origin을 확인하는 단일 대화 삭제(`DELETE /api/threads/{thread_id}`, 204/404/409)
- `health.py` — 서비스 생존 확인 `GET /health`(늘 `{"status": "ok"}`)
- `prices.py` — 가격·재고 `GET /api/prices`(로그인 필요, 요청 때 Mouser 한 번, `Cache-Control: no-store`, 데모 모드·키 없음이면 Mouser를 부르지 않음, ADR 0009)
- `quotes.py` — 완료 판정의 사람 승인, 가격 없는 견적, 사용자 승인 사례 API
- `profile.py` — 내 설정(사용자 사실 기억) `GET/PATCH/DELETE /api/me/memory`, 탈퇴 `DELETE /api/me`(Origin 확인, 관리자 409, 분석 기록 → Store → 계정 순서, 지운 건수)
- `projects.py` — `GET/POST /api/projects`, `POST /api/projects/upload`, `GET/PATCH/DELETE /api/projects/{project_id}`, `GET /api/demo-circuits`

화면과의 짝: `backend/api/<이름>.py`의 경로를 부르는 화면 함수는 `frontend/src/api/<이름>.ts`에 있다(auth · admin · prices · profile · projects · quotes · conversations). 예외는 둘이다: `health.py`는 화면이 부르지 않아 짝이 없고, 탈퇴 `DELETE /api/me`(`profile.py`)를 부르는 `deleteAccount`는 `frontend/src/api/auth.ts`에 있다. 라우터마다 태그(파일 이름과 같음)를 붙여 `/docs`가 묶음별로 보인다. 경로 40개(메서드, 경로)는 `tests/api/test_openapi.py`가 고정한다.

요청 · 응답 모델(SPEC 4절 엔드포인트 표): JSON 본문 모델은 `model_config`의 `json_schema_extra`로 `/docs` 예시를 달고 모르는 칸을 422로 막는다(`extra="forbid"`). 성공 응답은 경로 옆에 둔 응답 모델로 적는다: `health.py`의 `Health`, `auth.py`의 `UserId` · `Enabled` · `Me` · `Ok`(`admin.py`도 같은 `Ok`를 import), `admin.py`의 `Accounts`, `prices.py`의 `PricesAvailable | PricesUnavailable`, `projects.py`의 `DemoCircuit`(그리고 `backend/projects/models.py`의 `ProjectSummary` · `Project`), `quotes.py`의 `Approval` · `Quote` · `ApprovedCase`, `conversations.py`의 `Thread` · `ThreadSummary` · `ThreadDetail`(메시지·최신 run 참조) · `Run`(`result`는 `BrowserResult`) · `RoleLabel` · `DemoQuestion`(`resume`은 `DemoResume`), `profile.py`의 `ProfileFact` · `Deleted`. `response_model`은 선언하지 않은 칸을 응답에서 지우므로 칸을 더하면 모델과 `frontend/src/api/*.ts`를 함께 고친다(`tests/api/test_openapi.py`). run · 재개(SSE)는 `SSE_RESPONSE`로 `text/event-stream`과 이벤트 설명만 적고, 업로드는 본문을 직접 읽으므로 `UPLOAD_BODY`로 multipart `file` · `name` 칸을 OpenAPI에만 적는다.

`projects.py`의 모든 경로에 로그인 세션이 필요하다. 데모 POST는 `{demo_id, name}`, PATCH는 `{name}`만 받고, 다른 필드·공백 이름·200자 초과 이름·알 수 없는 데모는 공통 422로 거절한다. POST/PATCH/DELETE는 `auth.check_origin`을 적용한다. POST는 201 상세, GET 목록은 메타데이터 배열, GET/PATCH 상세는 `connections` 포함, DELETE는 204를 반환한다. 없는 프로젝트·다른 사용자 프로젝트는 같은 메시지의 공통 404다. DB 오류·DB 설정 누락은 안전한 503이다.

업로드 POST는 multipart `file` 하나와 `name` 하나만 받는다. 인증·Origin 확인 후 파일 5 MiB+1, 이름 800 bytes, 전체 multipart 5 MiB+16 KiB를 상한으로 메모리 수신하며 disk spool을 막는다. `UploadFile.read`는 최대 5 MiB+1로 한 번만 호출한다. 정규화 성공 직후 원본 버퍼를 닫고 finally에서도 모든 업로드를 닫는다. 파일명은 경로로 사용하지 않으며 저장소에는 connections/source_sha256/parser_version만 전달한다. 크기 초과는 공통 413 `PAYLOAD_TOO_LARGE`, UTF-8·넷리스트·multipart 형식 오류는 공통 400 `VALIDATION_ERROR`(`backend/errors.py`의 기본 코드)이며 두 오류 모두 request_id/X-Request-ID를 포함한다.

UploadFile의 filename은 비어 있지 않아야 하며 양끝 공백을 제외해 대소문자 구분 없이 `.net`으로 끝나야 한다. 잘못된 확장자/빈 filename은 읽기 전에 공통 400으로 거절하고 파일을 닫는다. filename 자체가 없으면 multipart text field로 처리되어 허용된 text field 수를 초과하므로 공통 400으로 거절한다.

`/api/me/memory`는 로그인 사용자의 사실 3칸(SPEC 8.5)이다. 사용자 id는 세션에서만 온다. GET은 사실 목록(최대 3개, 각 `{kind, value, text, version, updated_at, source}`)이고 선택 `q`(1~500자)를 주면 의미가 가까운 순이다(색인이 꺼져 있으면 순위 없이). PATCH는 `affiliation`·`job_role`·`mounting_preference` 중 바꿀 칸만 받아 바뀐 뒤 목록을 돌려준다. 다른 이름(사용자 id 포함)·틀린 값은 공통 422다. DELETE는 전부, `?kind=`면 한 칸을 지우고 204다. PATCH·DELETE는 Origin을 확인한다(403). 응답은 `Cache-Control: no-store`다. 분석 저장소(`THREADS_ENABLED=1`)가 없으면 503, 색인이 켜진 채 임베딩이 실패하면 PATCH는 503이고 아무 칸도 바뀌지 않는다.

`GET /judge/roles`는 인증된 사용자에게 `backend/judge/rules/roles.yaml` 정본의 역할 `code`·`name`만 코드 순서로 돌려준다. 규칙의 판정식·내부 상태는 노출하지 않는다.

`GET/POST /projects/{project_id}/threads`, `POST /threads/{thread_id}/runs`, `GET /runs/{run_id}`, `POST /runs/{run_id}/resume`는 소유권을 확인한다. 변경 요청은 Origin을 확인한다(다르면 403 `ORIGIN_MISMATCH`). 복수 역할 인터럽트는 응답의 `role_choices` 중 하나를 `role`로 다시 보내며, 그 밖의 역할은 422다. run과 resume은 SSE로 `run_started`, `status`, 마지막 상태를 보내며 마지막 상태는 짧은 DB 장애를 제한적으로 재시도해 저장한 뒤 전송한다. 연결이 끊어져도 실행은 계속되고 GET은 재실행하지 않는다. 실행 중 또는 추가 정보 대기 중인 thread가 있는 프로젝트 삭제는 409다. 프로젝트 삭제는 public의 프로젝트·회로·대화·run·메시지·승인·견적과 같은 UUID의 분석 thread·회로·checkpoint·분석 메시지·승인 기록·분석 사건을 한 트랜잭션에서 지운다(11-09 결정, `memory_service.delete_analysis_threads`). 분석 서비스 표가 없는 DB면 public 행만 지운다.

run과 resume은 사용자 분석 서비스(`app.state.conversations`, `THREADS_ENABLED=1`)를 거친다. 서비스가 없으면 스트림을 열기 전에 공통 503, 오늘(UTC) 예약 토큰이 사용자 200,000 또는 서비스 전체 2,000,000에 닿았으면 스트림 · run 행 전에 공통 429(`LIMIT_EXCEEDED`)다(`Conversations.admission`). 실행 도중 상한에 닿으면 그 호출 전에 멈추고 `failed` frame의 `error`가 429 코드다. 첫 run이 React 대화와 같은 UUID의 분석 회로·thread를 프로젝트의 `connections`와 `target_ref`로 만들고, 같은 대화에서 다른 `target_ref`를 보내면 run을 만들기 전에 409(`대상 부품을 바꾸려면 새 대화를 시작하세요.`), 회로에 없는 부품이면 422다. run은 `Conversations.message`, resume은 그 thread의 현재 버전으로 `Conversations.resume`을 스레드 풀에서 부르므로 사용자 사실 찾기, 실행·하루 예산과 호출 간격, 영속 체크포인트, Langfuse 사건 기록이 같이 적용된다. 완료·거절 frame에는 그 질문으로 찾은 사용자 사실(`profile_hints`, 칸·값·문장 최대 3개)이 붙고, `public.runs`에는 저장하지 않아 `GET /api/runs/{id}`의 결과에서는 빈 목록이다. 결과는 그래프 상태에서 `public_state`로 공개 값만 골라 `public.runs`·`public.messages`에 저장한 뒤 보낸다. 진행 frame은 시작 때 `status` 하나다. `failed` frame에는 `error: {code, message}`가 붙는다. 코드는 공통 오류와 같은 표(ADR 0019, `backend/errors.py`: 409 `CONDITION_PENDING` · `CONFLICT`, 429 `LIMIT_EXCEEDED` · `RATE_LIMITED`, 422 `VALIDATION_ERROR`, 502 `UPSTREAM_ERROR`(LLM · 임베딩 공급자 장애), 503 `UNAVAILABLE`(분석 전 DB 장애 포함), 504 `TIMEOUT`, 그 밖 `INTERNAL_ERROR`)이고 문구는 분석 서비스의 공개 문구다. 실패마다 `request_id` · `run_id` · `code` · `status` 로그 한 줄을 남긴다(4xx는 INFO, 5xx와 예상 못 한 예외는 traceback까지, 예상 못 한 예외의 문구는 고정 문장).

알려진 한계:
- 키 없는 데모(`DEMO_REPLAY=1`, SPEC 7절): `GET /api/demo-questions`는 기록한 데모 질문을 `DemoQuestion`(id · 종류 · 회로 이름 · React 데모 회로 id · 대상 · 질문 · 사용 조건 · 기록한 재개 값)으로만 돌려준다. 기록한 답 · 판정 · 넷리스트 경로는 응답 모델이 지운다. 재생 모드가 아니면 404(화면이 버튼을 숨김), 기록 파일이 없으면 503이다. run은 스트림을 열기 전에 `ensure_thread`에 질문 · 사용 조건을 넘겨, 기록한 회로 · 대상 · 질문 · 조건이 아니면 공통 422(문구에 데모 질문 목록)로 끝난다. 같은 대화의 두 번째 질문과 기록과 다른 재개 답은 스트림 뒤 `failed` 422다.
- React 승인(`POST /messages/{message_id}/approvals`)은 public 승인·견적·승인 사례만 저장한다. 분석 서비스의 옛 승인 기록(`sojafit_agent.approvals`)은 새로 쓰는 경로가 없다. 승인 사례는 장기 기억이 아니며(11-09) 새 분석에 넘기지 않는다.
- 재개 입력 400/409/422/429 뒤 실제 checkpoint가 계속 조건 입력을 기다리면 run과 입력 폼을 `requires_input`으로 복원한다. 그래프 도중 시스템 오류로 실패하거나 checkpoint가 더 이상 입력을 기다리지 않으면 `failed`이며, 자동 재실행하지 않는다. 이때는 상태 확인 또는 새 대화를 안내한다.

`POST /messages/{message_id}/approvals`는 소유자의 완료된 성공 판정 후보를 품번과 사용자가 확인한 verdict의 쌍으로 한 번만 승인한다(두 번째 승인 · 승인할 수 없는 판정은 409 `ALREADY_APPROVED`). `POST /approvals/{approval_id}/quotes`는 수량만 받아 승인 snapshot을 복사하고 가격·재고는 저장하지 않는다. 프로젝트 견적 목록과 사용자 승인 사례 목록·확인 삭제를 제공하며 모든 변경 요청은 Origin을 확인한다.

`GET /api/demo-circuits`는 단일 catalog의 15종을 `{id, name, schematic}`으로 반환한다. `q`(ID·이름 부분 검색), `offset`(0 이상), `limit`(1~100)을 선택적으로 받고 5분 public cache header를 보낸다. 모든 `schematic`은 `image_url`, `original_url`, `source_repo`, `source_commit`, `license`, `license_evidence_url`, `attribution`이다. 원본/배포 hash·로컬 파일 경로는 응답에서 제외한다. 로그인 세션이 없으면 401이다. CDN의 `source_commit`은 저장소 맥락이고 파일의 동일 바이트 출처를 증명하지 않는다.
저장 기록 조회: `GET /api/threads/{thread_id}`는 기존 세션 소유권을 확인하고 메시지 최대 50개(선택 limit 1~100)를 id 오름차순으로 반환한다. `before_message_id`(양의 BIGINT)를 주면 이전 페이지이며 `next_before_message_id`로 이어 읽는다. 소유 프로젝트 id·첫 질문 제목·저장된 대상(null 가능)·최신 run/message 참조만 포함하고 그래프·checkpoint·Store·조건 원문은 노출하지 않는다. 목록 GET의 기존 배열에 title/created_at/last_activity_at/latest_run_id/status를 더하며 전체 목록 형태는 유지한다(목록 cursor는 후속). 목록·상세·run GET은 no-store다. 대화 repository는 SELECT만 수행하며 기존 인증의 last_seen_at 갱신은 유지한다. 없는 자원과 타 사용자 자원은 같은 404, 잘못된 페이지/UUID는 422, 저장소 오류는 503이다. 새 경로와 목록 DTO의 조장 SPEC 반영 요청은 프로젝트·이전 대화 탐색 작업서에 기록한다.

## 일반 Google 로그인 후속
- callback은 연결된 활성 일반 사용자·관리자에 세션을 발급하고 미연결 신원은 `/login?google=finish`로 보낸다. 숨긴 `/api/auth/google/onboarding`은 마스킹 이메일만, POST `google/signup`은 명시적 동의, POST `google/link`는 기존 비밀번호 재확인 후 연결한다. 두 POST는 Origin을 확인한다. 관리자 최초 연결은 기존 pending HTML·운영자 CLI만 쓴다. 상세는 [작업서](../../docs/specs/google-user-login.md).
