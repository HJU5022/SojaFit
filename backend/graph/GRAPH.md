# graph

## 역할
- 이 폴더는 두 가지를 함께 둔다. (1) 단일 에이전트 기준선 그래프(D4 v2): `build.py`가 조립하고 평가 실행기만 돌린다. (2) 서비스가 import하는 공용 도구: `nodes.py`의 도우미 함수와 상수, `memory.py`, `mcp_retriever.py`, `netlist.py`의 `_sexpr`. 서비스가 실제로 돌리는 그래프는 `backend/multi_agent/`다([MULTI_AGENT.md](../multi_agent/MULTI_AGENT.md)).
- 넣는 것: 그래프 상태(`state.py`), 노드 함수(`nodes.py`), 갈림길과 compile(`build.py`), Supervisor V0 입출력 계약(`supervisor.py`), 사용자 기억 Store namespace 규칙과 기억 읽기 노드(`memory.py`), MCP 검색기(`mcp_retriever.py`), 평가용 넷리스트 파서(`netlist.py`).
- 넣지 않는 것: 숫자·단위 비교 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`만 쓴다), 검색 구현(`backend/rag/`), 프롬프트 원문(`backend/prompts/`), 로그인·세션(`backend/auth.py`).
- 담당: 에이전트

## 서비스와 평가 실행기의 사용 분담
`backend.graph` import를 `backend/`, `evals/`, `scripts/` 전체에서 grep한 결과다.

| 대상 | 서비스(요청 처리)가 쓰는가 | 사용처 |
|---|---|---|
| `nodes.py`의 `read_input`(내부에서 `parse_input` 호출), `price_answer`, `parts_list_answer`, `quote_answer`, `target_choice` | 쓴다 | `backend/multi_agent/build.py`가 멀티 그래프의 `입력 읽기`·`가격 안내`·`부품 목록`·`견적 안내`·`대상 확인` 노드로 붙인다(`부품 목록`(#55)·`견적 안내`(#60)·`대상 확인`(#62)은 멀티만). `parse_input`은 평가 스크립트(`run_skill_pair.py`, `check_retrieval_db.py`)도 직접 부른다 |
| `nodes.py`의 `find_parts`, `search`, `citations`, `circuit_parts`, `other_part_row`, `netlist_block`, `circuit_mechanism`와 상수 `NOT_FOUND`, `REVISION`, `WORD`, `QUANTITY`, `STANDARD` | 쓴다 | `multi_agent/agents/docs.py:27`, `multi_agent/facts.py:9`, `multi_agent/agents/part_names.py:10`, `multi_agent/supervisor.py`(`citations`, 계획 입력의 회로 부품 수 `circuit_parts`, #59) |
| `nodes.py`의 `_connections_file` | 쓴다 | `services/demo.py:111,124` |
| `nodes.py`의 `circuit_around` | MCP 서버만 쓴다. 서비스는 MCP 도구 중 `check_corpus`만 부르므로 서비스 경로에서는 호출되지 않는다 | `mcp_skill/mcp_server/server.py:12`(`get_circuit_info`), `evals/runners/run_input_surfaces.py` |
| `nodes.py`의 노드 함수 `route`, `short_reply`, `grade`, `rewrite`, `generate`, `judge`, `judgement_answer`, `refuse` | 쓰지 않는다 | `backend/graph/build.py`가 붙이고, 평가 실행기와 스크립트(`evals/runners/run_skill_pair.py`, `eval_grader.py`, `run_retrieval_layers.py`, `run_retrieval_r1.py`, `run_retrieval_service.py`, `run_retrieval_v3.py`, `scripts/langfuse/langfuse_skill_check.py`)가 `route`·`grade`·`rewrite`·`generate`·`refuse`를 직접 부른다 |
| `memory.py`의 `read_profile` | 쓴다 | `multi_agent/build.py:15`(멀티 그래프의 `기억 읽기` 노드) |
| `memory.py`의 `namespace` | 쓴다 | 탈퇴 때 승인 사례 Store namespace 정리(`conversations/memory_service.py:239`) |
| `memory.py`의 `memory_context`, `memory_sources`, `memory_policy` | 호출은 되지만 승인 사례 입력이 항상 빈 목록(`conversations/memory_service.py:442`)이라 효과가 없다 | `multi_agent/supervisor.py:23`, `multi_agent/agents/docs.py:24`, `multi_agent/agents/judge.py:21`, `conversations/memory_service.py:48` |
| `mcp_retriever.py` | 쓴다 | `RetrievalUnavailableError`는 `multi_agent/agents/docs.py:23`·`judge.py:20`, `StdioMcpRetriever`는 `conversations/memory_service.py:286` |
| `netlist.py`의 `_sexpr` | 쓴다 | `projects/schematic_render.py:21` |
| `netlist.py`의 `parse_netlist` | 쓰지 않는다 | `evals/runners/run_input_surfaces.py`, `run_injection_baseline.py`, `run_judgement_bundle.py`와 시험 |
| `build.py`의 `build_graph`, `after_grade` | 쓰지 않는다 | `evals/runners/run_graph.py:180`, `evals/runners/run_skill_pair.py:28` |
| `state.py`의 `AgentState` | 쓰지 않는다 | `nodes.py`와 `build.py`만 import한다. 멀티 그래프의 상태는 `backend/multi_agent/state.py` |
| `supervisor.py` | 쓰지 않는다 | `evals/runners/run_supervisor_prompt_v0.py`, `run_supervisor_prompt_v0_jev.py`, `supervisor_prompt_v0_common.py` |

`nodes.py`는 `backend/multi_agent/`의 `contracts`, `messages`, `supervisor`를 import하고, 멀티 쪽도 `nodes.py`를 import한다. 순환을 피하려고 `multi_agent/supervisor.py:314`는 함수 안에서 import한다. 서비스는 단일 그래프(`build_graph`)를 만들지 않는다.

## 단일 그래프 흐름 (D4 v2)
`build_graph(retriever, checkpointer, *, lookup, specs, find, chat)`가 compile한다. 가짜 검색기·가짜 도구를 넘기면 키 없이 시험할 수 있다. 입력 읽기 → 사실 확인(`backend/multi_agent/facts.py`) → 라우팅 뒤 갈림길(`after_route`)은 다음과 같다.

| 질문 | 길 |
|---|---|
| 거절 사유 있음(범위 밖·다른 부품·코퍼스에 없는 품번·개정판) | 검색 없이 거절 |
| 일상 대화 | 라우팅의 `reply`로 끝냄(`short_reply`) |
| 가격·재고 | 물은 품번만 `price_parts`에 남기고 안내(`price_answer`). 값은 `/api/prices`가 조회 |
| 역할 | 검색 없이 넷리스트 근거로 생성 |
| 정격 | 재작성 → 검색 → 채점 → 생성. 통과 청크 없음 + 재검색 가능이면 재작성으로 되돌아가고, 0장이거나 검색이 `MAX_TRIES`(`build.py:24`)에 닿으면 거절. 검색 장애(`retrieval_error`)는 채점 없이 거절 |
| 후보 판정·찾기 | 판정 읽기 → 판정(빠진 값 인터럽트) → 답 틀. 이 길은 `specs`·`find`를 둘 다 넘길 때만 이어지고(안 넘기면 정격과 같은 검색 고리), 하나만 주거나 체크포인터가 없으면 `ValueError`. 판정 뒤 코퍼스 밖 요구나 도구 장애는 거절(`after_judge`) |

판정 읽기와 판정은 `backend/multi_agent/agents/judge.py`의 Spec 에이전트를 그대로 쓰므로 단일과 멀티가 같은 판정 코드로 비교된다. 단일 대 멀티 비교 결과는 [EVAL_REPORT.md](../../EVAL_REPORT.md) 4장이다. 견적서 승인 단계는 이 그래프에 없다.

Supervisor V0(`supervisor.py`, `backend/prompts/supervisor_v0.md`)는 후보 모델의 라우팅 결정을 평가 실행기로 재는 프로토타입이고 `build_graph()`의 노드·갈림길에 연결되어 있지 않다. 절차는 [supervisor-prompt-v0.md](../../evals/guides/supervisor-prompt-v0.md)다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `GRAPH.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `state.py` | 단일 그래프 상태 `AgentState`(덮어쓰기 칸과 쌓이는 칸 `tries`·`path`) |
| `nodes.py` | 노드 함수(`read_input`, `route`, `short_reply`, `price_answer`, `parts_list_answer`(멀티만, 부품 종류 `part_kind`로 거름), `quote_answer`(멀티만, 견적 요청의 고정 안내), `search`, `grade`, `rewrite`, `generate`, `judge`, `judgement_answer`, `refuse`)와 서비스 공용 도우미(`find_parts`, `citations`, `other_part_row`, `circuit_around` 등) |
| `build.py` | 갈림길 `after_route`·`after_search`·`after_grade`·`after_judge`와 `build_graph` |
| `supervisor.py` | Supervisor V0의 네 필드 출력, 입력 envelope, 상태별 의미 검증, Jev typed-question 계약 |
| `memory.py` | 사용자별 Store namespace와 승인 사례 입력 도우미(`memory_context`, `memory_sources`), 멀티 그래프의 `기억 읽기` 노드 `read_profile`(사용자 사실 중 선호 실장 방식만 읽음, Store가 없거나 읽기가 실패하면 빈 값) |
| `mcp_retriever.py` | stdio MCP 세션을 재사용하는 동기 검색기 `StdioMcpRetriever`, 응답 검증, 빈 결과와 장애를 구분하는 `RetrievalUnavailableError` |
| `netlist.py` | KiCad `.net` S-expression/XML을 연결 목록으로 바꾸는 `parse_netlist`와 S-expression 파서 `_sexpr` |
