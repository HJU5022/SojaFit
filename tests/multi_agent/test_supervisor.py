"""Supervisor(backend/multi_agent/supervisor.py) 시험.

- 역할: LLM에 주는 글(질문 · 사실 · 보고 · 한도 현황 · 고를 수 있는 노드)이 맞게 만들어지는지, LLM 결정을 받되 한도를 넘거나
  꺼진 웹으로 가려 하면 거절로 바뀌는지, 판단 횟수 세기가 맞는지 확인한다. 가짜 LLM을 쓰므로 API를 부르지 않는다.
- 하지 않는 일: LLM이 실제로 좋은 결정을 내리는지는 보지 않는다(그건 실제 질문으로 따로 잰다).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/prompts/supervisor.md
"""
import typing
from pathlib import Path

from backend.multi_agent import contracts as C
from backend.multi_agent import supervisor as S
from backend.multi_agent.contracts import AgentReport, Counters, Decision, Reason

ROOT = Path(__file__).resolve().parents[2]


def inp(**kw):
    base = dict(question='D1을 1N5817로 바꿔도 돼?', target='D1', conditions='입력 최대 20V', target_value='1N4148',
                facts=S.Facts(parts={'1N5817': True}, revisions={}), reports=[], counters=Counters())
    return S.SupervisorInput(**{**base, **kw})


def fake_chat(decision, calls=None):
    def chat(node, system, user, schema):
        if calls is not None:
            calls.append((node, system, user, schema))
        return decision
    return chat


def test_render_contains_question_facts_reports_status_and_options():
    rep = AgentReport(agent='search', status='partial', summary='역전압만 찾음', evidence_ids=['10'], missing=['IF'], reason=Reason.PARTIAL)
    text = S.render(inp(facts=S.Facts(parts={'1N4001': False}, revisions={'Q2611': False}), reports=[rep],
                        counters=Counters(hops=2, searches=1, writes=0)))
    assert '1N5817' in text and '입력 최대 20V' in text
    assert 'part 1N4001: NOT in corpus' in text and 'revision Q2611: NOT in corpus' in text
    assert '역전압만 찾음' in text and 'IF' in text and 'partial' in text
    assert 'hops 2/8' in text and 'searches 1/2' in text and 'writes 0/2' in text
    assert 'web' not in text.split('Next nodes you may choose')[1]  # 웹이 꺼져 있으면 선택지에 없다


def test_render_shows_question_type_once_decided():
    assert 'Question type: not decided yet' in S.render(inp())
    assert 'Question type: candidate_judge' in S.render(inp(question_type='candidate_judge'))


def test_render_lists_web_and_judge_only_when_enabled():
    opts = S.render(inp()).split('Next nodes you may choose')[1]
    assert 'judge' not in opts and 'web' not in opts
    assert 'web' in S.render(inp(web_enabled=True)).split('Next nodes you may choose')[1]
    assert 'judge' in S.render(inp(judge_enabled=True)).split('Next nodes you may choose')[1]


def test_decide_passes_decision_schema_and_returns_llm_choice():
    calls = []
    d = S.decide(inp(), fake_chat(Decision(next='search', question_type='candidate_judge', brief='1N5817 찾기'), calls))
    assert d.next == 'search' and d.question_type == 'candidate_judge'
    node, system, user, schema = calls[0]
    assert node == 'supervisor' and schema is Decision and '1N5817' in user and 'Supervisor' in system


def test_decide_forces_refusal_at_hop_limit():
    d = S.decide(inp(counters=Counters(hops=C.MAX_HOPS)), fake_chat(Decision(next='search', brief='')))
    assert d.next == 'refuse' and d.reason == Reason.LIMIT_REACHED


def test_decide_reports_not_found_when_same_reason_failed_twice():
    c = Counters(hops=3, searches=C.MAX_SEARCHES, recent=[Reason.NO_RESULT, Reason.NO_RESULT])
    d = S.decide(inp(counters=c), fake_chat(Decision(next='search', brief='')))
    assert d.next == 'refuse' and d.reason == Reason.NOT_FOUND


def test_decide_keeps_finish_even_at_limits():
    c = Counters(hops=C.MAX_HOPS, searches=C.MAX_SEARCHES, writes=C.MAX_WRITES)
    assert S.decide(inp(counters=c), fake_chat(Decision(next='finish'))).next == 'finish'


def test_decide_turns_disabled_web_into_refusal_with_matching_reason():
    missing = inp(facts=S.Facts(parts={'1N4001': False}, revisions={}))
    d = S.decide(missing, fake_chat(Decision(next='web', brief='')))
    assert d.next == 'refuse' and d.reason == Reason.PART_MISSING  # 품번이 목록에 없었으니 확정 사유
    d2 = S.decide(inp(), fake_chat(Decision(next='web', brief='')))
    assert d2.reason == Reason.NOT_FOUND
    assert S.decide(inp(web_enabled=True), fake_chat(Decision(next='web', brief=''))).next == 'web'


def test_decide_sends_disabled_judge_to_writer():
    d = S.decide(inp(), fake_chat(Decision(next='judge', brief='')))
    assert d.next == 'writer'  # 판정 에이전트가 아직 없으니 근거로 쓰는 길로
    assert S.decide(inp(judge_enabled=True), fake_chat(Decision(next='judge', brief=''))).next == 'judge'


def test_count_decision_and_report():
    c = S.count_decision(Counters(), Decision(next='search', brief=''))
    assert (c.hops, c.searches, c.writes) == (1, 1, 0)
    c = S.count_decision(c, Decision(next='writer', brief=''))
    assert (c.hops, c.searches, c.writes) == (2, 1, 1)
    fail = AgentReport(agent='search', status='fail', summary='없음', reason=Reason.NO_RESULT)
    assert S.count_report(c, fail).recent == [Reason.NO_RESULT]
    ok = AgentReport(agent='search', status='ok', summary='충분')
    assert S.count_report(c, ok).recent == []  # 성공 보고는 실패 사유를 쌓지 않는다
    assert c.recent == []  # 원본은 바꾸지 않는다


def test_prompt_mentions_every_next_node_and_refusal_reason():
    text = (ROOT / 'backend/prompts/supervisor.md').read_text(encoding='utf-8')
    for node in typing.get_args(C.NextNode):
        assert f'`{node}`' in text, node
    for reason in C.REFUSAL_REASONS:
        assert reason.value in text, reason
