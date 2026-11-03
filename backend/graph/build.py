"""그래프 조립 (G4).

필수:
  - Supervisor와 서브에이전트 2개 이상 (역할과 컨텍스트를 나눈다)
  - 체크포인트 (재개 가능, DB에 저장)
  - 사람 승인(interrupt) 지점 1곳 이상
권장 순서:
  - D4(11/5) 단일 에이전트 그래프로 기준 점수를 잰다 (역할 파악, 대체 조건 도출, 후보 검색, 판정, 재검색)
  - D5(11/6) Supervisor와 서브에이전트로 나누고 같은 평가셋(v2)으로 다시 잰다
시험하기 쉽게 만드는 법:
  - 검색기와 체크포인터를 인자로 받는다: build_graph(retriever=None, checkpointer=None).
    그래야 가짜 검색기와 메모리 체크포인터로 키 없이 시험하고, 요청 수를 셀 수 있다.
  - 재작성 횟수 상한은 상수 하나로 둔다. 시험에서는 상수 대신 리터럴(예: 2)과 비교하고 retrieve 호출 횟수를 센다
    (상수끼리 비교하면 상한을 바꿔도 통과한다. docs/GATES.md 변이 확인).
  - 근거 충분 여부를 어휘 겹침 같은 점수 하나로만 정하지 말고, 품번·제조사·개정판·시험 조건(온도·전류)이 질문과 맞는지 같은 결정적 검사를 따로 둔다
    (예: 1N4148을 물었는데 1N4148W 카드를 인용하거나, TJ = 25°C 값을 물었는데 100°C 값을 인용하는 실패를 막는다).
  - 품번 목록, 낱말 가중치 같은 코퍼스 의존 값을 코드에 고정하지 않는다. 코퍼스가 커지면 새 대상을 전부 거절하게 된다.
"""
from langgraph.graph import END, START, StateGraph

from backend.graph import nodes
from backend.graph.state import AgentState

MAX_TRIES = 2  # 검색 상한: 첫 검색 + 재작성 뒤 1번(SPEC 2절)


def after_route(state: AgentState) -> str:
    """라우팅 뒤 갈림길: 범위 밖은 거절, 역할은 바로 생성, 나머지(정격·후보 판정·후보 찾기)는 검색(SPEC 2절, 강의 2주 20강 라우팅후)."""
    if state.get("question_type") == "out_of_scope":
        return "거절"  # 검색조차 하지 않는다
    if state.get("question_type") == "role":
        return "생성"  # [왜] 역할은 데이터시트가 아니라 넷리스트 연결로 답한다. 생성 노드가 [넷리스트] 근거를 붙인다
    return "검색"


def after_search(state: AgentState) -> str:
    """검색 장애는 빈 결과와 달리 채점·재검색하지 않고 안전하게 끝낸다."""
    return "거절" if state.get("retrieval_error") else "채점"


def after_grade(state: AgentState) -> str:
    """채점 뒤 갈림길: 통과 카드가 있으면 생성, 다시 찾아도 소용없거나 상한에 닿았으면 거절, 아니면 재작성(강의 2주 20강 채점후)."""
    if state.get("passed"):
        return "생성"  # 통과 카드가 하나라도 있으면 답한다
    if not state.get("docs"):
        # [왜] 재작성은 품번 필터를 바꾸지 않는다. 코퍼스에 없는 품번(1N4001)이라 0장이면 다시 찾아도 0장이고 LLM 호출만 버린다(11-02 조장 결정)
        return "거절"
    if state.get("tries", 0) >= MAX_TRIES:
        return "거절"
    return "재작성"


def build_graph(retriever=None, checkpointer=None):
    """줄기 그래프(D4 단일 에이전트)를 조립해 compile한 앱을 돌려준다(SPEC 2절 노드 표, 강의 2주 20강 조립)."""
    if retriever is None:
        # [왜] 여기서 불러와야 가짜 검색기를 넣는 시험이 DB·키 없이 돈다
        from backend.rag.retrieve import retrieve as retriever
    b = StateGraph(AgentState)
    for name, fn in [("입력 읽기", nodes.read_input), ("라우팅", nodes.route),
                     ("검색", lambda state: nodes.search(state, retriever)),  # 검색 노드만 검색기를 받는다
                     ("채점", nodes.grade), ("재작성", nodes.rewrite), ("생성", nodes.generate), ("거절", nodes.refuse)]:
        b.add_node(name, fn)  # [주의] 노드 이름은 갈림길이 돌려주는 값, path 칸에 남는 이름과 같아야 한다

    b.add_edge(START, "입력 읽기")
    b.add_edge("입력 읽기", "라우팅")
    b.add_conditional_edges("라우팅", after_route, {"거절": "거절", "생성": "생성", "검색": "검색"})  # {갈림길이 돌려준 값: 갈 노드}
    b.add_conditional_edges("검색", after_search, {"채점": "채점", "거절": "거절"})
    b.add_conditional_edges("채점", after_grade, {"생성": "생성", "재작성": "재작성", "거절": "거절"})
    b.add_edge("재작성", "검색")  # 되돌아가는 길. 무한히 돌지 않게 after_grade가 tries로 막는다
    b.add_edge("생성", END)
    b.add_edge("거절", END)
    # checkpointer를 주면 thread마다 메모장이 저장돼 다음 메시지에서 이어진다(강의 2주 05강). 시험에서는 None
    return b.compile(checkpointer=checkpointer)
