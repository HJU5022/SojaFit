"""GitHub 공개 저장소 후보의 출처와 외부 요청 상한을 검증한다."""
import json

import httpx
import pytest


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv("EXA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("EXA_API_KEY", "test-secret-not-for-output")


def exa_client(results, status=200):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json={"results": results})

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


def test_github_repository_root_only_and_casefold_deduplication():
    from backend.projects.external_circuit_search import search_github_repositories
    urls = ["https://github.com/features/actions", "https://github.com/org/a/blob/main/x",
            "https://github.com/org/a/issues", "https://github.com/org/a/tree/main",
            "http://github.com/org/a", "https://u@github.com/org/a", "https://github.com:8443/org/a",
            "https://github.com/O/A", "https://github.com/o/a", "https://github.com/o/b"]
    client, requests = exa_client([{"url": url} for url in urls])
    with client:
        result = search_github_repositories("LM7805", client=client)
    assert [r.repo for r in result] == ["A", "b"]
    request, = requests
    assert request.method == "POST"
    body = json.loads(request.content)
    assert body["numResults"] == 5 and body["includeDomains"] == ["github.com"]


def test_github_repository_limit_and_response_size():
    from backend.projects.external_circuit_search import ExternalCircuitSearchError, search_github_repositories
    client, _ = exa_client([{"url": f"https://github.com/O/R{i}"} for i in range(8)])
    with client:
        assert len(search_github_repositories("LM7805", client=client)) == 5
    client, _ = exa_client([{"url": "x" * 262144}])
    with client, pytest.raises(ExternalCircuitSearchError):
        search_github_repositories("LM7805", client=client)

@pytest.mark.parametrize('query', ['SS33 diode', 'SS33 다이오드'])
def test_diode_search_rejects_same_named_radio_and_keeps_component_application(query):
    from backend.projects.external_circuit_search import search_public_schematics
    client, requests = exa_client([
        {'title': 'Ranger SS33 transceiver schematic', 'url': 'https://example.org/ss33-radio-schematic.png'},
        {'title': 'SS33 Schottky diode application schematic', 'url': 'https://example.org/ss33-diode-schematic.png'},
    ])
    with client:
        result = search_public_schematics(query, client=client)
    assert [item.source_url for item in result] == ['https://example.org/ss33-diode-schematic.png']
    assert 'diode application circuit' in json.loads(requests[0].content)['query']


def test_partial_component_keyword_keeps_matching_web_candidates_and_rejects_radio():
    from backend.projects.external_circuit_search import search_public_schematics
    client, _ = exa_client([
        {'title': '1N4148 diode schematic', 'url': 'https://example.org/1n4148-diode-schematic.png'},
        {'title': '1N4148 transceiver schematic', 'url': 'https://example.org/1n4148-radio-schematic.png'},
    ])
    with client:
        result = search_public_schematics('1N414 diode', client=client)
    assert [ref.source_url for ref in result] == ['https://example.org/1n4148-diode-schematic.png']


@pytest.mark.parametrize('query,expected', [('Pico', 'Raspberry Pi Pico'), ('피코 W', 'Raspberry Pi Pico W'), ('Pico 2', 'Raspberry Pi Pico 2')])
def test_pico_keyword_uses_existing_manufacturer_discovery(query, expected):
    from backend.projects.external_circuit_search import canonical_product_query
    assert canonical_product_query(query) == expected
    assert canonical_product_query(expected) == expected


def test_diode_purpose_keywords_use_bounded_repository_search_without_a_model_number(monkeypatch):
    from backend.projects import external_circuit_search as search
    calls = []
    monkeypatch.setattr(search, 'search_github_repositories', lambda q, limit, **kwargs: calls.append((q, limit)) or ())
    assert search.search_component_repositories('schottky diode', 5, client=object()) == ()
    assert calls == [('schottky diode', 5)]


def test_partial_part_keyword_uses_bom_index_only_as_repository_discovery(monkeypatch):
    from backend.projects import external_circuit_search as search
    monkeypatch.setattr(search, 'search_github_repositories', lambda *args, **kwargs: ())
    def handle(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'results': [{'url': 'https://hardlabs.io/project/test'}]})
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text='1N4148 diode <a href="https://github.com/owner/project">Source</a>')
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        found = search.search_component_repositories('1N414 diode', 5, client=client)
    assert [repo.repository_url for repo in found] == ['https://github.com/owner/project']


def test_component_repository_search_follows_bom_index_without_requiring_diode_in_repo_name():
    from backend.projects.external_circuit_search import search_component_repositories
    calls = []
    def handle(request):
        calls.append(request)
        if request.url.host == 'api.exa.ai':
            body = json.loads(request.content)
            if body.get('includeDomains') == ['hardlabs.io']:
                return httpx.Response(200, json={'results': [{'url': 'https://www.hardlabs.io/boards/power-board', 'title': 'Power board'}]})
            return httpx.Response(200, json={'results': []})
        return httpx.Response(200, headers={'content-type': 'text/html'}, text='<a href="https://github.com/owner/power-board">Source</a><a href="https://localhost/private">bad</a> D1 SS33')
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = search_component_repositories('SS33 diode', 5, client=client)
    assert [ref.repository_url for ref in result] == ['https://github.com/owner/power-board']
    assert len(calls) == 4
    assert len({json.loads(call.content)['query'] for call in calls if call.method == 'POST'}) == 3


def test_schottky_evidence_does_not_require_literal_diode_token_in_page():
    from backend.projects.external_circuit_search import search_public_schematics
    client, _ = exa_client([{'title': 'SS33 Schottky application schematic', 'url': 'https://example.org/ss33-schematic.png'}])
    with client:
        assert len(search_public_schematics('SS33 diode',client=client)) == 1


def test_component_search_keeps_later_index_pages_and_independent_file_results():
    from backend.projects.external_circuit_search import search_component_repositories
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == 'api.exa.ai':
            body = json.loads(request.content)
            if body.get('includeDomains') == ['hardlabs.io']:
                return httpx.Response(200, json={'results': [
                    {'url': f'https://hardlabs.io/boards/board-{i}'} for i in range(8)]})
            return httpx.Response(200, json={'results': [
                {'url': 'https://github.com/independent/driver/blob/main/Circuit/driver.kicad_sch'},
                {'url': 'https://github.com/independent/driver/issues/1'},
                {'url': 'https://github.com@localhost/private/repo/blob/main/board.kicad_sch'},
            ]})
        index = request.url.path.rsplit('-', 1)[-1]
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text=f'<a href="https://github.com/index/board-{index}">Source</a> D1 1N4007')

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        found = search_component_repositories('1N4007 diode', 12, client=client)
    urls = [ref.repository_url for ref in found]
    assert 'https://github.com/index/board-7' in urls
    assert 'https://github.com/independent/driver' in urls
    assert len(urls) == len(set(urls)) == 9
    assert len(requests) <= 15


def test_component_search_reaches_candidates_after_the_old_twelve_slot_cap():
    from backend.projects.external_circuit_search import search_component_repositories
    cap = 24
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == 'api.exa.ai':
            body = json.loads(request.content)
            if body.get('includeDomains') == ['hardlabs.io']:
                return httpx.Response(200, json={'results': [
                    {'url': f'https://hardlabs.io/boards/board-{i}'}
                    for i in range(cap)]})
            return httpx.Response(200, json={'results': [
                {'url': f'https://github.com/independent/board-{i}/blob/main/board.kicad_sch'}
                for i in range(cap)]})
        index = request.url.path.rsplit('-', 1)[-1]
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text=f'<a href="https://github.com/index/board-{index}">Source</a> D1 1N4007')

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        found = search_component_repositories('1N4007 diode', cap, client=client)
    urls = [ref.repository_url for ref in found]
    assert 'https://github.com/index/board-11' in urls
    assert 'https://github.com/independent/board-11' in urls
    assert len(urls) == len(set(urls)) == cap
    post_requests = [request for request in requests if request.method == 'POST']
    assert len(post_requests) == 3
    assert all(json.loads(request.content)['numResults'] <= cap for request in post_requests)
    html_requests = [request for request in requests if request.url.host == 'hardlabs.io']
    assert len(html_requests) <= cap


def test_component_search_preserves_index_results_when_repository_search_fails():
    from backend.projects.external_circuit_search import search_component_repositories

    def handle(request):
        if request.url.host == 'api.exa.ai':
            if json.loads(request.content).get('includeDomains') != ['hardlabs.io']:
                return httpx.Response(503)
            return httpx.Response(200, json={'results': [{'url': 'https://hardlabs.io/boards/driver'}]})
        return httpx.Response(200, headers={'content-type': 'text/html'},
                              text='<a href="https://github.com/owner/driver">Source</a> BAT54')

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        found = search_component_repositories('BAT54 diode', client=client)
    assert [ref.repository_url for ref in found] == ['https://github.com/owner/driver']
