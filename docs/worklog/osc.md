# 오세창 작업 기록

## 2026-11-13 PR #114 후속 문서 교정

- 한 일: 사전 등록과 작업 기록의 문맥상 붙은 표현, 인젝션 검토 자료의 반복 설명, 프런트 안내 문장을 교정했다. 실행 이름과 실험 입력·원시 결과·측정 수치는 보존했다.
- 바꾼 파일: `docs/research/injection-case-review-packet.md`, `evals/guides/preregister.md`, `docs/worklog/osc.md`, `docs/worklog/sth.md`, `frontend/e2e/E2E.md`, `frontend/src/SRC.md`.
- 실행한 명령과 결과: `git diff --check`로 공백 오류를 검사하고, 변경 전후의 공백 제외 문자열·인용 문자열·Markdown 링크 대상을 대조했다. 문서 교정이므로 코드 실행이나 평가 재측정은 하지 않았다.
- 확인 못 한 것: 원본 자료의 재배포 조건과 팀원별 AI 도구 사용 기록.
- 다음 할 일: PR #114에서 교정된 문장을 검토한다.

## 2026-11-13 회로 원본 이미지 복구

- 한 일: `attiny85_dev` 원본 README가 참조하는 조립 사진 5개와 커넥터·회로도·PCB·렌더 이미지 5개를 기록된 원본 커밋에서 복구했다.
- 바꾼 파일: `data/circuits/collected/samples/attiny85_dev/original/assets/`, `data/circuits/CIRCUITS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`.
- 확인: README의 이미지 10개와 PDF 1개에 대해 상대경로와 원본 커밋의 Git blob SHA를 대조했다. 최초 다운로드에서 큰 조립 사진 5개가 빈 파일로 생성돼 원본에서 다시 받아 대조했다.

## 2026-11-13 원본 README 참조 자료 복구

- 한 일: c09 인증 마크 PNG와 attiny85_dev 참고 회로도 PDF를 각각 기록된 원본 커밋의 README 상대경로에 복구하고 수집 안내·저장소 트리를 갱신했다.
- 확인: 복구 당시에는 사용자 요청에 따라 별도 검증을 실행하지 않았다. 이후 위 항목의 README 상대경로와 Git blob SHA 대조로 파일 무결성을 확인했다.
- 다음 할 일: 원본 파일의 재배포 조건을 확인한다.

## 2026-11-13 문서 교정 진행

- 한 일: 현재 main `b5f050d` 기준 OSC에서 사전 등록, 프런트 안내, 인젝션 검토 자료와 작업 기록의 지정된 띄어쓰기 구간을 교정하고 수집 원본의 누락 참조를 안내하고 평가 보고서에 근거한 Codex 비교 기록을 추가했다.
- 바꾼 파일: `data/circuits/CIRCUITS.md`, `docs/deliverables/ai_tools_log.md`, `docs/research/injection-case-review-packet.md`, `docs/worklog/osc.md`, `docs/worklog/sth.md`, `evals/guides/preregister.md`, `frontend/e2e/E2E.md`, `frontend/src/SRC.md`.
- 확인: `git diff --check`, 기존 문구 및 목록 항목을 대조했다. 모델 호출·평가 재측정은 하지 않았다.
- 남은 일: 지정 구간 밖 과거 기록의 무공백 문장, 원본 파일의 재배포 조건과 팀원별 AI 도구 사용 기록을 확인한다. 기존 로컬 OSC 작업은 사용자 요청으로 버리고 main으로 갱신했다.

## 2026-11-12 피드백 정정 선별 PR

- 한 일: 검증한 채용 역할·후보 그룹 50건을 현재 시장 근거로 연결하고 기존 237건 조사는 과거 이력으로 구분했다. 여정 맵에서는 현재 승인·견적 저장 흐름과 미구현 기능을 구분했으며, 대체재 비교표에 판정 기준과 Codex의 역할·정답 초안 작성 경위를 기록했다.
- 평가셋: 승인된 범위에서 v3 50문항에 `judges: ["심태현", "하정운"]`을 추가하고 `FROZEN.json` 해시와 안내 문서를 갱신했다. 문항·정답·기준은 바꾸지 않았다.
- 인젝션: 본실측03 110건과 스모크08 2건을 분리했다. 사람 판정 정본은 본실측03 채점 사본의 20건 O·90건 pending이며, 어시스턴트 잠정 분류와 사람 판정을 구분했다. 원시 JSONL의 `human_review`는 측정 당시 미채점 상태를 유지했다.
- 재시작·계정 분리: 격리 PostgreSQL과 실제 HTTP 서버 프로세스로 A의 입력 대기 상태를 서버 재시작 뒤 재개하고, B가 A의 run을 조회·재개하지 못하는 것을 확인했다. 재현 그래프는 합성 대역이므로 실제 멀티에이전트·배포 환경 검증으로 확대하지 않는다.
- 주요 변경 파일: `EVAL_REPORT.md`, `SOJAFIT.md`, `docs/TOPIC.md`, `docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md`, `docs/evaluation-prep.md`, `docs/research/`, `evals/`, `tests/api/test_http_restart.py`, `tests/multi_agent/test_docs_agent.py`.
- 검증: 정정된 본실측03 SHA-256을 테스트 고정값과 맞췄다. 동결셋·사람 판정 가져오기·인젝션 저장본 집중 검사는 11 passed, HTTP 재시작 재현은 종료 코드 0이었다. 전체 검사에서 최신 `main`의 저장소 구조 검사 5건과 OpenAPI의 `SNAPSHOT` 미정의 수집 오류를 제외하면 1,831 passed·12 failed·3 errors·159 skipped였다. 남은 실패·오류는 이번 PR에서 수정하지 않은 API 인증 기대값과 Supervisor V0 동결 해시 불일치다.
- 제외: 배포 코드와 원격 `main` 완전 일치, Langfuse 스크린샷, KiCad·프런트 빌드 재측정 자료는 이 PR에 포함하지 않는다. 청크 SHA/DB 행 수와 v4h 동일 평가셋 원시 비교도 이번 범위가 아니다.

## 2026-11-09 PR #73 선반영 통합

- 목적: PR #73이 `main`에 먼저 병합된 상태를 가정하고, OSC의 React/D5 작업대와 #73의 사용자별 회로·thread·승인 기억·합성 데모 경로를 함께 유지한다. 원격 push·PR 생성·배포는 하지 않는다.
- 통합: 기존 프론트 변경을 `84e69fa`로 보존한 뒤 최신 `origin/main`을 `320538e`로 병합했다. 이어서 PR #73 head를 통합해 `/workspace`·`/api/circuits|threads|memories`와 React SPA·`/api/projects|runs|quotes`를 함께 등록하고 SPA는 모든 API 뒤에 mount했다. 겹치던 `GET /api/threads/{id}`는 #73 경로를 단일 소유자로 유지했다.
- 구조 충돌 수정: #73의 `backend/conversations.py`가 기존 `backend/conversations/` 패키지에 가려지는 문제를 `backend/conversations/memory_service.py`로 이동해 해결하고 main·Compose setup CLI·테스트·트리 문서를 함께 바꿨다. `tests/graph/test_netlist.py`와 기존 `tests/projects/test_netlist.py`의 pytest 모듈명 충돌은 전자를 `test_agent_netlist.py`로 바꿔 해결했다.
- DB·문서: 양쪽 초기화 SQL은 실제 파일명 정렬 순서대로 문서화했다. 루트 `SPEC.md`와 v4h RAG 정본은 최신 main 내용을 유지하고 OSC 구현 설명은 하위 작업서와 이 기록에 남겼다.
- 검증: API·SPA·thread 집중 검사는 `88 passed, 33 skipped`, 프론트는 `16 files / 87 tests passed`, production build 성공, 전체 backend는 `1074 passed, 113 skipped in 26.32s`였다. FastAPI method/path 중복 검사 결과는 `[]`였다.
- 추가 검증: `uv lock --check`, `docker compose config --quiet`, 전체 diff whitespace와 FastAPI method/path 중복 0건을 확인했다. 일반 로컬 clone을 Docker gitleaks로 검사해 `414 commits scanned`, `no leaks found`였다. 현재 main 및 PR #73 선병합 가상 main과의 `git merge-tree --write-tree --quiet`는 모두 exit 0이었다.
- 확인 못 한 것: 건너뛴 PostgreSQL·외부 모델·공유 DB·실제 배포와 Langfuse 전송은 확인하지 않았다.
- 다음 할 일: 최종 diff와 Git 상태를 확인한 뒤, 사용자 승인 시에만 push·PR 생성을 진행한다.

## 2026-11-09 PR #71 현재 구현·평가 근거 계약 보완

- 목적: 최신 main의 v4h 청킹·Voyage 검색 구현과 과거 v1 측정, 저장소 밖 lab 실행을 문서에서 서로 다른 근거로 구분하고 PR #71의 구현 현황 문서에 함께 반영한다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/EVALS.md`, `data/DATA.md`, `SPEC.md`, `backend/mcp_skill/MCP_SKILL.md`, `docs/experiments/embedding-voyage-candidates.md`, `docs/experiments/corpus-storage-budget.md`, `docs/research/embedding-candidate-investigation.md`, `docs/research/model-licenses.md`, 이 파일.
- 바꾼 내용: 평가 보고서 상단을 현재 코드 계약과 2026-11-01 측정 스냅샷으로 나누고, 임베딩 선택 완료 상태와 v1 manifest provenance를 명시했다. SPEC의 v3 50문항 수치는 저장소 밖 lab 결정 근거이며 공식 G5 결과가 아니라고 표시하고, 과거 STH 브랜치 안내를 현재 MCP 의존성·시험 경계로 바꿨다.
- 작업 경계: 동결 평가셋과 원시 결과는 수정하지 않았고 API 호출·DB 적재·배포는 하지 않았다.
- 검증: `uv lock --check`, `docker compose config --quiet`, `git diff --check`, 충돌 표식 검색을 통과했다. `PYTHONUTF8=1 uv run --frozen pytest -q -p no:cacheprovider`는 `885 passed, 58 skipped`였다.

## 2026-11-09 회로 프로젝트와 대상 선택 (Task 6)

- 범위: 승인된 `docs/specs/d5-frontend-service.md` AC-02/03/09의 프로젝트 화면만 기존 owner API에 연결했다. 프로젝트/대상 참조 선택에서 끝내며 D5 실행·대화·승인·견적·후보 가격 공급·React KiCad 파싱은 추가하지 않는다. 원격 쓰기·실제 서비스 호출은 없다.
- TDD RED: 신규 API 경계·실제 Workbench 상호작용 시험을 먼저 작성한 후 집중 5개 파일 실행에서 `16 failed, 3 passed in 5.76s`. 새 프로젝트 UI가 없어 label/선택/오류를 찾지 못했고, 기존 공통 fetch는 DELETE의 204 빈 본문을 JSON 파싱해 실패했다. 최소 구현 후 집중 `19 passed in 2.06s`.
- 중간 확인: 데모 option이 로드되기 전에 disabled select를 바꾸던 시험을 실제 option 대기로 보정했다. jsdom의 합성 FileList를 native validity가 보지 못해 업로드 시험은 실제 form submit 이벤트를 명시한다. required/파일 guard는 production에 유지한다. 오래된 삭제 callback의 Router query updater가 이전 params를 참조하는 문제는 현재 query signature를 사용해 해결했다.
- 추가 RED/GREEN: logout 직후 소유 Query 캐시가 다음 세션에 남지 않아야 한다는 StrictMode 시험이 `1 failed, 5 passed in 1.78s`. gcTime=0의 다음 timer를 기다리지 않고 Workbench 이탈 시 프로젝트·데모 쿼리를 즉시 remove/cancel한다. 보완 후 App/Workbench 집중 `11 passed in 1.76s`.
- API/상태: `['projects']`, `['project', id]`, `['demo-circuits']`를 사용하고 생성·이름 변경·삭제 후 해당 목록/상세를 invalidate한다. 삭제는 확인/취소 후 owner DELETE 204이며 해당 상세 쿼리를 취소·제거한다. `projectId`와 `targetRef`만 URL query에 두고, 서버 connections의 데모 components 또는 업로드 parts와 nets에서 요약/참조를 표시한다. 파일은 React state/Query mutation cache에 보관하지 않으며 업로드 성공/실패 finally에서 input을 비운다.
- 경합/경계: 이전 상세·생성·삭제 응답이 새 프로젝트 선택을 덮지 않는 시험, 대상 선택·전환 시 초기화, 없는/타 사용자 404·400/413 request ID 표시, rename/list/detail 갱신, 명시적 delete 취소·확인, 브라우저 비저장, 기존 auth/admin/price 회귀를 포함한다.
- 바꾼 파일: frontend/src/api/projects.ts·client.ts(+시험), ProjectSidebar/CircuitSetup/CircuitSummary(+각 시험), WorkbenchPage(+시험), styles.css, test/projects.tsx, 기존 App/Login/Admin 시험의 QueryClient wrapper·현재 DTO 대역, frontend 폴더 문서, SOJAFIT 신규 파일 8줄, 이 기록. backend·의존성·동결 평가셋은 수정하지 않았다.
- 최종 확인: `npm run test:run` → `10 files, 40 passed in 2.64s`; `npm run build` → TypeScript/Vite 성공(82 modules, 142ms). `PYTHONUTF8=1 uv run pytest -q tests/repo/test_repo_layout.py` → `5 passed in 0.35s`; diff whitespace 통과. 신규 코드의 localStorage/sessionStorage/IndexedDB/persist/FileReader/readAs/파일 text 호출이 없음을 대조했다. 빌드 dist/node_modules/tsbuildinfo와 작업 report는 무시 경로이며 커밋하지 않는다.
- 미검증/검토: live API·실제 DB·브라우저 E2E/시각 확인·배포·RAG 평가셋 재측정은 범위 밖이다. backend DTO/라우터/기존 API 시험 소스의 계약이 명확해 backend API 시험은 다시 실행하지 않았다. SPEC 정본은 OSC 소유 규칙대로 직접 바꾸지 않았으며 승인 spec AC-02/03/09의 화면 반영을 조장에게 요청한다. 권장 400줄을 넘는 UI/회귀 변경은 단일 프로젝트 선택 기능과 비동기/소유권 경계를 함께 검토하도록 요청된 한 커밋으로 유지한다. 최종 staged 20개 파일은 이 범위뿐이며 Docker gitleaks stdin(`--redact --no-banner --log-level warn`) 스캔에서 비밀값 0건, staged whitespace 통과를 확인했다. 요청된 `feat(web): 회로 프로젝트와 대상 선택`으로 로컬 커밋한다.

### Task 6 Fix Round 1

- 범위: 프로젝트 create/upload/rename/delete의 늦은 401이 재로그인한 세션을 종료하는 Important만 수정한다. backend·auth 정책·영속 저장은 바꾸지 않는다.
- RED: production 수정 전 `npm run test:run -- src/App.test.tsx src/components/ProjectSidebar.test.tsx --reporter=dot` → `2 files failed; 10 failed, 10 passed in 2.36s`. 실제 StrictMode App/AuthProvider/Workbench의 logout→relogin→old 401 네 종류 모두 새 세션이 로그인 화면으로 바뀌었고, unmount/switch 후 성공 응답 여섯 종류는 불필요한 GET이 1회 추가됐다.
- 변경: projects API mutation 4종에 signal 전달, CircuitSetup/ProjectActions effect별 AbortController·unmount abort·각 await 뒤 guard. 종료한 컴포넌트의 invalidate/selection/error/busy 업데이트를 막고 업로드 input finally reset은 유지한다. 정상 delete는 상세 cancel/remove·목록 invalidate 이후 선택을 지워 자체 unmount 전에 필요한 처리를 마친다.
- 회귀: create/upload/rename/delete 모두 새 세션·새 프로젝트·D2 선택 유지와 읽기 요청 수 불변/abort를 확인한다. 같은 QueryClient에 다시 연 작업대의 이전 성공 응답과 rename/delete editor 전환도 검증한다. test/projects 렌더러는 QueryClient 재사용을 허용하도록 보정했다.
- GREEN: focused project/workbench/AuthProvider 6개 파일 `33 passed in 2.76s`; 전체 `npm run test:run` → `10 files, 50 passed in 3.07s`; `npm run build` → TypeScript/Vite 성공(82 modules, 144ms). whitespace 검사를 통과했다. 실제 서비스/DB/browser E2E는 실행하지 않았다. 브라우저 abort가 이미 전달된 서버 mutation의 rollback을 보장하지는 않는다.
- 변경 파일: frontend/src/api/projects.ts, CircuitSetup.tsx, ProjectSidebar.tsx, App.test.tsx, ProjectSidebar.test.tsx, test/projects.tsx 및 이 기록. report의 Fix Round 1에 정확한 RED/GREEN 명령·출력을 남긴다. 신규 파일·의존성·backend·정본 문서 변경은 없다. staged 7개 파일의 whitespace 통과, Docker gitleaks stdin redacted 스캔 exit 0(비밀값 0건), 생성물 미포함을 확인했다. 별도의 fix(web) 로컬 커밋으로 남긴다.

### Task 6 Fix Round 2

- 범위: 프로젝트 전환 때 CircuitSetup이 유지되어 create/upload의 늦은 성공이 목록을 invalidate하는 지적만 수정한다.
- RED: production 전에 demo/upload deferred 전환 시험 2건 추가. `npm run test:run -- src/components/CircuitSetup.test.tsx src/pages/WorkbenchPage.test.tsx src/App.test.tsx --reporter=dot` → `1 file failed, 2 passed; 2 failed, 23 passed in 2.69s`. 다른 프로젝트/D2를 선택한 뒤 이전 성공 응답이 추가 `/api/projects` GET을 일으켜 실패했다.
- 변경: 기존 선택 세대를 CircuitSetup의 React key로 연결하는 1줄과 주석. 선택 세대 전환 시 기존 component cleanup이 mutation을 abort하고 이전 guard가 늦은 응답·invalidate·auto-selection을 무시한다. 새 폼은 빈 사용 가능 상태로 시작하며 오래된 upload finally는 이전 input만 비운다. 정상 생성 auto-selection은 유지한다.
- GREEN: 프로젝트 전환 직후(target 변경 전) abort도 별도로 확인한 최종 focused 3개 파일 `25 passed in 2.40s`; 전체 `npm run test:run` → `10 files, 52 passed in 3.04s`; build → TypeScript/Vite 성공(82 modules, 123ms). 기존 성공/400/413 input reset과 auth/admin/price/재로그인 경합 회귀도 유지된다.
- 파일/한계: WorkbenchPage.tsx, CircuitSetup.test.tsx와 이 기록. backend·API·영속 저장·신규 파일·의존성 변경 없음. 실제 서비스/DB/browser E2E는 미실행이고 브라우저 abort는 이미 전달된 서버 변경의 rollback을 보장하지 않는다. 최종 staged whitespace/비밀값/생성물을 점검한 뒤 별도 fix(web) 커밋을 남긴다.

## 2026-11-09 인증·관리자·화면 메모리 가격 연결 (Task 3)

- Fix Round 1: StrictMode의 이전 복원 401이 새 로그인을 해제하는 순서와, 관리자 PATCH 대기 중 로그아웃/경로 이동 후 후속 목록 GET이 실행되는 순서를 deferred-response 테스트로 먼저 재현했다. focused RED는 `3 failed, 5 passed`; effect별 AbortController·API signal 전달·응답/JSON 파싱 뒤 abort 검사·관리자 후속 GET/상태 변경 guard로 수정 후 `8 passed`. 전체 프런트 `24 passed in 2.01s`, build(TypeScript+Vite 78 modules), `git diff --check` 통과. non-JSON 오류 본문 Minor는 요청대로 최종 검토에 보류했다. backend·화면 범위·저장 경계는 변경하지 않았다.
- 한 일: 기존 API만 연결했다. HttpOnly 세션을 `/api/auth/me`로 복원하고 로그인 성공 후 me에서 role을 확인한다. 보호 경로와 역할별 관리자 탐색, 마스킹된 계정 목록·활성 상태 변경, 설정된 Google 링크·기존 callback 실패 안내, 로그아웃을 연결했다. API 401은 메모리 인증 상태를 비우고 로그인으로 보낸다.
- 가격 경계: 후보 품번을 받는 PricePanel은 열 때만 no-store 조회하며 React component memory에만 결과를 둔다. 닫기·품번 변경·화면 이탈 시 결과와 요청을 버린다. 같은 패널을 다시 열어도 새로 조회한다. 기존 Mouser nullable 응답을 표시하되 가격을 만들거나 숫자 비교를 하지 않는다. 작업대에는 아직 후보 공급 기능이 없어 빈 상태만 둔다.
- 바꾼 파일: `frontend/src/api/`·`auth/`·`pages/`·`components/` 신규 소스/동작 테스트, `test/network.ts`, `App.tsx`·`App.test.tsx`·`styles.css`·`SRC.md`, 신규 파일만 적은 `SOJAFIT.md` 트리, 이 기록. 서버 계약·백엔드 소스·동결 평가셋은 변경하지 않았다.
- RED: 최초 `npm run test:run`은 `7 files failed; 9 failed, 1 passed`와 아직 없는 모듈 import 4 suite 실패. 세션 만료·nullable 회귀는 `2 failed, 6 passed`, no-store 경계는 `1 failed, 2 passed`, 기존 Google callback 실패 안내는 `1 failed, 2 passed`를 관측하고 각각 최소 수정했다. 네트워크 fetch만 대체하고 실제 페이지·Provider·Router·PricePanel을 실행한다.
- 실행한 명령과 실제 결과: 최종 `npm run test:run` → `7 files, 21 passed in 1.91s`; `npm run build` → TypeScript·Vite 성공, 78 modules; `uv run pytest -q tests/api/test_auth.py tests/api/test_prices.py tests/api/test_frontend.py` → `57 passed, 21 skipped in 14.25s`; `uv run pytest -q tests/repo/test_repo_layout.py` → `5 passed in 0.25s`; `git diff --check` 통과.
- 확인 못 한 것: TEST_AUTH_DATABASE_URL 등이 필요한 기존 DB 통합 21건은 생략됐다. 실제 DB/계정·OAuth 왕복, 실제 Mouser, 브라우저 E2E/시각 확인·Docker 배포·모델 평가 재측정은 수행하지 않았다. 검색·판정 변경이나 평가 점수 개선을 주장하지 않는다.
- 다음 할 일: 후속 작업이 실제 후보 목록을 PricePanel에 공급한다. OSC의 주요 문서 소유 규칙에 따라 SPEC은 직접 수정하지 않고, 조장에게 기존 `docs/specs/d5-frontend-service.md`의 AC-01/AC-07 및 인증·가격 경계 문단을 SPEC 정본에 반영하도록 요청한다. 400줄을 넘는 핵심 diff는 인증·권한·가격의 안전 경계를 검증하는 테스트와 구조 문서가 대부분이며 요청된 하나의 연결 작업/커밋으로 유지한다.

## 2026-11-09 D5 같은 출처 React 기반 (Task 2)

- 한 일: React·Vite·TypeScript 셸과 `/login`, `/app`, `/admin/users` 경로, `/` 로그인 이동, Query provider·Router·API 개발 프록시를 추가했다. 인증·프로젝트·실행·승인 화면 동작은 후속 범위다. Node 24 다단계 빌드의 정적 산출물만 Python runtime에 복사한다.
- 서버 경계: API 등록 뒤 response-aware SPA middleware를 연결한다. 비 API GET/HEAD의 downstream 404만 index(미빌드이면 기존 로그인)로 바꾸고, API·health·assets·다른 메서드·리다이렉트는 보존한다. 화면에도 기존 요청 ID를 유지한다.
- 사용자 승인 예외: 표준 Vite가 요구하는 `frontend/` 도구 루트와 기존 design.md·정적 제공 어댑터를 함께 두는 `backend/web`에만 한 종류 규칙 예외를 둔다. 하위 폴더는 제외하지 않고 API 업무 로직은 어댑터에 넣지 않는다. 단순 GET catchall이 Google 끝 `/`와 POST 404를 바꾸는 실제 회귀가 확인되어 사용자가 response-aware 방식으로 대체를 승인했다.
- 바꾼 파일: `frontend/`의 package/lock·HTML·Vite/TypeScript 설정·폴더 설명·React 진입점/셸/스타일/단위 테스트, `backend/web/app.py`, `backend/main.py`, `Dockerfile`, `.gitignore`, `backend/web/WEB.md`, `backend/BACKEND.md`, `tests/api/test_frontend.py`, `tests/api/test_auth.py`, `tests/api/test_health.py`, `tests/api/API.md`, `tests/repo/test_repo_layout.py`, `SOJAFIT.md` 신규 파일 트리·설명 표 행, 이 작업 기록.
- RED: 최초 frontend API 테스트 `2 failed, 3 passed`; helper stub 경계 확장 `9 failed, 4 passed`; React null stub `4 failed`; 루트 진입 추가 `1 failed, 4 passed`. 단순 catchall의 추가 인증 검사 `3 failed, 49 passed, 21 skipped`와 HEAD/메서드/health 검사 `4 failed, 14 passed`를 관측한 뒤 middleware로 고쳤다.
- 실행한 명령과 실제 결과: `uv run pytest -q tests/api/test_frontend.py tests/api/test_health.py tests/api/test_auth.py` → `56 passed, 21 skipped in 13.97s`; `uv run pytest -q tests/repo/test_repo_layout.py` → `5 passed in 0.29s`; `cd frontend`, `npm run test:run` → 1 파일·5건 통과; `npm run build` → TypeScript·Vite 성공, 68 modules, `dist/index.html` 생성; 전체 `uv run pytest -q` → `935 passed, 58 skipped in 22.07s`.
- 확인 방법: 테스트는 실제 FastAPI/TestClient, 임시 dist 파일, 실제 React·MemoryRouter를 사용한다. `/` 404의 과거 health 가정은 API 404 검사로 이동했고 legacy 폼 assertion은 미빌드 fallback으로 격리했다. 화면 소스는 로컬 system font와 반응형·키보드 초점 스타일을 사용한다. npm audit는 의존성 설치 시 0 vulnerabilities였다.
- 확인 못 한 것: 격리 DB·별도 외부 환경이 필요한 58건은 생략됐다. Docker 이미지 자체의 빌드/실행, 실제 OAuth 왕복, 브라우저 E2E·스크린샷, 모델 평가·라이브 API는 실행하지 않았다. 검색·판정 모델을 바꾸지 않아 평가 점수 향상을 주장하지 않는다.
- 다음 할 일: 후속 Task에서 실제 로그인·세션 복구·관리자 기능을 셸에 연결한다. SPEC 변경이 필요하면 OSC에서 주요 문서를 수정하지 않고 조장에게 승인 계약 반영을 요청한다. push·배포하지 않는다.

## 2026-11-09 D5 프론트엔드 구현 계획

- 한 일: 승인된 D5 프론트엔드 설계를 기능 계약, React 기반, 프로젝트·업로드, D5 영속 실행, 작업대, 승인·견적·기억, 통합 검증의 6개 PR과 13개 테스트 우선 작업으로 나눴다.
- 계획 원칙: D5 내부 판단은 바꾸지 않고 안전한 API DTO만 추가한다. 가격·재고와 업로드 원본은 저장하지 않으며, 외부 웹 조회는 제외한다. 각 작업은 실패 테스트 → 최소 구현 → 통과 확인 → 목적별 커밋 순서다.
- 바꾼 파일: `docs/superpowers/plans/2026-11-09-d5-frontend-service.md`, `docs/superpowers/SUPERPOWERS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`.
- 확인 못 한 것: 실제 구현·npm 의존성 설치·DB migration·라이브 D5·브라우저 E2E는 실행하지 않았다.
- 다음 할 일: 실행 방식을 선택한 뒤 PR 1의 기능 계약부터 시작한다.

## 2026-11-09 D5 프론트엔드 서비스 설계

- 한 일: React + Vite + TypeScript 작업대에서 D5 멀티 에이전트를 그대로 사용하기 위한 전체 구조를 사용자와 합의했다. 데모·업로드 회로, 사용자별 프로젝트, D5 실행·인터럽트 재개, 근거·판정·가격, 승인·견적·사례 기억의 경계를 설계했다.
- 핵심 결정: D5만 서비스에 연결하고 D4는 평가용으로 둔다. 업로드 원본은 정규화 뒤 폐기하고 정규화 회로만 저장한다. 가격·재고는 그래프와 DB에 저장하지 않는다. 외부 웹 조회는 현재 D5에 없으므로 이번 범위에서 제외한다.
- 바꾼 파일: `docs/superpowers/specs/2026-11-09-d5-frontend-service-design.md`, `docs/superpowers/SUPERPOWERS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`.
- 확인 방법: 설계 문서의 목적·범위·API·저장·오류·테스트·PR 경계를 대조하고, 새 파일을 `SOJAFIT.md` 트리와 폴더 설명에 반영한다. 코드와 런타임은 변경하지 않는다.
- 확인 못 한 것: 실제 React 빌드, D5 서비스 API, DB migration, E2E는 구현 계획 승인 뒤 각 PR에서 검증한다.
- 다음 할 일: 사용자가 설계서를 검토한 뒤, 승인되면 `writing-plans` 절차로 구현 계획을 작성한다.

## 2026-11-09 main → OSC 병합

- 한 일: 최신 `origin/main`을 로컬 `OSC`에 merge하고, 충돌 7개 문서는 main 내용을 기준으로 두면서 기존 Supervisor Prompt V0 계약·평가·결과·트리 항목을 함께 보존했다. 이어 원격 `origin/OSC`에 남아 있던 닫힌 #67의 두 커밋(`feat(api)`, 구현 상태 문서)도 병합해 로컬 OSC가 원격 OSC보다 뒤처지지 않게 했다.
- 충돌 파일: `SOJAFIT.md`, `backend/graph/GRAPH.md`, `backend/prompts/PROMPTS.md`, `docs/specs/SPECS.md`, `docs/worklog/osc.md`, `evals/guides/preregister.md`, `evals/runners/RUNNERS.md`.
- 실행한 명령과 결과: 첫 병합에서 `uv lock --check` 통과, V0·저장소 구조 대상 테스트 `38 passed`, 전체 테스트 `911 passed, 58 skipped`, 충돌 해소분 기준 `git diff origin/main --check` 통과. #67 두 커밋 병합 뒤 API·V0·구조 대상 테스트 `56 passed`, 전체 테스트 `918 passed, 58 skipped`를 다시 확인했다. merge 전체의 `git diff --cached --check`는 main에서 들어온 `backend/rag/spec_lookup.py`의 EOF 빈 줄 1건을 알렸고 해당 main 내용은 바꾸지 않았다.
- 확인 못 한 것: PR 상태와 원격 push 결과는 이번 범위에서 확인하지 않았다. 팀 규칙에 따라 push하지 않았다.
- 다음 할 일: 필요하면 조장 승인 후 로컬 merge commit을 `origin/OSC`에 push하고 다음 PR의 기준으로 사용한다.

## 2026-11-06 Supervisor Prompt V0 Langfuse 가져오기

- 한 일: 완료된 V0 13문항과 세 후보 결과를 모델 재호출 없이 Langfuse Dataset `sojafit-supervisor-v0`과 Experiment 3개로 가져왔다. 입력에는 정답과 case id를 넣지 않고 정답은 Dataset expected output으로 분리했다. 형식·네 필드·의미·전체 일치의 결정적 점수 7개를 문항마다 기록했다.
- 바꾼 파일: `docs/specs/supervisor-v0-langfuse-import.md`, `evals/runners/import_supervisor_prompt_v0_langfuse.py`, `tests/evals/test_import_supervisor_prompt_v0_langfuse.py`, `evals/results/supervisor/2026-11-06-prompt-v0-v1/langfuse_import.json`과 폴더 색인·트리.
- 실행한 명령과 결과: API 없는 `plan`에서 Dataset 13개·Experiment 3개·점수 273개를 확인했고 전용 테스트 7건과 저장소 구조 테스트를 통과했다. 첫 외부 시도에서 `.env`의 trailing slash와 Langfuse 5.0.4의 OTEL endpoint 문자열 결합 때문에 Dataset만 저장되고 Experiment는 0건이었다. `.env`는 바꾸지 않고 실행기에서 base URL을 정규화한 뒤 서버의 Experiment 0건을 확인하고 다시 실행했다.
- 외부 재조회: Dataset 13개, Experiment 3개, 각 Experiment 13개 항목을 확인했다. 점수 이름별 39개씩 총 273개이며 합계는 schema 39, question type 38, required evidence 37, next action 35, reason code 38, semantic 34, exact 33으로 로컬 결과 합계와 일치했다. `imported_existing_result=true`를 기록했으며 원래 live trace로 가장하지 않는다. 모델 호출은 0회다.
- 확인 못 한 것: in-app browser에는 Langfuse 로그인 세션이 없어 UI 표를 직접 보지는 못했다. 인증된 API로 Dataset·Experiment·trace별 score를 재조회했다.
- 다음 할 일: Langfuse에 로그인한 팀원이 세 Experiment 비교 화면을 확인하고 필요하면 제출용 화면을 캡처한다. 프롬프트 인젝션 방어 설계는 별도 작업으로 진행한다.

## 2026-11-06 Supervisor Prompt V0 live 평가 사전 준비

- 목적·비교 조건: V0 상태 표본 13건에서 Luna/Azure, Haiku/Google, Jev/TypeSafe가 같은 네 필드 의미 계약을 지키는지 비교한다. 기존 v2 70문항 결과는 V0 점수로 재사용하지 않는다. 기대와 판정은 `evals/guides/preregister.md` #37에 결과 확인 전에 기록했다.
- 코드 보완: 본 실행이 성공한 smoke의 exact model/provider만 사용하도록 회귀 테스트를 RED로 확인한 뒤 고쳤고, smoke 요청에도 `--provider`를 필수로 두었다. 관련 API 없는 테스트 40건과 후속 선택 테스트 35건이 통과했다. 커밋은 `2834f96`, `ac82964`다.
- 현재 catalog: 세 모델 모두 ZDR catalog에 노출됐다. 적용 provider는 기존 성공 근거와 현재 endpoint를 대조해 Luna `Azure`, Haiku `Google`, Jev `TypeSafe`로 정했다. 단가는 Chat 두 모델 input/output `$0.0000001`/`$0.0000005` per token, Jev input `$0.000000042`, output `$0`다.
- 예산·시간·중단: Chat 모델별 smoke `$0.005`·3 raw calls·180초, 본 실행 `$0.060`·39 raw calls·1,800초. Jev smoke 승인 `$0.005`·1 call·180초, 본 실행 승인 `$0.010`·13 calls·1,800초. 전체 명령 상한 `$0.145`, 최악 98 raw calls다. smoke 실패, hash/model/provider 불일치, 상한 도달, 반복 provider 오류에서 중단하고 자동 증액·재실행하지 않는다. Jev USD는 기술적 cap이 아니라 승인 기록이다.
- 실행 명령·보존: API 없는 두 plan 뒤 `--confirm-live`·exact provider로 smoke 세 건, 본 실행 세 건, hash가 같은 13건만 통합 집계한다. 결과 예정 경로는 `evals/results/supervisor/2026-11-06-prompt-v0-v1/`이다. 루트 `.env`에서는 `OPENROUTER_API_KEY`만 현재 process에 주입하고 값은 출력·기록하지 않는다.
- 실행 결과: 사용자가 총 상한 `$0.145`를 승인한 뒤 exact provider smoke와 본 실행을 수행했다. Luna/Azure와 Haiku/Google은 13/13 schema·semantic·exact match, Jev/TypeSafe는 schema 13/13이나 semantic 8/13·exact 7/13이었다. Jev의 의미 오류 5건은 모두 `next_action` 상태 라우팅이었다. 실제 raw calls는 42회, provider 보고 usage cost 합계는 smoke 포함 `$0.007086424`다. 결과·실행 조건·출처 hash는 `evals/results/supervisor/2026-11-06-prompt-v0-v1/`에 보존했고 `.gitattributes`로 해당 JSON 원시 바이트를 유지한다.
- 해석: V0 기준에서는 Luna와 Haiku가 사전 기대를 충족했고 Jev는 semantic 12/13·exact 10/13 기대에 미달했다. 이 소형 13건은 prompt 프로토타입 검증이며 운영 모델 확정이나 기존 70문항 결과 대체 근거로 사용하지 않는다. 추가 유료 재실행이나 prompt·gold 수정은 하지 않았다.

## 2026-11-05 Supervisor Prompt V0 프로토타입

- 한 일: 확정본이 아닌 Supervisor 전용 V0 prompt와 입력·출력·상태 라우팅 계약을 만들었다. 별도 13건 상태 표본에서 `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5`, `typesafe/jev-1.14`를 같은 네 필드로 비교할 수 있도록 Chat·Decisions 독립 실행기와 API 없는 통합 집계기를 추가했다. 현재 `build_graph()`에는 연결하지 않았다.
- 계약: 입력은 `user_request`, `current_state`, `external_material`로 분리하고 정답·case id를 모델에 보내지 않는다. 출력은 `question_type`, `required_evidence`, `next_action`, `reason_code` 네 필드다. 외부 자료는 지시가 아닌 데이터로 취급하며 상세 프롬프트 인젝션 방어는 다음 작업으로 남겼다.
- 실행 안전: `plan`은 네트워크를 사용하지 않는다. Chat live 경로는 호출·시간·예약 비용 상한과 최대 3회 형식 시도를 사용한다. Jev는 호출·시간 상한을 집행하지만 비용 미보고 API라 USD는 승인 기록과 `Not Reported`를 구분한다. 구현 중 live 모델 호출과 유료 평가를 하지 않았다.
- 바꾼 파일: `backend/graph/supervisor.py`, `backend/prompts/supervisor_v0.md`, `evals/samples/supervisor_prompt_v0*`, V0 공통·Chat·Jev·통합 집계 실행기와 테스트, 설계·구현 계획·평가 절차 및 폴더 색인.
- 검증: 각 단계에서 모듈 부재 RED를 확인한 뒤 구현했다. V0 선택 테스트, 인접 LLM 서비스 테스트, 저장소 구조 검사를 API 없이 실행했다. `ruff`는 개발 의존성에 없어 실행하지 못했다. 전체 테스트의 기존 Windows 기본 인코딩 실패 `tests/evals/test_run_graph.py::test_main_writes_metrics_only_result_file`은 이 작업 범위에서 수정하지 않았다.
- 다음 할 일: 별도 승인 뒤 exact model/provider 1건 smoke와 13건을 실행하고, dataset·의미 계약 hash와 case 집합이 같은 결과만 비교한다. 그 뒤 프롬프트 인젝션 방어를 별도 설계한다.

> **2026-11-02 항목의 문서 전용 반영 범위**: 아래 2026-11-02 항목은 `OSC` 로컬에서 수행했던 탐색·구현·검증의 역사 기록이다. 해당 항목에는 임베딩 후보 관련 문서만 포함하며, 여기에 언급된 평가기 코드, 테스트, 입력 표본, 원시 JSON과 모델 캐시는 포함하지 않는다. 따라서 해당 항목의 테스트 통과·재현 성공 문구는 현재 `main`의 상태를 증명하지 않으며, 현재 저장소에서는 문서 정합성만 검증한다.

## 2026-11-08 FastAPI 공통 오류 응답 규약

- 한 일: 최신 `main` 기준 `backend/main.py`에 서버 생성 UUID 요청 식별자와 `X-Request-ID` 헤더를 추가하고, HTTP·검증·처리되지 않은 예외를 `error.code/message/request_id` JSON 구조로 통일했다. 기존 `/api/prices`와 Mouser 호출 경로는 유지했다.
- 바꾼 파일: `backend/main.py`, `backend/BACKEND.md`, `tests/api/test_health.py`, `tests/api/test_prices.py`, `tests/api/API.md`, `docs/specs/api-error-contract.md`, `docs/specs/SPECS.md`, `SOJAFIT.md`, 이 작업 기록.
- 확인 방법: 테스트를 먼저 추가해 기존 코드에서 실패를 확인한 뒤 구현했다. 최종 `uv run pytest -q -p no:cacheprovider`는 `770 passed, 43 skipped`, `uv lock --check`, `docker compose config --quiet`, `git diff --check`는 통과했다.
- 미확인: `TEST_AUTH_DATABASE_URL`·`TEST_DATABASE_URL`이 없어 건너뛴 통합 시험 43건, 실제 배포 응답과 외부 로그 저장소의 요청 ID 연결. DB·외부 API·배포는 변경하지 않았다.

## 2026-11-08 현재 구현 기준 문서 정합성 점검

- 팀장 요청에 따라 현재 상태를 설명하는 문서를 실제 저장소 코드와 대조했다. 과거 ADR·평가 결과·제출 주제서·작업 기록은 당시 증거로 보존하고, 현재 상태 문서에서만 구현·목표·외부 운영 이력을 구분했다.
- `README.md`, `SPEC.md`, `SOJAFIT.md`, `docs/GATES.md`에 현재 서비스 API 범위(로그인·Google 관리자·관리자 계정·가격 조회·공통 오류)와 미구현 범위(질문·회로·대화·견적 승인/저장·Store·영속 체크포인트·업무 화면)를 반영했다.
- RAG·데이터 문서에서 현재 `voyage-4-large` 1024차원, `rerank-3`, `008` 이후 차원 없는 `halfvec`을 기준으로 정리했다. 최신 main 재대조에서 v1 manifest·운영 스냅샷 52,244청크와 11-08 저장소 밖 v4h 전체 실행 51,967카드를 구분하고, 새 clone 재현과 에이전트 길 재측정은 별도 증거가 필요하다고 바로잡았다.
- Google 관리자 로그인 문서의 코드·SQL·CLI·합성 테스트 구현 항목은 완료로, 현재 Cloud Run·Secret Manager·운영 DB·실계정 상태는 재검증이 필요한 항목으로 분리했다. MCP 그래프 통합 문서는 구현 전 계획과 현재 `StdioMcpRetriever` 구현을 구분했다.
- 검증: 저장소 구조 검사 `5 passed`, 전체 테스트 `770 passed, 43 skipped`, `uv lock --check`, `docker compose config --quiet`, `git diff --check` 통과. 운영 배포·DB 상태는 이번 작업에서 조회하지 않았다.

## 2026-11-05 GCP Google OAuth 로그 보호 실측

- 한 일: GCP `sojafit` 프로젝트에 조회 전용 `Logs Viewer` 권한을 받은 뒤, Cloud Run 시험 태그에서 실제 Google 관리자 로그인·승인 대기·로그아웃을 수행했던 2026-11-05 20:20~22:05 KST 구간의 `sojafit-api` 로그를 읽기 전용으로 확인했다.
- 바꾼 파일: 개인 작업 기록 `docs/worklog/osc.md`만 갱신했다. GCP 설정, 애플리케이션 코드, DB, 주요 문서와 원격 브랜치는 변경하지 않았다.
- 실행한 조회와 실제 결과: 대상 구간의 일반 로그 158건이 조회됐다. Uvicorn의 Google callback 로그는 7건이며 모두 쿼리 문자열 없이 `GET /api/auth/google/callback` 경로와 `303` 상태만 남았다. Cloud Run 요청 로그에서 callback URL을 찾은 결과는 0건으로, callback 요청 로그 제외 설정이 실제 로그인에서도 작동했다. 같은 범위의 `code=`, access·refresh·ID token, client secret, 이메일 형식, 비밀번호·세션·Authorization·Cookie 관련 문자열 검색은 각각 0건이었다. 로그인·로그아웃·세션 확인과 서버 기동 같은 일반 로그는 유지됐다.
- 확인 못 한 것: 이번 결과는 지정한 시간대와 `sojafit-api`의 `textPayload`, `jsonPayload.message`, `httpRequest.requestUrl`에서 확인한 실측이다. 다른 프로젝트·로그 버킷·기간과 향후 코드 변경까지 민감정보가 절대 남지 않는다는 보장은 아니다. 시험 리비전은 0% 트래픽이며 운영 트래픽 전환은 검증하거나 수행하지 않았다.
- 다음 할 일: 실제 로그인이 새 OAuth 비밀로 성공했으므로, 운영 전환과 별개로 이전 OAuth 클라이언트 비밀 및 Secret Manager의 이전 버전을 폐기할지 정확한 대상을 다시 확인하고 별도 승인을 받아 처리한다. 운영 트래픽 전환은 최신 main 차이·환경변수·DB 연결·롤백 경로 검토 후 별도로 승인받는다.

## 2026-11-05 Google 로그인 작업과 최신 main 통합

- 통합 전 로컬 작업: 기존 ID·PW 계정의 로그인, `/api/auth/me`의 일반 사용자 역할, 로그아웃 뒤 `401`을 직접 확인했다. 별도 Google 관리자 로그인 구현과 `010_google_admin_login.sql`도 로컬·격리 DB에서 검증했지만 커밋하지 않은 상태였다.
- 최신 기준 반영: `origin/main`의 Google 관리자 로그인 커밋 `b71837e`를 포함한 `2e2db38`을 `STH`에 병합했다. main 구현은 `010_google_auth.sql`, `Authlib`·`joserfc`, 승인 대기·연결·회수 흐름과 더 넓은 테스트를 사용하므로 충돌한 실행 코드와 DB 계약은 main을 정본으로 삼았다.
- 보존 경계: 통합 전 추적·미추적 변경 전체는 `pre-main-sync-google-auth-20261105-195159` stash에 남겼다. 중복된 로컬 SQL과 현재 상황보다 오래된 GCP 미착수 기록은 활성 트리에 합치지 않았고, ERD만 main의 실제 표 이름에 맞춰 갱신했다.
- 외부 상태: main의 `docs/worklog/sth.md`에는 팀 Supabase 적용, 실제 Google 계정 로컬 시험, Cloud Run 0% 시험 리비전의 승인 대기 화면 확인이 기록돼 있다. 이번 병합 작업에서는 그 외부 상태를 다시 실행하거나 독립 검증하지 않았다.
- 미수행: 원격 `STH` push와 운영 트래픽 변경은 하지 않았다.

## 2026-11-05 팀 DB 적재 현황과 Google 관리자 로그인 확인

- 실제 로그인: Cloud Run의 0% 시험 태그에서 Google 계정 검증 후 승인 대기 요청이 생성됐다. 확인된 요청을 기존 활성 관리자 `user_id=5`에 연결하고 같은 Google 계정으로 다시 로그인해 `/api/auth/me`가 `{"user_id":5,"role":"admin"}`을 반환하는 것을 확인했다. 이메일·요청 번호·Google 식별자·쿠키·토큰 원문은 기록하지 않는다.
- DB 적재 스냅샷: 2026-11-05 20:37:12 KST에 팀 Supabase의 `public` 스키마를 읽기 전용으로 집계했다. `source_documents` 1,360건(`DATASHEET`), `document_chunks` 52,244건, `chunk_embeddings` 52,244건(`voyage-4-large`), `chunk_embedding_bits` 52,244건을 확인했다.
- 인증 스냅샷: `users` 5건(활성 관리자 3명·활성 일반 사용자 2명), `auth_sessions` 5건(활성 1·만료 4), `auth_login_attempts` 0건, `auth_google_identities` 1건, `auth_google_pending` 0건, `auth_google_states` 2건(활성 0·만료 2)이었다. 임시 상태와 세션 수는 이후 로그인·로그아웃·만료 정리에 따라 바뀐다.
- 동일 브라우저 재검증: 자동화 탭과 일반 탭을 섞은 최초 시험에서 남은 관리자 ID 5의 세션 1건을 사용자 승인 후 삭제하고, 일반 Chrome 탭 하나에서 Google 로그인→`/api/auth/me`의 `user_id=5`, `role=admin` 확인→로그아웃→브라우저 `401`과 DB 세션 0건을 확인했다. Google 연결은 1건 유지됐다. 따라서 최초 잔존 세션은 혼합 브라우저 환경의 시험 한계이며 동일 탭에서는 재현되지 않았다.
- 기존 인증 회귀: Google 계정이 연결된 관리자 ID 5가 기존 ID·PW로 다시 로그인했고 `/api/auth/me`가 같은 ID와 `role=admin`을 반환했다. DB에는 활성 세션 1건, 로그인 실패 행 0건, Google 연결 1건이 확인됐다. 비밀번호 원문은 사용자가 직접 입력했고 작업 기록이나 도구 출력에 남기지 않았다.
- 연결 철회·복구: ID·PW 로그인 세션의 정상 로그아웃과 DB 세션 0건을 확인한 뒤 사용자 승인으로 관리자 ID 5의 Google 연결 1건을 철회했다. 사용자 계정·관리자 역할·비밀번호 해시는 유지됐다. 같은 Google 계정의 다음 로그인은 세션을 만들지 않고 승인 대기 1건만 생성했으며, 이메일 일치와 대상 상태를 다시 확인해 관리자 ID 5에 재승인했다. 최종 DB 상태는 Google 연결 1건·활성 승인 대기 0건·세션 0건이며 재승인만으로 세션을 자동 생성하지 않았다.
- 미적재: 업무 테이블 11개와 LangGraph Checkpoint·Store 표는 조회 당시 `public` 스키마에 없었다. 업무 SQL은 `db/manual/004_create_business_tables.sql.draft` 초안 상태다.
- 기록 위치: 테이블별 전체 수치·조회 범위·변동 주의사항은 `db/DB.md`의 "팀 Supabase 적재 현황 스냅샷"에 기록했다. 실제 행 값과 비밀정보는 조회·기록하지 않았다.

## 2026-11-02 Voyage 후보 변경 독립 감사 후속

- PR #27 피드백 반영: 2026-11-02 확장 평가기·표본·원시 JSON이 저장소에 없으므로 해당 Recall@5·MRR·지연 상세값과 실행 불가능한 실제 PDF·Voyage 재현 명령을 제출용 `EVAL_REPORT.md`에서 제거하고, 로컬 탐색 이력은 `docs/embedding-candidate-investigation.md`에만 남겼다.
- 후보 정합성: 실제 PDF smoke 성공 기록은 Voyage 4 Nano를 포함한 5종으로 맞췄다. 캐시·원시 결과는 저장소 밖이므로 준비 상태를 `통과`가 아닌 `로컬 기록(저장소 밖)`으로 낮추고, 현재 main의 평가기는 확장 자산이 빠진 `일부 통과`로 표시했다.
- 범위: PR #26은 `main`에 병합됐지만, 리뷰어가 번호·판정 상태·용량·사후 등록·ADR 표현을 후속 PR에서 정리한다고 명시했다. 이 변경에서는 그 항목을 선점하지 않고 원시 근거가 없는 임베딩 상세값만 제출 보고서에서 내렸다.
- 재현성: 평가기가 모든 성공·오류·키 없음 결과에 Python과 `numpy`·`sentence-transformers`·`torch`·`transformers`·`openai` 버전을 기록하도록 바꿨다. 기존 Voyage 원시 결과 4건은 당시 버전을 사후 추정하지 않고 미기록으로 표시했다.
- API 정책: OpenRouter Terms 외에 공식 Privacy Policy·ZDR·provider 데이터 정책 출처를 라이선스 문서에 추가했다. Voyage 4는 정책 차단 상태이며 성공 호출·1,024차원 응답 검증 전 최종 모델로 선정하지 않는다. 계정 정책은 변경하지 않았다.
- 클라이언트 캐시: 지원하는 두 모델 키를 번갈아 호출해도 각 SDK 클라이언트를 한 번만 만들도록 캐시 크기를 2로 맞췄다.
- PR 규모 계획: 이번 변경은 Voyage 후보 2종의 계약·평가기·테스트·원시 결과·보고서를 함께 맞추는 단일 목적이지만 핵심 변경이 400줄을 넘는다. 계약과 결과를 분리하면 같은 PR 안에서 검증 근거가 끊기므로 PR은 나누지 않고, PR 본문에 규모·초과 이유·분리하지 않은 이유를 적는다. 커밋은 `평가기와 테스트` → `계약과 정책 문서` → `원시 결과와 보고서`의 논리 단위로 나눈다.
- 검증: 버전 메타데이터와 두 모델 캐시 테스트는 각각 실패하는 RED를 확인한 뒤 최소 구현으로 통과시켰다. 관련 테스트 41건과 전체 테스트 69건이 통과했고 2건은 기존 조건대로 skip됐다. Voyage JSON 4건 파싱, 변경 Markdown 로컬 링크, 비밀정보 모양 값, `git diff --check`도 확인했다.
- 보고서 연결 보완: `EVAL_REPORT.md`에 13종의 증거 수준별 요약을 추가하고, 후보별 선정·중단 이유의 정본인 `docs/embedding-candidate-investigation.md`와 라이선스 정본을 직접 연결했다. 보고서에는 결과·해석을, 상세 문서에는 모델별 조사 근거를 유지한다.
- 연관 문서 정합성 보완: 초기 4종 기준선 작업서의 후속 계획을 역사 기록으로 표시하고 현재 본평가 문서로 연결했다. `evals/EVALS.md`에는 API 정책 차단과 13종 상세 기록 링크를 추가했으며, 후보 평가기 작업서의 확장 전 상황을 과거형으로 고쳤다. `tests/TESTS.md`에는 Voyage 입력 계약·정책 오류·실행환경 메타데이터·두 모델 캐시 검증을 반영했다.

## 2026-11-02 Voyage 후보 계약과 서비스 경계 보완

- 한 일: Voyage 두 후보 추가가 기존 9+2 후보 작업서와 충돌하지 않도록 전용 5절 계약을 만들고, 후보 registry를 실행 11종·조사 2종으로 정렬했다. 현재 서비스 기본값은 `text-embedding-3-small`·`vector(1536)`이며 Voyage는 평가 후보라는 경계를 `SPEC.md`와 평가 문서에 명시했다.
- 해석 변경: 외부 관리형 API와 팀이 별도 추론 서버에 배포하는 자체 API는 최종 모델 확정 뒤 ADR로 결정한다. 로컬 Recall@5·MRR은 후보 선별 자료로 보존하고, 실제 운영 방식의 동일 동결 표본 결과만 최종 선택에 사용한다. 자체 API라면 모델 이미지·GPU/CPU·메모리 비용도 운영 지표에 포함한다.
- 후보 구분: `text-embedding-3-small`, `voyage-4`, `bge-m3`를 외부 관리형 API 우선 비교 대상으로 적고, Qwen 0.6B는 실행 시 provider 확인 대상으로 뒀다. KURE와 Voyage 4 Nano는 로컬 연구 기준점이면서 자체 추론 API를 택할 경우 운영 후보가 될 수 있다. `voyage-4-lite`는 Nano의 저비용 역할을 비교할 수 있는 미평가 API 후보로만 기록했으며 기존 13종 결과 수에는 넣지 않았다.
- 바꾼 파일: `SPEC.md`, `EVAL_REPORT.md`, `docs/specs/embedding-voyage-candidates.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/SPECS.md`, `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, Voyage 결과 JSON 4건, 후보·라이선스 문서와 작업 기록
- 확인 못 한 것: Voyage 4는 현재 계정 ZDR 정책으로 차단돼 있고, 나머지 API 후보도 동결 평가셋에서 아직 같은 조건으로 실행하지 않았다. 모델 제공 여부·가격·provider 정책은 재색인 전에 다시 확인해야 한다.
- 검증: Voyage 입력 메타데이터 테스트가 2건 실패하는 RED를 확인한 뒤 query/document 모드와 자동 prompt 기록을 구현했다. API 정책 오류가 품질 지표를 만들지 않는 테스트를 포함한 관련 테스트 39건, 전체 테스트 67건이 통과했고 2건은 기존 조건대로 skip됐다. 기존 원시 측정값은 바꾸지 않고 고정 입력 메타데이터만 보강했으며 JSON 4건을 다시 파싱했다. 5절 작업서 구조·로컬 Markdown 링크·현재 서비스 기본값·`git diff --check`도 확인했다.

## 2026-11-02 Voyage 4 후보 실행 사전 기록

- 목적: 실제 TSC PDF 3건·156청크·사전 고정 질의 9건에서 로컬 `voyage-4-nano`와 OpenRouter `voyage-4`를 기존 성공 후보와 같은 dense cosine `k=5`로 비교한다. 2차 판정 전 smoke이며 최종 선택에는 사용하지 않는다.
- 고정 조건: 두 모델 모두 1,024차원과 query/document 입력 구분을 사용한다. Nano 모델·코드 revision은 `5fb34e870f49f19e79c94d5e118f5ee730133279`, attention은 `sdpa`다. API 모델 ID는 `voyageai/voyage-4`다.
- 보안 점검: Nano 원격 코드 3,491자를 고정 revision에서 확인했다. 외부 프로세스·네트워크·동적 `eval/exec`·파일 쓰기 패턴은 발견되지 않았으며 이는 완전한 보안 감사를 뜻하지 않는다.
- 예산·중단 조건: Nano 신규 모델·패키지 다운로드 상한 2GiB, API 총비용 상한 `$0.02`, 최대 11요청, 자동 재시도 0회다. OOM·revision 불일치·상한 초과·새 호환성 오류가 나면 해당 후보를 중단한다. 키 값은 읽거나 출력하거나 결과에 저장하지 않는다.
- RED/GREEN: Voyage registry·OpenRouter allowlist·1,024차원·query/document 분리 테스트 8건이 먼저 실패했다. 최소 구현 뒤 관련 테스트 37건이 통과했다. 이 기록과 임베딩 탐색 표 #14·#15를 남길 때는 실제 모델 결과를 아직 보지 않았다.
- 실행 결과: Nano는 Recall@5 0.889, MRR 0.744, 1,000청크 5.29초, 질의 p50/p95 53.9/80.5ms였고 완전 오프라인에서 같은 순위 결과를 재현했다. HF·uv 캐시 합계 증가는 약 0.6GB로 2GiB 상한 안이었다.
- API 차단: 첫 명령은 API 호출 전 `PYTHONPATH` 누락으로 실패해 별도 JSON으로 보존했다. 환경만 교정한 요청은 OpenRouter ZDR/data-policy가 유일 endpoint를 제외해 404로 끝났으며 retry는 0이다. 성공 embedding·usage가 없어 Recall@5·MRR·비용 결과는 없고 계정 정책은 변경하지 않았다.
- 검증: Nano 온라인·오프라인의 Recall@5·MRR·문항별 순위가 모두 일치했다. 전체 테스트는 65건 통과·2건 skip이고 `git diff --check`, 후보 문서 13개 항목, 결과 JSON 상태·usage 부재 검사를 통과했다.

## 2026-11-02 임베딩 후보 11종 개별 조사 기록

- 한 일: 후보 11종을 같은 수준으로 평가했다는 오해를 막기 위해 모델별 선정 이유, 조사·실행 과정, 중단 사유, 현재 증거 수준과 다음 평가 조건을 개별 문서로 정리했다.
- 바꾼 파일: `docs/embedding-candidate-investigation.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/worklog/osc.md`
- 근거 구분: 실제 PDF smoke 완료 4종, 합성 프록시만 완료 1종, 호환성 차단 4종, 조사 전용 2종으로 나눴다. 오류 후보를 품질 0점으로 쓰지 않고 실행되지 않은 후보에는 Recall@5·MRR이 없다고 명시했다.
- 검증: 모델별 2차 제목 11개와 문서 내부 링크를 점검했고, `.venv-windows`의 오프라인 전체 테스트는 60건 통과·2건 skip이었다. `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정·동결 평가셋·전체 코퍼스가 없으므로 11종 동일 조건 본평가와 최종 모델 선정은 하지 않았다.
- 다음 할 일: 동결 뒤 우선 5종을 동일 조건으로 평가하고, 호환성 후보는 고정 환경을 해결한 경우에만 추가한다. 약관·연구용 후보는 별도 승인과 결과표로 분리한다.

## 2026-11-02 임베딩 본평가 준비 상태 점검

- 한 일: 2차 판정 전 범위의 마지막 단계로 본평가 시작 조건을 저장소 실물과 Docker 캐시에서 읽기 전용으로 점검했다. 2차 판정·동결·최종 모델 선정은 수행하지 않았다.
- 확인 결과: `data/manifest.jsonl`은 1,360행·청크 수 합계 52,244의 메타데이터를 보유하지만 저장소 PDF는 smoke용 3건뿐이다. `evals/FROZEN.json`, 전체 `chunks.jsonl`, `params.jsonl`, `tsc_datasheet_list.csv`는 없고 `evals/dataset_v1.jsonl`은 2행짜리 형식 예시다. BGE·KURE·Qwen·E5의 평가기에 고정한 정확한 revision snapshot은 `sojafit-hf`에 모두 있다.
- 상태 분류: 고정 revision·오프라인 실행기·지표 기록은 통과, 2차 사람 판정·평가셋 동결·API 기준선 승인은 대기, 전체 1,360건 본문 부재는 차단이다. 이 구분을 `EVAL_REPORT.md`의 본평가 준비 표에 기록했다.
- 검증: Windows 전용 `.venv-windows`에서 `UV_PROJECT_ENVIRONMENT=.venv-windows uv run --offline pytest -q`를 실행해 60건 통과·2건 skip을 확인했고 `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정 결과, 동결 gold의 실제 건수·해시, 전체 코퍼스 본문 위치, 동결 평가셋에서의 Recall@5·MRR, CPU 배포 지연은 아직 확인할 수 없다.
- 다음 할 일: 담당자가 2차 판정과 차이 합의를 마치고 전체 본문·동결 파일을 제공하면, 비용 상한을 다시 승인받아 동일 입력·동일 검색 조건에서 API 기준선과 로컬 후보를 실행한다. 최종 확정 뒤에만 별도 확인을 받아 탈락 후보 가중치와 평가용 임시 캐시를 삭제한다.

## 2026-11-02 2차 판정 전 임베딩 호환성 재검증 사전 기록

- 목적: 품질 점수 없이 중단된 GTE, Jina v3, Nomic v2 MoE, Arctic v2를 품질 탈락으로 오해하지 않도록 고정 revision과 공식 사용 조건을 기준으로 호환성 변수 하나씩만 바꿔 재검증한다. 이후 저장소의 실제 PDF 3건 smoke로 연결하되 2차 판정·동결·최종 선택은 하지 않는다.
- 이미 본 오류: GTE는 warmup CUDA `AcceleratorError`, Jina v3는 load의 `custom_st` `ModuleNotFoundError`, Nomic은 `einops` `ImportError`, Arctic은 warmup `AssertionError`다. 공식 고정 revision 자료는 각각 Sentence Transformers 3.0 이상, Jina의 3.1.0 지원, Nomic의 `einops`·`megablocks`, Arctic 설정의 Sentence Transformers 2.7.0·Transformers 4.39.3을 가리킨다.
- 변경 변수: GTE는 attention 구현만 `eager`, Jina는 Sentence Transformers만 3.1.0, Nomic은 공식 runtime extras만 추가, Arctic은 모델 설정의 런타임 버전 조합만 적용한다. 질의·문서·revision·batch·GPU·평가 표본은 고정한다.
- 예산: API 호출·비용 `$0`; 처음 승인한 신규 다운로드 상한은 1 GiB였다. Docling의 Linux Torch/CUDA 의존성이 병렬 다운로드되며 uv 캐시가 5.8GB에서 8.3GB로 늘어 즉시 컨테이너를 중단했고, 사용자가 2026-11-02에 실행 전 5.8GB 대비 총 증가 4 GiB(uv 캐시 9.8GB)까지 추가 승인했다. 기존 모델 가중치 캐시를 사용하며 환경변수 값과 키는 읽거나 출력하지 않는다.
- 실행·중단: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`에서 후보당 변경 후 최대 1회만 실행하며 자동 재시도는 0회다. 동일 오류, 새 오류, GPU OOM, revision 불일치가 발생하면 해당 후보를 중단한다. PDF 파싱 환경은 uv 캐시 9.8GB를 넘으면 중단하고 Hugging Face 모델은 네트워크로 받지 않는다.
- RED/GREEN: `error_metadata` 부재로 2건이 예상대로 실패한 뒤, 오류 형식·메시지 300자·단계·retry 0을 보존하는 최소 구현으로 `tests/test_benchmark_embeddings.py` 26건이 통과했다.
- 호환성 재검증 결과: GTE는 `eager` attention 단일 변경 뒤에도 같은 CUDA device-side assert가 발생해 차단됐다. Jina v3와 Arctic은 요구 버전이 오프라인 uv 캐시에 없어 모델 실행 전에 중단됐다. Nomic은 고정 README가 요구하는 `megablocks`가 커밋이 고정되지 않은 Git 설치여서 알 수 없는 외부 코드를 설치하지 않고 보안상 차단했다. 후보별 추가 재시도는 없었다.
- 비용·용량 결과: API 호출과 비용은 0이다. Hugging Face 볼륨은 실행 전후 모두 10.3GB였고 신규 모델 가중치 다운로드는 없었다. 호환성 패키지도 네트워크로 자동 다운로드하지 않았다.
- 실제 PDF smoke 사전 고정: PDF 본문이나 정답 청크를 보기 전에 `1N4148`, `1N5817`, `BZT52C2V4`에 품번·전기 정격·시험 조건 질문을 3건씩 작성했다. 총 9건이며 gold와 정답 숫자는 아직 넣지 않았다. 실제 3문서 청크 전체에서 dense cosine `k=5`로 Recall@5·MRR을 재는 조건을 임베딩 탐색 표 #13에 기록했다.
- PDF 파싱 추가 승인: Linux Torch/CUDA 패키지의 병렬 다운로드가 중단 중에도 진행돼 uv 캐시가 11.6GB까지 증가했고 사용자가 이 상태를 승인했다. 이후 네트워크 차단 상태에서 압축 해제 archive의 Docling·Torch·pdfplumber import는 성공했으나 Docling 분석 모델이 없어 PDF 3건 모두 파싱 전에 실패했다. 공식 API로 layout `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` 171,764,371바이트와 table `fc0f2d45e2218ea24bce5045f58a389aed16dc23` 358,236,323바이트를 확인했고 사용자가 두 고정 snapshot에 한해 추가 1GB 상한을 승인했다.
- 실제 PDF 파싱·청킹 결과: 고정 layout/table snapshot과 고정 MiniLM tokenizer `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`를 로컬 경로로 전달했다. 모델 파일 사용량은 505.5MiB, tokenizer는 698,829바이트였다. PDF 3건은 각각 5/6/7쪽, 표 5/6/7개로 파싱됐고 표 숫자 witness는 81/81, 49/49, 385/385가 일치했다. 기존 card chunker는 서로 다른 청크 156개를 만들었다.
- 수동 gold: 모델 결과를 보기 전에 1N4148의 VRRM·VF 조건·trr 조건, 1N5817의 VRRM·VF 조건·IFSM 조건, BZT52C2V4의 VZ/IZT·동적 저항·패키지/전력 청크를 PDF·쪽·표 행으로 대조했다. 전체 156청크와 9질의를 `embedding_real_pdf_smoke_v0.jsonl`에 결합했으며 마지막 질문만 두 gold 청크를 가진다.
- 실제 PDF 로컬 탐색 기록: KURE·BGE·Qwen·E5의 Recall@5·MRR·지연을 기록했지만 평가기와 원시 JSON은 저장소에 반영하지 않았다. 특히 Qwen의 `10.37초`는 기존 Windows 30청크 원시값 `10.372056...초`와 같고 실제 PDF 원시 JSON이 없어 재측정값인지 확인할 수 없다. 따라서 이 상세값은 제출용 `EVAL_REPORT.md`와 모델 선정 근거에서 제외했다. 호환성 차단 4종도 저장소에서 재현할 수 있는 결과로 취급하지 않는다.
- 해석: 3문서·9질의 dense-only smoke에서는 KURE가 가장 높은 MRR이었다. 그러나 네 성공 모델 모두 패키지와 전력 두 근거가 필요한 BZT52C2V4 질문을 top-5에서 놓쳤고, 표본이 작고 품번이 직접 포함돼 최종 선택에는 사용할 수 없다. 2차 판정·동결·전체 코퍼스 본평가 전까지 모든 결과는 최종 결정 부적격이다.

## 2026-11-02 임베딩 확장 후보 프록시 실행 기록

- 목적: 기존 30청크·18질의 프록시와 동일한 dense 검색 조건에서 Qwen 재측정과 GTE, multilingual-E5, Jina v3, Nomic v2, Arctic v2의 Recall@5·MRR·1,000청크 시간·22,000벡터 질의 지연을 측정한다. 동결 전 smoke test이므로 최종 모델 확정 근거로 승격하지 않는다.
- 예산: 신규 핵심 가중치 예상 합계 약 6.8GiB, 캐시·메타데이터 포함 신규 다운로드 상한 9GiB. API는 호출하지 않으며 비용 상한은 $0이다.
- 환경: RTX 5060 Laptop GPU 8GB, Docker `sojafit-hf`·`sojafit-uv` 캐시를 사용한다. BGE-M3와 KURE-v1은 Docker 캐시에 있으며 기존 결과를 재사용한다.
- 원격 코드 점검: GTE, Jina v3, Nomic이 외부 코드 저장소를 참조함을 실행 전에 발견했다. 외부 코드 SHA를 각각 고정하고 `code_revision` 전달·결과 기록 테스트를 추가했다. Arctic는 모델 저장소 내부 코드를 모델 SHA와 같은 값으로 고정했다.
- 실행 명령: `docker run --rm --gpus all -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --isolated --with sentence-transformers --with torch python evals/benchmark_embeddings.py --model MODEL --output evals/results/embedding_MODEL_2026-11-02.json`
- 중단 조건: 모델별 OOM·실행 오류·15분 이상 무출력 또는 누적 신규 캐시 9GiB 초과 시 해당 모델을 중단한다. 자동 재시도하지 않고 오류와 단계를 기록한다.
- 실행 결과(로컬 탐색·원시 미반영): Qwen `3.63초`, multilingual-E5의 품질·지연, GTE·Jina·Nomic·Arctic의 오류를 로컬에서 기록했지만 대응 원시 결과와 확장 평가기는 저장소에 반영하지 않았다. Qwen `3.63초`는 검수 가능한 원시가 없으므로 사용하지 않고, 저장소 원시 JSON이 있는 30청크 오프라인 값 `3.83초`만 재현 가능한 기록으로 유지한다. API는 호출하지 않았다.
- 저장·용량 결과: 온라인·오프라인 원시 JSON과 실패 JSON을 `evals/results/embedding_*_2026-11-02.json`에 저장했다. `sojafit-hf` 볼륨은 6.4GB에서 10.3GB로 약 3.9GB 늘어 9GiB 상한 안이었다. 전용 모델 Docker 이미지는 만들지 않고 공통 이미지·uv 캐시와 분리된 모델 볼륨을 사용했다.
- 해석: 성공 5종의 프록시 MRR은 API 0.907, KURE 0.894, Qwen 0.875, BGE 0.863, E5 0.785 순이다. 실패 4종은 품질 탈락이 아니라 현재 고정 환경에서 비교 불가로 둔다. 18질의 프록시 결과를 최종 모델 확정에 사용하지 않는다.
- 후속 정리: 2차 판정까지 끝내고 최종 임베딩 모델을 확정한 뒤 탈락 모델의 정확한 캐시 경로와 회수 용량을 제시해 별도 확인을 받고 로컬 가중치를 삭제한다. 평가 결과와 revision·라이선스 기록은 보존한다.

## 2026-11-02 임베딩 후보 확장 평가기 설계 및 구현

- 한 일: 팀장이 지시한 미평가·연구용 임베딩 후보 비교를 준비하기 위해 실행 후보 9종과 조사 전용 후보 2종을 확정했다. 모델별 query/document 입력 형식, 불변 revision, 라이선스·운영 분류, 키 없는 API 처리, 오프라인 로더와 오류 메타데이터를 평가기에 구현했다. Jina v3는 연구용 실행으로, EmbeddingGemma와 Jina v4는 조사 전용으로 분리했다. 최종 모델 확정은 2차 판정과 평가셋·코퍼스 표본 동결 이후로 유지했다.
- 바꾼 파일: `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, `tests/TESTS.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: catalog 부재 RED 4건, 입력 어댑터 부재 RED 11건, 실행 메타데이터 부재 RED 5건, 라이선스 문서 부재 RED 1건을 확인했다. GREEN에서 후보 테스트 15건과 중앙 API 경계 포함 21건이 통과했고, 최종 전체 가벼운 테스트는 46건 통과·2건 skip이었다. 공식 모델 카드와 라이선스를 2026-11-02에 다시 확인해 8개 로컬 실행 후보와 조사 후보 2개의 40자리 revision을 고정했다. 모델 다운로드와 API 호출은 하지 않았다.
- 확인 못 한 것: 신규 후보의 실제 모델 로드·다운로드 크기·VRAM, `HF_HUB_OFFLINE=1` 재실행, 프록시 Recall@5·MRR·지연, 동결 평가셋과 실제 코퍼스 표본 결과는 아직 측정하지 않았다.
- 다음 할 일: 2차 판정과 50건 평가셋·코퍼스 표본 동결 뒤 사전등록 조건을 확정하고, 비용·다운로드·중단 조건을 먼저 승인받아 실행 후보를 같은 환경에서 비교한다.

## 2026-10-30 임베딩 평가 리뷰 반영

- 한 일: 예비 기본 선택인 `text-embedding-3-small`과 본평가 기준선을 일치시켰다. `BM25 + text-embedding-3-small`을 기준선으로 두고 KURE와 Qwen 후보 구성을 각각 한 번에 하나만 바꾸도록 사전등록·평가 리포트·작업서를 정렬했다. 검색 품질 지표와 실행 환경이 다른 운영 프로파일을 분리하고, 로컬 지연이 RTX 5060 Laptop GPU 측정값이며 2026-10-30 배포 기준 Cloud Run CPU 1 vCPU·메모리 512 MiB를 대표하지 않는다는 점을 각 로컬 행에 연결했다. 로컬 모델 배포 시 메모리 증설·CPU 재측정이 필요하다는 점도 추가했다.
- 바꾼 파일: `evals/PREREGISTER.md`, `EVAL_REPORT.md`, `docs/specs/embedding-model-baseline.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 머지된 `origin/main`을 `OSC`에 fast-forward하고 기준선 관련 문구를 `rg`로 대조했다. Docker의 `uv sync --frozen --dev --offline` 뒤 전체 테스트를 실행해 3건이 통과했다.
- 확인 못 한 것: Cloud Run CPU 환경의 실제 임베딩 지연, 로컬 모델별 최소 메모리, 100문서 실제 청크의 본평가 결과는 아직 측정하지 않았다.
- 다음 할 일: 100문서 실제 청크와 교차 라벨한 질의가 준비되면 API 기준선, KURE, Qwen을 사전등록 조건 그대로 비교한다.

## 2026-10-30 임베딩 모델 예비 기준선

- 한 일: 실제 코퍼스 수집 전에 `text-embedding-3-small`, `bge-m3`, `KURE-v1`, `Qwen3-Embedding-0.6B` 후보를 거르기 위한 30청크·18질의 프록시 표본과 재현 스크립트를 만들었다. 로컬 세 모델의 Recall@5, MRR, 1,000청크 처리 시간, 22,000벡터 exact search 지연을 같은 RTX 5060 Laptop GPU에서 측정하고 `HF_HUB_OFFLINE=1` 재실행을 확인했다. 사용자가 비용을 확인하고 약 2원 한도 실행을 승인한 뒤 OpenRouter의 `openai/text-embedding-3-small`도 같은 표본으로 측정했다. 이 실행은 결과를 보기 전 기대 범위를 적지 못한 탐색적 smoke test라 G5 개선 실험으로 세지 않는다. 원격 최신 main `44dadbf`를 fast-forward로 반영한 뒤, 최신 데모 규칙에 맞춰 미등록 질의의 BM25-only 추출형 fallback과 실제 100문서 후속 평가를 문서화했다.
- 실험 조건과 승인 근거: 목적은 네 후보의 검색 품질·지연·비용·오프라인 적합성을 같은 프록시에서 비교하는 것이다. 청크 30개, 질의 18개, dense cosine, gold 1개, 리랭커 없음, RTX 5060 Laptop GPU를 고정했다. API 예산 상한은 약 2원으로 사용자가 비용 안내 뒤 승인했고, Qwen 추가도 약 1.21GB 다운로드·API 비용 $0 안내 뒤 사용자가 명시적으로 요청했다. 오류·OOM·사용자 중단 시 반복 호출하지 않는 것을 중단 조건으로 뒀고 Qwen query instruction은 실행 전에 영문 한 문장으로 고정했다. 단, 이 조건을 저장소 worklog에 적은 시점은 실행 뒤 규칙 검수 때였으므로 다음 무거운 실험부터는 명령 실행 전에 기록한다.
- 바꾼 파일: `SPEC.md`, `backend/services/llm.py`, `backend/services/SERVICES.md`, `tests/test_llm.py`, `tests/TESTS.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `evals/embedding_sample_v0.jsonl`, `evals/benchmark_embeddings.py`, `evals/EVALS.md`, `evals/PREREGISTER.md`, `evals/results/embedding_*_2026-10-30.json`, `EVAL_REPORT.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 로컬 후보는 Docker의 `uv run --offline --isolated --with sentence-transformers --with torch`로 최종 비교했다. `bge-m3`는 Recall@5 1.000, MRR 0.863, 1,000청크 5.95초였고 `KURE-v1`은 Recall@5 1.000, MRR 0.894, 1,000청크 5.68초였다. Qwen은 Recall@5 1.000, MRR 0.875, 1,000청크 3.83초, 질의 p50/p95 61.8/82.9 ms였으며 캐시 snapshot 경로를 직접 로드해 `HF_HUB_OFFLINE=1`을 통과했다. 최초 Windows 임시 환경 결과는 10.37초, 43.7/49.0 ms였으나 실행 환경이 달라 비교표에서 제외하고 원시 JSON으로만 보존했다. OpenRouter API 결과는 Recall@5 1.000, MRR 0.907, 1,000청크 7.02초, 질의 p50 918.7 ms였다. 전체 API 사용량은 45,699토큰, $0.000914였다. 첫 실행에서 22,000행 생성의 `numpy.tile` 축 오류를 재현해 행 방향 반복으로 수정한 뒤 재실행했다. 저장소 규칙 검수에서 API 직접 호출을 발견해 `backend/services/llm.py`의 단일 임베딩 호출 경계로 옮겼고, `embed_texts` 부재로 실패하는 RED를 확인한 뒤 mock client 계약 테스트를 통과시켰다.
- 확인 못 한 것: 100개 PDF 실제 청크, CPU/Cloud Run 지연, 최종 Dockerfile의 압축 이미지 크기는 아직 측정하지 않았다.
- 다음 할 일: `PREREGISTER.md` #1·#2의 고정 조건대로 100개 PDF 실제 청크와 사람이 교차 라벨한 질의에서 `BM25 + text-embedding-3-small`을 기준으로 KURE와 Qwen 후보 구성을 각각 비교한다. 그 뒤에만 `vector(N)`과 Migration 2를 확정한다.

## 2026-10-30 DB 테이블 정의서 초안 작성

- 한 일: SojaFit의 사용자, 회로, 부품·문서, 분석·판정, 승인 견적 데이터를 위한 테이블 정의서 초안을 작성했다. LangGraph 관리 테이블과 직접 관리하는 업무 테이블을 구분하고, `pgvector`·ERD·Migration은 현재 범위에서 제외했다. 확정되지 않은 항목은 가정·미정 및 추가 검토 항목 A-01~A-20으로 분리했다.
- 바꾼 파일: `db/table-definition.md`, `db/DB.md`, `docs/worklog/osc.md`, `docs/worklog/WORKLOG.md`
- 실행한 명령과 결과: `git branch --show-current`로 `OSC` 브랜치를 확인했다. `git diff --check`와 Markdown 구조·미정 항목 검색으로 문서 형식과 검토 항목을 확인했다.
- 확인 못 한 것: 로그인 방식, 사용자 ID 형식, 회로 파일 저장 방식, 판정·역할·사양 코드, 삭제 정책은 팀 합의 전이라 확정하지 않았다. ERD, Migration SQL, `pgvector` 구조는 작성하지 않았다.
- 다음 할 일: 팀이 정의서와 추가 검토 항목을 검토한 뒤 관계와 코드 정책을 확정하고 ERD를 작성한다.

## 2026-11-04 수퍼바이저 모델 비교 문서화

- 한 일: 동결 v2 70문항의 후보 5종 1회 비교 방법과 선정 기준을 문서화하고, 실험상 최종 수퍼바이저로 `openai/gpt-6-luna`를 기록했다.
- 범위: 실행 코드·manifest·모델별 parsed output은 제외하고, Markdown 문서와 약 4KB의 `stage1_summary.json`, 약 4KB의 `provider_evidence.json`만 포함한다. 집계 JSON의 모델별 품질·오류·호출·비용·latency·전체 합계와 evidence의 provider·actual model·원본 artifact hash를 보존했다. evidence 공개본은 원본 SHA-256 `f0d8c80d09566561ae663a11d2d80e4a9b10481973314cf5ca3bdd913f180494`를 기록하고 개인 PC 절대경로만 저장소 상대경로로 정규화했다.
- 정본 경계: 서비스 기본값 적용은 조장 소유 ADR·`SPEC.md` 갱신 뒤 별도 변경으로 수행한다.
- 사전등록: `evals/guides/preregister.md` #29에 추가 API 호출 없이 경량 문항별 증거로 표·집계값을 재계산하는 검증 조건, 입력 hash, 분모, 성공 기준과 0달러 비용 상한을 고정했다.
- 사후등록: `docs/experiments/supervisor-model-comparison-postregistration.md`에 완료된 5종 비교의 실제 입력·provider 조건·실행 중 변경·채점 범위·선정 순서·한계를 별도로 기록했다.
- 다음 측정 사전등록: `evals/guides/preregister.md` #30에 1·2위인 `openai/gpt-6-luna`와 `anthropic/claude-haiku-5.5`를 동결 v2 70문항에서 각각 1회 함께 재측정하는 조건을 고정했다. 두 모델의 1차 결과를 이미 본 기준값으로 공개하고, 두 품질 지표의 우위 반복 여부·절대 0.15 안정성·완전 호출 실패 중단·모델별 $0.10 예산을 결과 확인 전에 정했다. API 호출은 시작하지 않았다.

## 2026-11-04 수퍼바이저 1차 실측 근거 공개

- 바꾼 파일: `backend/services/llm.py`, `evals/runners/run_supervisor_models.py`, 두 회귀 테스트, `evals/results/supervisor/`의 1차 manifest·후보별 rows와 provider 출처가 가리키는 초기 호출 증거, 폴더 설명·트리.
- 범위: 기존 1차 실행의 코드·JSON을 보존한다. 새 모델 API 호출이나 재측정은 하지 않았다. run index 2·3은 manifest에 계획만 있고 이번 결과가 아니다.
- 확인: 실행 코드 hash가 1차 manifest와 같고, provider evidence가 가리키는 원본 hash 불일치는 0건이다. 결과 JSON의 경로·키 패턴을 검사했다. 관련 테스트와 저장소 구조 검사 41건이 통과했다. `uv sync --frozen --dev` 뒤 전체 테스트는 321건 통과·26건 skip·1건 실패했다. 실패한 기존 `test_run_graph.py::test_main_writes_metrics_only_result_file`은 Windows 기본 인코딩으로 쓴 한글 임시 파일을 UTF-8로 읽을 때의 `UnicodeDecodeError`이며 이번 변경 파일이 아니다. 저장소에 올리는 원본은 문항별 parsed decision·usage·오류 종류를 포함하며 raw prompt·raw response 원문은 포함하지 않는다.
- 남은 한계: OpenRouter의 외부 서명 로그가 없으므로 저장소 JSON만으로 실제 청구·호출을 독립 증명하지 못한다. 1차 계획 복원 기록은 이 PR에 포함하지 않는다.

## 2026-11-05 수퍼바이저 6종 2차 평가 PR 준비

- 바꾼 파일: `docs/experiments/supervisor-stage2-six-models.md`, `evals/guides/preregister.md`, `docs/research/supervisor-stage2-results.md`와 간단 보고서, Jev 평가 실행기·서비스 호출 경계·회귀 테스트, 1차 Jev와 2차 6종의 manifest·smoke·문항별 원시 행·정정 집계, 폴더 설명·`SOJAFIT.md` 트리.
- 브랜치·범위: 깨끗한 기존 보조 작업 트리에서 `OSC`를 최신 `origin/main`까지 fast-forward한 뒤 2차에 필요한 파일만 옮겼다. 원래 작업 트리의 다른 미커밋 변경은 보존했다. 기존 `#29`·`#30`은 유지하고 로컬 6종 기록의 중복 번호만 `#32`로 정정했으며 이력과 원격 커밋 시각의 한계를 문서에 명시했다.
- 결과 근거: 동결 데이터셋 SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`, 정정 집계 SHA-256 `2c4ef11f52a8467c390af8e34ec3ae9e77fc958876b79ccc974973b6d6f8570b`, 원시 행 6개 해시 일치. 실패 문항을 `Completion Rate`에서 제외한 초기 `stage2_summary.json`은 PR 범위에서 뺐다. 생성형 5종의 원시 summary는 3회 계획 분모를 쓰므로 정정 집계는 `run_index=2` 행만 사용한다.
- 표 설명 보강: 2차 계약·상세 결과·간단 보고서·Jev 1차 인수인계의 영어 지표 이름과 유형 코드는 유지하고 각 표 바로 아래에 뜻, 분모, 비용·오류·미측정 값의 해석을 한국어로 적었다.
- 검증: 관련 pytest 77건 통과, `git diff --check` 통과, JSON의 비밀값·원문 입력·gold 필드 패턴 0건. 전체 pytest는 Windows 기본 인코딩에서 기존 `test_run_graph.py::test_main_writes_metrics_only_result_file`의 `UnicodeDecodeError` 1건으로 실패했고, `PYTHONUTF8=1`에서는 364 passed·27 skipped였다. 실행 코드와 평가셋은 이 준비 작업에서 유료 API를 다시 호출하지 않았다.
- 확인 못 한 것·다음 할 일: 외부 청구서로 실제 총 비용을 대조하지 못했다. 5종 manifest의 실행기 원시 바이트 해시는 현재 Windows CRLF checkout과 다르지만 LF로 정규화하면 `ff4ace1` 코드 blob과 맞는다. Jev manifest에는 실행기 파일 해시가 없어 두 코드 재현 한계를 결과 문서에 적었다. commit·push·PR 생성은 하지 않았다.
- PR 준비 정리: 두 2차 결과 보고서에서 PR 공개 후 사실과 달라질 `미커밋` 상태 문구를 제거했다. `SPEC.md`는 조장 소유 주요 문서이므로 이 브랜치에서 수정하지 않고, 조장에게 평가 전용 Jev Decisions API 호출·ZDR 및 fallback 금지·typed answer 변환 계약을 SPEC의 평가 실행 절에 반영해 달라고 PR에서 요청한다. 새 `run_supervisor_jev.py` 592줄과 `test_supervisor_jev.py` 443줄은 권장 핵심 변경 400줄 안팎을 넘는다. 6종 2차 결과를 재현·검토하려면 Jev의 호출 경계·실행 조건·변환·오류/예산 처리와 그 회귀 검증, 동일 회차 원시 행·집계를 함께 봐야 하므로 하나의 평가 근거 PR에 묶는다. PR 본문에 이 규모와 이유를 적고 커밋은 코드·계약·결과 근거의 논리 단위로 나눈다.

## 2026-11-05 PR #54 검토 피드백 반영

- 원시 결과는 보존하고 Jev 2차 `out_of_scope` 자체 분류 6건 중 `next_action != refuse` 4건을 `Routing Consistency` 오류로 보고서에 별도 표시했다. 이는 형식상 유효 결정 70/70이나 gold 35문항 Accuracy를 바꾸지 않는다.
- Jev 실행기의 `--max-usd`는 입력 비용 추정으로 다음 job을 차단하는 관리값임을 명시했다. 실제 보고 비용이 계획값을 넘은 경우 해당 행을 저장하고 추가 job 없이 `budget_exceeded`로 중단하며, `NaN`·무한대 한도는 API 호출 전 거부한다. 기존 2차 실측이 이 수정 코드로 재실행된 것처럼 기록하지 않는다.
- 변경 범위: Jev 실행기·회귀 테스트, 2차 결과·간단 보고서, 실험 계약·사전 등록 결과 해석, Jev 인수인계와 실행기 색인. 원시 JSON과 동결 평가셋은 수정하지 않았다.
- 확인: Jev 원시 `rows.json` SHA-256 `f1995ce2b442d1f7dc72d427a7ffcb2fcf9c1b63dd9a27ee015ee109d4fa0d2d` 유지. 관련 테스트 63건, `PYTHONUTF8=1` 전체 테스트 374건 통과·27건 건너뜀, `git diff --check` 통과. 유료 API 호출과 재측정은 하지 않았다.

## 2026-11-05 수퍼바이저 3차 실행 전 준비

- 목적·범위: PR #54의 2차 실측은 보존하고 여섯 모델을 같은 동결 v2 70문항에서 `run_index=3`으로 각 한 번 더 측정할 계약을 사전 등록 #33과 `docs/experiments/supervisor-stage3-six-models.md`에 고정했다. 3차 점수·모델 호출은 아직 없다.
- 조건·예산·중단: 기존 프롬프트·typed question 계약, ZDR·fallback 금지, 유형 gold 35문항, 여섯 모델의 `out_of_scope → refuse` 일관성, 1~3차 완전한 행만의 agreement·flip을 고정했다. 본 실행 계획값 US$0.88, smoke US$0.033, 합계 US$0.913, 모델별 70 outputs·210 raw calls·7,200초와 provider·가격·코드 hash 불일치 중단을 등록했다. Jev 비용값은 실제 청구액의 절대 상한이 아니다.
- API 없는 명령·결과: `uv run --no-sync python -c '...create_manifest(...)...'`로 5종 manifest를 생성해 1,050건 중 3차 350건을 확인했고, `uv run --no-sync python -m evals.runners.run_supervisor_jev plan evals/results/supervisor/2026-11-05-jev-stage3-v1 --run-index 3`으로 Jev 70건을 준비했다. 생성된 파일은 두 manifest뿐이다. 유료 API 호출 0회, smoke·본 실행 0건이다.
- 바꾼 파일: 3차 계약·사전 등록, 두 manifest, `SOJAFIT.md` 트리, 실험·평가 폴더 색인과 이 작업 기록. 기존 1·2차 원시 결과와 동결 평가셋은 바꾸지 않았다. 다음 단계는 manifest hash·현재 catalog 가격·ZDR·provider를 다시 확인한 뒤 별도 지시에 따라 smoke를 시작하는 것이다.
- 준비 검증: 5종 3차 350건과 Jev 3차 70건의 고유 job, 동결 dataset hash, 5종 prompt·code hash, Jev typed question 계약 hash를 대조했다. 관련 pytest 69건 통과, `git diff --check` 통과. 원시 결과·API 호출·커밋·푸시·PR 갱신은 하지 않았다. 유료 실행 전에 사전 등록을 별도 커밋으로 확정해야 한다.
- Jev 코드 재현 경계: Jev manifest에는 실행기 hash가 없어 `run_supervisor_jev.py`의 LF 정규화 SHA-256 `291a3367856d5650b50925ae649254330fd230b766d1751ddb03f899b08a5e1f`를 사전 등록에 별도로 적고, live 전 수동 대조를 조건으로 추가했다.
- 실행 승인: 사용자가 3차 실행과 PR용 근거 보존을 지시했다. 유료 호출 전에 위 사전 등록·manifest를 로컬 커밋으로 고정한다. 현재 catalog·ZDR·가격·첫 문항 예약을 확인하고, 승인된 모델별 smoke·본 실행 계획값을 그대로 적용한다. 원격 공개 시점으로 사전 등록 순서를 독립 증명했다고 주장하지 않는다. 키는 기존 작업 트리 `.env`에서 `OPENROUTER_API_KEY`만 읽고 출력하지 않는다.

## 2026-11-05 수퍼바이저 6종 3차 실측 완료

- 실행 시점: 사전 등록 로컬 커밋 `d10a30b`는 11:25:50 KST, smoke·본 실행은 11:27:27~11:59:19 KST다. 현재 catalog에서 6종의 모델·ZDR 노출과 첫 문항 3회 시도 예약을 확인한 뒤 순차 실행했다. 모델별 정확한 인자·UTC 시각·종료 코드·provider·원시 hash는 `2026-11-05-stage3-five-v1/execution.json`과 smoke 파일에 있다.
- 결과: 6종 모두 동결 70문항을 시도해 고유 420개 3차 행을 남겼다. 본 실행은 재시도 포함 855호출, Budget-Accounted Cost 합계 US$0.239294618로 모델별 등록 계획값 이내다. smoke 비용 전체와 외부 실제 청구액은 확인하지 않았다. 형식 오류는 해당 행에 기록하고 계속했으며, `meta/muse-glimmer-30b`의 단발 `RateLimitError` 1건도 보존했다. 추가 유료 재실행은 하지 않았다.
- 해석: `openai/gpt-6-luna`와 `typesafe/jev-1.14`의 유형 정답은 각각 33/35다. Jev는 자체 `out_of_scope` 6건 중 `refuse` 외 동작 4건을 다시 냈다. `deepseek/deepseek-v4.1-flash`의 provider는 2차 Morph에서 3차 Relace로 달라졌고 형식 통과가 62/70→7/70이어서 모델 자체 성능 변화로만 귀속하지 않는다. 35개 비관련 문항의 올바른 거절 정답률이나 독립 평가셋 성능은 측정하지 않았다.
- 근거 파일: 3차 두 결과 폴더의 manifest·preflight·환경·smoke·문항별 행·실행 metadata, `2026-11-05-stage3-comparison-v1/stage3_summary.json`, `docs/research/supervisor-stage3-results.md`·간단 보고서, API 없는 `report_supervisor_stage3.py`와 회귀 테스트를 준비했다. 최초 결과 JSON 19개 합계 1,307,905 bytes, 출처 파일 hash 34개를 검증했다. 최초 집계 SHA-256은 `890122c802eb2f7bd5efedd6cdeab74a21703ae36ce8ebae34fd67acf3d2638c`이며 이후 출력 제한 진단을 추가한 집계는 아래 기록을 따른다.
- 검증: 원시 6개 파일 모두 고유 ID 70개·run_index 3·동결 ID 일치. 저장 원시 행에서 정확도·형식 통과·호출 수를 별도 대조했고, 1~3차 manifest의 dataset·prompt/typed question 계약도 일치했다. 집계기 재실행으로 JSON과 두 보고서의 바이트 동일성을 확인했다. `PYTHONUTF8=1 uv run --no-sync pytest -q`는 381 passed·27 skipped, `git diff --check` 통과. 결과 JSON의 비밀값·원문 입력·gold 본문 필드 검사도 통과했다.
- PR 준비 범위: 새 집계 코드·테스트·계약·보고서와 원시 근거는 한 목적이다. 향후 PR 본문에 400줄 초과 이유와 실행 코드/결과를 함께 검토해야 하는 이유를 적는다. 현재 유료 실행 전 사전 등록만 로컬 커밋했고, 결과 푸시·새 PR 생성은 하지 않았다. 기존 1·2차 원시 결과와 실제 호출 실행 코드는 변경하지 않았다.

## 2026-11-05 3차 해석·후속 후보 축소안

- 추가 확인: `deepseek/deepseek-v4.1-flash`의 3차 최종 형식 실패 63건은 모두 `finish_reason=length`, 해당 189개 시도 usage는 모두 출력 256토큰이었다. gold 35건 중 형식 실패 33건·유효 유형 정답 2건으로 확인했다. 2차 대비 프롬프트·실행 로직은 같고 실행기 hash 차이는 LF/CRLF 차이다. provider 변경과 출력 제한 실패가 함께 관찰됐으며 공급자의 내부 동작 차이를 원인으로 확정하지 않는다.
- 초기 후보 축소 제안(아래 사용자 결정으로 대체): 결과 확인 후 다음 유료 평가에 `openai/gpt-6-luna`와 `typesafe/jev-1.14`를 유지하는 2종 안을 적었으나, 최종 후보 결정은 다음 항목의 3종을 따른다. 과거 실행기 후보 목록·원시 결과·서비스 모델 설정은 바꾸지 않았다.
- PR 준비 확인: 최신 `origin/main`에 추가 변경이 없고 새 번호 충돌도 없다. 추가 진단 테스트 포함 전체 `PYTHONUTF8=1 uv run --no-sync pytest -q`는 382 passed·27 skipped, `git diff --check` 통과. 기존 출처 hash 34개는 유지됐다. 결과 JSON 19개는 1,314,675 bytes, 갱신 집계 SHA-256은 `6e0455bcf9748e658467163fb2f5ddf34a1e9e60d35a342ee992c1db8dfbaf5d`다. 이번 보강에서 유료 재호출·푸시·PR 생성은 하지 않았다.

## 2026-11-05 최종 후보 3종 사용자 결정

- 사용자 지시: PR에 순위는 포함하지 않는다. 최종 후보는 `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5`의 3종으로 명시한다. `deepseek/deepseek-v4.1-flash`는 실행 안정성 부족으로 탈락하며 `cohere/command-a-plus`·`meta/muse-glimmer-30b`도 최종 후보에서 제외한다.
- 반영: 상세·간단 보고서와 보고서 생성 코드의 기존 2종 축소안을 3종 최종 후보 결정으로 바꿨다. 세 후보 사이의 순위나 주/보조 구분은 부여하지 않았다. 후보 결정은 3차 결과 확인 후 사용자 결정이며 사전 등록 선정 규칙으로 소급하지 않는다.
- 확인: API 없이 보고서를 재생성했고 모델별 실측 수치와 기존 출처 hash가 모두 같음을 대조했다. 관련 테스트 13건과 `git diff --check`가 통과했다. 생성 코드 hash가 바뀌어 파생 집계의 새 SHA-256은 `83690c83250effb4c5395c8c4045136207c08f3c531e608638c9ae74352d0d0c`다. 원시 결과와 기존 실험 후보 목록은 보존했다. 새 유료 호출·푸시·PR 생성은 하지 않았다.

## 2026-11-05 3차 결과 PR 게시 준비

- 사용자 승인으로 `OSC`에서 사전 등록, API 없는 집계기·테스트, 실측·최종 후보 3종 보고서를 논리 단위로 커밋한다. 순위 표는 포함하지 않는다.
- Git 저장 바이트 확인 중 `core.autocrlf=true`가 일부 3차 JSON의 CRLF를 LF로 변환함을 발견했다. 3차 결과 폴더의 JSON에만 `.gitattributes -text`를 적용해 로컬 원본 바이트·보고서의 원시 hash를 보존한다. 사전 등록 당시 로컬 manifest의 CRLF 바이트와 선언 hash도 그대로 보존하며 이미 만든 커밋은 다시 쓰지 않는다. 기존 1·2차 출처는 LF 정규화 SHA-256으로 Git 저장 파일과 대조하고 hash 정책을 집계·보고서에 명시했다. 과거 회차 원시 파일과 모델 실측 수치는 변경하지 않았다.
- 파생 집계와 Markdown은 LF로 생성해 환경에 따른 출력 차이를 줄였다. 현재 집계 SHA-256은 `e0491c99d59405a982f4b96107ff617cc72dac2ac6e10e0ffea95c931719ae98`다. 원시 3차 hash와 기존 회차 Git blob의 LF hash 일치, 관련 테스트 14건, 전체 `PYTHONUTF8=1 uv run --no-sync pytest -q` 383 passed·27 skipped, `git diff --check`를 확인했다. 이번 게시 준비에서는 유료 API를 호출하지 않았다.
- 게시 바이트 검증: 스테이징된 JSON 19개가 로컬 파일의 원시 바이트와 동일하고 집계의 출처 34개 hash가 Git index의 저장 내용과 일치했다. Git index의 파일만 임시 경로에 풀어 집계해도 현재 집계 JSON 전체와 같았다. CRLF 보존 파일은 `whitespace=cr-at-eol`로 줄바꿈 CR만 공백 오류에서 구별하며 staged diff 검사도 통과했다.

## 2026-11-05 PR #55 부분 실행 표기 피드백 반영

- 1~3차 대조표에서 provider 오류로 3문항만 시도한 `deepseek/deepseek-v4.1-flash` 1차의 Accuracy와 Schema Valid Rate를 모두 `Not Comparable (3/70 attempted, 0 valid)`로 표시했다. 원래의 계획 분모 계산값 0/70은 집계 JSON에 보존하며 완주한 2·3차와의 직접 비교를 피한다.
- 보고서 생성 코드와 재생성 결과, 부분 실행 두 셀의 표기를 확인하는 회귀 테스트를 함께 수정했다. 원시 파일·모델별 수치·출처 hash·실행 기록은 변경하지 않았다. 관련 테스트 15건과 `git diff --check`를 통과했다. 파생 집계 SHA-256은 코드 hash 갱신에 따라 `77139315fb0b99a2d5441fe2c5b728f90984850763f6846f2b32237cfc5e4659`로 바뀌었다.
- 유료 API 재호출은 하지 않았다. 기존 인증 테스트 대소문자 비교와 과거 임베딩 캐시 Secret Scan 문제는 이번 표기 수정 범위에 포함하지 않았다.

## 2026-11-09 D5 프론트엔드 기능 계약

- 한 일: 승인된 D5 프론트엔드 설계를 10개 AC가 있는 Why/Goal/What/How/AC 기능 계약으로 구체화했다. 조장 소유 `SPEC.md` §2·§4·§8.4·§8.5 반영 문단과 ADR 제목을 요청 섹션에 제시했다.
- 바꾼 파일: `docs/specs/d5-frontend-service.md`, `docs/specs/SPECS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`.
- 확인: `uv run pytest -q tests/repo/test_repo_layout.py` 실행 결과: `5 passed in 0.28s`. 문서 구조·링크·요청 제안은 승인 설계와 대조한다.
- 확인 못 한 것: 구현 및 프론트/백엔드 런타임 테스트는 이 계약 작성 범위가 아니다. `SPEC.md` 및 ADR 반영은 조장 검토 후 별도로 진행해야 한다.
- 다음 할 일: 조장이 요청 문단과 ADR 제목을 검토하고 정본에 반영한 뒤 후속 구현 작업을 시작한다.

## 2026-11-09 D5 Task 4 사용자 프로젝트 저장

- 목적·범위: 데모 회로 5종으로 사용자 소유 프로젝트를 만들고 목록·상세·이름 변경·삭제를 제공한다. 업로드·D5 실행·가격 저장은 제외한다. `SPEC.md` 등 조장 소유 문서는 수정하지 않고 승인된 `docs/specs/d5-frontend-service.md` AC-02/09/10의 해당 범위만 구현한다.
- TDD RED: 먼저 저장소·API 테스트를 작성했다. `uv run pytest -q tests/projects tests/api/test_projects.py` 결과 `15 failed, 5 skipped in 0.80s`. 신규 라우트 미등록 때문에 인증 401·Origin 403·카탈로그 200 대신 404였고 저장소는 `ModuleNotFoundError: backend.projects`였다. DB 주소가 없어 통합 시험 5건은 이 최초 실행에서 건너뛰었다.
- GREEN 중간 확인: 구현 후 DB 없이 `15 passed, 5 skipped`; 이후 공유 DB와 무관한 새 Docker `postgres:16-alpine` 컨테이너(로컬 loopback 랜덤 포트, 기존 볼륨 연결 없음)의 전용 시험 DB에서 `20 passed in 2.62s`. 실제 PostgreSQL SQL로 소유자·타 사용자/관리자 분리, 생성 rollback, 사용자·프로젝트 cascade를 확인했다. 레이아웃 `5 passed`.
- 변경: `db/013_projects.sql`, `backend/projects/`, `backend/api/`, `backend/main.py`, `tests/projects/`, `tests/api/test_projects.py`와 폴더·스키마 문서. BIGINT/TIMESTAMPTZ, CHECK, users→projects→circuits cascade, user_id 선두 복합 인덱스, circuits PK의 FK 인덱스 겸용, RLS·공개 역할/sequence 권한 회수를 사용한다. 데모 hash는 기존 정규화 JSON의 SHA-256이다.
- 전체 회귀 사전 기록: 라우터·스키마 경계가 바뀌므로 `PYTHONUTF8=1`, `TEST_AUTH_DATABASE_URL=<새 일회용 로컬 시험 DB>`로 `uv run pytest -q`를 한 번 실행한다. 비교 조건은 기존 전체 백엔드 suite, 외부 모델/API 호출 예산 0달러, DB는 이번에 만든 컨테이너만 사용한다. 실패하면 원인을 확인하고 수정 범위가 Task 4를 벗어나면 보고한다. 무한 재실행·공유 DB 적용은 하지 않는다.
- 최종 검증: anon/authenticated 역할이 실제 존재하는 새 시험 DB에서 집중 명령 `uv run pytest -q tests/projects tests/api/test_projects.py tests/repo/test_repo_layout.py`는 `25 passed in 2.97s`. 전체 `uv run pytest -q`는 `976 passed, 37 skipped in 75.20s`; 신규 DB 시험 skip은 0건이며 기존 suite의 선택적 시험은 해당 설정이 없으면 skip한다. 전체 실행 중 외부 모델/API 비용 0달러. `git diff --check` 통과. 데모 JSON 5종의 최상위 구조가 components/nets 및 공개 sample 상태뿐임을 확인했다.
- 자체 검토: get/list/rename/delete SQL의 소유자 필터·관리자 예외 없음·transaction rollback·파라미터 바인딩·신규 경로의 세션/Origin과 안전한 공통 오류를 대조했다. 원본·가격 필드와 업로드 경로를 추가하지 않았다. 실제 배포·기존/공유 DB 마이그레이션 및 RAG 평가셋 재측정은 실행하지 않았으며 RAG 품질 개선을 주장하지 않는다. 권장 400줄을 넘는 경우에도 단일 프로젝트 저장 기능과 소유권 회귀를 함께 검토하도록 요청된 한 커밋 범위를 유지한다.
- 비밀값 점검: staged diff를 `ghcr.io/gitleaks/gitleaks:latest stdin --redact --no-banner --log-level warn`으로 검사했다. 실제 비밀값을 추가하지 않았으며 테스트 세션 문자열은 일회용 fixture다. 최종 diff는 Task 4의 20개 파일에 한정된다. 새 시험 컨테이너만 정리하고 지정 메시지로 로컬 커밋한다.

## 2026-11-09 D5 Task 5 KiCad 업로드 정규화

- 목적·범위: 승인된 `docs/specs/d5-frontend-service.md` AC-03 범위에서 인증된 multipart 업로드를 제한된 메모리에서 정규화하고 원본 없이 저장한다. frontend·D5 실행·가격·공유 DB·원격 변경은 제외한다. 주요 문서는 신규 파일의 `SOJAFIT.md` 트리 줄만 추가한다.
- TDD RED: 구현 전에 `uv run pytest -q tests/projects/test_netlist.py tests/api/test_projects.py` → `32 failed, 14 passed, 1 skipped in 1.02s`. 정규화 모듈 없음 assertion과 미등록 업로드 405가 예상 원인이다. 추가로 저장소 호출 전에 원본 버퍼가 닫혀야 한다는 시험을 RED(`1 failed, 2 passed`)로 확인하고 정규화 직후 close를 추가했다.
- 구현: `backend/projects/netlist.py`의 immutable 연결(parts/nets)/hash/ref tuple, `backend/api/projects.py`의 인증 후 제한 multipart 수신, `ProjectRepository.create_upload`의 원자적 저장. `uv add python-multipart`로 직접 의존성과 lock을 함께 갱신했다. 합성 정상/불완전 fixture와 파서·API·실제 DB 시험, 폴더 문서·신규 파일 트리를 추가했다.
- 상한·폐기: 파일 5 MiB, read 5 MiB+1 한 번, 깊이 64, token 500,000, component/net 각 100,000. 기본 multipart의 1 MiB disk spool 대신 파일/전체 요청 상한을 검사해 메모리에만 둔다. 원본 버퍼는 정규화 직후 닫고 finally에서도 성공/실패·부분 multipart 전체를 닫는다. 저장소 인수는 정규화 연결·hash·parser version뿐이다. 잘못된 UTF-8/문법은 공통 400, 초과는 공통 413이며 요청 ID를 유지한다.
- GREEN 중간 확인: 새 `postgres:16-alpine` 일회용 컨테이너(기존 볼륨 없음, loopback 임의 포트, 전용 `task5_test` DB)의 `uv run pytest -q tests/projects tests/api/test_projects.py tests/repo/test_repo_layout.py` → `60 passed in 4.11s`. DB rollback·타 사용자/관리자 비공개 404·저장 행 원본 없음·제한된 read·disk rollover 없음·close·불변 데이터·hash 순서를 검증했다. 공개 Breadboard export는 부품 20·넷 13개로 읽었다. `uv lock --check`, `git diff --check` 통과.
- 전체 회귀 사전 기록: multipart·API·DB 경계가 바뀌므로 `PYTHONUTF8=1`, `TEST_AUTH_DATABASE_URL=<이번 새 일회용 DB>`로 `uv run pytest -q`를 한 번 실행한다. 비교 조건은 기존 backend 전체 suite, 외부 API/모델 예산 0달러, `anon`/`authenticated` NOLOGIN 역할이 존재하는 시험 DB다. 실패 시 원인을 조사하며 Task 5 밖 변경·무한 재시도는 하지 않는다. RAG 동작은 바꾸지 않으므로 동결 평가셋 재측정·품질 개선 주장은 하지 않는다.
- 규모·미검증: 보안 파서·API 경계·실제 DB 회귀를 한 기능으로 검토하기 위해 핵심 변경은 권장 400줄을 넘는다. 코드/시험/폴더 계약을 기계적으로 분리하지 않고 요청된 한 커밋으로 남긴다. `SPEC.md` 반영은 조장 검토 대상이며 이번에 수정하지 않는다. 기존 공통 handler의 413 code는 `HTTP_ERROR`이며 413 전용 code 추가는 이 범위에 포함하지 않았다.
- 전체 회귀 결과: 1차 `14 failed, 997 passed, 37 skipped in 43.16s`는 새 시험 DB의 public 인증 테이블 초기화를 빠뜨린 준비 오류였다. CI와 동일한 003/005/006 SQL만 이번 시험 DB에 적용한 뒤 `1011 passed, 37 skipped in 75.84s`. production 수정 없이 해결했다. 기존 선택적 시험 37건은 설정/자산이 없어 skip했으며 신규 Task 5 DB 시험 skip은 0건이다. 외부 API/모델 호출 비용 0달러.
- 최종 확인: CRLF/LF에 무관한 fixture 처리로 시험을 보정한 뒤 집중/레이아웃 `60 passed in 4.16s`, lock·staged whitespace 검사 통과. staged 17개 파일은 Task 5 범위이며 합성 fixture 외 원본·생성 결과를 넣지 않았다. staged diff를 로컬 Docker gitleaks stdin(`--redact --no-banner --log-level warn`)으로 검사해 비밀값 발견 0건을 확인했다. 새 시험 컨테이너만 정리하며 요청된 메시지로 로컬 커밋한다.

### Task 5 Fix Round 1

- 검토에서 지적된 파일명/확장자, net code 유일성·형식, quoted NUL만 보완한다. raw/text 지역 참조 수명 관련 Minor는 요청대로 최종 검토까지 보류한다.
- RED: production 수정 전 `PYTHONUTF8=1 uv run pytest -q tests/projects/test_netlist.py tests/api/test_projects.py` → `20 failed, 49 passed, 1 skipped in 1.82s`. 비정상 입력이 정상 반환/201로 통과하는 것이 예상 원인이었다.
- 정책 근거: 기존 공개 KiCad 5종의 13/8/14/44/14 nets는 모두 ASCII 양의 정수 code를 사용한다. 표준 표기 `[1-9][0-9]*`와 net 간 유일성을 요구한다. code는 문자열로 유지하며 0/음수/소수/부호/지수/앞자리 0/비 ASCII 숫자는 거절한다. NUL은 metadata 포함 입력 전체에서 거절한다. filename은 비어 있지 않고 공백 제거·대소문자 무시 후 `.net`으로 끝나야 한다.
- 검증 계획: 새 일회용 `postgres:16-alpine` 컨테이너만 사용한다(기존 볼륨/공유 DB 없음). CI의 003/005/006 인증 SQL과 anon/authenticated NOLOGIN 역할을 먼저 준비하고 두 요청 시험 파일·repo layout·저장소 시험을 실행한다. 그 후 `PYTHONUTF8=1 TEST_AUTH_DATABASE_URL=<새 일회용 DB> uv run pytest -q` 전체 backend suite를 한 번 실행한다. 외부 API/모델 예산 0달러, 반복 실패하면 원인·범위 확인 후 중단한다.
- GREEN: `uv run pytest -q tests/projects/test_netlist.py tests/api/test_projects.py tests/projects/test_project_repository.py tests/repo/test_repo_layout.py` → `82 passed in 4.25s`; 전체 backend 한 번 실행 → `1033 passed, 37 skipped in 75.35s`. 신규 시험 skip은 없으며 기존 선택적 시험 37건만 skip했다. `uv lock --check`, `git diff --check`도 통과했다. 새 정상화 코드로 공개 KiCad 5종을 모두 읽어 net 수 13/8/14/44/14를 유지했다. 원본/DB schema/정규화 shape/의존성은 바꾸지 않았다. staged diff·비밀값을 확인하고 지정된 fix 커밋을 남긴 뒤 이번 시험 컨테이너만 정리한다.

### Task 5 Fix Round 2

- filename 누락 시험만 먼저 `PYTHONUTF8=1 uv run pytest -vv tests/api/test_projects.py::test_upload_rejects_missing_filename_before_reading_or_persisting`로 재현해 `1 passed in 0.57s`를 확인했다. 실제 400이며 422와의 결과 불일치는 없다. filename 없는 file은 두 번째 text field이므로 Starlette의 headers 처리에서 max_fields=1을 초과해 MultiPartException을 낸다. route의 공통 400 번역이 적용되어 type/shape의 422 검사는 실행되지 않는다.
- 변경: filename 누락과 빈/공백/잘못된 확장자 거절 시험에서 공통 error code·정확한 message·서버 request ID 전체 DTO를 확인한다. 기존 read 0·저장소 미호출·생성된 UploadFile close 검증을 유지했다. production 코드는 바꾸지 않았다.
- 확인: 두 요청 시험 파일 `70 passed, 1 skipped in 1.60s`; repo layout `5 passed in 0.29s`, diff whitespace 통과. 이번에는 DB를 새로 만들거나 연결하지 않아 기존 실제 DB CRUD 시험 1개만 skip했다. 부모 요청대로 production 변경이 없으므로 전체 suite는 다시 실행하지 않았으며 직전 Fix Round 1의 전체 결과는 `1033 passed, 37 skipped`이다. raw/text 수명 Minor는 최종 검토까지 보류한다.

### Task 7 — D5 실행 및 영속 대화

- 변경: `backend/services/d5.py`, `backend/conversations/`, `db/014_conversations.sql`, 관련 테스트와 폴더·DB 설명. D5 그래프 하나만 사용하고 API는 추가하지 않았다. 업로드·데모 연결을 기존 대상 부품 형식으로 바꾼다.
- RED: 서비스·SQL 부재를 확인했고, DB의 잘못된 결과 형식·다른 대화의 실행 연결·중복 종료 시험도 각각 먼저 실패했다. 격리 PostgreSQL만 사용, 실제 모델·검색 호출 없음.
- 검증: 전용 볼륨 없는 postgres 컨테이너에서 `uv run pytest -q tests/services/test_d5.py tests/conversations tests/multi_agent` 151 passed; `uv run pytest -q tests/repo/test_repo_layout.py` 5 passed; `uv lock --check` 통과. 전체 `uv run pytest -q` 첫 실행은 인증 기본 표 미준비로 14 failed, 1030 passed, 37 skipped; 격리 DB에 003/005/006을 준비한 재실행은 1044 passed, 37 skipped. 이후 안전 결과 SQL과 중복 종료 보호를 추가하여 집중 테스트로 재검증했다.
- 한계: 모델·MCP 실호출, 공유 DB·배포, 동결 평가셋 재측정은 하지 않았다. D5Service는 인증·DB 결과 저장을 직접 처리하지 않으며 후속 API가 소유권 검증과 저장을 연결해야 한다. Windows psycopg async는 SelectorEventLoop가 필요하다.

- 추가 검증: 실제 checkpoint가 프로젝트 cascade만으로 지워지지 않는 RED를 확인했다. `D5Service.delete_thread`는 라이브러리 `adelete_thread`로 checkpoint를 정리하며 격리 DB에서 검증했다. 프로젝트 삭제와 원자적 결합·실행 중 삭제 경계는 미구현으로 Task 8 연동 및 Task 13 E2E가 필요하다. `str(threads.id)`가 LangGraph thread_id 정본이다.


### Task 8 — 대화 API와 D5 실행 스트림

- RED: 공개 DTO 부재·대화 API 404, interrupt 복구 DTO, 공개 판정 필드, 인용 메타데이터, 가격 필드 및 중첩 SQL 제약을 각각 실패 테스트로 확인했다.
- 구현: 소유자별 thread/run 조회·생성·재개, 인증·Origin, SSE, 허용된 DTO, terminal 저장 후 전송, 연결 종료 후 백그라운드 실행. 공개 판정/인용만 저장하며 요청 ID와 가격·재고는 저장하지 않는다. 프로젝트 행 잠금으로 활성 실행 중 삭제와 새 실행 경쟁을 방지하고 체크포인터 API로 삭제한다. SQL 결과 검증은 허용 키와 중첩 타입을 검사한다.
- Task 8 검토 반영: 복수 역할 인터럽트의 선택값을 허용 목록으로 검증해 같은 checkpoint에 전달하고, terminal 상태 저장의 일시적 DB 오류는 3회 안에서 제한 재시도한다. `uv run pytest -q tests/api/test_conversations.py tests/conversations/test_dto.py tests/services/test_d5.py` 결과는 20 passed이며 재검토는 최종 검토로 미뤘다.
- Task 9·10 UI: 안전 DTO/SSE 상태 머신, 질문·진행·추가 입력·근거·5종 판정·가격/비활성 승인 패널, 3열 작업대와 900px 이하 프로젝트 drawer·결과 tab을 연결했다. 연결 종료는 run GET만 조회하고 질문을 재전송하지 않는다. focused Vitest 13 passed, production build 성공. Playwright smoke는 가짜 API 전용으로 작성했고 Task 13 전체 검증에서 실행한다.
- Task 11·12 승인·견적: 완료된 성공 판정 후보만 메시지당 한 번 승인하고 immutable snapshot으로 가격 없는 견적·승인 사례를 저장한다. Python과 PostgreSQL이 중첩 가격·재고·URL·조회 시각 키를 거절한다. UI는 후보·판정명을 다시 확인하고 승인 전 견적을 막으며 견적을 열 때 가격을 새로 조회한다. backend focused 31 passed, frontend focused 12 passed와 build 성공.
- 확인: 격리 PostgreSQL 컨테이너에서 `uv run pytest -q tests/api/test_conversations.py tests/conversations tests/services/test_d5.py tests/api/test_projects.py` → 71 passed. 이전 layout 검사 5 passed, 집중 DB 검사 73 passed(이후 문서 근거 보완 전). 실제 모델·MCP, 공유 DB, 배포, 동결 평가셋 재측정은 하지 않았다.
- 한계: checkpoint와 프로젝트 삭제는 별도 트랜잭션으로 원자적이지 않으며 중간 장애 때 checkpoint 일부가 먼저 지워질 수 있다. 서버 재시작·프로세스 중단 시 진행 run 복구, 다중 인스턴스 장애 주입 및 실제 checkpointer cascade는 Task 13에서 검증한다. 문서 근거는 최종 보고서에서 인용한 청크의 메타데이터만 반환한다.

### Task 13 — 전체 서비스 흐름 검증

- 범위: 업로드 정규화 → 사용자 소유 프로젝트·대화 → D5 추가 입력/완료 → 근거·판정 → 명시적 승인 → 가격 없는 견적·승인 사례 삭제를 실제 저장소/service·격리 PostgreSQL과 브라우저 가짜 API 흐름으로 검증했다. 전체 backend suite의 API 시험은 별도로 함께 통과했다. 외부 모델·MCP·Mouser, 공유 DB, 배포는 호출하지 않았다.
- backend 전체: 전용 볼륨 없는 `postgres:16-alpine`의 일회용 `ci_auth` DB에 003/005/006/013/014/015 migration과 `anon`/`authenticated` NOLOGIN 역할을 준비했다. 최초 실행의 15 failures는 CI 인증 스키마 초기화 누락과 신규 `frontend/e2e/` 폴더 설명 누락 때문이었고, 시험 환경·트리 설명을 바로잡은 뒤 `PYTHONUTF8=1 uv run pytest -q` 결과 `1082 passed, 37 skipped in 86.85s`. 신규 전체 흐름은 타 사용자 접근 거절, PostgreSQL의 중첩 가격 키 거절, 프로젝트 cascade까지 포함한다. `uv lock --check`도 통과했다.
- frontend 전체: 최초 Vitest가 Playwright `e2e/*.spec.ts`를 단위 테스트로 수집해 실패하여 Vite test exclude에 `e2e/**`를 추가했다. 이후 `npm ci`는 취약점 0건, `npm run test:run`은 13 files·62 tests 통과, `npm run build` 성공. Playwright Chromium 설치 후 최초 E2E는 과도한 `**/api/**` 패턴이 `/src/api/client.ts`까지 가로채는 문제를 발견했고, 호스트 루트 `/api/`만 가로채도록 고쳐 `npx playwright test --reporter=line` 2 passed.
- 보안·무결성: 승인 뒤 승인 사례 query를 무효화해 사용자별 캐시를 갱신한다. quote 요청 본문은 수량만 보내고, 화면 가격·재고 응답은 견적/사례 저장 DTO와 DB snapshot에 들어가지 않는다. 복합 소유자 FK·RLS/권한 회수·재귀 금지 키 CHECK와 전체 서비스 시험을 유지했다. worktree 경로를 읽지 못한 최초 Docker 호출은 유효 검사로 세지 않았고, 코드 커밋 `43fb8f2`를 임시 일반 clone으로 만든 뒤 CI와 같은 gitleaks 전체 Git 이력 검사 결과 탐지 0건·종료 코드 0이었다. 임시 clone은 검사 뒤 삭제했다.
- 남은 경계: 실제 외부 공급자·MCP·모델과 배포 환경, 프로세스 재시작 중 run 자동 복구, checkpoint 삭제와 프로젝트 삭제의 단일 트랜잭션 원자성은 확인하지 않았다. `README.md`·`SPEC.md`·ADR은 조장 소유이므로 수정하지 않았으며, 조장은 D5 로컬 실행·전체 사용자 흐름과 위 장애 경계를 정본 문서에 반영할지 검토해야 한다.

### 최종 독립 검토 1회 반영

- 검토 이슈 1: 같은 품번이 `results`와 `shown`에 서로 다른 verdict로 나타나면 품번만 보낸 승인이 다른 판정을 저장할 수 있었다. 화면 선택값을 후보 index로 분리하고 API가 `{candidate_part, verdict}` 쌍을 요구하며 service가 두 값이 모두 같은 후보만 snapshot으로 고르도록 수정했다. 누락 verdict 422와 중복 품번의 명시 verdict 선택을 회귀 시험으로 고정했다.
- 검토 이슈 2: checkpoint를 thread별 외부 트랜잭션으로 먼저 지우던 삭제는 중간 실패 때 일부만 지울 수 있었다. 서비스와 업무 표가 같은 `DATABASE_URL`을 쓰는 계약에 맞춰 checkpoint 세 표와 project cascade를 project 행 잠금이 유지되는 단일 PostgreSQL 트랜잭션으로 옮겼다. 격리 DB에서 실제 checkpoint 삭제·project cascade, 실행 시작과의 직렬화, cleanup 중 오류의 전체 rollback을 확인했다.
- 검토 방식·확인: 허용된 독립 최종 검토는 이 1회로 끝냈고 재검토는 하지 않았다. 수정 뒤 backend focused·실제 DB·repo layout `33 passed`, frontend focused `2 passed`, production build, 브라우저 E2E `2 passed`를 확인했다. Task 13의 전체 suite와 gitleaks는 앞서 한 번 수행한 결과를 유지하며 다시 실행하지 않았다.

### 교체 대상 부품 주변 연결 개념도

- 목적·범위: 기존 `OSC` 작업대의 가운데 회로 요약을 프로젝트 `connections`와 안전한 D5 결과에 연결된 SVG 개념도로 확장했다. 실제 PCB·회로도, 이미지 생성·검색, 새 그래프 라이브러리, 업로드·견적 저장 확장은 추가하지 않았다. 루트 `SPEC.md`와 `docs/adr/`도 수정하지 않았다.
- 기능 계약: `docs/specs/circuit-context-diagram.md`에 Why·Goal·What·How·AC를 작성했다. 연결 adapter는 `backend/graph/nodes.py::circuit_around`와 같은 net 순서, `MAX_NET_NODES=8`, 통과 부품 연결 net 수 3 이하 규칙을 사용한다. 대상은 중앙, 직접 연결은 안쪽, 2단계 연결은 바깥쪽·낮은 대비로 표시한다. 현재 연결 DTO에는 방향이 없어 SVG marker·화살표를 만들지 않는다.
- 실제 연결: 인증된 프로젝트 상세 API의 `parts|components`·`nets`, SSE/복구 run 결과의 역할 코드·근거·후보·판정·citation을 사용한다. 역할명은 `roles.yaml` 정본에서 `code`·`name`만 반환하는 인증된 `GET /api/judge/roles`로 제공한다. 사용 조건은 D5 요청에 실제로 보낸 원문만 화면 메모리에서 표시하며 후보 데이터시트 `checks.value`를 회로 조건으로 오인해 표시하지 않는다. production 코드에는 test fixture import나 실패 시 fixture fallback이 없다.
- 후보 연동: 판정 행을 선택하면 같은 후보의 check/package citation을 기존 근거 패널에 표시한다. 같은 품번이 다른 verdict로 중복될 수 있어 품번 문자열이 아니라 후보 index로 선택 상태를 유지한다.
- TDD/검증: 역할 API 미구현 404, adapter/component module 미존재, 후보 선택·Workbench 전달 부재를 RED로 먼저 확인했다. 최종 `npm run test:run`은 `15 files, 76 tests passed`, `npm run build`는 TypeScript와 Vite production build 성공, `uv run pytest -q tests/api/test_conversations.py tests/repo/test_repo_layout.py`는 `15 passed in 3.25s`, `git diff --check`는 통과했다. 외부 모델·MCP·공급자 API와 공유/배포 DB는 호출하지 않았다.
- fixture와 미확인: `breadboard_supply` D1의 `J1`, `S1`, `F1`, `U1` 및 무방향 선 AC는 실제 저장소 sample을 축약한 frontend test fixture로 검증했다. 이 작업에서 브라우저가 실제 배포 서버에 연결된 상태의 업로드→변환→D5 모델 실행은 재실행하지 않았다. 기존 `.net` 업로드·`connections` 정규화와 프로젝트/run API는 존재하지만, 실제 모델·MCP 응답 및 배포 환경 round-trip은 별도 운영 검증이 필요하다. run을 새로 시작할 때 입력한 사용 조건은 표시되지만 기존 safe result에는 구조화된 원 사용자 조건이 없어 페이지 재접속 뒤 복원하지 않는다.
- 다음 할 일: 조장이 아래 제안 문구를 루트 `SPEC.md`의 작업대/API 절에 반영할지 검토한다. 배포 환경에서 공개 demo와 실제 `.net` 업로드 각각 한 번의 authenticated round-trip을 확인하고, 재접속 뒤 사용 조건 복원이 필요하면 safe result 계약을 별도 기능으로 설계한다.

### 로컬 프론트 더미 로그인

- 원인: `5173`의 OSC Vite는 정상 실행됐지만 프록시 대상 `localhost:8000`은 현재 작업트리 서버가 아니라 `proj3-b-sth-api-1` Docker 컨테이너였다. 이 서비스의 `/api/auth/me` 401은 현재 공통 오류 계약 대신 `{"detail":"로그인이 필요합니다."}`를 반환해 프론트가 일반 요청 오류로 표시했다.
- 변경: `VITE_DUMMY_AUTH=1`이면서 Vite 개발 모드일 때만 인증 API 호출 없이 ID 0의 일반 더미 사용자로 시작한다. production build에서는 플래그가 있어도 비활성이고 프로젝트·역할 등 업무 API 응답은 더미로 대체하지 않는다. `docs/specs/login-auth.md`와 `frontend/FRONTEND.md`에 이 경계를 기록했다.
- TDD/검증: 신규 시험이 기존 구현에서 `1 failed, 2 passed`로 RED인 것을 확인했다. 구현과 production 차단 시험을 추가한 뒤 `npm run test:run -- src/auth/AuthProvider.test.tsx src/pages/LoginPage.test.tsx`는 `2 files, 7 tests passed`, `npm run build`와 `git diff --check`는 통과했다. Vite를 플래그와 함께 재시작하고 브라우저가 `/app`의 `회로 작업대`와 `로그아웃`을 표시하는 것을 확인했다.
- 남은 것: 로그인 경계만 임시 통과한 상태다. `proj3-b-sth-api-1`은 현재 OSC의 프로젝트·역할 API 계약과 맞지 않아 작업대의 실제 데이터 요청은 계속 실패한다. 현재 작업트리 FastAPI와 격리 DB를 별도 포트에 올리고 Vite proxy를 맞추는 작업은 아직 하지 않았다.

### Flux형 기본 다크 프론트엔드

- 범위: 로그인·관리자·작업대·drawer·표·상태·승인/견적·SVG 연결 개념도를 기본 다크 테마로 통일했다. Flux PCB Editor 문서의 편집기 셸과 panel 위계를 참고하되 화면 구조·브랜드를 복제하지 않았고, API·인증·데이터 계약·연결 의미는 바꾸지 않았다.
- 설계/계획: `docs/superpowers/specs/2026-11-09-dark-frontend-design.md`와 `docs/superpowers/plans/2026-11-09-dark-frontend.md`에 색상 토큰, 반응형, 접근성, 구현·검증 범위를 기록했다. 라이트 모드·전환 버튼·외부 폰트·새 라이브러리는 추가하지 않았다.
- TDD: `LoginPage.test.tsx`에 기본 `color-scheme: dark`, canvas `#0b0f14`, trace `#35d0ba` 계약을 먼저 추가했고 기존 CSS에서 `expected dark, received normal`로 RED를 확인했다. Vitest 기본값이 CSS를 DOM에 주입하지 않아 `vite.config.ts`의 test `css: true`만 추가했으며 Node 타입이나 의존성은 늘리지 않았다.
- 구현: `styles.css`에 의미 토큰, 어두운 sticky tool bar, panel 깊이, form·표·오류·경고·선택 상태, 키보드 focus와 reduced-motion을 적용했다. 연결 개념도에는 20px 격자, 청록 직접 연결, 낮은 대비 2단계 연결, 대상 부품의 제한된 glow를 적용했고 marker/화살표는 추가하지 않았다.
- 검증: 로그인·관리자 집중 `10 passed`, 작업대·개념도 집중 `21 passed`, 전체 `15 files / 79 tests passed`. `npm run build` 성공, repo layout `5 passed`, `git diff --check` 통과. 브라우저에서 1440×900 3열 작업대와 390×844 프로젝트 버튼·결과 tab 전환형 레이아웃을 확인한 뒤 viewport를 복원했다.
- 확인하지 못한 것: 현재 `localhost:8000`은 다른 `proj3-b-sth-api-1` 컨테이너라 실제 프로젝트·역할 데이터는 오류 상태다. 다크 화면의 정상·오류·빈 상태는 확인했지만 현재 OSC backend와 실제 데이터가 연결된 브라우저 흐름은 별도 후속 작업이다.

### 개발 전용 전체 더미 흐름

- 목적·범위: 사용자가 현재 다크 작업대에서 로그인부터 프로젝트 선택, D5 분석, 근거·판정, 사람 승인, 가격 조회, 가격 없는 견적 저장, 승인 사례 삭제까지 직접 조작하도록 개발 전용 비영속 API를 추가했다. 실제 LLM·RAG·Mouser·DB·업로드 변환은 호출하지 않는다.
- 설계 경계: `DEV && MODE === 'dummy'`일 때만 공통 `apiRequest`가 메모리 API를 사용한다. 일반 `npm run dev`와 production build는 기존 실제 `/api` 경계를 유지한다. 정의되지 않은 더미 API는 실제 서버로 fallback하지 않고 공통 404를 반환하며, 화면에 `더미 실행 모드 · 저장되지 않음`을 표시한다.
- TDD RED: mode 판별 export 부재로 client test `1 failed`, 메모리 API 미구현으로 dummy test `4 failed`, mode 인증·고지 부재로 auth/App test `3 failed`, 일반 개발 서버의 브라우저 흐름은 더미 고지가 없어 `1 failed`를 각각 확인했다.
- 구현: `frontend/src/api/dummy.ts`가 `breadboard_supply`의 D1·J1·S1·F1·U1 연결, R01 역할 근거, SS34 판정·데이터시트 위치, SSE, 승인·사례·견적·조회 순간 가격을 실제 DTO 형태로 제공한다. 상태는 모듈 메모리에만 있고 견적 JSON에는 가격·재고 필드가 없다. `npm run dev:dummy`와 route 가로채기 없는 Playwright 흐름을 추가했다.
- 검증: focused API `12 passed`, auth/App `21 passed`, 신규 직접 더미 E2E `1 passed`. 전체 `npm run test:run`은 `16 files / 87 tests passed`, `npm run build` 성공, `npm run e2e`는 기존 2건과 신규 1건 모두 통과했다. `uv run pytest -q tests/repo/test_repo_layout.py`는 `5 passed`, `git diff --check`는 CRLF 안내 외 오류 없이 통과했다. `127.0.0.1:5173`을 dummy mode로 다시 띄우고 브라우저에서 프로젝트·D1·R01·SS34 판정·승인·더미 가격·수량 2의 가격 없는 견적 저장까지 직접 확인했으며 사례 삭제는 같은 서버를 사용하는 E2E에서 확인했다.
- 확인하지 않은 것: 이 기능은 의도적으로 외부 서비스와 실제 DB를 검증하지 않는다. production bundle은 더미 모드를 실행하지 않지만 배포 환경 round-trip 검증은 이번 범위가 아니다. 커밋·push·PR은 만들지 않는다.

## 2026-11-10 D5 작업대 UI 개선 및 최신 main 동기화

### D5 작업대 정보 구조 개선

- 목적·범위: 기존 다크 PCB 토큰을 유지하면서 상단 앱 바, 축소 기능 레일, 넓은 D5 분석 작업면, 너비 조절·접기 가능한 우측 정보 콘솔의 4영역 구조로 재배치했다. Zenode 스크린샷에서는 높은 정보 밀도, 기능 레일, 넓은 주 작업면, 우측 자료 패널, 제한된 상태 motion만 참고했고 색상·브랜드·고유 화면은 복제하지 않았다.
- 실제 계약: 기존 project API, 인증 상태, `useRunStream` SSE/GET 복구, 안전 DTO, 승인·가격 없는 견적 API를 그대로 사용한다. 검색은 현재 불러온 프로젝트와 회로 부품만 대상으로 하며, 활동에는 실제 수신한 run 상태만 쌓는다. production fixture fallback·가짜 퍼센트·공개 회원가입·가격/재고 저장은 추가하지 않았다. `frontend/src/api/`와 `frontend/src/hooks/` 계약 파일은 수정하지 않았다.
- 화면·상호작용: 회로·근거·판정·활동 탭, 프로젝트 목록/생성, citation 상세, 후보 상세, 승인 확인, 견적 만들기, 계정 요청 안내를 구현했다. 공통 `AccessibleDialog`가 focus trap, Esc, focus 복귀를 제공하고 승인 확인은 backdrop 클릭으로 닫히지 않는다. 900px 이하 결과 영역·하단 기능 레일, 520px 이하 단일 열 dialog, reduced-motion을 적용했다.
- TDD/회귀: 새 shell·로컬 검색·계정 안내·승인/견적 dialog 시험이 기존 화면에서 4건 RED인 것을 먼저 확인했다. focus 복귀 2건과 기존 project 컴포넌트 13건은 새 dialog/drawer 경로를 반영해 고쳤으며, 데모 query의 메모리 cache 계약은 유지했다. 최종 `npm run test:run`은 `16 files / 92 tests passed`다.
- 브라우저·빌드: `npm run e2e -- --reporter=line`은 실제 탭 전환을 포함한 D5 완료 흐름, 개발 더미 전체 흐름, 승인→가격 조회→가격 없는 견적→사례 삭제, 1440×900·390×844 및 reduced-motion의 `4 passed`. `npm run build`와 `uv run pytest -q tests/repo/test_repo_layout.py`는 각각 성공 및 `5 passed`. `git diff --check`를 마지막 diff에서 다시 확인한다.
- 문서: `docs/specs/workbench-information-architecture.md`에 Why·Goal·What·How·AC를 작성하고, 새 파일만 `SOJAFIT.md`, `docs/specs/SPECS.md`, `frontend/src/SRC.md`에 등록했다. 루트 `SPEC.md`와 `docs/adr/`는 수정하지 않았다.
- 확인하지 못한 것: Playwright의 정상 흐름은 로컬 fake backend 또는 명시적 dummy mode다. 실제 배포 인증·FastAPI·PostgreSQL·모델·MCP·Mouser를 연결한 round-trip, 실제 사용자 데이터의 장시간 SSE 연결, 배포 브라우저별 시각 회귀는 실행하지 않았다. backend 코드 변경이 없어 전체 backend suite는 다시 실행하지 않았다.
- UX 검수 후속: 더미 프로젝트 생성·업로드 경로, 모바일 대상 선택, 단계 안내, 완료 뒤 후보 비교 이동, 근거/후보 CTA, 실패 재시도, 한국어 추가 조건 라벨, 승인 뒤에만 가격·견적 노출, 목록·가격·Google 상태 오류 복구, 단일 main과 탭·검색 키보드 계약을 보완했다. 우측 패널 안에서 dialog가 잘리던 문제는 body portal로 고쳤고, 빈 작업대에서는 정보 패널을 기본 축소한다.
- 후속 검증: 각 변경은 실패 시험을 먼저 확인했다. 최종 `npm run test:run`은 `16 files / 106 tests passed`, `npm run build` 성공, `npm run e2e`는 더미 생성·분석·근거·후보 비교·승인·가격 없는 견적·사례 삭제와 1440/390px 반응형을 포함해 `4 passed`다. 실제 배포 backend·DB·모델·MCP·공급자 연결은 이번 UI 범위에서 실행하지 않았다.
- 패널 발견성·크기 조절 후속: 왼쪽 아이콘 전용 기능 레일을 기본 220px의 `작업 메뉴`로 열어 항목명을 즉시 보이게 하고, 왼쪽 메뉴와 오른쪽 회로·분석 정보 경계에 마우스 drag 및 방향키 조절이 가능한 separator를 추가했다. 데스크톱은 각각 160~320px, 320~620px 범위로 제한하고 모바일은 기존 하단 메뉴를 유지한다. 신규 시험 2건의 RED를 확인한 뒤 전체 Vitest `16 files / 108 tests`, production build, Playwright `4 passed`, `git diff --check`를 통과했으며 dummy mode의 데스크톱 화면에서 양쪽 손잡이를 직접 확인했다.
- 우측 패널 확장 후속: 상단 `너비` range를 제거하고 경계 separator만 남겼다. 우측 패널은 화면 너비의 최대 50%까지 왼쪽으로 확장하되 중앙 분석 영역 480px을 우선 보존하며 최소 320px을 유지한다. 기존 구현에서 range가 남아 있는 RED를 확인한 뒤 Workbench 집중 `14 passed`, 전체 Vitest `16 files / 108 tests`, production build, Playwright `4 passed`를 통과했다.
- 접힌 작업 메뉴 경계 후속: 전역 `nav`의 wrap·gap·정렬이 작업 메뉴에 남아 접힌 58px 영역 밖으로 버튼이 87.5px까지 돌출되는 현상을 브라우저 RED로 재현했다. 작업 메뉴는 column nowrap·gap 0·stretch를 명시하고 접힌 상태의 라벨을 layout에서 제거하며 버튼을 가운데 정렬했다. 각 버튼 bounding box가 메뉴 경계 안에 들어오는 E2E를 추가한 뒤 전체 Vitest `108 passed`, production build, Playwright `4 passed`를 통과했다.
- 대화 영역 고정 후속: 프로젝트 생성 전에도 중앙에 비활성 분석 대화와 입력창을 노출하고, 데스크톱에서는 대화 내역만 세로 스크롤되며 입력창은 중앙 작업면 하단에 고정되도록 영역을 분리했다. 모든 스크롤바는 기존 청록 브랜드 토큰을 사용한다. 빈 프로젝트 노출과 입력창 좌표 고정 시험의 RED를 먼저 확인한 뒤 집중 Vitest `25 passed`, 전체 Vitest `108 passed`, production build, Playwright `5 passed`를 통과했으며 dummy mode 실제 화면도 확인했다.
- 작업 메뉴·프로젝트 선택 후속: 왼쪽 작업 메뉴에서 중앙 입력창과 중복되던 `분석 대화` 항목을 제거하고 모바일 하단 메뉴를 5열로 맞췄다. 상단 현재 프로젝트 이름은 기존 `내 프로젝트` dialog를 여는 버튼으로 바꾸어 선택 상태와 로직을 재사용한다. 두 동작의 RED를 먼저 확인한 뒤 집중 Vitest `15 passed`, 전체 Vitest `109 passed`, production build, Playwright `5 passed`를 통과했으며 dummy mode에서 간소화된 메뉴를 확인했다.
- 브랜드 색상 후속: 고채도 청록 토큰을 저채도 파스텔 민트 `#7ec2b5`, 밝은 강조 `#a7d8cf`, 어두운 선택 배경 `#1a3431`로 조정하고 상태 표시의 하드코딩 청록도 같은 토큰 계열로 통합했다. 토큰과 실제 scrollbar computed color의 RED를 확인한 뒤 집중 Vitest `20 passed`와 Playwright 색상 검사를 통과했다.
- 프로젝트 미선택 초기 화면 후속: 기존 작업대의 비활성 입력창 대신 회로 패턴·중앙 질문 입력·빠른 시작 질문을 갖춘 SojaFit 랜딩을 표시한다. 질문이 있어야 `분석 시작`이 활성화되고, 프로젝트 생성 dialog를 여닫거나 데모 프로젝트를 만든 뒤에도 질문과 사용 조건 초안이 기존 분석 입력창으로 이어진다. 프로젝트를 이미 선택한 작업대 구조와 API 계약은 바꾸지 않았다. 신규 Vitest와 Playwright를 RED부터 추가했고 최종 전체 Vitest `16 files / 110 tests passed`, production build 성공, Playwright `5 passed`, `git diff --check` 통과를 확인했다. dummy mode 모바일 화면을 직접 검수해 브랜드와 설명이 겹치던 배치를 분리했으며 실제 배포 backend·DB·모델·MCP·공급자 연결은 실행하지 않았다.
- 랜딩 서비스 소개 후속: 프로젝트 미선택 랜딩을 아래로 스크롤하면 `회로 맥락 확인 → 근거 기반 후보 비교 → 사람 승인`의 실제 SojaFit 흐름을 세 구간으로 소개하고, 마지막 `질문 입력하기`가 상단 질문 입력으로 복귀한다. 외부 이미지·가짜 수치·API/블로그·미완성 기능 문구는 넣지 않았으며 프로젝트 선택 뒤 작업대에서는 소개가 렌더링되지 않는다. 랜딩에만 `#171c22` 기반의 밝은 차콜 팔레트를 적용해 기존 작업대의 어두운 대비는 유지했다. 1440×900 교차 배치와 390×844 단일 열·가로 넘침·고정 하단 메뉴 간격을 브라우저에서 확인했고, 최종 전체 Vitest `16 files / 112 tests passed`, production build 성공, Playwright `5 passed`를 확인했다.
- 랜딩 브랜드 선명도 후속: 앱과 작업대의 로고 표기를 `SOJAFIT`으로 통일하고, 중앙 브랜드 마크는 아이콘과 글자를 같은 1.5배 비율로 확대했다. 랜딩 전용 텍스트 토큰과 제목·설명의 명도·굵기를 높이고 중앙의 작은 `회로 기반 부품 대체 분석` 문구는 제거했다. 1440×900과 390×844 실제 화면에서 로고 비율, 가독성, 가로 넘침이 없는 것을 확인했다.
- 측면 패널 애니메이션 후속: 데스크톱 좌측 작업 메뉴와 우측 정보 패널의 grid 폭을 240ms 동안 전환하고, 펼칠 때 내부 내용이 각 측면에서 들어오도록 했다. 모바일 레이아웃과 `prefers-reduced-motion`에서는 동작을 끈다. 실제 브라우저에서 우측 폭 `48 → 374 → 430px`, 좌측 폭 `220 → 82 → 58px`의 중간 프레임을 확인했다.
- 빠른 시작 레인 후속: 실제 회로·부품 질문 예시를 30개로 늘려 무작위 순서의 3개 레인에 10개씩 배치하고, `좌→우 / 우→좌 / 좌→우` 방향으로 화면 밖까지 흐른 뒤 반복하도록 했다. 레인 폭은 화면 크기와 같은 `100vw`이며 문서 가로 넘침은 만들지 않는다. 5가지 파스텔 색상, 가리키거나 포커스한 한 줄만 일시 정지, 클릭 시 질문 입력, reduced-motion 정적 가로 목록을 적용했다. 랜딩 본문·입력·예시 글자도 1px 안팎 키우고 굵기를 보강했으며 1920px 화면에서 레인 폭 `1920px`, 문서 가로 넘침 `0px`을 확인했다.
- 빠른 시작 선택 대비 후속: 공통 버튼 hover가 예시 칩을 밝은 민트 배경으로 바꾸고 `brightness(1.18)`까지 적용하던 문제를 제거했다. 각 색상의 원래 글자색을 유지하고 같은 계열의 어두운 hover 배경만 사용해 선택 중에도 문구가 읽히도록 했다.
- 계정 메뉴 후속: 좌측 작업 메뉴 하단의 계정 버튼을 제거하고 우측 상단 사용자 버튼에 계정 메뉴를 통합했다. 비로그인 상태는 실제 `/login` 이동, 로그인 상태는 개인 설정·로그아웃, 관리자는 사용자 관리 이동을 제공한다. 서버 개인 설정 API가 없어 가짜 프로필 저장은 만들지 않고, 개인 설정에는 현재 브라우저 `localStorage`에 저장되며 실제 화면 애니메이션을 끄는 `동작 효과 줄이기`만 제공한다.
- 랜딩 회로 배경 후속: 프로젝트 미선택 첫 화면에 전용 회로 일러스트를 추가했다. PCB 배선·via·소자 풋프린트·다이오드와 수동소자 기호는 양쪽 가장자리에 배치하고, 중앙 제목과 입력창 뒤는 비워 가독성을 유지했다. 파스텔 민트·스틸 블루·소량의 앰버를 기존 밝은 차콜 팔레트에 맞추고, 중앙 어두운 완충 그라데이션과 모바일 cover crop을 적용했다. 이미지에는 글자·숫자·로고·워터마크를 넣지 않았다.
- PR 전 저장소 구조 규칙 보완: `AGENTS.md`의 문서 위계·지킬 것 9·팀 규칙 3·10, `SOJAFIT.md`의 이름 규칙·파일 생성 절차, `tests/repo/test_repo_layout.py`를 확인했다. 새 랜딩 관련 설계·계획 5개, `LandingServiceIntroduction.tsx`, `frontend/public/sojafit-circuit-hero.png`를 `SOJAFIT.md` 트리에 설명과 함께 등록했다. 새 두 단계 폴더 `frontend/public/`에는 규칙대로 `PUBLIC.md`를 만들고 `frontend/FRONTEND.md`와 폴더 설명 표에도 연결했으며, `docs/superpowers/SUPERPOWERS.md`의 실제 설계·계획 목록을 동기화했다. 최초 전체 `uv run pytest -q`는 구조 문서 누락으로 `3 failed, 1071 passed, 113 skipped`였고, 보완 뒤 `uv run pytest -q tests/repo/test_repo_layout.py`는 `5 passed`, 최종 전체 `uv run pytest -q`는 `1074 passed, 113 skipped`였다. 프론트 Vitest `112 passed`, production build, Playwright `5 passed`, `git diff --check`도 통과했다. 읽기 전용 `git fetch origin main` 뒤 `git merge-tree`로 현재 변경을 시뮬레이션하니 `OSC` 기준 커밋이 최신 `origin/main`보다 99커밋 뒤였고 추적 파일 18개에서 충돌이 예상됐다. 실제 원격 push·PR 생성·병합은 하지 않았으며, 다음 단계는 최신 `main`을 반영해 충돌을 해결한 뒤 같은 검증을 다시 수행하는 것이다.
- 최신 main 동기화·충돌 해결: 미커밋 UI 변경과 신규 파일을 `backup-before-main-sync-20261110-landing-ui` stash(`82e78f7`)로 백업한 뒤 `OSC`를 `origin/main` `b683d9e`까지 fast-forward하고 백업을 적용했다. 충돌 18개는 최신 main의 회원가입·내 설정·데모 질문 재생·프로필 힌트·역할명·후보 정규화 계약을 유지하면서 랜딩, 작업대, dialog, 반응형 UI를 통합했다. main에서 AI 도구 흔적 정리로 삭제된 `docs/superpowers/`는 되살리지 않았고 백업 stash에는 계속 보존했다. 동기화 뒤 `origin/main...HEAD`는 `0 0`, 미해결 충돌 파일은 0개다.
- 동기화 후 검증: `uv run pytest -q`는 `1204 passed, 112 skipped`, `npm run test:run`은 `18 files / 133 tests passed`, `npm run build`는 TypeScript와 Vite production build 성공, `npm run e2e`는 랜딩·작업대·더미 전체 흐름을 포함해 `5 passed`였다. `uv lock --check`, staged whitespace 검사, Docker gitleaks stdin(`--redact --no-banner --log-level warn`)도 통과했다. 이 검증은 로컬 코드·fixture·더미/fake backend 범위이며 실제 배포, 외부 모델·MCP·Mouser, 공유 DB round-trip은 실행하지 않았다. 커밋·push·PR 생성은 하지 않았다.

### 검증된 회로 원본과 데이터시트 패키지 근거

- 목적·범위: 작업대에서 개념 연결도와 실제 회로 원본을 구분해 볼 수 있도록, 출처와 라이선스뿐 아니라 데모 회로와의 일치까지 확인한 4건에만 원본 회로 이미지를 연결했다. `breadboard_supply`는 수집한 PTH 회로와 공개 SMD 이미지가 달라 최종 검토에서 제외했고, `attiny85_time_switch`와 사용자 업로드도 원본 탭 없이 개념도만 유지한다.
- 회로 자산 계약: `data/circuits/visuals.json`에 원본 URL·저장소·commit·라이선스 증거·귀속·원본/제공 파일 SHA-256을 기록하고, API에는 브라우저에 필요한 안전한 메타데이터만 노출한다. 정적 PNG 4개는 `/circuit-schematics/`에서 제공하며, Docker production build에도 포함한다. 원본과 개념도를 같은 것으로 표현하거나 물리적 핀 호환·배선 정답을 보장하지 않는다.
- 데이터시트 근거: 1,360개 manifest와 외부 Docling JSON을 파일명 기준으로 결합해 `data/package-outline-pages.json`을 생성했다. URL 디코딩·casefold 일치를 사용하고 제어문자·위험 scheme을 거절하며, 페이지는 1-based다. 브라우저 응답에만 데이터시트 URL과 근거 페이지를 붙이고 안전 결과 저장 모델과 DB 스키마는 확장하지 않았다.
- 더미·UI: 허구의 `SS34.pdf` 대신 실제 `SS34L SERIES_C2103.pdf`와 `SS34L` 후보를 사용한다. VRRM 근거는 1쪽, 패키지 외형 근거는 4쪽이다. 원본 회로 탭에는 귀속·라이선스·안전한 원문 링크를 표시하고, 데이터시트 근거 링크는 HTTPS 새 탭으로 연다. 판정 문구는 `동일 패키지 가능성`, `기판 변경 가능성 있음`, `패키지 변경 여부 확인 필요`로 제한한다.
- 배포 경계 보완: `Dockerfile`이 `frontend/public/`을 Vite build 전에 복사하고, 런타임은 `frontend/dist`가 있으면 그 결과만 정본으로 사용한다. 따라서 production asset 누락을 개발용 public fallback이 숨기지 않는다. 최종 4종으로 로컬 image `sojafit-verified-visuals-check:local`을 다시 빌드했고 컨테이너에 `attiny85_dev`, `franzininho_diy`, `mosfet_driver`, `pro_micro` PNG만 있음을 확인했다.
- 검증: 최종 작업 트리에서 backend 전체 `1295 passed, 112 skipped`, frontend Vitest `19 files / 152 passed`, production build 성공, Playwright `7 passed`(검증 원본 PNG 브라우저 decode 포함), 저장소 구조 `5 passed`, `uv lock --check`, `git diff --check`를 확인했다. 생성 index는 1,360건이며 SHA-256 `EE961EC12D24227B1C6B2214B466D3D378922097BC9F59E46F7FF69413984B3A`로 재현됐다. 실제 외부 모델·MCP·Mouser·공유 DB·배포 환경 round-trip과 데이터시트 웹 원문의 장기 가용성은 이번 범위에서 검증하지 않았다. 커밋·push·PR은 만들지 않았다.
- 직접 검수용 dummy 보완: 초기 dummy가 원본 미제공 `breadboard_supply` 한 건만 노출해 사용자가 작업대에서 원본 4종을 볼 수 없던 공백을 수정했다. Vite build-time virtual module이 저장소의 실제 6종 `connections.json`과 `visuals.json`을 읽어 프로젝트·데모 API를 구성하며, 검증된 4종은 작업대에서 원본/개념 탭을 모두 제공한다. 손으로 축약한 연결 fixture는 제거했고 Docker frontend build에도 같은 정본 파일을 명시적으로 전달한다.
- 직접 검수용 dummy 검증: backend 전체 `1295 passed, 112 skipped`, frontend Vitest `19 files / 152 passed`, production build, Playwright 전체 `8 passed`, 저장소 구조 `5 passed`, `uv lock --check`, `git diff --check`, Docker image build를 통과했다. 더미 서버 `http://127.0.0.1:5174/app`에서 6종 프로젝트를 선택할 수 있고, `mosfet_driver`, `attiny85_dev`, `franzininho_diy`, `pro_micro`는 원본/개념 탭을, `breadboard_supply`, `attiny85_time_switch`는 개념도만 제공한다.
- 데모 6종 원본 완성: 기존 4종 제한을 제거했다. `breadboard_supply`는 공식 SparkFun 제품 페이지의 v10 PTH PDF와 canonical 20부품/13넷을 대조했고, `attiny85_time_switch`는 고정 commit `3566a94f`의 `attiny85_time_switch_schematic.pdf`를 canonical 연결과 대조했다. 두 PDF의 첫 페이지를 기존 규칙대로 160 DPI PNG로 고정하고 원본/배포 SHA-256, 고정 commit, 라이선스와 attribution을 catalog에 추가했다. 이제 등록된 6종 모두 원본/연결 개념도 탭을 제공하며 업로드만 개념도 전용이다. 계획서의 6종 범위와 모든 실행 체크를 완료 표시했고 commit·push·PR은 만들지 않았다.
- 6종 완료 검증: backend 전체 `1295 passed, 112 skipped`, frontend Vitest `19 files / 153 passed`, production build, 기본 `npm run e2e` `8 passed`, 저장소 구조 `5 passed`, `uv lock --check`, `git diff --check`, Docker image build를 통과했다. 최초 병렬 Playwright는 Windows trace 임시 파일 `ENOENT`로 3건이 인프라 실패했고 `--trace=off --workers=1`에서 8건이 통과했다. 기능 실패가 아닌 trace artifact 경합으로 확인해 기본 설정도 trace를 끈 뒤 병렬 기본 명령 8건 통과를 다시 확인했다. `127.0.0.1:5174`에서 6개 PNG 모두 HTTP 200 `image/png`를 반환한다.

### 판정 설명·승인·예상 상품금액 보강

- 근거 표시: 후보 상세에 필수 조건, 계산 근거, 요구 기준, 후보 데이터시트 값, 시험 조건, 판정 이유, 문서·쪽·표·행 및 안전한 HTTPS 원문 링크를 한 조건표로 표시한다. 백엔드의 구조화된 `checks`만 사용하고 원문이 없는 값은 만들지 않는다. 최종 답변의 줄바꿈도 보존한다.
- 승인 경계: 긍정 verdict라도 `missing`이 있거나 `tier=required` check가 `unverified`이면 프런트 승인 버튼을 비활성화하고, 같은 검사를 backend `approval_snapshot`에도 적용해 직접 API 호출로 우회할 수 없게 했다. 주의 문구만 있는 후보는 차단하지 않는다.
- 견적 설명: 조회된 가격 구간 중 입력 수량에 적용되는 단가를 골라 `수량 × 단가 = 예상 상품금액`을 화면에서 계산한다. 세금·배송비·환율 제외를 명시하고 기존 계약대로 서버에는 수량만 저장한다.
- 더미 흐름: SS34L 예시는 입력 최대 전압 12 V와 최대 순방향 전류 1 A에 안전 여유를 적용해 VRRM `15 V ≤ 40 V`, IF(AV) `1.43 A ≤ 3 A`를 설명한다. 패키지·극성 확인은 별도 주의로 남겼다.
- 검증: TDD RED 뒤 frontend 전체 `19 files / 152 tests passed`, 관련 backend `81 passed`, production build 성공, dummy Playwright `3 passed`를 확인했다. 최초 Playwright 재시도 한 번은 추적 파일 `ENOENT`로 실패해 trace를 끈 깨끗한 실행으로 기능 경로를 재검증했다. 실제 외부 가격 공급자·모델·MCP·공유 DB·배포 환경은 호출하지 않았다.

### 회로 작업대 상단 간소화

- 선택된 프로젝트의 중앙 작업면 상단에서 `부품 대체 분석`, `회로 작업대`, 설명, `결과 보기`, `프로젝트 만들기`를 제거하고 분석 진행 단계만 남겼다. 새 프로젝트 생성은 기능을 잃지 않도록 상단 현재 프로젝트 또는 왼쪽 프로젝트 메뉴로 여는 `내 프로젝트` 팝업의 `새 프로젝트 만들기`로 이동했다.
- TDD RED에서 기존 제목이 남아 있음을 확인한 뒤 수정했다. 관련 작업대 시험 `19 passed`, 영향받은 화면·비동기 프로젝트 시험 `48 passed`, frontend 전체 `19 files / 152 tests passed`, production build 성공, dummy Playwright `3 passed`, `git diff --check`를 확인했다.

### 선택형 사용 조건 입력

- 질문 입력창은 기본으로 항상 표시하고, 별도 `사용 조건 (선택)` 입력창은 `사용 조건 추가(선택)` 버튼을 눌렀을 때만 펼친다. 조건이 있는 초안과 기록 데모는 자동으로 펼치며, 다시 접어도 값은 유지해 기존 `StartRun.conditions` 필드로 별도 전송한다. 랜딩과 선택된 프로젝트의 대화 입력에 같은 동작을 적용했다.
- 기본 비노출과 펼치기 동작을 먼저 실패 시험으로 확인했다. 최종 frontend 전체 `19 files / 152 tests passed`, production build 성공, dummy Playwright `3 passed`, `git diff --check`를 확인했다. backend API와 저장 계약은 수정하지 않았다.

### 원본 회로도 확대·이동

- 우측 정보 패널의 검증된 원본 회로도에 50~300% 범위의 확대·축소, 현재 배율 표시, 화면 맞춤을 추가했다. 확대된 이미지는 마우스나 터치로 끌어 이동할 수 있고 기존 스크롤도 유지한다. 연결 개념도와 원본·출처 데이터 계약은 변경하지 않았다.
- 확대, 드래그 이동, 화면 맞춤 동작을 기존 구현에서 실패하는 시험으로 먼저 확인한 뒤 구현했다. 집중 Vitest `5 passed`, frontend 전체 `19 files / 153 tests passed`, production build, Playwright `8 passed`, `git diff --check`를 통과했다. 최초 Playwright 전체 재실행은 Windows trace 임시 파일 `ENOENT` 2건으로 종료되어, trace를 끈 깨끗한 실행으로 기능 경로를 재검증했다.

### 분석 입력 영역 간소화

- 중앙 질문 입력 영역의 `대상 …` 표기와 `질문과 확인된 조건만 전송합니다.` 안내 행을 제거하고 질문 입력창을 3줄에서 2줄로 줄였다. 사용 조건 선택 입력과 전송 데이터 계약은 유지한다.
- 행동 버튼은 상태별 하나만 표시한다. 분석 전·실패 후에는 `분석하기` 또는 `다시 분석하기`, 실제 실행 중에는 같은 위치에 `분석 취소`만 표시한다.
- 기존 구현에서 두 요구가 실패하는 시험 2건을 먼저 확인했다. 수정 뒤 집중 Vitest `23 passed`, frontend 전체 `19 files / 154 tests passed`, production build, 관련 dummy Playwright `1 passed`를 확인했다.

### 채팅형 분석 입력줄

- 질문 입력을 기본 한 줄 높이로 낮추고 분석 실행·취소 버튼을 입력창 오른쪽 안에 배치했다. 대상 미선택 안내 문구는 제거하고 선택 사용 조건은 기존처럼 별도로 펼치도록 유지했다.
- 입력 내용에 따라 최대 6줄까지 스크롤바 없이 늘어나고 그 이상에서만 내부 스크롤을 사용한다. Enter는 분석을 시작하고 Shift+Enter는 줄바꿈을 유지하며, 한글 IME 조합 중 Enter는 전송하지 않는다. 화면에는 별도 단축키 안내를 추가하지 않았다.
- 입력 높이·버튼 위치·상태 전환·키보드·스크롤 동작을 기존 구현에서 실패하는 시험으로 확인한 뒤 수정했다. 집중 Vitest `25 passed`, production build, 관련 dummy Playwright `1 passed`를 통과했다. 전체 Vitest는 동시 작업 중 추가된 회로 원본 9건의 dummy fixture 기대값 불일치 1건으로 `155 passed, 1 failed`이며 이번 입력 영역과 무관해 수정하지 않았다.

### 진행도 아래 초기 안내 제거

- 선택된 프로젝트의 중앙 작업면에서 진행도 바 아래에 있던 `분석 대화`, `대체 가능성 분석 흐름`, 대상 배지와 회로 입력 확인 카드를 제거했다. 분석 전에는 빈 대화 작업면과 하단 입력줄만 보이며, 분석을 시작한 뒤 생성되는 실제 질문·상태·결과는 유지한다.
- 기존 마크업에서 안내 문구가 남아 실패하는 시험을 먼저 확인했다. 수정 뒤 관련 Vitest `2 files / 44 tests passed`, production build, 관련 dummy Playwright `1 passed`, `git diff --check`를 확인했다.

### 하단 입력줄 위치 고정 복구

- 초기 제목 행을 제거한 뒤에도 대화 패널이 기존 3행 Grid를 유지해 입력 영역이 두 번째 `1fr` 행 전체로 529px까지 늘어나던 원인을 확인했다. 실제 자식 구조에 맞춰 `대화 내역 minmax(0, 1fr) + 입력줄 auto`의 2행 Grid로 수정했다.
- 입력 영역 높이가 200px 미만이고 중앙 작업면 하단과 맞닿는 브라우저 회귀 시험을 RED부터 추가했다. 수정 뒤 관련 Vitest `2 files / 44 tests passed`, production build, Playwright 전체 `9 passed`, `git diff --check`를 통과했다.

### 더미 모드 화면 내부 입력줄 보정

- 이전 검증은 입력줄이 작업면 하단에 붙는지만 확인해, 더미 모드 안내 배너만큼 작업면 전체가 뷰포트 아래로 밀리는 문제를 놓쳤다. `1328×864`에서 입력줄 하단이 `906.4px`에 위치하는 것을 재현했다.
- 바깥 셸은 안내 배너를 제외한 남은 높이를 작업대에 배분하고, 중앙 작업면은 자체 `100vh` 계산을 제거해 Grid 행 높이를 따르도록 수정했다. 모바일은 기존 문서 스크롤 방식을 유지한다.
- 입력 영역 높이 200px 미만, 하단 좌표 864px 이하, 사용 조건 버튼의 viewport 노출을 자동 검증한다. 같은 크기의 실제 화면을 캡처해 입력창과 두 버튼이 모두 보이는 것도 확인했다. 최종 관련 Vitest `2 files / 44 tests passed`, production build, Playwright 전체 `9 passed`, `git diff --check`를 통과했다.

### 추가 조건 배치와 오버레이 스크롤바

- 질문 입력 바로 아래에 선택형 사용 조건 입력을 배치하고 `사용 조건 닫기` 버튼을 입력 영역의 마지막으로 옮겼다. 조건 입력은 200ms 동안 위에서 자연스럽게 펼쳐지며, 모션 최소화 환경에서는 즉시 완료된다.
- 네이티브 스크롤바의 전용 폭을 0으로 만들어 화면을 자르지 않게 했다. 포인터가 실제 스크롤 가장자리에 접근할 때만 레이아웃 위에 겹치는 오버레이 손잡이가 나타나며, 세로·가로 드래그, 휠·트랙패드·키보드 스크롤을 유지한다.
- `1328×864` 실제 화면에서 조건 입력과 닫기 버튼이 모두 viewport 안에 있고, 오버레이 막대가 별도 여백 없이 콘텐츠 위에 표시되는 것을 캡처해 확인했다. frontend Vitest `19 files / 157 passed`, production build, Playwright 전체 `10 passed`를 통과했다.

### 랜딩 세부 문구 간소화

- 중앙 설명 문장 `부품과 사용 조건을 자연어로 적으면…`은 유지했다. 랜딩 조건 입력의 화면상 `사용 조건 (선택)` 라벨과 예시 목록 위 `빠른 시작` 표기만 제거했다.
- 조건 입력의 접근성 이름과 입력 기능, 빠른 시작 예시 버튼·애니메이션은 그대로 유지했다. 관련 Vitest `19 passed`, production build, 랜딩 Playwright `1 passed`를 확인했다.

### 프로젝트 선택 전 원본 회로도 미리보기

- 초기 랜딩에서 접혀 있던 우측 정보 패널을 기본으로 펼치고, `/api/demo-circuits`가 제공하는 검증된 데모 회로도를 프로젝트 생성 전에도 선택·확대·이동해 볼 수 있게 했다. 프로젝트를 선택하면 기존처럼 해당 demo id의 회로 요약으로 전환되며, 업로드 프로젝트에 원본 이미지를 추정하지 않는 경계는 유지했다.
- RED는 초기 화면에 이미지가 없고 `console-collapsed`인 것을 확인했다. 구현 후 `WorkbenchPage.test.tsx` `20 passed`, 전체 Vitest `19 files / 158 tests passed`, production build 성공. 실제 dummy 브라우저에서 선택지 15종과 `breadboard_supply` 초기 이미지, `zr7_taillight` 전환 이미지의 정상 로드를 확인했다.

### 연결 개념도 자동 배치

- 고정 원형 좌표와 직선 연결을 제거하고, 부품과 net junction을 분리한 그래프를 `elkjs` Web Worker에서 layered/orthogonal 방식으로 배치한다. 한 페이지는 네트 6개, 네트당 이웃 5개로 제한하며 초과 연결은 `+N`, 나머지 네트는 페이지로 탐색한다. 회로 연결 데이터는 브라우저 밖으로 전송하지 않는다.
- 배치 그래프·페이지·초과 묶음·입력 순서 독립성을 먼저 실패 시험으로 고정했다. 이후 SVG는 방향 화살표 없이 직교 `path`를 그리고, 실제 브라우저 시험에서 Worker 결과 전환, net junction 존재, 직선 `line` 부재, 표시 노드 간 겹침 0건을 확인했다.
- 검증: frontend Vitest `20 files / 161 passed`, production build 성공, 신규 회로 배치 Playwright `1 passed`. 전체 Playwright는 `10 passed, 1 failed`이며 실패는 초기 정보 패널이 이미 펼쳐진 현재 UI에서 기존 시험이 `정보 패널 펼치기` 버튼을 기다리는 계약 불일치다. 연결 개념도 시험과 나머지 흐름은 통과했다.

## 2026-11-10 데모 회로 15종 실서비스 catalog 확장

- 바꾼 파일: `data/circuits/catalog.json`, `visuals.json`, 신규 회로도 PNG 9개, `backend/projects/catalog.py`, 프로젝트 repository·visual 검증·API, `db/026_projects_catalog_demo.sql`, Vite dummy catalog, Dockerfile, 관련 계약 테스트와 폴더 문서.
- 실제 작업: 저장소에 수집된 공개 회로 15종을 단일 catalog로 묶고, 기존 Python·Vite·Docker의 6개 하드코딩을 제거했다. 누락 9종은 각 공식 저장소의 고정 commit에서 PNG·PDF·KiCad 원본을 받아 원본을 추정하거나 재배선하지 않고 배포 PNG를 만들었다. c02 하드웨어 라이선스는 원 저장소 근거에 따라 CC BY-SA 4.0으로 기록했다.
- API: 기존 전체 목록 응답을 유지하면서 ID·이름 검색, offset/limit, 5분 public cache header를 추가했다. 원본/배포 hash와 로컬 경로는 공개 응답에 포함하지 않는다.
- TDD: 6종만 반환하는 기존 구현과 6종 visual catalog에서 계약 테스트가 실패하는 것을 먼저 확인했다. 이후 catalog 기반 구현과 15종 자산을 추가했다.
- 검증: backend 전체 pytest `1304 passed, 112 skipped`, frontend Vitest `19 files / 157 passed`, production build, catalog 대상 Playwright `1 passed`(15종 원본 이미지 natural width), repo layout `5 passed`, `uv lock --check`, Docker image build와 실행 smoke(`/health` 200, 신규 9개 PNG 9/9 HTTP 200)를 통과했다. 전체 Playwright는 catalog 흐름을 포함해 `9 passed`였으나, 동시에 추가된 별도 스크롤바 hover E2E 1건이 투명 상태로 남아 `1 failed`이며 이 catalog 작업 범위에서는 수정하지 않았다.

## 2026-11-11 PR 준비와 최신 main 통합

- 범위 정리: 작업대 랜딩·대화 입력·근거·승인/견적 흐름과 15종 회로 catalog·원본 회로도·연결 개념도 자동 배치를 하나의 사용자 흐름으로 검토했다. API DTO, catalog, Vite dummy, Docker 정적 자산, 화면과 검증이 함께 바뀌어 분리하면 통합 계약을 중복 수정해야 하므로 한 PR로 유지하며, 400줄 초과 이유와 리뷰 지점을 PR 본문에 명시한다.
- 저장소 구조: `SOJAFIT.md`에서 누락됐던 회로 배치 Worker·client·test·E2E와 오버레이 스크롤 hook 6개를 실제 트리에 맞게 등록했다. `uv run --no-sync pytest -q tests/repo/test_repo_layout.py`는 `5 passed`다.
- main 통합: 기능 커밋 `f551b87`을 만든 뒤 `origin/main` `c96dbbe`를 merge commit `e50c657`로 충돌 없이 반영했다. 동결 평가셋은 수정하지 않았고 PR 기준 변경은 100개 파일이다.
- 브라우저 회귀 수정: 병합 직후 전체 Playwright에서 초기 정보 패널을 접힌 상태로 가정한 시험과, 모바일 가로 오버레이 스크롤바의 투명 track이 프로젝트 버튼 클릭을 가로막는 문제가 드러났다. 초기 패널의 현재 계약을 시험에 반영하고 track은 클릭을 통과시키되 thumb만 드래그 입력을 받도록 수정했다(`a4403b1`). 실패 시험을 재현한 뒤 집중 Playwright `1 passed`, 전체 Playwright `11 passed`를 확인했다.
- 최종 검증: `uv run --no-sync pytest -q`는 `1445 passed, 112 skipped`, `npm run test:run`은 `20 files / 163 tests passed`, `npm run build`는 TypeScript·Vite production build 성공, `npm run e2e -- --reporter=line`은 `11 passed`, `uv lock --check`, `git diff origin/main...HEAD --check`와 repo layout `5 passed`를 확인했다. PR diff 593 KB를 Gitleaks stdin으로 검사해 `no leaks found`를 확인했다. worktree 전체 `dir` 검사는 Git 비추적 `.env`와 `.venv`까지 읽어 유효하지 않았으며 값은 출력하지 않았다.
- 확인하지 않은 것: 실제 외부 모델·MCP·Mouser·공유 PostgreSQL·배포 환경 round-trip, 데이터시트 외부 URL의 장기 가용성은 이번 로컬 PR 검증 범위가 아니다. GitHub Actions의 전체 이력 Gitleaks와 CI는 push 후 확인한다.

## 2026-11-11 제조사 데이터시트의 페이지·표 행 인용

- 내부 문서가 부족할 때 제조사 공식 PDF에서 대상 품번의 값과 단위를 찾아 문서 에이전트에 전달한다. 체크포인트에는 인용 위치만 남긴다.
- 실호출 검증 조건: 공개 질문 "Vishay SS34의 최대 반복 역전압은?"을 내부 검색 0건으로 입력한다. Exa 최대 1회, OpenRouter 문서 답변 최대 1회, 결과 형식 또는 공급자 실패 시 추가 유료 호출 없이 종료한다. 기준은 Vishay 문서 88751 1쪽의 SS34 열 40 V와 최종 인용 위치가 일치하는지다.
- 실호출: 문서 에이전트에 내부 결과 0건을 주어 Vishay SS34를 조회했다. Exa 1회, 제조사 PDF GET 1회, OpenRouter 문서 모델 1회. 답은 40 V [W1], 출처는 ss32.pdf 1쪽 Maximum repetitive peak reverse voltage 행이었다.
- 최종 검증: 기능·DTO·그래프·저장소 구조 94 passed. 전체 pytest 1482 passed, 112 skipped, 1 failed. 유일한 실패 tests/evals/test_input_surfaces.py의 P3는 변경 전 main(14cf261)에서도 재현됐다. uv lock --check와 git diff --check 통과. 실호출은 내부 검색 0건을 주입한 문서 에이전트에서 실시했으며 로그인부터 운영 DB까지의 실사용은 검증 범위 밖이다.
- Windows의 core.autocrlf=true가 동결 JSONL의 바이트 해시를 바꾸므로, 전체 검사 때 해당 파일이 Git 원본 LF 및 동결 해시와 일치하는지 확인했다. 검증 뒤 로컬 기본 줄바꿈으로 복구했으며 평가셋 변경은 없다.

### SS34 로그인 경로의 외부 근거 재채점

- 이전 로그인 실행은 외부 검색에서 Vishay 원문을 찾고도 `all_rejected`로 끝났다. 재채점 입력에 이미 탈락한 내부 카드가 다시 들어가고, 제조사 URL이 누락되는 문제를 재현했다. 외부 재채점이 실패하면 이전 내부 채점의 누락 사유가 반환되는 문제도 확인했다.
- 실호출 조건: 같은 공개 SS34 질문 1건, 격리 PostgreSQL과 42문서 스냅샷, 일반 계정 로그인, 데모 재생 끔. Exa 한 번과 서비스의 기존 모델·시간·비용 상한을 적용한다. 성공 기준은 실시간 completed, 저장 재조회 일치, 인용된 페이지의 같은 표 행에서 SS34 열 40 V 확인이다. 추가 유료 평가 없이 종료한다.
- 수정: `backend/multi_agent/agents/docs.py`에서 탈락한 내부 카드를 제외하고, 부분 답에서 인용한 카드만 외부 표 행과 함께 재채점한다. 모델에 공식 PDF URL·페이지·표·행을 표시하며, 재채점도 실패하면 해당 누락 사유를 보고한다. `backend/prompts/docs_answer.md`에 제조사 출처와 같은 계열 안의 품번 열을 구분하는 기준을 명시했다.
- 실제 결과: 로그인·세션 확인 200, 내부 SS34 검색 0건, Voyage 200, Exa 1회 200, Vishay PDF 다운로드 200. 문서 모델이 내부 근거에 none, 외부 표 행에 enough를 반환했다. 최종 SSE completed와 GET /api/runs 재조회에 같은 40 V [W1] 답변과 근거가 남았다. `ss32.pdf` 1쪽 MAXIMUM RATINGS 표의 Maximum repetitive peak reverse voltage 행에서 SS33=30, SS34=40, 단위 V를 원문과 대조했다.
- 회귀 검사: 수정 전 재채점 입력과 실패 보고 관련 3건 실패를 확인했다. 수정 후 문서 에이전트·PDF 추출 79건, 대화 DTO·API·Supervisor 105건 통과. 격리된 로컬 백엔드에서 실제 공급자를 사용했으며 브라우저 렌더링·운영 배포·전체 동결 평가셋 재측정은 이번 검증 범위 밖이다.

### 공식 PDF 원문 셀과 최종 답변 대조

- 기존 구현은 PDF가 SS34 40 V여도 모델이 쓴 400 V [W1]을 문서 노드와 최종 검사에서 통과시켰다. 공개 예제 1건을 격리 DB(42문서)에서 일반 계정으로 실행한다. Exa 1회와 기존 서비스 호출 예산을 사용한다. 통과 조건은 잘못된 품번·수치·단위를 회귀 검사에서 거절하고, 로그인 질문의 답변·저장 재조회·공식 PDF 1쪽 SS34 열이 일치하는 것이다.
- 1차 로그인 실행은 텍스트로 W행을 선택하는 방식에서 verify_failed로 거절됐다. 선택을 모델의 구조화 필드 `pdf_rows`로 옮겼다. 외부 근거만 있으면 모델의 자유 답변 필드는 빈 문자열이어야 한다. 서버가 PDF 셀의 품번·행·수치·단위로 문장을 만들며 최종 검사에서 인용 번호와 문장 해시를 다시 확인한다.
- 수정 후 같은 질문을 새 로그인 세션에서 재검증했다. 각 실행에서 Exa 1회, 최종 실행에서 공식 PDF 200, 외부 문서 모델 enough·W1, SSE completed, GET 재조회 일치. 원문 1쪽 MAXIMUM RATINGS의 Maximum repetitive peak reverse voltage 행은 SS33=30, SS34=40, 단위 V였다. 테스트는 400 V, 다른 품번, 다른 단위, 최종 인용 변경을 거절했다. 관련 pytest 193건 통과. 전체 동결 평가셋 재측정·운영 배포 검증은 미실시.
- 멀티 에이전트 전체와 관련 서비스·대화·레이아웃으로 넓힌 회귀 검사: 315 passed.

## 2026-11-11 중단·재개 후 저장 답변의 PDF 인용 유지

- 수정 전에는 독립 검색이 모두 W1부터 시작해 두 공식 PDF의 표 행이 같은 문장을 만들면 마지막 URL만 남았다. `backend/judge/pdf_claims.py`와 `backend/multi_agent/supervisor.py`에서 체크포인트 보고를 회차·작업 순으로 읽고 기존 문장 해시를 검증한 뒤 실행 전체 번호를 부여한다. 같은 위치의 같은 주장은 번호를 재사용한다. `backend/graph/nodes.py`와 `backend/conversations/dto.py`에서도 W4 이후 번호를 읽는다.
- 격리 PostgreSQL 16과 FastAPI TestClient에서 일반 계정 로그인 → 실행 → requires_input → 분석 서비스와 DB 풀 재생성 → 같은 run 재개 → completed → 새 클라이언트로 로그인 → GET /api/runs/{id} 순서로 확인했다. 인증·체크포인트·DB 저장은 실제 경로를 사용했다. 두 검색과 모델 응답은 고정했고 PDF는 테스트에서 생성했다. 외부 공급자 호출은 0회였다.
- 두 PDF의 SS34 `Peak reverse voltage` 행이 모두 40 V인 조건에서 완료 응답과 재조회 결과가 일치했다. W1은 test-a.pdf 1쪽 Table 1, W2는 test-b.pdf 2쪽 Table 2였다. 로그아웃 상태의 GET은 401이었다. `tests/services/test_datasheet_rows.py`에 같은 표를 다시 찾은 경우, 변조된 400 V 거절, W4 재조회도 포함했다.
- 관련 pytest는 317 passed. 격리 DB에서 `uv run --no-sync pytest -q --tb=line`으로 전체를 비교했다. 깨끗한 Windows 체크아웃에서 수정 전 `2d726e3`은 1548 passed, 수정 후 1550 passed였고, 양쪽 모두 같은 11 failed, 3 errors, 39 skipped였다. 이 중 평가 표본 해시 문제는 Git의 CRLF 변환으로 재현했다. 실제 작업 폴더의 첫 실행은 이전 frontend/dist에 회로도 이미지가 없어 데모 API도 실패했다. 동결 평가셋이나 다른 기능의 실패는 이번 수정에 포함하지 않았다.

## 2026-11-11 재개 후 Exa 품번과 공식 PDF 행 검증

- 수정 전 실제 재개 실행은 1N5819 작업에도 1N4001과 1N5819를 함께 검색해 1N4001의 50 V만 두 번 저장했다. 같은 공개 질문, 빈 코퍼스, 격리 DB 일반 계정, onsemi 원문으로 다시 실행한다. `Conversations` 기본 그래프와 실제 Exa·OpenRouter를 사용하고, 한 실행당 Exa 최대 2회, 각 호출 단계는 서비스 예산 상한을 적용한다. 재조회 결과의 W1·W2와 두 원문 2쪽 VRRM 행을 대조한 뒤 중단한다.
- `backend/multi_agent/agents/docs.py`에서 외부 검색 품번을 작업 지시서 기준으로 유지한다. 지정 목록이 비어 있으면 전체 질문의 품번 중 Supervisor의 작업 검색어에 나온 품번을 우선한다. PDF의 대상 품번과 셀 열을 확인한 행만 모델에 전달한다. `tests/multi_agent/test_agents.py`는 다른 품번의 행과 다른 품번 열에 든 수치가 모델 입력에 들어가지 않는지 검증한다.
- 실제 실행 `401eea2f-a13a-4cbf-8a76-167e4400795b`에서 일반 계정 로그인 200 → 첫 Exa 검색 1N4001 → requires_input → 분석 서비스 재생성 → 같은 run 재개 → 두 번째 Exa 검색 1N5819 → completed를 확인했다. 비로그인 조회 401 후 새 세션으로 로그인했고, 완료 응답·저장 답변·DB 근거 목록의 두 번호가 일치했다. 외부 PDF 다운로드 대상은 질문의 제조사 onsemi로 제한했다.
- 두 PDF를 별도로 텍스트 추출해 2쪽 `MAXIMUM RATINGS` 표의 `Peak Repetitive Reverse Voltage`(VRRM) 행에서 머리글과 값의 열 위치를 대조했다. W1은 [1N4001의 50 V](https://www.onsemi.com/pdf/datasheet/1n4001-d.pdf#page=2), W2는 [1N5819의 40 V](https://www.onsemi.com/pdf/datasheet/1n5817-d.pdf#page=2)였다. Exa 2회, PDF GET 2회, OpenRouter 노드 응답 5회(Supervisor 2, 판정 조건 읽기 1, 문서 답변 2). DB에 기록된 분석 시간은 중단 전 9.952초, 재개 후 6.109초였다. 실제 청구 금액은 확인하지 않았다.
- 관련 pytest 319 passed. 각각 새 PostgreSQL DB와 LF 체크아웃에서 `uv run --no-sync pytest -q --tb=no`로 비교했다. 수정 전 dd7fc3c는 1561 passed, 수정 후 1563 passed였다. 양쪽 모두 39 skipped이며 같은 테스트 3건(두 Google 관리자 세션, PostgreSQL 판정 재개 시 judge_read 횟수, 입력 표면 P3)이 실패했다. 동결 평가셋을 변경하거나 전체 실모델 평가를 실행하지 않았다.
## 2026-11-11 원본 회로도 백엔드

- 공개 GitHub 저장소에서 출처와 커밋, 라이선스, KiCad 원본을 확인한 뒤 전체 회로도를 시트별 PNG로 제공한다. 같은 설계의 PDF가 있으면 목표 300 DPI로 변환한다. 프런트와 일반 검색·LLM 답변 통합은 포함하지 않았다.
- 검증: `uv run --no-sync pytest -q` 전체는 1,598 passed, 112 skipped, 1 failed(88.43초). 실패한 `tests/evals/test_input_surfaces.py::test_real_input_path_records_bad_raw_and_contains_final[P3]`는 변경 전 main(`14cf261`)의 별도 스냅샷에서도 단독 실행으로 재현됐다. 회로도 API·검색·변환·오류·OpenAPI·폴더 규칙 집중 검사 181 passed.
- 실제 공급자 점검: `verify_external_schematics.py --query RP2040 --check-cache`에서 MIT 프로젝트 `calliah333/RP2040-designguide@a9afaa2`의 3509×2484 PNG 한 장을 받았다. 반복 요청에서 외부 검색·저장소 검사·변환은 각각 0회. Docker 이미지 빌드 후 KiCad 9.0.2 비루트 컨테이너에서 `--force-kicad-fallback`으로 ATtiny85 원본도 3508×2481 PNG 한 장으로 변환했다. 배포 서버와 실제 사용자 로그인은 이번 실조회 대상이 아니다.
- 운영 요청: 팀 GitHub 조직 관리자가 공개 회로도 조회용 OAuth App을 등록한다. 앱 자격 증명은 배포용 Secret Manager에 보관하고, 앱 인증 연결과 요청 한도 확인은 등록 후 진행한다.

## 2026-11-12 · 1→2→3등급 PR 준비

공식 근거/참고 폴백과 정확 품번·판본·인용 검증, 관련 품질 보완을 분리한다. 검증 정리는 docs/research/grade-evidence-validation.md. 전체 pytest 1764 passed,112 skipped,실패0(64.59초). 운영 부하는 보류. 포화 재확인은 공급자 제한으로 중단돼 안정 포화점 미확정. 상세 사전등록 원문은 작성자 기존 작업공간에 보존하며 게시 전 필요한 등급 관련 사전등록 절을 검토한다.


## 2026-11-12 OSC에 최신 main 통합 후 최종 상태

- 브랜치는 OSC. 최신 main `11dc216`을 fast-forward로 반영했다. 원래 OSC의 회로도/프런트 미커밋 작업은 stash `fc262a301cf7f47d133bdbdc587716380403f5f1`에 보존했다. 기존 검증 원본 작업공간도 유지했다.
- main 기능을 보존하며 등급 변경을 3-way 통합했다. Spec 에이전트/회로 읽기 명칭, FIND_N_DOCS 기본5와 환경변수, SUPERVISOR_REPLAN 설정, 응답·보안 경계를 보존했다. 프런트/DB 추가변경은 없다. 통합 후 유료 답변 평가·포화 재측정은 수행하지 않았다. 위 실측 수치는 통합 전 코드의 이력이며 새 코드의 새 실측으로 주장하지 않는다.
- 충돌 마커 제거/문법 검사/diff check 통과. HEAD=origin/main인 상태에서 전체 통합 변경(신규 파일 포함)을 별도 임시 index의 패치로 만들어 최신 main에 적용 검사 통과. 실제 index·commit·push·PR은 변경하지 않았다. 원격 main이 이후 변경되면 다시 검사해야 한다.
- 전체 pytest는 변경하지 않은 main의 tests/api/test_openapi.py:154 `SNAPSHOT` 미정의로 수집 오류1건. 이 파일을 제외하고 .env 영향을 차단한 `PYTHON_DOTENV_DISABLED=1 uv run --no-sync pytest -q --ignore=tests/api/test_openapi.py` 결과는 **1818 passed,158 skipped,9 failed**,69.62초다. 실패9건은 인증 사전검증2, stage_timing2, 저장소구조5이며 동일 main 기준선에서 재현됐다. 기준선 export의 추가 sample-hash 관련 실패는 이9건의 근거와 섞지 않는다.
- 통합 중 os/display_inputs 등 누락은 수정하고 관련173테스트를 통과했다. 첫 실패 회차 로그도 보존했다. 기존 main 오류를 이번 범위에서 임의로 고치거나 테스트 기대를 바꾸지 않았다.
- 판단: 내용상 최신 main 통합/무충돌 검사는 완료. 테스트 전체 통과 기준의 PR 준비 완료는 보류. 위 기존 main 오류의 처리/팀 판단이 남았다.
- 자료는 PR-준비/OSC-final-verification.json, OSC-main-integrated.patch, OSC-final-included-files.txt, OSC-main-full-pytest.log, OSC-main-final-pytest.log, OSC-main-baseline-repo-layout.log에 보존했다. 패치 적용 가능은 실제 GitHub PR 생성/CI 성공/병합 승인과 구분한다.

### 2026-11-12 · PR103 계약 감사 보완 시작

- 사용자 승인 범위: 품번별 판본 연결, 공식 검색 슬롯 소진과 근거 부재 구분, 웹 연결/SSE·GET 예외 계약 문서. 기존 커밋 d15331e가 복구 기준이며 추가 작업 없이 복구 가능하다. 제품·문서·시험 파일은 각 담당으로 나눠 병렬 수정하고, 공유 호출부는 담당 완료 후 순차 통합한다.
- 새 유료 평가/포화 실측/운영 부하 없음. 단위 회귀와 최종 pytest/main 병합 검사 후 기존 OSC PR103에 추가 커밋을 반영한다. 기존 main 오류는 이번 범위와 구분해 남긴다.


## PR103 계약 감사 수정 반영 — 2026-11-12

- 품번별 판본 연결을 추가했다. SS34/F16·SS34H/F20의 교차 판본은 문서 입력/공식 행/후보 판정/최종 인용 검사에서 배제한다. 1N 계열·하이픈 품번, 단일 판본의 기존 locator와 단일 품번의 복수 판본 비교도 회귀 시험에 포함했다. 관계가 모호한 다품번·다판본 자료는 추정하지 않고 거부한다. 지원되는 명시적 절 연결을 검증한 것으로 모든 자연어 문장을 해석한다고 주장하지 않는다.
- 공식/참고 검색 슬롯은 요청당 각각 1회로 유지한다. 사용 중이거나 소진된 슬롯은 SearchBudgetExhausted로 실제 검색 0건과 구분한다. 공식 슬롯 소진만으로 3등급으로 이동하지 않는다. 실제 0건/공급자 실패의 기존 폴백과 유효 내부 답변은 보존한다. 다른 에이전트의 검색 결과 공유·추가 호출 기능은 넣지 않았다.
- MULTI_AGENT의 낡은 웹 거부 설명, 공식 검색 계약, API의 SSE/GET 공통 결과 설명을 갱신했다. profile_hints/input_conditions가 SSE 전용인 기존 동작과 DB 계약은 바꾸지 않았다.
- 최종 `PYTHON_DOTENV_DISABLED=1 uv run --no-sync pytest -q`는 기존 main의 `tests/api/test_openapi.py`에서 SNAPSHOT 미정의 수집 오류 1건으로 중단됐다. 해당 파일을 제외한 전체 결과는 **1836 passed, 158 skipped, 9 failed**(71.92초)였다. 실패 9건의 테스트 ID는 수정 전과 동일했다(인증 사전 검증 2건, 단계 타이밍 2건, 저장소 구조 5건). 기대치를 바꾸거나 비용 문제로 실패를 제외하지 않았다.
- 독립 검토에서 판본 필터가 문서·판정·최종 인용 경계까지 연결되고 검색 상한 1+1이 유지됨을 확인했다. 초기 집중 검사 1건의 실패는 병렬 작업 중 상위 테스트와 helper의 갱신 시점이 겹친 실행으로 기록했다. 산출물 고정 후 관련 검사 506 passed, 1 skipped였고 마지막 복수 절 호환 추가 후 전체 검증으로 확인했다.
- 가짜 검색·모델·사양과 실제 코드 경로를 이용한 회귀 검증이다. 이번 수정 후 실 Exa/PDF/LLM 호출·포화/운영 부하 실측은 하지 않았다. 통합 전 실측을 새 코드의 새 실측으로 바꾸지 않는다.
- 근거: PR-준비/PR103-contract-focused.log, PR103-contract-final-targeted.log, PR103-contract-full.log, PR103-contract-full-excluding-known-main-error.log. 동결 v3·정답·해시는 유지했다.

### 2026-11-12 · 조회 제한 후 문서 완료 상태 보완

- 사용자 승인: 공식 보강이 필요한데 검색 슬롯이 소진되면 기존 내부 답을 ok로 보고하는 문제를 수정한다. 복구 기준은 c0c453e다. `docs.py`의 최종 상태 계산만 고쳐 내부 보강 후 남은 요구와 조회 제한을 함께 확인하고 답변·인용은 유지한다. 내부 packet만으로 요구가 충족되면 정상 완료로 보존한다.
- Red 회귀 검사 2건에서 잘못된 ok 상태를 재현했고, Green 경계 검사 8건을 통과했다. 관련 테스트와 전체 검사 후 기존 PR #103에 추가 커밋과 본문 갱신을 예정했다. 새 유료 평가나 운영 부하 실측은 없었다.


## PR103 공식 조회 제한 후 미완료 상태 보완 — 2026-11-12

- 공식 조회 슬롯이 소진된 뒤에도 필수 trr 측정 조건이 부족한데 문서 보고가 ok/missing[]로 남는 문제를 수정했다. 최종 내부 보강 뒤에 남은 조건·누락·재검색 요구와 조회 제한 여부를 함께 검사한다.
- 확인된 내부 답변·인용은 유지하면서 미완료 상태 partial, 사유 limit_reached, 미확인 항목을 남긴다. Supervisor의 부분 답변 안내가 실제로 출력되는지도 시험했다. 검증된 내부 packet만으로 요구가 충족되면 정상 완료를 유지하며 불필요한 partial을 추가하지 않는다. DB·프런트·모델 설정·검색 횟수는 바꾸지 않았다.
- Red: enough/partial 입력 2건에서 잘못된 ok를 재현했다. Green: 해당 경계와 내부 완결 packet의 조회 제한 유무를 포함한 8건을 통과했다. 최종 관련 검사는 190 passed(7.33초)였다.
- 최종 전체 pytest는 기존 main의 SNAPSHOT 수집 오류 1건으로 중단됐다. 해당 파일을 제외하고 .env 영향을 차단한 뒤의 결과는 **1841 passed, 158 skipped, 9 failed**(71.16초)였다. 실패 테스트 ID는 이전과 같고 이번 수정으로 늘어난 실패는 없었다. 비용 문제나 기존 실패를 성공으로 바꾸지 않았다.
- 가짜 조회·모델을 실제 문서 에이전트와 최종 안내 코드에 연결한 검증이다. 실제 Exa·LLM 유료 호출이나 동결 v3의 새 품질·포화 평가는 하지 않았다. 실제 모델 오답률 개선을 주장하지 않는다.
- 로그: PR-준비/PR103-completion-focused.log, PR103-completion-full.log, PR103-completion-full-excluding-known-main-error.log. 계약은 docs/specs/official-datasheet-evidence.md에 추가했고 기존 PR103 본문과 추가 커밋으로 반영한다.
