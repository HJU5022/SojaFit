# graph

## 역할
- 이 폴더는 서비스가 import하는 공용 도구를 둔다: `nodes.py`의 도우미 함수와 상수, `memory.py`, `mcp_retriever.py`, `netlist.py`의 `_sexpr`. 서비스가 실제로 돌리는 그래프는 `backend/multi_agent/`다([MULTI_AGENT.md](../multi_agent/MULTI_AGENT.md)). 옛 D4 단일 그래프 조립(`build.py`)은 2026-11-26에 지웠다. 다시 볼 때는 로컬 태그 `freeze-2026-11-22`에서 꺼낸다.
- 넣는 것: 그래프 상태(`state.py`), 노드 함수와 도우미(`nodes.py`), 옛 승인 사례 Store namespace와 기억 읽기 노드(`memory.py`), MCP 검색기(`mcp_retriever.py`), 평가용 넷리스트 파서(`netlist.py`).
- 넣지 않는 것: 숫자·단위 비교 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`만 쓴다), 검색 구현(`backend/rag/`), 프롬프트 원문(`backend/prompts/`), 로그인·세션(`backend/auth.py`).
- 담당: 에이전트

## 서비스와 평가 실행기의 사용 분담
`backend.graph` import를 `backend/`, `evals/`, `scripts/` 전체에서 grep한 결과다.

| 대상 | 서비스(요청 처리)가 쓰는가 | 사용처 |
|---|---|---|
| `nodes.py`의 `read_input`(내부에서 `parse_input` 호출), `price_answer`, `parts_list_answer`, `quote_answer`, `target_choice` | 쓴다 | `backend/multi_agent/build.py`가 멀티 그래프의 `입력 읽기`·`가격 안내`·`부품 목록`·`견적 안내`·`대상 확인` 노드로 붙인다(`부품 목록`(#55)·`견적 안내`(#60)·`대상 확인`(#62)은 멀티만). `parse_input`은 평가 스크립트(`run_skill_pair.py`, `check_retrieval_db.py`)도 직접 부른다 |
| `nodes.py`의 `find_parts`, `search`, `citations`, `circuit_parts`, `other_part_row`, `netlist_block`, `circuit_mechanism`와 상수 `NOT_FOUND`, `REVISION`, `WORD`, `QUANTITY`, `STANDARD` | 쓴다 | `multi_agent/agents/docs.py`, `multi_agent/facts.py`, `multi_agent/agents/part_names.py`, `multi_agent/build.py`(`QUANTITY_CLAIM`), `multi_agent/supervisor.py`(`citations`, 계획 입력의 회로 부품 수 `circuit_parts`(#59), 함수 안 import `QUANTITY_CLAIM` · `find_parts` · `unsupported_numbers`), `api/projects.py`(부품 점검표 `KIND_NAMES` · `part_kind` · `circuit_parts` · `find_parts`, #68) |
| `nodes.py`의 `_connections_file` | 쓴다 | `services/demo.py` |
| `nodes.py`의 `circuit_around` | 쓴다(`read_input` · `target_choice` 안에서 대상 부품 주변 넷을 읽음) | 그 밖에 `mcp_skill/mcp_server/server.py`(`get_circuit_info`), `evals/runners/run_input_surfaces.py` |
| `nodes.py`의 노드 함수 `route`, `grade`, `rewrite`, `generate`, `refuse` | 쓰지 않는다 | 평가 실행기와 스크립트(`evals/runners/eval_grader.py`, `run_retrieval_layers.py`, `run_retrieval_r1.py`, `run_retrieval_service.py`, `run_retrieval_v3.py`, `scripts/langfuse/langfuse_skill_check.py`)가 `route`·`grade`·`rewrite`·`generate`·`refuse`를 직접 부른다 |
| `memory.py`의 `read_profile` | 쓴다 | `multi_agent/build.py`(멀티 그래프의 `기억 읽기` 노드) |
| `memory.py`의 `namespace` | 쓴다 | 탈퇴 때 옛 승인 사례 Store namespace 정리(`conversations/memory_service.py`). 사용자 사실 Store namespace는 `conversations/profile.py`의 `namespace`다 |
| `memory.py`의 `memory_context`, `memory_sources`, `memory_policy` | 호출은 되지만 승인 사례 입력이 항상 빈 목록(`conversations/memory_service.py`의 `Conversations.message`)이라 효과가 없다 | `multi_agent/supervisor.py`, `multi_agent/agents/docs.py`, `multi_agent/agents/judge.py`, `conversations/memory_service.py` |
| `mcp_retriever.py` | 쓴다 | `RetrievalUnavailableError`는 `multi_agent/agents/docs.py`·`judge.py`, `StdioMcpRetriever`는 `conversations/memory_service.py`(`Conversations._graph`) |
| `netlist.py`의 `_sexpr`, `TOKEN` | 쓴다 | `projects/schematic_render.py`(둘 다), `projects/schematic_discovery.py`(`_sexpr`) |
| `netlist.py`의 `parse_netlist` | 쓰지 않는다 | `evals/runners/run_input_surfaces.py`, `run_injection_baseline.py`, `run_judgement_bundle.py`와 시험 |
| `state.py`의 `AgentState` | 쓰지 않는다 | `nodes.py`만 import한다. 멀티 그래프의 상태는 `backend/multi_agent/state.py` |

`nodes.py`는 `backend/multi_agent/`의 `contracts`, `messages`, `supervisor`를 import하고, 멀티 쪽도 `nodes.py`를 import한다. 순환을 피하려고 `multi_agent/supervisor.py`는 `graph.nodes`를 함수 안(조건만 준 말 판단 `_conditions_only`, 답 검사 `check_node`)에서 import한다. 서비스는 단일 그래프(`build_graph`)를 만들지 않는다.


## 파일
| 파일 | 하는 일 |
|---|---|
| `GRAPH.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `state.py` | `nodes.py` 노드 함수가 쓰는 상태 `AgentState`(덮어쓰기 칸과 쌓이는 칸 `tries`·`path`) |
| `nodes.py` | 노드 함수(`read_input`, `route`, `price_answer`, `parts_list_answer`(멀티만, 부품 종류 `part_kind`로 거름), `quote_answer`(멀티만, 견적 요청의 고정 안내), `target_choice`(멀티만, 대상 부품 묻기, #62), `search`, `grade`, `rewrite`, `generate`, `refuse`)와 서비스 공용 도우미(`find_parts`, `citations`, `other_part_row`, `circuit_around` 등) |
| `memory.py` | 옛 승인 사례 Store namespace와 승인 사례 입력 도우미(`memory_context`, `memory_sources`), 멀티 그래프의 `기억 읽기` 노드 `read_profile`(사용자 사실 중 선호 실장 방식만 읽음, Store가 없거나 읽기가 실패하면 빈 값) |
| `mcp_retriever.py` | stdio MCP 세션을 재사용하는 동기 검색기 `StdioMcpRetriever`, 응답 검증, 빈 결과와 장애를 구분하는 `RetrievalUnavailableError` |
| `netlist.py` | KiCad `.net` S-expression/XML을 연결 목록으로 바꾸는 `parse_netlist`(평가 · 시험용. 서비스 업로드는 `projects/netlist.py`)와 S-expression 파서 `_sexpr` |
