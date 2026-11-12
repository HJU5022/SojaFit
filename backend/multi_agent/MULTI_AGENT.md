# multi_agent

## 역할
- 이 폴더: 서비스가 질문마다 돌리는 멀티 에이전트 그래프(Supervisor 1개 + 서브에이전트 RAG 에이전트·Spec 에이전트). `backend/conversations/memory_service.py`가 `build.build_graph`로 만들어 쓰고(`memory_service.py:284-309`), 평가 실행기는 `evals/runners/run_graph.py --multi`로 같은 그래프를 잰다. Supervisor가 질문을 보고 할 일 목록을 한 번에 짜고, 서브에이전트가 할 일을 동시에 하고, 코드가 보고를 모아 답을 정리한다.
- 넣는 것: 계획서·할 일·보고서의 형식, 이유 코드, 상한(`contracts.py`), 멀티용 상태(`state.py`), Supervisor(계획·모으기·종합·답 검사), 서브에이전트(`agents/`), 조립(`build.py`), 사실 확인(`facts.py`), 거절 문구·판정 답 틀(`messages.py`), 판본 추출(`revisions.py`).
- 넣지 않는 것: 단일 에이전트 기준선 그래프와 공용 도구(`backend/graph/`, 분담은 [GRAPH.md](../graph/GRAPH.md)), 숫자·단위 비교(`backend/judge/`), 검색 구현(`backend/rag/`), LLM 직접 호출(`backend/services/llm.py`), 프롬프트 원문(`backend/prompts/`), MCP 도구 정의(`backend/mcp_skill/`).
- 담당: 에이전트

## graph/와의 관계
두 폴더는 서로 import한다. 이 폴더는 `backend/graph/`에서 `nodes.py`의 도우미(`read_input`, `price_answer`, `find_parts`, `search`, `citations`, `other_part_row`, `netlist_block`, `circuit_mechanism`, 상수 `REVISION`·`WORD`·`NOT_FOUND`·`QUANTITY`·`STANDARD`), `memory.py`(`read_profile`, `memory_context`, `memory_sources`), `mcp_retriever.py`(`RetrievalUnavailableError`)를 가져다 쓴다. 반대로 `backend/graph/nodes.py`는 이 폴더의 `contracts.py`, `messages.py`, `supervisor.py`(`Facts`·`render_facts`)를 가져다 쓰고, 단일 그래프(`backend/graph/build.py`)는 `facts.py`의 `facts_node`와 `agents/judge.py`의 Spec 에이전트 노드를 그대로 붙인다. 사용처별 근거는 [GRAPH.md](../graph/GRAPH.md)의 분담 표다. 순환을 피하려고 `supervisor.py:314`는 `citations`를 함수 안에서 import한다.

## 구조
그래프 노드 이름은 한국어이고 조립한 그래프의 `get_graph().draw_mermaid()`로 그림을 뽑는다(SPEC.md 2절).

| 노드 | 하는 일 | LLM |
|---|---|---|
| `입력 읽기` | 입력 글 나누기, 대상 부품 주변 넷 읽기(`graph.nodes.read_input`) | 없음 |
| `기억 읽기` | Store에서 선호 실장 방식만 읽어 `mount_preference`에 둠(`graph.memory.read_profile`) | 없음 |
| `품번·판 확인` | 질문의 품번·개정판이 코퍼스에 있는지 확인(`facts.py`, MCP `check_corpus`) | 없음 |
| `Supervisor` | 계획: 범위 판정, 질문 종류, 할 일(최대 `MAX_TASKS`)과 지시서. 일상 대화·가격·범위 밖·코퍼스 밖은 여기서 끝냄 | `supervisor` |
| `RAG 에이전트` | 검색 → 다른 품번 줄·다른 판 거르기 → 근거 채점 + 답 쓰기 → 근거가 없거나 일부 답이면 다른 검색어로 재검색 → 인용 검사 → 보고 | `docs_answer` |
| `Spec 에이전트` | 하위 그래프 `회로 읽기` → `대체 부품 판정`. 읽기 LLM 1번, 빠진 값은 인터럽트로 묻고, 사양 값 비교는 `backend/judge/verdict.py`가 함 | `judge_read` |
| `답 모으기` | 코드만. 보고 상태와 상한을 보고 길을 정함 | 없음 |
| `답 정리` | 할 일 1개의 답(판정은 코드 답 틀) | 없음 |
| `종합` | 할 일 2개 이상일 때만. 판정 표는 코드가 그대로 붙임 | `synth` |
| `답 검사` | 인용 번호가 받은 근거 안인지, 종합 글의 숫자가 부분 답·판정 결과·질문에 있던 숫자인지 검사. 걸리면 거절 | 없음 |
| `끝내기`, `거절`, `가격 안내` | 마무리. 가격 안내는 `graph.nodes.price_answer` | 없음 |

- 노드별 모델: `backend/services/langfuse_prompts.py`의 `NODE_MODELS`가 정본이고, 선정 이유는 ADR 0014·0017이다.
- 상한(질문당): 할 일 수, 재계획, Supervisor LLM 호출, 서브에이전트 실행, 문서 할 일의 검색 횟수는 `contracts.py`의 `MAX_TASKS`, `MAX_REPLANS`, `MAX_SUPERVISOR_CALLS`, `MAX_AGENT_RUNS`, `MAX_SEARCHES`다. 넘으면 거절한다.
- 재계획: `답 모으기`가 다시 해 볼 만한 실패(사유가 `RETRY_REASONS`이거나 없음)나 계획의 `replan` 표시를 보고 재계획 횟수가 `MAX_REPLANS` 미만이면 `Supervisor`로 되돌린다(`supervisor.py` `collect_node`). 확정 거절 사유는 되돌리지 않는다.
- 판정 길(`Spec 에이전트`)은 사양 값 도구(`specs`, `find`)와 체크포인터가 있어야 켜지고, 없이 켜면 `build.py`가 `ValueError`를 낸다. 서비스는 카드 도구(`backend/rag/card_specs.py`, `backend/rag/card_find.py`)를 넘긴다.
- 사용자 사실 기억: `mount_preference`는 판정 할 일의 Send 꾸러미에만 들어가고 찾기에서 질문이 실장 방식을 말하지 않았을 때 같은 판정 안의 후보 순서만 바꾼다(`backend/judge/verdict.py` `rank`의 `preferred`). 평가 실행기는 Store 없이 compile해 빈 값이다.
- 승인 사례: 상태에 `approved_memories` 칸과 `memory_refs` 처리가 남아 있지만 서비스가 새 분석 입력에 빈 목록을 넣는다(`conversations/memory_service.py:442`). 승인 사례는 서비스 응답에 영향을 주지 않는다.
- 웹 조회: 별도 에이전트가 아니다. `memory_service.py`가 `DEMO_MODE`가 아니고 `exa.enabled()`일 때만 문서·판정 에이전트에 등급별 조회 도구(`backend/services/exa.py`)를 넣는다(`memory_service.py:303-307`).
- 계약: 분석 흐름은 [SPEC.md](../../SPEC.md), 판정은 [judge-agent.md](../../docs/specs/judge-agent.md)를 따른다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `MULTI_AGENT.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `build.py` | 그래프 조립 `build_graph`와 노드 `parse_node`·`finish_node`·`refuse_node`, Spec 에이전트 하위 그래프 `judge_subgraph` |
| `contracts.py` | 계획서 `Plan`, 할 일 `Task`, 보고서 `TaskReport`, 짧은 보고 `AgentReport`, 이유 코드 `Reason`, 질문당 상한 |
| `state.py` | 멀티 상태 `MultiState`와 판정 하위 그래프 상태 `JudgeState`·`JudgeOut`, 보고 합치기 규칙 `add_or_reset` |
| `facts.py` | 질문의 품번·개정판이 코퍼스 목록에 있는지 확인해 `Facts`를 만듦(`make_facts`, MCP 도구로 묻는 `make_lookup`, 노드 `facts_node`) |
| `messages.py` | 거절 사유를 사용자 문구로 바꾸는 `refusal_message`·`refusal_for`, 가격 안내 `price_message`, 판정 결과를 코드 틀 답으로 만드는 `render_judgement` |
| `revisions.py` | 사용자가 지정한 판본 추출, 검색 결과·판정 행 파일명에서 판본 확인 |
| `supervisor.py` | 계획 `plan_node`, 배분 `after_plan`(Send), 답 모으기 `collect_node`, 답 정리 `single_node`, 종합 `synth_node`, 답 검사 `check_node`, 사실 글 `render_facts` |
| `agents/` | 서브에이전트(설명 파일은 이 문서): `docs.py` RAG 에이전트, `judge.py` Spec 에이전트, `part_names.py` 품번 바로잡기(LLM 없음), `__init__.py` |
