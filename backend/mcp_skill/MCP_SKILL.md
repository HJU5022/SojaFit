# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 도메인 Skill을 둡니다. 에이전트가 서비스 안에서 호출해야 하므로 Dockerfile이 복사하는 `backend/` 아래에 둡니다. STH에는 MCP 서버 도구 5종이 구현되어 있지만 LangGraph MCP 클라이언트 연결은 별도 작업입니다. Skill 문서는 있고 코드가 읽습니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/` 규칙 파일), [노드 프롬프트](../prompts/PROMPTS.md)(`backend/prompts/`). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP stdio 도구 5종(`search_corpus`, `get_corpus_document`, `search_tsc_web`, `verify_tsc_pdf`, `get_circuit_info`). 계약과 한계는 [작업서](../../docs/specs/mcp-search-tools.md)와 [검토 기록](../../docs/research/mcp-tool-contract-review.md)을 따릅니다. 실행: `uv run --env-file .env python -m backend.mcp_skill.mcp_server.server`
- `skills/SKILL.md` — S1 정격·시험 조건 해석, S2 회로 연결 설명 지침. 기본 적용은 꺼짐이고 수치 비교·최종 판정·되묻기는 제외합니다. 경로가 고정입니다: `backend/graph/nodes.py`(생성 노드), `backend/services/langfuse_prompts.py`, `evals/runners/run_skill_pair.py`가 이 경로를 읽으므로 옮기거나 이름을 바꾸지 않습니다. 적용 계약은 [SPEC](../../SPEC.md), 선정 근거는 [조사](../../docs/research/skill-feasibility.md), 검증 상태는 [EVAL_REPORT](../../EVAL_REPORT.md)를 따름

폴더 설명 파일은 이 `MCP_SKILL.md`뿐이고 `mcp_server/`·`skills/` 안에는 두지 않습니다.

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. (`mcp_server/`) 아직 연결되지 않았습니다.
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

이 STH 브랜치에는 MCP Python SDK 의존성이 잠금 파일에 포함되어 있습니다. main 통합 전에는 해당 브랜치의 실행·import 상태를 별도로 확인합니다.
