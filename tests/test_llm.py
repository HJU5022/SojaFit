from types import SimpleNamespace

from backend.services import llm


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
