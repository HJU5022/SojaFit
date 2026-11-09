"""멀티 에이전트 약속(backend/multi_agent/contracts.py) 시험: Supervisor 지시서 형식 검사 · 상한 숫자.

- 역할: 형식이 틀린 지시서(거절 사유 없음 · 일상 대화 reply 없음 · 에이전트를 골랐는데 지시 없음 · 판정에 맞지 않는 질문 종류 ·
  검색어 없는 RAG 지시)가 ValidationError로 걸리는지(llm.chat이 다시 부르는 조건), 상한이 합의한 숫자인지 본다.
- 하지 않는 일: LLM · 그래프 실행.
- 출처: backend/multi_agent/contracts.py, 참조/아티팩트 "SojaFit 멀티 에이전트 구조", 회의록 D4-D5 B-지시서 4-4
"""
import pytest
from pydantic import ValidationError

from backend.multi_agent import contracts as C
from backend.multi_agent.contracts import Plan, Reason, Task


def task(**kw):
    return {'goal': 'VRRM of SS14', 'query': 'SS14 VRRM', **kw}


def test_reason_groups_are_disjoint_and_cover_all():
    assert not C.REFUSAL_REASONS & C.RETRY_REASONS
    assert C.REFUSAL_REASONS | C.RETRY_REASONS == set(Reason)


def test_valid_plans():
    assert Plan(question_type='rating', next='docs', task=task()).task.query == 'SS14 VRRM'
    assert Plan(question_type='chat', next='finish', reply='안녕하세요').reply
    assert Plan(question_type='out_of_scope', next='refuse', reason=Reason.OUT_OF_SCOPE).reason is Reason.OUT_OF_SCOPE
    assert Plan(question_type='price', next='price').task is None
    role = Plan(question_type='role', next='docs', task=task(query=''))  # 역할은 넷리스트로 답해 검색어가 없어도 된다
    assert role.task.query == ''
    assert Plan(question_type='candidate_find', next='judge', task={'goal': 'find'}).task.goal == 'find'


@pytest.mark.parametrize('bad', [
    {'question_type': 'out_of_scope', 'next': 'refuse'},                                     # 거절 사유 없음
    {'question_type': 'rating', 'next': 'refuse', 'reason': 'no_result'},                     # 재시도 사유는 거절 사유가 아니다
    {'question_type': 'chat', 'next': 'finish', 'reply': ' '},                                # 일상 대화인데 답이 없음
    {'question_type': 'rating', 'next': 'docs'},                                              # 에이전트를 골랐는데 지시가 없음
    {'question_type': 'rating', 'next': 'judge', 'task': task()},                            # 판정 에이전트에 정격 질문
    {'question_type': 'rating', 'next': 'docs', 'task': task(query='')},                     # 검색어 없는 RAG 지시(역할 질문이 아님)
    {'question_type': 'rating', 'next': 'docs', 'task': task(), 'declined': [{'ask': 'x', 'reason': 'no_result'}]},  # 거절한 부분에 재시도 사유
    {'question_type': 'rating', 'next': 'tasks', 'task': task()},                            # 없는 길(11-09에 할 일 목록을 뺐다)
    {'question_type': 'rating', 'next': 'web'},                                               # 없는 길
])
def test_malformed_plans_fail_validation(bad):
    with pytest.raises(ValidationError):
        Plan(**bad)


def test_limits_match_agreed_numbers():
    assert (C.MAX_SEARCHES, C.MAX_SUMMARY) == (2, 200)
    assert Task(**task()).boundary == ''
