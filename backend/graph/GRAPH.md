# graph

## 역할
- 이 폴더: LangGraph 그래프의 상태, 노드, 조립과 사용자별 장기 기억 규칙을 둡니다. 지금은 D4 단일 에이전트 줄기 그래프만 있습니다.
- 넣는 것: 그래프 상태 정의(`state.py`), 노드 함수(`nodes.py`), 노드를 잇고 갈림길을 정해 compile하는 코드(`build.py`), Supervisor 공통 입출력 계약(`supervisor.py`), 사용자별 장기 기억 Store namespace 규칙(`memory.py`).
- 넣지 않는 것: 숫자·단위 비교 판정(`backend/judge/`), LLM 직접 호출([services](../services/SERVICES.md)의 `llm.py`만 씁니다), 검색 구현(`backend/rag/`), 프롬프트 원문(`backend/prompts/`), 로그인·세션(`backend/auth.py`).
- 담당: 에이전트

## 구현 상태
- 있음: D4 줄기 그래프(입력 읽기 → 라우팅 → 재작성 → 검색 → 채점 → 생성 / 거절, 채점에서 통과가 없으면 재작성 → 검색으로 돌아감). 검색기와 체크포인터를 인자로 받아(`build_graph(retriever, checkpointer)`) 가짜 검색기로 키 없이 시험할 수 있습니다.
- 아직 없음: Supervisor와 서브에이전트(D5), DB 체크포인트 설정, 사람 승인(interrupt) 지점, 판정 노드(`backend/judge/` 연결), 견적서 승인 단계, 장기 기억 Store 연결. 필수 요건은 SPEC과 `docs/GATES.md`를 따릅니다.

## 흐름 (지금 코드)
입력 읽기 → 라우팅. 범위 밖이면 거절, 역할 질문이면 검색 없이 생성, 나머지는 재작성 → 검색(첫 검색부터 재작성한 검색어를 씁니다. 품번 필터는 원래 질문에서 뽑습니다). 정상 검색은 채점으로 가고 MCP 장애는 빈 결과와 구분해 바로 안전하게 거절합니다. 채점에서 통과 청크가 있으면 생성, 검색 결과가 0장이거나 검색을 이미 2번(`MAX_TRIES`) 했으면 거절, 아니면 재작성 → 검색을 한 번 더 합니다.

목표 흐름(역할 파악 → 대체 조건 도출 → 후보 검색 → 판정 → 견적서 승인)은 SPEC 2절에 있고 아직 구현 전입니다.

## 강사 안내
11/5(D4)에 단일 에이전트 그래프로 기준 점수를 재고, 11/6(D5)에 Supervisor와 서브에이전트로 나눠 같은 평가셋으로 다시 잽니다. 단일을 건너뛰면 멀티가 나았다는 걸 증명할 기준이 없습니다. 개선이 없었다면 없었다고 `EVAL_REPORT.md`에 적습니다.

## 파일
- `__init__.py` — 패키지 표시
- `state.py` — 그래프 상태(공용 메모장 `AgentState`) 정의. SPEC 2절 노드 표의 칸들과, 쌓이는 칸 `tries`(검색 횟수)·`path`(지나간 노드), 현재 응답의 Skill 적용 정보 `skill`
- `supervisor.py` — Supervisor V0의 네 필드 출력, 입력 envelope, 상태별 의미 검증과 Jev typed-question 공통 계약. `build_graph()`에는 아직 연결하지 않음
- `nodes.py` — 노드 함수 7개. 입력 읽기(`read_input`: 입력 글 나누기, `connections.json`에서 대상 부품 주변 넷 읽기), 라우팅(`route`: 질문 종류 5가지, `prompts/route.md`), 검색(`search`: 질문 품번 또는 대상 값 품번으로 `retrieve`의 `parts`를 정함), 채점(`grade`: 다른 품번 줄·다른 개정판 청크를 규칙으로 뺀 뒤 LLM 1회, `prompts/grade.md`), 재작성(`rewrite`: 영어 검색어 한 줄, `prompts/rewrite.md`), 생성(`generate`: 통과 청크와 `[넷리스트]`만 근거로 답하고 없는 근거 인용·인용 없는 문장을 `check`에 기록, `prompts/generate.md`, 선택적 Skill 적용), 거절(`refuse`: LLM 없이 범위 밖 / 품번 문서 없음 / 찾은 문서에 답 없음을 나눠 적고 단서 요청)
- `mcp_retriever.py` — PR #44의 `structuredContent.result` 청크 목록을 검증하고 stdio MCP 세션을 재사용하는 동기 검색기. 빈 결과와 timeout·도구·응답 장애를 구분
- `memory.py` — 사용자별 장기 기억(Store) namespace `("memories", user_id)`만 정의합니다. 부르는 곳이 아직 없고, 승인 사례 저장과 틀린 기억 정정은 없습니다
- `build.py` — 갈림길 `after_route`·`after_search`·`after_grade`를 정해 compile합니다. MCP 장애는 채점·재검색하지 않으며 검색 상한은 `MAX_TRIES`(2)입니다
