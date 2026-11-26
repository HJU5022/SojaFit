"""재작성 노드: 원래 질문을 고쳐 검색어를 덮어쓰는지 확인한다(평가 실행기 run_retrieval_* 가 이 노드를 쓴다).

- 하지 않는 일: 실제 LLM이 질문을 잘 고치는지는 보지 않는다(가짜 LLM).
- 출처: SPEC 2절(그래프)·"근거가 없을 때"
"""
from backend.graph import nodes


def test_rewrite_fixes_original_question_not_last_query(monkeypatch):
    seen = {}

    def fake_chat(system, user, schema):
        seen["system"], seen["user"] = system, user
        return schema(query=" 1N5819 Forward voltage VF \n")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = nodes.rewrite({"question": "1N5819 순방향 전압 몇이야?", "query": "1차 검색어"})

    assert out == {"query": "1N5819 Forward voltage VF", "path": ["재작성"]}
    assert seen["user"] == "1N5819 순방향 전압 몇이야?"  # 1차 검색어가 아니라 원래 질문을 고친다
    assert "Do not invent part numbers" in seen["system"]  # rewrite.md가 시스템 프롬프트로 간다

