# specs

## 역할
- 이 폴더: 기능 스펙을 둡니다. 루트 `SPEC.md`에 없는 기능의 계약과 수용 기준을 씁니다. 각 문서의 상태는 문서 맨 위 헤더가 정본입니다.
- 넣는 것: `<english-kebab>.md` 기능 스펙. Why, Goal, What, How, AC 다섯 절을 둡니다. 형식은 `_example.md`입니다.
- 넣지 않는 것: 측정·평가 설계(`../experiments/`), 조사·실측 기록(`../research/`), `SPEC.md`에 이미 절이 있는 기능의 수용 기준(`SPEC.md` 한 곳), 결정 기록(`../adr/`).
- 담당: 그 기능을 구현하는 담당

## 알려진 겹침
- 가입·로그인 규칙, 오류 코드, 토큰 한도, API 경로 수는 루트 `SPEC.md`가 정본입니다. 이 폴더의 문서는 해당 절을 링크합니다.
- 화면 계약은 `frontend-screen-redesign.md`가 정본입니다.

## 파일
- `_example.md` — 강사 스캐폴드의 작업서 형식 예시(AGENTS.md가 가리킴)
- `api-error-contract.md` — FastAPI 공통 JSON 오류 응답과 서버 생성 요청 식별자
- `circuit-context-diagram.md` — 대상 부품의 1·2단계 연결 개념도 계약
- `d5-frontend-service.md` — React·Vite 화면과 서비스 API 연결 계약
- `dummy-full-flow.md` — 개발 전용 메모리 API로 로그인부터 사례 삭제까지 실행하는 흐름
- `evaluator-demo-readiness.md` — 키 없는 Compose 데모: DEMO_REPLAY 기록 응답 재생
- `external-complete-schematics.md` — 공개 저장소 완성 회로도 시트의 백엔드 제공 계약과 자원 상한
- `frontend-screen-redesign.md` — 랜딩·로그인·대화 중심 작업대의 경로와 화면 계약
- `google-admin-login.md` — Google 관리자 최초 연결·운영자 승인과 OIDC 검증
- `google-user-login.md` — 일반 사용자 Google 가입, 비밀번호 재확인 연결
- `judge-agent.md` — Spec 에이전트와 대체품 찾기(역할 23개, 조건 판정, 후보 정렬)
- `login-auth.md` — 이메일 가입·로그인, 서버 세션, 가입·로그인 한도
- `mcp-graph-integration.md` — MCP 검색 도구를 LangGraph 검색 주입에 연결하는 계약
- `mcp-search-tools.md` — MCP 서버 도구 6개의 입출력 계약
- `official-datasheet-evidence.md` — 내부 근거가 부족할 때 제조사 PDF 페이지·표 행 인용 계약
- `project-conversation-navigation.md` — 프로젝트·이전 대화 탐색 API 계약
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색
- `supervisor-v0-langfuse-import.md` — Supervisor V0 결과를 Langfuse Dataset·Experiment로 가져오는 계약
- `user-thread-memory.md` — 사용자별 분석 thread 소유권, 체크포인트, 사용자 사실 기억, 보관 기간
- `verified-circuit-and-datasheet-visuals.md` — 검증된 데모 회로도와 데이터시트·패키지 외형 근거 표시 계약
