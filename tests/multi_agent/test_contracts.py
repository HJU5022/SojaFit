"""멀티 에이전트 약속(backend/multi_agent/contracts.py) 시험: 계획서 형식 검사 · 보고서 한도 · 상한 숫자.

- 역할: 형식이 틀린 계획(거절 사유 없음 · 일상 대화 reply 없음 · 할 일 0개나 4개 · 번호 순서 · 판정에 맞지 않는 종류 · 검색어 없는 문서 할 일)이
  ValidationError로 걸리는지(llm.chat이 다시 부르는 조건), 보고 요약이 200자를 넘지 못하는지, 상한이 합의한 숫자인지 본다.
- 하지 않는 일: LLM · 그래프 실행.
- 출처: backend/multi_agent/contracts.py, 참조/아티팩트 "SojaFit 멀티 에이전트 구조", 회의록 D4-D5 B-지시서 4-4
"""
import pytest
from pydantic import ValidationError

from backend.multi_agent import contracts as C
from backend.multi_agent.contracts import Plan, Reason, Task, TaskReport


def task(i=1, **kw):
    return {'id': i, 'agent': 'docs', 'kind': 'rating', 'goal': 'VRRM of SS14', 'query': 'SS14 VRRM', **kw}


def test_reason_groups_are_disjoint_and_cover_all():
    assert not C.REFUSAL_REASONS & C.RETRY_REASONS
    assert C.REFUSAL_REASONS | C.RETRY_REASONS == set(Reason)


def test_valid_plans():
    assert Plan(question_type='rating', next='tasks', tasks=[task()]).tasks[0].agent == 'docs'
    assert Plan(question_type='chat', next='finish', reply='안녕하세요').reply
    assert Plan(question_type='out_of_scope', next='refuse', reason=Reason.OUT_OF_SCOPE).reason is Reason.OUT_OF_SCOPE
    assert Plan(question_type='price', next='price').tasks == []
    role = Plan(question_type='role', next='tasks', tasks=[task(kind='role', query='')])  # 역할은 넷리스트로 답해 검색어가 없어도 된다
    assert role.tasks[0].query == ''


@pytest.mark.parametrize('bad', [
    {'question_type': 'out_of_scope', 'next': 'refuse'},                                     # 거절 사유 없음
    {'question_type': 'rating', 'next': 'refuse', 'reason': 'no_result'},                     # 재시도 사유는 거절 사유가 아니다
    {'question_type': 'chat', 'next': 'finish', 'reply': ' '},                                # 일상 대화인데 답이 없음
    {'question_type': 'rating', 'next': 'tasks', 'tasks': []},                                # 할 일 0개
    {'question_type': 'rating', 'next': 'tasks', 'tasks': [task(i) for i in range(1, 5)]},    # 할 일 4개(상한 3)
    {'question_type': 'rating', 'next': 'tasks', 'tasks': [task(2)]},                         # 번호가 1부터가 아님
    {'question_type': 'rating', 'next': 'tasks', 'tasks': [task(agent='judge')]},            # 판정에 rating 할 일
    {'question_type': 'rating', 'next': 'tasks', 'tasks': [task(query='')]},                 # 검색어 없는 문서 할 일
    {'question_type': 'rating', 'next': 'web'},                                               # 없는 길
])
def test_malformed_plans_fail_validation(bad):
    with pytest.raises(ValidationError):
        Plan(**bad)


def test_report_summary_limit_and_agents():
    with pytest.raises(ValidationError):
        TaskReport(task=1, agent='docs', status='ok', summary='x' * 201)
    with pytest.raises(ValidationError):
        TaskReport(task=1, agent='writer', status='ok', summary='x')  # 서브에이전트는 문서 · 판정 둘뿐이다
    assert Task(**task()).boundary == ''


def test_limits_match_agreed_numbers():
    assert (C.MAX_TASKS, C.MAX_SUPERVISOR_CALLS, C.MAX_AGENT_RUNS, C.MAX_SEARCHES, C.MAX_SUMMARY) == (3, 4, 6, 2, 200)
