"""재작성 노드와 채점 뒤 갈림길: 원래 질문을 고쳐 검색어를 덮어쓰는지, 생성·재작성·거절 중 어디로 가는지 확인한다(SPEC 2절). LLM은 가짜로 바꾼다."""
from backend.graph import nodes
from backend.graph.build import after_grade

CARD = [{"chunk_id": 1}]


def test_rewrite_fixes_original_question_not_last_query(monkeypatch):
    seen = {}

    def fake_chat(system, user, schema):
        seen["system"], seen["user"] = system, user
        return schema(query=" 1N5819 Forward voltage VF \n")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = nodes.rewrite({"question": "1N5819 순방향 전압 몇이야?", "query": "1차 검색어"})

    assert out == {"query": "1N5819 Forward voltage VF", "path": ["재작성"]}
    assert seen["user"] == "1N5819 순방향 전압 몇이야?"  # 1차 검색어가 아니라 원래 질문을 고친다
    assert "지어내지 않는다" in seen["system"]  # rewrite.md가 시스템 프롬프트로 간다


def test_after_grade_goes_to_answer_when_cards_pass():
    assert after_grade({"passed": [1], "docs": CARD, "tries": 2}) == "생성"


def test_after_grade_rewrites_once_then_refuses():
    # 상수 MAX_TRIES가 아니라 리터럴 2와 비교한다. 상수끼리 비교하면 상한을 바꿔도 통과한다(build.py 안내)
    assert after_grade({"passed": [], "docs": CARD, "tries": 1}) == "재작성"
    assert after_grade({"passed": [], "docs": CARD, "tries": 2}) == "거절"


def test_after_grade_refuses_without_rewrite_when_search_found_nothing():
    # 코퍼스에 없는 품번(1N4001)은 재작성해도 품번 필터가 같아 다시 0장이다(11-02 조장 결정)
    assert after_grade({"passed": [], "docs": [], "tries": 1}) == "거절"
