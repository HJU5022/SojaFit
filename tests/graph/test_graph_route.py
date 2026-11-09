"""라우팅 노드: 프롬프트·입력을 LLM에 넘기고 질문 종류 · 거절 사유 · 일상 대화 답을 메모장에 적는지 확인한다.

- 역할: route.md 프롬프트와 대상·질문·확인된 사실이 LLM에 넘어가는지, 라우팅 답안지(`route`)가 상태에 적히는지,
  답안지 검사(범위 밖 · 다른 부품의 거절 사유, 일상 대화의 reply)를 확인한다.
- 하지 않는 일: 실제 LLM의 분류 정확도는 보지 않는다(가짜 LLM).
- 출처: SPEC 2절(그래프), backend/multi_agent/contracts.py(질문 종류 · 거절 사유)
"""
import pytest
from pydantic import ValidationError

from backend.graph import nodes


def test_route_sends_prompt_and_target_and_writes_question_type(monkeypatch):
    seen = {}

    def fake_chat(system, user, schema):
        seen["system"], seen["user"] = system, user
        return schema(question_type="other_part")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    state = {"target": "Q1", "target_part": {"value": "AO3406"}, "question": "Q1 대신 쓸 MOSFET 골라 줘."}

    out = nodes.route(state)

    assert out["question_type"] == "other_part" and out["path"] == ["라우팅"]
    assert out["route"] == {"question_type": "other_part", "reason": "not_found", "reply": ""}
    assert "not a diode" in seen["system"] and "Verified facts" in seen["system"]  # route.md의 다른 부품 · 사실 규칙이 시스템 프롬프트로 간다
    assert "Q1 AO3406" in seen["user"] and "MOSFET" in seen["user"]
    assert "(no part number or revision to verify in the question)" in seen["user"]  # 사실 확인이 비어도 그렇다고 적는다


@pytest.mark.parametrize("question_type, reason", [("out_of_scope", "out_of_scope"), ("other_part", "not_found"), ("rating", None)])
def test_refusing_types_get_their_reason_without_a_retry(question_type, reason):
    """[왜] 범위 밖 · 다른 부품은 종류만으로 거절 사유가 정해진다. LLM이 비워 와도 형식 재시도(유료) 없이 채운다."""
    assert nodes.Route(question_type=question_type).reason == reason


def test_reason_is_limited_to_first_stage_refusals():
    assert nodes.Route(question_type="rating", reason="part_missing").reason == "part_missing"
    with pytest.raises(ValidationError):
        nodes.Route(question_type="rating", reason="limit_reached")  # 한도 · 검증 사유는 라우팅이 정할 수 없다


def test_chat_needs_a_reply():
    assert nodes.Route(question_type="chat", reply="안녕하세요!").reply == "안녕하세요!"
    with pytest.raises(ValidationError):
        nodes.Route(question_type="chat")
    with pytest.raises(ValidationError):
        nodes.Route(question_type="chat", reply="가" * 301)  # 멀티 Decision.reply와 같은 300자 상한
