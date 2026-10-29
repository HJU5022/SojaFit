# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 Skill 문서를 둡니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/rules/`). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP 서버
- `skills/SKILL.md` — Skill 문서

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. (`mcp_server/`)
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

하지 않을 조는 이 폴더를 지우세요. 쓰려면 `uv add mcp`로 `mcp` 패키지를 추가해야 합니다.
