"""라우팅 노드: 프롬프트·입력을 LLM에 넘기고 질문 종류를 메모장에 적는지 확인한다.

- 역할: route.md 프롬프트와 대상·질문이 LLM에 넘어가는지, 질문 종류가 상태에 적히는지 확인한다.
- 하지 않는 일: 실제 LLM의 분류 정확도는 보지 않는다(가짜 LLM).
- 출처: SPEC 2절(그래프)
"""
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
    assert "that is not a diode" in seen["system"]     # route.md의 범위 밖 규칙이 시스템 프롬프트로 간다
    assert "Q1 AO3406" in seen["user"] and "MOSFET" in seen["user"]
