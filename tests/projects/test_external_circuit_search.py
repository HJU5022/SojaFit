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
