"""저장소·계층 구조·이미지 연결·네트워크 상한을 격리된 HTTP 응답으로 검사한다."""
import httpx
import pytest

from backend.projects.external_circuit_search import GitHubRepositoryRef
from backend.projects.schematic_discovery import download_bounded, inspect_github_candidates, inspect_github_repository
from backend.projects.schematic_source import ALLOWED_LICENSES, ExternalSchematicInvalidSource, ExternalSchematicRateLimited

REF = GitHubRepositoryRef("o", "r", "https://github.com/o/r")
SHA, TREE = "a" * 40, "b" * 40
API = "https://api.github.com/repos/o/r"
RAW = f"https://raw.githubusercontent.com/o/r/{SHA}/"
SUPPORT = (b'(symbol (lib_id "Connector:TestPoint") (at 30 20 0) (property "Value" "TestPoint")) '
           b'(wire (pts (xy 20 20) (xy 30 20)))')
BOARD = (b'(kicad_sch (symbol (at 20 20 0) (property "Value" "ATtiny85-20PU")) ' + SUPPORT + b')')
CHILD = b'(kicad_sch (sheet (property "Sheetfile" "power.kicad_sch")))'


class Repo:
    def __init__(self, files, license_id="MIT"):
        self.calls = []
        self.head = {"sha": SHA, "commit": {"tree": {"sha": TREE}}}
        self.tree = {"tree": [{"type": "blob", "mode": "100644", "path": p} for p in files], "truncated": False}
        self.responses = {API: {"license": {"spdx_id": license_id}, "default_branch": "main"},
                          API + "/commits/main": self.head, API + f"/git/trees/{TREE}?recursive=1": self.tree}
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


@pytest.mark.parametrize("license_id", sorted(ALLOWED_LICENSES))
def test_paired_asset_at_pinned_commit_with_allowed_license(license_id, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture")
    repo = Repo({"hw/board.kicad_sch": BOARD, "hw/schematic.png": b""}, license_id)
    result = repo.inspect("ATtiny85")
    assert result.commit == SHA and result.license == license_id
    assert result.asset_paths == ("hw/schematic.png",)
    assert repo.calls[:3] == [API, API + "/commits/main", API + f"/git/trees/{TREE}?recursive=1"]
    assert repo.calls[3:] == [RAW + "hw/board.kicad_sch"]


@pytest.mark.parametrize("license_id", [None, "NOASSERTION", "Custom"])
def test_license_boundary(license_id):
    repo = Repo({"board.kicad_sch": BOARD}, license_id)
    assert repo.inspect() is None and repo.calls == [API]


def test_readme_link_priority_and_query_mismatch():
    repo = Repo({"hw/board.kicad_sch": BOARD, "docs/schematic.png": b"", "hw/schematic.svg": b"",
                 "README.md": b"![Schematic](./docs/schematic.png)"})
    assert repo.inspect("ATtiny85").asset_kind == "png"
    assert repo.inspect("ATtiny850") is None
    assert repo.inspect("LM7805 power supply") is None


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
        repo.head["sha"] = "main"
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
            download_bounded(url, max_bytes=100, allowed_hosts=frozenset({"raw.githubusercontent.com"}), client=client)
    assert len(requests) == 1
    if mode == "rate":
        assert error.value.retry_after == 3600

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
    assert Repo({"board.sch": source}).inspect().asset_kind == "kicad"
    assert Repo({"board.sch": source.replace(b"Wire Wire Line", b"Wire Notes Line")}).inspect() is None
