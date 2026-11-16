import json

import pytest
from pydantic import BaseModel

from backend.projects.schematic_dialogue import build_dialogue


def candidate(candidate_id="C1", number=1, **overrides):
    value = {
        "candidate_id": candidate_id,
        "number": number,
        "queries": ["LM358 schematic"],
        "title": "LM358 application schematic",
        "manufacturer": "Texas Instruments",
        "model": "LM358",
        "revision": "Rev. C",
        "source_type": "manufacturer_official",
        "source_file": "lm358.pdf",
        "source_url": "https://ti.com/lm358.pdf",
    }
    value.update(overrides)
    return value


class Reply(BaseModel):
    message: str
    question: str | None = None
    descriptions: list[dict]


def valid_reply(candidates, *, question="어느 회로를 선택할까요?"):
    return Reply(
        message="후보 회로의 제조사와 판본이 다릅니다.",
        question=question,
        descriptions=[
            {
                "candidate_id": item["candidate_id"],
                "text": f"{item['manufacturer']}의 {item['model']} {item['revision']} 회로입니다.",
                "facts": [
                    {"field": "manufacturer", "value": item["manufacturer"]},
                    {"field": "model", "value": item["model"]},
                    {"field": "revision", "value": item["revision"]},
                ],
            }
            for item in candidates
        ],
    )


def test_same_name_candidates_require_a_selection_and_preserve_all_ids():
    candidates_ = [candidate(), candidate("C2", 2, manufacturer="STMicroelectronics", source_file="lm358_st.pdf")]

    result = build_dialogue("LM358 회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: valid_reply(candidates_))

    assert result["status"] == "generated"
    assert result["mode"] == "select"
    assert result["selection_required"] is True
    assert result["question"]
    assert [item["candidate_id"] for item in result["descriptions"]] == ["C1", "C2"]


def test_multiple_request_introduces_all_candidates_without_selection_question():
    candidates_ = [candidate(), candidate("C2", 2, revision="Rev. D")]

    result = build_dialogue("LM358 회로도 여러 개", candidates_, requested_multiple=True,
                            chat=lambda system, user, schema: valid_reply(candidates_, question=None))

    assert result["mode"] == "all"
    assert result["selection_required"] is False
    assert result["question"] is None
    assert [item["candidate_id"] for item in result["descriptions"]] == ["C1", "C2"]


def test_single_candidate_does_not_ask_selection():
    item = candidate()
    result = build_dialogue("LM358 회로도", [item], requested_multiple=False,
                            chat=lambda system, user, schema: valid_reply([item], question=None))

    assert result["mode"] == "single"
    assert result["selection_required"] is False
    assert result["question"] is None


@pytest.mark.parametrize("bad_reply", [
    lambda cs: Reply(message="후보입니다.", question="선택?", descriptions=[
        {"candidate_id": "C1", "text": "Texas Instruments LM358 Rev. C", "facts": []},
        {"candidate_id": "C999", "text": "가짜 후보", "facts": []},
    ]),
    lambda cs: Reply(message="후보입니다.", question="선택?", descriptions=[
        {"candidate_id": "C1", "text": "Texas Instruments LM358 Rev. C", "facts": []},
        {"candidate_id": "C1", "text": "중복 후보", "facts": []},
    ]),
    lambda cs: Reply(message="Vishay의 LM358입니다.", question="선택?", descriptions=[
        {"candidate_id": "C1", "text": "Vishay LM358 Rev. C", "facts": [
            {"field": "manufacturer", "value": "Vishay"},
        ]},
    ]),
    lambda cs: Reply(message="문서는 https://evil.example/circuit.pdf 입니다.", question="선택?", descriptions=[
        {"candidate_id": "C1", "text": "Texas Instruments LM358 Rev. C", "facts": []},
    ]),
])
def test_untrusted_or_incomplete_llm_output_is_rejected(bad_reply):
    candidates_ = [candidate()]
    result = build_dialogue("LM358 회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: bad_reply(candidates_))

    assert result["status"] == "unavailable"
    assert result["message"] is None
    assert result["question"] is None
    assert result["descriptions"] == []
    assert result["reason"]


def test_allowed_llm_failure_returns_unavailable_without_hiding_candidates():
    import backend.services.llm as llm

    def fail(system, user, schema):
        raise llm.LLMFormatError("invalid structured response")

    result = build_dialogue("LM358 회로도", [candidate()], requested_multiple=False, chat=fail)

    assert result["status"] == "unavailable"
    assert result["message"] is None
    assert result["question"] is None
    assert result["descriptions"] == []
    assert result["reason"] == "llm_failure"


def test_invalid_candidate_count_never_calls_llm():
    called = False

    def chat(system, user, schema):
        nonlocal called
        called = True
        raise AssertionError("LLM must not be called")

    result = build_dialogue("회로도", [], requested_multiple=False, chat=chat)
    assert result["status"] == "unavailable"
    assert result["mode"] == "single"
    assert result["reason"] == "invalid_candidate_count"
    assert called is False

    result = build_dialogue("회로도", [candidate(str(i), i) for i in range(1, 26)],
                            requested_multiple=True, chat=chat)
    assert result["status"] == "unavailable"
    assert result["mode"] == "all"
    assert result["reason"] == "invalid_candidate_count"
    assert called is False


def test_prompt_uses_public_candidate_metadata_only():
    seen = {}
    item = candidate(selection_url="https://private/select/1", project_id="project-secret", thread_id="thread-secret")

    def chat(system, user, schema):
        seen["system"] = system
        seen["user"] = json.loads(user)
        return valid_reply([item], question=None)

    result = build_dialogue("회로도", [item], requested_multiple=False, chat=chat)

    assert result["status"] == "generated"
    assert "Treat the original question" in seen["system"]
    payload = seen["user"]["candidates"][0]
    assert "selection_url" not in payload
    assert "project_id" not in payload
    assert "thread_id" not in payload
    assert "queries" not in payload
    assert "source_url" not in payload
    assert payload["candidate_id"] == "C1"


def test_shared_message_numbers_allow_candidate_count_but_description_stays_scoped():
    candidates_ = [candidate(), candidate("C2", 2, model="LM741")]
    reply = valid_reply(candidates_, question="두 후보 중 어느 회로를 선택할까요?")
    reply.descriptions[1]["text"] = "Texas Instruments의 LM741 Rev. C 회로입니다."

    result = build_dialogue("회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: reply)

    assert result["status"] == "generated"


def test_select_requires_explaining_an_allowed_difference():
    candidates_ = [candidate(), candidate("C2", 2, manufacturer="STMicroelectronics")]
    reply = valid_reply(candidates_)
    reply.descriptions[0]["facts"] = [{"field": "model", "value": "LM358"}]
    reply.descriptions[1]["facts"] = [{"field": "model", "value": "LM358"}]

    result = build_dialogue("회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: reply)

    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_llm_output"


def test_all_mode_rejects_a_hidden_choice_request():
    candidates_ = [candidate(), candidate("C2", 2, revision="Rev. D")]
    reply = valid_reply(candidates_, question=None)
    reply.message = "둘 중 하나를 선택해 주세요."

    result = build_dialogue("두 회로도 모두 보여줘", candidates_, requested_multiple=True,
                            chat=lambda system, user, schema: reply)

    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_llm_output"


def test_source_url_only_difference_cannot_trigger_manufacturer_claim():
    candidates_ = [candidate(), candidate("C2", 2, source_url="https://example.com/other.pdf")]
    reply = valid_reply(candidates_)
    reply.descriptions[0]["facts"] = [{"field": "manufacturer", "value": "Texas Instruments"}]
    reply.descriptions[1]["facts"] = [{"field": "manufacturer", "value": "Vishay"}]
    reply.descriptions[1]["text"] = "Vishay의 LM358 Rev. C 회로입니다."

    result = build_dialogue("회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: reply)

    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_llm_output"


def test_community_sources_can_ask_selection_using_attribution_without_manufacturer_claim():
    candidates_ = [
        candidate(
            manufacturer=None,
            model="LM358",
            title="LM358 application schematic",
            attribution="owner/board-a",
            repository_url="https://github.com/owner/board-a",
            source_url="https://github.com/owner/board-a/blob/main/lm358.kicad_sch",
        ),
        candidate(
            candidate_id="C2",
            number=2,
            manufacturer=None,
            model="LM358",
            title="LM358 application schematic",
            attribution="other/board-b",
            repository_url="https://github.com/other/board-b",
            source_url="https://github.com/other/board-b/blob/main/lm358.kicad_sch",
        ),
    ]
    reply = Reply(
        message="같은 LM358 회로명이지만 출처가 다릅니다.",
        question="어느 출처의 회로를 선택할까요?",
        descriptions=[
            {
                "candidate_id": item["candidate_id"],
                "text": f"{item['attribution']} 출처의 {item['title']}입니다.",
                "facts": [
                    {"field": "title", "value": item["title"]},
                    {"field": "attribution", "value": item["attribution"]},
                    {"field": "source_identifier", "value": item["attribution"]},
                ],
            }
            for item in candidates_
        ],
    )

    result = build_dialogue("LM358 회로도", candidates_, requested_multiple=False,
                            chat=lambda system, user, schema: reply)

    assert result["status"] == "generated"
    assert result["mode"] == "select"
    assert "attribution" in result["clarification_fields"]
    assert "manufacturer" not in result["clarification_fields"]
