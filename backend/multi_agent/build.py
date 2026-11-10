"""멀티 에이전트 조립: 입력 읽기 → 기억 읽기 → 품번·판 확인 → Supervisor → RAG 에이전트 · 대체 부품 에이전트(Send 동시 실행) → 답 모으기 → 답 정리 · 종합 → 답 검사 → 끝내기.

- 역할: 노드와 연결을 정하고 compile한다. 노드 이름은 강의처럼 한국어로 달아 `get_graph().draw_mermaid()` 그림이 그대로 읽히게 한다.
  답 모으기 → Supervisor 되돌림(재계획, 설계 v2)이 유일한 고리다. 서브에이전트는 RAG 에이전트(`agents/docs.py`, 노드 하나)와
  대체 부품 에이전트(회로 역할 읽기 → 대체 부품 판정 두 노드의 하위 그래프, 인터럽트 재개 때 읽기 LLM을 다시 부르지 않게)다.
  일상 대화는 계획의 reply로 끝, 가격 · 재고는 가격 안내(단일 그래프와 같은 노드)로 끝, 범위 밖 · 코퍼스 밖은 거절로 끝난다.
  LLM · 검색기 · 사양 표 도구는 인자로 받아 시험에서 가짜로 바꾼다. 기억 읽기는 compile에 넘긴 Store에서 선호 실장 방식만 읽는다(`graph/memory.py`).
- 하지 않는 일: 판단 규칙(프롬프트와 Supervisor의 몫), 웹 조회 에이전트(아직 없어서 켜려 하면 거부한다), 체크포인터 만들기(부르는 쪽이 넘긴다).
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"(11-06 재설계), backend/graph/build.py(조립 방식을 따름)
"""
from functools import partial

from langgraph.graph import END, START, StateGraph

from backend.graph.memory import read_profile
from backend.multi_agent import facts as facts_mod
from backend.multi_agent import supervisor as sup
from backend.multi_agent.agents.docs import docs_agent
from backend.multi_agent.contracts import Reason
from backend.multi_agent.messages import refusal_for
from backend.multi_agent.state import JudgeOut, JudgeState, MultiState

KEYS = set(MultiState.__annotations__) - {'path', 'reports'}


def parse_node(state: dict, *, parse) -> dict:
    """입력 읽기: 단일 그래프의 `read_input`을 그대로 쓰고, 턴마다 계획 · 보고 · 답 칸을 비운다."""
    fields = {k: v for k, v in parse(state).items() if k in KEYS}  # 단일 그래프의 tries 같은 칸은 이 메모장에 없다
    # [왜] 같은 thread의 다음 질문에서 앞 질문의 보고 · 판정으로 답을 쓰지 않게 비운다(reports는 None을 받으면 비우는 합치기 규칙)
    return {**fields, 'facts': {}, 'plan': {}, 'question_type': '', 'counters': {'hops': 0, 'agents': 0, 'searches': 0, 'replans': 0},
            'reports': None, 'round': 0, 'final_reports': [], 'outcome': '', 'refusal_reason': '', 'synth_text': '', 'docs': [], 'passed': [], 'judgement': {}, 'price_parts': [],
            'answer': '', 'check': {}, 'refusal': {}, 'memory_refs': [], 'path': ['입력 읽기']}


def finish_node(state: dict) -> dict:
    """끝내기: 일상 대화는 계획의 reply가 답이다. 서브에이전트를 거친 답은 이미 answer에 있다."""
    if not state.get('reports'):
        reply = (state.get('plan') or {}).get('reply', '')
        if '승인사례:' in reply:
            reason = Reason.VERIFY_FAILED
            return {'answer': refusal_for(reason, state.get('facts') or {}),
                    'refusal': {'code': reason.value}, 'memory_refs': [], 'path': ['끝']}
        return {'answer': reply, 'path': ['끝']}
    return {'path': ['끝']}


def refuse_node(state: dict) -> dict:
    """거절: 이유 코드는 `refusal`에 남기고(Langfuse로), 사용자에게는 일상어 문구를 답으로 준다."""
    reason = Reason(state.get('refusal_reason') or Reason.LIMIT_REACHED.value)
    message = refusal_for(reason, state.get('facts') or {})
    return {'answer': message, 'check': {}, 'refusal': {'code': reason.value, 'message': message}, 'path': ['거절']}


def judge_subgraph(*, chat, specs, find, retriever):
    """대체 부품 에이전트: 회로 역할 읽기(LLM 1번) → 대체 부품 판정(코드 관문 · 인터럽트 · 사양 표 · 비교). 하위 그래프라 재개하면 멈춘 판정 노드부터 다시 돈다."""
    from backend.multi_agent.agents.judge import judge_read_agent, judge_task_node
    g = StateGraph(JudgeState, output_schema=JudgeOut)  # [왜] 바깥 메모장에는 보고와 지나간 노드만 돌려준다. 다른 칸은 동시 실행 중 덮어쓰기 충돌이 난다
    g.add_node('회로 역할 읽기', partial(judge_read_agent, chat=chat))
    g.add_node('대체 부품 판정', partial(judge_task_node, specs=specs, find=find, retriever=retriever))
    g.add_edge(START, '회로 역할 읽기')
    g.add_edge('회로 역할 읽기', '대체 부품 판정')
    g.add_edge('대체 부품 판정', END)
    return g.compile()


def build_graph(*, chat, retriever, parse=None, lookup=None, web_enabled: bool = False, judge_enabled: bool = False,
                specs=None, find=None, checkpointer=None, store=None):
    """멀티 에이전트 그래프를 만들어 compile한다. chat은 `(node, system, user, schema)` 모양의 LLM 호출이다.

    판정을 켜려면 specs(`card_specs.default_specs()`) · find(`card_find.default_find()`) 도구와 checkpointer가 필요하다(인터럽트 재개).
    """
    if web_enabled:
        raise ValueError('웹 조회 에이전트는 아직 없어 켤 수 없습니다')  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
    if judge_enabled and (specs is None or find is None or checkpointer is None):
        raise ValueError('판정 에이전트는 사양 표 도구(specs · find)와 체크포인터가 있어야 켭니다')
    from backend.graph import nodes  # [왜] 여기서 불러와야 가짜 함수를 넣는 시험이 키 없이 돈다
    g = StateGraph(MultiState)
    # [왜] 노드 이름 = 그림에 보이는 이름. 갈림 함수(supervisor.after_*)도 이 이름을 돌려준다(supervisor.NODE)
    g.add_node('입력 읽기', partial(parse_node, parse=parse or nodes.read_input))
    g.add_node('기억 읽기', read_profile)  # Store(사용자 사실)에서 선호 실장 방식만 읽는다. Store 없이 compile하면(평가 실행기) 선호 없음
    g.add_node('품번·판 확인', partial(facts_mod.facts_node, lookup=lookup))
    g.add_node('Supervisor', partial(sup.plan_node, chat=chat, judge_enabled=judge_enabled))  # 계획(LLM 1번)
    g.add_node('RAG 에이전트', partial(docs_agent, retriever=retriever, chat=chat, find=find))  # find: 품번 없이 정격만 준 질문의 품번 찾기
    g.add_node('답 모으기', sup.collect_node)  # 코드만(LLM 없음). 두 번째 Supervisor가 아니다
    g.add_node('답 정리', sup.single_node)
    g.add_node('종합', partial(sup.synth_node, chat=chat))
    g.add_node('답 검사', sup.check_node)
    g.add_node('끝내기', finish_node)
    g.add_node('거절', refuse_node)
    # [왜] 가격 안내는 단일 그래프 노드를 그대로 쓴다. Mouser는 그래프 밖 /api/prices만 부른다(ADR 0009)
    g.add_node('가격 안내', nodes.price_answer)
    g.add_edge(START, '입력 읽기')
    g.add_edge('입력 읽기', '기억 읽기')
    g.add_edge('기억 읽기', '품번·판 확인')
    g.add_edge('품번·판 확인', 'Supervisor')
    agents = ['RAG 에이전트']
    if judge_enabled:
        g.add_node('대체 부품 에이전트', judge_subgraph(chat=chat, specs=specs, find=find, retriever=retriever))
        agents.append('대체 부품 에이전트')
    # [왜] 목록(path_map)의 이름 = 노드 이름이라 그림에 라벨이 붙지 않는다. 할 일이 둘이면 두 에이전트에 동시에 Send
    g.add_conditional_edges('Supervisor', sup.after_plan, ['끝내기', '가격 안내', '거절', '답 모으기', *agents])  # 답 모으기: 재계획이 '있는 답으로'
    for agent in agents:
        g.add_edge(agent, '답 모으기')  # [왜] 같은 단계에서 동시에 돈 서브에이전트가 모두 끝나야 모으기가 한 번 돈다
    # [왜] 설계 v2(11-07): 모으기가 다시 해 볼 만한 실패를 보면 Supervisor로 한 번 되돌린다(MAX_REPLANS). 이 간선만 키가 노드 이름과 달라 그림에 조건이 라벨로 보인다
    g.add_conditional_edges('답 모으기', sup.after_collect, {'답 정리': '답 정리', '종합': '종합', '거절': '거절', sup.REPLAN: 'Supervisor'})
    g.add_edge('답 정리', '답 검사')
    g.add_edge('종합', '답 검사')
    g.add_conditional_edges('답 검사', sup.after_check, ['끝내기', '거절'])
    g.add_edge('끝내기', END)
    g.add_edge('거절', END)
    g.add_edge('가격 안내', END)
    return g.compile(checkpointer=checkpointer, store=store)
