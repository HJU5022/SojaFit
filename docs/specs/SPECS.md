# specs

## 역할
- 이 폴더: 기능 스펙을 둡니다. 루트 `SPEC.md`에 없는 기능의 계약과 수용 기준을 씁니다. 각 문서의 상태는 문서 맨 위 헤더가 정본입니다.
- 넣는 것: `<english-kebab>.md` 기능 스펙. Why, Goal, What, How, AC 다섯 절을 둡니다. 형식은 `_example.md`입니다.
- 넣지 않는 것: 측정·평가 설계(`../experiments/`), 조사·실측 기록(`../research/`), `SPEC.md`에 이미 절이 있는 기능의 수용 기준(`SPEC.md` 한 곳), 결정 기록(`../adr/`).
- 담당: 그 기능을 구현하는 담당

## 알려진 겹침
- 가입·로그인 규칙, 오류 코드, 토큰 한도, API 경로 수는 루트 `SPEC.md`가 정본입니다. 이 폴더의 문서는 해당 절을 링크합니다.
- 화면 계약: 현재 화면의 경로 · 파일 구조는 `frontend/FRONTEND.md`와 `frontend/src/SRC.md`, 흐름은 루트 `SPEC.md` 2절이 정본입니다. 2026-11-16 교체 전 화면 문서는 [docs/archive/frontend-screen-redesign.md](../archive/frontend-screen-redesign.md)에 보관합니다. `d5-frontend-service.md`는 기능 계약(API · 저장 경계)이 현행이고 화면 구현 행만 새 화면에 맞췄습니다.

## 줄 번호
- 문서 안의 `파일:줄` 번호는 그 문서 머리의 기준 커밋 때의 것이다. 코드가 바뀌면 몇 줄씩 어긋나므로 함수 · 상수 이름으로 찾는다.

## 파일
- `_example.md` — 강사 스캐폴드의 작업서 형식 예시(AGENTS.md가 가리킴)
- `api-error-contract.md` — FastAPI 공통 JSON 오류 응답과 서버 생성 요청 식별자
- `circuit-context-diagram.md` — 대상 부품의 1·2단계 연결 개념도 계약
- `d5-frontend-service.md` — React·Vite 화면과 서비스 API 연결 계약(기능 계약 현행, 화면 구현 행은 새 화면 기준)
- `evaluator-demo-readiness.md` — 키 없는 Compose 데모: DEMO_REPLAY 기록 응답 재생
- `external-complete-schematics.md` — TSC와 영어 공식 제조사 참고 회로도, 공개 저장소 완성 회로도 시트의 백엔드 제공 계약, 자원 상한, 공식 PDF 최대 2개 병렬 검사 범위
- `netlist-conversation-versions.md` — 빈 프로젝트 생성, 채팅 넷리스트 접수와 대화별 회로 버전 고정
- `google-admin-login.md` — Google 관리자 최초 연결·운영자 승인과 OIDC 검증
- `google-user-login.md` — 일반 사용자 Google 가입, 비밀번호 재확인 연결
- `judge-agent.md` — Spec 에이전트와 대체품 찾기(역할 23개, 조건 판정, 후보 정렬)
- `login-auth.md` — 이메일 가입·로그인, 서버 세션, 가입·로그인 한도
- `local-live-api.md` — 운영 DB와 분리한 로컬 실제 API·화면·분석 저장소 실행
- `mcp-graph-integration.md` — MCP 검색 도구를 LangGraph 검색 주입에 연결하는 계약
- `mcp-search-tools.md` — MCP 서버 도구 6개의 입출력 계약
- `official-datasheet-evidence.md` — 내부 근거가 부족할 때 제조사 PDF 페이지·표 행 인용 계약
- `project-conversation-navigation.md` — 프로젝트·이전 대화 탐색 API 계약
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색
- `supervisor-v0-langfuse-import.md` — Supervisor V0 결과를 Langfuse Dataset·Experiment로 가져오는 계약
- `user-thread-memory.md` — 사용자별 분석 thread 소유권, 체크포인트, 사용자 사실 기억, 보관 기간
- `verified-circuit-and-datasheet-visuals.md` — 검증된 데모 회로도와 데이터시트·패키지 외형 근거 표시 계약
