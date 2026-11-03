# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 Skill 문서를 둡니다. 에이전트가 서비스 안에서 호출해야 하므로 Dockerfile이 복사하는 `backend/` 아래에 둡니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/rules/`), [노드 프롬프트](../prompts/README.md). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP 서버 틀. 도구5종 구현은 [PR #36](https://github.com/aihuman-7th/proj3-b/pull/36)의 통합 대상
- `skills/SKILL.md` — S1 정격·시험 조건 해석, S2 회로 연결 설명. 기본 적용은 꺼짐. 수치 비교·최종 판정·되묻기는 제외. 적용 계약은 [SPEC](../../SPEC.md), 선정 근거는 [조사](../../docs/skill-feasibility.md), 검증 상태는 [EVAL_REPORT](../../EVAL_REPORT.md)를 따름

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. (`mcp_server/`)
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

쓰려면 `uv add mcp`로 `mcp` 패키지를 추가해야 합니다. 그 전에는 `server.py`를 import하지 않습니다.
