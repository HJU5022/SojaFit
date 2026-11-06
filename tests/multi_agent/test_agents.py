"""서브에이전트(검색 · 작성 · 검증)와 사실 · 거절 문구 시험.

- 역할: 검색이 실패 사유를 보고서에 담는지(결과 없음 · 전부 탈락 · 검색 장애), 재시도 때 필터를 푸는지, 작성이 거절 답을 실패로
  보고하는지, 검증이 작성의 자체 검사를 믿지 않고 다시 계산하는지, 사실 확인과 거절 문구를 확인한다. 가짜 LLM · 검색기를 쓴다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/agents/, facts.py, messages.py
"""
from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.nodes import NOT_FOUND
from backend.multi_agent import facts as F
from backend.multi_agent import messages as M
from backend.multi_agent.agents import search as SA
from backend.multi_agent.agents import verifier as VA
from backend.multi_agent.agents import writer as WA
from backend.multi_agent.contracts import Counters, Reason


def doc(cid, page=1, file='a.pdf'):
    return {'chunk_id': cid, 'file': file, 'page': page, 'content': 'x', 'table': None, 'doc_parts': []}


def base_state(**kw):
    s = {'question': 'D1을 1N5817로 바꿔도 돼?', 'target': 'D1', 'target_part': {}, 'counters': Counters().model_dump(), 'reports': [],
         'decision': {'next': 'search', 'brief': ''}}
    s.update(kw)
    return s


def run_search(state, docs, passed, error=None, seen=None):
    def retriever(query, parts=None):
        if seen is not None:
            seen.append((query, parts))
        if error:
            raise RetrievalUnavailableError(error)
        return docs
    return SA.search_agent(state, retriever=retriever, rewrite=lambda s: {'query': 'search words'}, grade=lambda s: {'passed': passed})


def last_report(out):
    return out['reports'][-1]


def test_search_ok_reports_evidence_and_updates_state():
    out = run_search(base_state(), [doc(1), doc(2)], [1])
    r = last_report(out)
    assert r['agent'] == 'search' and r['status'] == 'ok' and r['evidence_ids'] == ['1'] and r['reason'] is None
    assert out['passed'] == [1] and out['query'] == 'search words' and len(out['docs']) == 2


def test_search_no_result_and_all_rejected_and_error_have_distinct_reasons():
    assert last_report(run_search(base_state(), [], []))['reason'] == Reason.NO_RESULT.value
    assert last_report(run_search(base_state(), [doc(1)], []))['reason'] == Reason.ALL_REJECTED.value
    err = last_report(run_search(base_state(), [], [], error='timeout'))
    assert err['reason'] == Reason.SEARCH_ERROR.value and err['status'] == 'fail'


def test_search_failure_reason_is_stacked_for_the_limit_rule():
    out = run_search(base_state(), [], [])
    assert out['counters']['recent'] == [Reason.NO_RESULT.value]
    ok = run_search(base_state(), [doc(1)], [1])
    assert ok['counters']['recent'] == []


def test_retry_after_no_result_relaxes_the_part_filter():
    part = {'ref': 'D1', 'value': '1N4148', 'nets': []}  # 대상 부품의 회로 기호 D1은 품번으로 뽑히지 않는다
    seen = []
    state = base_state(target_part=part, decision={'next': 'search', 'reason': Reason.NO_RESULT.value, 'brief': '필터를 풀어서 다시'})
    run_search(state, [], [], seen=seen)
    assert seen[0][1] is None  # [왜] 필터가 원인일 수 있으니 두 번째 시도는 다르게 한다(결정 11-05)
    seen2 = []
    run_search(base_state(target_part=part), [], [], seen=seen2)
    assert seen2[0][1] == ['1N5817']  # 처음 시도는 질문의 품번으로 거른다


def test_writer_reports_ok_and_marks_refusal_answer_as_fail():
    ok = WA.writer_agent(base_state(), generate=lambda s: {'answer': '정격은 20 V이다 [1].', 'check': {'fake_citations': []}})
    assert last_report(ok)['status'] == 'ok' and ok['answer'].startswith('정격')
    no = WA.writer_agent(base_state(), generate=lambda s: {'answer': NOT_FOUND, 'check': {}})
    r = last_report(no)
    assert r['status'] == 'fail' and r['reason'] == Reason.NOT_FOUND.value


def verify(answer, passed=(), part=None, enforce=True):
    state = base_state(answer=answer, passed=list(passed), docs=[doc(i) for i in passed], target_part=part or {})
    return last_report(VA.verifier_agent(state, enforce=enforce))


def test_verifier_passes_valid_citations_and_recomputes_instead_of_trusting_writer():
    assert verify('정격은 20 V이다 [1].', passed=[1])['status'] == 'ok'
    bad = verify('정격은 20 V이다 [99].', passed=[1])  # 넘긴 적 없는 번호
    assert bad['status'] == 'fail' and bad['reason'] == Reason.VERIFY_FAILED.value
    assert verify('근거 없는 문장이다. 이것도 그렇다.', passed=[1])['status'] == 'fail'  # 인용 없는 문장


def test_verifier_accepts_netlist_citation_only_when_netlist_was_given():
    part = {'ref': 'D1', 'nets': []}
    assert verify('D1은 보호 다이오드이다 [넷리스트].', part=part)['status'] == 'ok'
    assert verify('D1은 보호 다이오드이다 [넷리스트].')['status'] == 'fail'


def test_verifier_skips_refusal_answer_and_can_run_record_only():
    assert verify(NOT_FOUND)['status'] == 'ok'  # 거절 답은 검증할 인용이 없다
    soft = verify('근거 없는 문장이다.', enforce=False)
    assert soft['status'] == 'ok' and 'record-only' in soft['summary']  # [왜] 기준선과 같은 조건으로 재볼 때는 막지 않고 기록만 한다


def test_make_facts_checks_parts_and_revisions_against_lists():
    f = F.make_facts('SS34 Q2611판 말고 1N4001은 어때?', set(), {'ss34'}, {'Q2412'})
    assert f.parts == {'SS34': True, '1N4001': False} and f.revisions == {'Q2611': False}


def test_refusal_messages_are_plain_korean_and_cover_every_refusal_reason():
    from backend.multi_agent.contracts import REFUSAL_REASONS
    for reason in REFUSAL_REASONS:
        text = M.refusal_message(reason, ['1N4001'], ['Q2611'])
        assert text and '코퍼스' not in text and reason.value not in text  # 우리끼리 쓰는 말과 내부 코드는 보이지 않는다
    assert '1N4001' in M.refusal_message(Reason.PART_MISSING, ['1N4001'])
    assert 'Q2611' in M.refusal_message(Reason.REVISION_MISSING, [], ['Q2611'])
