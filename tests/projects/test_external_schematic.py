"""공개 회로도 검색·시트 캐시와 다른 인스턴스에서의 원본 복구."""
import base64
import hmac
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, Lock

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
    from backend.projects import schematic_source
    monkeypatch.setenv("AUTH_SECRET", "unit-test-only-padding".ljust(32, "x"))
    counts = Counter()
    clock = [1000]
    monkeypatch.setattr(schematic_source, '_RATE_LIMITS', {})
    monkeypatch.setattr(schematic_source, '_rate_clock', lambda: clock[0])
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
    assert counts == {"search": 1, "inspect": MAX_COMPONENT_REPOSITORIES, "render": 1}
    cold = api.ExternalSchematicService(worker.search, worker.inspect, worker.render, wall=lambda: clock[0])
    assert cold.load(result.token, 0) == b"sheet0"
    assert counts == {"search": 1, "inspect": MAX_COMPONENT_REPOSITORIES, "render": 2}


def test_project_match_cache_and_token_are_bound_to_full_connections(service):
    worker,_,clock,_=service
    connections={'parts':[{'ref':'D1','value':'SS34','footprint':''}],
                 'nets':[{'nodes':[{'ref':'D1','pin':'1'}]}]}
    other={'parts':connections['parts'],'nets':[{'nodes':[{'ref':'D1','pin':'2'}]}]}
    calls=[]
    def matched(source,expected):
        calls.append(expected)
        if expected!=connections:raise ExternalSchematicInvalidSource()
        return (b'correct sheet',b'correct sheet2')
    worker.match_render=matched
    result=worker.find('custom project',connections=connections)
    assert worker.load(result.token,0,connections=connections)==b'correct sheet'
    with pytest.raises(ExternalSchematicNotFound):worker.find('custom project',connections=other)
    with pytest.raises(ExternalSchematicInvalidToken):worker.load(result.token,0,connections=other)
    with pytest.raises(ExternalSchematicInvalidToken):worker.load(result.token,0)
    unbound=worker.find('custom project')
    with pytest.raises(ExternalSchematicInvalidToken):worker.load(unbound.token,0,connections=connections)
    cold=api.ExternalSchematicService(worker.search,worker.inspect,worker.render,match_render=matched,wall=lambda:clock[0])
    assert cold.load(result.token,0,connections=connections)==b'correct sheet'
    assert len(calls)==3


@pytest.mark.parametrize('kind', ['pdf', 'png', 'svg'])
def test_project_original_never_accepts_a_web_document_without_connections(service, kind):
    worker, counts, _, _ = service
    worker.search = lambda *args: (WebSchematicRef(
        f'https://example.org/board-schematic.{kind}', 'https://example.org/board',
        f'board-schematic.{kind}', kind, 'Board schematic', 'Publisher'),)
    connections = {'parts': [{'ref': 'D1', 'value': 'SS34'}],
                   'nets': [{'nodes': [{'ref': 'D1', 'pin': '1'}]}]}
    with pytest.raises(ExternalSchematicNotFound) as error:
        worker.find('Board schematic', connections=connections)
    assert error.value.reason == 'circuit_mismatch'
    assert counts['inspect'] == counts['render'] == 0
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


def test_choices_preserve_verified_identity_and_provenance_for_llm_dialogue(service):
    worker, _, _, source = service
    sources = tuple(replace(
        source,
        repository=f"maker/board-{index}",
        repository_url=f"https://github.com/maker/board-{index}",
        source_url=f"https://github.com/maker/board-{index}/tree/{'a' * 40}",
        source_file=f"board-{index}.kicad_sch",
        root_schematic=f"board-{index}.kicad_sch",
        manufacturer=manufacturer,
        model="Same Board",
        revision=revision,
        source_type="manufacturer_official",
        source_sha256=str(index) * 64,
        license="MIT",
        attribution=f"{manufacturer} contributors",
    ) for index, (manufacturer, revision) in enumerate(
        (("Maker A", "Rev A"), ("Maker B", "Rev B")), start=1
    ))
    refs = tuple(WebSchematicRef(
        f"https://maker.example/board-{index}.pdf",
        f"https://maker.example/board-{index}",
        f"board-{index}.pdf", "pdf", "Same Board", "Maker"
    ) for index in (1, 2))
    worker.search = lambda query, limit: refs
    worker.inspect = lambda ref, **kwargs: (sources[refs.index(ref)],)
    worker.render = lambda candidate: (b"sheet", b"sheet")

    result = worker.find("same board")

    actual = {(choice.title, choice.manufacturer, choice.model, choice.revision,
               choice.source_file, choice.source_sha256, choice.commit,
               choice.license, choice.attribution, choice.repository_url)
              for choice in result.choices}
    assert actual == {
        ("Same Board · board-1.kicad_sch", "Maker A", "Same Board", "Rev A",
         "board-1.kicad_sch", "1" * 64, "c" * 40, "MIT", "Maker A contributors",
         "https://github.com/maker/board-1"),
        ("Same Board · board-2.kicad_sch", "Maker B", "Same Board", "Rev B",
         "board-2.kicad_sch", "2" * 64, "c" * 40, "MIT", "Maker B contributors",
         "https://github.com/maker/board-2"),
    }


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


def test_legacy_unbound_token_cannot_bypass_current_source_verification(service):
    worker, counts, _, source = service
    expires = 1500
    payload = [source.repository, source.commit, source.license, source.attribution,
               source.source_file, source.asset_kind, list(source.asset_paths),
               source.root_schematic, source.expected_sheets, expires]
    part = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.digest(api._key(), part, "sha256")).rstrip(b"=")
    token = (part + b"." + signature).decode()

    with pytest.raises(ExternalSchematicInvalidToken):
        worker.load(token, 0)
    assert counts["render"] == 0


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


@pytest.mark.parametrize('partial', [False, True])
def test_provider_limit_stops_candidates_and_blocks_reclick_until_original_deadline(service, partial):
    worker, counts, clock, source = service
    refs = tuple(GitHubRepositoryRef('group', str(i), f'https://github.com/group/{i}') for i in range(4))
    worker.search = lambda *args: counts.update(search=1) or refs
    inspected = []

    def inspect(ref, **kwargs):
        inspected.append(ref)
        if clock[0] < 4300 and (not partial or ref != refs[0]):
            raise ExternalSchematicRateLimited(3300, host='api.github.com', phase='github_api', status_code=403)
        return (source,)

    worker.inspect = inspect
    if partial:
        first = worker.find('SS33 diode')
    else:
        with pytest.raises(ExternalSchematicRateLimited):
            worker.find('SS33 diode')
    assert inspected == list(refs[:2 if partial else 1])
    for advance in (1, 901, 1000):
        clock[0] = 1000 + advance
        if partial and advance == 1:
            assert worker.find('SS33 diode', first.source_url).source_url == first.source_url
        else:
            with pytest.raises(ExternalSchematicRateLimited) as error:
                worker.find('SS33 diode')
            assert error.value.retry_after == 3300 - advance
        assert counts['search'] == 1
        assert len(inspected) == (2 if partial else 1)
        assert worker._retry_deadline('ss33 diode') == 4300
    clock[0] = 4300
    assert worker.find('SS33 diode').sheet_count == 2
    assert counts['search'] == 2
    assert len(inspected) == (2 if partial else 1) + len(refs)


def test_rate_limited_web_provider_skips_its_next_candidate_but_keeps_other_provider(service):
    worker, _, _, source = service
    refs = tuple(replace(_official_ref(), source_url=f'https://{host}/{i}.pdf')
                 for i, host in enumerate(('blocked.example', 'blocked.example', 'good.example')))
    worker.search = lambda *args: refs
    inspected = []

    def inspect(ref, **kwargs):
        inspected.append(ref)
        if ref == refs[0]:
            raise ExternalSchematicRateLimited(60, host='blocked.example', phase='public_asset', status_code=429)
        return (replace(source, source_type='manufacturer_official', evidence_grade=2,
                        source_url=ref.source_url, asset_kind='pdf', source_sha256='a' * 64),)

    worker.inspect = inspect
    worker.render = lambda source: (b'one', b'two')
    assert worker.find('SS33 diode').source_url == refs[2].source_url
    assert inspected == [refs[0], refs[2]]


def test_query_rate_limit_does_not_block_a_new_github_credential(service, monkeypatch):
    import os
    worker, _, _, source = service
    ref = GitHubRepositoryRef('group', 'board', 'https://github.com/group/board')
    worker.search = lambda *args: (ref,)

    def inspect(*args, **kwargs):
        if os.getenv('GITHUB_TOKEN') == 'first-fixture-token':
            raise ExternalSchematicRateLimited(60, host='api.github.com', phase='github_api', status_code=403)
        return (source,)

    worker.inspect = inspect
    monkeypatch.setenv('GITHUB_TOKEN', 'first-fixture-token')
    with pytest.raises(ExternalSchematicRateLimited):
        worker.find('SS33 diode')
    monkeypatch.setenv('GITHUB_TOKEN', 'second-fixture-token')
    assert worker.find('SS33 diode').sheet_count == 2


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


def test_direct_public_pdf_gets_one_bounded_publication_search(monkeypatch):
    from backend.projects import external_circuit_search as search
    direct=replace(_official_ref(),source_url='https://example.org/schematic.pdf',page_url='https://example.org/schematic.pdf',source_type='public_web',evidence_grade=None)
    linked=replace(direct,page_url='https://example.org/project')
    calls=[]
    monkeypatch.setattr(search,'search_public_schematics',lambda *a:(direct,))
    monkeypatch.setattr(search,'search_manufacturer_schematics',lambda *a:())
    monkeypatch.setattr(search,'_search_public_schematics',lambda *a,**kw:calls.append(kw['search_text']) or (linked,))
    assert api._search('555 Theremin',5)==(linked,)
    assert len(calls)==1 and 'project' in calls[0]
    calls.clear()
    assert api._search('Teensy 4.0',5)==(direct,)
    assert calls==[]


def _official_ref():
    return WebSchematicRef(
        source_url="https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro_Micro_v13b.pdf",
        page_url="https://learn.sparkfun.com/tutorials/pro-micro--fio-v3-hookup-guide",
        source_file="Pro_Micro_v13b.pdf", asset_kind="pdf", title="SparkFun Pro Micro v13",
        attribution="SparkFun Electronics", source_type="manufacturer_official",
        evidence_grade=2, manufacturer="SparkFun Electronics", model="SparkFun Pro Micro v13",
        revision="v13b", license="CC-BY-4.0",
    )


@pytest.mark.parametrize('mirror_hash,with_original,expected', [
    ('b' * 64, True, 1), ('a' * 64, True, 2), ('b' * 64, False, 0),
])
def test_mislabelled_public_bytes_need_a_rendered_original(service, mirror_hash, with_original, expected):
    worker, _, _, source = service
    official = replace(source, repository='', commit='', source_file='schematic.png', root_schematic='schematic.png',
        asset_kind='png', asset_paths=(), expected_sheets=1, source_type='manufacturer_official', evidence_grade=2,
        source_url='https://www.pjrc.com/teensy/schematic40.png', source_sha256='a' * 64, model='Teensy 4.0')
    renamed = replace(official, source_type='public_web', evidence_grade=None,
        source_url='https://example.org/schematic.png', source_sha256=mirror_hash, model='Wrong project title')
    sources = (official, renamed) if with_original else (renamed,)
    refs = tuple(replace(_official_ref(), source_url=s.source_url, source_type=s.source_type) for s in sources)
    worker.search = lambda *a: refs
    worker.inspect = lambda candidate, **kw: (sources[refs.index(candidate)],)
    worker.render = lambda s: (b'rendered bytes',)
    if expected:
        result = worker.find('Teensy 4.0')
        assert len(result.choices) == expected
        assert (renamed.source_url in [c.source_url for c in result.choices]) == (mirror_hash == 'a' * 64)
        if expected == 2:
            assert worker.find('Teensy 4.0', renamed.source_url).model == official.model
    else:
        with pytest.raises(ExternalSchematicNotFound):
            worker.find('Teensy 4.0')


def test_community_preview_cannot_replace_eda_render(service):
    worker, _, _, source = service
    preview = replace(source, asset_kind='png', asset_paths=('schematic.png',))
    worker.inspect = lambda *a, **kw: (preview, source)
    rendered = []
    worker.render = lambda s: rendered.append(s.asset_kind) or (b'EDA sheet', b'EDA sheet2')
    assert worker.find('custom project').source_type == 'community'
    assert rendered == ['kicad']


@pytest.mark.parametrize('query,kind,proof,accepted', [
    ('555 Theremin','pdf',('a'*64,1),True),
    ('Teensy 4.0','pdf',None,False),
    ('555 Theremin','png',None,False),
    ('555 Theremin','pdf',('b'*64,1),False),
    ('555 Theremin','pdf',('a'*64,2),False),
])
def test_unanchored_pdf_requires_publication_proof_without_board_or_image_bypass(service,query,kind,proof,accepted):
    worker,_,_,source=service
    ref=replace(_official_ref(),source_url='https://example.org/schematic.'+kind,source_type='public_web',evidence_grade=None,asset_kind=kind)
    public=replace(source,repository='',commit='',source_type='public_web',evidence_grade=None,asset_kind=kind,
        source_url=ref.source_url,source_file='schematic.'+kind,root_schematic='schematic.'+kind,
        source_sha256='a'*64,expected_sheets=1,asset_paths=(),model='Wrong search title')
    calls=[]
    worker.search=lambda *a:(ref,)
    worker.inspect=lambda *a,**kw:(public,)
    worker.render=lambda s:(b'verified image',)
    worker.public_pdf_inspect=lambda source,**kw:calls.append(kw['query']) or proof
    if accepted:
        result=worker.find(query)
        assert result.source_type=='public_web' and result.evidence_grade is None
        assert result.model==query.casefold()
        assert worker.find(query,ref.source_url).source_url==ref.source_url
    else:
        with pytest.raises(ExternalSchematicNotFound):worker.find(query)
    assert calls==([] if proof is None else [query.casefold()])


def test_publication_verification_preserves_rate_limit(service):
    worker,_,_,source=service
    ref=replace(_official_ref(),source_type='public_web',evidence_grade=None)
    worker.search=lambda *a:(ref,)
    worker.inspect=lambda *a,**kw:(replace(source,source_type='public_web',evidence_grade=None,
        asset_kind='pdf',expected_sheets=1,source_sha256='a'*64),)
    def limited(*a,**kw):raise ExternalSchematicRateLimited(77)
    worker.public_pdf_inspect=limited
    with pytest.raises(ExternalSchematicRateLimited) as error:worker.find('555 Theremin')
    assert error.value.retry_after==77


def test_unrenderable_original_cannot_vouch_for_a_public_copy(service):
    worker, _, _, source = service
    refs=(replace(_official_ref(),source_url='https://example.org/original.pdf'),
          replace(_official_ref(),source_url='https://example.org/mirror.pdf',source_type='public_web'))
    worker.search=lambda *a: refs
    worker.inspect=lambda ref, **kw: (replace(source,source_type=ref.source_type,
        evidence_grade=2 if ref==refs[0] else None,asset_kind='pdf',asset_paths=(),
        source_file='schematic.pdf',root_schematic='schematic.pdf',expected_sheets=1,
        source_url=ref.source_url,source_sha256='a'*64),)
    def render(ref):
        if ref.source_type=='manufacturer_official':
            raise ExternalSchematicInvalidSource()
        pytest.fail('untrusted copy was rendered')
    worker.render=render
    with pytest.raises(ExternalSchematicNotFound):
        worker.find('Teensy 4.0')


def test_old_policy_token_cannot_bypass_reference_verification(service):
    import base64, json, hmac
    worker, counts, _, _ = service
    token = worker.find('custom project').token
    payload = json.loads(base64.urlsafe_b64decode(token.split('.')[0]+'=='))
    payload['version'] = 2
    part = api._encode(json.dumps(payload, separators=(',', ':')).encode())
    old = (part+b'.'+api._encode(hmac.digest(api._key(), part, 'sha256'))).decode()
    previous = counts['render']
    with pytest.raises(ExternalSchematicInvalidToken):
        worker.load(old, 0)
    assert counts['render'] == previous


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
    original = replace(public, source_type='manufacturer_official', evidence_grade=2,
                       source_url='https://www.pjrc.com/schematic.png')
    refs = (replace(_official_ref(), source_url=original.source_url), replace(_official_ref(), source_url=public.source_url))
    worker.search = lambda query, limit: refs
    worker.inspect = lambda candidate, **kwargs: (original if candidate == refs[0] else public,)
    worker.render = lambda candidate: (b"verified",)
    result = worker.find("board schematic", public.source_url)
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
                        source_type="manufacturer_official" if candidate == refs[0] else "public_web",
                        evidence_grade=2 if candidate == refs[0] else None, source_sha256="a" * 64),)

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
        source_type="manufacturer_official" if candidate == refs[0] else "public_web",
        evidence_grade=2 if candidate == refs[0] else None, source_sha256="a" * 64),)
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
    monkeypatch.setattr(search, 'search_semiconductor_schematics', lambda *args: ())
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
        source_type="manufacturer_official", evidence_grade=2, source_sha256="a" * 64),)
    worker.render = lambda source: (b"ok",)
    first = worker.find("public board")
    for ref in (refs[1], refs[0]):
        selected = worker.find("public board", ref.source_url)
        assert selected.source_url == ref.source_url
        assert selected.choices == first.choices


@pytest.mark.parametrize("source_type", ["manufacturer_official", "public_web"])
def test_diode_search_does_not_hide_verified_web_source_behind_repository_hits(service, monkeypatch, source_type):
    from backend.projects import external_circuit_search as search
    monkeypatch.setattr(search, 'search_semiconductor_schematics', lambda *args: ())
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
                       expected_sheets=1, source_sha256="a" * 64, source_url=web.source_url,
                       asset_kind='pdf', asset_paths=(), source_file=web.source_file, root_schematic=web.source_file)
    worker.search = api._search
    worker.inspect = lambda candidate, **kwargs: (verified,) if candidate is web else ()
    worker.render = lambda candidate: (b"verified",)
    if source_type == 'public_web':
        worker.public_pdf_inspect = lambda *args, **kwargs: ('a' * 64, 1)
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
    monkeypatch.setattr(search, 'search_semiconductor_schematics', lambda *args: ())
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


@pytest.mark.parametrize('render_fails',[False,True])
def test_bare_tsc_query_isolated_from_old_github_cache_and_never_falls_back(service,render_fails):
    from backend.projects.schematic_source import provider_rate_key
    worker,counts,clock,src=service
    bare='ts19371cx6'
    worker.queries.get(bare,lambda:api._SearchFailure('validation_failed'))
    worker.candidates.get(bare,lambda:(GitHubRepositoryRef('old','unrelated','https://github.com/old/unrelated'),))
    worker.retry_until[bare]=(clock[0]+600,('api.github.com','github_api',403,provider_rate_key('api.github.com')))
    url='https://services.taiwansemi.com/storage/resources/datasheet/TS19371CX6_J1708.pdf'
    source=replace(src,repository='',commit='',source_type='manufacturer_official',evidence_grade=2,
        repository_url=url,source_url=url,source_file='TS19371CX6_J1708.pdf',asset_kind='pdf',
        asset_paths=(),root_schematic='TS19371CX6_J1708.pdf',source_sha256='d'*64,model='TS19371CX6')
    ref=WebSchematicRef(url,url,source.source_file,'pdf','TSC application','Taiwan Semiconductor',
        source_type='manufacturer_official',evidence_grade=2,model=source.model)
    def search(q,limit):
        assert q=='tsc ts19371cx6'
        return (ref,)
    worker.search=search
    worker.inspect=lambda *args,**kwargs:(source,)
    def render(source):
        counts['bare_render'] += 1
        if render_fails:raise ExternalSchematicInvalidSource()
        return (b'sheet0',b'sheet1')
    worker.render=render
    worker.fallback_search=lambda *args:pytest.fail('TSC validation failure must not fall back to GitHub')
    if render_fails:
        with pytest.raises(ExternalSchematicNotFound):worker.find('TS19371CX6')
    else:
        assert worker.find('TS19371CX6').source_url==url
        assert worker.find('TSC TS19371CX6').source_url==url
    assert counts['bare_render'] == 1


@pytest.mark.parametrize('query', [
    'TI TIDA-010197', 'ST NUCLEO MB1136', 'Analog Devices DC368B',
    'onsemi NSVR351SDSA3 diode', 'Infineon BAT62-02V diode', 'Vishay SiC diode PFC',
])
def test_named_semiconductor_search_uses_only_official_provider(monkeypatch, query):
    from backend.projects import external_circuit_search as search
    ref = _official_ref()
    seen = []
    def official(q, limit):
        seen.append((q, limit))
        return (ref,)
    monkeypatch.setattr(search, 'search_semiconductor_schematics', official, raising=False)
    monkeypatch.setattr(search, 'search_public_schematics', lambda *a: pytest.fail('named manufacturer must stay official'))
    monkeypatch.setattr(search, 'search_component_repositories', lambda *a: pytest.fail('named manufacturer must not use GitHub'))
    assert api._search(query, 5) == (ref,)
    assert seen == [(query, 5)]


def test_rejected_official_semiconductor_never_falls_back_to_unrelated_github(service):
    worker, _, _, _ = service
    worker.search = lambda *a: (_official_ref(),)
    worker.inspect = lambda *a, **kw: ()
    worker.fallback_search = lambda *a: pytest.fail('official validation failure must stay a failure')
    with pytest.raises(ExternalSchematicNotFound):
        worker.find('NSVR351SDSA3 onsemi diode')


@pytest.mark.parametrize('selected', [False, True])
def test_bare_part_never_selects_first_manufacturer_even_with_explicit_source(service,selected):
    worker,counts,_,source=service
    refs=tuple(replace(_official_ref(),source_url=url,page_url=url,manufacturer=maker)
               for url,maker in [('https://www.ti.com/lit/ds/symlink/lm2596.pdf','Texas Instruments'),
                                ('https://www.onsemi.com/pdf/datasheet/lm2596-d.pdf','onsemi')])
    sources={ref:replace(source,repository='',commit='',source_url=ref.source_url,repository_url=ref.page_url,
                        asset_kind='pdf',asset_paths=(),expected_sheets=1,source_type='manufacturer_official',
                        evidence_grade=2,manufacturer=ref.manufacturer,model='LM2596',source_sha256='a'*64) for ref in refs}
    worker.search=lambda *a:counts.update(search_bare=1) or refs
    worker.inspect=lambda candidate,**kw:(sources[candidate],)
    worker.render=lambda s:(b'verified',)
    worker.fallback_search=lambda *a:pytest.fail('ambiguity must not fall back')
    for _ in range(2):
        with pytest.raises(ExternalSchematicNotFound) as error:
            worker.find('LM2596',refs[0].source_url if selected else None)
        assert error.value.reason=='ambiguous_manufacturer'
    assert counts['search_bare']==1


def test_bare_part_does_not_treat_other_manufacturer_failure_as_unique(service):
    worker,_,_,source=service
    refs=tuple(replace(_official_ref(),source_url=url,page_url=url,manufacturer=maker)
               for url,maker in [('https://www.ti.com/lit/ds/symlink/lm2596.pdf','Texas Instruments'),
                                ('https://www.onsemi.com/pdf/datasheet/lm2596-d.pdf','onsemi')])
    official=replace(source,repository='',commit='',source_url=refs[0].source_url,asset_kind='pdf',asset_paths=(),
                     expected_sheets=1,source_type='manufacturer_official',evidence_grade=2,
                     manufacturer='Texas Instruments',source_sha256='a'*64)
    worker.search=lambda *a:refs
    def inspect(candidate,**kw):
        if candidate==refs[1]:raise ExternalSchematicUpstreamError()
        return (official,)
    worker.inspect=inspect
    worker.render=lambda s:(b'verified',)
    with pytest.raises(ExternalSchematicUpstreamError):worker.find('LM2596')


def test_bare_part_ambiguity_includes_sixth_official_manufacturer(service):
    worker,_,_,source=service
    urls=['https://www.ti.com/lm2596.pdf','https://www.st.com/lm2596.pdf',
          'https://www.analog.com/lm2596.pdf','https://www.onsemi.com/lm2596.pdf',
          'https://www.infineon.com/lm2596.pdf','https://www.vishay.com/lm2596.pdf']
    refs=tuple(replace(_official_ref(),source_url=url,page_url=url) for url in urls)
    worker.search=lambda *a:refs
    def inspect(ref,**kw):
        if ref not in (refs[0],refs[5]):return ()
        return (replace(source,repository='',commit='',source_url=ref.source_url,asset_kind='pdf',asset_paths=(),
                        expected_sheets=1,source_type='manufacturer_official',evidence_grade=2,
                        source_sha256='a'*64),)
    worker.inspect=inspect;worker.render=lambda s:(b'verified',)
    with pytest.raises(ExternalSchematicNotFound) as error:worker.find('LM2596')
    assert error.value.reason=='ambiguous_manufacturer'


def test_bare_part_invalid_application_note_gets_one_official_datasheet_search(service):
    worker,counts,_,source=service
    note=replace(_official_ref(),source_url='https://www.st.com/resource/en/application_note/an290.pdf')
    data=replace(_official_ref(),source_url='https://www.st.com/resource/en/datasheet/l78.pdf')
    official=replace(source,repository='',commit='',source_url=data.source_url,asset_kind='pdf',asset_paths=(),
                     expected_sheets=1,source_type='manufacturer_official',evidence_grade=2,
                     manufacturer='STMicroelectronics',source_sha256='a'*64)
    worker.search=lambda *a:(note,)
    worker.official_search=lambda q,limit:counts.update(datasheet_search=1) or (data,)
    worker.inspect=lambda ref,**kw:(official,) if ref==data else ()
    worker.render=lambda s:(b'verified',)
    worker.fallback_search=lambda *a:pytest.fail('official retry must not use GitHub')
    assert worker.find('L7805').source_url==data.source_url
    assert worker.find('L7805').source_url==data.source_url
    assert counts['datasheet_search']==1


def test_first_official_pdf_request_downloads_and_inspects_once(monkeypatch, caplog):
    """A fake PDF/HTTP boundary exercises the current first-request pipeline only."""
    from backend.projects import schematic_render as render
    monkeypatch.setenv('AUTH_SECRET','pdf-request-test-padding'.ljust(32,'x'))
    url='https://www.ti.com/lit/ds/symlink/lm2596.pdf'
    ref=WebSchematicRef(url,url,'lm2596.pdf','pdf','LM2596','Texas Instruments',
                        source_type='manufacturer_official',evidence_grade=2,manufacturer='Texas Instruments')
    calls=Counter();data=b'%PDF-DO_NOT_LOG_OR_SIGN_THESE_BYTES'
    def download(*args,**kwargs):calls.update(download=1);return data,'application/pdf'
    def inspect(*args,**kwargs):calls.update(inspect=1);return (0,2)
    def convert(kind,path,output,*,pdf_pages):
        assert path.read_bytes()==data and pdf_pages==(0,2)
        calls.update(convert=1);return (b'png-one',b'png-two')
    monkeypatch.setattr(render,'_public_asset',download)
    monkeypatch.setattr(render,'_bounded_official_pdf_schematic_pages',inspect)
    monkeypatch.setattr(render,'_sheets',convert)
    worker=api.ExternalSchematicService(lambda *a:(ref,),api._inspect,api._render)
    with caplog.at_level('INFO'):
        result=worker.find('TI LM2596 datasheet')
    assert result.sheet_count==2
    assert calls=={'download':1,'inspect':1,'convert':1}
    payload=base64.urlsafe_b64decode(result.token.split('.')[0]+'==').decode()
    assert 'DO_NOT_LOG_OR_SIGN' not in payload
    assert 'DO_NOT_LOG_OR_SIGN' not in str([vars(record) for record in caplog.records])


def test_pdf_reuse_does_not_cross_new_requests(monkeypatch):
    from backend.projects import schematic_render as render
    monkeypatch.setenv('AUTH_SECRET','pdf-request-test-padding'.ljust(32,'x'))
    url='https://www.ti.com/lit/ds/symlink/lm2596.pdf'
    ref=WebSchematicRef(url,url,'lm2596.pdf','pdf','LM2596','Texas Instruments',
                        source_type='manufacturer_official',evidence_grade=2,manufacturer='Texas Instruments')
    calls=Counter();data=b'%PDF-request-local-only'
    def download(*args,**kwargs):calls.update(download=1);return data,'application/pdf'
    def inspect(*args,**kwargs):calls.update(inspect=1);return (0,)
    monkeypatch.setattr(render,'_public_asset',download)
    monkeypatch.setattr(render,'_bounded_official_pdf_schematic_pages',inspect)
    monkeypatch.setattr(render,'_sheets',lambda *a,**kw:(b'png',))
    for _ in range(2):
        worker=api.ExternalSchematicService(lambda *a:(ref,),api._inspect,api._render)
        assert worker.find('TI LM2596').sheet_count==1
    assert calls=={'download':2,'inspect':2}


def test_concurrent_pdf_requests_keep_checked_bytes_separate(monkeypatch):
    from threading import Barrier
    from backend.projects import schematic_render as render
    monkeypatch.setenv('AUTH_SECRET','pdf-request-test-padding'.ljust(32,'x'))
    barrier=Barrier(2);downloads=Counter()
    urls=[f'https://www.ti.com/lit/ds/symlink/lm2596-{suffix}.pdf' for suffix in ['a','b']]
    data={url:f'%PDF-{i}'.encode() for i,url in enumerate(urls)}
    def download(url,*a,**kw):downloads[url]+=1;return data[url],'application/pdf'
    monkeypatch.setattr(render,'_public_asset',download)
    monkeypatch.setattr(render,'_bounded_official_pdf_schematic_pages',lambda *a:(0,))
    monkeypatch.setattr(render,'_sheets',lambda kind,path,*a,**kw:(path.read_bytes(),))
    def run(url):
        ref=WebSchematicRef(url,url,url.rsplit('/',1)[-1],'pdf','LM2596','Texas Instruments',
                           source_type='manufacturer_official',evidence_grade=2,manufacturer='Texas Instruments')
        def inspect(ref,**kw):
            result=api._inspect(ref,**kw);barrier.wait(timeout=5);return result
        worker=api.ExternalSchematicService(lambda *a:(ref,),inspect,api._render)
        result=worker.find('TI LM2596')
        assert worker.load(result.token,0)==data[url]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run,urls))
    assert downloads=={url:1 for url in urls}


def test_first_request_inspects_two_official_pdf_candidates_in_parallel(monkeypatch):
    """첫 요청에서도 연속된 공식 PDF 후보 두 개의 검사 슬롯을 동시에 사용한다."""
    from backend.projects import schematic_render as render

    monkeypatch.setenv('AUTH_SECRET', 'pdf-parallel-test-padding'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        url, url, f'{maker.lower()}.pdf', 'pdf', 'LM2596', maker,
        source_type='manufacturer_official', evidence_grade=2, manufacturer=maker,
    ) for maker, url in (
        ('Texas Instruments', 'https://www.ti.com/lit/ds/symlink/lm2596.pdf'),
        ('STMicroelectronics', 'https://www.st.com/resource/en/datasheet/lm2596.pdf'),
    ))
    active = 0
    peak = 0
    lock = Lock()

    def inspect(candidate, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            # 순차 구현에서는 이 지연 동안 다음 후보가 시작되지 않는다.
            time.sleep(0.12)
            return (VerifiedSchematicSource(
                '', '', '미확인', candidate.manufacturer, candidate.source_url,
                candidate.source_url, candidate.source_file, 'pdf', (),
                candidate.source_file, 1, 'manufacturer_official', 2,
                candidate.manufacturer, 'LM2596', source_sha256='a' * 64,
            ),)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(render, '_sheets', lambda *args, **kwargs: (b'png',))
    worker = api.ExternalSchematicService(lambda query, limit: refs, inspect, lambda source: (b'png',))

    with pytest.raises(ExternalSchematicNotFound) as error:
        worker.find('LM2596')

    assert error.value.reason == 'ambiguous_manufacturer'
    assert peak == 2


def test_parallel_inspection_keeps_candidate_order_and_selected_pdf_bytes(monkeypatch):
    """후보 2가 먼저 끝나도 후보 1을 선택하고 각 원문 바이트를 유지한다."""
    from backend.projects import schematic_render as render

    monkeypatch.setenv('AUTH_SECRET', 'pdf-parallel-order-test'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        url, url, f'lm2596-{index}.pdf', 'pdf', 'LM2596', 'Texas Instruments',
        source_type='manufacturer_official', evidence_grade=2,
        manufacturer='Texas Instruments',
    ) for index, url in enumerate((
        'https://www.ti.com/lit/ds/symlink/lm2596-first.pdf',
        'https://www.ti.com/lit/ds/symlink/lm2596-second.pdf',
    ), 1))
    completion = []
    rendered = []

    def inspect(candidate, **kwargs):
        if candidate is refs[0]:
            time.sleep(0.08)
        completion.append(candidate.source_url)
        return (VerifiedSchematicSource(
            '', '', '미확인', candidate.manufacturer, candidate.source_url,
            candidate.source_url, candidate.source_file, 'pdf', (),
            candidate.source_file, 1, 'manufacturer_official', 2,
            candidate.manufacturer, 'LM2596',
            source_sha256=('1' if candidate is refs[0] else '2') * 64,
        ),)

    def render_source(source):
        payload = b'first-pdf' if source.source_url == refs[0].source_url else b'second-pdf'
        rendered.append((source.source_url, payload))
        return (payload,)

    monkeypatch.setattr(render, '_sheets', lambda *args, **kwargs: (b'png',))
    worker = api.ExternalSchematicService(lambda query, limit: refs, inspect, render_source)
    result = worker.find('TI LM2596')

    assert completion == [refs[1].source_url, refs[0].source_url]
    assert [url for url, _ in rendered] == [refs[0].source_url, refs[1].source_url]
    assert result.source_url == refs[0].source_url


def test_parallel_real_pdf_boundary_keeps_each_checked_bytes_for_conversion(monkeypatch):
    """실제 inspect/render 진입점에서도 병렬 후보별 PDF 바이트와 1회 재사용을 분리한다."""
    from backend.projects import schematic_render as render

    monkeypatch.setenv('AUTH_SECRET', 'pdf-parallel-bytes-test'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        url, url, f'lm2596-{suffix}.pdf', 'pdf', 'LM2596', 'Texas Instruments',
        source_type='manufacturer_official', evidence_grade=2,
        manufacturer='Texas Instruments',
    ) for suffix, url in (
        ('a', 'https://www.ti.com/lit/ds/symlink/lm2596-a.pdf'),
        ('b', 'https://www.ti.com/lit/ds/symlink/lm2596-b.pdf'),
    ))
    payloads = {refs[0].source_url: b'%PDF-A', refs[1].source_url: b'%PDF-B'}
    downloads = Counter()
    converted = []

    # _public_asset does not receive the source URL in _sheets, so retain the
    # downloaded bytes in the temporary PDF path and verify those exact bytes.
    def download(url, *args, **kwargs):
        downloads[url] += 1
        return payloads[url], 'application/pdf'

    def pages(data, query, manufacturer, *args):
        return (0,)

    def sheets(kind, path, output, *, pdf_pages):
        converted.append(path.read_bytes())
        return (b'png',)

    monkeypatch.setattr(render, '_public_asset', download)
    monkeypatch.setattr(render, '_bounded_official_pdf_schematic_pages', pages)
    monkeypatch.setattr(render, '_sheets', sheets)
    worker = api.ExternalSchematicService(lambda query, limit: refs, api._inspect, api._render)

    result = worker.find('TI LM2596')

    assert result.source_url == refs[0].source_url
    assert downloads == Counter({refs[0].source_url: 1, refs[1].source_url: 1})
    assert converted == [payloads[refs[0].source_url], payloads[refs[1].source_url]]


def test_four_official_pdf_candidates_use_no_more_than_two_inspection_slots(monkeypatch):
    """후보가 네 개여도 한 요청의 PDF 다운로드·검사 동시성은 2로 제한한다."""
    monkeypatch.setenv('AUTH_SECRET', 'pdf-parallel-four-test'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        f'https://www.{maker}.com/lm2596.pdf', f'https://www.{maker}.com/lm2596.pdf',
        f'{maker}.pdf', 'pdf', 'LM2596', maker,
        source_type='manufacturer_official', evidence_grade=2, manufacturer=maker,
    ) for maker in ('ti', 'st', 'onsemi', 'infineon'))
    active = 0
    peak = 0
    lock = Lock()

    def inspect(candidate, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.05)
            return (VerifiedSchematicSource(
                '', '', '미확인', candidate.manufacturer, candidate.source_url,
                candidate.source_url, candidate.source_file, 'pdf', (),
                candidate.source_file, 1, 'manufacturer_official', 2,
                candidate.manufacturer, 'LM2596', source_sha256='a' * 64,
            ),)
        finally:
            with lock:
                active -= 1

    worker = api.ExternalSchematicService(lambda query, limit: refs, inspect,
                                          lambda source: (b'png',))
    with pytest.raises(ExternalSchematicNotFound) as error:
        worker.find('LM2596')

    assert error.value.reason == 'ambiguous_manufacturer'
    assert peak == 2


def test_parallel_inspection_shares_one_upstream_retry_budget(monkeypatch):
    """두 병렬 검사 모두 실패해도 요청 전체의 검사 재시도는 한 번만 허용한다."""
    monkeypatch.setenv('AUTH_SECRET', 'pdf-parallel-retry-test'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        url, url, 'lm2596.pdf', 'pdf', 'LM2596', maker,
        source_type='manufacturer_official', evidence_grade=2, manufacturer=maker,
    ) for maker, url in (
        ('Texas Instruments', 'https://www.ti.com/lm2596.pdf'),
        ('STMicroelectronics', 'https://www.st.com/lm2596.pdf'),
    ))
    calls = Counter()

    def inspect(candidate, **kwargs):
        calls[candidate.source_url] += 1
        raise ExternalSchematicUpstreamError()

    worker = api.ExternalSchematicService(lambda query, limit: refs, inspect,
                                          lambda source: (b'png',))
    with pytest.raises(ExternalSchematicUpstreamError):
        worker.find('LM2596')

    assert sum(calls.values()) == 3
    assert all(value >= 1 for value in calls.values())


def test_parallel_requests_share_process_pdf_inspection_cap(monkeypatch):
    """서로 다른 두 요청의 공식 PDF 검사도 프로세스 전체 peak 2를 넘지 않는다."""
    from backend.projects import schematic_render as render

    monkeypatch.setenv('AUTH_SECRET', 'pdf-global-cap-test'.ljust(32, 'x'))
    groups = []
    for group in ('a', 'b'):
        groups.append(tuple(WebSchematicRef(
            f'https://www.ti.com/lit/ds/symlink/lm2596-{group}-{suffix}.pdf',
            f'https://www.ti.com/lit/ds/symlink/lm2596-{group}-{suffix}.pdf',
            f'lm2596-{group}-{suffix}.pdf', 'pdf', 'LM2596', 'Texas Instruments',
            source_type='manufacturer_official', evidence_grade=2,
            manufacturer='Texas Instruments',
        ) for suffix in ('a', 'b')))
    payloads = {ref.source_url: f'%PDF-{ref.source_url[-6:]}'.encode()
                for refs in groups for ref in refs}
    active = 0
    peak = 0
    lock = Lock()

    def download(url, *args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.06)
            return payloads[url], 'application/pdf'
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(render, '_public_asset', download)
    monkeypatch.setattr(render, '_bounded_official_pdf_schematic_pages', lambda *args: (0,))
    monkeypatch.setattr(render, '_sheets', lambda *args, **kwargs: (b'png',))

    def run(refs):
        worker = api.ExternalSchematicService(lambda query, limit: refs, api._inspect, api._render)
        return worker.find('TI LM2596').source_url

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, groups))

    assert results == [groups[0][0].source_url, groups[1][0].source_url]
    assert peak == 2


def test_parallel_worker_error_waits_for_sibling_and_clears_request_state(monkeypatch):
    """한 worker가 실패해도 sibling join 후 ContextVar와 준비 원문을 정리한다."""
    from backend.projects import schematic_render as render

    monkeypatch.setenv('AUTH_SECRET', 'pdf-worker-cleanup-test'.ljust(32, 'x'))
    refs = tuple(WebSchematicRef(
        url, url, 'lm2596.pdf', 'pdf', 'LM2596', maker,
        source_type='manufacturer_official', evidence_grade=2, manufacturer=maker,
    ) for maker, url in (
        ('Texas Instruments', 'https://www.ti.com/lm2596-error.pdf'),
        ('STMicroelectronics', 'https://www.st.com/lm2596-sibling.pdf'),
    ))
    sibling_done = Event()
    state_ref = []

    def inspect(candidate, **kwargs):
        state = render._PDF_REQUEST.get()
        state_ref.append(state)
        if candidate is refs[0]:
            assert sibling_done.wait(timeout=1)
            raise RuntimeError('synthetic inspection error')
        state['prepared'].append(object())
        sibling_done.set()
        return ()

    worker = api.ExternalSchematicService(lambda query, limit: refs, inspect,
                                          lambda source: (b'png',))
    with pytest.raises(RuntimeError, match='synthetic inspection error'):
        worker.find('LM2596')

    assert sibling_done.is_set()
    assert state_ref and all(state == {} for state in state_ref)
    assert render._PDF_REQUEST.get() is None
