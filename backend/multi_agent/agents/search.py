"""검색 에이전트: 한 번 찾고 채점한 결과를 보고서로 올린다.

- 역할: 재작성(검색어) → 검색(품번 필터) → 채점을 한 번 돌리고, 결과를 보고서(통과 청크 번호, 실패면 사유)로 만든다.
  이전 시도가 "결과 없음"으로 실패했으면 이번에는 품번 필터를 풀어 다르게 시도한다.
- 하지 않는 일: 재시도 판단(다시 할지는 Supervisor가 정한다), 답 작성, LLM 직접 호출(`rewrite` · `grade`를 받아 쓴다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`search`는 그대로 쓴다)
"""
from backend.graph.nodes import search
from backend.multi_agent import supervisor as sup
from backend.multi_agent.contracts import AgentReport, Counters, Reason


def search_report(ws: dict) -> AgentReport:
    docs, passed = ws.get('docs') or [], ws.get('passed') or []
    if ws.get('retrieval_error'):
        return AgentReport(agent='search', status='fail', summary='검색 도구 장애', reason=Reason.SEARCH_ERROR)
    if not docs:
        return AgentReport(agent='search', status='fail', summary='검색 결과가 없음', reason=Reason.NO_RESULT)
    if not passed:
        return AgentReport(agent='search', status='fail', summary=f'청크 {len(docs)}장을 찾았지만 채점에서 모두 탈락', reason=Reason.ALL_REJECTED)
    # shortcut: 지금 채점은 통과 있음/없음 두 갈래라 ok와 fail뿐이다. 충분 · 부분 · 부족 3갈래는 채점기를 바꿀 때(partial) 넣는다
    return AgentReport(agent='search', status='ok', summary=f'청크 {len(docs)}장 중 {len(passed)}장 통과',
                       evidence_ids=[str(i) for i in passed])


def search_agent(state: dict, *, retriever, rewrite, grade) -> dict:
    """검색 에이전트 한 번 실행. 돌려주는 dict가 메모장에 합쳐진다."""
    ws = dict(state)
    relax = (state.get('decision') or {}).get('reason') == Reason.NO_RESULT.value  # 이전 시도가 결과 없음이면 필터를 푼다
    find = (lambda query, parts=None: retriever(query, parts=None)) if relax else retriever
    ws.update(rewrite(ws))                  # query
    ws.update(search(ws, find))             # query · parts · docs · retrieval_error (tries는 쓰지 않는다)
    ws.update(grade(ws))                    # passed
    report = search_report(ws)
    counters = sup.count_report(Counters.model_validate(state['counters']), report)
    return {'query': ws['query'], 'parts': ws['parts'], 'docs': ws['docs'], 'passed': ws['passed'],
            'retrieval_error': ws['retrieval_error'], 'reports': (state.get('reports') or []) + [report.model_dump(mode='json')],
            'counters': counters.model_dump(mode='json'), 'path': ['검색']}
