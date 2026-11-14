"""공개 회로도 검색·시트 캐시와 다른 인스턴스에서의 원본 복구."""
import base64
import hmac
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest
import httpx
from fastapi.testclient import TestClient

from backend.projects import external_schematic as api
from backend.projects.schematic_source import (
    ExternalSchematicInvalidToken, ExternalSchematicInvalidSource, ExternalSchematicNotFound,
    ExternalSchematicRateLimited,
    ExternalSchematicUpstreamError, VerifiedSchematicSource,
)
from backend.projects.external_circuit_search import WebSchematicRef
from backend.projects.external_circuit_search import GitHubRepositoryRef
from backend.projects.external_circuit_search import MAX_COMPONENT_REPOSITORIES


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


def test_default_community_render_rate_limit_is_not_reported_as_missing(service):
    worker, _, _, source = service
    ref = GitHubRepositoryRef('group', 'board', 'https://github.com/group/board')
    worker.search = lambda query, limit: (ref,)
    worker.inspect = lambda candidate, **kwargs: (source,)
    def render(candidate):
        raise ExternalSchematicRateLimited(60)
    worker.render = render
    with pytest.raises(ExternalSchematicRateLimited):
        worker.find('rate-limited circuit')


def test_community_inspection_never_exceeds_repository_budget(service):
    worker, _, _, source = service
    refs = tuple(GitHubRepositoryRef('group', f'board{i}', f'https://github.com/group/board{i}')
                 for i in range(13))
    calls = []
    worker.search = lambda query, limit: refs
    def inspect(candidate, **kwargs):
        calls.append(candidate)
        return (source,) if candidate == refs[-1] else ()
    worker.inspect = inspect
    result = worker.find('bounded community circuit')
    assert result.source_url == source.source_url
    assert calls == list(refs[:MAX_COMPONENT_REPOSITORIES])


def test_default_community_prefers_a_compact_complete_circuit_without_hiding_others(service):
    worker, _, _, source = service
    refs = tuple(GitHubRepositoryRef('group', name, f'https://github.com/group/{name}') for name in ('large', 'compact'))
    sources = tuple(replace(source, repository=f'group/{ref.repo}', source_url=ref.repository_url,
                            expected_sheets=count) for ref, count in zip(refs, (11, 1)))
    worker.search = lambda query, limit: refs
    worker.inspect = lambda ref, **kwargs: (sources[refs.index(ref)],)
    worker.render = lambda source: (b'page',) * source.expected_sheets
    result = worker.find('component circuit')
    assert result.source_url == sources[1].source_url
    assert {choice.source_url for choice in result.choices} == {source.source_url for source in sources}


@pytest.mark.parametrize("query", [
    "https://github.com/group/board",
    "http://github.com/group/board",
    "https://github.com/group/board/blob/main/board.sch",
])
def test_repository_url_is_not_a_search_query(service, query):
    worker, counts, _, _ = service
    worker.search = lambda *_: pytest.fail("repository URL must not reach search")
    with pytest.raises(ExternalSchematicNotFound):
        worker.find(query)
    assert counts["inspect"] == 0
    assert counts["render"] == 0


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


def test_reads_legacy_v1_token_during_rolling_deployment(service):
    worker, counts, _, source = service
    expires = 1500
    payload = [source.repository, source.commit, source.license, source.attribution,
               source.source_file, source.asset_kind, list(source.asset_paths),
               source.root_schematic, source.expected_sheets, expires]
    part = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.digest(api._key(), part, "sha256")).rstrip(b"=")
    token = (part + b"." + signature).decode()

    assert worker.load(token, 0) == b"sheet0"
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
    assert counts["rejected"] == MAX_COMPONENT_REPOSITORIES


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
    assert fallback_calls == [("official", MAX_COMPONENT_REPOSITORIES)]


def test_partial_rate_pool_is_rechecked_after_retry_window(service):
    worker, counts, clock, source = service
    refs = tuple(GitHubRepositoryRef("group", name, f"https://github.com/group/{name}")
                 for name in ("first", "second"))
    first = replace(source, repository="group/first", repository_url=refs[0].repository_url,
                    source_url=refs[0].repository_url + "/blob/" + "c" * 40 + "/first.kicad_sch")
    second = replace(source, repository="group/second", repository_url=refs[1].repository_url,
                     source_url=refs[1].repository_url + "/blob/" + "c" * 40 + "/second.kicad_sch")
    worker.search = lambda query, limit: refs
    attempts = Counter()

    def inspect(ref, **kwargs):
        attempts[ref.repo] += 1
        if ref is refs[0]:
            return (first,) if clock[0] < 1061 else ()
        if clock[0] < 1061:
            raise ExternalSchematicRateLimited(60)
        return (second,)

    worker.inspect = inspect
    worker.render = lambda candidate: (b"verified",) * candidate.expected_sheets

    initial = worker.find("partial rate circuit")
    assert initial.source_url == first.source_url
    assert attempts == Counter(first=1, second=1)

    # A known source remains usable during the provider cooldown, without
    # extending the original retry deadline.
    clock[0] += 30
    assert worker.find("partial rate circuit", first.source_url).source_url == first.source_url
    assert attempts == Counter(first=1, second=1)

    clock[0] += 31
    refreshed = worker.find("partial rate circuit", second.source_url)
    assert refreshed.source_url == second.source_url
    assert attempts == Counter(first=2, second=2)
    assert worker.find("partial rate circuit").source_url == second.source_url
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("partial rate circuit", first.source_url)


def test_partial_retry_deadline_cache_is_bounded(service):
    worker, _, _, _ = service
    worker.queries.capacity = 2
    worker._set_retry_deadline("one", 1100)
    worker._set_retry_deadline("two", 1100)
    worker._set_retry_deadline("three", 1100)
    assert len(worker.retry_until) <= worker.queries.capacity


def test_community_choices_are_bounded_verified_sources_from_one_repository(service):
    worker, _, _, source = service
    first = replace(source, source_url="https://github.com/group/board/blob/" + "c" * 40 + "/one.kicad_sch",
                    source_file="one.kicad_sch", root_schematic="one.kicad_sch")
    second = replace(source, source_url="https://github.com/group/board/blob/" + "c" * 40 + "/two.kicad_sch",
                     source_file="two.kicad_sch", root_schematic="two.kicad_sch")
    worker.search = lambda query, limit: (1,)
    worker.inspect = lambda candidate, **kwargs: (first, second)
    worker.render = lambda candidate: (b"verified", b"verified")

    result = worker.find("board")

    assert result.source_url == first.source_url
    assert [(choice.source_url, choice.source_type) for choice in result.choices] == [
        (first.source_url, "community"), (second.source_url, "community")]
    assert result.choices[0].title == "group/board · one.kicad_sch"


def test_community_selection_uses_cached_verified_source_without_reinspection(service):
    worker, counts, _, source = service
    refs = tuple(GitHubRepositoryRef(owner, repo, f"https://github.com/{owner}/{repo}")
                 for owner, repo in (("one", "board"), ("two", "board")))
    sources = tuple(replace(source, repository=ref.owner + "/" + ref.repo,
                            repository_url=ref.repository_url,
                            source_url=ref.repository_url + "/blob/" + "c" * 40 + "/board.sch")
                    for ref in refs)
    worker.search = lambda query, limit: refs
    worker.inspect = lambda ref, **kwargs: (sources[refs.index(ref)],)
    worker.render = lambda candidate: (b"verified", b"verified")

    first = worker.find("community board")
    inspected = counts["inspect"]
    selected = worker.find("community board", sources[1].source_url)

    assert selected.source_url == sources[1].source_url
    assert counts["inspect"] == inspected
    assert [choice.source_url for choice in first.choices] == [source.source_url for source in sources]


def test_community_selection_rejects_other_query_and_arbitrary_url(service):
    worker, _, _, source = service
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    worker.search = lambda query, limit: (ref,) if query == "community board" else ()
    worker.inspect = lambda ref, **kwargs: (source,)
    worker.render = lambda candidate: (b"verified", b"verified")
    result = worker.find("community board")
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("other board", source.source_url)
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("community board", "https://attacker.example/board.sch")
    assert result.source_url == source.source_url


def test_selected_source_keeps_same_url_format_fallbacks(service):
    worker, _, _, source = service
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    png = replace(source, source_url="https://github.com/one/board/blob/" + "c" * 40 + "/board.png",
                  source_file="board.png", root_schematic="board.kicad_sch", asset_kind="png")
    kicad = replace(source, source_url=png.source_url, source_file="board.kicad_sch", asset_kind="kicad")
    worker.search = lambda query, limit: (ref,)
    worker.inspect = lambda ref, **kwargs: (png, kicad)
    worker.render = lambda candidate: (_ for _ in ()).throw(ExternalSchematicInvalidSource()) if candidate.asset_kind == "png" else (b"ok", b"ok")
    result = worker.find("format board")
    assert result.source_file == "board.kicad_sch"
    assert len(result.choices) == 1


def test_expired_community_pool_cannot_select_stale_source(service):
    worker, _, clock, source = service
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    worker.search = lambda query, limit: (ref,) if clock[0] < 1900 else ()
    worker.inspect = lambda ref, **kwargs: (source,)
    worker.render = lambda candidate: (b"ok", b"ok")
    first = worker.find("expiring board")
    clock[0] += 900
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("expiring board", first.source_url)


def test_community_pool_preserves_partial_rate_limit_when_other_render_fails(service):
    worker, _, _, source = service
    refs = (GitHubRepositoryRef("one", "board", "https://github.com/one/board"),
            GitHubRepositoryRef("two", "board", "https://github.com/two/board"))
    worker.search = lambda query, limit: refs
    def inspect(ref, **kwargs):
        if ref == refs[0]:
            raise ExternalSchematicRateLimited(60)
        return (source,)
    worker.inspect = inspect
    worker.render = lambda candidate: (_ for _ in ()).throw(ExternalSchematicInvalidSource())
    with pytest.raises(ExternalSchematicRateLimited):
        worker.find("partial failure")


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


def test_only_kicad_sources_use_remote_renderer(service, monkeypatch):
    from backend.projects import schematic, schematic_render

    _, _, _, source = service
    calls = []
    monkeypatch.setenv("KICAD_RENDERER_URL", "http://renderer:8000")
    monkeypatch.setattr(schematic, "render_remote_kicad", lambda item: calls.append("remote") or (b"remote",))
    monkeypatch.setattr(schematic_render, "render_external_schematic",
                        lambda item: calls.append("static") or (b"static",))
    monkeypatch.setattr(schematic_render, "render_public_schematic",
                        lambda item: calls.append("official") or (b"official",))

    assert api._render(replace(source, asset_kind="png", asset_paths=("board.png",))) == (b"static",)
    assert api._render(replace(source, source_type="manufacturer_official", evidence_grade=2)) == (b"official",)
    assert api._render(source) == (b"remote",)
    assert calls == ["static", "official", "remote"]


def test_remote_renderer_failure_is_public_upstream_error(service, monkeypatch):
    from backend.projects import schematic

    _, _, _, source = service
    monkeypatch.setenv("KICAD_RENDERER_URL", "http://renderer:8000")
    monkeypatch.setattr(schematic, "render_remote_kicad",
                        lambda item: (_ for _ in ()).throw(schematic.KicadServiceUnavailable()))

    with pytest.raises(ExternalSchematicUpstreamError):
        api._render(source)


def test_remote_renderer_422_is_invalid_source_not_upstream(service, monkeypatch):
    from backend.projects import schematic
    monkeypatch.setenv("KICAD_RENDERER_URL", "http://renderer:8000")
    transport = httpx.MockTransport(lambda request: httpx.Response(422, json={"detail": "invalid"}))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ExternalSchematicInvalidSource):
            schematic.render_remote_kicad(service[3], client=client)


@pytest.mark.parametrize(
    ("error", "status"),
    [(ExternalSchematicInvalidSource(), 422), (ExternalSchematicUpstreamError(), 503)],
)
def test_renderer_boundary_maps_source_and_upstream_errors(error, status, monkeypatch, service):
    from backend.projects import schematic, schematic_render
    monkeypatch.setattr(schematic_render, "render_external_schematic",
                        lambda source: (_ for _ in ()).throw(error))
    payload = {"source": schematic._source_payload(service[3])}
    response = TestClient(schematic.app).post("/render", json=payload)
    assert response.status_code == status


def test_diode_component_search_does_not_reject_repository_by_its_name(monkeypatch):
    from backend.projects import external_circuit_search as search
    ref = search.github_repository_ref('https://github.com/owner/power-board')
    monkeypatch.setattr(search, 'search_component_repositories', lambda query, limit: (ref,))
    monkeypatch.setattr(search, 'search_public_schematics', lambda *args: ())
    monkeypatch.setattr(search, 'search_manufacturer_schematics', lambda *args: ())
    assert api._search('SS33 diode', 5) == (ref,)
    assert api._search_community('SS33 diode', 5) == (ref,)


def test_broad_search_keeps_public_provider_limit_at_five(monkeypatch):
    from backend.projects import external_circuit_search as search
    calls = []
    monkeypatch.setattr(search, "search_public_schematics",
                        lambda query, limit: calls.append(("public", limit)) or ())
    monkeypatch.setattr(search, "search_manufacturer_schematics",
                        lambda query, limit: calls.append(("manufacturer", limit)) or ())
    monkeypatch.setattr(search, "search_github_repositories", lambda query, limit: ())
    assert api._search("generic board", 12) == ()
    assert calls == [("public", 5), ("manufacturer", 5)]


def test_community_choices_do_not_revisit_a_render_rejected_source(service):
    worker, _, _, source = service
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    good = replace(source, source_url=ref.repository_url + "/good.kicad_sch")
    bad = replace(source, source_url=ref.repository_url + "/bad.kicad_sch")
    rendered = []
    worker.search = lambda query, limit: (ref,)
    worker.inspect = lambda candidate, **kwargs: (good, bad)
    def render(candidate):
        rendered.append(candidate.source_url)
        if candidate == bad:
            raise ExternalSchematicInvalidSource()
        return (b"ok", b"ok")
    worker.render = render
    result = worker.find("community board")
    assert [choice.source_url for choice in result.choices] == [good.source_url]
    before = list(rendered)
    with pytest.raises(ExternalSchematicNotFound):
        worker.find("community board", bad.source_url)
    assert rendered == before


@pytest.mark.parametrize("failure", ["inspect", "render", "sheet_count"])
def test_community_rejections_keep_validation_failed_reason(service, failure):
    worker, _, _, source = service
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    worker.search = lambda query, limit: (ref,)
    worker.inspect = lambda candidate, **kwargs: () if failure == "inspect" else (source,)
    def render(candidate):
        if failure == "render":
            raise ExternalSchematicInvalidSource()
        return (b"wrong sheet count",)
    worker.render = render
    for _ in range(2):
        with pytest.raises(ExternalSchematicNotFound) as error:
            worker.find("rejected community board")
        assert error.value.reason == "validation_failed"


def test_community_fallback_keeps_all_verified_roots_and_excludes_failed_render(service):
    worker, _, _, source = service
    web = WebSchematicRef("https://example.org/schematic.pdf", "https://example.org/board",
                          "schematic.pdf", "pdf", "Board", "Publisher")
    ref = GitHubRepositoryRef("one", "board", "https://github.com/one/board")
    sources = tuple(replace(source, source_url=ref.repository_url + f"/{index}.kicad_sch",
                            root_schematic=f"{index}.kicad_sch") for index in range(3))
    worker.search = lambda query, limit: (web,)
    worker.fallback_search = lambda query, limit: (ref,)
    worker.inspect = lambda candidate, **kwargs: () if candidate == web else sources
    def render(candidate):
        if candidate == sources[1]:
            raise ExternalSchematicInvalidSource()
        return (b"ok", b"ok")
    worker.render = render
    result = worker.find("fallback board")
    assert [choice.source_url for choice in result.choices] == [sources[0].source_url, sources[2].source_url]
    assert worker.find("fallback board", sources[2].source_url).source_url == sources[2].source_url


def test_empty_community_fallback_keeps_validation_failed_reason(service):
    worker, _, _, _ = service
    web = WebSchematicRef("https://example.org/schematic.pdf", "https://example.org/board",
                          "schematic.pdf", "pdf", "Board", "Publisher")
    worker.search = lambda query, limit: (web,)
    worker.inspect = lambda candidate, **kwargs: ()
    worker.fallback_search = lambda query, limit: ()
    with pytest.raises(ExternalSchematicNotFound) as error:
        worker.find("fallback board")
    assert error.value.reason == "validation_failed"


def test_public_choice_switch_keeps_all_verified_choices(service):
    worker, _, _, source = service
    refs = tuple(WebSchematicRef(f"https://example.org/{i}-schematic.png", "https://example.org/board",
                                f"{i}-schematic.png", "png", "Board", "Publisher") for i in range(2))
    worker.search = lambda query, limit: refs
    worker.inspect = lambda ref, **kwargs: (replace(source, repository="", commit="",
        source_url=ref.source_url, source_file=ref.source_file, root_schematic=ref.source_file,
        asset_kind="png", asset_paths=(), expected_sheets=1,
        source_type="public_web", evidence_grade=None, source_sha256="a" * 64),)
    worker.render = lambda source: (b"ok",)
    first = worker.find("public board")
    for ref in (refs[1], refs[0]):
        selected = worker.find("public board", ref.source_url)
        assert selected.source_url == ref.source_url
        assert selected.choices == first.choices


@pytest.mark.parametrize("source_type", ["manufacturer_official", "public_web"])
def test_diode_search_does_not_hide_verified_web_source_behind_repository_hits(service, monkeypatch, source_type):
    from backend.projects import external_circuit_search as search
    worker, _, _, source = service
    web = replace(_official_ref(), source_type=source_type,
                  title="SS33 diode application schematic", source_file="SS33-diode.pdf",
                  source_url="https://cdn.sparkfun.com/SS33-diode.pdf")
    repository = GitHubRepositoryRef("unrelated", "board", "https://github.com/unrelated/board")
    calls = Counter()
    monkeypatch.setattr(search, "search_component_repositories", lambda *args: (repository,))
    monkeypatch.setattr(search, "search_public_schematics", lambda *args: calls.update(public=1) or (web,))
    monkeypatch.setattr(search, "search_manufacturer_schematics", lambda *args: calls.update(manufacturer=1) or ())
    verified = replace(source, source_type=source_type, evidence_grade=2 if source_type == "manufacturer_official" else None,
                       expected_sheets=1, source_sha256="a" * 64, source_url=web.source_url)
    worker.search = api._search
    worker.inspect = lambda candidate, **kwargs: (verified,) if candidate is web else ()
    worker.render = lambda candidate: (b"verified",)
    result = worker.find("SS33 diode")
    assert result.source_url == web.source_url
    assert calls == {"public": 1, "manufacturer": 1}


@pytest.mark.parametrize("failure_kind", ["rate", "upstream"])
@pytest.mark.parametrize("partial", [False, True])
def test_render_failures_keep_retry_state_and_recover_after_deadline(service, failure_kind, partial):
    worker, _, clock, source = service
    refs = tuple(GitHubRepositoryRef("group", name, f"https://github.com/group/{name}")
                 for name in ("good", "delayed") if partial or name == "delayed")
    sources = {ref.repo: replace(source, repository=f"group/{ref.repo}", repository_url=ref.repository_url,
                               source_url=ref.repository_url + "/board.kicad_sch") for ref in refs}
    attempts = Counter()
    delay = 7 if failure_kind == "rate" else 60
    def search(query, limit):
        attempts["search"] += 1
        return refs
    def inspect(ref, **kwargs):
        attempts["inspect"] += 1
        return (sources[ref.repo],)
    def render(candidate):
        attempts[candidate.repository] += 1
        if candidate is sources["delayed"] and clock[0] < 1000 + delay:
            if failure_kind == "rate":
                raise ExternalSchematicRateLimited(delay)
            raise ExternalSchematicUpstreamError()
        return (b"one", b"two")
    worker.search, worker.inspect, worker.render = search, inspect, render
    expected_error = ExternalSchematicRateLimited if failure_kind == "rate" else ExternalSchematicUpstreamError
    if partial:
        result = worker.find("SS33 diode")
        assert [choice.source_url for choice in result.choices] == [sources["good"].source_url]
    else:
        with pytest.raises(expected_error):
            worker.find("SS33 diode")
    before = dict(attempts)
    assert worker._retry_deadline("ss33 diode") == 1000 + delay
    clock[0] += 1
    if partial:
        worker.find("SS33 diode", sources["good"].source_url)
    else:
        with pytest.raises(expected_error):
            worker.find("SS33 diode")
    assert worker._retry_deadline("ss33 diode") == 1000 + delay
    assert attempts == before
    clock[0] = 1000 + delay
    recovered = worker.find("SS33 diode")
    assert {choice.source_url for choice in recovered.choices} == {s.source_url for s in sources.values()}
    selected = worker.find("SS33 diode", sources["delayed"].source_url)
    assert selected.source_url == sources["delayed"].source_url
    assert attempts["search"] == 2
    assert attempts["inspect"] == len(refs) * 2


@pytest.mark.parametrize("provider_failure", [False, True])
def test_diode_web_failure_keeps_community_fallback(service, monkeypatch, provider_failure):
    from backend.projects import external_circuit_search as search
    worker, _, _, source = service
    web = replace(_official_ref(), title="SS33 diode schematic", source_file="SS33-diode.pdf")
    ref = GitHubRepositoryRef("group", "board", "https://github.com/group/board")
    calls = Counter()
    def public(*args):
        calls["public"] += 1
        if provider_failure:
            raise search.ExternalCircuitSearchError()
        return (web,)
    def manufacturer(*args):
        calls["manufacturer"] += 1
        if provider_failure:
            raise search.ExternalCircuitSearchError()
        return ()
    def repositories(*args):
        calls["component"] += 1
        return (ref,)
    monkeypatch.setattr(search, "search_public_schematics", public)
    monkeypatch.setattr(search, "search_manufacturer_schematics", manufacturer)
    monkeypatch.setattr(search, "search_component_repositories", repositories)
    worker.search, worker.fallback_search = api._search, api._search_community
    worker.inspect = lambda candidate, **kwargs: () if isinstance(candidate, WebSchematicRef) else (source,)
    result = worker.find("SS33 diode")
    assert result.source_type == "community"
    assert calls == {"public": 1, "manufacturer": 1, "component": 1}
