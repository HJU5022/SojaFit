# specs

## 역할
- 이 폴더: 기능 작업서를 둡니다. 루트 `SPEC.md`에 없는 기능을 에이전트에게 시키기 전에 씁니다.
- 넣는 것: `<english-kebab>.md` 기능 작업서. 다섯 섹션(Why, Goal, What, How, AC)이 모두 있어야 에이전트에게 그대로 넘길 수 있습니다. 형식은 `_example.md`입니다.
- 넣지 않는 것: 무엇을 어떤 조건으로 잴지 정한 측정·평가 작업서(`../experiments/`), 조사·실측 기록(`../research/`), `SPEC.md`에 이미 절이 있는 기능의 수용 기준(`SPEC.md` 한 곳에 둡니다), 결정 기록(`../adr/`).
- 담당: 그 기능을 구현하는 담당

## 알려진 겹침
`login-auth.md`의 수용 기준은 루트 `SPEC.md` 8.6(로그인)과 겹칩니다. 내용이 다르면 `SPEC.md`를 따릅니다.

## 파일
- `_example.md` — 강사 스캐폴드의 작업서 형식 예시(AGENTS.md가 가리킴)
- `login-auth.md` — 로그인과 사용자 식별 작업서(이메일·비밀번호 로그인, 서버 세션)
- `google-admin-login.md` — 기존 인증을 유지하는 Google 관리자 로그인 설계·구현 상태와 남은 운영 검증
- `login-completion-plan.md` — 암호 처리·개인정보·인증 DB 적재의 상태 비교와 실행 순서
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색 작업서
- `api-error-contract.md` — FastAPI 공통 JSON 오류 응답과 서버 생성 요청 식별자 작업서
- `mcp-tool-prompt.md` — MCP 도구 선택·결과 해석 프롬프트(Langfuse `sojafit/tool-use`)와 모의 검증 범위 작업서
- mcp-search-tools.md — MCP 검색·문서 조회·외부 후보·로컬 점검 도구의 1차 계약
- `mcp-graph-integration.md` — PR #44의 `search_corpus`를 LangGraph 검색 주입 계약에 연결하고 빈 결과와 장애를 구분하는 작업서
- `mcp-graph-integration-plan.md` — MCP 그래프 통합 작업서의 테스트 우선 구현 계획
- `judge-agent.md` — 판정 에이전트와 대체품 찾기 작업서(역할 23개, 조건 세 층, 인터럽트로 빠진 값 묻기, 후보 정렬)
- `judge-agent-plan.md` — 판정 에이전트 작업서의 테스트 우선 구현 계획(Task 11개, 커밋 단위)
- `supervisor-v0-langfuse-import.md` — 완료된 Supervisor V0 결과를 모델 재호출 없이 Langfuse Dataset·Experiment로 가져오는 작업서
