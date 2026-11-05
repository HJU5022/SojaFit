"""Supervisor: 서브에이전트의 보고를 읽고 다음에 누구에게 맡길지 판단한다.

- 역할: 질문 · 확인된 사실(품번 · 개정판이 코퍼스에 있나) · 지금까지의 보고 · 한도 현황 · 고를 수 있는 노드를 글로 만들어
  LLM에 주고 결정서(`Decision`)를 받는다. 한도를 넘거나 꺼져 있는 웹으로 가려 하면 거절로 바꾼다. 판단 횟수를 센다.
- 하지 않는 일: 검색 · 판정 · 작성 자체, LLM 직접 호출(`chat` 함수를 받아 쓴다. 실제 연결은 `llm.node_chat`), 사실 조회(호출하는 쪽이
  조회 결과 `Facts`를 만들어 넘긴다), 질문 문구 해석 규칙(그건 프롬프트의 몫이고 코드로 if 문을 쓰지 않는다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/prompts/supervisor.md
"""
from pathlib import Path

from pydantic import BaseModel, Field

from backend.multi_agent.contracts import (MAX_HOPS, MAX_SEARCHES, MAX_WRITES, RETRY_REASONS, AgentReport, Counters,
                                           Decision, Reason, check_limit)

PROMPT = (Path(__file__).resolve().parents[1] / 'prompts' / 'supervisor.md').read_text(encoding='utf-8')
ALWAYS = ('search', 'writer', 'verifier', 'finish', 'refuse')  # 판정 · 웹은 켜져 있을 때만 선택지에 넣는다


class Facts(BaseModel):
    """코드가 목록에서 확인한 사실. LLM이 짐작하지 않고 이 값을 믿는다."""
    parts: dict[str, bool] = Field(default_factory=dict)      # 질문에 나온 품번 → 코퍼스 목록에 있나
    revisions: dict[str, bool] = Field(default_factory=dict)  # 요청한 개정 코드 → 코퍼스에 있나


class SupervisorInput(BaseModel):
    question: str
    target: str = ''
    conditions: str = ''
    target_value: str = ''
    question_type: str = ''  # 처음 판단에서 정한 질문 종류. 이후 판단(판정이 필요한가 등)이 이걸 읽는다
    facts: Facts = Field(default_factory=Facts)
    reports: list[AgentReport] = Field(default_factory=list)
    counters: Counters = Field(default_factory=Counters)
    web_enabled: bool = False    # [왜] 평가 모드에서는 끈다(동결한 코퍼스만 쓴다)
    judge_enabled: bool = False  # [왜] 판정 에이전트가 아직 없다. 기능 스위치로 숨겨 두면 미완성이 전체 동작을 깨지 않는다


def render(i: SupervisorInput) -> str:
    """LLM에 줄 user 글. 청크 원문은 없고 요약 보고만 담는다(컨텍스트 분리)."""
    lines = [f'질문: {i.question}', f'대상: {i.target} {i.target_value}'.rstrip(), f'사용 조건: {i.conditions}',
             f'질문 종류: {i.question_type or "아직 정하지 않음"}']
    lines.append('확인된 사실:')
    for name, ok in i.facts.parts.items():
        lines.append(f'- 품번 {name}: {"코퍼스에 있음" if ok else "코퍼스에 없음"}')
    for name, ok in i.facts.revisions.items():
        lines.append(f'- 개정판 {name}: {"코퍼스에 있음" if ok else "코퍼스에 없음"}')
    if not i.facts.parts and not i.facts.revisions:
        lines.append('- (질문에서 확인할 품번 · 개정판 없음)')
    lines.append('지금까지의 보고:')
    for n, r in enumerate(i.reports, 1):
        extra = ''.join([f' · 사유 {r.reason.value}' if r.reason else '', f' · 부족한 값 {", ".join(r.missing)}' if r.missing else '',
                         f' · 근거 {len(r.evidence_ids)}개' if r.evidence_ids else ''])
        lines.append(f'{n}. {r.agent} → {r.status}: {r.summary}{extra}')
    if not i.reports:
        lines.append('(아직 없음)')
    c = i.counters
    lines.append(f'현황: 판단 {c.hops}/{MAX_HOPS} · 검색 {c.searches}/{MAX_SEARCHES} · 작성 {c.writes}/{MAX_WRITES}')
    options = ALWAYS + (('judge',) if i.judge_enabled else ()) + (('web',) if i.web_enabled else ())
    lines.append('고를 수 있는 다음 노드: ' + ', '.join(options))
    return '\n'.join(lines)


def decide(i: SupervisorInput, chat, system: str = PROMPT) -> Decision:
    """LLM에게 다음 노드를 묻고 결정서를 돌려준다. 한도를 넘거나 꺼진 웹이면 거절로 바꾼다.

    chat은 `(node, system, user, schema) -> schema 객체` 모양이다(실제로는 `llm.node_chat`).
    """
    d = chat('supervisor', system, render(i), Decision)
    forced = check_limit(i.counters, d.next)
    if forced:
        return Decision(next='refuse', reason=forced, brief='한도')
    if d.next == 'web' and not i.web_enabled:
        # [왜] 웹이 꺼져 있는데 LLM이 골랐다. 품번이 목록에 없었으면 확정 사유로, 아니면 못 찾음(추정)으로 거절한다
        reason = Reason.PART_MISSING if any(not ok for ok in i.facts.parts.values()) else Reason.NOT_FOUND
        return Decision(next='refuse', reason=reason, brief='웹 조회 꺼짐')
    if d.next == 'judge' and not i.judge_enabled:
        return d.model_copy(update={'next': 'writer', 'brief': '판정 꺼짐: 찾은 근거로 답을 쓴다'})  # 거절이 아니라 근거로 쓰는 길로 돌린다
    return d


def count_decision(c: Counters, d: Decision) -> Counters:
    """결정을 내린 뒤의 횟수. 원본은 바꾸지 않는다."""
    new = c.model_copy(deep=True)
    new.hops += 1
    new.searches += d.next == 'search'
    new.writes += d.next == 'writer'
    return new


def count_report(c: Counters, r: AgentReport) -> Counters:
    """보고를 받은 뒤의 횟수. 검색이 재시도 사유로 실패했으면 사유를 쌓는다(같은 사유 반복을 보려는 것)."""
    new = c.model_copy(deep=True)
    if r.agent == 'search' and r.reason in RETRY_REASONS:
        new.recent.append(r.reason)
    return new


def supervisor_node(state: dict, *, chat, web_enabled: bool = False, judge_enabled: bool = False) -> dict:
    """그래프 노드: 메모장에서 Supervisor 입력을 만들어 결정서를 받고 판단 횟수를 센다."""
    part = state.get('target_part') or {}
    i = SupervisorInput(question=state['question'], target=state.get('target', ''), conditions=state.get('conditions', ''),
                        target_value=part.get('value', ''), question_type=state.get('question_type', ''), facts=Facts(**(state.get('facts') or {})),
                        reports=[AgentReport(**r) for r in state.get('reports') or []], counters=Counters(**state['counters']),
                        web_enabled=web_enabled, judge_enabled=judge_enabled)
    d = decide(i, chat)
    out = {'decision': d.model_dump(mode='json'), 'counters': count_decision(i.counters, d).model_dump(mode='json'), 'path': ['판단']}
    if d.question_type:  # 처음 판단에서 정한 질문 종류를 이어 쓴다. 한도 거절처럼 없으면 그대로 둔다
        out['question_type'] = d.question_type
    return out
