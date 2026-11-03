from pathlib import Path

from evals import evaluate_reranker_matrix as matrix
from evals.build_reranker_matrix_vectors import normalize, retrieval_queries


def test_matrix_contains_all_six_by_three_combinations_in_fixed_order():
    combinations = matrix.combinations()

    assert len(combinations) == 18
    assert combinations[0] == ("text-embedding-3-small", "cohere/rerank-4-pro")
    assert combinations[-1] == ("KURE-v1", "qwen/qwen3-reranker-8b")
    assert {embedding for embedding, _ in combinations} == set(matrix.EMBEDDINGS)
    assert {reranker for _, reranker in combinations} == set(matrix.RERANKERS)


def test_matrix_can_select_one_embedding_without_changing_default_order():
    combinations = matrix.combinations(
        ("qwen/qwen3-reranker-8b",), embeddings=("KURE-v1",)
    )

    assert combinations == [("KURE-v1", "qwen/qwen3-reranker-8b")]


def test_vector_arguments_require_only_selected_embeddings():
    parsed = matrix.parse_vector_args(
        ["KURE-v1=C:/cache/kure.f32"], required=("KURE-v1",)
    )

    assert parsed == {"KURE-v1": Path("C:/cache/kure.f32")}


def test_rrf_candidates_use_fifty_per_branch_and_keep_union_up_to_one_hundred():
    dense = list(range(50)) + list(range(100, 120))
    keyword = list(range(50, 100))

    candidates = matrix.fused_candidates(dense, keyword)

    assert len(candidates) == 100
    assert set(candidates) == set(range(100))


def test_preflight_cost_supports_token_and_per_search_models():
    usage = {
        "cohere/rerank-4-pro": {"tokens": 999_999, "searches": 19},
        "voyageai/rerank-3": {"tokens": 1_000_000, "searches": 19},
        "qwen/qwen3-reranker-8b": {"tokens": 1_000_000, "searches": 19},
    }

    costs = matrix.estimated_rerank_costs(usage)

    assert costs == {
        "cohere/rerank-4-pro": 0.0475,
        "voyageai/rerank-3": 0.05,
        "qwen/qwen3-reranker-8b": 0.2,
    }


def test_preflight_counts_only_selected_embedding_searches():
    candidate_sets = {
        "KURE-v1": {
            "rows": [
                {
                    "question": "q",
                    "candidates": [0],
                }
            ]
        }
    }

    preflight = matrix.preflight_usage(
        candidate_sets,
        [{"text": "document"}],
        ("qwen/qwen3-reranker-8b",),
    )

    assert preflight["usage"]["qwen/qwen3-reranker-8b"]["searches"] == 19


def test_markdown_keeps_all_failed_and_success_rows():
    rows = []
    for index, (embedding, reranker) in enumerate(matrix.combinations()):
        rows.append(
            {
                "embedding": embedding,
                "reranker": reranker,
                "status": "ok" if index % 2 == 0 else "error",
                "baseline": {},
                "reranked": {},
            }
        )

    markdown = matrix.render_markdown(rows)

    data_lines = [line for line in markdown.splitlines() if line.startswith("| `")]
    assert len(data_lines) == 18
    assert "| error |" in markdown
    assert "| ok |" in markdown


def test_summarize_ranking_uses_top_five_and_tracks_regressions():
    baseline = {"q1": 2, "q2": 1, "q3": None}
    reranked = {"q1": 1, "q2": None, "q3": 4}

    summary = matrix.summarize_ranks(baseline, reranked)

    assert summary["improved_count"] == 2
    assert summary["worsened_count"] == 1
    assert summary["regression_ids"] == ["q2"]
    assert summary["baseline_mrr"] == 0.5
    assert summary["reranked_mrr"] == (1 + 0 + 0.25) / 3


def test_vector_builder_normalizes_and_rejects_zero_vectors():
    import numpy as np
    import pytest

    normalized = normalize([[3.0, 4.0]], 1, 2)
    assert np.allclose(normalized, [[0.6, 0.8]])
    with pytest.raises(ValueError, match="zero"):
        normalize([[0.0, 0.0]], 1, 2)


def test_gold_locations_are_restored_after_json_round_trip():
    assert matrix.gold_tuples([["part.pdf", 3], ["part.pdf", 4]]) == [
        ("part.pdf", 3),
        ("part.pdf", 4),
    ]


def test_query_builder_keeps_only_relevant_rows_with_pdf_gold(tmp_path):
    path = tmp_path / "dataset.jsonl"
    path.write_text(
        '\n'.join(
            [
                '{"id":"a","kind":"relevant","input":"q1","gold_chunks":["a.pdf, 3쪽"]}',
                '{"id":"b","kind":"relevant","input":"q2","gold_chunks":["회로 NET"]}',
                '{"id":"c","kind":"irrelevant","input":"q3","gold_chunks":[]}',
            ]
        ),
        encoding="utf-8",
    )
    assert retrieval_queries(path) == [{"id": "a", "text": "q1"}]


def test_voyage_reranker_routes_to_direct_api(monkeypatch):
    seen = {}

    def direct(query, documents, **kwargs):
        seen.update(query=query, documents=documents, kwargs=kwargs)
        return ([{"index": 0, "relevance_score": 1.0}], 7, "voyage", "rerank-3")

    monkeypatch.setattr(matrix, "voyage_rerank_texts", direct, raising=False)

    result = matrix.rerank_api_call(
        "voyageai/rerank-3", "query", ["document"], timeout=30
    )

    assert result[2:] == ("voyage", "rerank-3")
    assert seen == {
        "query": "query",
        "documents": ["document"],
        "kwargs": {"model_id": "rerank-3", "top_n": 1, "timeout": 30},
    }


def test_cohere_reranker_routes_to_direct_api(monkeypatch):
    seen = {}

    def direct(query, documents, **kwargs):
        seen.update(query=query, documents=documents, kwargs=kwargs)
        return ([{"index": 0, "relevance_score": 1.0}], 7, "cohere", "rerank-v4.0-pro")

    monkeypatch.setattr(matrix, "cohere_rerank_texts", direct, raising=False)

    result = matrix.rerank_api_call(
        "cohere/rerank-4-pro", "query", ["document"], timeout=30
    )

    assert result[2:] == ("cohere", "rerank-v4.0-pro")
    assert seen == {
        "query": "query",
        "documents": ["document"],
        "kwargs": {"model_id": "rerank-v4.0-pro", "top_n": 1, "timeout": 30},
    }


def test_cohere_trial_slot_waits_only_for_remaining_interval(monkeypatch):
    times = iter([103.0, 106.5])
    slept = []
    monkeypatch.setattr(matrix, "_last_cohere_request_started", 100.0)

    matrix.wait_for_cohere_trial_slot(
        monotonic=lambda: next(times), sleep=lambda seconds: slept.append(seconds)
    )

    assert slept == [3.5]
    assert matrix._last_cohere_request_started == 106.5


def test_voyage_query_embedding_routes_to_direct_api(monkeypatch):
    seen = {}

    def direct(texts, **kwargs):
        seen.update(texts=texts, kwargs=kwargs)
        return ([[1.0, 0.0]], 5, "voyage", "voyage-4")

    monkeypatch.setattr(matrix, "voyage_embed_texts", direct, raising=False)

    vector, used, provider, model = matrix.api_query_embedding("voyage-4", "query")

    assert vector.tolist() == [1.0, 0.0]
    assert (used, provider, model) == (5, "voyage", "voyage-4")
    assert seen == {
        "texts": ["query"],
        "kwargs": {
            "model_id": "voyage-4",
            "input_type": "query",
            "dimensions": 1024,
        },
    }
