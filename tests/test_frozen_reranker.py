import json
from pathlib import Path

from evals import evaluate_frozen_reranker as reranker
from evals.evaluate_frozen_embedding_sample import summarize


ROOT = Path(__file__).parents[1]


def test_success_models_and_reranker_are_fixed():
    assert reranker.SUCCESS_MODELS == (
        "qwen/qwen3-embedding-8b",
        "perplexity/pplx-embed-v1-0.6b",
        "openai/text-embedding-3-small",
        "intfloat/multilingual-e5-large",
        "amazon/titan-embed-text-v2",
    )
    assert reranker.RERANK_MODEL == "qwen/qwen3-reranker-8b"
    assert reranker.BRANCH_LIMIT == reranker.CANDIDATE_LIMIT == 50


def test_fused_candidates_take_rrf_top_50():
    dense = list(range(70))
    keyword = list(range(30, 100))

    hybrid, candidates = reranker.fused_candidates(dense, keyword)

    assert len(candidates) == 50
    assert candidates == hybrid[:50]
    assert set(candidates) <= set(dense[:50]) | set(keyword[:50])


def test_candidate_row_distinguishes_retrieval_ceiling_from_top_5():
    chunks = [
        {"doc": "wrong.pdf", "page": 1, "idx": 0},
        {"doc": "gold.pdf", "page": 3, "idx": 1},
    ]
    item = {"id": "q1"}

    row = reranker.candidate_row([0, 1], item, [("gold.pdf", 3)], chunks)

    assert row["rank"] == 2
    assert row["hit_at_50"] is True
    assert row["candidate_count"] == 2


def test_final_metrics_do_not_give_mrr_credit_below_top_5():
    chunks = [
        {"doc": f"wrong-{index}.pdf", "page": 1, "idx": index}
        for index in range(5)
    ] + [{"doc": "gold.pdf", "page": 3, "idx": 5}]

    row = reranker.top5_metric_row(
        list(range(6)), {"id": "q1"}, [("gold.pdf", 3)], chunks
    )

    assert row["rank"] is None


def test_token_preflight_is_conservative_and_deterministic():
    assert reranker.estimated_token_upper_bound("abcd", ["123456", "xy"]) == 8


def test_published_rerank_results_recompute_and_match_summary():
    results = ROOT / "evals" / "results"
    summary = json.loads(
        (results / "rerank_hybrid_frozen100_summary_2026-11-02.json").read_text(
            encoding="utf-8"
        )
    )
    summary_by_model = {row["embedding_model"]: row for row in summary["results"]}
    paths = [
        path
        for path in results.glob("rerank_hybrid_frozen100_*_2026-11-02.json")
        if not any(mark in path.name for mark in ("summary", "_503_", "_progress_", "_budget_"))
    ]
    assert len(paths) == 5
    for path in paths:
        result = json.loads(path.read_text(encoding="utf-8"))
        assert result["status"] == "ok"
        rows = result["rows"]
        assert {
            name: summarize([row[name] for row in rows])
            for name in ("bm25", "dense", "hybrid", "reranked")
        } == result["metrics"]
        published = summary_by_model[result["embedding_model"]]
        assert published["candidate_hit_at_50"] == result["candidate_hit_at_50"]
        assert published["reranked_recall_at_5"] == result["metrics"]["reranked"][
            "recall_at_5"
        ]
        assert published["reranked_mrr"] == result["metrics"]["reranked"]["mrr"]
        assert published["manual_resume_count"] == result["manual_resume_count"]

    assert summary["total_cost_usd"] <= summary["approved_cost_ceiling_usd"]
    assert summary["automatic_retry_count"] == 0
    assert summary["manual_resume_count"] == 1

    progress_paths = sorted(results.glob("rerank_hybrid_frozen100_*_progress_2026-11-02.json"))
    assert len(progress_paths) == 5
    assert all(
        len(json.loads(path.read_text(encoding="utf-8"))["rows"]) == 19
        for path in progress_paths
    )
    budget = json.loads(
        (results / "rerank_hybrid_frozen100_budget_2026-11-02.json").read_text(
            encoding="utf-8"
        )
    )
    assert budget["total_tokens"] == summary["total_tokens"]
    assert budget["total_cost_usd"] == summary["total_cost_usd"]
