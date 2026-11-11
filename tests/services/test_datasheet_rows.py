"""PDF 원문에서 근거를 읽어 응답과 재조회에 같은 위치를 제공하는지 검사한다."""
import httpx
import pytest

from backend.conversations.dto import public_state, result_dto, stored_evidence
from backend.conversations.models import SafeResult
from backend.multi_agent.agents.docs import DocsAnswer, docs_agent
from backend.services import exa
from backend.services.datasheet_rows import official_pdf


URL = 'https://www.vishay.com/docs/88751/ss32.pdf'


def family_pdf():
    # A small self-contained PDF with a ruled table and different ratings per part.
    commands = ['0.5 w']
    for y in (50, 70, 90):
        commands.append(f'10 {y} m 325 {y} l S')
    for x in (10, 145, 195, 250, 325):
        commands.append(f'{x} 50 m {x} 90 l S')
    for x, y, value in [(12, 100, 'Table 1. Maximum ratings'), (12, 76, 'PARAMETER'),
                        (147, 76, 'SS33'), (197, 76, 'SS34'), (252, 76, 'UNIT'),
                        (12, 57, 'Peak reverse voltage'), (147, 57, '30'), (197, 57, '40'), (252, 57, 'V')]:
        commands.append(f'BT /F1 9 Tf {x} {y} Td ({value}) Tj ET')
    stream = '\n'.join(commands).encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 350 180] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream']
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
        return DocsAnswer(grade='enough', answer='SS34의 역전압은 40 V입니다 [W1].')
    task = {'id': 1, 'agent': 'docs', 'kind': 'rating', 'parts': ['SS34'],
            'goal': 'SS34 VRRM', 'query': 'SS34 peak reverse voltage'}
    with exa.request_scope():
        report = docs_agent({'question': 'SS34의 역전압은?', 'task': task}, retriever=lambda *a, **k: [],
                            chat=chat, web_search=lambda p,t: exa.search_evidence(p,t,transport=mock))['reports'][0]
        assert not exa.search_evidence(['SS34'], 'reverse voltage', transport=mock)
    assert calls == ['POST', 'GET'] and report['evidence_ids'] == ['W1']
    assert 'content' not in report['docs'][0]
    state = public_state({'answer': report['answer'], 'final_reports': [report], 'docs': report['docs']})
    browser = result_dto(state, request_id='test')
    saved = SafeResult(answer=browser.answer, evidence=stored_evidence(browser.evidence)).model_dump()
    assert result_dto(saved, request_id='test').evidence == browser.evidence
    cite = browser.evidence[0]
    assert cite['document'] == 'ss32.pdf'
    assert (cite['source_url'], cite['page'], cite['table'], cite['row']) == (
        URL + '#page=1', 1, 'Table 1. Maximum ratings', 'Peak reverse voltage')


def test_related_part_and_unrelated_spec_provide_no_evidence(transport):
    mock, _ = transport
    assert not exa.search_evidence(['SS34A'], 'reverse voltage', transport=mock)
    assert not exa.search_evidence(['SS34'], 'capacitance', transport=mock)


@pytest.mark.parametrize('url', ['http://www.vishay.com/docs/88751/ss32.pdf',
    'https://www.vishay.com.example.org/docs/88751/ss32.pdf',
    'https://e2e.ti.com/cfs-file/f.pdf', 'https://127.0.0.1/s.pdf'])
def test_only_manufacturer_document_paths(url):
    assert not official_pdf(url)


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
        assert not exa.search_evidence(['SS34'], 'reverse voltage', transport=httpx.MockTransport(handle))
    assert visited == ['https://api.exa.ai/search', URL]
