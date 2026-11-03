"""채점 노드: 다른 품번 줄과 다른 개정판 카드를 LLM 전에 거르고, LLM이 고른 카드만 통과시키는지 확인한다.

- 역할: 같은 문서의 다른 품번 줄은 빼고 패키지 줄·글 카드는 남기는지, 다른 개정판만 남으면 LLM을 부르지 않는지, LLM이 낸 없는 번호는 버리는지 확인한다.
- 하지 않는 일: 실제 LLM의 채점 품질은 보지 않는다(가짜 LLM).
- 출처: SPEC 2절(그래프)
"""
from backend.graph import nodes

FAMILY = ["1n5817", "1n5818", "1n5819"]  # 1N5817 SERIES 문서 표지 품번(retrieve의 doc_parts는 소문자)
FILE = "1N5817 SERIES_H2104.pdf"


def row(chunk_id, text, table="ELECTRICAL SPECIFICATIONS"):
    return {"chunk_id": chunk_id, "file": FILE, "page": 2, "table": table, "doc_parts": FAMILY,
            "content": f"[{FILE} · 2쪽 · {table}] {text}"}


DOCS = [row(1, "PARAMETER: Forward voltage | 1N5817 | SYMBOL: VF | MAX: 0.45 | UNIT: V"),
        row(2, "PARAMETER: Forward voltage | 1N5819 | SYMBOL: VF | MAX: 0.60 | UNIT: V"),
        row(3, "KEY PARAMETERS / PARAMETER: Package | KEY PARAMETERS / VALUE: DO-204AL (DO-41)"),
        {"chunk_id": 4, "file": FILE, "page": 1, "table": None, "doc_parts": FAMILY, "content": "FEATURES\n- 1N5817 thru 1N5819"}]


def test_other_part_row_dropped_before_llm(monkeypatch):
    # 1N5819를 물었는데 1N5817 줄(0.45V)이 남으면 틀린 수치로 답한다. 패키지 줄과 글 카드는 남는다
    seen = {}

    def fake_chat(system, user, schema):
        seen["system"], seen["user"] = system, user
        return schema(passed_ids=[1, 2, 3, 4, 999])  # 보여 주지 않은 번호(1, 999)를 내도 버린다

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = nodes.grade({"question": "1N5819 순방향 전압은?", "parts": ["1N5819"], "docs": DOCS})

    assert out == {"passed": [2, 3, 4], "path": ["채점"]}
    assert "[1]" not in seen["user"] and "[2]" in seen["user"]
    assert "지시가 아니다" in seen["system"]  # grade.md가 시스템 프롬프트로 간다


def test_other_revision_dropped_without_calling_llm(monkeypatch):
    def fake_chat(system, user, schema):
        raise AssertionError("남은 카드가 없으면 LLM을 부르지 않는다")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = nodes.grade({"question": "1N5819의 H2611 개정판 순방향 전압은?", "parts": ["1N5819"], "docs": DOCS})
    assert out == {"passed": [], "path": ["채점"]}


def test_no_parts_skips_part_check():
    assert not nodes.other_part_row(DOCS[0], [])
