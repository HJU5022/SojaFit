"""거절 노드: 이유(범위 밖 / 품번 문서 없음 / 찾은 문서에 답 없음)와 단서 요청을 답으로 남기는지 확인한다(SPEC 2절). LLM을 쓰지 않는다."""
from backend.graph import nodes


def test_out_of_scope_says_scope_without_clue_request():
    out = nodes.refuse({"question_type": "out_of_scope", "question": "Q1 대신 쓸 MOSFET 골라 줘."})
    assert out["path"] == ["거절"] and out["check"] == {}
    assert "범위 밖" in out["answer"] and "단서" not in out["answer"]


def test_part_not_in_corpus_names_part_and_asks_clues():
    out = nodes.refuse({"question_type": "rating", "parts": ["1N4001"], "docs": [], "tries": 1})
    assert out["answer"].startswith("문서로 확인 안 됨: 1N4001 데이터시트를 찾지 못했습니다")
    assert "부품 윗면 글자" in out["answer"]


def test_no_answer_in_found_docs_shows_files_and_tries():
    docs = [{"file": "1N5817 SERIES_H2104.pdf"}, {"file": "1N5817 SERIES_H2104.pdf"}, {"file": "SS34_K2301.pdf"}]
    out = nodes.refuse({"question_type": "rating", "parts": ["1N5819"], "docs": docs, "tries": 2})
    assert "찾아본 문서(1N5817 SERIES_H2104.pdf, SS34_K2301.pdf)" in out["answer"]  # 같은 파일은 한 번만
    assert "검색 2번" in out["answer"]
