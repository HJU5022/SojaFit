"""공개 회로도 검색·시트 캐시와 다른 인스턴스에서의 원본 복구."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest

from backend.projects import external_schematic as api
from backend.projects.schematic_source import (
    ExternalSchematicInvalidToken, ExternalSchematicInvalidSource, ExternalSchematicNotFound,
    ExternalSchematicUpstreamError, VerifiedSchematicSource,
)
from backend.projects.external_circuit_search import OfficialSchematicRef


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "unit-test-only-padding".ljust(32, "x"))
    counts = Counter()
    clock = [1000]
    repo = "group/board"
    commit = "c" * 40
    url = "https://github.com/" + repo
    src = VerifiedSchematicSource(repo, commit, "MIT", "group/board contributors", url,
                                  url + "/tree/" + commit, "board.sch", "kicad", (), "board.sch", 2)

    def search(q, limit):
        counts["search"] += 1
        return () if q == "missing" else range(limit)

    def inspect(ref, *, query):
        counts["inspect"] += 1
        return (src,) if ref == 1 else ()

    def render(source):
        counts["render"] += 1
        assert source == src
        return (b"sheet0", b"sheet1")

    worker = api.ExternalSchematicService(search, inspect, render, clock=lambda: clock[0], wall=lambda: clock[0])
    return worker, counts, clock, src


def test_manifest_all_sheets_and_cross_instance(service):
    worker, counts, clock, _ = service
    result = worker.find("ATtiny85")
    assert result == worker.find("  attiny85  ")
    assert result.sheet_count == 2
    assert worker.load(result.token, 1) == b"sheet1"
    assert counts == {"search": 1, "inspect": 2, "render": 1}
    cold = api.ExternalSchematicService(worker.search, worker.inspect, worker.render, wall=lambda: clock[0])
    assert cold.load(result.token, 0) == b"sheet0"
    assert counts == {"search": 1, "inspect": 2, "render": 2}


def test_expired_tampered_or_out_of_range_never_redownloads(service):
    worker, counts, clock, _ = service
    token = worker.find("ATtiny85").token
    for bad, index in [(token + "=", 0), ("x.y", 0), (token, -1), (token, 2)]:
        with pytest.raises(ExternalSchematicInvalidToken):
            worker.load(bad, index)
    clock[0] += 900
    with pytest.raises(ExternalSchematicInvalidToken):
        worker.load(token, 0)
    assert counts["render"] == 1


def test_negative_cache_expires_and_transient_failure_is_retried(service):
    worker, counts, clock, _ = service
    for q in ["missing", "Missing"]:
        with pytest.raises(ExternalSchematicNotFound):
            worker.find(q)
    assert counts["search"] == 1
    clock[0] += 900
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("missing")
    assert counts["search"] == 2
    def fail(*args, **kwargs):
        raise ExternalSchematicUpstreamError()
    worker.search = fail
    with pytest.raises(ExternalSchematicUpstreamError):
        worker.find("board")
    worker.search = lambda q, limit: [1]
    assert worker.find("board").sheet_count == 2


def test_concurrent_requests_coalesce(service):
    worker, counts, _, _ = service
    started, release = Event(), Event()
    render = worker.render
    def slow(source):
        started.set()
        assert release.wait(5)
        return render(source)
    worker.render = slow
    with ThreadPoolExecutor(6) as pool:
        futures = [pool.submit(worker.find, "same") for _ in range(6)]
        assert started.wait(5)
        release.set()
        assert len({f.result().token for f in futures}) == 1
    assert counts["search"] == counts["render"] == 1


def test_bad_preview_falls_back_and_limits_candidates(service):
    worker, counts, _, source = service
    worker.inspect = lambda repo, **kw: (replace(source, asset_kind="png", asset_paths=("schematic.png",)), source)
    render = worker.render
    def convert(src):
        if src.asset_kind != "kicad":
            raise ExternalSchematicInvalidSource()
        return render(src)
    worker.render = convert
    assert worker.find("board").sheet_count == 2
    def rejected(repo, **kw):
        counts.update(["rejected"])
        return ()
    worker.inspect = rejected
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("another")
    assert counts["rejected"] == 3


def test_lru_and_image_byte_limit_evict_least_recent_complete_source(service):
    worker, counts, _, src = service
    worker.images.byte_capacity = 24
    worker.queries.capacity = 2
    worker.inspect = lambda repo, *, query: (replace(src, source_file=query + ".sch", root_schematic=query + ".sch"),)
    def draw(source):
        counts["draw"] += 1
        return (b"a" * 5, b"b" * 7)
    worker.render = draw
    first = worker.find("first")
    second = worker.find("second")
    worker.load(first.token, 0)
    worker.find("third")
    assert counts["draw"] == 3
    assert worker.load(second.token, 1) == b"b" * 7
    assert counts["draw"] == 4
    worker.find("first")
    assert counts["search"] == 4


def test_search_and_render_do_not_touch_database_or_log_input(service, monkeypatch, caplog):
    import psycopg

    worker, _, _, _ = service
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: pytest.fail("unexpected database call"))
    sentinel = "private query marker"
    result = worker.find(sentinel)
    assert worker.load(result.token, 0) == b"sheet0"
    assert sentinel not in caplog.text and result.token not in caplog.text


def test_skips_unaddressable_source_before_render_and_cache(service):
    worker, counts, _, src = service
    long_path = "가" * 850 + ".sch"
    worker.inspect = lambda repo, **kw: (replace(src, root_schematic=long_path, source_file=long_path), src)
    assert worker.find("board").source_file == src.source_file
    assert counts["render"] == 1


def test_official_candidates_short_circuit_community_fallback(monkeypatch):
    from backend.projects import external_circuit_search as search
    from backend.projects import external_schematic as api

    official = object()
    monkeypatch.setattr(search, "search_official_schematics", lambda query, limit: (official,))
    monkeypatch.setattr(search, "search_github_repositories", lambda query, limit: pytest.fail("community fallback must not run"))

    assert api._search("SparkFun Pro Micro v13", 5) == (official,)


def _official_ref():
    return OfficialSchematicRef(
        "pro_micro", "SparkFun Electronics", "SparkFun Pro Micro v13", "v13b",
        "https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro_Micro_v13b.pdf",
        "Pro_Micro_v13b.pdf", "pdf", "a" * 64, "CC-BY-4.0",
        "https://github.com/sparkfun/Pro_Micro/blob/main/LICENSE.md", "SparkFun Electronics",
    )


def test_service_does_not_call_lazy_fallback_after_verified_official_render(service):
    worker, _, _, source = service
    source = replace(source, expected_sheets=1)
    official = replace(source, source_type="manufacturer_official", evidence_grade=2,
                       source_url="https://cdn.sparkfun.com/test.pdf", source_sha256="a" * 64)
    fallback_calls = []
    worker.search = lambda query, limit: (_official_ref(),)
    worker.inspect = lambda candidate, **kw: (official,)
    worker.render = lambda candidate: (b"verified",)
    worker.fallback_search = lambda query, limit: fallback_calls.append((query, limit)) or ()

    result = worker.find("official")

    assert result.source_type == "manufacturer_official"
    assert fallback_calls == []


def test_service_uses_lazy_fallback_when_official_render_fails(service):
    worker, _, _, source = service
    source = replace(source, expected_sheets=1)
    official = replace(source, source_type="manufacturer_official", evidence_grade=2,
                       source_url="https://cdn.sparkfun.com/test.pdf", source_sha256="a" * 64)
    fallback_calls = []
    worker.search = lambda query, limit: (_official_ref(),)
    worker.inspect = lambda candidate, **kw: (official if isinstance(candidate, OfficialSchematicRef) else source,)
    def render(candidate):
        if candidate.source_type == "manufacturer_official":
            raise ExternalSchematicInvalidSource()
        return (b"community",)
    worker.render = render
    worker.fallback_search = lambda query, limit: fallback_calls.append((query, limit)) or (1,)

    result = worker.find("official")

    assert result.source_type == "community"
    assert fallback_calls == [("official", 5)]
