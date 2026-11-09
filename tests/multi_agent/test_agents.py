"""RAG 에이전트(하위 그래프)와 사실 · 거절 문구 · 판정 답 틀 시험.

- 역할: RAG 에이전트가 지시서의 검색어로 찾고(역할 질문은 검색 없이 넷리스트로), 근거 채점 + 답 쓰기를 LLM 한 번으로 하고,
  근거가 없으면 LLM이 준 다른 검색어로 고리를 한 번만 더 돌고(상한 MAX_SEARCHES), 보여 준 적 없는 근거 인용을 코드로 막는지,
  다른 품번 줄을 LLM에 보이기 전에 거르는지, 검색 장애 · 0건이면 거절 사유를 내는지 본다. 사실 확인과 거절 문구 · 판정 답 틀도 확인한다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/agents/docs.py · build.py(rag_subgraph), facts.py, messages.py
"""
import pytest

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.multi_agent import build as B
from backend.multi_agent import facts as F
from backend.multi_agent import messages as M
from backend.multi_agent import messages as Msg
from backend.multi_agent.agents import docs as D
from backend.multi_agent.contracts import Reason

PART = {'ref': 'D1', 'value': 'SS14', 'footprint': 'SMA', 'nets': [{'name': '+5V', 'nodes': ['D1.1', 'U1.3'], 'more': 0}]}


def doc(cid, content='VRRM 40 V', table=None, parts=()):
    return {'chunk_id': cid, 'file': 'SS12 SERIES_K2301.pdf', 'page': 2, 'content': content, 'table': table, 'doc_parts': list(parts)}


def llm(*answers):
    queue, seen = list(answers), []

    def chat(node, system, user, schema):
        seen.append((node, user))
        return queue.pop(0)
    chat.seen = seen
    return chat


def run(task, chat, docs=(), seen=None, error=None, question='SS14의 VRRM은?', part=PART, find=None):
    """RAG 에이전트 하위 그래프를 혼자 돌려 바깥에 돌려주는 칸(답 · 거절 사유 · 근거 · 검색 기록 · 경로)을 받는다."""
    def retriever(query, parts=None):
        if seen is not None:
            seen.append((query, parts))
        if error:
            raise RetrievalUnavailableError(error)
        return list(docs(query, parts) if callable(docs) else docs)
    return B.rag_subgraph(chat=chat, retriever=retriever, find=find).invoke(
        {'task': task, 'question': question, 'target_part': part, 'counters': {'hops': 1, 'searches': 0}})


def task(**kw):
    return {'goal': 'VRRM of SS14', 'query': 'SS14 Repetitive peak reverse voltage VRRM', **kw}


def test_rating_task_searches_with_the_brief_query_and_answers_in_one_llm_call():
    seen = []
    chat = llm(D.DocsAnswer(grade='enough', answer='SS14의 VRRM은 40 V이다 [3].'))
    r = run(task(), chat, docs=[doc(3)], seen=seen)
    assert seen == [('SS14 Repetitive peak reverse voltage VRRM', ['SS14'])]  # 지시서 검색어 + 질문의 품번 필터
    assert r['path'] == ['검색', '근거 채점·답 쓰기'] and r['refusal_reason'] == '' and r['passed'] == [3] and len(chat.seen) == 1
    assert r['searches'][0]['top'] == [['SS12 SERIES_K2301.pdf', 2]] and r['counters'] == {'hops': 1, 'searches': 1}
    node, user = chat.seen[0]
    assert node == 'docs_answer' and 'goal: VRRM of SS14' in user and '[3] SS12 SERIES_K2301.pdf' in user and '[넷리스트] D1 SS14' in user


def test_role_task_uses_only_the_netlist_without_searching():
    seen = []
    r = run(task(query=''), llm(D.DocsAnswer(grade='enough', answer='D1은 +5V에 연결된다 [넷리스트].')), seen=seen)
    assert seen == [] and r['answer'].endswith('[넷리스트].') and r['passed'] == [] and 'searches' not in r


def test_no_evidence_loops_once_with_the_llm_query_then_refuses_as_not_found():
    seen = []
    chat = llm(D.DocsAnswer(grade='none', next_query='SS14 Peak reverse voltage'), D.DocsAnswer(grade='none', next_query='again'))
    r = run(task(), chat, docs=[doc(3)], seen=seen)
    # [왜] 고리는 상한(MAX_SEARCHES = 2)까지만 돈다. 둘째 채점이 또 검색어를 줘도 나간다(AGENTS 6)
    assert [q for q, _ in seen] == ['SS14 Repetitive peak reverse voltage VRRM', 'SS14 Peak reverse voltage']
    assert r['path'] == ['검색', '근거 채점·답 쓰기'] * 2 and len(chat.seen) == 2
    assert r['refusal_reason'] == Reason.NOT_FOUND.value and r['answer'] == '' and r['docs'] == []


def test_fake_or_missing_citation_is_blocked_by_code():
    fake = run(task(), llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [9].')), docs=[doc(3)])
    none = run(task(), llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다.')), docs=[doc(3)])
    assert fake['refusal_reason'] == none['refusal_reason'] == Reason.VERIFY_FAILED.value and fake['answer'] == ''
    # [왜] 가짜 번호 하나로 답 전체를 거절하지 않는다(공식 5회차 v3-18). 그 번호만 단 문장은 빼고, 함께 단 괄호에서는 그 번호만 지운다
    mixed = run(task(), llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [3, 9]. 주문 코드는 같은 소자다 [9].')), docs=[doc(3)])
    assert mixed['refusal_reason'] == '' and mixed['answer'] == 'VRRM은 40 V이다 [3].'
    assert D.drop_fake_citations('값은 [0.60 V]이다 [3].', {'3'}) == ('값은 [0.60 V]이다 [3].', [])
    # [왜] 일부만 답함(partial)도 답으로 낸다. 여러 개를 묻는 질문에서 근거가 있는 부분만 답한다
    partial = run(task(), llm(D.DocsAnswer(grade='partial', answer='VRRM은 40 V이다 [3].', missing=['IFSM'])), docs=[doc(3)])
    assert partial['refusal_reason'] == '' and partial['answer'] == 'VRRM은 40 V이다 [3].'


def test_rows_of_other_part_numbers_are_dropped_before_the_llm_sees_them():
    rows = [doc(3, '[f · 2 · T] SS12 | VRRM: 20', table='T', parts=['ss12', 'ss14']), doc(4, '[f · 2 · T] SS14 | VRRM: 40', table='T', parts=['ss12', 'ss14'])]
    chat = llm(D.DocsAnswer(grade='enough', answer='SS14의 VRRM은 40 V이다 [4].'))
    r = run(task(), chat, docs=rows)
    assert '[3]' not in chat.seen[0][1] and [d['chunk_id'] for d in r['docs']] == [4]


def test_search_error_and_empty_filter_result():
    err = run(task(), llm(), error='timeout')
    assert err['refusal_reason'] == Reason.SEARCH_ERROR.value and err['path'] == ['검색', '근거 채점·답 쓰기']  # LLM을 부르지 않는다
    seen = []
    chat = llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [5].'))
    r = run(task(), chat, docs=lambda q, parts: [] if parts else [doc(5)], seen=seen, part={})
    # [왜] 품번 필터 안에서 0건이면 필터를 풀어 같은 검색어로 고리를 한 번 더 돈다(LLM은 근거가 생긴 둘째 바퀴에만 부른다)
    assert [p for _, p in seen] == [['SS14'], None] and r['refusal_reason'] == '' and len(chat.seen) == 1
    assert r['path'] == ['검색', '근거 채점·답 쓰기'] * 2


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



JUDGEMENT = {'kind': 'judge', 'roles': ['R01'], 'role_evidence': ['D1.K → RAW'], 'shown': [], 'unverified': [], 'terms': [],
             'capped': False, 'dropped': [], 'asked': [], 'results': [{
                 'part': '1N5817', 'role': 'R01', 'verdict': 'NOT_VERIFIED', 'missing': ['i_max'], 'uncertain': [], 'cautions': ['발열'],
                 'board_change': True, 'checks': [{'code': 'VRRM', 'tier': 'required', 'op': '>=', 'basis': 'v_in_max * kV',
                                                   'threshold': 15.0, 'value': 20.0, 'unit': 'V', 'condition': None,
                                                   'citation': {'document': 'a.pdf', 'page': 1, 'table': 'T', 'row': 'VRRM', 'chunk_index': 1},
                                                   'result': 'pass', 'why': ''}]}]}


def test_render_judgement_shows_values_missing_and_cautions_even_when_not_verified():
    text = Msg.render_judgement(JUDGEMENT)
    for want in ('문서로 확인 안 됨', 'VRRM', '15', '20', 'a.pdf', '1쪽', 'i_max', '발열', '기판 수정', '같은 동작은 보장하지 않'):
        assert want in text, want


def test_render_find_with_no_candidates_says_so_and_shows_terms():
    j = {**JUDGEMENT, 'kind': 'find', 'results': [], 'shown': [], 'terms': [{'code': 'VRRM', 'gte': 15.0}], 'capped': True}
    text = Msg.render_judgement(j)
    assert 'VRRM ≥ 15' in text and '찾지 못했어요' in text and '50개 상한' in text


def test_described_ratings_find_parts_with_those_exact_values_then_search_only_them():
    calls, seen = [], []

    def find(conditions, category, package, limit):
        calls.append((conditions, category, limit, package))
        return [{'part': 'BAS70'}]
    t = task(specs=[{'code': 'VRRM', 'value': 70, 'unit': 'V'}, {'code': 'IF_AV', 'value': 70, 'unit': 'mA'},
                    {'code': 'VZ', 'value': 5.1, 'unit': 'V'}], category='schottky-diode', package='SOT-23', query='PD power dissipation')
    chat = llm(D.DocsAnswer(grade='enough', answer='PD는 200 mW이다 [3].'))
    retriever_seen = []

    def docs(q, parts):
        retriever_seen.append(parts)
        return [doc(3)]
    r = run(t, chat, docs=docs, question='반복 역전압 70 V 평균 70 mA 쇼트키의 소모 전력은?', part={}, find=find)
    conds, category, _, package = calls[0]
    assert package == 'SOT-23'  # 묘사의 패키지도 거른다(h4-20)
    # [왜] 묘사한 정격은 '그 값인 부품'이다: 감쇄율 · 이상 없이 같은 값(반올림 폭 0.5%), SI 단위(70 mA = 0.07 A), 제너 전압은 대표 칸
    assert conds[0]['gte'] <= 70 <= conds[0]['lte'] and conds[0]['lte'] < 71 and abs(conds[1]['gte'] - 0.07) < 0.001
    assert conds[2]['slot'] == 'typ' and category == 'schottky-diode'
    assert retriever_seen[0] == ['BAS70'] and r['refusal_reason'] == '' and r['searches'][0]['parts'] == ['BAS70']
    none = run(t, llm(), docs=[doc(3)], question='q', part={}, find=lambda *a: [])
    assert none['refusal_reason'] == Reason.NOT_FOUND.value and 'searches' not in none  # 그 정격의 품번이 없으면 검색 · LLM 없이 '못 찾음'


def test_zener_voltage_falls_back_to_the_min_max_window_when_no_nominal_column():
    calls = []

    def find(conditions, category, package, limit):
        calls.append(conditions)
        return [] if len(calls) == 1 else [{'part': 'BZT52B68'}]
    parts = D.lookup_parts(D.Task.model_validate(task(specs=[{'code': 'VZ', 'value': 68, 'unit': 'V'}])), find)
    assert parts == ['BZT52B68'] and calls[1] == [{'code': 'VZ', 'slot': 'min', 'lte': 68.0}, {'code': 'VZ', 'slot': 'max', 'gte': 68.0}]
