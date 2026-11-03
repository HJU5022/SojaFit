"""그래프 조립 (G4). 노드(`nodes.py`)를 이어 compile한 LangGraph 앱을 만들고 갈림길 두 개를 정한다.

- 역할: `build_graph(retriever, checkpointer)`가 앱을 돌려주고, `evals/runners/run_graph.py`(평가)와 시험이 `app.invoke({"input": ...})`로 돌린다.
- 하지 않는 일: 노드 동작(`nodes.py`), 상태 칸 정의(`state.py`), Supervisor·서브에이전트 분리와 사람 승인(interrupt)은 아직 없다(D5, SPEC 2절).
- 출처: SPEC.md 2절 "그래프"(노드 표, 재검색 상한), backend/graph/GRAPH.md, ADR 0006(근거가 없어도 대화는 이어 간다), 강의 2주 20강.
- 근거 충분 여부는 어휘 겹침 같은 점수 하나로 정하지 않고, 품번·개정판 같은 결정적 검사를 따로 둔다(채점 노드).
  품번 목록·낱말 가중치 같은 코퍼스 의존 값은 코드에 고정하지 않는다(코퍼스가 커지면 새 대상을 전부 거절하게 된다).
"""
from langgraph.graph import END, START, StateGraph

from backend.graph import nodes
from backend.graph.state import AgentState

# 검색 상한: 첫 검색 + 재작성 뒤 1번(SPEC 2절)
# [주의] 시험은 이 상수 대신 리터럴 2와 비교하고 retrieve 호출 횟수를 센다. 상수끼리 비교하면 상한을 바꿔도 통과한다(docs/GATES.md 변이 확인)
MAX_TRIES = 2


def after_route(state: AgentState) -> str:
    """라우팅 뒤 갈림길: 범위 밖은 거절, 역할은 바로 생성, 나머지(정격·후보 판정·후보 찾기)는 "검색"(연결표가 재작성으로 먼저 보낸다). 돌려주는 값은 갈 노드 이름이다(SPEC 2절)."""
    if state.get("question_type") == "out_of_scope":
        return "거절"  # 검색조차 하지 않는다
    if state.get("question_type") == "role":
        return "생성"  # [왜] 역할은 데이터시트가 아니라 넷리스트 연결로 답한다. 생성 노드가 [넷리스트] 근거를 붙인다
    return "검색"  # 갈림길 값은 "검색"이지만 아래 연결에서 재작성으로 먼저 간다


def after_search(state: AgentState) -> str:
    """검색 장애는 빈 결과와 달리 채점·재검색하지 않고 안전하게 끝낸다."""
    return "거절" if state.get("retrieval_error") else "채점"


def after_grade(state: AgentState) -> str:
    """채점 뒤 갈림길: 통과 청크가 있으면 생성, 다시 찾아도 소용없거나 상한에 닿았으면 거절, 아니면 재작성(SPEC 2절)."""
    if state.get("passed"):
        return "생성"  # 통과 청크가 하나라도 있으면 답한다
    if not state.get("docs"):
        # [왜] 재작성은 품번 필터를 바꾸지 않는다. 코퍼스에 없는 품번(1N4001)이라 0장이면 다시 찾아도 0장이고 LLM 호출만 버린다(11-02 조장 결정)
        return "거절"
    if state.get("tries", 0) >= MAX_TRIES:
        return "거절"  # 상한에 닿았다. 더 돌면 LLM 호출만 늘어난다
    return "재작성"


def build_graph(retriever=None, checkpointer=None):
    """줄기 그래프(D4 단일 에이전트)를 조립해 compile한 앱을 돌려준다(SPEC 2절 노드 표)."""
    # [왜] 검색기와 체크포인터를 인자로 받아야 가짜 검색기·메모리 체크포인터로 키 없이 시험하고 요청 수를 셀 수 있다
    # retriever: (question, *, parts) 모양의 검색 함수. checkpointer: None이면 대화를 저장하지 않는다
    if retriever is None:
        # [왜] 여기서 불러와야 가짜 검색기를 넣는 시험이 DB·키 없이 돈다
        from backend.rag.retrieve import retrieve as retriever
    b = StateGraph(AgentState)  # AgentState가 메모장 칸과 합치는 규칙(리듀서)을 정한다
    for name, fn in [("입력 읽기", nodes.read_input), ("라우팅", nodes.route),
                     ("검색", lambda state: nodes.search(state, retriever)),  # 검색 노드만 검색기를 받는다
                     ("채점", nodes.grade), ("재작성", nodes.rewrite), ("생성", nodes.generate), ("거절", nodes.refuse)]:
        b.add_node(name, fn)  # [주의] 노드 이름은 갈림길이 돌려주는 값, path 칸에 남는 이름과 같아야 한다

    b.add_edge(START, "입력 읽기")  # 항상 입력 읽기에서 시작한다
    b.add_edge("입력 읽기", "라우팅")
    b.add_conditional_edges("라우팅", after_route, {"거절": "거절", "생성": "생성", "검색": "재작성"})  # {갈림길이 돌려준 값: 갈 노드}. [왜] 첫 검색부터 재작성한 검색어로 찾는다(사전 등록 #25 Q3)
    b.add_conditional_edges("검색", after_search, {"채점": "채점", "거절": "거절"})
    b.add_conditional_edges("채점", after_grade, {"생성": "생성", "재작성": "재작성", "거절": "거절"})
    b.add_edge("재작성", "검색")  # 되돌아가는 길. 무한히 돌지 않게 after_grade가 tries로 막는다
    b.add_edge("생성", END)
    b.add_edge("거절", END)
    # checkpointer를 주면 thread마다 메모장이 저장돼 다음 메시지에서 이어진다(강의 2주 05강). 시험에서는 None
    return b.compile(checkpointer=checkpointer)
