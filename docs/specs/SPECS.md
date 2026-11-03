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
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색 작업서
- `mcp-tool-prompt.md` — MCP 도구 선택·결과 해석 프롬프트(Langfuse `sojafit/tool-use`)와 모의 검증 범위 작업서
- `mcp-search-tools.md` — MCP 코퍼스 검색과 제한된 TSC 웹 후보 검색의 도구 계약·수용 기준
- `mcp-graph-integration.md` — LangGraph 검색 주입 계약에 MCP `search_corpus`를 연결하고 빈 결과와 장애를 구분하는 작업서
- `mcp-graph-integration-plan.md` — 승인된 MCP 그래프 통합 작업서의 테스트 우선 구현 계획
