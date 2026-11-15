"""서브에이전트(RAG 에이전트)와 사실 · 거절 문구 · 판정 답 틀 시험.

- 역할: RAG 에이전트가 지시서의 검색어로 찾고(역할 할 일은 검색 없이 넷리스트로), 근거 채점 + 답 쓰기를 LLM 한 번으로 하고,
  근거가 없으면 LLM이 준 다른 검색어로 한 번만 다시 찾고, 보여 준 적 없는 근거 인용을 코드로 막는지,
  다른 품번 줄을 LLM에 보이기 전에 거르는지, 검색 장애 · 0건을 보고하는지 본다. 사실 확인과 거절 문구 · 판정 답 틀도 확인한다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/agents/docs.py, facts.py, messages.py
"""
import pytest

from backend.graph.mcp_retriever import RetrievalUnavailableError
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


def run(task, chat, docs=(), seen=None, error=None, question='SS14의 VRRM은?', part=PART):
    def retriever(query, parts=None):
        if seen is not None:
            seen.append((query, parts))
        if error:
            raise RetrievalUnavailableError(error)
        return list(docs(query, parts) if callable(docs) else docs)
    return D.docs_agent({'task': task, 'question': question, 'target_part': part}, retriever=retriever, chat=chat)['reports'][0]


def task(**kw):
    return {'id': 1, 'agent': 'docs', 'kind': 'rating', 'goal': 'VRRM of SS14', 'query': 'SS14 Repetitive peak reverse voltage VRRM', **kw}


def test_rating_task_searches_with_the_brief_query_and_answers_in_one_llm_call():
    seen = []
    chat = llm(D.DocsAnswer(grade='enough', answer='SS14의 VRRM은 40 V이다 [3].'))
    r = run(task(), chat, docs=[doc(3)], seen=seen)
    assert seen == [('SS14 Repetitive peak reverse voltage VRRM', ['SS14'])]  # 지시서 검색어 + 질문의 품번 필터
    assert r['status'] == 'ok' and r['evidence_ids'] == ['3'] and r['llm_calls'] == 1 and r['docs'][0]['chunk_id'] == 3
    assert r['searches'][0]['top'] == [['SS12 SERIES_K2301.pdf', 2]]
    node, user = chat.seen[0]
    assert node == 'docs_answer' and 'goal: VRRM of SS14' in user and '[3] SS12 SERIES_K2301.pdf' in user
    assert '[넷리스트]' not in user and 'D1.1' not in user


def test_role_task_uses_only_the_netlist_without_searching():
    seen = []
    chat = llm(D.DocsAnswer(grade='enough', answer='D1은 +5V에 연결된다 [넷리스트].'))
    r = run(task(kind='role', query=''), chat, seen=seen)
    assert seen == [] and r['status'] == 'ok' and r['evidence_ids'] == ['넷리스트'] and r['searches'] == []
    assert '[넷리스트] D1 SS14' in chat.seen[0][1] and '+5V: D1.1, U1.3' in chat.seen[0][1]


def test_rating_without_documents_does_not_fall_back_to_circuit_evidence():
    seen = []
    r = run(task(), lambda *a: pytest.fail('Rating must not call a model without document evidence'), seen=seen)
    assert len(seen) == 2 and r['llm_calls'] == 0 and r['reason'] == 'no_result'


def test_no_evidence_retries_once_with_the_llm_query_then_reports_a_retry_reason():
    seen = []
    chat = llm(D.DocsAnswer(grade='none', next_query='SS14 Peak reverse voltage'), D.DocsAnswer(grade='none', next_query='again'))
    r = run(task(), chat, docs=[doc(3)], seen=seen)
    assert [q for q, _ in seen] == ['SS14 Repetitive peak reverse voltage VRRM', 'SS14 Peak reverse voltage']  # 검색은 2번까지
    # [왜] 설계 v2: RAG 에이전트는 거절을 정하지 않고 다시 찾을 사유를 올린다(청크는 봤지만 근거가 아님 → all_rejected)
    assert r['status'] == 'fail' and r['reason'] == Reason.ALL_REJECTED.value and r['llm_calls'] == 2


def test_internal_failure_uses_one_external_search_and_accepts_web_citations():
    web_calls = []

    def web_search(parts, terms):
        web_calls.append((parts, terms))
        return [{'chunk_id': 'W1', 'file': 'Maker data sheet', 'page': '', 'content': 'trr is 4 ns',
                 'table': 'Switching characteristics', 'row': 'Reverse recovery time',
                 'cells': [('1N4148','4')], 'unit': 'ns', 'doc_parts': ['1N4148'], 'source_type': 'external_web',
                 'source_url': 'https://maker.example/1N4148.pdf', 'title': 'Maker data sheet',
                 'retrieved_at': '2026-11-11T00:00:00+00:00'}]

    chat = llm(D.DocsAnswer(grade='none', next_query='1N4148 reverse recovery time trr'),
               D.DocsAnswer(grade='none', next_query='1N4148 switching time'),
               D.PdfOnlyAnswer(grade='enough', pdf_rows=['W1']))
    result = D.docs_agent({'task': task(parts=['1N4148']), 'question': '1N4148의 역회복 시간은?', 'target_part': PART},
                          retriever=lambda *args, **kwargs: [doc(3)], chat=chat,
                          web_search=web_search)['reports'][0]

    assert len(web_calls) == 1
    assert result['status'] == 'ok' and result['evidence_ids'] == ['W1']
    assert next(d for d in result['docs'] if d['chunk_id'] == 'W1')['source_url'] == 'https://maker.example/1N4148.pdf'
    external_prompt = chat.seen[-1][1]
    assert 'https://maker.example/1N4148.pdf' in external_prompt
    assert '[3]' not in external_prompt


@pytest.mark.parametrize('grade', ['none', 'partial'])
def test_external_recheck_preserves_only_cited_internal_facts_and_reports_rejected_rows(grade):
    prior = D.DocsAnswer(grade=grade, answer='조건은 25 °C이다 [3].' if grade == 'partial' else '',
                         missing=['정격'])
    chat = llm(prior, D.PdfAnswer(grade='none', pdf_rows=[], missing=['요청한 품번 열']))
    row = {'chunk_id': 'W1', 'file': 'ss32.pdf', 'source_type': 'external_web',
           'source_url': 'https://www.vishay.com/docs/88751/ss32.pdf', 'page': 1,
           'table': 'MAXIMUM RATINGS', 'row': 'Maximum RMS voltage', 'content': 'SS14 = 28 V',
           'doc_parts': ['SS14'], 'cells': [('SS14', '28')], 'unit': 'V'}
    report = D.docs_agent({'task': task(), 'question': 'SS14의 VRRM은?', 'target_part': PART},
                          retriever=lambda *a, **kw: [doc(3, 'VRRM 40 V, TA = 25 °C'), doc(4)], chat=chat,
                          web_search=lambda *a: [row])['reports'][0]
    prompt = chat.seen[-1][1]
    assert '[4]' not in prompt and ('[3]' in prompt) == (grade == 'partial')
    if grade == 'none':
        assert report['reason'] == 'all_rejected' and report['missing'] == ['요청한 품번 열']
        assert [d['chunk_id'] for d in report['docs']] == ['W1']
        assert 'content' not in report['docs'][0]
    else:
        assert report['evidence_ids'] == ['3'] and report['status'] == 'partial'


@pytest.mark.parametrize('assigned', [[], ['1n5819']])
def test_external_lookup_keeps_task_part_after_relaxed_internal_retry(assigned):
    query = 'onsemi 1N5819 peak repetitive reverse voltage'
    requested = []
    base = {'file': 'ratings.pdf', 'source_type': 'external_web', 'page': 2, 'table': 'MAXIMUM RATINGS',
            'row': 'Peak Repetitive Reverse Voltage', 'unit': 'V', 'source_url': 'https://www.onsemi.com/pdf/datasheet/1n5817-d.pdf'}

    def lookup(parts, terms):
        requested.append((parts, terms))
        return [{**base, 'chunk_id': cid, 'doc_parts': [part], 'cells': [(column, value)], 'content': value}
                for cid, part, column, value in [('W1', '1N4001', '1N4001', '50'),
                                                 ('W2', '1N5819', '1N4001', '50'),
                                                 ('W3', '1N5819', '1N5819', '40')]]

    chat = llm(D.PdfOnlyAnswer(grade='enough', pdf_rows=['W3']))
    report = D.docs_agent({'task': task(parts=assigned, query=query), 'round': 2,
                           'question': '1N4001과 1N5819의 VRRM은?'},
                          retriever=lambda *args, **kwargs: [], chat=chat, web_search=lookup)['reports'][0]
    assert requested == [(assigned or ['1N5819'], query)]
    assert '[W1]' not in chat.seen[0][1] and '[W2]' not in chat.seen[0][1]
    assert report['evidence_ids'] == ['W3'] and '40 V' in report['answer']


def test_internal_answer_never_calls_external_search():
    chat = llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [3].'))
    result = D.docs_agent({'task': task(), 'question': 'SS14의 VRRM은?', 'target_part': PART},
                          retriever=lambda *args, **kwargs: [doc(3)], chat=chat,
                          web_search=lambda *args: pytest.fail('sufficient internal evidence must not call Exa'))['reports'][0]
    assert result['status'] == 'ok' and result['evidence_ids'] == ['3']


def test_fake_or_missing_citation_is_blocked_by_code():
    bad=D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [9].')
    uncited=D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다.')
    fake = run(task(), llm(bad,bad), docs=[doc(3)])
    none = run(task(), llm(uncited,uncited), docs=[doc(3)])
    assert fake['status'] == none['status'] == 'fail' and fake['reason'] == none['reason'] == Reason.VERIFY_FAILED.value
    # [왜] 가짜 번호 하나로 답 전체를 거절하지 않는다(공식 5회차 v3-18). 그 번호만 단 문장은 빼고, 함께 단 괄호에서는 그 번호만 지운다
    partly_cited=D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [3, 9]. 주문 코드는 같은 소자다 [9].')
    mixed = run(task(), llm(partly_cited,partly_cited), docs=[doc(3)])
    assert mixed['status'] == 'partial' and mixed['answer'] == 'VRRM은 40 V이다 [3].'
    assert D.drop_fake_citations('값은 [0.60 V]이다 [3].', {'3'}) == ('값은 [0.60 V]이다 [3].', [])
    partial = run(task(), llm(D.DocsAnswer(grade='partial', answer='VRRM은 40 V이다 [3].', missing=['IFSM'])), docs=[doc(3)])
    assert partial['status'] == 'partial' and partial['missing'] == ['IFSM']


def test_rows_of_other_part_numbers_are_dropped_before_the_llm_sees_them():
    rows = [doc(3, '[f · 2 · T] SS12 | VRRM: 20', table='T', parts=['ss12', 'ss14']), doc(4, '[f · 2 · T] SS14 | VRRM: 40', table='T', parts=['ss12', 'ss14'])]
    chat = llm(D.DocsAnswer(grade='enough', answer='SS14의 VRRM은 40 V이다 [4].'))
    r = run(task(), chat, docs=rows)
    assert '[3]' not in chat.seen[0][1] and [d['chunk_id'] for d in r['docs']] == [4]


def test_search_error_and_empty_filter_result():
    err = run(task(), llm(), error='timeout')
    assert err['status'] == 'fail' and err['reason'] == Reason.SEARCH_ERROR.value
    seen = []
    chat = llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [5].'))
    r = run(task(), chat, docs=lambda q, parts: [] if parts else [doc(5)], seen=seen, part={})
    assert [p for _, p in seen] == [['SS14'], None] and r['status'] == 'ok'  # 품번 필터 안 0건이면 필터를 풀어 한 번 더


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


def test_parts_in_the_brief_filter_the_search_to_those_part_numbers():
    seen = []
    r = run(task(parts=['TS40P05G']), llm(D.DocsAnswer(grade='enough', answer='TJ는 150°C이다 [3].')), docs=[doc(3, 'TJ 150 °C')], seen=seen,
            question='반복 역전압 1000 V, 평균 40 A 브리지 정류기의 접합부 온도 한계는?', part={})
    # [왜] 재계획이 앞 회차 찾기의 품번을 지시서에 넣었다. 질문에 품번이 없어도 그 품번 문서 안에서만 찾는다(설계 v2)
    assert seen[0][1] == ['TS40P05G'] and r['searches'][0]['parts'] == ['TS40P05G'] and r['status'] == 'ok'


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
        return [doc(3, 'PD 200 mW')]
    r = D.docs_agent({'task': t, 'question': '반복 역전압 70 V 평균 70 mA 쇼트키의 소모 전력은?', 'target_part': {}},
                     retriever=lambda q, parts=None: docs(q, parts), chat=chat, find=find)['reports'][0]
    conds, category, _, package = calls[0]
    assert package == 'SOT-23'  # 묘사의 패키지도 거른다(h4-20)
    # [왜] 묘사한 정격은 '그 값인 부품'이다: 감쇄율 · 이상 없이 같은 값(반올림 폭 0.5%), SI 단위(70 mA = 0.07 A), 제너 전압은 대표 칸
    assert conds[0]['gte'] <= 70 <= conds[0]['lte'] and conds[0]['lte'] < 71 and abs(conds[1]['gte'] - 0.07) < 0.001
    assert conds[2]['slot'] == 'typ' and category == 'schottky-diode'
    assert retriever_seen[0] == ['BAS70'] and r['status'] == 'ok' and 'BAS70' in r['summary']
    none = D.docs_agent({'task': t, 'question': 'q', 'target_part': {}}, retriever=lambda q, parts=None: [doc(3)], chat=llm(),
                        find=lambda *a: [])['reports'][0]
    assert none['status'] == 'fail' and none['reason'] == Reason.NO_RESULT.value  # 그 정격의 품번이 없으면 다시 찾을 사유


def test_zener_voltage_falls_back_to_the_min_max_window_when_no_nominal_column():
    calls = []

    def find(conditions, category, package, limit):
        calls.append(conditions)
        return [] if len(calls) == 1 else [{'part': 'BZT52B68'}]
    parts = D.lookup_parts(D.Task.model_validate(task(specs=[{'code': 'VZ', 'value': 68, 'unit': 'V'}])), find)
    assert parts == ['BZT52B68'] and calls[1] == [{'code': 'VZ', 'slot': 'min', 'lte': 68.0}, {'code': 'VZ', 'slot': 'max', 'gte': 68.0}]


def test_partial_answer_searches_once_more_for_what_is_missing_and_keeps_the_first_evidence():
    """[왜] 일부만 답하고 끝내 정답 근거(SS14H · SS14 정격표) 없이 답했다(v3-20, 사전 등록 #49)."""
    seen = []
    chat = llm(D.DocsAnswer(grade='partial', answer='주문 코드는 SS1xH이다 [3].', missing=['IF'], next_query='SS14H SS14 average forward current IF'),
               D.DocsAnswer(grade='enough', answer='주문 코드는 SS1xH이다 [3]. IF는 둘 다 1 A이다 [4].'))
    r = run(task(), chat, docs=lambda q, parts: [doc(3)] if 'VRRM' in q else [doc(3), doc(4, content='IF 1 A')], seen=seen)
    assert [q for q, _ in seen] == ['SS14 Repetitive peak reverse voltage VRRM', 'SS14H SS14 average forward current IF']
    assert r['status'] == 'ok' and r['evidence_ids'] == ['3', '4'] and r['llm_calls'] == 2
    assert '[3]' in chat.seen[1][1] and '[4]' in chat.seen[1][1]  # 두 번째 답 쓰기는 앞 근거와 새 근거를 함께 본다
    # 새 근거가 없으면 다시 부르지 않고, 다시 답이 none이면 첫 일부 답을 쓴다
    same = run(task(), llm(D.DocsAnswer(grade='partial', answer='VRRM은 40 V이다 [3].', next_query='more')), docs=[doc(3)])
    assert same['status'] == 'partial' and same['llm_calls'] == 1
    worse = run(task(), llm(D.DocsAnswer(grade='partial', answer='VRRM은 40 V이다 [3].', next_query='more'), D.DocsAnswer(grade='none')),
                docs=lambda q, parts: [doc(3)] if 'VRRM' in q else [doc(5)])
    assert worse['status'] == 'partial' and worse['answer'] == 'VRRM은 40 V이다 [3].' and worse['llm_calls'] == 2


def test_grade2_search_preserves_explicit_manufacturer_in_user_question():
    queries = []
    task_input = task(parts=['BAT54'], query='BAT54 diode reverse voltage')
    def official(parts, terms):
        queries.append((parts, terms))
        return []
    report = D.docs_agent({'task': task_input, 'question': '인피니언 BAT54의 역전압은?'},
                          retriever=lambda *args, **kwargs: [doc(1, parts=['BAT54'])], chat=llm(),
                          web_search=official)['reports'][0]
    assert queries == [(['BAT54'], 'BAT54 diode reverse voltage Infineon')]
    assert report['evidence_ids'] == []
    report = D.docs_agent({'task': task_input, 'question': 'Vishay BAT54의 역전압은?'},
                          retriever=lambda *a, **k: [doc(1, parts=['BAT54'])], chat=llm(),
                          web_search=lambda *a: pytest.fail('wrong manufacturer'))['reports'][0]
    assert report['evidence_ids'] == []


def _early_web_run(facts, chat, *, web_calls, topic='역회복 시간', query='reverse recovery time trr'):
    """코퍼스 밖 품번 병렬 출발 시험 틀: 내부 검색이 웹 검색이 출발할 때까지 기다리게 해 순서를 본다."""
    import threading
    started = threading.Event()
    row = {'chunk_id': 'W1', 'file': 'Maker data sheet', 'page': '', 'content': 'trr is 4 ns', 'table': 'Switching characteristics',
           'row': 'Reverse recovery time', 'cells': [('1N4148', '4')], 'unit': 'ns', 'doc_parts': ['1N4148'],
           'source_type': 'external_web', 'source_url': 'https://maker.example/1N4148.pdf', 'title': 'Maker data sheet',
           'retrieved_at': '2026-11-15T00:00:00+00:00'}

    def web_search(parts, terms):
        web_calls.append((parts, terms))
        started.set()
        return [row]

    def retriever(query, parts=None):
        # 병렬 출발이면 웹 검색이 곧 시작해 True, 내부 검색 뒤에야 출발하면 0.5초 뒤 False
        web_calls.append('internal' if started.wait(timeout=0.5) else 'internal-without-web')
        return [doc(3)]

    return D.docs_agent({'task': task(parts=['1N4148'], query=f'1N4148 {query}'), 'facts': facts,
                         'question': f'1N4148의 {topic}은?', 'target_part': PART},
                        retriever=retriever, chat=chat, web_search=web_search)['reports'][0]


def test_part_missing_from_corpus_starts_official_web_search_with_the_internal_search_and_reuses_it():
    web_calls = []
    chat = llm(D.DocsAnswer(grade='none', next_query='ignored by the early call'), D.DocsAnswer(grade='none'),
               D.PdfOnlyAnswer(grade='enough', pdf_rows=['W1']))
    result = _early_web_run({'parts': {'1N4148': False}, 'revisions': {}}, chat, web_calls=web_calls)
    assert 'internal-without-web' not in web_calls  # 내부 검색이 끝나기 전에 웹 검색이 이미 출발했다
    assert [c for c in web_calls if isinstance(c, tuple)] == [(['1N4148'], '1N4148 reverse recovery time trr')]  # 한 번만, task.query로
    assert web_calls.count('internal') == 2 and result['status'] == 'ok' and result['evidence_ids'] == ['W1']


def test_early_web_result_is_discarded_when_the_internal_search_answers():
    web_calls = []
    chat = llm(D.DocsAnswer(grade='enough', answer='VRRM은 40 V이다 [3].'))
    result = _early_web_run({'parts': {'1N4148': False}, 'revisions': {}}, chat, web_calls=web_calls, topic='VRRM', query='VRRM')
    assert any(isinstance(c, tuple) for c in web_calls) and result['evidence_ids'] == ['3']  # 웹은 출발했지만 결과는 쓰지 않는다


def test_part_present_in_corpus_keeps_the_web_search_after_the_internal_failure():
    web_calls = []
    chat = llm(D.DocsAnswer(grade='none', next_query='x'), D.DocsAnswer(grade='none'), D.PdfOnlyAnswer(grade='enough', pdf_rows=['W1']))
    result = _early_web_run({'parts': {'1N4148': True}, 'revisions': {}}, chat, web_calls=web_calls)
    assert web_calls[:2] == ['internal-without-web'] * 2 and len(web_calls) == 3  # 웹은 내부 검색 두 번이 끝난 뒤에만 부른다
    assert result['evidence_ids'] == ['W1']
