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


def test_embed_texts_forwards_openrouter_model_options(monkeypatch):
    seen = {}
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.3, 0.4])],
        usage=SimpleNamespace(total_tokens=11),
    )

    def create(**kwargs):
        seen.update(kwargs)
        return response

    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    monkeypatch.setattr(
        llm,
        "_embedding_client",
        lambda model_id=None: (client, "openrouter", model_id or "openai/text-embedding-3-small"),
    )

    result = llm.embed_texts(
        ["datasheet"],
        model_id="voyageai/voyage-4-large",
        input_type="document",
        dimensions=1024,
    )

    assert result == ([[0.3, 0.4]], 11, "openrouter", "voyageai/voyage-4-large")
    assert seen == {
        "model": "voyageai/voyage-4-large",
        "input": ["datasheet"],
        "extra_body": {"input_type": "document"},
        "dimensions": 1024,
    }


def test_rerank_texts_normalizes_and_sorts_openrouter_response(monkeypatch):
    seen = {}

    def fake_request(payload, timeout):
        seen["payload"] = payload
        seen["timeout"] = timeout
        return {
            "model": "voyageai/rerank-3",
            "provider": "Voyage",
            "results": [
                {"index": 1, "relevance_score": 0.25},
                {"index": 0, "relevance_score": 0.9},
            ],
            "usage": {"total_tokens": 17},
        }

    monkeypatch.setattr(llm, "_openrouter_rerank_request", fake_request, raising=False)

    rows, used, provider, model = llm.rerank_texts(
        "BZT52C3V6 정격은?",
        ["정답 문서", "다른 문서"],
        model_id="voyageai/rerank-3",
        top_n=2,
        timeout=30,
    )

    assert rows == [
        {"index": 0, "relevance_score": 0.9},
        {"index": 1, "relevance_score": 0.25},
    ]
    assert (used, provider, model) == (17, "Voyage", "voyageai/rerank-3")
    assert seen == {
        "payload": {
            "model": "voyageai/rerank-3",
            "query": "BZT52C3V6 정격은?",
            "documents": ["정답 문서", "다른 문서"],
            "top_n": 2,
        },
        "timeout": 30,
    }


def test_rerank_texts_rejects_duplicate_or_out_of_range_indices(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_openrouter_rerank_request",
        lambda payload, timeout: {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.8},
            ]
        },
        raising=False,
    )

    with pytest.raises(ValueError, match="index"):
        llm.rerank_texts("q", ["a", "b"], model_id="cohere/rerank-4-pro")


def test_cohere_rerank_texts_uses_direct_v2_api_contract(monkeypatch):
    seen = {}

    def fake_request(payload, timeout):
        seen.update(payload=payload, timeout=timeout)
        return {
            "results": [
                {"index": 1, "relevance_score": 0.2},
                {"index": 0, "relevance_score": 0.8},
            ],
            "meta": {"tokens": {"input_tokens": 15}},
        }

    monkeypatch.setattr(llm, "_cohere_request", fake_request, raising=False)

    result = llm.cohere_rerank_texts(
        "query",
        ["right", "wrong"],
        model_id="rerank-v4.0-pro",
        top_n=2,
        timeout=30,
    )

    assert result == (
        [
            {"index": 0, "relevance_score": 0.8},
            {"index": 1, "relevance_score": 0.2},
        ],
        15,
        "cohere",
        "rerank-v4.0-pro",
    )
    assert seen == {
        "payload": {
            "model": "rerank-v4.0-pro",
            "query": "query",
            "documents": ["right", "wrong"],
            "top_n": 2,
        },
        "timeout": 30,
    }


def test_voyage_embed_texts_uses_direct_api_contract(monkeypatch):
    seen = {}

    def fake_request(path, payload, timeout):
        seen.update(path=path, payload=payload, timeout=timeout)
        return {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ],
            "model": "voyage-4-large",
            "usage": {"total_tokens": 9},
        }

    monkeypatch.setattr(llm, "_voyage_request", fake_request, raising=False)

    result = llm.voyage_embed_texts(
        ["first", "second"],
        model_id="voyage-4-large",
        input_type="document",
        dimensions=1024,
        timeout=30,
    )

    assert result == (
        [[0.1, 0.2], [0.3, 0.4]],
        9,
        "voyage",
        "voyage-4-large",
    )
    assert seen == {
        "path": "/v1/embeddings",
        "payload": {
            "input": ["first", "second"],
            "model": "voyage-4-large",
            "input_type": "document",
            "output_dimension": 1024,
        },
        "timeout": 30,
    }


def test_voyage_rerank_texts_uses_top_k_and_normalizes_results(monkeypatch):
    seen = {}

    def fake_request(path, payload, timeout):
        seen.update(path=path, payload=payload, timeout=timeout)
        return {
            "data": [
                {"index": 1, "relevance_score": 0.2},
                {"index": 0, "relevance_score": 0.8},
            ],
            "model": "rerank-3",
            "usage": {"total_tokens": 13},
        }

    monkeypatch.setattr(llm, "_voyage_request", fake_request, raising=False)

    result = llm.voyage_rerank_texts(
        "query",
        ["right", "wrong"],
        model_id="rerank-3",
        top_n=2,
        timeout=40,
    )

    assert result == (
        [
            {"index": 0, "relevance_score": 0.8},
            {"index": 1, "relevance_score": 0.2},
        ],
        13,
        "voyage",
        "rerank-3",
    )
    assert seen == {
        "path": "/v1/rerank",
        "payload": {
            "query": "query",
            "documents": ["right", "wrong"],
            "model": "rerank-3",
            "top_k": 2,
            "return_documents": False,
        },
        "timeout": 40,
    }
