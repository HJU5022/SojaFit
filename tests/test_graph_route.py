"""라우팅 노드: 프롬프트·입력을 LLM에 넘기고 질문 종류를 메모장에 적는지 확인한다(SPEC 2절). LLM은 가짜로 바꾼다."""
from backend.graph import nodes


def test_route_sends_prompt_and_target_and_writes_question_type(monkeypatch):
    seen = {}

    def fake_chat(system, user, schema):
        seen["system"], seen["user"] = system, user
        return schema(question_type="out_of_scope")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    state = {"target": "Q1", "target_part": {"value": "AO3406"}, "question": "Q1 대신 쓸 MOSFET 골라 줘."}

    out = nodes.route(state)

    assert out == {"question_type": "out_of_scope", "path": ["라우팅"]}
    assert "다이오드가 아닌 부품" in seen["system"]     # route.md의 범위 밖 규칙이 시스템 프롬프트로 간다
    assert "Q1 AO3406" in seen["user"] and "MOSFET" in seen["user"]
