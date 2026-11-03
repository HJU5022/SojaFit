"""LLM 호출 입구(backend.services.llm): 형식 검증, 재시도 상한, 임베딩 반환 계약을 가짜 모델로 확인한다.

- 역할: chat()의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령, 임베딩 반환 계약을 확인한다.
- 하지 않는 일: API를 부르지 않는다. 모델 응답의 품질은 보지 않는다.
- 출처: AGENTS.md 지킬 것 2·6, ADR 0010
"""
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from backend.services import llm


class Route(BaseModel):
    kind: str


def _fake_calls(monkeypatch, answers):
    """LangChain 채팅 모델을 가짜로 바꾼다. 정해 둔 답 글자를 schema로 검증해 돌려주고 호출 횟수를 센다."""
    calls = []

    def invoke(messages, schema):
        calls.append(messages)
        # 진짜 with_structured_output처럼 형식이 틀리면 ValidationError를 낸다
        return schema.model_validate_json(answers[len(calls) - 1])

    fake_model = SimpleNamespace(
        with_structured_output=lambda schema: SimpleNamespace(invoke=lambda messages: invoke(messages, schema)))
    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm, "_chat_model", lambda: fake_model)
    return calls


def test_chat_returns_validated_model(monkeypatch):
    calls = _fake_calls(monkeypatch, ['{"kind": "role"}'])
    assert llm.chat("sys", "q", Route) == Route(kind="role")
    assert len(calls) == 1
    assert calls[0] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]


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


def test_cli_call_reads_json_inside_code_fence(monkeypatch):
    fenced = '```json\n{"kind": "rating"}\n```'
    monkeypatch.setattr(llm, "LLM_PROVIDER", "claude_cli")
    monkeypatch.setattr(llm.subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout=json.dumps({"result": fenced})))
    assert llm.chat("규칙", "질문", Route).kind == "rating"


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


def _voyage_http(monkeypatch, *replies):
    """httpx.post를 가짜로 바꿔 (주소, 요청 본문)을 기록하고 replies를 차례로 돌려준다. 네트워크는 쓰지 않는다."""
    import httpx
    sent, replies = [], list(replies)
    monkeypatch.setenv("VOYAGE_API_KEY", "fake-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: sent.append((url, kw["json"])) or replies.pop(0))
    return sent


def _reply(status, body=None, text=""):
    return SimpleNamespace(status_code=status, json=lambda: body, text=text)


def test_voyage_embed_builds_query_payload_and_orders_by_index(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(200, {"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]}))
    assert llm.voyage_embed(["a", "b"], "query") == [[1.0], [2.0]]
    assert sent == [("https://api.voyageai.com/v1/embeddings", {"input": ["a", "b"], "model": "voyage-4-large", "input_type": "query",
                                                                  "truncation": True, "output_dimension": 1024})]


def test_voyage_rerank_returns_ranked_indices(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(200, {"data": [{"index": 2}, {"index": 0}, {"index": 1}]}))
    assert llm.voyage_rerank("q", ["a", "b", "c"]) == [2, 0, 1]
    assert sent[0] == ("https://api.voyageai.com/v1/rerank", {"query": "q", "documents": ["a", "b", "c"], "model": "rerank-3", "truncation": True})


def test_voyage_retries_429_but_stops_on_payment_signal(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(429), _reply(200, {"data": [{"index": 0}]}))
    assert llm.voyage_rerank("q", ["a"]) == [0] and len(sent) == 2
    sent = _voyage_http(monkeypatch, _reply(402, text="payment required"))
    with pytest.raises(RuntimeError, match="payment"):
        llm.voyage_rerank("q", ["a"])
    assert len(sent) == 1  # 결제 신호는 다시 부르지 않는다
