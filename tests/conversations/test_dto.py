import importlib.util

import pytest


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


def test_safe_judgement_fields_match_runs_sql_shape():
    # [왜] 11-10 SafeJudgement에 preferred_mount를 더하고 runs.safe_result 저장 검사(db/019)를 빠뜨려, 판정이 붙은 run이 저장에서 거부됐다
    import json
    from pathlib import Path
    from backend.conversations.models import SafeJudgement
    root = Path(__file__).resolve().parents[2] / 'db'
    for name in ('019_conversations.sql', '025_runs_safe_result_preferred_mount.sql'):
        text = (root / name).read_text(encoding='utf-8')
        key = "conversation_json_matches(safe_result, '"
        start = text.index(key) + len(key)
        shape = json.loads(text[start:text.index("'", start)])
        allowed = [alt for alt in shape['judgement']['$any'] if isinstance(alt, dict)][0]
        assert set(SafeJudgement.model_fields) <= set(allowed), (name, set(SafeJudgement.model_fields) - set(allowed))


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
