"""웹 근거 미리 출발(exa.prefetch)의 계약: 꺼짐이 기본이고, 켜면 받아 둔 같은 PDF를 본 경로가 다시 받지 않는다. 네트워크 없음(_body를 가짜로 바꿈)."""
import json

import pytest

from backend.services import exa

URL = 'https://www.vishay.com/docs/88751/ss34.pdf'


@pytest.mark.parametrize('excluded_url', [
    'https://assets.nexperia.com/documents/data-sheet/BAS16.pdf',
])
def test_prefetch_searches_only_seven_makers_and_skips_excluded_pdf(fake, monkeypatch, excluded_url):
    searches, gets = [], []

    def body(client, method, url, limit, **kwargs):
        if method == 'POST':
            searches.append(kwargs['json'])
            return json.dumps({'results': [{'url': excluded_url}]}).encode(), url
        gets.append(url)
        return b'%PDF-1.7 fake', url

    monkeypatch.setattr(exa, '_body', body)
    assert exa._prefetch_pdfs(['BAS16']) == {}
    assert gets == []
    assert {domain.split('/')[0] for domain in searches[0]['includeDomains']} == {
        'www.ti.com', 'www.st.com', 'www.analog.com',
        'www.onsemi.com', 'www.infineon.com', 'www.vishay.com',
        'services.taiwansemi.com',
    }


@pytest.fixture
def fake(monkeypatch):
    """Exa 검색은 공식 PDF 1건을 돌려주고, PDF 받기는 횟수만 센다. 표 읽기는 행 1개를 돌려준다."""
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'unit-test')
    gets = []

    def body(client, method, url, limit, **kwargs):
        if method == 'POST':
            return json.dumps({'results': [{'url': URL, 'title': 'SS34 datasheet'}]}).encode(), url
        gets.append(url)
        return b'%PDF-1.7 fake', url

    monkeypatch.setattr(exa, '_body', body)
    monkeypatch.setattr(exa, 'verified_rows', lambda raw, url, parts, words, grade=None: [
        {'content': 'SS34 VRRM 40 V', 'page': 1, 'doc_parts': ['SS34']}])
    return gets


def test_prefetch_is_off_by_default(fake, monkeypatch):
    monkeypatch.delenv('WEB_PREFETCH', raising=False)
    with exa.request_scope():
        exa.prefetch(['SS34'])
        assert 'job' not in exa._prefetched.get()
        exa.search_evidence(['SS34'], 'reverse voltage', grade=2)
    assert fake == [URL]  # 본 경로가 한 번 받는다(지금까지와 같음)


def test_prefetched_pdf_is_reused_once(fake, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    with exa.request_scope():
        exa.prefetch(['SS34'])
        exa._prefetched.get()['job'].result(timeout=5)
        docs = exa.search_evidence(['SS34'], 'reverse voltage', grade=2)
    assert fake == [URL]  # 미리 받기 1번뿐, 본 경로는 다시 받지 않았다
    assert docs and docs[0]['source_url'] == URL and docs[0]['chunk_id'] == 'W1'


def test_prefetch_outside_request_scope_does_nothing(fake, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    exa.prefetch(['SS34'])
    assert fake == []


def test_prefetch_failure_falls_back_to_normal_download(fake, monkeypatch):
    monkeypatch.setenv('WEB_PREFETCH', '1')
    monkeypatch.setattr(exa, '_prefetch_pdfs', lambda parts: (_ for _ in ()).throw(RuntimeError('down')))
    with exa.request_scope():
        exa.prefetch(['SS34'])
        docs = exa.search_evidence(['SS34'], 'reverse voltage', grade=2)
    assert fake == [URL] and docs
