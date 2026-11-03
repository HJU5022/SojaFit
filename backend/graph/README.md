# graph

## 역할
- 이 폴더: LangGraph 상태 그래프를 둡니다. Supervisor, 서브에이전트 2개 이상, 체크포인트, 사람 승인(interrupt) 뒤 재개가 여기서 조립됩니다(G4).
- 넣는 것: 그래프 상태 정의, 노드와 분기, 체크포인트 설정, 승인 지점.
- 넣지 않는 것: 숫자 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`만 씁니다), 검색 구현(`backend/rag/`).
- 담당: 에이전트

## 흐름
역할 파악 → 대체 조건 도출 → 후보 검색 → 판정 → 견적서 승인. 정보가 모자라면 되묻고, 값이 없으면 다시 찾고, 그래도 없으면 판정을 보류합니다.

## 강사 안내
11/5(D4)에 단일 에이전트 그래프로 기준 점수를 재고, 11/6(D5)에 Supervisor와 서브에이전트로 나눠 같은 평가셋으로 다시 잽니다. 단일을 건너뛰면 멀티가 나았다는 걸 증명할 기준이 없습니다. 개선이 없었다면 없었다고 `EVAL_REPORT.md`에 적습니다.

## 파일
- `state.py` — 그래프 상태(공용 메모장) 정의. SPEC 2절 노드 표의 칸들과, 쌓이는 칸 `tries`(검색 횟수)·`path`(지나간 노드)
- `nodes.py` — 줄기 노드 함수 7개. 지금은 입력 읽기(`read_input`: 입력 글 나누기, `connections.json`에서 대상 부품과 핀 3개 이하 이웃 부품 너머까지 2단계 넷 읽기), 라우팅(`route`: 질문 종류 5가지, 프롬프트 `backend/prompts/route.md`), 검색(`search`: 질문 품번, 없으면 대상 값 품번으로 `retrieve`의 `parts`를 정함. 품번 뽑기는 `find_parts`, 회로 기호·값·개정 코드는 뺌), 채점(`grade`: 다른 품번 줄·다른 개정판 카드를 규칙으로 뺀 뒤 LLM 1회, 프롬프트 `backend/prompts/grade.md`), 재작성(`rewrite`: 원래 질문을 영어 검색어 한 줄로, 프롬프트 `backend/prompts/rewrite.md`), 생성(`generate`: 통과 카드와 `[넷리스트]`만 근거로 답하고 없는 근거 인용·인용 없는 문장을 `check`에 기록, 프롬프트 `backend/prompts/generate.md`), 거절(`refuse`: LLM 없이 범위 밖 / 품번 문서 없음 / 찾은 문서에 답 없음을 나눠 적고 단서 요청)이 있음
- `build.py` — 그래프 조립(Supervisor, 서브에이전트, 체크포인트, interrupt) 자리. 지금은 D4 줄기(단일 에이전트)만 있다. `build_graph(retriever, checkpointer)`가 입력 읽기 → 라우팅 → 라우팅 뒤 갈림길 `after_route`(범위 밖은 거절, 역할은 생성, 나머지는 검색) → 검색 → 채점 → 채점 뒤 갈림길 `after_grade`(통과 있으면 생성, 검색 0장이거나 검색 2번이면 거절, 아니면 재작성 → 검색)를 잇는다. 검색 상한은 `MAX_TRIES`. Supervisor·서브에이전트·interrupt는 아직 없다
