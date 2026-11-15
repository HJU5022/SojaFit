"""저장소·계층 구조·이미지 연결·네트워크 상한을 격리된 HTTP 응답으로 검사한다."""
import httpx
import pytest
import socket

from backend.projects.external_circuit_search import GitHubRepositoryRef
from backend.projects import schematic_discovery as discovery
from backend.projects.schematic_discovery import download_bounded, inspect_github_candidates, inspect_github_repository
from backend.projects.schematic_source import ALLOWED_LICENSES, ExternalSchematicInvalidSource, ExternalSchematicRateLimited

REF = GitHubRepositoryRef("o", "r", "https://github.com/o/r")
SHA, TREE = "a" * 40, "b" * 40
API = "https://api.github.com/repos/o/r"
RAW = f"https://raw.githubusercontent.com/o/r/{SHA}/"


@pytest.fixture(autouse=True)
def isolated_provider_limits(monkeypatch):
    from backend.projects import schematic_source
    monkeypatch.setattr(schematic_source, '_RATE_LIMITS', {})


@pytest.mark.parametrize('status', [403, 429])
def test_provider_cooldown_blocks_other_urls_but_keeps_hosts_and_credentials_separate(monkeypatch, status):
    from backend.projects import schematic_source
    clock = [1000.0]
    monkeypatch.setattr(schematic_source, '_rate_clock', lambda: clock[0])
    monkeypatch.setenv('GITHUB_TOKEN', 'first-fixture-token')
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(status, headers={'retry-after': '10', 'x-ratelimit-remaining': '0'})
        return httpx.Response(200, content=b'ok')

    def download(url, client):
        return download_bounded(url, max_bytes=100, allowed_hosts=frozenset({'api.github.com', 'other.example'}), client=client)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ExternalSchematicRateLimited):
            download(API, client)
        clock[0] += 2.2
        with pytest.raises(ExternalSchematicRateLimited) as error:
            download(API + '/branches/main', client)
        assert error.value.retry_after == 8
        assert calls == [API]
        assert download('https://other.example/board', client)[0] == b'ok'
        monkeypatch.setenv('GITHUB_TOKEN', 'second-fixture-token')
        assert download(API, client)[0] == b'ok'
        monkeypatch.setenv('GITHUB_TOKEN', 'first-fixture-token')
        clock[0] = 1010
        assert download(API, client)[0] == b'ok'
        assert len(calls) == 4


def test_provider_limits_are_bounded_and_public_download_limit_survives_token_change(monkeypatch):
    from backend.projects import schematic_source as limits
    clock = [1000]
    monkeypatch.setattr(limits, '_rate_clock', lambda: clock[0])
    for index in range(130):
        limits.remember_provider_limit(ExternalSchematicRateLimited(10, host=f'{index}.example'))
    assert len(limits._RATE_LIMITS) == 128
    limits.remember_provider_limit(ExternalSchematicRateLimited(10, host='raw.githubusercontent.com'))
    monkeypatch.setenv('GITHUB_TOKEN', 'different-fixture-token')
    clock[0] = 1005
    assert limits.provider_rate_limit('raw.githubusercontent.com').retry_after == 5
    limits.remember_provider_limit(limits.provider_rate_limit('raw.githubusercontent.com'))
    clock[0] = 1010
    assert limits.provider_rate_limit('raw.githubusercontent.com') is None
    limits.remember_provider_limit(ExternalSchematicRateLimited(5, host='fresh.example'))
    assert len(limits._RATE_LIMITS) == 1

SUPPORT = (b'(symbol (lib_id "Connector:TestPoint") (at 30 20 0) (property "Value" "TestPoint")) '
           b'(wire (pts (xy 20 20) (xy 30 20)))')
BOARD = (b'(kicad_sch (symbol (at 20 20 0) (property "Value" "ATtiny85-20PU")) ' + SUPPORT + b')')
CHILD = b'(kicad_sch (sheet (property "Sheetfile" "power.kicad_sch")))'


class Repo:
    def __init__(self, files, license_id="MIT"):
        self.calls = []
        self.branch = {"name": "main", "commit": {"sha": SHA, "commit": {"tree": {"sha": TREE}}}}
        self.tree = {"tree": [{"type": "blob", "mode": "100644", "path": p} for p in files], "truncated": False}
        self.responses = {API: {"license": {"spdx_id": license_id}, "default_branch": "main"},
                          API + "/branches/main": self.branch, API + f"/git/trees/{TREE}?recursive=1": self.tree}
        self.responses.update({RAW + p: body for p, body in files.items()})

    def handle(self, request):
        url = str(request.url)
        self.calls.append(url)
        if url.startswith(RAW):
            assert "authorization" not in request.headers
        body = self.responses[url]
        if isinstance(body, bytes):
            return httpx.Response(200, content=body)
        return httpx.Response(200, json=body)

    def inspect(self, query=""):
        with httpx.Client(transport=httpx.MockTransport(self.handle)) as client:
            return inspect_github_repository(REF, client=client, query=query)


def test_large_commit_diff_does_not_hide_a_valid_pinned_schematic():
    repo = Repo({"board.kicad_sch": BOARD})
    repo.responses[API + "/commits/main"] = {
        "sha": SHA, "commit": {"tree": {"sha": TREE}},
        "files": [{"patch": "x" * 440_000}],
    }
    result = repo.inspect("ATtiny85")
    assert result is not None
    assert result.commit == SHA
    assert API + "/branches/main" in repo.calls
    assert API + "/commits/main" not in repo.calls


def test_multiple_matching_projects_are_separate_selectable_sources():
    repo = Repo({'first/board.kicad_sch': BOARD, 'second/board.kicad_sch': BOARD})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        sources = inspect_github_candidates(REF, query='ATtiny85', client=client)
    assert {s.root_schematic for s in sources} == {'first/board.kicad_sch', 'second/board.kicad_sch'}
    assert len({s.source_url for s in sources}) == 2
    for source in sources:
        assert source.asset_paths == (source.root_schematic,)
        assert source.source_url == f'https://github.com/o/r/blob/{SHA}/{source.root_schematic}'


def test_query_isolates_broken_unrelated_project_but_not_its_own_missing_child():
    assert Repo({'board.kicad_sch': BOARD, 'broken.sch': b'broken unrelated EDA'}).inspect('ATtiny85') is not None
    assert Repo({'board.kicad_sch': CHILD, 'other.kicad_sch': BOARD.replace(b'ATtiny85', b'ATTINY45')}).inspect('ATtiny85') is None


def test_query_can_select_complete_nested_hierarchy_when_parent_has_broken_sibling():
    parent = (b'(kicad_sch (sheet (property "Sheetfile" "broken.kicad_sch")) '
              b'(sheet (property "Sheetfile" "valid.kicad_sch")) '
              b'(wire (pts (xy 1 1) (xy 2 2))))')
    sources = Repo({'parent.kicad_sch': parent, 'broken.kicad_sch': b'broken',
                    'valid.kicad_sch': BOARD.replace(b'ATtiny85', b'SS33')}).inspect('SS33')
    assert sources.root_schematic == 'valid.kicad_sch'


def test_query_prefers_complete_matching_parent_over_nested_child():
    parent = (b'(kicad_sch (sheet (property "Sheetfile" "valid.kicad_sch")) '
              b'(wire (pts (xy 1 1) (xy 2 2))))')
    repo = Repo({'parent.kicad_sch': parent, 'valid.kicad_sch': BOARD.replace(b'ATtiny85', b'SS33')})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        sources = inspect_github_candidates(REF, query='SS33', client=client)
    assert [source.root_schematic for source in sources] == ['parent.kicad_sch']


def test_nested_matching_hierarchy_with_missing_child_is_rejected():
    parent = b'(kicad_sch (sheet (property "Sheetfile" "valid.kicad_sch")))'
    valid = (b'(kicad_sch (sheet (property "Sheetfile" "missing.kicad_sch")) '
             b'(symbol (lib_id "Device:D") (property "Reference" "D1") '
             b'(property "Value" "SS33")) (wire (pts (xy 1 1) (xy 2 2))))')
    assert Repo({'parent.kicad_sch': parent, 'valid.kicad_sch': valid}).inspect('SS33') is None


def test_large_repository_can_offer_a_small_complete_matching_project():
    other = BOARD.replace(b'ATtiny85', b'ATTINY45')
    files = {f'other/board{i}.kicad_sch': other for i in range(21)}
    files['valid/board.kicad_sch'] = BOARD
    result = Repo(files).inspect('ATtiny85')
    assert result.root_schematic == 'valid/board.kicad_sch'
    assert result.asset_paths == ('valid/board.kicad_sch',)


def test_complete_kicad_hierarchy_over_twelve_mib_stays_bounded():
    child_names = [f"sheet{i}.kicad_sch" for i in range(11)]
    root = (b'(kicad_sch ' + b''.join(
        f'(sheet (property "Sheetfile" "{name}"))'.encode() for name in child_names
    ) + b' (symbol (lib_id "Device:D") (property "Reference" "D1") '
      b'(property "Value" "SS33")) (wire (pts (xy 1 1) (xy 2 2))))')
    padded = BOARD + b" " * 1_200_000
    files = {"root.kicad_sch": root + b" " * 1_000_000}
    files.update({name: padded for name in child_names})
    result = Repo(files).inspect("SS33 diode")
    assert result.root_schematic == "root.kicad_sch"
    assert result.expected_sheets == 12


def test_discovery_byte_budget_remains_bounded(monkeypatch):
    child_names = [f"sheet{i}.kicad_sch" for i in range(19)]
    root = (b'(kicad_sch ' + b''.join(
        f'(sheet (property "Sheetfile" "{name}"))'.encode() for name in child_names
    ) + b' (symbol (lib_id "Device:D") (property "Reference" "D1") '
      b'(property "Value" "SS33")) (wire (pts (xy 1 1) (xy 2 2))))')
    padded = BOARD + b" " * 1_400_000
    files = {"root.kicad_sch": root}
    files.update({name: padded for name in child_names})
    assert Repo(files).inspect("SS33 diode") is None
    monkeypatch.setattr(discovery, "MAX_DISCOVERY_BYTES", 40 * 1024**2)
    result = Repo(files).inspect("SS33 diode")
    assert result.root_schematic == "root.kicad_sch"
    assert result.expected_sheets == 20


def test_mixed_cad_repository_does_not_count_eagle_files_as_matching_projects():
    files = {f'other/eagle{i}.sch': b'<?xml version="1.0"?><eagle></eagle>' for i in range(65)}
    files['valid/board.kicad_sch'] = BOARD
    result = Repo(files).inspect('ATtiny85')
    assert result.root_schematic == 'valid/board.kicad_sch'
    assert result.asset_paths == ('valid/board.kicad_sch',)


def test_github_api_cache_expires_and_is_separate_for_credentials(monkeypatch):
    from backend.projects.external_schematic import _Cache
    clock = [1000]
    monkeypatch.setattr(discovery, '_GITHUB_API_CACHE', _Cache(8, 4096, lambda entry: entry[1], 900, lambda: clock[0]))
    calls = []
    def download(url, **kwargs):
        calls.append(url)
        return b'{"public": true}', 'application/json'
    monkeypatch.setattr(discovery, 'download_bounded', download)
    url = 'https://api.github.com/repos/cache/example'
    with httpx.Client(trust_env=False) as client:
        monkeypatch.setenv('GITHUB_TOKEN', 'one-test-credential')
        assert discovery._api(url, 1024, client) == {'public': True}
        assert discovery._api(url, 1024, client) == {'public': True}
        assert len(calls) == 1
        monkeypatch.setenv('GITHUB_TOKEN', 'other-test-credential')
        discovery._api(url, 1024, client)
        assert len(calls) == 2
        clock[0] += 900
        discovery._api(url, 1024, client)
        assert len(calls) == 3


def test_instance_value_cannot_come_from_an_unrelated_metadata_path():
    uuid = '00000000-0000-0000-0000-00005f94c4d9'
    source = (f'(kicad_sch (symbol (lib_id "Diode:1N4007") (uuid {uuid}) '
              '(property "Reference" "D1") (property "Value" "")) '
              '(symbol (lib_id "Device:R") (property "Value" "10k")) '
              '(wire (pts (xy 1 1) (xy 2 2))) (symbol_instances) '
              f'(metadata (path "/{uuid}" (reference "D1") (value "1N4007"))))').encode()
    assert Repo({'board.kicad_sch': source}).inspect('1N4007 diode') is None


@pytest.mark.parametrize('license_id,description,scope', [
    ('CERN-OHL-P-2.0', 'Strongly Reciprocal', 'All hardware design files are licensed under the CERN-OHL-P-2.0.'),
    ('CERN-OHL-S-2.0', 'Strongly Reciprocal', 'All hardware design files are NOT licensed under the CERN-OHL-S-2.0.'),
])
def test_short_license_rejects_mismatched_identity_and_negated_scope(license_id, description, scope):
    notice = f'CERN Open Hardware Licence Version 2 - {description}\n({license_id})\n\nCopyright (c) 2025 Example'
    assert discovery._short_cern_license(notice, scope) is None


@pytest.mark.parametrize("license_id", sorted(ALLOWED_LICENSES))
def test_paired_asset_at_pinned_commit_with_allowed_license(license_id, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture")
    repo = Repo({"hw/board.kicad_sch": BOARD, "hw/schematic.png": b""}, license_id)
    result = repo.inspect("ATtiny85")
    assert result.commit == SHA and result.license == license_id
    assert result.asset_paths == ("hw/schematic.png",)
    assert repo.calls[:3] == [API, API + "/branches/main", API + f"/git/trees/{TREE}?recursive=1"]
    assert repo.calls[3:] == [RAW + "hw/board.kicad_sch"]



def test_github_canonical_casing_is_used_for_pinned_sources():
    repo = Repo({"board.kicad_sch": BOARD})
    repo.responses[API]["full_name"] = "O/R"
    canonical_api = "https://api.github.com/repos/O/R"
    repo.responses[canonical_api + "/branches/main"] = repo.branch
    repo.responses[canonical_api + f"/git/trees/{TREE}?recursive=1"] = repo.tree
    repo.responses[f"https://raw.githubusercontent.com/O/R/{SHA}/board.kicad_sch"] = BOARD
    result = repo.inspect()
    assert result.repository == "O/R"
    assert result.repository_url == "https://github.com/O/R"


def test_github_metadata_cannot_switch_to_another_repository():
    repo = Repo({"board.kicad_sch": BOARD})
    repo.responses[API]["full_name"] = "other/repo"
    assert repo.inspect() is None


@pytest.mark.parametrize("license_id", [None, "NOASSERTION", "Custom"])
def test_license_boundary(license_id):
    repo = Repo({"board.kicad_sch": BOARD}, license_id)
    assert repo.inspect() is None
    if license_id != "NOASSERTION":
        assert repo.calls == [API]


def test_noassertion_requires_structured_cern_notice_and_hardware_scope():
    license_text = (b"CERN Open Hardware Licence Version 2 - Strongly Reciprocal\n"
                    b"(CERN-OHL-S-2.0)\n\nCopyright (c) 2025 Fixture\n")
    readme = (b"All hardware design files (including PCB schematics, layouts, and 3D "
              b"mechanical design files) are licensed under the CERN Open Hardware "
              b"Licence Version 2 - Strongly Reciprocal (CERN-OHL-S-2.0).")
    repo = Repo({"board.kicad_sch": BOARD, "LICENSE": license_text, "README.md": readme}, "NOASSERTION")
    assert repo.inspect().license == "CERN-OHL-S-2.0"
    assert repo.inspect().license_evidence_url == RAW + "LICENSE"


def test_readme_link_priority_and_query_mismatch():
    repo = Repo({"hw/board.kicad_sch": BOARD, "docs/schematic.png": b"", "hw/schematic.svg": b"",
                 "README.md": b"![Schematic](./docs/schematic.png)"})
    assert repo.inspect("ATtiny85").asset_kind == "png"
    assert repo.inspect("ATtiny850") is None
    assert repo.inspect("LM7805 power supply") is None


@pytest.mark.parametrize('query,readme', [
    ('ATtiny85 dev board', '# attiny85 development board'),
    ('tiny85 Fan Control', '# Tiny85FanControl\nA temperature-controlled fan system.'),
    ('Tiny85FanControl', '# Tiny85FanControl\nA temperature-controlled fan system.'),
])
def test_project_name_spelling_keeps_verified_native_schematic(query, readme):
    repo = Repo({'board.kicad_sch': BOARD, 'README.md': readme.encode()})
    source = repo.inspect(query)
    assert source is not None and source.asset_kind == 'kicad'


@pytest.mark.parametrize('query,source,readme', [
    ('tiny850 Fan Control', BOARD, '# Tiny850FanControl'),
    ('tiny85 Fan Control', BOARD.replace(b'ATtiny85', b'ATtiny84'), '# Tiny85FanControl\nATtiny85'),
    ('ATtiny85 dev board', BOARD, '# attiny85 development tool'),
])
def test_project_spelling_cannot_replace_placed_model_or_requested_purpose(query, source, readme):
    assert Repo({'board.kicad_sch': source, 'README.md': readme.encode()}).inspect(query) is None


@pytest.mark.parametrize("image", ["photo.png", "schematic-3d.png", "docs/schematic.png", "block-diagram.pdf"])
def test_irrelevant_asset_falls_back_to_valid_eda(image):
    assert Repo({"board.kicad_sch": BOARD, image: b""}).inspect().asset_kind == "kicad"


def test_complete_hierarchy_and_ambiguous_or_missing_children():
    files = {"hw/board.kicad_sch": CHILD, "hw/power.kicad_sch": BOARD, "hw/schematic.png": b""}
    result = Repo(files).inspect("ATtiny85")
    assert (result.root_schematic, result.asset_kind) == ("hw/board.kicad_sch", "kicad")
    assert Repo({**files, "other.kicad_sch": BOARD}).inspect() is None
    assert Repo({"hw/board.kicad_sch": CHILD}).inspect() is None
    assert Repo({"schematic.png": b""}).inspect() is None
    assert Repo({"board.sch": b"not an EDA schematic"}).inspect() is None


def test_query_selects_matching_hierarchy_without_mixing_independent_projects():
    diode = (b'(kicad_sch (symbol (lib_id "Device:SS34") '
             b'(property "Reference" "D1") (property "Value" "SS34") (at 20 20 0)) '
             b'(symbol (lib_id "Connector:TestPoint") (property "Reference" "J1") '
             b'(property "Value" "TestPoint") (at 30 20 0)) '
             b'(wire (pts (xy 20 20) (xy 30 20))))')
    other = BOARD.replace(b'ATtiny85-20PU', b'1N4007')
    repo = Repo({"controller.kicad_sch": diode, "front-panel.kicad_sch": other})
    result = repo.inspect("SS34 diode")
    assert result.root_schematic == "controller.kicad_sch"
    assert result.asset_paths == ("controller.kicad_sch",)
    assert Repo({"controller.kicad_sch": diode, "front-panel.kicad_sch": other}).inspect() is None


@pytest.mark.parametrize("bad", ["truncated", "oversize", "symlink", "submodule", "traversal", "duplicate", "sha"])
def test_invalid_trees_and_immutable_commit(bad):
    repo = Repo({"board.kicad_sch": BOARD})
    e = repo.tree["tree"][0]
    if bad == "truncated":
        repo.tree["truncated"] = True
    elif bad == "oversize":
        repo.tree["tree"] *= 5001
    elif bad == "duplicate":
        repo.tree["tree"].append(dict(e, path=e["path"].upper()))
    elif bad == "sha":
        repo.branch["commit"]["sha"] = "main"
    elif bad == "traversal":
        e["path"] = "../x"
    else:
        e["mode"] = {"symlink": "120000", "submodule": "160000"}[bad]
        if bad == "submodule":
            e["type"] = "commit"
    assert repo.inspect() is None


@pytest.mark.parametrize("mode", ["declared", "actual", "redirect", "changed_commit", "rate"])
def test_bounded_download(mode):
    url = RAW + "board.png"
    requests = []
    def handle(request):
        requests.append(request)
        if mode == "declared":
            return httpx.Response(200, headers={"Content-Length": "10000"}, content=b"x")
        if mode == "actual":
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * 200))
        if mode == "rate":
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "retry-after": "9999"})
        target = "https://localhost/x" if mode == "redirect" else url.replace(SHA, "main")
        return httpx.Response(302, headers={"Location": target})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ExternalSchematicRateLimited if mode == "rate" else ExternalSchematicInvalidSource) as error:
            download_bounded(url, max_bytes=100, allowed_hosts=frozenset({"raw.githubusercontent.com"}),
                             client=client, phase="github_raw")
    assert len(requests) == 1
    if mode == "rate":
        assert error.value.retry_after == 3600
        assert error.value.host == "raw.githubusercontent.com"
        assert error.value.phase == "github_raw"
        assert error.value.status_code == 403


def test_public_download_connects_to_checked_ip_with_original_tls_name(monkeypatch):
    monkeypatch.setattr(discovery.socket, "getaddrinfo", lambda host, port, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    seen = []

    class Transport(httpx.BaseTransport):
        def handle_request(self, request):
            seen.append(request)
            return httpx.Response(200, content=b"asset", headers={"content-type": "image/png"})

    with httpx.Client(transport=Transport(), trust_env=False) as client:
        data, _ = download_bounded("https://example.org/schematic.png", max_bytes=20,
                                   allowed_hosts=frozenset({"example.org"}), client=client)
    assert data == b"asset"
    assert str(seen[0].url) == "https://93.184.216.34/schematic.png"
    assert seen[0].headers["host"] == "example.org"
    assert seen[0].extensions["sni_hostname"] == "example.org"


def test_public_download_rejects_private_dns_before_connection(monkeypatch):
    monkeypatch.setattr(discovery.socket, "getaddrinfo", lambda host, port, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))])

    class Transport(httpx.BaseTransport):
        def handle_request(self, request):
            pytest.fail("private address must never be contacted")

    with httpx.Client(transport=Transport(), trust_env=False) as client:
        with pytest.raises(ExternalSchematicInvalidSource):
            download_bounded("https://example.org/schematic.png", max_bytes=20,
                             allowed_hosts=frozenset({"example.org"}), client=client)

def test_generic_photo_and_model_name_without_circuit_evidence():
    repo = Repo({"board.kicad_sch": BOARD, "board.png": b"",
                 "README.md": b"![Assembled board](board.png)"})
    assert repo.inspect("ATtiny85의 회로도를 보여줘").asset_kind == "kicad"
    assert repo.inspect("ATtiny850의 회로도를 보여줘") is None
    assert repo.inspect("5V 전원 공급 회로") is None


def test_korean_purpose_all_terms_and_unrelated_submodule():
    repo = Repo({"board.kicad_sch": BOARD, "board.png": b"",
                 "README.md": b"5 V regulated power supply. ![Entire schematic](board.png)"})
    repo.tree["tree"].append({"mode": "160000", "type": "commit", "path": "backups"})
    assert repo.inspect("5V 전원 공급 회로").asset_paths == ("board.png",)
    assert repo.inspect("12V 전원 공급 회로") is None

def test_library_symbol_is_not_a_placed_component_and_empty_source_fails_closed():
    eda = (b'(kicad_sch (lib_symbols (symbol "ATtiny85" (property "Value" "ATtiny85"))) '
           b'(symbol (at 20 20 0) (property "Value" "LM7805")) ' + SUPPORT + b')')
    repo = Repo({"board.kicad_sch": eda})
    assert repo.inspect("ATtiny85") is None
    assert repo.inspect("LM7805").asset_kind == "kicad"
    assert Repo({"board.kicad_sch": b"(kicad_sch)", "README.md": b"ATtiny85"}).inspect("ATtiny85") is None


def test_diode_query_requires_ss33_value_and_reference_on_same_placed_instance():
    source = (b'(kicad_sch '
              b'(lib_symbols (symbol "Device:SS33" (property "Value" "SS33"))) '
              b'(symbol (lib_id "Device:SS33") (property "Reference" "D1") '
              b'(property "Value" "SS33") (at 20 20 0)) '
              b'(symbol (lib_id "Connector:TestPoint") (property "Reference" "J1") '
              b'(property "Value" "TestPoint") (at 10 10 0)) '
              b'(wire (pts (xy 10 10) (xy 20 20))))')
    assert Repo({"board.kicad_sch": source}).inspect("SS33 diode").asset_kind == "kicad"

    unrelated = source.replace(b'(property "Reference" "D1") ', b'(property "Reference" "U1") ')
    assert Repo({"board.kicad_sch": unrelated}).inspect("SS33 diode") is None


def test_diode_query_collects_all_instances_and_supports_legacy_sch():
    source = b'''EESchema Schematic File Version 4
LIBS:power
EELAYER 29 0
EELAYER END
$Descr A4 11693 8268
Sheet 1 1
Title "fixture"
$EndDescr
$Comp
L Device:SS34 D1
U 1 1 1
P 1000 1000
F 0 "D1" H 1000 800 50  0000 C CNN
F 1 "SS34" H 1000 900 50  0000 C CNN
	1    1000 1000
	1    0    0    -1
$EndComp
$Comp
L Device:SS33 D2
U 1 1 2
P 2000 1000
F 0 "D2" H 2000 800 50  0000 C CNN
F 1 "SS33" H 2000 900 50  0000 C CNN
	1    2000 1000
	1    0    0    -1
$EndComp
Wire Wire Line
	1000 1000 2000 1000
$EndSCHEMATC
'''
    assert Repo({"board.sch": source}).inspect("SS33 diode") is None
    repo = Repo({"board.sch": source, "board.pdf": b""})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        sources = inspect_github_candidates(REF, query="SS33 diode", client=client)
    assert [s.asset_kind for s in sources] == ["pdf"]


@pytest.mark.parametrize("model", ["1N4148", "1N4007", "BAT54"])
@pytest.mark.parametrize("library", ["Device:D", "Device:D_Small", "Device:D_Schottky"])
def test_generic_device_d_symbols_accept_normal_diode_values(model, library):
    source = (f'(kicad_sch (symbol (lib_id "{library}") '
              f'(property "Reference" "D1") (property "Value" "{model}") '
              f'(at 20 20 0)) '
              '(symbol (lib_id "Device:R") (property "Reference" "R1") '
              '(property "Value" "1k") (at 30 20 0)) '
              '(wire (pts (xy 20 20) (xy 30 20))))')
    _, values, _, has_wire = discovery._sheet_data("board.kicad_sch", source)
    assert has_wire
    assert _matches_diode_query(model, values)


def _matches_diode_query(model, values):
    return discovery._matches_query(f"{model} diode", " ".join(values), "")


def test_diode_classification_rejects_led_and_keeps_instances_separate():
    source = ('(kicad_sch '
              '(symbol (lib_id "Device:LED") (property "Reference" "D1") '
              '(property "Value" "1N4148") (at 20 20 0)) '
              '(symbol (lib_id "Device:D") (property "Reference" "D2") '
              '(property "Value" "1N4007") (at 30 20 0)) '
              '(wire (pts (xy 20 20) (xy 30 20))))')
    _, values, _, _ = discovery._sheet_data("board.kicad_sch", source)
    assert not _matches_diode_query("1N4148", values)
    assert _matches_diode_query("1N4007", values)


@pytest.mark.parametrize("library, model", [("Device:R", "SS33"), ("Device:R", "BAT54"),
                                             ("Device:LED", "SS33"), ("Device:Laserdiode", "BAT54")])
def test_diode_value_alone_does_not_classify_non_diode_symbols(library, model):
    source = (f'(kicad_sch (symbol (lib_id "{library}") '
              f'(property "Reference" "D1") (property "Value" "{model}") '
              f'(at 20 20 0)) '
              '(symbol (lib_id "Device:R") (property "Reference" "R1") '
              '(property "Value" "1k") (at 30 20 0)) '
              '(wire (pts (xy 20 20) (xy 30 20))))')
    _, values, _, _ = discovery._sheet_data("board.kicad_sch", source)
    assert not _matches_diode_query(model, values)


def test_legacy_generic_device_d_accepts_bat54_but_photo_diode_does_not():
    source = '''EESchema Schematic File Version 4
EELAYER 29 0
EELAYER END
$Comp
L Device:D D1
U 1 1 1
P 1000 1000
F 0 "D1" H 1000 800 50  0000 C CNN
F 1 "BAT54" H 1000 900 50  0000 C CNN
\t1    1000 1000
\t1    0    0    -1
$EndComp
$Comp
L Device:D_Photo D2
U 1 1 2
P 2000 1000
F 0 "D2" H 2000 800 50  0000 C CNN
F 1 "BPW34" H 2000 900 50  0000 C CNN
\t1    2000 1000
\t1    0    0    -1
$EndComp
Wire Wire Line
\t1000 1000 2000 1000
$EndSCHEMATC
'''
    _, values, _, has_wire = discovery._sheet_data("board.sch", source)
    assert has_wire
    assert _matches_diode_query("BAT54", values)
    assert not _matches_diode_query("BPW34", values)

@pytest.mark.parametrize("name", ["old-schematic.png", "schematic-power-stage.png", "schematic-subsystem.pdf"])
def test_outdated_or_partial_name_never_overrides_the_source(name):
    repo = Repo({"board.kicad_sch": BOARD, name: b"", "README.md": f"![Schematic]({name})".encode()})
    assert repo.inspect().asset_kind == "kicad"


def test_part_requires_an_instance_and_7805_alias_requires_correct_voltage():
    source = b'(kicad_sch (symbol (lib_id "Regulator_Linear:L7805") (at 20 20 0) (property "Value" "U1")) ' + SUPPORT + b')'
    repo = Repo({"board.kicad_sch": source, "README.md": b"LM7805 voltage regulator power supply; ATtiny85 is unsupported."})
    assert repo.inspect("LM7805 power supply").asset_kind == "kicad"
    assert repo.inspect("ATtiny85") is None
    assert Repo({"board.kicad_sch": source, "README.md": b"LM7805 voltage regulator is unsupported."}).inspect("LM7805") is None
    repo = Repo({"board.kicad_sch": source.replace(b"L7805", b"L7812"), "README.md": b"LM7805 power supply"})
    assert repo.inspect("LM7805") is None


def test_single_inspection_returns_bounded_format_fallbacks():
    repo = Repo({"board.kicad_sch": BOARD, "schematic.png": b"", "schematic.pdf": b"",
                 "board-schematic.png": b"", "schematic.svg": b""})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        results = inspect_github_candidates(REF, client=client)
    assert [r.asset_kind for r in results] == ["pdf", "png", "svg", "kicad"]
    assert [r.expected_sheets for r in results] == [1] * 4
    assert repo.calls.count(API) == 1


def test_multi_sheet_pdf_counts_repeated_instances_without_exposing_a_partial_png():
    root = b'(kicad_sch (sheet (property "Sheetfile" "switch.kicad_sch")) (sheet (property "Sheetfile" "switch.kicad_sch")))'
    repo = Repo({"board.kicad_sch": root, "switch.kicad_sch": BOARD, "schematic.pdf": b"", "schematic.png": b""})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        results = inspect_github_candidates(REF, client=client)
    assert [(r.asset_kind, r.expected_sheets) for r in results] == [("pdf", 3), ("kicad", 3)]


def test_root_named_pdf_is_preferred_to_low_resolution_png():
    repo = Repo({"PCB/RP2040-Guide.kicad_sch": BOARD,
                 "PCB/RP2040-Guide.pdf": b"pdf",
                 "img/eeschema.png": b"png"})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        results = inspect_github_candidates(REF, client=client, query="ATtiny85")
    assert results[0].asset_kind == "pdf"
    assert results[0].asset_paths == ("PCB/RP2040-Guide.pdf",)


def test_excluded_same_named_pdfs_do_not_override_a_generic_schematic():
    repo = Repo({"board.kicad_sch": BOARD,
                 "datasheets/board.pdf": b"datasheet",
                 "old/board.pdf": b"old",
                 "schematic.pdf": b"schematic"})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        results = inspect_github_candidates(REF, client=client, query="ATtiny85")
    assert results[0].asset_paths == ("schematic.pdf",)


def test_exact_root_pdf_wins_over_generic_schematic_pdf():
    repo = Repo({"PCB/board.kicad_sch": BOARD,
                 "PCB/board.pdf": b"root",
                 "README.md": b"[Schematic](schematic.pdf)",
                 "schematic.pdf": b"generic"})
    with httpx.Client(transport=httpx.MockTransport(repo.handle)) as client:
        results = inspect_github_candidates(REF, client=client, query="ATtiny85")
    assert results[0].asset_paths == ("PCB/board.pdf",)


def test_pcb_folder_exception_keeps_archived_pdf_excluded():
    repo = Repo({"old/PCB/board.kicad_sch": BOARD, "old/PCB/board.pdf": b"old"})
    assert repo.inspect().asset_kind == "kicad"


@pytest.mark.parametrize("source", [
    b'(kicad_sch (symbol (property "Value" "ATtiny85")))',
    b'(kicad_sch (symbol (property "Value" "ATtiny85")) (symbol (property "Value" "R")))',
    b'(kicad_sch (symbol (property "Value" "ATtiny85")) (wire (pts (xy 0 0)(xy 10 0))))',
    BOARD.replace(b"(xy 30 20)", b"(xy 20 20)"),
])
def test_pinout_or_unwired_component_placement_is_not_a_complete_schematic(source):
    assert Repo({"board.kicad_sch": source, "schematic.png": b""}).inspect() is None


def test_legacy_wire_requires_an_electrical_line_and_two_placed_components():
    source = (b'EESchema Schematic File Version 4\n$Comp\nL Device:R R1\nF 1 "R" H 0\n$EndComp\n'
              b'$Comp\nL Device:C C1\nF 1 "C" H 0\n$EndComp\nWire Wire Line\n  400 700 800 700\n$EndSCHEMATC\n')
    assert Repo({"board.sch": source, "board.pdf": b""}).inspect().asset_kind == "pdf"
    assert Repo({"board.sch": source.replace(b"Wire Wire Line", b"Wire Notes Line"),
                 "board.pdf": b""}).inspect() is None


def test_public_asset_download_identifies_the_service_without_browser_impersonation():
    requests = []

    def handle(request):
        requests.append(request)
        if request.headers.get('user-agent') != 'SojaFit/1.0 (schematic viewer)':
            return httpx.Response(403, text='Forbidden')
        return httpx.Response(200, content=b'public asset', headers={'content-type': 'image/png'})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        data, mime = download_bounded('https://example.org/preview-schematic.png', max_bytes=100,
                                     allowed_hosts=frozenset({'example.org'}), client=client,
                                     phase='public_asset')
    assert data == b'public asset'
    assert mime == 'image/png'
    assert len(requests) == 1
    assert requests[0].headers['accept-encoding'] == 'identity'
    assert 'authorization' not in requests[0].headers


def custom_bat54_board(description='Single Schottky clamp diode', cathode='K', reference='D3'):
    return (f'(kicad_sch (lib_symbols (symbol "Controller:BAT54" '
            f'(property "Description" "{description}") '
            '(symbol "BAT54_1_1" (pin passive line (name "A" (effects (font (size 1 1)))) (number "1")) '
            f'(pin passive line (name "{cathode}") (number "3")) '
            '(pin no_connect line (name "NC") (number "2"))))) '
            '(symbol (lib_id "Controller:BAT54") '
            f'(property "Reference" "{reference}") (property "Value" "BAT54")) '
            '(symbol (lib_id "Device:R") (property "Reference" "R1") (property "Value" "10k")) '
            '(wire (pts (xy 1 1) (xy 2 2))))').encode()


def test_custom_diode_uses_embedded_description_and_anode_cathode_pins():
    assert Repo({'board.kicad_sch': custom_bat54_board()}).inspect('BAT54 diode') is not None


def test_custom_diode_accepts_cathode_pin_alias_c():
    assert Repo({'board.kicad_sch': custom_bat54_board(cathode='C')}).inspect('BAT54 diode') is not None


@pytest.mark.parametrize('options', [{'description':'Photodiode'}, {'cathode':'B'}, {'reference':'R3'}])
def test_custom_diode_rejects_optical_wrong_pins_and_non_diode_placements(options):
    assert Repo({'board.kicad_sch': custom_bat54_board(**options)}).inspect('BAT54 diode') is None


def test_query_hierarchy_counts_repeated_child_instances():
    parent = CHILD.replace(b'(kicad_sch', b'(kicad_sch (sheet (property "Sheetfile" "power.kicad_sch"))', 1)
    result = Repo({'board.kicad_sch': parent, 'power.kicad_sch': BOARD}).inspect('ATtiny85')
    assert result.expected_sheets == 3


def test_kicad_symbol_instance_value_fallback_requires_matching_placed_uuid():
    source = (b'(kicad_sch '
              b'(symbol (lib_id "Device:D") (uuid "11111111-1111-1111-1111-111111111111") '
              b'(property "Reference" "D1") (property "Value" "")) '
              b'(symbol (lib_id "Device:R") (uuid "22222222-2222-2222-2222-222222222222") '
              b'(property "Reference" "R1") (property "Value" "1k")) '
              b'(wire (pts (xy 1 1) (xy 2 2))) '
              b'(symbol_instances (path "/11111111-1111-1111-1111-111111111111" '
              b'(reference "D1") (value "BAT54"))))')
    assert Repo({'board.kicad_sch': source}).inspect('BAT54 diode').asset_kind == 'kicad'


def test_kicad_symbol_instance_fallback_accepts_unquoted_placed_uuid():
    source = (b'(kicad_sch '
              b'(symbol (lib_id "Device:D") (uuid 11111111-1111-1111-1111-111111111111) '
              b'(property "Reference" "D1") (property "Value" "")) '
              b'(symbol (lib_id "Device:R") (uuid 22222222-2222-2222-2222-222222222222) '
              b'(property "Reference" "R1") (property "Value" "1k")) '
              b'(wire (pts (xy 1 1) (xy 2 2))) '
              b'(symbol_instances (path "/11111111-1111-1111-1111-111111111111" '
              b'(reference "D1") (value "1N4007"))))')
    assert Repo({'board.kicad_sch': source}).inspect('1N4007 diode').asset_kind == 'kicad'


@pytest.mark.parametrize('instance', [
    b'(path "/99999999-9999-9999-9999-999999999999" (reference "D1") (value "BAT54"))',
    b'(path "/11111111-1111-1111-1111-111111111111" (reference "R1") (value "BAT54"))',
])
def test_kicad_symbol_instance_fallback_rejects_orphan_or_conflicting_uuid(instance):
    source = (b'(kicad_sch '
              b'(symbol (lib_id "Device:D") (uuid "11111111-1111-1111-1111-111111111111") '
              b'(property "Reference" "D1") (property "Value" "")) '
              b'(symbol (lib_id "Device:R") (uuid "22222222-2222-2222-2222-222222222222") '
              b'(property "Reference" "R1") (property "Value" "1k")) '
              b'(wire (pts (xy 1 1) (xy 2 2))) (symbol_instances ') + instance + b'))'
    assert Repo({'board.kicad_sch': source}).inspect('BAT54 diode') is None
