import json
from pathlib import Path

from evals import evaluate_frozen_embedding_sample as sample


ROOT = Path(__file__).parents[1]


def test_managed_api_candidate_set_and_dimensions_are_fixed():
    assert set(sample.MODELS) == {
        "openai/text-embedding-3-small",
        "baai/bge-m3",
        "voyageai/voyage-4-lite",
        "voyageai/voyage-4",
        "qwen/qwen3-embedding-8b",
        "intfloat/multilingual-e5-large",
        "perplexity/pplx-embed-v1-0.6b",
        "amazon/titan-embed-text-v2",
    }
    assert sample.MODELS["openai/text-embedding-3-small"].dimension == 1536
    assert all(
        spec.dimension == 1024
        for model, spec in sample.MODELS.items()
        if model != "openai/text-embedding-3-small"
    )


def test_model_specific_query_and_document_formats_are_explicit():
    qwen = sample.prepare_texts("qwen/qwen3-embedding-8b", ["질문"], "query")
    assert qwen == [f"Instruct: {sample.QWEN_INSTRUCTION}\nQuery: 질문"]
    assert sample.prepare_texts(
        "intfloat/multilingual-e5-large", ["질문"], "query"
    ) == ["query: 질문"]
    assert sample.prepare_texts(
        "intfloat/multilingual-e5-large", ["passage"], "document"
    ) == ["passage: passage"]
    assert sample.embedding_options(
        "perplexity/pplx-embed-v1-0.6b", "document"
    ) == {"input_type": "document", "dimensions": 1024}
    assert sample.embedding_options("baai/bge-m3", "query") == {
        "input_type": None,
        "dimensions": None,
    }


def test_retrieval_metrics_keep_document_page_and_multi_evidence_separate():
    rows = [
        {"rank": 1, "page_hit": True, "all_gold_locations_hit": False},
        {"rank": None, "page_hit": False, "all_gold_locations_hit": False},
    ]
    assert sample.summarize(rows) == {
        "recall_at_5": 0.5,
        "mrr": 0.5,
        "page_hit_at_5": 0.5,
        "multi_evidence_recall_at_5": 0.0,
    }


def test_public_error_messages_drop_provider_request_ids():
    assert sample.sanitized_error(
        RuntimeError('HTTP 429 {"request_id":"secret-like-id"} overloaded')
    ) == "provider returned HTTP 429 overload"
    assert sample.sanitized_error(
        RuntimeError("endpoint excluded by ZDR data policy")
    ) == "endpoint blocked by configured ZDR/data-policy guardrails"


def test_published_success_metrics_recompute_from_per_query_rows():
    paths = sorted(
        (ROOT / "evals" / "results").glob(
            "embedding_hybrid_frozen100_*_2026-11-02.json"
        )
    )
    success = 0
    for path in paths:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        if result.get("status") != "ok" or "rows" not in result:
            continue
        success += 1
        assert {
            name: sample.summarize(rows) for name, rows in result["rows"].items()
        } == result["metrics"]
    assert success == 5


def test_published_sample_hashes_match_frozen_contract():
    dataset = ROOT / "evals" / "dataset_v1.jsonl"
    selection = ROOT / "evals" / "results" / (
        "embedding_hybrid_frozen100_selection_2026-11-02.json"
    )
    metadata = json.loads(selection.read_text(encoding="utf-8"))
    assert sample.file_sha256(dataset) == sample.DATASET_SHA256
    assert metadata["dataset_sha256"] == sample.DATASET_SHA256
    assert metadata["chunks_sha256"] == sample.SAMPLE_CHUNKS_SHA256
    assert metadata["documents"] == sample.SAMPLE_DOCUMENTS


def test_published_summary_matches_model_results_and_budget():
    results = ROOT / "evals" / "results"
    summary = json.loads(
        (results / "embedding_hybrid_frozen100_summary_2026-11-02.json").read_text(
            encoding="utf-8-sig"
        )
    )
    budget = json.loads(
        (results / "embedding_hybrid_frozen100_budget_2026-11-02.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["budget_ledger"] == budget
    for row in summary["results"]:
        slug = row["model"].replace("/", "-")
        result = json.loads(
            (
                results
                / f"embedding_hybrid_frozen100_{slug}_2026-11-02.json"
            ).read_text(encoding="utf-8-sig")
        )
        assert result["status"] == row["status"]
        if row["status"] == "ok":
            assert result["metrics"]["dense"]["recall_at_5"] == row[
                "dense_recall_at_5"
            ]
            assert result["metrics"]["hybrid"]["recall_at_5"] == row[
                "hybrid_recall_at_5"
            ]
            assert result["metrics"]["hybrid"]["mrr"] == row["hybrid_mrr"]
