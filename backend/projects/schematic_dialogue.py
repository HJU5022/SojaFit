"""검증된 회로도 후보의 LLM 설명과 선택 질문을 검사한다.

후보의 사실과 출처는 서버가 소유한다. LLM은 후보를 찾거나 URL을 만들지 않고,
서버가 넘긴 후보 ID의 설명 문장만 작성한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.services import llm


MAX_CANDIDATES = 24
DIFFERENCE_FIELDS = (
    "title",
    "manufacturer",
    "model",
    "revision",
    "source_type",
    "source_file",
    "attribution",
    "source_identifier",
    "source_url",
)
FACT_FIELDS = (
    "title",
    "manufacturer",
    "model",
    "revision",
    "source_type",
    "source_file",
    "attribution",
    "source_identifier",
)
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
_CHOICE_LANGUAGE = re.compile(r"선택|고르|어느\s+회로|choose|pick|one\s+(?:of|only)", re.IGNORECASE)
_FORBIDDEN_QUESTION = re.compile(r"전압|전류|가격|비용|성능|호환|수량|링크|URL|사양", re.IGNORECASE)
_PROMPT = (Path(__file__).parents[1] / "prompts" / "schematic_dialogue.md").read_text(encoding="utf-8")


class DialogueFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal["title", "manufacturer", "model", "revision", "source_type", "source_file", "attribution", "source_identifier"]
    value: str


class DialogueDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    text: str = Field(min_length=1, max_length=500)
    facts: list[DialogueFact] = Field(min_length=1, max_length=len(FACT_FIELDS))


class SchematicDialogueReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=500)
    question: str | None = Field(default=None, min_length=1, max_length=250)
    descriptions: list[DialogueDescription]


def _mode(candidates: list[dict], requested_multiple: bool) -> str:
    if requested_multiple:
        return "all"
    return "select" if len(candidates) > 1 else "single"


def _differences(candidates: list[dict]) -> list[str]:
    return [
        field
        for field in DIFFERENCE_FIELDS
        if len({str(_field_value(item, field) or "") for item in candidates}) > 1
    ]


def _invalid_count(reason: str, mode: str) -> dict:
    return {
        "status": "unavailable",
        "mode": mode,
        "selection_required": mode == "select",
        "message": None,
        "question": None,
        "descriptions": [],
        "reason": reason,
        "clarification_fields": [],
    }


def _failure(reason: str, mode: str, fields: list[str]) -> dict:
    return {
        "status": "unavailable",
        "mode": mode,
        "selection_required": mode == "select",
        "message": None,
        "question": None,
        "descriptions": [],
        "reason": reason,
        "clarification_fields": fields,
    }


def _candidate_values(candidate: dict) -> set[str]:
    return {
        str(_field_value(candidate, field))
        for field in (*FACT_FIELDS, "number")
        if _field_value(candidate, field) not in (None, "")
    }


def _source_identifier(candidate: dict) -> str | None:
    """출처 URL을 노출하지 않고 서버가 검증한 호스트/저장소 식별자만 만든다."""
    attribution = candidate.get("attribution")
    if attribution:
        return str(attribution)
    source = candidate.get("repository_url") or candidate.get("source_url")
    if not source:
        return None
    parsed = urlparse(str(source))
    if not parsed.netloc:
        return None
    path = parsed.path.strip("/").split("/", 2)
    return "/".join([parsed.netloc, *path[:2]]) if path else parsed.netloc


def _field_value(candidate: dict, field: str):
    if field == "source_identifier":
        return _source_identifier(candidate)
    return candidate.get(field)


def _validate_reply(reply: object, candidates: list[dict], mode: str, fields: list[str]) -> SchematicDialogueReply:
    try:
        raw = reply.model_dump() if isinstance(reply, BaseModel) else reply
        parsed = SchematicDialogueReply.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"dialogue schema validation failed: {error}") from error

    expected_ids = [str(item["candidate_id"]) for item in candidates]
    actual_ids = [item.candidate_id for item in parsed.descriptions]
    if actual_ids != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise ValueError("dialogue candidate IDs must exactly preserve server order")

    by_id = {str(item["candidate_id"]): item for item in candidates}
    all_text = [parsed.message, *(item.text for item in parsed.descriptions)]
    if parsed.question:
        all_text.append(parsed.question)
    if any(_URL.search(text or "") for text in all_text):
        raise ValueError("dialogue must not generate URLs")

    all_numbers = {
        number
        for source in candidates
        for value in _candidate_values(source)
        for number in _NUMBER.findall(value)
    }
    all_numbers.update(str(source.get("number", "")) for source in candidates)
    for text in (parsed.message, parsed.question or ""):
        if any(number not in all_numbers for number in _NUMBER.findall(text)):
            raise ValueError("dialogue contains an unsupported number")

    for description in parsed.descriptions:
        source = by_id[description.candidate_id]
        for fact in description.facts:
            expected = _field_value(source, fact.field)
            if expected in (None, "") or fact.value != str(expected):
                raise ValueError("dialogue fact is not an exact server value")
            if fact.value not in description.text:
                raise ValueError("dialogue description must contain each cited fact")
        allowed_numbers = {
            number for value in _candidate_values(source) for number in _NUMBER.findall(value)
        }
        allowed_numbers.add(str(source.get("number", "")))
        if any(number not in allowed_numbers for number in _NUMBER.findall(description.text)):
            raise ValueError("description contains an unsupported number")

        if mode == "select" and not any(fact.field in fields and fact.field != "source_url" for fact in description.facts):
            raise ValueError("selection description must explain a known candidate difference")

    if mode == "select" and not parsed.question:
        raise ValueError("selection mode requires a question")
    if mode == "select" and not any(field != "source_url" for field in fields):
        raise ValueError("selection has no explainable metadata difference")
    if mode == "select" and _FORBIDDEN_QUESTION.search(parsed.question or ""):
        raise ValueError("selection question uses an unsupported field")
    if mode != "select" and parsed.question is not None:
        raise ValueError("single/all mode must not ask a selection question")
    if mode != "select" and any(_CHOICE_LANGUAGE.search(text or "") for text in all_text):
        raise ValueError("single/all mode must not ask the user to choose")
    return parsed


def _public_candidate(candidate: dict) -> dict:
    return {
        "candidate_id": candidate["candidate_id"],
        "number": candidate["number"],
        **{field: _field_value(candidate, field) for field in FACT_FIELDS},
    }


def build_dialogue(
    question: str,
    candidates: list[dict],
    *,
    requested_multiple: bool,
    chat: Callable[[str, str, type[BaseModel]], object],
) -> dict:
    """후보 설명을 생성한다. 외부 후보는 이미 서버에서 검증됐다는 전제다."""
    mode = _mode(candidates, requested_multiple) if candidates else ("all" if requested_multiple else "single")
    if not candidates or len(candidates) > MAX_CANDIDATES:
        return _invalid_count("invalid_candidate_count", mode)

    ids = [item.get("candidate_id") for item in candidates]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        return _invalid_count("invalid_candidate_metadata", mode)
    if any("number" not in item or "queries" not in item for item in candidates):
        return _invalid_count("invalid_candidate_metadata", mode)

    fields = _differences(candidates)
    system = _PROMPT
    user = json.dumps(
        {
            "question": question,
            "mode": mode,
            "selection_required": mode == "select",
            "clarification_fields": fields,
            "candidates": [_public_candidate(item) for item in candidates],
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    try:
        reply = chat(system, user, SchematicDialogueReply)
        parsed = _validate_reply(reply, candidates, mode, fields)
    except (llm.EvaluationLimitError, llm.LLMFormatError):
        return _failure("llm_failure", mode, fields)
    except Exception as error:
        if llm.is_llm_failure(error):
            return _failure("llm_failure", mode, fields)
        if isinstance(error, ValueError):
            return _failure("invalid_llm_output", mode, fields)
        raise

    return {
        "status": "generated",
        "mode": mode,
        "selection_required": mode == "select",
        "message": parsed.message,
        "question": parsed.question,
        "descriptions": [item.model_dump(include={"candidate_id", "text"}) for item in parsed.descriptions],
        "reason": None,
        "clarification_fields": fields,
    }
