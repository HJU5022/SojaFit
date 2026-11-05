"""거절 노드: 이유 코드(`refusal`)와 안내문, 단서 요청을 답으로 남기는지 확인한다.

- 역할: 라우팅이 첫 단에서 정한 거절(범위 밖 · 없는 품번 · 없는 개정판 · 다른 부품)은 멀티와 같은 일상어 문구와 사유 코드를,
  검색 고리의 거절(품번 문서 없음 · 찾은 문서에 답 없음 · 검색 장애)은 그 품번과 단서 요청, 찾아본 문서 이름(중복 없이)·검색 횟수를 남기는지,
  모든 거절 경로가 이전 턴 Skill 적용 정보를 초기화하는지 확인한다.
- 하지 않는 일: LLM을 쓰지 않는다.
- 출처: SPEC 2절 "근거가 없을 때", SPEC 5절 "도메인 Skill 적용", ADR 0006, backend/multi_agent/messages.py
"""
from backend.graph import nodes
import pytest


def test_out_of_scope_says_scope_without_clue_request():
    out = nodes.refuse({"question_type": "out_of_scope", "route": {"reason": "out_of_scope"}, "question": "오늘 날씨 어때?"})
    assert out["path"] == ["거절"] and out["check"] == {}
    assert out["refusal"] == {"code": "out_of_scope", "message": out["answer"]}
    assert "회로나 부품" in out["answer"] and "단서" not in out["answer"]


def test_first_stage_refusal_names_the_missing_part_and_revision():
    """라우팅이 사실 확인으로 거절하면 없다고 확인된 품번 · 개정판을 문구에 넣는다(멀티 refuse_node와 같은 문구)."""
    part = nodes.refuse({"route": {"reason": "part_missing"}, "facts": {"parts": {"1N4001": False, "1N5817": True}, "revisions": {}}})
    assert part["refusal"]["code"] == "part_missing" and "1N4001" in part["answer"] and "1N5817" not in part["answer"]
    rev = nodes.refuse({"route": {"reason": "revision_missing"}, "facts": {"parts": {}, "revisions": {"K9999": False}}})
    assert rev["refusal"]["code"] == "revision_missing" and "K9999" in rev["answer"]


def test_part_not_in_corpus_names_part_and_asks_clues():
    out = nodes.refuse({"question_type": "rating", "parts": ["1N4001"], "docs": [], "tries": 1})
    assert out["answer"].startswith("문서로 확인 안 됨: 1N4001 데이터시트를 찾지 못했습니다")
    assert "부품 윗면 글자" in out["answer"]
    assert out["refusal"]["code"] == "not_found"  # [왜] 검색 고리의 0장은 사실 확인을 지난 뒤라 '못 찾음'(추정)으로 센다(멀티와 같음)


def test_no_answer_in_found_docs_shows_files_and_tries():
    docs = [{"file": "1N5817 SERIES_H2104.pdf"}, {"file": "1N5817 SERIES_H2104.pdf"}, {"file": "SS34_K2301.pdf"}]
    out = nodes.refuse({"question_type": "rating", "parts": ["1N5819"], "docs": docs, "tries": 2})
    assert "찾아본 문서(1N5817 SERIES_H2104.pdf, SS34_K2301.pdf)" in out["answer"]  # 같은 파일은 한 번만
    assert "검색 2번" in out["answer"] and out["refusal"]["code"] == "not_found"


def test_retrieval_error_is_a_search_error_code():
    out = nodes.refuse({"question_type": "rating", "retrieval_error": {"kind": "timeout"}})
    assert "검색 도구" in out["answer"] and out["refusal"]["code"] == "search_error"


@pytest.mark.parametrize("current", [
    {"question_type": "out_of_scope", "route": {"reason": "out_of_scope"}},
    {"question_type": "rating", "docs": []},
    {"question_type": "rating", "docs": [{"file": "SS34.pdf"}], "tries": 2},
])
def test_refusal_clears_previous_turn_skill_provenance(current):
    state = {"skill": {"enabled": True, "applied": True, "sha256": "previous-turn"}, **current}
    merged = {**state, **nodes.refuse(state)}
    assert merged["skill"] == {"enabled": False, "applied": False, "sha256": None}
