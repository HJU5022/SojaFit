from types import SimpleNamespace

import pytest

from backend.services import llm
from evals import benchmark_embeddings as bench


def test_api_candidate_contracts_are_exact_openrouter_model_ids():
    assert set(bench.API_MODELS) == {
        "openai/text-embedding-3-small",
        "voyageai/voyage-4",
        "baai/bge-m3",
    }
    assert bench.API_MODELS["openai/text-embedding-3-small"].dimension == 1536
    assert bench.API_MODELS["voyageai/voyage-4"].dimension == 1024
    assert bench.API_MODELS["baai/bge-m3"].dimension == 1024


def test_api_request_options_only_adds_voyage_input_roles():
    assert bench.api_request_options("openai/text-embedding-3-small", "query") == {
        "dimensions": 1536
    }
    assert bench.api_request_options("baai/bge-m3", "document") == {}
    assert bench.api_request_options("voyageai/voyage-4", "query") == {
        "input_type": "query",
        "dimensions": 1024,
    }
    assert bench.api_request_options("voyageai/voyage-4", "document") == {
        "input_type": "document",
        "dimensions": 1024,
    }


def test_embed_texts_forwards_approved_model_and_embedding_options(monkeypatch):
    calls = []
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2])],
        usage=SimpleNamespace(total_tokens=7),
    )
    client = SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or response)
    )
    monkeypatch.setattr(
        llm,
        "_embedding_client",
        lambda model_id: (client, "openrouter", model_id),
    )

    got = llm.embed_texts(
        ["datasheet"],
        model_id="voyageai/voyage-4",
        input_type="query",
        dimensions=1024,
    )

    assert got == ([[0.1, 0.2]], 7, "openrouter", "voyageai/voyage-4")
    assert calls == [
        {
            "model": "voyageai/voyage-4",
            "input": ["datasheet"],
            "extra_body": {"input_type": "query"},
            "dimensions": 1024,
        }
    ]


def test_embedding_client_rejects_models_outside_api_experiment_allowlist(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    llm._embedding_client.cache_clear()
    try:
        with pytest.raises(ValueError, match="unsupported embedding model"):
            llm._embedding_client("unapproved/model")
    finally:
        llm._embedding_client.cache_clear()


def test_error_result_has_no_quality_metrics_and_no_retry():
    result = bench.api_error_result(
        "voyageai/voyage-4", RuntimeError("endpoint excluded by data policy")
    )

    assert result["status"] == "error"
    assert result["retry_count"] == 0
    assert "recall_at_5" not in result
    assert "mrr" not in result
