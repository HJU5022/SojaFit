import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from backend.services import llm


class Route(BaseModel):
    kind: str


def _fake_calls(monkeypatch, answers):
    """OpenRouter 호출을 정해 둔 답 목록으로 바꾸고 호출 횟수를 센다."""
    calls = []

    def fake(system, user, schema):
        calls.append(user)
        return answers[len(calls) - 1]

    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm, "_openrouter_call", fake)
    return calls


def test_chat_returns_validated_model(monkeypatch):
    calls = _fake_calls(monkeypatch, ['{"kind": "role"}'])
    assert llm.chat("sys", "q", Route) == Route(kind="role")
    assert len(calls) == 1


def test_chat_reads_json_inside_code_fence(monkeypatch):
    _fake_calls(monkeypatch, ['```json\n{"kind": "rating"}\n```'])
    assert llm.chat("sys", "q", Route).kind == "rating"


def test_chat_retries_bad_format_then_succeeds(monkeypatch):
    calls = _fake_calls(monkeypatch, ["not json", '{"wrong": 1}', '{"kind": "out_of_scope"}'])
    assert llm.chat("sys", "q", Route).kind == "out_of_scope"
    assert len(calls) == 3


def test_chat_stops_after_retry_limit(monkeypatch):
    # [왜] 상수끼리 비교하면 상한을 바꿔도 통과하므로 호출 수를 리터럴 3(첫 호출 + 재시도 2)과 비교한다
    calls = _fake_calls(monkeypatch, ["bad"] * 10)
    with pytest.raises(ValueError):
        llm.chat("sys", "q", Route)
    assert len(calls) == 3


def test_cli_call_disables_tools_and_puts_schema_in_system_prompt(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["cwd"] = cmd, kwargs["cwd"]
        return SimpleNamespace(stdout=json.dumps({"result": '{"kind": "role"}'}))

    monkeypatch.setattr(llm, "LLM_PROVIDER", "claude_cli")
    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    assert llm.chat("규칙", "질문", Route).kind == "role"
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--model") + 1] == llm.LLM_CLI_MODEL
    assert '"kind"' in cmd[cmd.index("--system-prompt") + 1]
    assert cmd[-1] == "질문"


def test_embed_texts_returns_vectors_usage_and_provider_metadata(monkeypatch):
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2])],
        usage=SimpleNamespace(total_tokens=7),
    )
    embeddings = SimpleNamespace(create=lambda **_: response)
    client = SimpleNamespace(embeddings=embeddings)
    monkeypatch.setattr(
        llm,
        "_embedding_client",
        lambda: (client, "test-provider", "test-model"),
        raising=False,
    )

    assert llm.embed_texts(["query"]) == (
        [[0.1, 0.2]],
        7,
        "test-provider",
        "test-model",
    )
