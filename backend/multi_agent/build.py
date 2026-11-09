"""멀티 에이전트 조립: 입력 읽기 → 품번·판 확인 → Supervisor → (RAG 에이전트 | 대체 부품 에이전트) → 답 검사 → 끝내기 · 거절.

- 역할: 노드와 간선을 정하고 compile한다. Supervisor는 다음 길 하나를 고르고(강의 15강), 갈림길은 모두 간선 표(path map)로 적는다. 갈림 함수는 노드 이름을 돌려주고 간선 표의 키도 노드 이름이다(강의 20강 {"거절": "거절"}, 그림에 영어 라벨이 없게)(강의 03강).
  - RAG 에이전트(하위 그래프): 검색 → 근거 채점·답 쓰기, 근거가 없으면 검색으로 되돌아가는 고리(강의 18 · 20강, 상한 MAX_SEARCHES).
  - 대체 부품 에이전트(하위 그래프): 회로 역할 읽기 → 대체 부품 판정. 판정이 인터럽트로 한 번 묻고(강의 09강), 재개하면
    판정 노드부터 다시 돌아 읽기 LLM을 다시 부르지 않는다.
  - 일상 대화는 Supervisor의 reply로 끝내기, 가격 · 재고는 가격 안내(단일 그래프와 같은 노드)로 끝, 범위 밖 · 코퍼스 밖은 거절로 끝난다.
  LLM · 검색기 · 사양 표 도구는 인자로 받아 시험에서 가짜로 바꾼다.
- 하지 않는 일: 판단 규칙(프롬프트와 Supervisor의 몫), 웹 조회 에이전트(아직 없어서 켜려 하면 거부한다), 체크포인터 만들기(부르는 쪽이 넘긴다).
- 출처: 강의 IV-3 15강 cell 14, 강의 IV-2 03 · 09 · 14 · 18 · 20강, 11-09 강사 피드백(Supervisor가 에이전트 앞뒤에 있어 헷갈림 · LLM 단계가 많음)
"""
from functools import partial

from langgraph.graph import END, START, StateGraph

from backend.multi_agent import facts as facts_mod
from backend.multi_agent import supervisor as sup
from backend.multi_agent.agents import docs
from backend.multi_agent.contracts import Reason
from backend.multi_agent.messages import refusal_for
from backend.multi_agent.state import JudgeIn, JudgeOut, JudgeState, MultiState, RagIn, RagOut, RagState

KEYS = set(MultiState.__annotations__) - {'path'}


def parse_node(state: dict, *, parse) -> dict:
    """입력 읽기: 단일 그래프의 `read_input`을 그대로 쓰고, 턴마다 지시서 · 답 칸을 비운다."""
    fields = {k: v for k, v in parse(state).items() if k in KEYS}  # 단일 그래프의 tries 같은 칸은 이 메모장에 없다
    # [왜] 같은 thread의 다음 질문에서 앞 질문의 지시서 · 판정으로 답을 쓰지 않게 비운다
    return {**fields, 'facts': {}, 'plan': {}, 'task': {}, 'question_type': '', 'counters': {'hops': 0, 'searches': 0}, 'searches': [],
            'refusal_reason': '', 'docs': [], 'passed': [], 'judgement': {}, 'price_parts': [],
            'answer': '', 'check': {}, 'refusal': {}, 'path': ['입력 읽기']}


def finish_node(state: dict) -> dict:
    """끝내기: 일상 대화는 Supervisor의 reply가 답이다. 에이전트를 거친 답은 이미 answer에 있다."""
    plan = state.get('plan') or {}
    return {'answer': plan.get('reply', ''), 'path': ['끝내기']} if plan.get('next') == 'finish' else {'path': ['끝내기']}


def refuse_node(state: dict) -> dict:
    """거절: 이유 코드는 `refusal`에 남기고(Langfuse로), 사용자에게는 일상어 문구를 답으로 준다."""
    reason = Reason(state.get('refusal_reason') or Reason.LIMIT_REACHED.value)
    message = refusal_for(reason, state.get('facts') or {})
    return {'answer': message, 'check': {}, 'refusal': {'code': reason.value, 'message': message}, 'path': ['거절']}


def rag_subgraph(*, chat, retriever, find):
    """RAG 에이전트: 검색 → 근거 채점·답 쓰기 → (근거 없음이면) 검색으로 되돌아감. 고리 상한은 갈림길 `docs.after_answer`가 본다."""
    g = StateGraph(RagState, input_schema=RagIn, output_schema=RagOut)  # [왜] 바깥 메모장에는 답 · 근거 · 검색 기록 · 지나간 노드만 돌려준다
    g.add_node('검색', partial(docs.search_step, retriever=retriever, find=find))  # find: 품번 없이 정격만 준 질문의 품번 찾기
    g.add_node('근거 채점·답 쓰기', partial(docs.answer_step, chat=chat))
    g.add_edge(START, '검색')
    g.add_edge('검색', '근거 채점·답 쓰기')
    g.add_conditional_edges('근거 채점·답 쓰기', docs.after_answer, {'검색': '검색', END: END})  # 다른 검색어로 다시 찾는 고리, 아니면 나감
    return g.compile()


def judge_subgraph(*, chat, specs, find, retriever):
    """대체 부품 에이전트: 회로 역할 읽기(LLM 1번) → 대체 부품 판정(코드 관문 · 인터럽트 · 사양 표 · 비교 · 답 틀)."""
    from backend.multi_agent.agents.judge import judge_read_agent, judge_task_node
    g = StateGraph(JudgeState, input_schema=JudgeIn, output_schema=JudgeOut)  # [왜] 바깥에는 답 · 판정 결과 · 지나간 노드만 돌려준다
    g.add_node('회로 역할 읽기', partial(judge_read_agent, chat=chat))
    g.add_node('대체 부품 판정', partial(judge_task_node, specs=specs, find=find, retriever=retriever))
    g.add_edge(START, '회로 역할 읽기')
    g.add_edge('회로 역할 읽기', '대체 부품 판정')
    g.add_edge('대체 부품 판정', END)
    return g.compile()


def build_graph(*, chat, retriever, parse=None, lookup=None, web_enabled: bool = False, judge_enabled: bool = False,
                specs=None, find=None, checkpointer=None):
    """멀티 에이전트 그래프를 만들어 compile한다. chat은 `(node, system, user, schema)` 모양의 LLM 호출이다.

    대체 부품 에이전트를 켜려면 specs(`get_part_specs`) · find(`find_parts_by_specs`) 도구와 checkpointer가 필요하다(인터럽트 재개).
    """
    if web_enabled:
        raise ValueError('웹 조회 에이전트는 아직 없어 켤 수 없습니다')  # [왜] 켜진 척 조용히 무시하면 측정이 거짓이 된다
    if judge_enabled and (specs is None or find is None or checkpointer is None):
        raise ValueError('판정 에이전트는 사양 표 도구(specs · find)와 체크포인터가 있어야 켭니다')
    from backend.graph import nodes  # [왜] 여기서 불러와야 가짜 함수를 넣는 시험이 키 없이 돈다
    g = StateGraph(MultiState)
    g.add_node('입력 읽기', partial(parse_node, parse=parse or nodes.read_input))
    g.add_node('품번·판 확인', partial(facts_mod.facts_node, lookup=lookup))
    g.add_node('Supervisor', partial(sup.plan_node, chat=chat, judge_enabled=judge_enabled))
    g.add_node('RAG 에이전트', rag_subgraph(chat=chat, retriever=retriever, find=find))
    g.add_node('답 검사', sup.check_node)
    g.add_node('끝내기', finish_node)
    g.add_node('거절', refuse_node)
    # [왜] 가격 안내는 단일 그래프 노드를 그대로 쓴다. Mouser는 그래프 밖 /api/prices만 부른다(ADR 0009)
    g.add_node('가격 안내', nodes.price_answer)
    g.add_edge(START, '입력 읽기')
    g.add_edge('입력 읽기', '품번·판 확인')
    g.add_edge('품번·판 확인', 'Supervisor')
    # [왜] Supervisor가 고를 수 있는 노드(에이전트는 하나만, 강의 15강). 대체 부품이 꺼지면 plan_node가 RAG로 돌려 그 이름이 나오지 않는다
    targets = ['RAG 에이전트', '가격 안내', '거절', '끝내기']
    if judge_enabled:
        g.add_node('대체 부품 에이전트', judge_subgraph(chat=chat, specs=specs, find=find, retriever=retriever))
        g.add_edge('대체 부품 에이전트', '답 검사')
        targets.append('대체 부품 에이전트')
    g.add_conditional_edges('Supervisor', sup.after_plan, {t: t for t in targets})
    g.add_edge('RAG 에이전트', '답 검사')
    g.add_conditional_edges('답 검사', sup.after_check, {'끝내기': '끝내기', '거절': '거절'})
    g.add_edge('끝내기', END)
    g.add_edge('거절', END)
    g.add_edge('가격 안내', END)
    return g.compile(checkpointer=checkpointer)
