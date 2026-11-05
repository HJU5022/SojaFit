"""작성 에이전트: 통과한 근거로만 답을 쓰고 보고서를 올린다.

- 역할: 단일 그래프의 생성(`generate`)을 그대로 불러 답과 인용 검사를 만들고, 거절 답("문서로 확인 안 됨")이면 실패로 보고한다.
  판정 결과가 있으면 LLM 없이 코드 틀(`messages.render_judgement`)로 답한다.
- 하지 않는 일: 검색, 인용 검증(검증 에이전트가 따로 한다), 판정(숫자 비교는 `backend/judge/`), LLM 직접 호출(`generate`를 받아 쓴다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`generate`)
"""
from backend.graph.nodes import NOT_FOUND
from backend.multi_agent.contracts import AgentReport, Reason


def writer_agent(state: dict, *, generate) -> dict:
    if state.get('judgement'):
        # [왜] 판정 답의 숫자 · 인용은 코드가 만든다. LLM이 다시 쓰면 숫자가 바뀔 수 있다(AGENTS 7번)
        from backend.multi_agent.messages import render_judgement
        answer = render_judgement(state['judgement'])
        report = AgentReport(agent='writer', status='ok', summary='judgement answer built by code from spec rows')
        return {'answer': answer, 'check': {'used': [], 'judgement': True},
                'reports': (state.get('reports') or []) + [report.model_dump(mode='json')], 'path': ['작성']}
    out = generate(dict(state))
    answer = out['answer']
    if answer == NOT_FOUND:
        report = AgentReport(agent='writer', status='fail', summary='cannot answer from the evidence ("not verified in the documents")', reason=Reason.NOT_FOUND)
    else:
        report = AgentReport(agent='writer', status='ok', summary=f'answer written ({len(answer)} chars)', evidence_ids=out.get('check', {}).get('used', []))
    return {'answer': answer, 'check': out.get('check') or {}, 'reports': (state.get('reports') or []) + [report.model_dump(mode='json')],
            'path': ['작성']}
