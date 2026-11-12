"""PDF 원문에서 근거를 읽어 응답과 재조회에 같은 위치를 제공하는지 검사한다."""
import json
import re
import base64
import httpx
import pytest

from backend.conversations.dto import public_state, result_dto, stored_evidence
from backend.conversations.models import SafeResult
from backend.multi_agent.agents.docs import PdfAnswer, PdfOnlyAnswer, docs_agent
from backend.multi_agent.supervisor import check_node
from backend.judge.pdf_claims import recovery_figure_doc
from backend.services import exa
from backend.services.datasheet_rows import _figure_png, grade2_pdf, official_pdf, _row_has_part


URL = 'https://www.vishay.com/docs/88751/ss32.pdf'


def test_row_product_matching_does_not_promote_suffix_siblings():
    assert _row_has_part('UF4005 UF4006 UF4007', 'UF4007')
    assert not _row_has_part('UF4007H UF4008', 'UF4007')


def test_recovery_figure_keeps_table_and_waveform_pages_separate():
    parent = {'file': 'UF4001 SERIES_P2104.pdf', 'source_url': 'https://services.taiwansemi.com/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf',
              'source_sha256': 'a' * 64, 'source_type': 'external_web', 'evidence_grade': 2,
              'retrieved_at': '2026-11-12T00:00:00Z', 'doc_parts': ['UF4007'],
              'conditions': 'IF = 0.5 A, IR = 1.0 A, Irr = 0.25 A', 'page': 2,
              'row': 'Reverse recovery time', 'figure': {'page': 4,
              'caption': 'Fig.6 Reverse Recovery Time Characteristic and Test Circuit Diagram'}}
    reading = {'readable': True, 'start_on_zero_crossing': True, 'end_on_recovery': True,
               'unit': 'A', 'forward_current': .5, 'reverse_peak': -1,
               'recovery_end': -.25, 'arrow_start': 0, 'arrow_end': -.25,
               'labels': ['+0.5A', '0', '-1.0A', '-0.25A', 'trr']}
    doc = recovery_figure_doc(parent, reading, 'W1')
    assert doc and doc['page'] == 4 and doc['figure_reading'] == reading
    assert doc['source_url'] == parent['source_url'] and doc['evidence_grade'] == 2


@pytest.mark.parametrize('changes', [
    {'end_on_recovery': False}, {'unit': 'V'}, {'arrow_end': 0}, {'recovery_end': 0},
])
def test_recovery_figure_rejects_unsafe_waveform_readings(changes):
    parent = {'source_url': 'https://services.taiwansemi.com/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf',
              'source_sha256': 'a' * 64, 'source_type': 'external_web', 'evidence_grade': 2,
              'doc_parts': ['UF4007'], 'conditions': 'IF = 0.5 A, IR = 1.0 A, Irr = 0.25 A',
              'row': 'Reverse recovery time', 'figure': {'page': 4,
              'caption': 'Fig.6 Reverse Recovery Time Characteristic and Test Circuit Diagram'}}
    reading = {'readable': True, 'start_on_zero_crossing': True, 'end_on_recovery': True,
               'unit': 'A', 'forward_current': .5, 'reverse_peak': -1,
               'recovery_end': -.25, 'arrow_start': 0, 'arrow_end': -.25}
    reading.update(changes)
    assert recovery_figure_doc(parent, reading, 'W1') is None


def test_figure_png_is_bounded_and_keeps_page_caption():
    class Stream:
        def get_data(self):
            return bytes([255, 255, 255] * 4)

    page = type('Page', (), {'images': [{'width': 2, 'height': 2, 'top': 20, 'srcsize': (2, 2),
                                         'stream': Stream()}], 'page_number': 4,
                              'search': lambda self, *args, **kwargs: [{'bottom': 10}]})()
    result = _figure_png(page, 'Fig.6 Reverse Recovery Time Characteristic and Test Circuit Diagram')
    assert result['page'] == 4
    assert result['caption'].startswith('Fig.6 Reverse Recovery Time')
    assert len(base64.b64decode(result['image_base64'])) <= 512 * 1024


def family_pdf(*, cover=False, suffix=''):
    # A small self-contained PDF with a ruled table and different ratings per part.
    commands = ['0.5 w']
    for y in (50, 70, 90):
        commands.append(f'10 {y} m 325 {y} l S')
    for x in (10, 145, 195, 250, 325):
        commands.append(f'{x} 50 m {x} 90 l S')
    for x, y, value in [(12, 100, 'Table 1. Maximum ratings'), (12, 76, 'PARAMETER'),
                        (147, 76, 'SS33' + suffix), (197, 76, 'SS34' + suffix), (252, 76, 'UNIT'),
                        (12, 57, 'Peak reverse voltage'), (147, 57, '30'), (197, 57, '40'), (252, 57, 'V')]:
        commands.append(f'BT /F1 9 Tf {x} {y} Td ({value}) Tj ET')
    stream = '\n'.join(commands).encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 350 180] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream']
    if cover:
        objects[1] = b'<< /Type /Pages /Kids [6 0 R 3 0 R] /Count 2 >>'
        objects.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 350 180] >>')
    body = bytearray(b'%PDF-1.4\n')
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    start = len(body)
    body.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets:
        body.extend(f'{offset:010} 00000 n \n'.encode())
    return bytes(body) + f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []
    def handler(req):
        calls.append(req.method)
        if req.method == 'POST':
            assert req.url.host == 'api.exa.ai' and b'private' not in req.content
            return httpx.Response(200, json={'results': [
                {'url': 'https://example.org/other.pdf'}, {'url': URL, 'highlights': ['fabricated 99 V']}]})
        assert str(req.url) == URL and 'x-api-key' not in req.headers
        return httpx.Response(200, content=family_pdf())
    return httpx.MockTransport(handler), calls


def test_verified_row_drives_answer_and_survives_run_reload(transport):
    mock, calls = transport
    def chat(node, system, prompt, schema):
        assert node == 'docs_answer'
        assert '[W1]' in prompt and 'PDF p.1' in prompt and 'SS34 = 40 V' in prompt
        assert '99 V' not in prompt and '30 V' not in prompt
        assert schema is PdfOnlyAnswer
        return schema(grade='enough', pdf_rows=['W1'])
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    with exa.request_scope():
        report = docs_agent({'question': 'SS34의 역전압은?', 'task': task}, retriever=lambda *a, **k: [],
                            chat=chat, web_search=lambda p,t: exa.search_evidence(p,t,transport=mock))['reports'][0]
        with pytest.raises(exa.SearchBudgetExhausted):
            exa.search_evidence(['SS34'], 'reverse voltage', transport=mock)
    assert calls == ['POST', 'GET'] and report['evidence_ids'] == ['W1']
    assert 'content' not in report['docs'][0]
    assert report['answer'] == 'SS34의 Peak reverse voltage 값은 40 V입니다 [W1].'
    state_for_check = {'final_reports': [report], 'passed': ['W1'], 'docs': report['docs'], 'answer': report['answer']}
    assert 'refusal_reason' not in check_node(state_for_check)
    for old, new in [('40 V', '400 V'), ('SS34', 'SS33'), ('40 V', '40 mV')]:
        changed = report['answer'].replace(old, new)
        assert check_node({**state_for_check, 'answer': changed})['refusal_reason'] == 'verify_failed'
    assert check_node({**state_for_check, 'passed': ['W1', 3], 'answer': 'SS34 400 V [3].'})['refusal_reason'] == 'verify_failed'
    state = public_state({'answer': report['answer'], 'final_reports': [report], 'docs': report['docs']})
    browser = result_dto(state, request_id='test')
    saved = SafeResult(answer=browser.answer, evidence=stored_evidence(browser.evidence)).model_dump()
    assert result_dto(saved, request_id='test').evidence == browser.evidence
    cite = browser.evidence[0]
    assert cite['document'] == 'ss32.pdf'
    assert (cite['source_url'], cite['page'], cite['table'], cite['row']) == (
        URL + '#page=1', 1, 'Table 1. Maximum ratings', 'Peak reverse voltage')


@pytest.mark.parametrize('claim', [
    'SS34의 Peak reverse voltage 값은 400 V입니다 [W1].',
    'SS33의 Peak reverse voltage 값은 40 V입니다 [W1].',
    'SS34의 Peak reverse voltage 값은 40 mV입니다 [W1].',
    'SS34는 400 V\n[W1]',
])
def test_docs_rejects_mismatched_claim_even_with_real_citation(transport, claim):
    mock, _ = transport
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    report = docs_agent({'question': 'SS34의 역전압은?', 'task': task}, retriever=lambda *a, **k: [],
                        chat=lambda *a: PdfAnswer(grade='enough', answer=claim, pdf_rows=[]),
                        web_search=lambda p,t: exa.search_evidence(p,t,transport=mock))['reports'][0]
    assert report['reason'] == 'verify_failed' and not report['answer'] and not report['evidence_ids']


def test_related_part_and_unrelated_spec_provide_no_evidence(transport):
    mock, _ = transport
    assert not exa.search_evidence(['SS34A'], 'reverse voltage', transport=mock)
    assert not exa.search_evidence(['SS34'], 'capacitance', transport=mock)


def test_grade3_reference_uses_public_url_and_title_without_fetch(transport, monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []
    def handler(req):
        calls.append(req.method)
        assert req.method == 'POST'
        return httpx.Response(200, json={'results': [
            {'url': 'https://example.org/SS34-reference', 'title': 'SS34 reference page'},
            {'url': 'https://example.org/SS340-reference', 'title': 'SS340 unrelated'},
        ]})
    with exa.request_scope():
        rows = exa.search_grade3_reference(['SS34'], 'reverse voltage', transport=httpx.MockTransport(handler))
    assert [r['source_url'] for r in rows] == ['https://example.org/SS34-reference']
    assert rows[0]['file'] == 'SS34 reference page'
    assert calls == ['POST']


def test_grade2_then_grade3_are_separate_request_scope_slots(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []
    def handler(req):
        calls.append(req.method)
        return httpx.Response(200, json={'results': []})
    transport = httpx.MockTransport(handler)
    with exa.request_scope():
        assert exa.search_evidence(['SS34'], 'reverse voltage', grade=2, transport=transport) == []
        assert exa.search_grade3_reference(['SS34'], 'reverse voltage', transport=transport) == []
    assert calls == ['POST', 'POST']


def test_grade2_slot_is_single_use_and_contention_is_typed(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []

    def handler(req):
        calls.append(req.method)
        return httpx.Response(200, json={'results': []})

    with exa.request_scope():
        transport = httpx.MockTransport(handler)
        assert exa.search_grade2_evidence(['SS34'], 'reverse voltage', transport=transport) == []
        with pytest.raises(exa.SearchBudgetExhausted) as error:
            exa.search_grade2_evidence(['SS34'], 'reverse voltage', transport=transport)
        assert error.value.grade == 2
    assert calls == ['POST']


def test_grade3_slot_is_single_use(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={'results': []}))
    with exa.request_scope():
        assert exa.search_grade3_reference(['SS34'], 'reverse voltage', transport=transport) == []
        with pytest.raises(exa.SearchBudgetExhausted) as error:
            exa.search_grade3_reference(['SS34'], 'reverse voltage', transport=transport)
        assert error.value.grade == 3


def test_docs_does_not_spend_grade3_when_grade2_slot_is_busy():
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    fallback_calls = []

    def busy(*_args):
        raise exa.SearchBudgetExhausted(2)

    def fallback(*_args):
        fallback_calls.append(True)
        return []

    report = docs_agent(
        {'question': 'SS34의 역전압은?', 'task': task}, retriever=lambda *a, **k: [],
        chat=lambda *a: pytest.fail('budget exhaustion must not call the LLM'),
        web_search=busy, web_search_fallback=fallback)['reports'][0]
    assert fallback_calls == []
    assert report['reason'] == 'limit_reached'


@pytest.mark.parametrize('failure', ['429', 'timeout'])
def test_grade2_provider_failure_is_bounded_and_grade3_remains_available(monkeypatch, failure):
    """공식 검색 장애가 무한 재시도로 번지지 않고 3등급 흐름을 막지 않는다."""
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []

    def handler(req):
        calls.append(req.method)
        if len(calls) == 1:
            if failure == 'timeout':
                raise httpx.ReadTimeout('synthetic Exa timeout', request=req)
            return httpx.Response(429, json={'error': 'rate limited'})
        return httpx.Response(200, json={'results': [
            {'url': 'https://example.org/SS34-reference', 'title': 'SS34 reference page'},
        ]})

    transport = httpx.MockTransport(handler)
    with exa.request_scope():
        assert exa.search_grade2_evidence(['SS34'], 'reverse voltage', transport=transport) == []
        refs = exa.search_grade3_reference(['SS34'], 'reverse voltage', transport=transport)

    assert len(calls) == 2
    assert refs and refs[0]['evidence_grade'] == 3


def test_grade3_fallback_is_saved_as_reference_only(monkeypatch):
    from backend.multi_agent.agents.docs import docs_agent
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    refs = [{'source_type': 'external_web_reference', 'source_url': 'https://example.org/SS34-reference',
             'file': 'SS34 reference page', 'doc_parts': ['SS34'], 'evidence_grade': 3,
             'retrieved_at': '2026-11-11T00:00:00+00:00'}]
    report = docs_agent({'question': 'SS34의 역전압은?', 'task': task}, retriever=lambda *a, **k: [],
                        chat=lambda *a: pytest.fail('grade-3 link must not be sent to the LLM'),
                        web_search=lambda *a: [], web_search_fallback=lambda *a: refs)['reports'][0]
    assert report['references'][0]['source_url'] == refs[0]['source_url']
    assert report['evidence_ids'] == []
    assert report['docs'] == []


@pytest.mark.parametrize('failure', ['429', 'timeout'])
def test_docs_agent_uses_grade3_after_grade2_provider_failure(monkeypatch, failure):
    """문서 에이전트의 정상 폴백 경로에서 2등급 장애 뒤 3등급을 한 번만 탄다."""
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    calls = []

    def handler(req):
        calls.append(req.method)
        if len(calls) == 1:
            if failure == 'timeout':
                raise httpx.ReadTimeout('synthetic Exa timeout', request=req)
            return httpx.Response(429, json={'error': 'rate limited'})
        return httpx.Response(200, json={'results': [
            {'url': 'https://example.org/SS34-reference', 'title': 'SS34 reference page'},
        ]})

    transport = httpx.MockTransport(handler)
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    with exa.request_scope():
        report = docs_agent(
            {'question': 'SS34의 역전압은?', 'task': task},
            retriever=lambda *a, **k: [],
            chat=lambda *a: pytest.fail('grade-3 references must not enter the answer model'),
            web_search=lambda p, t: exa.search_grade2_evidence(p, t, transport=transport),
            web_search_fallback=lambda p, t: exa.search_grade3_reference(p, t, transport=transport),
        )['reports'][0]

    assert calls == ['POST', 'POST']
    assert report['evidence_ids'] == []
    assert report['references'][0]['source_url'] == 'https://example.org/SS34-reference'


def test_replanned_reports_keep_their_pdf_cells_on_reload(transport):
    from backend.multi_agent.supervisor import collect_node, single_node

    mock, _ = transport
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    def lookup(transport):
        return docs_agent({'question': 'SS34?', 'task': task}, retriever=lambda *a, **kw: [],
                          chat=lambda *a: PdfOnlyAnswer(grade='enough', pdf_rows=['W1']),
                          web_search=lambda p,t: exa.search_evidence(p,t,transport=transport))['reports'][0]

    second_url = 'https://www.onsemi.com/pdf/datasheet/other.pdf'
    def second_source(req):
        if req.method == 'POST':
            return httpx.Response(200, json={'results': [{'url': second_url}]})
        return httpx.Response(200, content=family_pdf(cover=True).replace(b'Table 1.', b'Table 2.'))

    report, later = lookup(mock), lookup(httpx.MockTransport(second_source))
    old = report['docs'][0]
    # 체크포인트에 저장된 검색별 W1을 재생한다. 같은 표를 다시 찾으면 동일한 실행 번호를 쓴다.
    reports = [report, {**later, 'round': 2}, {**report, 'round': 2, 'task': 2}]
    state = {'question': 'SS34?', 'round': 2, 'plan': {'keep_earlier': True}, 'reports': reports}
    state.update(collect_node(state))
    assert [r['evidence_ids'] for r in state['final_reports']] == [['W1'], ['W2'], ['W1']]
    assert reports[1]['docs'][0]['chunk_id'] == 'W1'
    state.update(single_node(state))
    assert 'refusal_reason' not in check_node(state)
    assert check_node({**state, 'answer': state['answer'].replace('40 V입니다 [W2]', '400 V입니다 [W2]')})['refusal_reason'] == 'verify_failed'
    result = result_dto(public_state(state), request_id='finish')
    reopened = result_dto({'evidence': stored_evidence(result.evidence)}, request_id='reopen')
    assert [(d['citation_number'], d['source_url'], d['table'], d['row']) for d in reopened.evidence] == [
        ('W1', URL + '#page=1', old['table'], old['row']),
        ('W2', second_url + '#page=2', 'Table 2. Maximum ratings', old['row'])]

    # 재번호화가 체크포인트에 섞인 잘못된 수치에 새 해시를 발급해서는 안 된다.
    bad = {**report, 'answer': report['answer'].replace('40 V', '400 V')}
    assert collect_node({**state, 'reports': [bad]})['refusal_reason'] == 'verify_failed'


def test_run_labels_cross_search_limit_without_cascading_replacements():
    from backend.judge.pdf_claims import bind_run_citations, row_sentence, sentence_digest
    from backend.multi_agent.contracts import TaskReport

    def make_report(round_number, pages):
        docs, lines = [], []
        for index, page in enumerate(pages, 1):
            doc = {'chunk_id': f'W{index}', 'source_type': 'external_web', 'source_url': URL,
                   'file': 'ss32.pdf', 'page': page, 'table': 'Ratings', 'row': 'VRRM',
                   'doc_parts': ['SS34'], 'cells': [('SS34', '40')], 'unit': 'V'}
            lines.append(row_sentence(doc))
            docs.append({**doc, 'sentence_sha256': sentence_digest(lines[-1])})
        return TaskReport(round=round_number, task=1, agent='docs', status='ok', summary='',
                          answer='\n'.join(reversed(lines)), docs=docs, evidence_ids=[d['chunk_id'] for d in docs])

    first, second = make_report(1, [1, 2]), make_report(2, [3, 4])
    assert bind_run_citations([second, first])
    state = {'final_reports': [r.model_dump() for r in (first, second)], 'passed': ['W1', 'W2', 'W3', 'W4'],
             'docs': first.docs + second.docs, 'answer': first.answer + '\n' + second.answer, 'question': 'SS34?'}
    assert [line[-5:] for line in state['answer'].splitlines()] == ['[W2].', '[W1].', '[W4].', '[W3].']
    assert 'refusal_reason' not in check_node(state)
    evidence = result_dto(public_state(state), request_id='cross-limit').evidence
    assert [(d['citation_number'], d['page']) for d in evidence] == [('W1', 1), ('W2', 2), ('W3', 3), ('W4', 4)]


@pytest.mark.parametrize('url', ['http://www.vishay.com/docs/88751/ss32.pdf',
    'https://www.vishay.com.example.org/docs/88751/ss32.pdf',
    'https://e2e.ti.com/cfs-file/f.pdf', 'https://127.0.0.1/s.pdf'])
def test_only_manufacturer_document_paths(url):
    assert not official_pdf(url)


@pytest.mark.parametrize('url', [
    'https://services.taiwansemi.com/storage/resources/datasheet/1N4148-SERIES_K2301.pdf',
    'https://services.taiwansemi.com/storage/resources/datasheet/1N4148%20SERIES_K2301.pdf',
    'https://www.infineon.com/assets/row/public/documents/30/49/infineon-bat54series-datasheet-en.pdf',
    'https://www.infineon.com/assets/row/public/documents/24/49/infineon-bat54series-ds-en.pdf',
    'https://www.infineon.com/assets/row/public/documents/24/49/infineon-bas16series-ds-en.pdf',
])
def test_grade2_accepts_only_manufacturer_datasheet_paths(url):
    assert grade2_pdf(url).startswith('https://')
    assert official_pdf(url, grade=2)


@pytest.mark.parametrize('url', [
    'https://services.taiwansemi.com/storage/resources/datasheet/application-note.pdf',
    'https://www.infineon.com/assets/row/public/documents/30/49/reference-manual.pdf',
    'https://www.infineon.com/assets/row/public/documents/30/49/bat54.pdf',
    'https://services.taiwansemi.com/storage/resources/datasheet/1N4148-SERIES_K2301.pdf?download=1',
])
def test_grade2_does_not_promote_legacy_or_non_datasheet_paths(url):
    assert not grade2_pdf(url)


@pytest.mark.parametrize('pdf_status', [302, 200, 503])
def test_unreadable_pdf_never_substitutes_search_summary(transport, pdf_status):
    _, _calls = transport
    visited = []
    def handle(req):
        visited.append(str(req.url))
        if req.method == 'POST':
            return httpx.Response(200, json={'results': [{'url': URL, 'highlights': ['40 V']}]})
        return httpx.Response(pdf_status, content=b'not a PDF', headers={'Location': 'https://example.org'})
    with exa.request_scope():
        assert not exa.search_evidence(['SS34'], 'reverse voltage', transport=httpx.MockTransport(handle))
        with pytest.raises(exa.SearchBudgetExhausted):
            exa.search_evidence(['SS34'], 'reverse voltage', transport=httpx.MockTransport(handle))
    assert visited == ['https://api.exa.ai/search', URL]


def test_grade2_search_returns_only_verified_tsc_rows_and_sha256(transport, monkeypatch):
    target = 'https://services.taiwansemi.com/storage/resources/datasheet/SS34%20SERIES.pdf'
    calls = []

    def handle(req):
        calls.append((req.method, str(req.url)))
        if req.method == 'POST':
            payload = json.loads(req.content)
            assert payload['includeDomains'] == [
                'services.taiwansemi.com/storage/resources/datasheet/',
                'www.infineon.com/assets/row/public/documents/',
            ]
            return httpx.Response(200, json={'results': [{'url': target}]})
        assert str(req.url) == target
        return httpx.Response(200, content=family_pdf())

    import json
    rows = exa.search_grade2_evidence(['SS34'], 'reverse voltage', transport=httpx.MockTransport(handle))
    assert rows and rows[0]['evidence_grade'] == 2
    assert rows[0]['source_url'] == 'https://services.taiwansemi.com/storage/resources/datasheet/SS34%20SERIES.pdf'
    assert re.fullmatch(r'[0-9a-f]{64}', rows[0]['source_sha256'])
    assert calls[0][0] == 'POST'


def test_grade2_cites_redirect_destination_and_exact_family_members(transport):
    url = 'https://services.taiwansemi.com/storage/resources/datasheet/family.pdf'
    final = url.replace('family.pdf', 'SS34LW_SERIES.pdf')
    def respond(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'results': [{'url': url}]})
        if str(request.url) == url:
            return httpx.Response(301, headers={'Location': final})
        assert str(request.url) == final
        return httpx.Response(200, content=family_pdf(suffix='LW'))

    rows = exa.search_grade2_evidence(['SS34', 'SS33LW', 'SS34LW'], 'TSC reverse voltage',
                                      transport=httpx.MockTransport(respond))
    assert [(r['doc_parts'][0], r['cells'][0][1], r['source_url']) for r in rows] == [
        ('SS33LW', '30', final), ('SS34LW', '40', final)]


@pytest.mark.parametrize('manufacturer, expected', [
    ('TSC', ['services.taiwansemi.com/storage/resources/datasheet/']),
    ('Taiwan Semiconductor', ['services.taiwansemi.com/storage/resources/datasheet/']),
    ('\uB300\uB9CC\uBC18\uB3C4\uCCB4', ['services.taiwansemi.com/storage/resources/datasheet/']),
    ('Infineon', ['www.infineon.com/assets/row/public/documents/']),
    ('\uC778\uD53C\uB2C8\uC5B8', ['www.infineon.com/assets/row/public/documents/']),
])
def test_grade2_search_honors_manufacturer_alias(manufacturer, expected, monkeypatch):
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_API_KEY', 'test')
    domains = []

    def handle(req):
        if req.method == 'POST':
            domains.extend(json.loads(req.content)['includeDomains'])
            return httpx.Response(200, json={'results': []})
        raise AssertionError('no PDF should be downloaded')

    exa.search_grade2_evidence(['SS34'], f'{manufacturer} reverse voltage',
                               transport=httpx.MockTransport(handle))
    assert domains == expected
