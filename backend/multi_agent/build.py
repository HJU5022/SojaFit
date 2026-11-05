"""멀티 에이전트 조립: Supervisor를 가운데 두고 서브에이전트가 끝날 때마다 Supervisor로 돌아오는 그래프를 만든다.

- 역할: 입력 읽기 → 사실 확인 → Supervisor, 그리고 Supervisor의 결정(search · writer · verifier · finish · refuse)에 따라
  서브에이전트나 끝내기 노드로 가는 연결을 정하고 compile한다. LLM · 검색기 · 단일 그래프 함수는 인자로 받아 시험에서 가짜로 바꾼다.
- 하지 않는 일: 판단 규칙(프롬프트와 Supervisor의 몫), 판정 · 웹 조회 에이전트(아직 없어서 켜려 하면 거부한다), 체크포인트 설정.
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
from backend.multi_agent.messages import refusal_message
from backend.multi_agent.state import MultiState

KEYS = set(MultiState.__annotations__) - {'path'}


def parse_node(state: dict, *, parse) -> dict:
    """입력 읽기: 단일 그래프의 `read_input`을 그대로 쓰고, 턴마다 보고 · 횟수 · 결정을 비운다."""
    fields = {k: v for k, v in parse(state).items() if k in KEYS}  # 단일 그래프의 tries 같은 칸은 이 메모장에 없다
    return {**fields, 'facts': {}, 'decision': {}, 'reports': [], 'counters': Counters().model_dump(mode='json'),
            'answer': '', 'refusal': {}, 'path': ['입력 읽기']}


def finish_node(state: dict) -> dict:
    return {'path': ['끝']}


def refuse_node(state: dict) -> dict:
    """거절: 이유 코드는 `refusal`에 남기고(Langfuse로), 사용자에게는 일상어 문구를 답으로 준다."""
    reason = Reason(state['decision']['reason'])
    facts = state.get('facts') or {}
    missing_parts = [p for p, ok in (facts.get('parts') or {}).items() if not ok]
    missing_revs = [r for r, ok in (facts.get('revisions') or {}).items() if not ok]
    message = refusal_message(reason, missing_parts or list((facts.get('parts') or {})), missing_revs)
    return {'answer': message, 'check': {}, 'refusal': {'code': reason.value, 'message': message}, 'path': ['거절']}


def next_node(state: dict) -> str:
    return state['decision']['next']


def build_graph(*, chat, retriever, rewrite=None, grade=None, generate=None, parse=None, lookup=None, enforce_verify: bool = True,
                web_enabled: bool = False, judge_enabled: bool = False, checkpointer=None):
    """멀티 에이전트 그래프를 만들어 compile한다. chat은 `(node, system, user, schema)` 모양의 LLM 호출이다."""
    if web_enabled or judge_enabled:
        raise ValueError('웹 조회 · 판정 에이전트는 아직 없어 켤 수 없습니다')  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
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
    g.add_edge(START, 'parse')
    g.add_edge('parse', 'facts')
    g.add_edge('facts', 'supervisor')
    g.add_conditional_edges('supervisor', next_node, {'search': 'search', 'writer': 'writer', 'verifier': 'verifier', 'finish': 'finish', 'refuse': 'refuse'})
    for agent in ('search', 'writer', 'verifier'):
        g.add_edge(agent, 'supervisor')  # [왜] 서브에이전트는 끝나면 반드시 Supervisor로 돌아온다(허브 구조, 결정 11-05)
    g.add_edge('finish', END)
    g.add_edge('refuse', END)
    return g.compile(checkpointer=checkpointer)
