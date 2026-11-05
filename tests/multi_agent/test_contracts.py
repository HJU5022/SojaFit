"""멀티 에이전트 약속(backend/multi_agent/contracts.py) 시험.

- 역할: 결정서 · 보고서의 모양 검사, 이유 코드 분류, 한도 규칙(검색 2회 · 다시 쓰기 1회 · Supervisor 판단 8회)을 확인한다.
- 하지 않는 일: LLM · 검색 · DB를 부르지 않는다. 순수한 데이터 모양과 규칙만 본다.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), AGENTS.md 규칙 6(루프 상한)
"""
import pytest
from pydantic import ValidationError

from backend.multi_agent import contracts as C
from backend.multi_agent.contracts import AgentReport, Counters, Decision, Reason


def test_reason_groups_are_disjoint_and_cover_all():
    assert C.REFUSAL_REASONS == {Reason.OUT_OF_SCOPE, Reason.PART_MISSING, Reason.REVISION_MISSING, Reason.NOT_FOUND,
                                 Reason.LIMIT_REACHED, Reason.VERIFY_FAILED, Reason.SEARCH_ERROR}
    assert C.RETRY_REASONS == {Reason.NO_RESULT, Reason.ALL_REJECTED, Reason.PARTIAL}
    assert not C.REFUSAL_REASONS & C.RETRY_REASONS
    assert C.REFUSAL_REASONS | C.RETRY_REASONS == set(Reason)  # 이유는 거절 사유이거나 재시도 사유 둘 중 하나다


def test_decision_accepts_only_known_next_nodes():
    assert Decision(next='search', brief='1N5817 검색').next == 'search'
    with pytest.raises(ValidationError):
        Decision(next='mystery', brief='')  # [왜] LLM이 엉뚱한 이름을 내면 걸러낸다


def test_refuse_decision_needs_a_refusal_reason():
    assert Decision(next='refuse', reason=Reason.PART_MISSING, brief='').reason == Reason.PART_MISSING
    with pytest.raises(ValidationError):
        Decision(next='refuse', brief='')  # 이유 없는 거절
    with pytest.raises(ValidationError):
        Decision(next='refuse', reason=Reason.NO_RESULT, brief='')  # 재시도 사유는 거절 사유가 아니다


def test_retry_decision_may_carry_the_failure_reason():
    d = Decision(next='search', reason=Reason.NO_RESULT, brief='필터를 풀어서 다시')
    assert d.reason == Reason.NO_RESULT


def test_brief_allows_up_to_800_chars():
    """Sonnet Supervisor가 300자를 넘는 지시를 써서 #38에서 3문항이 형식 검사로 실패했다(11-05). 서브에이전트만 읽어 800자까지 받는다."""
    assert len(Decision(next='search', question_type='candidate_find', brief='x' * 800).brief) == 800
    with pytest.raises(ValidationError):
        Decision(next='search', question_type='candidate_find', brief='x' * 801)


def test_report_status_and_summary_limits():
    r = AgentReport(agent='search', status='partial', summary='부분: VRRM만 있음', evidence_ids=['10'], missing=['IF'])
    assert r.missing == ['IF'] and r.reason is None
    with pytest.raises(ValidationError):
        AgentReport(agent='search', status='great', summary='x')
    with pytest.raises(ValidationError):
        AgentReport(agent='search', status='ok', summary='가' * (C.MAX_SUMMARY + 1))  # [왜] Supervisor는 짧은 요약만 읽는다


def test_no_limit_hit_under_the_limits():
    assert C.check_limit(Counters(hops=3, searches=1, writes=1), 'search') is None
    assert C.check_limit(Counters(hops=3, searches=1, writes=1), 'writer') is None


def test_hop_limit_forces_refusal():
    assert C.check_limit(Counters(hops=C.MAX_HOPS), 'search') == Reason.LIMIT_REACHED


def test_search_limit_and_repeated_reason_becomes_not_found():
    two_same = Counters(searches=C.MAX_SEARCHES, recent=[Reason.NO_RESULT, Reason.NO_RESULT])
    assert C.check_limit(two_same, 'search') == Reason.NOT_FOUND  # 같은 사유로 두 번 실패하면 못 찾음(추정)
    mixed = Counters(searches=C.MAX_SEARCHES, recent=[Reason.NO_RESULT, Reason.ALL_REJECTED])
    assert C.check_limit(mixed, 'search') == Reason.LIMIT_REACHED
    assert C.check_limit(Counters(searches=C.MAX_SEARCHES), 'writer') is None  # 검색 한도는 작성에 영향 없음


def test_write_limit_means_verification_failed():
    assert C.check_limit(Counters(writes=C.MAX_WRITES), 'writer') == Reason.VERIFY_FAILED


def test_limits_match_agreed_numbers():
    assert (C.MAX_SEARCHES, C.MAX_WRITES, C.MAX_HOPS) == (2, 2, 8)  # 검색 처음+재시도 1 · 작성 처음+다시 1 · 판단 8


def test_decision_may_carry_question_type_for_downstream_agents():
    d = Decision(next='search', question_type='candidate_judge', brief='')
    assert d.question_type == 'candidate_judge'
    with pytest.raises(ValidationError):
        Decision(next='search', question_type='weather', brief='')  # [왜] 판정 에이전트가 필요한지는 질문 종류로 갈린다


def test_terminal_nodes_are_never_blocked_by_limits():
    over = Counters(hops=C.MAX_HOPS, searches=C.MAX_SEARCHES, writes=C.MAX_WRITES)
    assert C.check_limit(over, 'finish') is None and C.check_limit(over, 'refuse') is None  # 끝내는 길은 막지 않는다


def test_chat_and_other_part_are_question_types():
    import typing
    assert {'chat', 'other_part'} <= set(typing.get_args(C.QuestionType))


def test_chat_finish_needs_a_reply_and_reply_is_short():
    with pytest.raises(ValueError):
        C.Decision(next='finish', question_type='chat')  # 일상 대화로 끝내는데 답이 없다
    ok = C.Decision(next='finish', question_type='chat', reply='안녕하세요! 회로 속 다이오드를 도와 드려요.')
    assert ok.reply.startswith('안녕')
    with pytest.raises(ValueError):
        C.Decision(next='finish', question_type='chat', reply='가' * 301)
