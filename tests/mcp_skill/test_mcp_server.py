"""MCP 서버 도구 8종: 오프라인에서 입력 검사, 차단 조건, 반환 형식이 계약대로인지 확인한다.

- 역할: 가짜 검색기·가짜 HTTP·가짜 사양 조회로 search_corpus, get_corpus_document, search_tsc_web, verify_tsc_pdf, get_circuit_info,
  check_corpus, get_part_specs, find_parts_by_specs와 도구 목록을 확인한다.
- 하지 않는 일: 실제 Exa 호출, DB, API 키, 검색 품질은 보지 않는다. .env는 읽지 않는다.
- 출처: SPEC 8.7, docs/specs/mcp-search-tools.md AC
"""
import asyncio
import hashlib
import json

import httpx
import pytest

from backend.rag.spec_lookup import CODES

from backend.mcp_skill.mcp_server import server

BASE = "https://services.taiwansemi.com/storage/resources/datasheet"
ROW = {"doc_id": "tsc-abc-series_a1234", "title": "ABC SERIES", "revision": "A1234",
       "source_url": f"{BASE}/ABC SERIES_A1234.pdf", "sha256": "0" * 64, "bytes": 10, "pages": 2}
SAMPLES = ["tsc-1n4148-series_k2301", "tsc-1n5817-series_h2104", "tsc-bzt52c2v4-series_g1804"]


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    """가짜 manifest 파일을 만들고 서버가 그 경로를 읽게 한다. 행 목록을 받아 쓴다."""
    def write(rows):
        path = tmp_path / "manifest.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        monkeypatch.setattr(server, "MANIFEST_PATH", path)
    return write


@pytest.fixture
def web(monkeypatch):
    """외부 검색을 허용하고 키를 꽂은 뒤, HTTP 호출 기록을 돌려준다. 응답은 calls.response로 바꾼다."""
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("EXA_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("EXA_API_KEY", "secret-key")

    class Calls(list):
        response = None

    calls = Calls()

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(calls.response, Exception):
            raise calls.response
        return calls.response

    monkeypatch.setattr(server.httpx, "post", fake_post)
    return calls


def exa(urls):
    """Exa 응답 모양의 가짜 httpx 응답을 만든다."""
    request = httpx.Request("POST", "https://api.exa.ai/search")
    return httpx.Response(200, json={"results": [{"url": u} for u in urls]}, request=request)


# --- search_corpus ---

def test_search_corpus_passes_args_to_retriever(monkeypatch):
    """query·k·parts를 기존 검색기에 그대로 넘기고 결과를 그대로 돌려준다."""
    seen = {}

    def fake_retrieve(query, **kwargs):
        seen.update(query=query, **kwargs)
        return [{"chunk_id": 1}]

    monkeypatch.setattr(server, "retrieve", fake_retrieve)
    assert server.search_corpus("역전압", k=3, parts=["1n5817"]) == [{"chunk_id": 1}]
    assert seen["query"] == "역전압" and seen["k"] == 3 and seen["parts"] == ["1n5817"]


@pytest.mark.parametrize("query,k", [("", 5), ("   ", 5), ("x" * 501, 5), ("q", 0), ("q", 11), ("q", True)])
def test_search_corpus_rejects_bad_input(monkeypatch, query, k):
    """빈 질의·긴 질의·범위 밖 k는 검색 전에 거절한다."""
    monkeypatch.setattr(server, "retrieve", lambda *a, **kw: pytest.fail("검색기를 부르면 안 된다"))
    with pytest.raises(ValueError):
        server.search_corpus(query, k=k)


# --- get_corpus_document ---

def test_get_corpus_document_found_for_real_manifest():
    """실제 manifest의 문서 ID는 found와 pdf_verified false를 돌려준다."""
    result = server.get_corpus_document(SAMPLES[0])
    assert result["status"] == "found" and result["pdf_verified"] is False
    assert result["document"]["doc_id"] == SAMPLES[0]


def test_get_corpus_document_not_found():
    """없는 ID는 not_found다."""
    assert server.get_corpus_document("no-such-doc")["status"] == "not_found"


def test_get_corpus_document_unavailable(monkeypatch, tmp_path):
    """manifest를 읽을 수 없으면 unavailable이다."""
    monkeypatch.setattr(server, "MANIFEST_PATH", tmp_path / "missing.jsonl")
    assert server.get_corpus_document("x") == {"status": "unavailable", "document": None, "pdf_verified": False}


def test_get_corpus_document_unavailable_when_corrupt(manifest, monkeypatch):
    """manifest 줄이 깨졌으면 unavailable이다."""
    manifest([ROW])
    server.MANIFEST_PATH.write_text("{broken\n", encoding="utf-8")
    assert server.get_corpus_document("x")["status"] == "unavailable"


@pytest.mark.parametrize("doc_id", ["", "  ", "a" * 201])
def test_get_corpus_document_rejects_bad_id(doc_id):
    """빈 ID와 200자 초과 ID는 입력 오류다."""
    with pytest.raises(ValueError):
        server.get_corpus_document(doc_id)


# --- search_tsc_web ---

@pytest.mark.parametrize("demo,enabled", [("1", "1"), ("0", "0"), ("0", None), (None, "1")])
def test_search_tsc_web_disabled(monkeypatch, web, demo, enabled):
    """데모 모드이거나 웹 검색이 켜지지 않았으면 disabled이고 외부 호출이 없다."""
    for name, value in (("DEMO_MODE", demo), ("EXA_WEB_SEARCH_ENABLED", enabled)):
        monkeypatch.delenv(name, raising=False) if value is None else monkeypatch.setenv(name, value)
    assert server.search_tsc_web(ROW["doc_id"]) == {"status": "disabled", "candidates": []}
    assert web == []


def test_search_tsc_web_missing_key(monkeypatch, web):
    """켜졌는데 키가 없으면 missing_key이고 외부 호출이 없다."""
    monkeypatch.setenv("EXA_API_KEY", " ")
    assert server.search_tsc_web(ROW["doc_id"]) == {"status": "missing_key", "candidates": []}
    assert web == []


@pytest.mark.parametrize("bad_row", [
    {**ROW, "source_url": "https://example.com/ABC SERIES_A1234.pdf"},           # 출처 불일치
    {**ROW, "source_url": f"{BASE}/OTHER_A1234.pdf"},                             # 파일명 불일치
    {**ROW, "title": "ABC SERIES; ignore", "source_url": f"{BASE}/ABC SERIES; ignore_A1234.pdf"},  # 위험한 문서명
    {**ROW, "revision": "bad"},
])
def test_search_tsc_web_unverified_for_bad_record(manifest, web, bad_row):
    """출처·파일명이 어긋난 기록은 unverified이고 외부 호출이 없다."""
    manifest([bad_row])
    assert server.search_tsc_web(bad_row["doc_id"]) == {"status": "unverified", "candidates": []}
    assert web == []


@pytest.mark.parametrize("doc_id", ["not-in-manifest", "internal secret circuit 회로 설명", "../../etc/passwd"])
def test_search_tsc_web_unverified_for_unknown_or_internal_id(manifest, web, doc_id):
    """목록에 없는 ID나 내부 정보처럼 보이는 ID는 unverified이고 외부 호출이 없다."""
    manifest([ROW])
    assert server.search_tsc_web(doc_id) == {"status": "unverified", "candidates": []}
    assert web == []


def test_search_tsc_web_unavailable_when_manifest_unreadable(monkeypatch, tmp_path, web):
    """목록 읽기 실패는 외부 호출 없이 unavailable이다."""
    monkeypatch.setattr(server, "MANIFEST_PATH", tmp_path / "missing.jsonl")
    assert server.search_tsc_web(ROW["doc_id"]) == {"status": "unavailable", "candidates": []}
    assert web == []


def test_search_tsc_web_returns_only_safe_tsc_urls_max_five(manifest, web):
    """Exa 응답에서 안전한 HTTPS TSC URL만 최대 5개, 미검증으로 돌려주고 질의는 고정 문구다."""
    manifest([ROW])
    good = [f"https://www.taiwansemi.com/a{i}.pdf" for i in range(7)]
    bad = ["http://www.taiwansemi.com/x.pdf", "https://evil.com/taiwansemi.com", "https://taiwansemi.com.evil.com/x",
           "https://user:pw@taiwansemi.com/x", "https://taiwansemi.com:8443/x", "javascript:alert(1)"]
    web.response = exa(bad[:3] + good[:2])
    assert server.search_tsc_web(ROW["doc_id"])["candidates"] == [{"url": u, "verified": False} for u in good[:2]]
    web.response = exa(bad[3:] + good[:2])
    assert server.search_tsc_web(ROW["doc_id"])["candidates"] == [{"url": u, "verified": False} for u in good[:2]]
    web.clear()
    web.response = exa(good)
    result = server.search_tsc_web(ROW["doc_id"])
    assert result["status"] == "ok"
    assert result["candidates"] == [{"url": u, "verified": False} for u in good[:5]]
    assert len(web) == 1
    assert web[0][1]["json"]["query"] == "Taiwan Semiconductor ABC SERIES A1234 datasheet"
    assert web[0][1]["follow_redirects"] is False and web[0][1]["timeout"] == 15


def test_search_tsc_web_unavailable_on_http_error_without_leak(manifest, web):
    """HTTP 오류면 unavailable이고 키·오류 본문을 노출하지 않으며 한 번만 부른다."""
    manifest([ROW])
    request = httpx.Request("POST", "https://api.exa.ai/search")
    web.response = httpx.Response(500, text="provider-error-body secret-key", request=request)
    result = server.search_tsc_web(ROW["doc_id"])
    assert result == {"status": "unavailable", "candidates": []}
    assert "secret-key" not in json.dumps(result) and "provider-error-body" not in json.dumps(result)
    assert len(web) == 1


def test_search_tsc_web_unavailable_on_malformed_response(manifest, web):
    """비정상 응답 모양이면 unavailable이고 재시도하지 않는다."""
    manifest([ROW])
    request = httpx.Request("POST", "https://api.exa.ai/search")
    web.response = httpx.Response(200, json={"results": "oops"}, request=request)
    assert server.search_tsc_web(ROW["doc_id"])["status"] == "unavailable"
    assert len(web) == 1


def test_search_tsc_web_unavailable_on_network_error(manifest, web):
    """연결 오류도 unavailable이다."""
    manifest([ROW])
    web.response = httpx.ConnectError("boom")
    assert server.search_tsc_web(ROW["doc_id"])["status"] == "unavailable"


# --- verify_tsc_pdf ---

@pytest.mark.parametrize("doc_id", SAMPLES)
def test_verify_tsc_pdf_matches_manifest_for_samples(doc_id):
    """표본 PDF 세 개는 manifest의 크기·해시와 맞고 내용 검증은 false로 둔다."""
    result = server.verify_tsc_pdf(doc_id)
    assert result == {"status": "integrity_verified", "integrity_verified": True, "content_verified": False}


def test_verify_tsc_pdf_detects_mismatch(manifest, monkeypatch, tmp_path):
    """파일이 manifest와 다르면 integrity_mismatch다."""
    pdf = tmp_path / "data" / "corpus" / "tsc"
    pdf.mkdir(parents=True)
    (pdf / "1N4148-SERIES_K2301.pdf").write_bytes(b"%PDF-1.4 tampered")
    manifest([{**ROW, "doc_id": SAMPLES[0], "sha256": hashlib.sha256(b"x").hexdigest(), "bytes": 99}])
    monkeypatch.setattr(server, "REPO", tmp_path)
    result = server.verify_tsc_pdf(SAMPLES[0])
    assert result["status"] == "integrity_mismatch" and result["content_verified"] is False


def test_verify_tsc_pdf_rejects_other_ids():
    """표본이 아닌 ID는 not_available_locally, manifest에 없으면 not_found, 빈 ID는 입력 오류다."""
    assert server.verify_tsc_pdf("tsc-1.5ke-series_o2104")["status"] == "not_available_locally"
    assert server.verify_tsc_pdf("no-such-doc")["status"] == "not_found"
    with pytest.raises(ValueError):
        server.verify_tsc_pdf("")


# --- get_circuit_info ---

def test_get_circuit_info_returns_connections():
    """허용된 회로 ID와 존재하는 ref는 연결 정보를 돌려준다."""
    result = server.get_circuit_info("breadboard_supply", "D1")
    assert result["status"] == "found" and result["data"]["ref"] == "D1" and result["data"]["nets"]


def test_get_circuit_info_not_found():
    """알 수 없는 회로 ID나 ref는 not_found다."""
    assert server.get_circuit_info("unknown_circuit", "D1") == {"status": "not_found", "data": None}
    assert server.get_circuit_info("breadboard_supply", "ZZ99") == {"status": "not_found", "data": None}


@pytest.mark.parametrize("circuit_id,target", [
    ("../etc/passwd", "D1"), ("data/circuits/x", "D1"), ("breadboard_supply/../x", "D1"), ("", "D1"),
    ("breadboard_supply", "../D1"), ("breadboard_supply", "D1/../../x"), ("breadboard_supply", ""),
])
def test_get_circuit_info_rejects_path_like_input(circuit_id, target):
    """경로 모양 입력은 거절한다."""
    with pytest.raises(ValueError):
        server.get_circuit_info(circuit_id, target)


# --- 도구 목록 ---

def test_stdio_tool_list_has_all_tools():
    """MCP 도구 목록에 여덟 도구가 모두 있다."""
    names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert names >= {"search_corpus", "get_corpus_document", "search_tsc_web", "verify_tsc_pdf", "get_circuit_info", "check_corpus",
                     "get_part_specs", "find_parts_by_specs"}


# --- check_corpus ---

@pytest.fixture
def known(monkeypatch):
    """코퍼스 목록을 가짜로 바꾼다(DB 없이)."""
    monkeypatch.setattr(server, "corpus_known", lambda: ({"1n5819", "1n4148"}, {"H2104", "K2301"}))


def test_check_corpus_marks_each_part_and_revision(known):
    """품번은 대소문자를 가리지 않고, 개정 코드는 대문자로 맞춰 확인하되 키는 받은 글 그대로 돌려준다."""
    out = server.check_corpus(["1N5819", "1n4001"], ["H2104", "q2611"])
    assert out == {"parts": {"1N5819": True, "1n4001": False}, "revisions": {"H2104": True, "q2611": False}}


def test_check_corpus_accepts_empty_lists(known):
    assert server.check_corpus([], []) == {"parts": {}, "revisions": {}}


@pytest.mark.parametrize("parts,revisions", [
    ("1N5819", []), ([1], []), ([""], []), (["x" * 101], []), (["A1"] * 21, []),
    ([], "H2104"), ([], [2104]), ([], ["H2104"] * 21),
])
def test_check_corpus_rejects_bad_input(known, parts, revisions):
    """목록이 아니거나 글자가 아닌 값, 빈 글, 너무 길거나 너무 많은 입력은 거절한다."""
    with pytest.raises(ValueError):
        server.check_corpus(parts, revisions)


# --- get_part_specs · find_parts_by_specs ---

@pytest.fixture
def lookup(monkeypatch):
    """DB 연결과 사양 조회 함수를 가짜로 바꾸고 받은 인자를 기록한다."""
    from contextlib import nullcontext
    seen = {}
    monkeypatch.setattr(server, "_connect", lambda: nullcontext("conn"))
    monkeypatch.setattr(server, "part_specs", lambda conn, part, codes=None: seen.update(conn=conn, part=part, codes=codes) or ["row"])
    monkeypatch.setattr(server, "find_candidates", lambda conn, conditions, category=None, package=None, limit=50,
                        original_packages=None, original_category=None: seen.update(
        conn=conn, conditions=conditions, category=category, package=package, limit=limit,
        original_packages=original_packages, original_category=original_category) or ["part"])
    return seen


def test_get_part_specs_passes_args(lookup):
    assert server.get_part_specs(" SS34 ", ["VRRM", "PACKAGE"]) == ["row"]
    assert lookup == {"conn": "conn", "part": "SS34", "codes": ["VRRM", "PACKAGE"]}
    server.get_part_specs("SS34")
    assert lookup["codes"] is None


@pytest.mark.parametrize("part,codes", [
    ("", None), ("   ", None), ("x" * 101, None), (1, None),
    ("SS34", "VRRM"), ("SS34", ["NOPE"]), ("SS34", [1]), ("SS34", ["VRRM"] * (len(CODES) + 1)),  # 항목 수보다 많으면 거절
])
def test_get_part_specs_rejects_bad_input(monkeypatch, part, codes):
    """빈·긴 품번, 목록이 아닌 코드, 허용 코드 밖 값은 DB에 가기 전에 거절한다."""
    monkeypatch.setattr(server, "_connect", lambda: pytest.fail("DB에 연결하면 안 된다"))
    with pytest.raises(ValueError):
        server.get_part_specs(part, codes)


def test_find_parts_by_specs_passes_args(lookup):
    cond = [{"code": "VZ", "slot": "min", "gte": 3.42}, {"code": "VZ", "slot": "max", "lte": 3.78}]
    assert server.find_parts_by_specs(cond, category="zener-diode", package="SOD-123") == ["part"]
    assert lookup == {"conn": "conn", "conditions": cond, "category": "zener-diode", "package": "SOD-123", "limit": 20,
                      "original_packages": None, "original_category": None}
    server.find_parts_by_specs([{"code": "VRRM", "gte": 40}], limit=50)
    assert lookup["limit"] == 50 and lookup["category"] is None and lookup["package"] is None
    # 원래 부품의 패키지 · 분류는 순서에만 쓴다(B3)
    server.find_parts_by_specs([{"code": "VRRM", "gte": 15}], original_packages=["DO-41", "DO-204AL"], original_category="standard-rectifier")
    assert lookup["original_packages"] == ["DO-41", "DO-204AL"] and lookup["original_category"] == "standard-rectifier"


@pytest.mark.parametrize("conditions,kw", [
    ([], {}), ({"code": "VRRM", "gte": 40}, {}), ([{"code": "VRRM", "gte": 40}] * 11, {}),
    (["VRRM"], {}), ([{"gte": 40}], {}), ([{"code": "NOPE", "gte": 40}], {}), ([{"code": "PACKAGE", "gte": 1}], {}),
    ([{"code": "VRRM"}], {}),                                     # 이상·이하가 하나도 없다
    ([{"code": "VRRM", "gte": float("nan")}], {}), ([{"code": "VRRM", "lte": float("inf")}], {}),
    ([{"code": "VRRM", "gte": True}], {}), ([{"code": "VRRM", "gte": "40"}], {}),
    ([{"code": "VRRM", "slot": "avg", "gte": 40}], {}), ([{"code": "VRRM", "gte": 40, "op": ">="}], {}),
    ([{"code": "VRRM", "gte": 40}], {"limit": 0}), ([{"code": "VRRM", "gte": 40}], {"limit": 51}),
    ([{"code": "VRRM", "gte": 40}], {"limit": True}),
    ([{"code": "VRRM", "gte": 40}], {"category": ""}), ([{"code": "VRRM", "gte": 40}], {"category": "x" * 101}),
    ([{"code": "VRRM", "gte": 40}], {"package": "SMA%"}), ([{"code": "VRRM", "gte": 40}], {"package": ""}),
    ([{"code": "VRRM", "gte": 40}], {"original_packages": "SMA"}), ([{"code": "VRRM", "gte": 40}], {"original_packages": ["SMA%"]}),
    ([{"code": "VRRM", "gte": 40}], {"original_packages": ["SMA"] * 11}), ([{"code": "VRRM", "gte": 40}], {"original_category": ""}),
])
def test_find_parts_by_specs_rejects_bad_input(monkeypatch, conditions, kw):
    """조건 목록 모양, 코드·자리·숫자(유한한 수만), 개수 상한, 분류·패키지 글자를 DB에 가기 전에 검사한다."""
    monkeypatch.setattr(server, "_connect", lambda: pytest.fail("DB에 연결하면 안 된다"))
    with pytest.raises(ValueError):
        server.find_parts_by_specs(conditions, **kw)
