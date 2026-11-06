# graph

## 역할
- 이 폴더: LangGraph 그래프의 상태, 노드, 조립과 사용자별 장기 기억 규칙을 둡니다. D4 단일 에이전트 그래프(11-06에 D4 v2로 고침)가 있고, 멀티 그래프는 `backend/multi_agent/`에 있습니다.
- 넣는 것: 그래프 상태 정의(`state.py`), 노드 함수(`nodes.py`), 노드를 잇고 갈림길을 정해 compile하는 코드(`build.py`), 사용자별 장기 기억 Store namespace 규칙(`memory.py`).
- 넣지 않는 것: 숫자·단위 비교 판정(`backend/judge/`), LLM 직접 호출([services](../services/SERVICES.md)의 `llm.py`만 씁니다), 검색 구현(`backend/rag/`), 프롬프트 원문(`backend/prompts/`), 로그인·세션(`backend/auth.py`).
- 담당: 에이전트

## 구현 상태
- 있음: D4 v2 단일 그래프(아래 흐름). 사실 확인(`lookup`), 판정 길(`specs` · `find` · `chat`), 체크포인터를 인자로 받아(`build_graph(retriever, checkpointer, *, lookup, specs, find, chat)`) 가짜 검색기 · 가짜 도구로 키 없이 시험할 수 있습니다. 판정 길의 빠진 값 묻기(interrupt, 문항당 1번)는 체크포인터가 있어야 켜지고, 평가 실행기는 메모리 체크포인터(`InMemorySaver`)를 넘깁니다.
- 아직 없음: Supervisor와 서브에이전트(D5, `backend/multi_agent/`에 따로 있음), DB 체크포인트 설정, 견적서 승인 단계(interrupt), 장기 기억 Store 연결. 필수 요건은 SPEC과 `docs/GATES.md`를 따릅니다.
- 다른 폴더 코드를 그대로 씁니다: 사실 확인 노드(`multi_agent/facts.py`), 판정 읽기 · 판정 에이전트(`multi_agent/agents/judge.py`), 거절 문구와 판정 답 틀(`multi_agent/messages.py`), 질문 종류 · 거절 사유 코드(`multi_agent/contracts.py`). D4 v2와 D5가 같은 사실 · 같은 판정 코드로 비교되게 하려는 것입니다.

## 흐름 (지금 코드, D4 v2 11-06)
입력 읽기 → 사실 확인(질문 속 품번 · 개정판이 코퍼스 목록에 있나, 코드) → 라우팅(질문 종류 8가지와 검색 전 거절 사유, LLM). 라우팅 뒤 갈림길:
- 거절 사유가 있으면(범위 밖 · 다른 부품 · 코퍼스에 없는 품번 · 개정판) 검색 없이 거절합니다. 이유 코드는 `refusal`에 남습니다.
- 일상 대화는 짧은 답(라우팅이 낸 `reply`)으로 끝냅니다.
- 가격 · 재고 질문은 가격 안내(코드)로 끝냅니다. 물은 품번만 `price_parts`에 남기고 Mouser는 부르지 않습니다. 값은 화면이 그래프 밖 `/api/prices`로 볼 때마다 조회합니다(SPEC 4절 · 6절, ADR 0009).
- 역할 질문은 검색 없이 생성(넷리스트 근거)으로 갑니다.
- 정격 질문은 재작성 → 검색(첫 검색부터 재작성한 검색어를 씁니다. 품번 필터는 원래 질문에서 뽑습니다). 정상 검색은 채점으로 가고 MCP 장애는 빈 결과와 구분해 바로 안전하게 거절합니다. 채점에서 통과 청크가 있으면 생성, 검색 결과가 0장이거나 검색을 이미 2번(`MAX_TRIES`) 했으면 거절, 아니면 재작성 → 검색을 한 번 더 합니다.
- 후보 판정 · 찾기 질문은 판정 읽기(LLM 1번) → 판정(빠진 값 인터럽트 1번, 사양 표 값으로 `backend/judge/`가 판정) → 답 틀(코드)로 갑니다. 사양 표 도구 장애나 코퍼스 밖 요구(판정이 남긴 `refusal` 코드, SPEC 8.3)면 거절합니다. `specs` · `find`를 넘기지 않으면 예전처럼 정격과 같은 검색 고리로 갑니다.

목표 흐름 중 견적서 승인과 사례 기억은 SPEC 2절에 있고 아직 구현 전입니다.

## 강사 안내
11/5(D4)에 단일 에이전트 그래프로 기준 점수를 재고, 11/6(D5)에 Supervisor와 서브에이전트로 나눠 같은 평가셋으로 다시 잽니다. 단일을 건너뛰면 멀티가 나았다는 걸 증명할 기준이 없습니다. 개선이 없었다면 없었다고 `EVAL_REPORT.md`에 적습니다.
11-06 검토에서 강사가 D4 그래프를 두 가지로 지적했습니다: "범위 판정을 첫 단에서 먼저 하라", "지금 것은 단순 직렬 흐름이다". D4 v2(위 흐름)는 이 두 가지를 고친 단일 에이전트 기준선입니다. D4 v2 점수는 아직 다시 재지 않았습니다.

## 파일
- `__init__.py` — 패키지 표시
- `state.py` — 그래프 상태(공용 메모장 `AgentState`) 정의. SPEC 2절 노드 표의 칸들(사실 `facts`, 라우팅 답안지 `route`, 가격 안내 품번 `price_parts`(값은 넣지 않음), 판정 `judge_read` · `judgement`, 거절 코드 `refusal` 포함)과, 쌓이는 칸 `tries`(검색 횟수)·`path`(지나간 노드), 현재 응답의 Skill 적용 정보 `skill`
- `nodes.py` — 노드 함수 11개. 입력 읽기(`read_input`: 입력 글 나누기, `connections.json`에서 대상 부품 주변 넷 읽기, 앞 턴의 검색 · 사실 · 판정 · 거절 · 가격 안내 칸 비우기), 라우팅(`route`: 질문 종류 8가지 · 검색 전 거절 사유 · 일상 대화 답, 확인된 사실을 멀티 Supervisor와 같은 글로 받음, `prompts/route.md`), 짧은 답(`short_reply`: 라우팅의 `reply`를 답으로), 가격 안내(`price_answer`: 질문 또는 대상 값의 품번을 `price_parts`에 남기고 `messages.price_message` 안내로 끝냄, LLM · Mouser 호출 없음, 멀티도 같은 노드), 검색(`search`: 질문 품번 또는 대상 값 품번으로 `retrieve`의 `parts`를 정함), 채점(`grade`: 다른 품번 줄·다른 개정판 청크를 규칙으로 뺀 뒤 LLM 1회, `prompts/grade.md`), 재작성(`rewrite`: 영어 검색어 한 줄, `prompts/rewrite.md`), 생성(`generate`: 통과 청크와 `[넷리스트]`만 근거로 답하고 없는 근거 인용·인용 없는 문장을 `check`에 기록, `prompts/generate.md`, 선택적 Skill 적용), 판정(`judge`: 멀티 판정 에이전트를 부르고 보고서는 버리며 사양 표 장애는 `retrieval_error`로), 답 틀(`judgement_answer`: `render_judgement`로 판정 답), 거절(`refuse`: LLM 없이 이유 코드 `refusal`과 안내문. 라우팅 거절은 멀티와 같은 문구, 검색 고리는 품번 문서 없음 / 찾은 문서에 답 없음 / 검색 장애를 나눠 적고 단서 요청)
- `mcp_retriever.py` — PR #44의 `structuredContent.result` 청크 목록을 검증하고 stdio MCP 세션을 재사용하는 동기 검색기. 빈 결과와 timeout·도구·응답 장애를 구분
- `memory.py` — 사용자별 장기 기억(Store) namespace `("memories", user_id)`만 정의합니다. 부르는 곳이 아직 없고, 승인 사례 저장과 틀린 기억 정정은 없습니다
- `build.py` — 갈림길 `after_route`·`after_search`·`after_grade`·`after_judge`를 정해 compile합니다. 사실 확인 노드와 판정 읽기 노드는 멀티 코드를 그대로 붙이고, 판정 길은 `specs` · `find`를 둘 다 줄 때만 잇습니다(하나만 주거나 체크포인터가 없으면 `ValueError`). MCP 장애는 채점·재검색하지 않으며 검색 상한은 `MAX_TRIES`(2)입니다
