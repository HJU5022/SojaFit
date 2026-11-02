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
- `nodes.py` — 줄기 노드 함수. 지금은 입력 읽기(`read_input`: 입력 글 나누기, `connections.json`에서 대상 부품과 핀 3개 이하 이웃 부품 너머까지 2단계 넷 읽기), 라우팅(`route`: 질문 종류 5가지, 프롬프트 `backend/prompts/route.md`), 검색(`search`: 질문 품번, 없으면 대상 값 품번으로 `retrieve`의 `parts`를 정함. 품번 뽑기는 `find_parts`, 회로 기호·값·개정 코드는 뺌)이 있음
- `build.py` — 그래프 조립(Supervisor, 서브에이전트, 체크포인트, interrupt) 자리. 지금은 `build_graph()`가 `NotImplementedError`를 내는 빈 틀
