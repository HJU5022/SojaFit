import importlib.util

import pytest


def test_saved_run_error_exposes_only_known_public_code_and_message():
    from backend.conversations.models import SafeResult
    from backend.conversations.dto import result_dto
    error = {'code': 'LIMIT_EXCEEDED', 'message': '분석 한도에 도달했습니다.'}
    saved = SafeResult.model_validate({'interrupt': {'missing': ['v_in_max']}, 'error': error}).model_dump()
    assert result_dto(saved, request_id='new-request', status='requires_input').model_dump()['error'] == error
    assert result_dto({}, request_id='legacy').model_dump()['error'] is None
    for bad in ({**error, 'raw': 'private traceback'}, {**error, 'request_id': 'old-request'}, {**error, 'code': 'PRIVATE_CODE'}):
        with pytest.raises(ValueError):
            SafeResult.model_validate({'error': bad})
        assert result_dto({'error': bad}, request_id='r').model_dump()['error'] is None


def test_browser_dto_excludes_internal_state():
    assert importlib.util.find_spec('backend.conversations.dto') is not None
    from backend.conversations.dto import result_dto
    body = result_dto({'answer': 'ok', 'facts': 'secret', 'plan': 'secret', 'reports': 'secret', 'counters': 1, 'check': 'secret'}, request_id='req-1').model_dump()
    assert set(body) == {'answer','status','stage','question_type','evidence','judgement','price_parts','refusal','interrupt','request_id','profile_hints','web_search_unavailable','error'}
    assert 'secret' not in str(body)


def test_web_search_notice_only_when_no_web_evidence_is_shown():
    """#28: 웹 검색 장애 표시는 답에 웹 근거([W] · [R])가 없을 때만 낸다. 있으면 '등록된 자료로만 답했다'는 말이 틀린다."""
    from backend.conversations.dto import result_dto
    assert result_dto({'answer': 'x', 'web_search_unavailable': True}, request_id='r').web_search_unavailable is True
    ref = {'citation_number': 'R1', 'document': 'https://example.org/SS34-reference', 'section': '미검증 참고 정보'}
    shown = result_dto({'answer': 'x', 'web_search_unavailable': True, 'evidence': [ref]}, request_id='r')
    assert shown.evidence and shown.web_search_unavailable is False


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


def test_judgement_keeps_the_applied_mount_preference_code():
    """찾기 순서에 쓴 선호 실장 방식 코드(SPEC 8.5)만 내보낸다. 소속 · 직무 같은 다른 사실은 판정 칸에 없다."""
    from backend.conversations.dto import result_dto
    body = result_dto({'answer': 'ok', 'judgement': {'kind': 'find', 'preferred_mount': 'smd'}}, request_id='req').model_dump()
    assert body['judgement']['preferred_mount'] == 'smd'
    assert result_dto({'answer': 'ok', 'judgement': {'kind': 'judge'}}, request_id='req').model_dump()['judgement']['preferred_mount'] == ''


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


def test_target_choice_question_is_rebuilt_from_checked_choices():
    """대상 부품 질문은 저장된 문장이 아니라 검사한 후보(ref 모양 · 값 100자)로 다시 만든다(SPEC 8.9)."""
    from backend.conversations.dto import result_dto
    choices = [{'ref': 'D1', 'value': '1N4007', 'raw': 'private'}, {'ref': 'R1', 'value': '10k'}, {'ref': '<b>', 'value': 'x'},
               {'ref': 'D3', 'value': ''}, 'private', {'ref': 'D4', 'value': 'V' * 300}]
    dto = result_dto({}, request_id='r', status='requires_input',
                     interrupt={'target_choices': choices, 'question': 'private', 'pending_start': 'private'}).model_dump()
    assert dto['interrupt']['target_choices'] == [{'ref': 'D1', 'value': '1N4007'}, {'ref': 'D3', 'value': ''}, {'ref': 'D4', 'value': 'V' * 100}]
    assert dto['interrupt']['question'].startswith('넷리스트에서 다이오드 D1(1N4007), D3, D4(')
    assert dto['interrupt']['question'].endswith('를 찾았어요. 어떤 부품을 바꿀까요?')
    assert 'private' not in str(dto)


def test_terminal_public_result_preserves_safe_graph_fields_only():
    from backend.conversations.dto import public_state
    result = public_state({'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819', 'https://private'], 'facts': {'x': 'secret'}, 'reports': [{'secret': 1}]})
    assert result == {'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819']}
    from backend.conversations.dto import result_dto  # 견적 안내(#60)의 질문 종류도 저장 · 화면 결과의 허용 목록 두 곳에 있다
    assert public_state({'answer': 'ok', 'question_type': 'quote'})['question_type'] == 'quote'
    assert result_dto({'answer': 'ok', 'question_type': 'quote'}, request_id='r').question_type == 'quote'


def test_docs_evidence_selects_only_cited_metadata():
    from backend.conversations.dto import public_state
    result = public_state({'answer': 'ok [3]', 'final_reports': [{'evidence_ids': ['3'], 'summary': 'secret summary'}],
                           'docs': [{'chunk_id': 3, 'file': '/private/sheet.pdf', 'page': 2, 'table': 'T', 'content': 'private chunk', 'doc_parts': ['private']},
                                    {'chunk_id': 4, 'file': 'unused.pdf', 'page': 3, 'content': 'other private'}]})
    assert result['evidence'] == [{'document': 'sheet.pdf', 'page': 2, 'table': 'T', 'row': '', 'section': '', 'citation_number': '3'}]
    assert 'private' not in str(result) and 'unused' not in str(result)


def test_safe_result_always_has_the_six_keys_the_runs_check_requires():
    # [왜] DB(ck_runs_safe_result)는 앱 JSON 모양을 복제하지 않고 필수 키 6개만 본다. 모양 검사는 SafeResult 모델이 맡으므로
    #      모델 출력이 그 6개를 언제나 가지는지만 확인한다(키를 모델에서 빼면 저장이 거부된다)
    from backend.conversations.models import SafeResult
    required = {'answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence'}
    assert required <= set(SafeResult.model_validate({}).model_dump())
    assert required <= set(SafeResult.model_validate({'answer': 'x', 'judgement': {'kind': 'judge'}}).model_dump())

@pytest.mark.parametrize('group', ['results', 'shown', 'unverified'])
def test_citation_uses_canonical_manifest_url_not_model_url(group):
    from backend.conversations.dto import result_dto
    citation = {'document': '1N4148 SERIES_K2301.pdf', 'page': 2,
                'source_url': 'javascript:alert(1)', 'outline_page': 999}
    state = {'judgement': {'kind': 'judge', group: [{
        'part': '1N4148', 'verdict': 'ROLE_SUFFICIENT', 'package_citation': citation,
        'checks': [{'code': 'VRRM', 'citation': citation}],
    }]}}
    body = result_dto(state, request_id='req').model_dump()
    candidate = body['judgement'][group][0]
    for result in (candidate['checks'][0]['citation'], candidate['package_citation'], body['evidence'][0]):
        assert result['source_url'] == 'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf'
        assert result['outline_page'] == 4
    assert 'javascript:' not in str(body)


def test_unknown_citation_discards_supplied_source_metadata():
    from backend.conversations.dto import result_dto
    state = {'judgement': {'kind': 'judge', 'results': [{'part': 'UNKNOWN', 'verdict': 'NOT_VERIFIED',
        'checks': [{'code': 'VRRM', 'citation': {'document': 'unknown.pdf', 'source_url': 'https://evil.example/a.pdf', 'outline_page': 999}}]}]}}
    body = result_dto(state, request_id='req').model_dump()
    citation = body['judgement']['results'][0]['checks'][0]['citation']
    assert citation['source_url'] == '' and citation['outline_page'] is None
    assert body['evidence'][0]['source_url'] == '' and body['evidence'][0]['outline_page'] is None
    assert 'evil.example' not in str(body)


def test_existing_evidence_is_enriched_from_canonical_manifest_only():
    from backend.conversations.dto import result_dto
    state = {'evidence': [{'document': '/private/1N4148 SERIES_K2301.pdf', 'page': 2,
                          'source_url': 'javascript:alert(1)', 'outline_page': 999}]}
    evidence = result_dto(state, request_id='req').model_dump()['evidence'][0]
    assert evidence['document'] == '1N4148 SERIES_K2301.pdf'
    assert evidence['source_url'] == 'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf'
    assert evidence['outline_page'] == 4


@pytest.mark.parametrize('document', ['1N4148 SERIES_K2301.pdf',
    'C:\\private\\1N4148 SERIES_K2301.pdf', '/private/1N4148 SERIES_K2301.pdf'])
def test_persisted_result_has_no_browser_source_metadata(document):
    from backend.conversations.dto import public_state, result_dto
    from backend.conversations.models import SafeResult
    citation = {'document': document, 'page': 2,
                'source_url': 'javascript:alert(1)', 'outline_page': 999}
    state = {'judgement': {'kind': 'judge', 'results': [{
        'part': '1N4148', 'verdict': 'ROLE_SUFFICIENT', 'package_citation': citation,
        'checks': [{'code': 'VRRM', 'citation': citation}],
    }]}, 'docs': [{'file': citation['document'], 'page': 2, 'chunk_id': 3}],
        'final_reports': [{'evidence_ids': ['3']}]}
    public = public_state(state)
    persisted = SafeResult.model_validate(public).model_dump()
    assert 'source_url' not in str(public) and 'outline_page' not in str(public)
    assert 'source_url' not in str(persisted) and 'outline_page' not in str(persisted)
    browser = result_dto(persisted, request_id='req').model_dump()
    assert browser['evidence'][0]['outline_page'] == 4
    assert browser['judgement']['results'][0]['package_citation']['outline_page'] == 4


@pytest.mark.parametrize('document', [
    'https://evil.example/1N4148 SERIES_K2301.pdf',
    'javascript:folder/1N4148 SERIES_K2301.pdf',
    'file:///private/1N4148 SERIES_K2301.pdf',
    '//evil.example/1N4148 SERIES_K2301.pdf',
    '\\\\evil.example\\1N4148 SERIES_K2301.pdf',
    '  https://evil.example/1N4148 SERIES_K2301.pdf',
    'x://evil.example/1N4148%20SERIES_K2301.pdf',
    'ht\ttps://evil.example/1N4148%20SERIES_K2301.pdf',
    'private\t/1N4148 SERIES_K2301.pdf',
])
@pytest.mark.parametrize('group', ['results', 'shown', 'unverified'])
def test_document_urls_never_gain_canonical_metadata_after_persistence(document, group):
    from backend.conversations.dto import public_state, result_dto
    from backend.conversations.models import SafeResult
    citation = {'document': document, 'page': 2}
    state = {'judgement': {'kind': 'judge', group: [{
        'part': '1N4148', 'verdict': 'ROLE_SUFFICIENT', 'package_citation': citation,
        'checks': [{'code': 'VRRM', 'citation': citation}],
    }]}, 'docs': [{'file': document, 'page': 2, 'chunk_id': 3}],
        'final_reports': [{'evidence_ids': ['3']}]}
    persisted = SafeResult.model_validate(public_state(state)).model_dump()
    for payload in (persisted, {'evidence': [{'document': document, 'page': 2}]}):
        browser = result_dto(payload, request_id='req').model_dump()
        values = list(browser['evidence'])
        if browser['judgement']:
            candidate = browser['judgement'][group][0]
            values += [candidate['package_citation'], candidate['checks'][0]['citation']]
        assert values
        for value in values:
            assert value['source_url'] == ''
            assert value['outline_page'] is None
def test_verified_input_conditions_are_live_only_and_storage_shape_is_unchanged():
    from backend.conversations.dto import public_state, result_dto, safe_judgement
    from backend.conversations.models import SafeResult
    rows = [{'code': 'v_in_max', 'value': '20 V'}, {'code': 'i_max', 'value': '0.15 A'}]
    public = public_state({'judgement': {'kind': 'judge', 'input_conditions': rows, 'analysis_inputs': {'raw': 'private'}}})
    live = result_dto(public, request_id='req', input_conditions=rows)
    assert live.judgement['input_conditions'] == rows
    stored = SafeResult.model_validate({'judgement': safe_judgement(live.judgement)}).model_dump(mode='json')
    assert 'input_conditions' not in stored['judgement']
    assert result_dto(stored, request_id='req').judgement['input_conditions'] == []
    assert 'private' not in str(stored)


def test_input_condition_allowlist_ignores_private_or_malformed_items():
    from backend.conversations.dto import result_dto
    rows = [{'code': 'price', 'value': 'private'}, {'code': 'v_in_max', 'value': '20 V', 'raw': 'private'},
            {'code': 'i_max', 'value': {'secret': 'private'}}]
    result = result_dto({'judgement': {'kind': 'judge'}}, request_id='req', input_conditions=rows).judgement
    assert result['input_conditions'] == [{'code': 'v_in_max', 'value': '20 V'}]
    assert 'private' not in str(result)


def test_verified_grade2_row_survives_storage_and_reopen_with_exact_pdf_hash():
    from backend.conversations.dto import public_state, result_dto, stored_evidence
    from backend.conversations.models import SafeResult
    url = 'https://services.taiwansemi.com/storage/resources/datasheet/SS34_K2301.pdf'
    row = {'page': 2, 'row': 'Reverse voltage', 'table': 'Maximum ratings',
           'file': 'SS34_K2301.pdf', 'chunk_id': 'W1', 'source_type': 'external_web',
           'evidence_grade': 2, 'source_sha256': 'a' * 64, 'source_url': url}
    state = public_state({'docs': [row], 'final_reports': [{'evidence_ids': ['W1']}]})
    live = result_dto(state, request_id='live').evidence
    saved = SafeResult(evidence=stored_evidence(live)).model_dump()
    reopened = result_dto(saved, request_id='reload').evidence
    assert live == reopened
    assert len(live) == 1
    assert (live[0]['source_url'], live[0]['source_sha256'], live[0]['evidence_grade']) == (
        url + '#page=2', 'a' * 64, 2)
    assert 'cells' not in saved['evidence'][0]


def test_judge_grade2_citation_and_evidence_keep_provenance_on_reload():
    from backend.conversations.dto import result_dto, safe_judgement, stored_evidence
    from backend.conversations.models import SafeResult
    url = 'https://www.ti.com/lit/ds/symlink/SS34_K2301.pdf'
    cite = {'document': 'SS34_K2301.pdf', 'page': 1, 'table': 'Maximum ratings',
            'row': 'Reverse voltage', 'source_url': url, 'source_sha256': 'b' * 64, 'evidence_grade': 2}
    state = {'judgement': {'kind': 'judge', 'results': [{'part': 'SS34', 'verdict': 'NOT_VERIFIED',
            'checks': [{'code': 'VRRM', 'citation': cite}]}]}}
    live = result_dto(state, request_id='live')
    saved = SafeResult(evidence=stored_evidence(live.evidence), judgement=safe_judgement(live.judgement)).model_dump()
    reopened = result_dto(saved, request_id='reload')
    assert live.evidence == reopened.evidence
    assert live.judgement == reopened.judgement
    for item in (live.evidence[0], live.judgement['results'][0]['checks'][0]['citation']):
        assert item['source_url'] == url + '#page=1'
        assert item['source_sha256'] == 'b' * 64
        assert item['evidence_grade'] == 2


@pytest.mark.parametrize('url', [
    'https://assets.nexperia.com/documents/data-sheet/BAS16.pdf',
])
def test_excluded_grade2_source_is_not_exposed_or_stored_as_verified_evidence(url):
    from backend.conversations.dto import public_state, result_dto, stored_evidence
    from backend.conversations.models import SafeResult
    row = {'page': 2, 'row': 'Reverse voltage', 'table': 'Maximum ratings',
           'file': 'part.pdf', 'chunk_id': 'W1', 'source_type': 'external_web',
           'evidence_grade': 2, 'source_sha256': 'a' * 64, 'source_url': url}
    live = result_dto(public_state({'docs': [row], 'final_reports': [{'evidence_ids': ['W1']}]}),
                      request_id='excluded').evidence
    assert live == []
    saved = SafeResult(evidence=stored_evidence(live)).model_dump()
    assert result_dto(saved, request_id='reload').evidence == []
    # Saved grade-2 provenance from before the policy change is checked too.
    old = {'document': url + '#sha256=' + 'a' * 64, 'page': 2,
           'table': 'Maximum ratings', 'row': 'Reverse voltage', 'citation_number': 'W1'}
    reopened = result_dto({'evidence': [old]}, request_id='old-policy').evidence
    assert not any(item.get('evidence_grade') == 2 for item in reopened)


def test_web_references_survive_refusal_and_reload_without_becoming_rating_evidence():
    from backend.conversations.dto import public_state, result_dto, stored_evidence
    from backend.conversations.models import SafeResult
    url = 'https://www.diodes.com/datasheet/download/BAT54.pdf'
    report = {'references': [{'source_url': url}, {'source_url': url}, {'source_url': 'file:///secret'}]}
    public = public_state({'answer': '지정한 정격을 확인할 수 없습니다.', 'final_reports': [report]})
    live = result_dto(public, request_id='test', status='refused')
    saved = SafeResult(answer=live.answer, evidence=stored_evidence(live.evidence)).model_dump()
    reopened = result_dto(saved, request_id='test', status='refused')
    assert live == reopened
    assert live.answer.count(url) == 1 and '미검증 참고 정보' in live.answer
    assert len(live.evidence) == 1 and not live.judgement
    item = live.evidence[0]
    assert (item['evidence_grade'], item['citation_number'], item['source_url']) == (3, 'R1', url)
    assert not item['row'] and not item['page']


def test_interrupt_exposes_read_roles_evidence_and_per_role_inputs_only_in_safe_shapes():
    """조건 질문에 에이전트가 읽은 역할 · 근거 · 역할별 묻는 값을 싣는다(11-17). 모양이 다른 값 · 묻지 않은 이름은 버린다."""
    from backend.conversations.dto import result_dto
    dto = result_dto({}, request_id='r', status='requires_input', interrupt={
        'missing': ['v_in_max', 'v_reverse_max'], 'role_choices': ['R01', 'R02'], 'roles': ['R01', 'R02', 'R99', 5],
        'role_evidence': ['D1.K → RAW\n(커넥터 쪽)', '', 7, 'x' * 400],
        'role_missing': {'R01': ['v_in_max', 'secret_path'], 'R02': ['v_reverse_max'], 'R99': ['v_in_max'], 'R03': 'v_in_max'}}).model_dump()
    asked = dto['interrupt']
    assert asked['roles'] == ['R01', 'R02']
    assert asked['role_evidence'] == ['D1.K → RAW (커넥터 쪽)', 'x' * 300]
    assert asked['role_missing'] == {'R01': ['v_in_max'], 'R02': ['v_reverse_max']}
    assert asked['question'] == '판정에 필요한 값을 알려 주세요.'
    # [주의] 실행을 끝낼 때 저장소가 같은 결과를 저장용 모델로 다시 검사한다. 새 칸이 그 모델에 없으면 저장에서 500이 난다(11-17 8010 실측)
    from backend.conversations.models import SafeInterrupt
    assert SafeInterrupt.model_validate(asked).model_dump()['role_missing'] == {'R01': ['v_in_max'], 'R02': ['v_reverse_max']}
