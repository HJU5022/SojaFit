import asyncio
import httpx
import pytest

from backend.mcp_skill.mcp_server import server


def test_corpus_tool_uses_retriever_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'retrieve', lambda q, **kw: calls.append((q, kw)) or [{'id': 1}])
    assert server.search_corpus('1N4148', 3, ['1N4148']) == [{'id': 1}]
    assert calls == [('1N4148', {'k': 3, 'parts': ['1N4148'], 'method': 'hybrid'})]


@pytest.mark.parametrize('query,k', [('', 5), ('  ', 5), ('x' * 501, 5), ('x', 0), ('x', 11)])
def test_corpus_rejects_invalid_input(query, k):
    with pytest.raises(ValueError):
        server.search_corpus(query, k)


def test_web_disabled_by_default_and_in_demo(monkeypatch):
    monkeypatch.delenv('EXA_WEB_SEARCH_ENABLED', raising=False)
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web('tsc-1n4148-series_k2301')['status'] == 'disabled'
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('DEMO_MODE', '1')
    assert server.search_tsc_web('tsc-1n4148-series_k2301')['status'] == 'disabled'


def test_web_requires_key(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.delenv('EXA_API_KEY', raising=False)
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web('tsc-1n4148-series_k2301')['status'] == 'missing_key'


def test_web_returns_only_unverified_tsc_https_candidates(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    calls = []
    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request('POST', url), json={'results': [
            {'url': 'https://services.taiwansemi.com/good.pdf'},
            {'url': 'https://taiwansemi.com.evil.test/fake.pdf'},
            {'url': 'http://taiwansemi.com/insecure.pdf'},
            {'url': 'https://name@taiwansemi.com/fake.pdf'},
            {'url': 'https://taiwansemi.com:444/fake.pdf'},
        ]})
    monkeypatch.setattr(server.httpx, 'post', fake_post)
    result = server.search_tsc_web('tsc-1n4148-series_k2301')
    assert result == {'status': 'ok', 'candidates': [{'url': 'https://services.taiwansemi.com/good.pdf', 'verified': False}]}
    assert len(calls) == 1
    assert calls[0][1]['follow_redirects'] is False
    assert calls[0][1]['json']['numResults'] == 5
    assert calls[0][1]['json']['query'] == 'Taiwan Semiconductor 1N4148 SERIES K2301 datasheet'


def test_web_fails_closed_without_exposing_provider_details(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    def fail(url, **kwargs):
        raise httpx.ConnectError('private provider details')
    monkeypatch.setattr(server.httpx, 'post', fail)
    assert server.search_tsc_web('tsc-1n4148-series_k2301') == {'status': 'unavailable', 'candidates': []}


@pytest.mark.parametrize('doc_id', [
    'tsc-1n4148-series_k2301',
    'tsc-1n5817-series_h2104',
    'tsc-bzt52c2v4-series_g1804',
])
def test_local_pdf_integrity_verification(doc_id):
    result = server.verify_tsc_pdf(doc_id)
    assert result == {'status': 'integrity_verified', 'integrity_verified': True, 'content_verified': False}


def test_circuit_tool_reads_allowlisted_public_example():
    result = server.get_circuit_info('breadboard_supply', 'D1')
    assert result['status'] == 'found'
    assert result['data']['ref'] == 'D1'
    assert result['data']['value'] == '1N4001'
    assert result['data']['nets']


def test_circuit_tool_rejects_unknown_circuit_and_target():
    assert server.get_circuit_info('unknown', 'D1') == {'status': 'not_found', 'data': None}
    assert server.get_circuit_info('breadboard_supply', 'NOPE') == {'status': 'not_found', 'data': None}
    with pytest.raises(ValueError):
        server.get_circuit_info('../secret', 'D1')


@pytest.mark.parametrize('query', ['', '   ', 'x' * 501])
def test_web_rejects_invalid_query(query):
    with pytest.raises(ValueError):
        server.search_tsc_web(query)


def test_mcp_exposes_both_tools():
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert names == {'search_corpus', 'search_tsc_web', 'get_corpus_document', 'verify_tsc_pdf', 'get_circuit_info'}


def test_stdio_client_lists_tools_and_demo_disables_external_search():
    import sys
    import json
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=['-m', 'backend.mcp_skill.mcp_server.server'],
            env={'DEMO_MODE': '1', 'EXA_WEB_SEARCH_ENABLED': '1'},
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.list_tools()
                assert {tool.name for tool in result.tools} == {'search_corpus', 'search_tsc_web', 'get_corpus_document', 'verify_tsc_pdf', 'get_circuit_info'}
                response = await session.call_tool('search_tsc_web', {'doc_id': 'tsc-1n4148-series_k2301'})
                assert response.isError is not True
                assert json.loads(response.content[0].text)['status'] == 'disabled'
                first = json.loads(server.MANIFEST_PATH.read_text(encoding='utf8').splitlines()[0])
                document_response = await session.call_tool('get_corpus_document', {'doc_id': first['doc_id']})
                document = json.loads(document_response.content[0].text)
                assert document['status'] == 'found'
                assert document['document']['doc_id'] == first['doc_id']
                assert document['pdf_verified'] is False
                circuit_response = await session.call_tool('get_circuit_info', {'circuit_id': 'breadboard_supply', 'target': 'D1'})
                circuit = json.loads(circuit_response.content[0].text)
                assert circuit['status'] == 'found' and circuit['data']['ref'] == 'D1'
                pdf_response = await session.call_tool('verify_tsc_pdf', {'doc_id': 'tsc-1n4148-series_k2301'})
                pdf = json.loads(pdf_response.content[0].text)
                assert pdf['status'] == 'integrity_verified' and pdf['content_verified'] is False

    asyncio.run(run())


@pytest.mark.parametrize('doc_id', [
    'unknown-part',
    'tsc-1n4148-series_k2301 internal_customer_secret',
    'customer=private@example.test',
])
def test_web_blocks_unverified_input_without_network(monkeypatch, doc_id):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web(doc_id) == {'status': 'unverified', 'candidates': []}


def test_web_blocks_untrusted_manifest_source(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    monkeypatch.setattr(server, 'get_corpus_document', lambda _: {'status': 'found', 'document': {
        'title': '1N4148 SERIES', 'revision': 'K2301', 'source_url': 'https://evil.test/1N4148 SERIES_K2301.pdf'}})
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web('known-id') == {'status': 'unverified', 'candidates': []}


def test_web_catalog_unavailable_fails_closed(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    monkeypatch.setattr(server, 'get_corpus_document', lambda _: {'status': 'unavailable'})
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web('known-id') == {'status': 'unavailable', 'candidates': []}


@pytest.mark.parametrize('title,revision,source', [
    ('1N4148 SERIES internal_secret', 'K2301', 'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES internal_secret_K2301.pdf'),
    ('1N4148 SERIES', 'K2301', 'https://services.taiwansemi.com/storage/resources/datasheet/other_K2301.pdf'),
    ('1N4148 SERIES', 'K2301-private', 'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301-private.pdf'),
])
def test_web_blocks_bad_metadata_without_network(monkeypatch, title, revision, source):
    monkeypatch.setenv('DEMO_MODE', '0')
    monkeypatch.setenv('EXA_WEB_SEARCH_ENABLED', '1')
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    monkeypatch.setattr(server, 'get_corpus_document', lambda _: {'status': 'found', 'document': {
        'title': title, 'revision': revision, 'source_url': source}})
    monkeypatch.setattr(server.httpx, 'post', lambda *a, **kw: pytest.fail('unexpected network'))
    assert server.search_tsc_web('known-id')['status'] == 'unverified'
