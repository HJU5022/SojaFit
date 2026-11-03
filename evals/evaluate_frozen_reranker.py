"""Evaluate one fixed API reranker on the frozen 100-document sample.

The private card body and vector caches stay outside Git. Public results contain
only hashes, ranks, metrics, latency, usage and cost. The experiment reuses the
same BM25/dense/RRF contract as evaluate_frozen_embedding_sample.py.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from backend.rag.retrieve import positive_top, rrf, tokens
from backend.services.llm import rerank_texts
from evals.evaluate_frozen_embedding_sample import (
    DATASET_SHA256,
    MODELS,
    RETRIEVAL_QUESTIONS,
    SAMPLE_CARDS,
    SAMPLE_CHUNKS_SHA256,
    SAMPLE_DOCUMENTS,
    SAMPLE_UNIQUE_TEXTS,
    atomic_json,
    call_embedding,
    load_inputs,
    ranking_row,
    sanitized_error,
    summarize,
    update_ledger,
)


SUCCESS_MODELS = (
    "qwen/qwen3-embedding-8b",
    "perplexity/pplx-embed-v1-0.6b",
    "openai/text-embedding-3-small",
    "intfloat/multilingual-e5-large",
    "amazon/titan-embed-text-v2",
)
RERANK_MODEL = "qwen/qwen3-reranker-8b"
RERANK_PRICE_PER_MILLION_USD = 0.20
BRANCH_LIMIT = 50
CANDIDATE_LIMIT = 50


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def fused_candidates(dense: list[int], keyword: list[int]) -> tuple[list[int], list[int]]:
    """Return the full RRF union and its fixed top-50 rerank candidates."""
    hybrid = [int(index) for index, _ in rrf(dense[:BRANCH_LIMIT], keyword[:BRANCH_LIMIT])]
    return hybrid, hybrid[:CANDIDATE_LIMIT]


def candidate_row(ranking: list[int], item: dict, gold: list, chunks: list[dict]) -> dict:
    row = ranking_row(ranking, item, gold, chunks)
    row["candidate_count"] = len(ranking)
    row["hit_at_50"] = row["rank"] is not None and row["rank"] <= CANDIDATE_LIMIT
    return row


def top5_metric_row(ranking: list[int], item: dict, gold: list, chunks: list[dict]) -> dict:
    """Keep MRR on the same final top-5 scope as the published baseline."""
    return ranking_row(ranking[:5], item, gold, chunks)


def estimated_token_upper_bound(query: str, documents: list[str]) -> int:
    """Conservative preflight only; billed usage comes from the API response."""
    return math.ceil((len(query) * len(documents) + sum(map(len, documents))) / 2)


def reranked_indices(query: str, candidates: list[int], chunks: list[dict]):
    documents = [chunks[index]["text"] for index in candidates]
    started = time.perf_counter()
    rows, used, provider, api_model = rerank_texts(
        query,
        documents,
        model_id=RERANK_MODEL,
        top_n=len(documents),
    )
    latency_ms = (time.perf_counter() - started) * 1000
    return [candidates[row["index"]] for row in rows], used, provider, api_model, latency_ms


def load_progress(path: Path, model_id: str) -> dict:
    if not path.exists():
        return {
            "model": model_id,
            "reranker": RERANK_MODEL,
            "dataset_sha256": DATASET_SHA256,
            "chunks_sha256": SAMPLE_CHUNKS_SHA256,
            "rows": [],
        }
    progress = json.loads(path.read_text(encoding="utf-8"))
    expected = (model_id, RERANK_MODEL, DATASET_SHA256, SAMPLE_CHUNKS_SHA256)
    actual = (
        progress.get("model"),
        progress.get("reranker"),
        progress.get("dataset_sha256"),
        progress.get("chunks_sha256"),
    )
    if actual != expected:
        raise ValueError("rerank progress contract mismatch")
    for row in progress["rows"]:
        for name in ("bm25", "dense", "hybrid", "reranked"):
            if row[name]["rank"] is not None and row[name]["rank"] > 5:
                row[name]["rank"] = None
    return progress


def run(args) -> dict:
    model_id = args.model
    spec = MODELS[model_id]
    chunks, unique_rows, card_to_unique, targets = load_inputs(
        args.chunks, args.dataset, args.selection
    )
    expected_bytes = SAMPLE_UNIQUE_TEXTS * spec.dimension * 4
    if args.vectors.stat().st_size != expected_bytes:
        raise ValueError("vector cache size mismatch")
    vectors = np.memmap(
        args.vectors,
        dtype=np.float32,
        mode="r",
        shape=(len(unique_rows), spec.dimension),
    )
    bm25 = BM25Okapi([tokens(row["text"]) for row in chunks])
    ids = np.arange(len(chunks))
    progress = load_progress(args.progress, model_id)
    progress["manual_resume_count"] = args.manual_resume_count
    atomic_json(args.progress, progress)
    completed = {row["id"] for row in progress["rows"]}

    for item, gold in targets:
        if item["id"] in completed:
            continue
        question = item.get("question") or item["input"]
        query_started = time.perf_counter()
        query_vectors, query_tokens, embedding_provider, embedding_api_model = call_embedding(
            model_id, [question], "query"
        )
        query_latency_ms = (time.perf_counter() - query_started) * 1000
        query = query_vectors[0]
        norm = np.linalg.norm(query)
        if norm == 0:
            raise ValueError("zero query embedding")
        query /= norm
        embedding_cost = query_tokens / 1_000_000 * spec.price_per_million_usd
        update_ledger(
            args.ledger,
            model_id,
            query_tokens,
            embedding_cost,
            args.total_cost_ceiling,
        )

        dense_scores = np.asarray(vectors) @ query
        card_scores = dense_scores[card_to_unique]
        dense = [int(index) for index in np.argsort(-card_scores, kind="stable")]
        keyword = [
            int(index)
            for index in positive_top(bm25.get_scores(tokens(question)), ids, BRANCH_LIMIT)
        ]
        hybrid, candidates = fused_candidates(dense, keyword)
        documents = [chunks[index]["text"] for index in candidates]
        estimated_tokens = estimated_token_upper_bound(question, documents)
        estimated_cost = estimated_tokens / 1_000_000 * RERANK_PRICE_PER_MILLION_USD
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        if ledger["total_cost_usd"] + estimated_cost > args.total_cost_ceiling:
            raise RuntimeError("preflight rerank cost would exceed the approved ceiling")

        reranked, rerank_tokens, rerank_provider, rerank_api_model, rerank_ms = reranked_indices(
            question, candidates, chunks
        )
        rerank_cost = rerank_tokens / 1_000_000 * RERANK_PRICE_PER_MILLION_USD
        update_ledger(
            args.ledger,
            RERANK_MODEL,
            rerank_tokens,
            rerank_cost,
            args.total_cost_ceiling,
        )
        progress["rows"].append(
            {
                "id": item["id"],
                "bm25": top5_metric_row(keyword, item, gold, chunks),
                "dense": top5_metric_row(dense, item, gold, chunks),
                "hybrid": top5_metric_row(hybrid, item, gold, chunks),
                "candidate": candidate_row(candidates, item, gold, chunks),
                "reranked": top5_metric_row(reranked, item, gold, chunks),
                "query_embedding_tokens": query_tokens,
                "query_embedding_cost_usd": embedding_cost,
                "query_embedding_ms": query_latency_ms,
                "embedding_provider": embedding_provider,
                "embedding_api_model": embedding_api_model,
                "rerank_tokens": rerank_tokens,
                "rerank_cost_usd": rerank_cost,
                "rerank_ms": rerank_ms,
                "rerank_provider": rerank_provider,
                "rerank_api_model": rerank_api_model,
            }
        )
        atomic_json(args.progress, progress)

    if len(progress["rows"]) != RETRIEVAL_QUESTIONS:
        raise RuntimeError("rerank evaluation did not complete all frozen retrieval questions")
    groups = {
        name: [row[name] for row in progress["rows"]]
        for name in ("bm25", "dense", "hybrid", "reranked")
    }
    candidate_rows = [row["candidate"] for row in progress["rows"]]
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    rerank_latencies = [row["rerank_ms"] for row in progress["rows"]]
    return {
        "status": "ok",
        "evaluation_level": "frozen_100_document_sample",
        "decision_support": True,
        "formal_full_corpus_evaluation": False,
        "embedding_model": model_id,
        "reranker": RERANK_MODEL,
        "dataset_sha256": DATASET_SHA256,
        "chunks_sha256": SAMPLE_CHUNKS_SHA256,
        "documents": SAMPLE_DOCUMENTS,
        "cards": SAMPLE_CARDS,
        "unique_texts": SAMPLE_UNIQUE_TEXTS,
        "questions": RETRIEVAL_QUESTIONS,
        "branch_limit": BRANCH_LIMIT,
        "rerank_candidate_limit": CANDIDATE_LIMIT,
        "candidate_hit_at_50": sum(row["hit_at_50"] for row in candidate_rows) / len(candidate_rows),
        "metrics": {name: summarize(rows) for name, rows in groups.items()},
        "rerank_api_ms_p50": statistics.median(rerank_latencies),
        "rerank_api_ms_p95": percentile(rerank_latencies, 0.95),
        "query_embedding_tokens": sum(row["query_embedding_tokens"] for row in progress["rows"]),
        "rerank_tokens": sum(row["rerank_tokens"] for row in progress["rows"]),
        "incremental_cost_usd": sum(
            row["query_embedding_cost_usd"] + row["rerank_cost_usd"]
            for row in progress["rows"]
        ),
        "budget_ledger": ledger,
        "rows": progress["rows"],
        "retry_count": 0,
        "manual_resume_count": args.manual_resume_count,
        "public_artifact_note": "card text, vectors, request ids, and raw provider responses are excluded",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=SUCCESS_MODELS, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("evals/dataset_v1.jsonl"))
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("evals/results/embedding_hybrid_frozen100_selection_2026-11-02.json"),
    )
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--total-cost-ceiling", type=float, default=0.50)
    parser.add_argument("--manual-resume-count", type=int, default=0)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as error:
        no_key = "api key" in sanitized_error(error).lower()
        result = {
            "status": "not_run_no_key" if no_key else "error",
            "evaluation_level": "frozen_100_document_sample",
            "decision_support": False,
            "formal_full_corpus_evaluation": False,
            "embedding_model": args.model,
            "reranker": RERANK_MODEL,
            "error_type": type(error).__name__,
            "error_message": sanitized_error(error),
            "retry_count": 0,
            "manual_resume_count": args.manual_resume_count,
        }
    atomic_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
