"""작성 에이전트: 통과한 근거로만 답을 쓰고 보고서를 올린다.

- 역할: 단일 그래프의 생성(`generate`)을 그대로 불러 답과 인용 검사를 만들고, 거절 답("문서로 확인 안 됨")이면 실패로 보고한다.
- 하지 않는 일: 검색, 인용 검증(검증 에이전트가 따로 한다), 판정(숫자 비교는 `backend/judge/`), LLM 직접 호출(`generate`를 받아 쓴다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`generate`)
"""
from backend.graph.nodes import NOT_FOUND
from backend.multi_agent.contracts import AgentReport, Reason


def writer_agent(state: dict, *, generate) -> dict:
    out = generate(dict(state))
    answer = out['answer']
    if answer == NOT_FOUND:
        report = AgentReport(agent='writer', status='fail', summary='근거로 답할 수 없어 "문서로 확인 안 됨"', reason=Reason.NOT_FOUND)
    else:
        report = AgentReport(agent='writer', status='ok', summary=f'답 {len(answer)}자 작성', evidence_ids=out.get('check', {}).get('used', []))
    return {'answer': answer, 'check': out.get('check') or {}, 'reports': (state.get('reports') or []) + [report.model_dump(mode='json')],
            'path': ['작성']}
