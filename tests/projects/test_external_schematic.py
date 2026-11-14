"""공개 회로도 검색·시트 캐시와 다른 인스턴스에서의 원본 복구."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest

from backend.projects import external_schematic as api
from backend.projects.schematic_source import (
    ExternalSchematicInvalidToken, ExternalSchematicInvalidSource, ExternalSchematicNotFound,
    ExternalSchematicRateLimited,
    ExternalSchematicUpstreamError, VerifiedSchematicSource,
)
from backend.projects.external_circuit_search import WebSchematicRef


@pytest.mark.parametrize('has_candidate,reason', [(False, 'no_candidates'), (True, 'validation_failed')])
def test_not_found_preserves_failure_reason_in_negative_cache(service, has_candidate, reason):
    worker, counts, _, _ = service
    worker.search = lambda query, limit: counts.update(search=1) or ((1,) if has_candidate else ())
    worker.inspect = lambda *args, **kwargs: ()
    for _ in range(2):
        with pytest.raises(ExternalSchematicNotFound) as error:
            worker.find('missing board')
        assert error.value.reason == reason
    assert counts['search'] == 1


def test_failure_diagnostics_do_not_log_query_or_source(service, caplog):
    worker, _, _, _ = service
    worker.search = lambda *args: (WebSchematicRef('https://example.org/private-schematic.pdf',
        'https://example.org/private', 'private.pdf', 'pdf', 'private title', 'Publisher'),)
    worker.inspect = lambda *args, **kwargs: ()
    with caplog.at_level('INFO', logger=api.__name__):
        with pytest.raises(ExternalSchematicNotFound):
            worker.find('private user query')
    record = next(record for record in caplog.records if record.message == 'schematic_lookup_failed')
    assert (record.candidate_count, record.inspect_rejected, record.render_rejected) == (1, 1, 0)
    assert record.reason == 'validation_failed'
    assert 'private' not in str(vars(record))


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


def test_transient_candidate_download_gets_one_bounded_retry(service):
    worker, _, _, source = service
    attempts = []
    worker.search = lambda query, limit: (1,)

    def inspect(candidate, *, query):
        attempts.append(candidate)
        if len(attempts) == 1:
            raise ExternalSchematicUpstreamError()
        return (source,)

    worker.inspect = inspect
    assert worker.find("board").sheet_count == 2
    assert attempts == [1, 1]


def test_persistent_candidate_failure_is_not_retried_without_limit(service):
    worker, _, _, _ = service
    attempts = []
    worker.search = lambda query, limit: (1,)
    worker.fallback_search = None

    def inspect(candidate, *, query):
        attempts.append(candidate)
        raise ExternalSchematicUpstreamError()

    worker.inspect = inspect
    with pytest.raises(ExternalSchematicUpstreamError):
        worker.find("board")
    assert attempts == [1, 1]


def test_rate_limited_asset_does_not_block_next_candidate(service):
    worker, _, _, source = service
    worker.search = lambda query, limit: (1, 2)
    attempts = []

    def inspect(candidate, *, query):
        attempts.append(candidate)
        if candidate == 1:
            raise ExternalSchematicRateLimited(60)
        return (source,)

    worker.inspect = inspect
    assert worker.find("board").sheet_count == 2
    assert attempts == [1, 2]


def test_rate_limit_is_preserved_when_no_candidate_works(service):
    worker, _, _, _ = service
    worker.search = lambda query, limit: (1,)
    worker.inspect = lambda candidate, *, query: (_ for _ in ()).throw(ExternalSchematicRateLimited(60))
    with pytest.raises(ExternalSchematicRateLimited) as error:
        worker.find("board")
    assert error.value.retry_after == 60


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
    assert counts["rejected"] == 5


def test_lru_and_image_byte_limit_evict_least_recent_complete_source(service):
    worker, counts, _, src = service
    worker.images.byte_capacity = 24
    worker.queries.capacity = 2
    worker.candidates.capacity = 2
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


def test_public_candidates_short_circuit_community_fallback(monkeypatch):
    from backend.projects import external_circuit_search as search
    from backend.projects import external_schematic as api

    official = object()
    monkeypatch.setattr(search, "search_public_schematics", lambda query, limit: (official,))
    monkeypatch.setattr(search, "search_manufacturer_schematics", lambda query, limit: ())
    monkeypatch.setattr(search, "search_github_repositories", lambda query, limit: pytest.fail("community fallback must not run"))

    assert api._search("SparkFun Pro Micro v13", 5) == (official,)


def test_search_supplements_public_results_with_manufacturer_results(monkeypatch):
    from backend.projects import external_circuit_search as search

    broad = _official_ref()
    official = replace(broad, source_url="https://cdn.sparkfun.com/pro-micro-schematic.pdf")
    calls = []
    monkeypatch.setattr(search, "search_public_schematics", lambda query, limit: calls.append("broad") or (broad,))
    monkeypatch.setattr(search, "search_manufacturer_schematics", lambda query, limit: calls.append("official") or (official,))
    monkeypatch.setattr(search, "search_github_repositories", lambda query, limit: pytest.fail("unexpected fallback"))

    assert api._search("SparkFun Pro Micro v13", 5) == (official, broad)
    assert calls == ["broad", "official"]


def _official_ref():
    return WebSchematicRef(
        source_url="https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro_Micro_v13b.pdf",
        page_url="https://learn.sparkfun.com/tutorials/pro-micro--fio-v3-hookup-guide",
        source_file="Pro_Micro_v13b.pdf", asset_kind="pdf", title="SparkFun Pro Micro v13",
        attribution="SparkFun Electronics", source_type="manufacturer_official",
        evidence_grade=2, manufacturer="SparkFun Electronics", model="SparkFun Pro Micro v13",
        revision="v13b", license="CC-BY-4.0",
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
    worker.inspect = lambda candidate, **kw: (official if isinstance(candidate, WebSchematicRef) else source,)
    def render(candidate):
        if candidate.source_type == "manufacturer_official":
            raise ExternalSchematicInvalidSource()
        return (b"community",)
    worker.render = render
    worker.fallback_search = lambda query, limit: fallback_calls.append((query, limit)) or (1,)

    result = worker.find("official")

    assert result.source_type == "community"
    assert fallback_calls == [("official", 5)]


def test_public_web_token_restores_verified_asset_on_cold_instance(service):
    worker, _, clock, source = service
    public = replace(source, repository="", commit="", license="미확인",
                     attribution="Publisher", repository_url="https://example.org/board",
                     source_url="https://example.org/schematic.png", source_file="schematic.png",
                     root_schematic="schematic.png", asset_kind="png", asset_paths=(),
                     expected_sheets=1, source_type="public_web", evidence_grade=None,
                     source_sha256="a" * 64)
    worker.search = lambda query, limit: (1,)
    worker.inspect = lambda candidate, **kwargs: (public,)
    worker.render = lambda candidate: (b"verified",)
    result = worker.find("board schematic")
    assert result.source_type == "public_web"
    assert result.evidence_grade is None
    cold = api.ExternalSchematicService(worker.search, worker.inspect, worker.render, wall=lambda: clock[0])
    assert cold.load(result.token, 0) == b"verified"


def test_choices_only_include_fully_verified_sources_and_reuse_validation(service):
    worker, _, _, source = service
    refs = tuple(WebSchematicRef(
        f"https://example.org/board-{index}-schematic.png", "https://example.org/board",
        f"board-{index}-schematic.png", "png", f"Board {index}", "Publisher",
    ) for index in range(5))
    inspected, rendered = [], []
    worker.search = lambda query, limit: refs

    def inspect(candidate, **kwargs):
        inspected.append(candidate.source_url)
        if candidate in refs[1:3]:
            raise ExternalSchematicInvalidSource()
        return (replace(source, repository="", commit="", source_url=candidate.source_url,
                        source_file=candidate.source_file, root_schematic=candidate.source_file,
                        asset_kind="png", asset_paths=(), expected_sheets=1,
                        source_type="public_web", evidence_grade=None, source_sha256="a" * 64),)

    def render(candidate):
        rendered.append(candidate.source_url)
        if candidate.source_url == refs[3].source_url:
            raise ExternalSchematicInvalidSource()
        return (b"verified",)

    worker.inspect, worker.render = inspect, render
    result = worker.find("Board")
    assert [choice.source_url for choice in result.choices] == [refs[0].source_url, refs[4].source_url]
    for choice in result.choices:
        assert worker.find("Board", choice.source_url).source_url == choice.source_url
    for rejected in (*refs[1:4], replace(refs[0], source_url="https://attacker.example/schematic.png")):
        with pytest.raises(ExternalSchematicNotFound):
            worker.find("Board", rejected.source_url)
    assert inspected == [ref.source_url for ref in refs]
    assert rendered == [refs[index].source_url for index in (0, 3, 4)]


def test_user_can_select_an_exact_web_candidate_without_arbitrary_url_fetch(service):
    worker, counts, _, source = service
    urls = ("https://example.org/first-schematic.png", "https://example.org/second-schematic.png")
    refs = tuple(WebSchematicRef(url, "https://example.org/board", url.rsplit("/", 1)[-1],
                                 "png", f"Board version {index}", "Publisher")
                 for index, url in enumerate(urls, 1))
    worker.search = lambda query, limit: counts.update(["web_search"]) or refs
    worker.inspect = lambda candidate, **kwargs: (replace(
        source, repository="", commit="", source_url=candidate.source_url,
        source_file=candidate.source_file, root_schematic=candidate.source_file,
        asset_kind="png", asset_paths=(), expected_sheets=1,
        source_type="public_web", evidence_grade=None, source_sha256="a" * 64),)
    worker.render = lambda candidate: (b"verified",)

    first = worker.find("Board")
    assert first.source_url == urls[0]
    assert [choice.source_url for choice in first.choices] == list(urls)
    assert worker.find("Board", urls[1]).source_url == urls[1]
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("Board", "https://attacker.example/schematic.png")
    assert counts["web_search"] == 1
