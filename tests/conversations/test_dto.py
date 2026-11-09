import importlib.util


def test_browser_dto_excludes_internal_state():
    assert importlib.util.find_spec('backend.conversations.dto') is not None
    from backend.conversations.dto import result_dto
    body = result_dto({'answer': 'ok', 'facts': 'secret', 'plan': 'secret', 'reports': 'secret', 'counters': 1, 'check': 'secret'}, request_id='req-1').model_dump()
    assert set(body) == {'answer','status','stage','question_type','evidence','judgement','price_parts','refusal','interrupt','request_id','profile_hints'}
    assert 'secret' not in str(body)


def test_profile_hints_keep_only_kind_value_text():
    """참고(내 설정)는 사실의 칸 · 값 · 문장만 내보내고 버전 · 출처 같은 다른 칸은 버린다(최대 3개)."""
    from backend.conversations.dto import result_dto
    hint = {'kind': 'mounting_preference', 'value': 'smd', 'text': '이 사용자는 SMD 실장을 선호한다.', 'version': 2, 'source': 'user_settings'}
    body = result_dto({'answer': 'ok'}, request_id='req-1', status='completed', profile_hints=[hint] * 4).model_dump()
    assert body['profile_hints'] == [{'kind': 'mounting_preference', 'value': 'smd', 'text': '이 사용자는 SMD 실장을 선호한다.'}] * 3


def test_interrupt_result_round_trip_has_no_private_fields():
    from backend.conversations.models import SafeResult
    from pydantic import ValidationError
    import pytest
    value = SafeResult.model_validate({'answer': '', 'interrupt': {'missing': ['voltage'], 'role_choices': ['R01'], 'question': '입력해 주세요'}})
    assert value.interrupt.missing == ['voltage']
    with pytest.raises(ValidationError):
        SafeResult.model_validate({'answer': '', 'interrupt': {'missing': [], 'raw': 'private'}})


def test_safe_public_judgement_removes_internal_data():
    from backend.conversations.dto import result_dto
    state = {'answer': 'ok', 'judgement': {'kind': 'judge', 'roles': ['R01'], 'role_evidence': ['D1.K'], 'results': [
        {'part': '1N5817', 'role': 'R01', 'verdict': 'NOT_VERIFIED', 'checks': [
            {'code': 'VRRM', 'tier': 'required', 'op': '>=', 'basis': 'v_in_max * kV', 'threshold': 15, 'value': 20,
             'unit': 'V', 'condition': None, 'result': 'pass', 'why': '',
             'citation': {'document': 'a.pdf', 'page': 1, 'table': 'T', 'row': 'VRRM', 'chunk_index': 1, 'text': 'private chunk'}}],
         'secret': 'private report'}]}, 'reports': [{'secret': 'private'}]}
    body = result_dto(state, request_id='req').model_dump()
    assert body['judgement']['results'][0]['checks'][0]['citation']['document'] == 'a.pdf'
    assert 'private' not in str(body)


def test_refusal_and_judgement_citation_are_public_metadata_only():
    from backend.conversations.dto import result_dto
    state = {'answer': 'no', 'judgement': {'kind': 'judge', 'results': [{'part': '1N5817', 'verdict': 'NOT_VERIFIED', 'checks': [{'code': 'VRRM', 'citation': {'document': '/private/a.pdf', 'page': 1, 'text': 'private'}}]}]}}
    result = result_dto(state, status='refused', request_id='r').model_dump()
    assert result['refusal'] == 'no'
    assert result['evidence'][0]['document'] == 'a.pdf'
    assert 'private' not in str(result)


def test_interrupt_never_exposes_unrecognized_graph_payload():
    from backend.conversations.dto import result_dto
    dto = result_dto({}, request_id='r', status='requires_input', interrupt={'missing': ['v_in', '/private/path'], 'role_choices': ['R01', 'private'], 'question': '/private/raw', 'secret': 'private'}).model_dump()
    assert dto['interrupt']['missing'] == ['v_in']
    assert dto['interrupt']['role_choices'] == ['R01']
    assert 'private' not in str(dto)


def test_terminal_public_result_preserves_safe_graph_fields_only():
    from backend.conversations.dto import public_state
    result = public_state({'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819', 'https://private'], 'facts': {'x': 'secret'}, 'reports': [{'secret': 1}]})
    assert result == {'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819']}


def test_docs_evidence_selects_only_cited_metadata():
    from backend.conversations.dto import public_state
    result = public_state({'answer': 'ok [3]', 'final_reports': [{'evidence_ids': ['3'], 'summary': 'secret summary'}],
                           'docs': [{'chunk_id': 3, 'file': '/private/sheet.pdf', 'page': 2, 'table': 'T', 'content': 'private chunk', 'doc_parts': ['private']},
                                    {'chunk_id': 4, 'file': 'unused.pdf', 'page': 3, 'content': 'other private'}]})
    assert result['evidence'] == [{'document': 'sheet.pdf', 'page': 2, 'table': 'T', 'row': '', 'section': '', 'citation_number': '3'}]
    assert 'private' not in str(result) and 'unused' not in str(result)
