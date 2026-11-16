# mcp_skill

## 역할
- 이 폴더: 가산 항목의 MCP 서버와 도메인 Skill. 에이전트가 서비스 안에서 호출하므로 Dockerfile이 복사하는 `backend/` 아래에 둔다.
- 넣는 것: RAG 검색을 FastMCP stdio 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/` 규칙 파일), [노드 프롬프트](../prompts/PROMPTS.md). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않는다.
- 담당: 가산을 시작할 때 정한다.
- 폴더 설명 파일은 이 문서뿐이고 `mcp_server/`·`skills/` 안에는 두지 않는다.

## 동작 요약
| 대상 | 사실 | 근거 |
|---|---|---|
| MCP 서버 도구 | `@mcp.tool()` 6개: `search_corpus`, `get_corpus_document`, `search_tsc_web`, `verify_tsc_pdf`, `get_circuit_info`, `check_corpus` | `mcp_server/server.py` |
| MCP 클라이언트 | LangGraph 쪽 stdio 클라이언트 `StdioMcpRetriever`(`backend/graph/mcp_retriever.py`)가 `search_corpus`, `check_corpus`를 부름 | `mcp_retriever.py:187-192` |
| 서비스의 사용 | 서비스 분석은 사실 확인(`check_corpus`)만 MCP로 하고, 문서 검색은 `retrieve()`, 찾기·판정 값은 카드 도구(`backend/rag/card_*.py`)를 직접 부름 | `conversations/memory_service.py:297-309` |
| Skill 읽는 곳 | `backend/graph/nodes.py:31`(단일 그래프 생성 노드), `backend/services/langfuse_prompts.py:170`(Langfuse 등록), `evals/runners/run_skill_pair.py`(Skill 유무 쌍 평가). 경로가 고정이므로 옮기거나 이름을 바꾸지 않는다 | 각 파일 |

MCP 서버 계약과 한계는 [mcp-search-tools.md](../../docs/specs/mcp-search-tools.md)와 [mcp-tool-contract-review.md](../../docs/research/mcp/mcp-tool-contract-review.md), Skill 적용 계약은 [SPEC.md](../../SPEC.md), 선정 근거는 [skill-feasibility.md](../../docs/research/mcp/skill-feasibility.md), 검증 상태는 [EVAL_REPORT.md](../../EVAL_REPORT.md)를 따른다. 서버 실행: `uv run --env-file .env python -m backend.mcp_skill.mcp_server.server`. 의존성은 `pyproject.toml`과 `uv.lock`에서 관리한다. import와 stdio 연결 계약은 `tests/mcp_skill/test_mcp_server.py`, `tests/graph/test_graph_mcp_retriever.py`, `tests/graph/test_graph_mcp_stdio.py`가 확인한다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `MCP_SKILL.md` | 이 문서 |
| `mcp_server/` | `server.py`: FastMCP stdio 서버 `sojafit-search`. 코퍼스 검색과 미검증 TSC 문서 후보 노출 |
| `skills/` | `SKILL.md`: S1 정격·시험 조건 해석, S2 회로 연결 설명 지침. 수치 비교·최종 판정·되묻기는 제외 |
