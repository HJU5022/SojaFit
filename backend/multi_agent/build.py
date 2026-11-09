"""멀티 에이전트 조립: Supervisor를 가운데 두고 서브에이전트가 끝날 때마다 Supervisor로 돌아오는 그래프를 만든다.

- 역할: 입력 읽기 → 사실 확인 → Supervisor, 그리고 Supervisor의 결정(search · judge · writer · verifier · finish · refuse · price)에 따라
  서브에이전트나 끝내기 노드로 가는 연결을 정하고 compile한다. LLM · 검색기 · 단일 그래프 함수는 인자로 받아 시험에서 가짜로 바꾼다.
  판정 길: Supervisor → 판정 읽기 → 판정(인터럽트 1번) → Supervisor. 가격 길: Supervisor → 가격 안내(단일 그래프와 같은 노드) → 끝.
- 하지 않는 일: 판단 규칙(프롬프트와 Supervisor의 몫), 웹 조회 에이전트(아직 없어서 켜려 하면 거부한다), 체크포인터 만들기(부르는 쪽이 넘긴다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/build.py(조립 방식을 따름)
"""
from functools import partial

from langgraph.graph import END, START, StateGraph

from backend.multi_agent import facts as facts_mod
from backend.multi_agent import supervisor as sup
from backend.multi_agent.agents.search import search_agent
from backend.multi_agent.agents.verifier import verifier_agent
from backend.multi_agent.agents.writer import writer_agent
from backend.multi_agent.contracts import Counters, Reason
from backend.multi_agent.messages import refusal_for
from backend.multi_agent.state import MultiState

KEYS = set(MultiState.__annotations__) - {'path'}


def parse_node(state: dict, *, parse) -> dict:
    """입력 읽기: 단일 그래프의 `read_input`을 그대로 쓰고, 턴마다 보고 · 횟수 · 결정을 비운다."""
    fields = {k: v for k, v in parse(state).items() if k in KEYS}  # 단일 그래프의 tries 같은 칸은 이 메모장에 없다
    # [왜] 판정 칸도 비운다. 같은 thread의 다음 질문에서 앞 질문의 판정으로 답을 쓰지 않게 한다(작성은 judgement가 있으면 판정 틀로 쓴다)
    return {**fields, 'facts': {}, 'decision': {}, 'reports': [], 'counters': Counters().model_dump(mode='json'),
            'answer': '', 'refusal': {}, 'judge_read': {}, 'judgement': {}, 'price_parts': [], 'path': ['입력 읽기']}


def finish_node(state: dict) -> dict:
    """끝내기: 일상 대화는 Supervisor의 reply가 답이다. 작성 · 검증을 거친 답은 이미 answer에 있다."""
    reply = (state.get('decision') or {}).get('reply', '')
    return {'answer': reply, 'path': ['끝']} if reply else {'path': ['끝']}


def refuse_node(state: dict) -> dict:
    """거절: 이유 코드는 `refusal`에 남기고(Langfuse로), 사용자에게는 일상어 문구를 답으로 준다."""
    reason = Reason(state['decision']['reason'])
    message = refusal_for(reason, state.get('facts') or {})
    return {'answer': message, 'check': {}, 'refusal': {'code': reason.value, 'message': message}, 'path': ['거절']}


def next_node(state: dict) -> str:
    return state['decision']['next']


def build_graph(*, chat, retriever, rewrite=None, grade=None, generate=None, parse=None, lookup=None, enforce_verify: bool = True,
                web_enabled: bool = False, judge_enabled: bool = False, specs=None, find=None, checkpointer=None, store=None):
    """멀티 에이전트 그래프를 만들어 compile한다. chat은 `(node, system, user, schema)` 모양의 LLM 호출이다.

    판정을 켜려면 specs(`get_part_specs`) · find(`find_parts_by_specs`) 도구와 checkpointer가 필요하다(인터럽트 재개).
    """
    if web_enabled:
        raise ValueError('웹 조회 에이전트는 아직 없어 켤 수 없습니다')  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
    if judge_enabled and (specs is None or find is None or checkpointer is None):
        raise ValueError('판정 에이전트는 사양 표 도구(specs · find)와 체크포인터가 있어야 켭니다')
    from backend.graph import nodes  # [왜] 여기서 불러와야 가짜 함수를 넣는 시험이 키 없이 돈다
    rewrite, grade, generate, parse = rewrite or nodes.rewrite, grade or nodes.grade, generate or nodes.generate, parse or nodes.read_input
    g = StateGraph(MultiState)
    g.add_node('parse', partial(parse_node, parse=parse))
    g.add_node('facts', partial(facts_mod.facts_node, lookup=lookup))
    g.add_node('supervisor', partial(sup.supervisor_node, chat=chat, web_enabled=web_enabled, judge_enabled=judge_enabled))
    g.add_node('search', partial(search_agent, retriever=retriever, rewrite=rewrite, grade=grade))
    g.add_node('writer', partial(writer_agent, generate=generate))
    g.add_node('verifier', partial(verifier_agent, enforce=enforce_verify))
    g.add_node('finish', finish_node)
    g.add_node('refuse', refuse_node)
    # [왜] 가격 안내는 단일 그래프 노드를 그대로 쓴다. Mouser는 그래프 밖 /api/prices만 부른다(ADR 0009)
    g.add_node('price', nodes.price_answer)
    g.add_edge(START, 'parse')
    g.add_edge('parse', 'facts')
    g.add_edge('facts', 'supervisor')
    targets = {'search': 'search', 'writer': 'writer', 'verifier': 'verifier', 'finish': 'finish', 'refuse': 'refuse', 'price': 'price'}
    if judge_enabled:
        from backend.multi_agent.agents.judge import judge_agent, judge_read_agent
        g.add_node('judge_read', partial(judge_read_agent, chat=chat))
        g.add_node('judge', partial(judge_agent, specs=specs, find=find, retriever=retriever))
        g.add_edge('judge_read', 'judge')  # [왜] 읽기 → 판정. 판정 노드가 인터럽트로 멈췄다 재개해도 읽기는 다시 돌지 않는다
        g.add_edge('judge', 'supervisor')
        targets['judge'] = 'judge_read'
    g.add_conditional_edges('supervisor', next_node, targets)
    for agent in ('search', 'writer', 'verifier'):
        g.add_edge(agent, 'supervisor')  # [왜] 서브에이전트는 끝나면 반드시 Supervisor로 돌아온다(허브 구조, 결정 11-05)
    g.add_edge('finish', END)
    g.add_edge('refuse', END)
    g.add_edge('price', END)
    return g.compile(checkpointer=checkpointer, store=store)
