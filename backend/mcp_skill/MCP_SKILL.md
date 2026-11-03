# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 도메인 Skill을 둡니다. 에이전트가 서비스 안에서 호출해야 하므로 Dockerfile이 복사하는 `backend/` 아래에 둡니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/` 규칙 파일), [노드 프롬프트](../prompts/PROMPTS.md)(`backend/prompts/`). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP stdio 서버. `search_corpus`, `get_corpus_document`, `search_tsc_web`, `verify_tsc_pdf`, `get_circuit_info` 5개 도구를 제공합니다. 실행: `uv run --env-file .env python -m backend.mcp_skill.mcp_server.server`
- `skills/SKILL.md` — S1 정격·시험 조건 해석, S2 회로 연결 설명 지침. 기본 적용은 꺼짐이고 수치 비교·최종 판정·되묻기는 제외합니다. 경로가 고정입니다: `backend/graph/nodes.py`(생성 노드), `backend/services/langfuse_prompts.py`, `evals/run_skill_pair.py`가 이 경로를 읽으므로 옮기거나 이름을 바꾸지 않습니다. 적용 계약은 [SPEC](../../SPEC.md), 선정 근거는 [조사](../../docs/research/skill-feasibility.md), 검증 상태는 [EVAL_REPORT](../../EVAL_REPORT.md)를 따름

폴더 설명 파일은 이 `MCP_SKILL.md`뿐이고 `mcp_server/`·`skills/` 안에는 두지 않습니다.

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. 현재 `search_corpus`만 `backend/graph/mcp_retriever.py`를 통해 연결되어 있고 나머지 네 도구의 그래프 연결은 후속 범위입니다.
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

`search_corpus`는 적재된 DB가 필요합니다. `search_tsc_web`은 기본적으로 꺼져 있고 `DEMO_MODE=0`, `EXA_WEB_SEARCH_ENABLED=1`, `EXA_API_KEY`가 모두 있어야 동작합니다. 반환 URL은 검증 전 후보입니다. 상세 계약과 테스트 경계는 [MCP 검색 도구 작업서](../../docs/specs/mcp-search-tools.md)와 [그래프 통합 작업서](../../docs/specs/mcp-graph-integration.md)를 따릅니다.
