# 오세창 작업 기록

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
- 서버 경계: API 등록 뒤 response-aware SPA middleware를 연결한다. 비API GET/HEAD의 downstream 404만 index(미빌드이면 기존 로그인)로 바꾸고, API·health·assets·다른 메서드·리다이렉트는 보존한다. 화면에도 기존 요청 ID를 유지한다.
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
- RAG·데이터 문서에서 현재 `voyage-4-large` 1024차원, `rerank-3`, `008` 이후 차원 없는 `halfvec`을 기준으로 정리했다. 1,360문서·52,244청크 등 v1 수치는 날짜가 있는 외부 산출물·DB 이력으로 두고 현재 진행 중인 v2 전체 청킹 완료 증거로 사용하지 않도록 했다.
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
- 정책 근거: 기존 공개 KiCad 5종의 13/8/14/44/14 nets는 모두 ASCII 양의 정수 code를 사용한다. 표준 표기 `[1-9][0-9]*`와 net 간 유일성을 요구한다. code는 문자열로 유지하며 0/음수/소수/부호/지수/앞자리 0/비ASCII 숫자는 거절한다. NUL은 metadata 포함 입력 전체에서 거절한다. filename은 비어 있지 않고 공백 제거·대소문자 무시 후 `.net`으로 끝나야 한다.
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
