"""멀티 에이전트 조립: 입력 읽기 → 사실 확인 → Supervisor ① 계획 → 서브에이전트(Send 동시 실행) → Supervisor ② 모으기 · 종합 → 답 검사 → 끝.

- 역할: 노드와 연결을 정하고 compile한다. 모으기 → 계획 되돌림(재계획, 설계 v2)이 유일한 고리다. 서브에이전트는 문서 에이전트(`agents/docs.py`, 노드 하나)와
  판정 에이전트(읽기 → 판정 두 노드의 하위 그래프, 인터럽트 재개 때 읽기 LLM을 다시 부르지 않게)다.
  일상 대화는 계획의 reply로 끝, 가격 · 재고는 가격 안내(단일 그래프와 같은 노드)로 끝, 범위 밖 · 코퍼스 밖은 거절로 끝난다.
  LLM · 검색기 · 사양 표 도구는 인자로 받아 시험에서 가짜로 바꾼다.
- 하지 않는 일: 판단 규칙(프롬프트와 Supervisor의 몫), 웹 조회 에이전트(아직 없어서 켜려 하면 거부한다), 체크포인터 만들기(부르는 쪽이 넘긴다).
- 출처: 참조/아티팩트 "SojaFit 멀티 에이전트 구조"(11-06 정운 결정), backend/graph/build.py(조립 방식을 따름)
"""
from functools import partial

from langgraph.graph import END, START, StateGraph

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
    """판정 에이전트: 읽기(LLM 1번) → 판정(코드 관문 · 인터럽트 · 사양 표 · 비교). 하위 그래프라 재개하면 멈춘 판정 노드부터 다시 돈다."""
    from backend.multi_agent.agents.judge import judge_read_agent, judge_task_node
    g = StateGraph(JudgeState, output_schema=JudgeOut)  # [왜] 바깥 메모장에는 보고와 지나간 노드만 돌려준다. 다른 칸은 동시 실행 중 덮어쓰기 충돌이 난다
    g.add_node('judge_read', partial(judge_read_agent, chat=chat))
    g.add_node('judge', partial(judge_task_node, specs=specs, find=find, retriever=retriever))
    g.add_edge(START, 'judge_read')
    g.add_edge('judge_read', 'judge')
    g.add_edge('judge', END)
    return g.compile()


def build_graph(*, chat, retriever, parse=None, lookup=None, web_enabled: bool = False, judge_enabled: bool = False,
                specs=None, find=None, checkpointer=None, store=None):
    """멀티 에이전트 그래프를 만들어 compile한다. chat은 `(node, system, user, schema)` 모양의 LLM 호출이다.

    판정을 켜려면 specs(`get_part_specs`) · find(`find_parts_by_specs`) 도구와 checkpointer가 필요하다(인터럽트 재개).
    """
    if web_enabled:
        raise ValueError('웹 조회 에이전트는 아직 없어 켤 수 없습니다')  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
    if judge_enabled and (specs is None or find is None or checkpointer is None):
        raise ValueError('판정 에이전트는 사양 표 도구(specs · find)와 체크포인터가 있어야 켭니다')
    from backend.graph import nodes  # [왜] 여기서 불러와야 가짜 함수를 넣는 시험이 키 없이 돈다
    g = StateGraph(MultiState)
    g.add_node('parse', partial(parse_node, parse=parse or nodes.read_input))
    g.add_node('facts', partial(facts_mod.facts_node, lookup=lookup))
    g.add_node('plan', partial(sup.plan_node, chat=chat, judge_enabled=judge_enabled))
    g.add_node('docs', partial(docs_agent, retriever=retriever, chat=chat, find=find))  # find: 품번 없이 정격만 준 질문의 품번 찾기
    g.add_node('collect', sup.collect_node)
    g.add_node('single', sup.single_node)
    g.add_node('synth', partial(sup.synth_node, chat=chat))
    g.add_node('check', sup.check_node)
    g.add_node('finish', finish_node)
    g.add_node('refuse', refuse_node)
    # [왜] 가격 안내는 단일 그래프 노드를 그대로 쓴다. Mouser는 그래프 밖 /api/prices만 부른다(ADR 0009)
    g.add_node('price', nodes.price_answer)
    g.add_edge(START, 'parse')
    g.add_edge('parse', 'facts')
    g.add_edge('facts', 'plan')
    agents = ['docs']
    if judge_enabled:
        g.add_node('judge', judge_subgraph(chat=chat, specs=specs, find=find, retriever=retriever))
        agents.append('judge')
    g.add_conditional_edges('plan', sup.after_plan, ['finish', 'price', 'refuse', 'collect', *agents])  # collect: 재계획이 '있는 답으로'
    for agent in agents:
        g.add_edge(agent, 'collect')  # [왜] 같은 단계에서 동시에 돈 서브에이전트가 모두 끝나야 모으기가 한 번 돈다
    # [왜] 설계 v2(11-07): 모으기가 다시 해 볼 만한 실패를 보면 Supervisor ① 계획으로 한 번 되돌린다(MAX_REPLANS)
    g.add_conditional_edges('collect', sup.after_collect, {'single': 'single', 'synth': 'synth', 'refuse': 'refuse', 'replan': 'plan'})
    g.add_edge('single', 'check')
    g.add_edge('synth', 'check')
    g.add_conditional_edges('check', sup.after_check, ['finish', 'refuse'])
    g.add_edge('finish', END)
    g.add_edge('refuse', END)
    g.add_edge('price', END)
    return g.compile(checkpointer=checkpointer, store=store)
