"""검증 에이전트: 쓴 답의 인용을 다시 계산해 확인한다.

- 역할: 답의 문장마다 근거 번호가 있는지, 인용한 번호가 실제로 넘긴 근거(통과 청크 · 넷리스트)인지 확인하고 보고서를 올린다.
  작성의 자체 검사(`check`)를 믿지 않고 상태의 답과 근거로 다시 계산한다. 판정 답은 코드 틀과 같은지만 본다.
- 하지 않는 일: 답 고치기(다시 쓸지는 Supervisor가 정한다), 값이 맞는지 판단(의미 정확도는 보지 않는다), 검색.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`citations` 재사용)
"""
import re

from backend.graph.nodes import NOT_FOUND, citations
from backend.multi_agent.contracts import AgentReport, Reason


def verifier_agent(state: dict, *, enforce: bool = True) -> dict:
    """enforce가 False면 걸려도 막지 않고 기록만 한다(기준선과 같은 조건으로 재볼 때)."""
    answer = state.get('answer') or ''
    passed = {str(i) for i in state.get('passed') or []}
    valid = {str(d['chunk_id']) for d in state.get('docs') or [] if str(d['chunk_id']) in passed} | ({'넷리스트'} if state.get('target_part') else set())
    if state.get('judgement'):
        from backend.multi_agent.messages import render_judgement
        same = answer == render_judgement(state['judgement'])  # [왜] 판정 답은 코드 틀이다. 틀과 같으면 인용은 사양 표 행 그대로다
        report = (AgentReport(agent='verifier', status='ok', summary='judgement answer matches the code template')
                  if same or not enforce else AgentReport(agent='verifier', status='fail', summary='judgement answer was edited', reason=Reason.VERIFY_FAILED))
        return {'reports': (state.get('reports') or []) + [report.model_dump(mode='json')], 'path': ['검증']}
    if answer == NOT_FOUND or not answer:
        report = AgentReport(agent='verifier', status='ok', summary='refusal answer, no citations to verify')
    else:
        fake = sorted(citations(answer) - valid)
        uncited = sum(1 for s in re.split(r'(?<=[.。])\s+', answer) if s.strip() and not citations(s))
        problem = f'citations of evidence not provided {fake}, sentences without a citation {uncited}' if fake or uncited else ''
        if not problem:
            report = AgentReport(agent='verifier', status='ok', summary='every sentence cites provided evidence only')
        elif enforce:
            report = AgentReport(agent='verifier', status='fail', summary=problem, reason=Reason.VERIFY_FAILED)
        else:
            report = AgentReport(agent='verifier', status='ok', summary=f'record-only (not blocking): {problem}')
    return {'reports': (state.get('reports') or []) + [report.model_dump(mode='json')], 'path': ['검증']}
