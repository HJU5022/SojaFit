"""Supervisor(LLM 1번)가 다음 길 하나를 고르고, 에이전트가 낸 답을 코드로 검사한다(답 검사).

- 역할:
  - `plan_node`: 질문 · 대상 회로 · 확인된 사실을 글로 만들어 LLM에 주고 지시서(`Plan`: 범위 판정 · 질문 종류 · 다음 길 하나와
    그 에이전트의 지시)를 받는다. 형식이 틀리면 `llm.chat`이 다시 부르고, 끝내 틀리면 거절한다.
    `after_plan`은 지시서의 `next`를 갈 노드 이름(`ROUTES`)으로 바꿔 돌려준다. 그래프 그림의 간선에 영어 라벨이 붙지 않게 노드 이름 그대로다.
  - `check_node`(답 검사, 코드): 인용 번호가 에이전트가 받은 근거 안인지, 근거 인용이 하나라도 있는지 본다.
- 하지 않는 일: 검색 · 판정 자체(에이전트), 숫자 비교(`backend/judge/`), LLM 직접 호출(`chat` 함수를 받아 쓴다. 실제 연결은 `llm.node_chat`),
  여러 에이전트의 답 합치기(11-09부터 에이전트 하나가 질문 전체를 답한다).
- 출처: 강의 IV-3 15강 cell 14(Supervisor가 하나를 고르고 끝), 강의 IV-2 03강(갈림길은 간선 표로), backend/prompts/supervisor.md
"""
import re
from pathlib import Path

from pydantic import BaseModel, Field

from backend.multi_agent.contracts import Plan, Reason

PROMPTS = Path(__file__).resolve().parents[1] / 'prompts'
PROMPT = (PROMPTS / 'supervisor.md').read_text(encoding='utf-8')
# [왜] 지시서의 다음 길(LLM이 쓰는 영어 이름) → 갈 노드 이름. 갈림 함수가 노드 이름을 돌려줘야 간선 표가 {'거절': '거절'}처럼 되고 그림에 라벨이 없다(강의 20강)
ROUTES = {'docs': 'RAG 에이전트', 'judge': '대체 부품 에이전트', 'price': '가격 안내', 'refuse': '거절', 'finish': '끝내기'}


class Facts(BaseModel):
    """코드가 목록에서 확인한 사실. LLM이 짐작하지 않고 이 값을 믿는다."""
    parts: dict[str, bool] = Field(default_factory=dict)      # 질문에 나온 품번 → 코퍼스 목록에 있나
    revisions: dict[str, bool] = Field(default_factory=dict)  # 요청한 개정 코드 → 코퍼스에 있나


def render_facts(facts: Facts) -> list[str]:
    """확인된 사실을 LLM 입력 줄로 쓴다. [왜] D4 v2 단일 그래프의 라우팅도 이 글을 받아, 같은 사실로 거절을 정하게 한다(D4 · D5 공정 비교)."""
    lines = ['Verified facts:']
    for name, ok in facts.parts.items():
        lines.append(f'- part {name}: {"in corpus" if ok else "NOT in corpus"}')
    for name, ok in facts.revisions.items():
        lines.append(f'- revision {name}: {"in corpus" if ok else "NOT in corpus"}')
    if not facts.parts and not facts.revisions:
        lines.append('- (no part number or revision to verify in the question)')
    return lines


def render_plan(state: dict, judge_enabled: bool) -> str:
    """Supervisor LLM에 줄 user 글(영어 라벨). 청크 원문은 없다: 질문 · 대상 · 사용 조건 · 확인된 사실 · 고를 수 있는 에이전트."""
    part = state.get('target_part') or {}
    target = f"{part.get('ref', state.get('target', ''))} {part.get('value', '')} {part.get('footprint', '')}".strip() or state.get('target', '')
    agents = ['docs'] + (['judge'] if judge_enabled else [])
    return '\n'.join([f"Question: {state['question']}", f'Target part: {target or "(none)"}', f"Conditions: {state.get('conditions', '')}",
                      *render_facts(Facts(**(state.get('facts') or {}))), 'Agents you may use: ' + ', '.join(agents)])


def plan_node(state: dict, *, chat, judge_enabled: bool = False) -> dict:
    """그래프 노드 Supervisor: 지시서를 받는다. 형식이 끝내 틀리면 거절로 끝낸다."""
    counters = {'hops': 1, 'searches': 0}
    try:
        plan = chat('supervisor', PROMPT, render_plan(state, judge_enabled), Plan)
    except ValueError:
        # [왜] llm.chat이 형식을 다시 맞춰 보고도(MAX_FORMAT_RETRIES) 틀리면 ValueError를 낸다. 틀린 지시서로 에이전트를 부르지 않는다(B-지시서 4-4)
        return {'plan': {}, 'task': {}, 'question_type': '', 'refusal_reason': Reason.LIMIT_REACHED.value, 'counters': counters, 'path': ['Supervisor']}
    if plan.next == 'judge' and not judge_enabled:
        # [왜] 대체 부품 에이전트가 없으면 RAG 에이전트로 돌린다(거절이 아니라 근거로 답하는 길, 예전 Supervisor와 같음)
        plan = plan.model_copy(update={'next': 'docs', 'task': plan.task.model_copy(update={'query': plan.task.query or plan.task.goal})})
    out = {'plan': plan.model_dump(mode='json'), 'task': plan.task.model_dump(mode='json') if plan.task else {},
           'question_type': plan.question_type, 'counters': counters, 'path': ['Supervisor']}
    if plan.next == 'refuse':
        out['refusal_reason'] = plan.reason.value
    return out


def after_plan(state: dict) -> str:
    """Supervisor 뒤 갈림길: 갈 노드 이름(RAG 에이전트 · 대체 부품 에이전트 · 가격 안내 · 거절 · 끝내기). 형식 실패 · 거절 사유가 있으면 거절."""
    plan = state.get('plan') or {}
    return '거절' if state.get('refusal_reason') or not plan else ROUTES[plan['next']]


def check_node(state: dict) -> dict:
    """그래프 노드 답 검사(코드): 인용 번호가 받은 근거 안인지, 근거 인용이 하나라도 있는지 본다(판정 답 틀은 표의 인용이라 번호가 없어도 된다)."""
    from backend.graph.nodes import citations  # [왜] 여기서 불러온다. graph.nodes가 이 모듈의 Facts를 불러 맨 위에서 부르면 순환 import다
    if state.get('refusal_reason'):
        return {'path': ['답 검사']}  # 에이전트가 이미 거절 사유를 냈다(근거 없음 · 코퍼스 밖 요구 · 도구 장애)
    answer = state.get('answer') or ''
    valid = {str(i) for i in state.get('passed') or []} | ({'넷리스트'} if state.get('target_part') else set())
    cited = citations(answer)
    sentences = [s for s in re.split(r'(?<=[.。])\s+', answer) if s.strip()]
    check = {'used': sorted(cited & valid), 'fake_citations': sorted(cited - valid),
             'uncited_sentences': sum(1 for s in sentences if not citations(s)), 'judgement': bool(state.get('judgement'))}
    problem = bool(check['fake_citations']) or (not check['judgement'] and not check['used'])
    out = {'check': check, 'path': ['답 검사']}
    return {**out, 'refusal_reason': Reason.VERIFY_FAILED.value} if problem else out


def after_check(state: dict) -> str:
    """답 검사 뒤 갈림길: 거절 사유가 있으면 '거절', 없으면 '끝내기'(노드 이름)."""
    return '거절' if state.get('refusal_reason') else '끝내기'
