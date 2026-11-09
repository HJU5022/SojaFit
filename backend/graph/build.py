"""그래프 조립 (G4). D4 v2 단일 에이전트 그래프: 노드(`nodes.py`)를 이어 compile하고 갈림길(라우팅 · 검색 · 채점 · 판정 뒤)을 정한다.

- 역할: `build_graph(retriever, checkpointer, *, lookup, specs, find, chat)`가 앱을 돌려주고, `evals/runners/run_graph.py`(평가)와 시험이
  `app.invoke({"input": ...})`로 돌린다. 흐름: 입력 읽기 → 사실 확인 → 라우팅 → 거절 / 짧은 답 / 가격 안내 / 생성(역할) /
  재작성 → 검색 → 채점 고리(정격) / 판정 읽기 → 판정 → 답 틀(판정 · 찾기, specs · find를 줬을 때). 판정은 빠진 값을 인터럽트로 한 번 묻는다.
- 하지 않는 일: 노드 동작(`nodes.py`), 상태 칸 정의(`state.py`), Supervisor와 서브에이전트(멀티 그래프 `backend/multi_agent/`),
  체크포인터 만들기(부르는 쪽이 넘긴다), 견적서 저장 승인(interrupt)과 장기 기억 Store 연결(아직 없음, SPEC 2절).
- 출처: SPEC.md 2절 "그래프"(노드 표, 재검색 상한), backend/graph/GRAPH.md, ADR 0006(근거가 없어도 대화는 이어 간다), 강의 2주 20강,
  D4 v2 흐름(11-06: 범위 판정을 첫 단에서, 단순 직렬 흐름이 아니게, GRAPH.md 설계 근거), docs/specs/judge-agent.md(판정 길).
- 근거 충분 여부는 어휘 겹침 같은 점수 하나로 정하지 않고, 품번·개정판 같은 결정적 검사를 따로 둔다(채점 노드).
  품번 목록·낱말 가중치 같은 코퍼스 의존 값은 코드에 고정하지 않는다(코퍼스가 커지면 새 대상을 전부 거절하게 된다).
"""
from functools import partial

from langgraph.graph import END, START, StateGraph

from backend.graph import nodes
from backend.graph.state import AgentState
from backend.multi_agent.facts import facts_node
from backend.services import llm

# 검색 상한: 첫 검색 + 재작성 뒤 1번(SPEC 2절)
# [주의] 시험은 이 상수 대신 리터럴 2와 비교하고 retrieve 호출 횟수를 센다. 상수끼리 비교하면 상한을 바꿔도 통과한다(docs/GATES.md 변이 확인)
MAX_TRIES = 2


def after_route(state: AgentState) -> str:
    """라우팅 뒤 갈림길: 거절 사유가 있으면 거절, 일상 대화는 짧은 답, 가격은 가격 안내, 역할은 바로 생성, 판정 · 찾기는 "판정", 정격은 "검색"(SPEC 2절).

    돌려주는 값은 갈림길 값이고, 갈 노드는 build_graph의 연결표가 정한다("검색"은 재작성으로 먼저, "판정"은 판정 길이 없으면 재작성으로).
    """
    if (state.get("route") or {}).get("reason"):
        # [왜] 범위 판정을 첫 단에서 한다: 범위 밖 · 다른 부품 · 코퍼스에 없는 품번 · 개정판은 검색조차 하지 않는다(GRAPH.md 설계 근거)
        return "거절"
    question_type = state.get("question_type")
    if question_type == "chat":
        return "짧은 답"  # 라우팅이 낸 reply로 끝낸다
    if question_type == "price":
        return "가격 안내"  # [왜] 가격 · 재고 값은 그래프 밖 화면이 조회한다. 그래프는 품번만 정하고 끝낸다(ADR 0009)
    if question_type == "role":
        return "생성"  # [왜] 역할은 데이터시트가 아니라 넷리스트 연결로 답한다. 생성 노드가 [넷리스트] 근거를 붙인다
    if question_type in ("candidate_judge", "candidate_find"):
        return "판정"
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


def after_judge(state: AgentState) -> str:
    """판정 뒤 갈림길: 사양 표 도구 장애(검색 장애)나 코퍼스 밖 요구(판정이 남긴 거절 코드, SPEC 8.3)면 거절, 아니면 답 틀."""
    return "거절" if state.get("retrieval_error") or state.get("refusal") else "답 틀"


def build_graph(retriever=None, checkpointer=None, *, lookup=None, specs=None, find=None, chat=None, store=None):
    """D4 v2 단일 에이전트 그래프를 조립해 compile한 앱을 돌려준다(SPEC 2절 노드 표).

    specs · find를 둘 다 주면 판정 · 찾기 질문이 판정 길로 가고, 주지 않으면 예전처럼 검색 고리로 간다(기존 호출을 깨지 않는다).
    Raises:
        ValueError: specs · find 중 하나만 주거나, 판정 길에 체크포인터가 없을 때(인터럽트 재개에 필요).
    """
    # [왜] 검색기와 체크포인터를 인자로 받아야 가짜 검색기·메모리 체크포인터로 키 없이 시험하고 요청 수를 셀 수 있다
    # retriever: (question, *, parts) 모양의 검색 함수. checkpointer: None이면 대화를 저장하지 않는다
    # lookup: 사실 확인 함수(state → Facts, 멀티와 같은 `make_lookup(mcp.check)`). None이면 확인 없이 비워 둔다
    # specs · find: 사양 표 도구(MCP `get_part_specs` · `find_parts_by_specs`). chat: 판정 읽기 LLM 호출, None이면 `llm.node_chat`
    judging = specs is not None or find is not None
    if judging and (specs is None or find is None or checkpointer is None):
        raise ValueError("판정 길은 사양 표 도구(specs · find)와 체크포인터가 있어야 잇습니다")  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
    if retriever is None:
        # [왜] 여기서 불러와야 가짜 검색기를 넣는 시험이 DB·키 없이 돈다
        from backend.rag.retrieve import retrieve as retriever
    b = StateGraph(AgentState)  # AgentState가 메모장 칸과 합치는 규칙(리듀서)을 정한다
    for name, fn in [("입력 읽기", nodes.read_input), ("사실 확인", partial(facts_node, lookup=lookup)), ("라우팅", nodes.route),
                     ("검색", lambda state: nodes.search(state, retriever)),  # 검색 노드만 검색기를 받는다
                     ("채점", nodes.grade), ("재작성", nodes.rewrite), ("생성", nodes.generate), ("거절", nodes.refuse),
                     ("짧은 답", nodes.short_reply), ("가격 안내", nodes.price_answer)]:
        b.add_node(name, fn)  # [주의] 노드 이름은 갈림길이 돌려주는 값, path 칸에 남는 이름과 같아야 한다
    if judging:
        from backend.multi_agent.agents.judge import judge_read_agent  # [왜] 판정 길을 이을 때만 판정 규칙 · 프롬프트를 읽는다
        b.add_node("판정 읽기", partial(judge_read_agent, chat=chat or llm.node_chat))  # 멀티와 같은 읽기 노드(LLM 1번)
        b.add_node("판정", partial(nodes.judge, specs=specs, find=find, retriever=retriever))
        b.add_node("답 틀", nodes.judgement_answer)
        b.add_edge("판정 읽기", "판정")  # [왜] 읽기 → 판정. 판정이 인터럽트로 멈췄다 재개해도 읽기는 다시 돌지 않는다
        b.add_conditional_edges("판정", after_judge, {"답 틀": "답 틀", "거절": "거절"})
        b.add_edge("답 틀", END)

    b.add_edge(START, "입력 읽기")  # 항상 입력 읽기에서 시작한다
    b.add_edge("입력 읽기", "사실 확인")
    b.add_edge("사실 확인", "라우팅")  # [왜] 범위 판정을 첫 단에서 한다: 라우팅이 확인된 사실로 검색 전에 거절을 정한다(GRAPH.md 설계 근거)
    # {갈림길이 돌려준 값: 갈 노드}. [왜] 첫 검색부터 재작성한 검색어로 찾는다(사전 등록 #25 Q3)
    b.add_conditional_edges("라우팅", after_route, {"거절": "거절", "짧은 답": "짧은 답", "가격 안내": "가격 안내", "생성": "생성", "검색": "재작성",
                                                     "판정": "판정 읽기" if judging else "재작성"})
    b.add_conditional_edges("검색", after_search, {"채점": "채점", "거절": "거절"})
    b.add_conditional_edges("채점", after_grade, {"생성": "생성", "재작성": "재작성", "거절": "거절"})
    b.add_edge("재작성", "검색")  # 되돌아가는 길. 무한히 돌지 않게 after_grade가 tries로 막는다
    b.add_edge("생성", END)
    b.add_edge("거절", END)
    b.add_edge("짧은 답", END)
    b.add_edge("가격 안내", END)
    # checkpointer를 주면 thread마다 메모장이 저장돼 다음 메시지에서 이어진다(강의 2주 05강). 시험에서는 None
    return b.compile(checkpointer=checkpointer, store=store)
