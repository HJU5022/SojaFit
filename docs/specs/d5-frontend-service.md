# D5 프론트엔드 서비스 기능 계약

- 상태: 현행(기능 계약). 화면 구현 설명은 2026-11-16 새 화면 교체에 맞춰 고침
- 기준일: 2026-11-12(기능 계약), 화면 부분 2026-11-16
- 기준 커밋: 6707002(기능 계약), `76fadcb4`(화면 부분)
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 2절 흐름, 4절 API 표, 8.4절 견적 승인). 화면이 쓰는 기능 계약의 상세
- 관련 문서: [frontend/FRONTEND.md](../../frontend/FRONTEND.md) · [frontend/src/SRC.md](../../frontend/src/SRC.md)(현재 화면 구조), [frontend-screen-redesign.md](frontend-screen-redesign.md)(11-16 교체 전 화면, 이력), [project-conversation-navigation.md](project-conversation-navigation.md), [api-error-contract.md](api-error-contract.md), [circuit-context-diagram.md](circuit-context-diagram.md), [login-auth.md](login-auth.md)

## Why

- 대상: 로그인한 SojaFit 사용자.
- 상황: 공개 데모 회로를 고르거나 KiCad 넷리스트를 올려 대상 부품을 정하고, D5(멀티 에이전트 그래프)에 질문해 데이터시트 근거와 후보 판정을 확인한다.
- 문제: 인증·프로젝트·대화·승인 흐름을 브라우저에서 이어 쓸 화면이 없으면 질문에서 승인 견적까지 한 흐름으로 쓸 수 없다.
- 지표: AC-01~AC-10의 사용자 흐름·저장 경계·권한 조건을 만족하는 통합 수용 시험 통과율 100%.

## Goal

- React + Vite + TypeScript 화면을 FastAPI와 같은 출처로 제공하고, D5의 실행·판정 규칙을 바꾸지 않은 채 인증부터 프로젝트 생성, 질문·재개, 결과 확인, 승인 견적까지 연결한다.
- 업로드 원본·가격/재고 응답은 영속 저장소에 0건이다. 로그인한 사용자의 프로젝트·대화는 새로고침과 재로그인 뒤에도 복구된다.
- 범위 밖: D4 실행 UI, D5 판단 규칙 변경, 외부 웹 조회 에이전트, 주문·결제, 원본 회로도/PCB 업로드, 프로젝트 공유, 실시간 공동 편집, 모바일 전용 앱.

## What

### Happy Path

1. 같은 출처에서 로그인하고 새로고침해도 서버 세션으로 인증 상태가 복원된다.
2. 프로젝트를 만든다. 업로드(UTF-8 KiCad `.net`, 최대 5 MiB)가 기본이다. 공개 데모 회로 5종 중 하나로 만드는 길은 서버가 데모 모드(`DEMO_MODE=1`)일 때만 열린다.
3. 업로드는 구조와 부품·넷 존재를 확인해 정규화한다. 처리가 끝나면 성공·실패와 관계없이 원본 참조를 버리고, 원본 바이트는 D5 입력·실행 상태·checkpoint로 전달하지 않는다. 저장하는 것은 정규화 JSON, 원본 SHA-256, 파서 버전(`kicad-export-v2`), 생성 시각이다.
4. 프로젝트를 고르고 질문하면 서버가 같은 thread에서 D5를 실행하고 허용된 진행 상태(그래프 단계)를 SSE로 보낸다. 대상 부품은 직접 지정하지 않아도 되고, 서버가 질문 · 회로로 정하지 못하면 고를 부품을 묻는다(SPEC 8.9).
5. 판정에 회로 값이 더 필요하면 thread/checkpoint에 interrupt를 두고 `requires_input`으로 끝낸다. 사용자의 입력은 같은 run을 재개한다.
6. 가격·재고가 필요하면 `/api/prices`를 별도 호출하고 화면 메모리에만 둔다. 판정을 사람이 승인한 뒤에만 견적과 승인 사례를 저장한다.

### Edge Case

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 비로그인 또는 만료 세션 | 401이면 로그인 화면으로 보내고 토큰을 브라우저 저장소에 두지 않는다 |
| EC-02 | 업로드가 5 MiB 초과 또는 UTF-8·넷리스트 형식 오류 | 413 또는 400으로 거절하고 프로젝트를 만들지 않으며 원본을 보존하지 않는다 |
| EC-03 | 같은 thread에서 실행 중 중복 질문 | 409(`run_in_progress`). 화면은 중복 실행을 막고 기존 run 상태만 조회한다. 실행 중에도 질문 입력창 · 넷리스트 파일 고르기 · 새 검토는 쓸 수 있고, 보내기 · 데모 질문 · 대화 삭제 · 대상 부품 바꾸기만 막는다(보내기 옆에 "답변이 끝나면 보낼 수 있습니다", 11-16) |
| EC-04 | SSE 연결 끊김 | `GET /api/runs/{run_id}`로 저장 상태를 조회하고 질문을 자동 재전송하지 않는다 |
| EC-05 | 다른 사용자의 프로젝트·thread·승인 자료 접근 | 404로 거절하고 내용을 반환하지 않는다 |
| EC-06 | 승인 전 견적 저장 요청 | 409로 거절하고 견적·승인 사례를 저장하지 않는다 |
| EC-07 | 프로젝트 삭제 | 한 트랜잭션으로 회로, thread, 메시지, run, 견적, 연결된 승인 사례와 같은 UUID 분석 thread의 checkpoint·메시지·승인 기록·분석 사건을 삭제한다. 사용자 사실 기억(Store)은 프로젝트에 딸리지 않아 남는다. 실행 중 대화가 있으면 409 |
| EC-08 | 가격 API 미가용 | 가격 없이 판정은 유지한다. 가격 응답은 DB·메시지·checkpoint·견적·승인 사례에 기록하지 않는다 |

## How

| 항목 | 구현 | 근거 |
|---|---|---|
| 프론트 스택 | React 19 + Vite 8 + TypeScript 7. 라우터 · 서버 상태 라이브러리 없이 `ui.tsx`의 `navigate()` · `useLocation()`과 `api.ts`의 `api()` · `streamRun()`(`fetch` 스트림 SSE)만 쓴다. 경로 표는 `App.tsx` 한 곳 | `frontend/package.json`, `frontend/src/SRC.md` |
| 개발 서버 | Vite가 `/api`를 `http://localhost:8000`으로 프록시 | `frontend/vite.config.ts` |
| 배포 | `Dockerfile` 다단계: `frontend-build`(Node)에서 빌드한 `dist`를 FastAPI 이미지에 복사. FastAPI는 `/api/*`, `/health`, Google 콜백을 먼저 처리하고 나머지 화면 경로는 React 진입 파일로 보낸다 | `Dockerfile`, `backend/web/app.py` |
| 인증 | HttpOnly 서버 세션 쿠키와 같은 출처 정책. 상세 [login-auth.md](login-auth.md) | `backend/auth.py` |
| 프로젝트 API | 목록·생성(데모 모드만)·업로드·상세·이름 변경·삭제, `GET /api/demo-circuits`(데모 모드만). 업로드는 multipart `.net`이며 사용자 파일명·경로를 서버 경로로 쓰지 않는다 | `backend/api/projects.py` |
| 대화 API | thread 생성·목록·상세·삭제, `POST /api/threads/{id}/runs`, `GET /api/runs/{id}`, `POST /api/runs/{id}/recover`, `POST /api/runs/{id}/resume`, `GET /api/judge/roles`(역할 이름), `GET /api/demo-questions`(키 없는 데모 재생 모드만). 한 thread에 동시 run 하나. run·재개는 `THREADS_ENABLED=1`의 분석 서비스(`backend/conversations/memory_service.py`)를 같은 UUID thread로 거치고, 대상 부품은 고정되며 서비스가 없으면 503. 표·요청 모델·오류는 SPEC 4절이 정본 | `backend/api/conversations.py` |
| SSE 이벤트 | `run_started`, `status`, `requires_input`, `completed`, `refused`, `failed`. 토큰 단위 출력은 보내지 않는다. 이벤트별 칸은 SPEC 4절 표 | `backend/api/conversations.py` |
| 진행 단계 | 서버가 보내는 값은 `입력 확인`(시작), `판정`(추가 정보 대기), `완료`(완료·거절, 거절은 상태 `refused`), `오류`(상태 `failed`) | `backend/api/conversations.py` `STAGES` |
| 브라우저 결과 DTO | 허용 칸 `answer, status, stage, question_type, evidence, judgement, price_parts, refusal, interrupt, request_id, profile_hints, web_search_unavailable`(#28). Plan·TaskReport 전문, 내부 추론, 서버 경로, 내부 예외, prompt·업로드 본문·모델 원문은 반환하지 않는다 | `backend/conversations/dto.py` `BrowserResult` |
| 승인·견적·사례 API | `POST /api/messages/{id}/approvals`, `POST /api/approvals/{id}/quotes`, `GET /api/projects/{id}/quotes`, `GET /api/approved-cases`, `DELETE /api/approved-cases/{id}`. 승인·견적은 판정 메시지의 immutable snapshot을 참조 | `backend/api/quotes.py` |
| 승인 차단·안내 | 후보의 필수 입력이 `missing`이거나 required check가 `unverified`면 승인 API와 화면 모두 막는다. 승인 버튼 바로 아래에 입력할 회로 조건(한글 항목명·형식 예시)과 확인할 필수 사양(이름/코드·미확인 이유·요구값/기록된 시험 조건·필요한 문서 근거)을 구분한다. 회로값/원래 부품/후보 문서의 확인 대상을 서버 이유에 맞춰 안내하고 보완 후 새 검토를 요청한다. 기본 접힘인 native details의 제목에는 입력/사양 항목 수를 표시하고 펼치면 상세 안내를 확인한다. 접기/펼치기는 질문 초안·승인 상태를 유지하며 API 쓰기를 하지 않는다. 중복 missing을 제거하고 모르는 코드의 값·단위를 추정하지 않는다. 안내 영역을 버튼의 aria-describedby에 연결하며 정상·조건부 미확인 후보의 기존 동작은 유지한다 | `backend/services/quote.py`(서버 차단). 화면의 승인 버튼 아래 안내 · 접기는 새 화면에 아직 없다(`frontend/src/Candidate.tsx`는 문서에 없는 값을 보이기만 하고, 「필수 조건 미확인 승인 안내」는 11-16 통합에서 미뤘다) |
| 견적 복원·저장 | 프로젝트 견적 GET으로 이력을 복원하고 현재 승인 id의 견적만 선택한다. 프로젝트 전체 이력에는 이전 승인 견적도 남는다. 선택/재진입은 GET만 수행하며 별도 ‘새 견적 작성→견적 저장’에서만 POST한다. 이력 조회 실패 때 저장을 막고 재조회한다. 저장 응답이 끊기면 GET으로 결과를 확인한다 | `frontend/src/Candidate.tsx`, `frontend/src/approval.ts` |
| 가격 경계 | 승인 응답의 식별 품번과 선택/작성 수량으로 사용자가 조회를 눌렀을 때만 `/api/prices?parts=...&quantity=...`를 부른다. quantity는 선택값이며 1~100000 정수다. backend/judge/pricing.py가 동일 품번·같은 통화의 적용 구간을 선택하고 Decimal 곱셈한 estimate(quantity/break_quantity/unit_price/total/currency)를 응답에만 둔다. 다른 품번·혼합 통화·모호한 가격은 estimate=null이며 추정하지 않는다. 수량 변경/포커스/재연결 때 자동 외부 조회는 없다. 가격·재고·estimate는 영속 저장하지 않고 견적 POST에는 수량만 보낸다. 세금·배송비·환율 미포함을 밝힌다 | `frontend/src/Candidate.tsx`, `frontend/src/display.ts`, `backend/api/prices.py`, `backend/judge/pricing.py` |
| 권한 | 사용자 소유 행은 `user_id` 또는 프로젝트 관계로 검증한다. 관리자 계정 관리 권한은 프로젝트·대화 열람 권한을 주지 않는다 | `backend/conversations/repository.py` |
| 판정 이름 | `동일품`, `사양 동등`, `역할상 충분`, `불충족`, `문서로 확인 안 됨`. 모든 판정에 "같은 동작은 보장하지 않는다"를 표시 | [SPEC.md](../../SPEC.md) 3절 |
| 오류 | `{error:{code,message,request_id}}`와 `X-Request-ID`([api-error-contract.md](api-error-contract.md)). 오류 화면은 `error.message`와 `request_id`만 보인다 | `backend/errors.py` |

## AC

| # | Given - When - Then | 테스트 |
|---|---|---|
| AC-01 | 활성 사용자가 로그인 뒤 새로고침 - 서버 세션으로 상태 복원, 토큰은 브라우저 저장소에 없음 | (화면 시험 없음: 옛 시험은 11-16 교체로 지워짐) |
| AC-02 | 데모 모드의 로그인 사용자가 데모 회로 5종 중 하나로 생성 - 소유 사용자와 회로 출처가 연결된 프로젝트, 부품 후보 확인 | `tests/api/test_projects.py`, `frontend/tests/demo.spec.ts`(브라우저) |
| AC-03 | UTF-8 `.net`(5 MiB 이하) 업로드 - 성공 시 정규화 JSON·원본 SHA-256·파서 버전·시각만 저장, 원본 바이트·본문·경로는 저장소에 없음. 5 MiB 초과 413, 형식 오류 400, 실패 시 프로젝트 없음 | `tests/projects/test_netlist.py`, `tests/projects/test_project_repository.py`, `tests/api/test_projects.py` |
| AC-04 | 프로젝트·대상 선택 뒤 질문 - 같은 thread에서 D5 실행, 허용된 SSE 단계와 마지막 `completed` 또는 `refused`를 저장 뒤 전송. 중복 run 409, 내부 상태 전문·토큰 스트림 비노출 | `tests/api/test_conversations.py`, `tests/api/test_threads.py::test_react_run_and_resume_go_through_analysis_service` |
| AC-05 | 판정이 추가 회로 값 요구 - interrupt 저장, 값 제출 시 같은 thread/checkpoint에서 재개, 최종 상태 조회 가능 | `tests/api/test_threads.py::test_checkpoint_history_and_interrupt_survive_runtime_reconnection`, `::test_planned_judge_subgraph_resumes_from_postgres_without_approved_cases` |
| AC-06 | 판정 완료 - 후보마다 판정 5종 중 하나와 문서명·쪽·표/행 또는 절 근거, 고지 문구. 안전 DTO의 `checks`는 후보 상세 표로 보이고 값이 없으면 `확인 안 됨`. 필수 입력 `missing` 또는 필수 check `unverified` 후보는 화면·API 모두 승인 불가 | `tests/api/test_quotes.py` |
| AC-07 | `price_parts` 있는 완료 결과 - 가격 패널이 `/api/prices`를 별도 호출, 응답은 화면 메모리에만 | `frontend/tests/display.test.ts`, `tests/api/test_prices.py` |
| AC-08 | 승인 전 견적 요청 409. 승인 뒤 승인 snapshot을 참조하는 견적·승인 사례 저장. 견적 화면은 수량만 저장 | `tests/api/test_quotes.py`, `frontend/tests/approval.test.ts`, `frontend/tests/demo.spec.ts`(브라우저) |
| AC-09 | 사용자 A의 프로젝트·thread·메시지·승인 자료를 B 또는 관리자가 요청 - 404, 본문 조회 불가 | `tests/api/test_conversations.py`, `tests/api/test_threads.py::test_other_user_cannot_access_thread_or_resume` |
| AC-10 | 프로젝트 삭제 - 회로·thread·메시지·run·견적·연결 승인 사례와 같은 UUID 분석 기록이 한 트랜잭션에서 삭제되고 이후 조회 불가 | `tests/api/test_deletion.py::test_project_delete_removes_its_react_and_analysis_records_only` |

## 구현 상태

| AC | 상태 |
|---|---|
| AC-01~AC-10 | 서버 쪽 테스트 파일이 있다. 화면 시험은 새 화면 것만 남았고([frontend/tests/TESTS.md](../../frontend/tests/TESTS.md)) AC-01 · AC-06은 화면 단위 시험이 없다. 파일 지정은 주제별 대응이며 AC 문장과 시험 함수의 일치는 대조하지 않았다. DB·checkpoint를 쓰는 사례는 전용 시험 DB가 없으면 skip된다 |

## 한계

- 업로드 요청의 128 KiB 본문 한도 예외(5 MiB 업로드는 별도 한도)는 `SPEC.md` 4절이 정한다. 이 문서는 업로드 한도만 적는다.
- 가격·재고 응답이 로그에 남지 않는지는 이 문서 작성 중 대조하지 않았다(미확인).
- SPEC 4절·8.4절·8.5절이 이 기능의 API·승인·사례 계약을 싣고 있다. "React·Vite 화면은 FastAPI와 같은 출처로 배포한다"는 제목의 ADR은 `docs/adr/`에 없다. 화면 통일 결정은 `docs/adr/0018-react-작업대-하나로-화면을-통일하고-옛-workspace-화면을-지운다.md`다.
