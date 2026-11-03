"""검색 노드: 질문·대상 값에서 품번을 골라 retrieve의 parts로 넘기는지 확인한다(SPEC 2절). 검색기는 가짜로 바꾼다."""
from backend.graph.nodes import find_parts, search

D3 = {"ref": "D3", "value": "1N4148", "nets": [{"name": "VCC", "nodes": ["D3.K(1N4148)", "K1.1(RELAY)"], "more": 0}]}


def fake_retriever(calls):
    def retriever(question, *, parts=None):
        calls.append((question, parts))
        return [{"chunk_id": 1}]
    return retriever


def test_find_parts_skips_refs_values_and_revisions():
    text = "D3 후보로 TSC BZT52C3V6의 G1804판에서 3.6V, 1V일 때 100pF 넘는지, 1N5819는? 2026년판 BZT52C3V6"
    assert find_parts(text, {"D3"}) == ["BZT52C3V6", "1N5819"]


def test_question_part_wins_over_target_value():
    # 평가셋 n11: 코퍼스에 없는 1N60P를 물었는데 D3 값 1N4148 문서까지 합치면 1N4148 수치로 답하게 된다
    calls = []
    out = search({"question": "D3 대체 후보 1N60P의 역전압을 알려 줘.", "target_part": D3}, fake_retriever(calls))
    assert calls == [("D3 대체 후보 1N60P의 역전압을 알려 줘.", ["1N60P"])]
    assert out == {"query": "D3 대체 후보 1N60P의 역전압을 알려 줘.", "parts": ["1N60P"], "docs": [{"chunk_id": 1}],
                   "retrieval_error": None, "tries": 1, "path": ["검색"]}


def test_target_value_used_when_question_has_no_part():
    calls = []
    search({"question": "D3 대신 쓸 다이오드 찾아 줘.", "target_part": D3}, fake_retriever(calls))
    assert calls[0][1] == ["1N4148"]


def test_no_part_searches_whole_corpus():
    calls = []
    search({"question": "역류 전류를 측정한 값이 있어?", "target_part": {"ref": "D2", "value": "DIODESOD", "nets": []}},
           fake_retriever(calls))
    assert calls[0][1] is None


def test_rewritten_query_is_searched():
    calls = []
    search({"question": "1N4148 전압강하?", "query": "1N4148 forward voltage VF", "target_part": D3}, fake_retriever(calls))
    assert calls == [("1N4148 forward voltage VF", ["1N4148"])]
