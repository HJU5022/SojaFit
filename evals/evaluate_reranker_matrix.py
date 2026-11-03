"""Evaluate six fixed embeddings with three API rerankers.

Document vectors and full card text remain outside Git. This script writes only
indices, ranks, metrics, usage, cost and sanitized failures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from backend.rag.retrieve import positive_top, rrf, tokens
from backend.services.llm import (
    cohere_rerank_texts,
    embed_texts,
    rerank_texts,
    voyage_embed_texts,
    voyage_rerank_texts,
)
from evals.run_retrieval import gold_locations


DATASET_SHA256 = "2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b"
CHUNKS_SHA256 = "aa4b9576dfe9a0ac27b178efb9575526e0be4f3442f6f59de328501ebf8871a9"
CARDS = 52_228
UNIQUE_TEXTS = 45_898
QUESTIONS = 19
BRANCH_LIMIT = 50
CANDIDATE_LIMIT = 100
RRF_K = 60

EMBEDDINGS = (
    "text-embedding-3-small",
    "Qwen3-Embedding-0.6B",
    "voyage-4-lite",
    "voyage-4",
    "voyage-4-large",
    "KURE-v1",
)
RERANKERS = (
    "cohere/rerank-4-pro",
    "voyageai/rerank-3",
    "qwen/qwen3-reranker-8b",
)
DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "Qwen3-Embedding-0.6B": 1024,
    "voyage-4-lite": 1024,
    "voyage-4": 1024,
    "voyage-4-large": 1024,
    "KURE-v1": 1024,
}
API_EMBEDDING_IDS = {
    "text-embedding-3-small": "openai/text-embedding-3-small",
    "voyage-4-lite": "voyageai/voyage-4-lite",
    "voyage-4": "voyageai/voyage-4",
    "voyage-4-large": "voyageai/voyage-4-large",
}
LOCAL_EMBEDDING_KEYS = {
    "Qwen3-Embedding-0.6B": "qwen3-embedding-0.6b",
    "KURE-v1": "kure-v1",
}
RERANK_TOKEN_PRICE = {
    "voyageai/rerank-3": 0.05,
    "qwen/qwen3-reranker-8b": 0.20,
}
COHERE_PRICE_PER_SEARCH = 0.0025
COHERE_TRIAL_MIN_INTERVAL_SECONDS = 6.5
_last_cohere_request_started: float | None = None


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def ranking_row(ranking: list[int], item: dict, gold: list, chunks: list[dict]) -> dict:
    gold_docs = {document for document, _ in gold}
    gold_locations_set = set(gold)
    top = ranking[:5]
    top_locations = {(chunks[index]["doc"], chunks[index]["page"]) for index in top}
    rank = next(
        (
            position
            for position, index in enumerate(ranking, 1)
            if chunks[index]["doc"] in gold_docs
        ),
        None,
    )
    return {
        "id": item["id"],
        "rank": rank,
        "page_hit": bool(top_locations & gold_locations_set),
        "all_gold_locations_hit": gold_locations_set <= top_locations,
        "top": [
            {
                "file": chunks[index]["doc"],
                "page": chunks[index]["page"],
                "idx": chunks[index]["idx"],
            }
            for index in top
        ],
    }


def summarize(rows: list[dict]) -> dict:
    count = len(rows)
    return {
        "recall_at_5": sum(
            row["rank"] is not None and row["rank"] <= 5 for row in rows
        )
        / count,
        "mrr": sum(1 / row["rank"] for row in rows if row["rank"]) / count,
        "page_hit_at_5": sum(row["page_hit"] for row in rows) / count,
        "multi_evidence_recall_at_5": sum(
            row["all_gold_locations_hit"] for row in rows
        )
        / count,
    }


def combinations(
    rerankers: tuple[str, ...] = RERANKERS,
    *,
    embeddings: tuple[str, ...] = EMBEDDINGS,
) -> list[tuple[str, str]]:
    return [(embedding, reranker) for embedding in embeddings for reranker in rerankers]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fused_candidates(dense: list[int], keyword: list[int]) -> list[int]:
    return [
        int(index)
        for index, _ in rrf(dense[:BRANCH_LIMIT], keyword[:BRANCH_LIMIT])
    ][:CANDIDATE_LIMIT]


def estimated_token_upper_bound(query: str, documents: list[str]) -> int:
    return math.ceil((len(query) * len(documents) + sum(map(len, documents))) / 2)


def estimated_rerank_costs(usage: dict[str, dict[str, int]]) -> dict[str, float]:
    return {
        reranker: (
            values["searches"] * COHERE_PRICE_PER_SEARCH
            if reranker == "cohere/rerank-4-pro"
            else values["tokens"] / 1_000_000 * RERANK_TOKEN_PRICE[reranker]
        )
        for reranker, values in usage.items()
    }


def summarize_ranks(baseline: dict[str, int | None], reranked: dict[str, int | None]) -> dict:
    ids = list(baseline)
    improved = []
    worsened = []
    for question_id in ids:
        before = baseline[question_id] if baseline[question_id] is not None else math.inf
        after = reranked[question_id] if reranked[question_id] is not None else math.inf
        if after < before:
            improved.append(question_id)
        elif after > before:
            worsened.append(question_id)
    return {
        "baseline_mrr": sum(1 / rank for rank in baseline.values() if rank) / len(ids),
        "reranked_mrr": sum(1 / rank for rank in reranked.values() if rank) / len(ids),
        "improved_count": len(improved),
        "worsened_count": len(worsened),
        "improved_ids": improved,
        "regression_ids": worsened,
    }


def gold_tuples(value: list) -> list[tuple]:
    """Restore tuple locations after a candidate cache JSON round trip."""
    return [tuple(location) for location in value]


def _number(value, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_markdown(rows: list[dict]) -> str:
    header = (
        "| 임베딩 | 리랭커 | status | 기준 Recall@5 | 기준 MRR | 기준 쪽 적중@5 | "
        "기준 다중근거 R@5 | 리랭크 Recall@5 | 리랭크 MRR | ΔMRR | 리랭크 쪽 적중@5 | "
        "리랭크 다중근거 R@5 | p50(ms) | p95(ms) | 토큰 | 비용(USD) | 좋아짐/나빠짐 | 회귀 문항 |\n"
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )
    lines = [header]
    for row in rows:
        baseline = row.get("baseline") or {}
        reranked = row.get("reranked") or {}
        delta = None
        if baseline.get("mrr") is not None and reranked.get("mrr") is not None:
            delta = reranked["mrr"] - baseline["mrr"]
        lines.append(
            "| `{embedding}` | `{reranker}` | {status} | {b_recall} | {b_mrr} | {b_page} | "
            "{b_multi} | {r_recall} | {r_mrr} | {delta} | {r_page} | {r_multi} | {p50} | {p95} | "
            "{tokens} | {cost} | {changed} | {regressions} |".format(
                embedding=row["embedding"],
                reranker=row["reranker"],
                status=row["status"],
                b_recall=_number(baseline.get("recall_at_5")),
                b_mrr=_number(baseline.get("mrr")),
                b_page=_number(baseline.get("page_hit_at_5")),
                b_multi=_number(baseline.get("multi_evidence_recall_at_5")),
                r_recall=_number(reranked.get("recall_at_5")),
                r_mrr=_number(reranked.get("mrr")),
                delta=_number(delta),
                r_page=_number(reranked.get("page_hit_at_5")),
                r_multi=_number(reranked.get("multi_evidence_recall_at_5")),
                p50=_number(row.get("rerank_ms_p50"), 1),
                p95=_number(row.get("rerank_ms_p95"), 1),
                tokens=row.get("tokens", "—"),
                cost=_number(row.get("cost_usd"), 6),
                changed=(
                    f"{row.get('improved_count', '—')}/{row.get('worsened_count', '—')}"
                ),
                regressions=", ".join(row.get("regression_ids") or []) or "—",
            )
        )
    return "\n".join(lines) + "\n"


def load_inputs(chunks_path: Path, dataset_path: Path):
    if file_sha256(chunks_path) != CHUNKS_SHA256:
        raise ValueError("full corpus chunk hash mismatch")
    if file_sha256(dataset_path) != DATASET_SHA256:
        raise ValueError("frozen dataset hash mismatch")
    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line]
    unique_rows = []
    unique_by_sha = {}
    card_to_unique = []
    for row in chunks:
        key = row["sha256"]
        if key not in unique_by_sha:
            unique_by_sha[key] = len(unique_rows)
            unique_rows.append(row)
        card_to_unique.append(unique_by_sha[key])
    if len(chunks) != CARDS or len(unique_rows) != UNIQUE_TEXTS:
        raise ValueError("full corpus card or unique-text count mismatch")
    dataset = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line]
    targets = []
    for item in dataset:
        locations = sorted(set(gold_locations(item["gold_chunks"]))) if item["kind"] == "relevant" else []
        if locations:
            targets.append((item, locations))
    if len(targets) != QUESTIONS:
        raise ValueError("frozen retrieval question count mismatch")
    return chunks, unique_rows, np.asarray(card_to_unique), targets


def parse_vector_args(
    values: list[str], *, required: tuple[str, ...] = EMBEDDINGS
) -> dict[str, Path]:
    parsed = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or name not in EMBEDDINGS:
            raise ValueError(f"invalid --vector mapping: {value}")
        parsed[name] = Path(path)
    missing = set(required) - set(parsed)
    if missing:
        raise ValueError(f"missing vector mappings: {sorted(missing)}")
    return parsed


def _load_vectors(path: Path, embedding: str):
    expected = UNIQUE_TEXTS * DIMENSIONS[embedding] * 4
    if path.stat().st_size != expected:
        raise ValueError(f"vector cache size mismatch for {embedding}")
    return np.memmap(path, dtype=np.float32, mode="r", shape=(UNIQUE_TEXTS, DIMENSIONS[embedding]))


def _query_encoder(embedding: str):
    if embedding in API_EMBEDDING_IDS:
        def encode(text: str):
            return api_query_embedding(embedding, text)

        return encode
    from evals import benchmark_embeddings as benchmark

    spec = benchmark.MODEL_CATALOG[LOCAL_EMBEDDING_KEYS[embedding]]
    model = benchmark.load_local_model(spec)

    def encode(text: str):
        vector = benchmark.encode_role(model, spec, [text], "query", 16)[0]
        return np.asarray(vector, dtype=np.float32), 0, "local-cache", spec.model_id

    return encode


def api_query_embedding(embedding: str, text: str):
    if embedding.startswith("voyage-"):
        vectors, used, provider, actual_model = voyage_embed_texts(
            [text],
            model_id=embedding,
            input_type="query",
            dimensions=DIMENSIONS[embedding],
        )
    else:
        vectors, used, provider, actual_model = embed_texts(
            [text],
            model_id=API_EMBEDDING_IDS[embedding],
            dimensions=DIMENSIONS[embedding],
        )
    return np.asarray(vectors[0], dtype=np.float32), used, provider, actual_model


def rerank_api_call(reranker: str, query: str, documents: list[str], timeout: float = 120):
    if reranker == "cohere/rerank-4-pro":
        return cohere_rerank_texts(
            query,
            documents,
            model_id="rerank-v4.0-pro",
            top_n=len(documents),
            timeout=timeout,
        )
    if reranker == "voyageai/rerank-3":
        return voyage_rerank_texts(
            query,
            documents,
            model_id="rerank-3",
            top_n=len(documents),
            timeout=timeout,
        )
    return rerank_texts(
        query,
        documents,
        model_id=reranker,
        top_n=len(documents),
        timeout=timeout,
    )


def wait_for_cohere_trial_slot(*, monotonic=time.monotonic, sleep=time.sleep) -> None:
    """Keep direct Cohere calls below the trial key's 10 requests/minute limit."""
    global _last_cohere_request_started
    now = monotonic()
    if _last_cohere_request_started is not None:
        delay = COHERE_TRIAL_MIN_INTERVAL_SECONDS - (now - _last_cohere_request_started)
        if delay > 0:
            sleep(delay)
    _last_cohere_request_started = monotonic()


def build_candidates(embedding: str, vectors, chunks, card_to_unique, targets, bm25, output: Path):
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("embedding") == embedding and cached.get("chunks_sha256") == CHUNKS_SHA256:
            return cached
    encode = _query_encoder(embedding)
    ids = np.arange(len(chunks))
    rows = []
    for item, gold in targets:
        question = item.get("question") or item["input"]
        query, used, provider, actual_model = encode(question)
        norm = np.linalg.norm(query)
        if norm == 0:
            raise ValueError("zero query embedding")
        query /= norm
        dense_scores = np.asarray(vectors) @ query
        card_scores = dense_scores[card_to_unique]
        dense = [int(index) for index in np.argsort(-card_scores, kind="stable")[:BRANCH_LIMIT]]
        keyword = [int(index) for index in positive_top(bm25.get_scores(tokens(question)), ids, BRANCH_LIMIT)]
        candidates = fused_candidates(dense, keyword)
        baseline = ranking_row(candidates[:5], item, gold, chunks)
        rows.append(
            {
                "id": item["id"],
                "question": question,
                "gold": gold,
                "candidates": candidates,
                "baseline": baseline,
                "query_tokens": used,
                "embedding_provider": provider,
                "embedding_api_model": actual_model,
            }
        )
    result = {"embedding": embedding, "chunks_sha256": CHUNKS_SHA256, "rows": rows}
    atomic_json(output, result)
    return result


def build_candidates_from_query_vectors(
    embedding: str,
    vectors,
    query_vectors,
    chunks,
    card_to_unique,
    targets,
    bm25,
    output: Path,
):
    if len(query_vectors) != len(targets):
        raise ValueError("query vector count mismatch")
    ids = np.arange(len(chunks))
    rows = []
    for (item, gold), raw_query in zip(targets, query_vectors, strict=True):
        question = item.get("question") or item["input"]
        query = np.asarray(raw_query, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm == 0:
            raise ValueError("zero query embedding")
        query /= norm
        dense_scores = np.asarray(vectors) @ query
        card_scores = dense_scores[card_to_unique]
        dense = [int(index) for index in np.argsort(-card_scores, kind="stable")[:BRANCH_LIMIT]]
        keyword = [int(index) for index in positive_top(bm25.get_scores(tokens(question)), ids, BRANCH_LIMIT)]
        candidates = fused_candidates(dense, keyword)
        rows.append(
            {
                "id": item["id"],
                "question": question,
                "gold": gold,
                "candidates": candidates,
                "baseline": ranking_row(candidates[:5], item, gold, chunks),
                "query_tokens": 0,
                "embedding_provider": "local-cache",
                "embedding_api_model": embedding,
            }
        )
    result = {"embedding": embedding, "chunks_sha256": CHUNKS_SHA256, "rows": rows}
    atomic_json(output, result)
    return result


def preflight_usage(
    candidate_sets: dict[str, dict],
    chunks: list[dict],
    rerankers: tuple[str, ...] = RERANKERS,
) -> dict:
    tokens_per_embedding = {}
    for embedding, candidate_set in candidate_sets.items():
        total = 0
        for row in candidate_set["rows"]:
            documents = [chunks[index]["text"] for index in row["candidates"]]
            total += estimated_token_upper_bound(row["question"], documents)
        tokens_per_embedding[embedding] = total
    total_tokens = sum(tokens_per_embedding.values())
    usage = {
        reranker: {"tokens": total_tokens, "searches": len(candidate_sets) * QUESTIONS}
        for reranker in rerankers
    }
    costs = estimated_rerank_costs(usage)
    return {
        "tokens_per_embedding": tokens_per_embedding,
        "usage": usage,
        "costs_usd": costs,
        "total_rerank_cost_usd": sum(costs.values()),
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def evaluate_combination(embedding: str, reranker: str, candidate_set: dict, chunks: list[dict], output: Path):
    progress = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.exists()
        else {"embedding": embedding, "reranker": reranker, "rows": []}
    )
    completed = {row["id"] for row in progress["rows"]}
    for source in candidate_set["rows"]:
        if source["id"] in completed:
            continue
        candidates = source["candidates"]
        documents = [chunks[index]["text"] for index in candidates]
        if reranker == "cohere/rerank-4-pro":
            wait_for_cohere_trial_slot()
        started = time.perf_counter()
        ranked, used, provider, actual_model = rerank_api_call(
            reranker, source["question"], documents, timeout=120
        )
        latency_ms = (time.perf_counter() - started) * 1000
        reranked_indices = [candidates[row["index"]] for row in ranked]
        item = {"id": source["id"]}
        final = ranking_row(reranked_indices[:5], item, gold_tuples(source["gold"]), chunks)
        estimated_tokens = estimated_token_upper_bound(source["question"], documents)
        progress["rows"].append(
            {
                "id": source["id"],
                "baseline": source["baseline"],
                "reranked": final,
                "tokens": used,
                "estimated_tokens": estimated_tokens,
                "rerank_ms": latency_ms,
                "provider": provider,
                "api_model": actual_model,
            }
        )
        atomic_json(output, progress)
    if len(progress["rows"]) != QUESTIONS:
        raise RuntimeError("combination did not complete all questions")
    baseline_rows = [row["baseline"] for row in progress["rows"]]
    reranked_rows = [row["reranked"] for row in progress["rows"]]
    rank_summary = summarize_ranks(
        {row["id"]: row["rank"] for row in baseline_rows},
        {row["id"]: row["rank"] for row in reranked_rows},
    )
    tokens_used = sum(row["tokens"] or row["estimated_tokens"] for row in progress["rows"])
    cost = (
        QUESTIONS * COHERE_PRICE_PER_SEARCH
        if reranker == "cohere/rerank-4-pro"
        else tokens_used / 1_000_000 * RERANK_TOKEN_PRICE[reranker]
    )
    latencies = [row["rerank_ms"] for row in progress["rows"]]
    return {
        "embedding": embedding,
        "reranker": reranker,
        "status": "ok",
        "baseline": summarize(baseline_rows),
        "reranked": summarize(reranked_rows),
        **rank_summary,
        "rerank_ms_p50": statistics.median(latencies),
        "rerank_ms_p95": _percentile(latencies, 0.95),
        "tokens": tokens_used,
        "cost_usd": cost,
        "retry_count": 0,
    }


def sanitized_failure(embedding: str, reranker: str, error: Exception) -> dict:
    message = str(error)
    return {
        "embedding": embedding,
        "reranker": reranker,
        "status": "error",
        "baseline": {},
        "reranked": {},
        "error_type": type(error).__name__,
        "error_message": message[:200],
        "retry_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("evals/dataset_v1.jsonl"))
    parser.add_argument("--vector", action="append", default=[], help="EMBEDDING=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cost-ceiling", type=float, default=5.0)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--stop-on-first-error", action="store_true")
    parser.add_argument("--embedding", action="append", choices=EMBEDDINGS, default=[])
    parser.add_argument("--reranker", action="append", choices=RERANKERS, default=[])
    parser.add_argument(
        "--base-summary",
        type=Path,
        help="Existing 18-row summary whose selected reranker rows will be replaced",
    )
    args = parser.parse_args()
    selected_embeddings = tuple(args.embedding) or EMBEDDINGS
    selected_rerankers = tuple(args.reranker) or RERANKERS
    vector_paths = parse_vector_args(args.vector, required=selected_embeddings)
    chunks, _, card_to_unique, targets = load_inputs(args.chunks, args.dataset)
    bm25 = BM25Okapi([tokens(row["text"]) for row in chunks])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_sets = {}
    for embedding in selected_embeddings:
        vectors = _load_vectors(vector_paths[embedding], embedding)
        candidate_sets[embedding] = build_candidates(
            embedding,
            vectors,
            chunks,
            card_to_unique,
            targets,
            bm25,
            args.output_dir / f"candidates-{embedding}.json",
        )
    preflight = preflight_usage(candidate_sets, chunks, selected_rerankers)
    preflight["cost_ceiling_usd"] = args.cost_ceiling
    preflight["within_ceiling"] = preflight["total_rerank_cost_usd"] <= args.cost_ceiling
    atomic_json(args.output_dir / "preflight.json", preflight)
    if not preflight["within_ceiling"]:
        raise RuntimeError("preflight rerank cost exceeds the approved ceiling")
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False))
        return
    selected_rows = []
    for embedding, reranker in combinations(
        selected_rerankers, embeddings=selected_embeddings
    ):
        path = args.output_dir / f"progress-{embedding}-{reranker.replace('/', '__')}.json"
        failure_path = path.with_suffix(".failure.json")
        if failure_path.exists():
            selected_rows.append(json.loads(failure_path.read_text(encoding="utf-8")))
            atomic_json(args.output_dir / "selected-summary.json", {"rows": selected_rows})
            if args.stop_on_first_error:
                break
            continue
        try:
            row = evaluate_combination(embedding, reranker, candidate_sets[embedding], chunks, path)
        except Exception as error:
            row = sanitized_failure(embedding, reranker, error)
            atomic_json(failure_path, row)
        selected_rows.append(row)
        atomic_json(args.output_dir / "selected-summary.json", {"rows": selected_rows})
        if row["status"] == "error" and args.stop_on_first_error:
            break
    if args.base_summary:
        base_rows = json.loads(args.base_summary.read_text(encoding="utf-8"))["rows"]
        merged = {(row["embedding"], row["reranker"]): row for row in base_rows}
        merged.update({(row["embedding"], row["reranker"]): row for row in selected_rows})
        rows = [merged[pair] for pair in combinations()]
    else:
        rows = selected_rows
    atomic_json(args.output_dir / "summary.json", {"rows": rows})
    markdown = render_markdown(rows)
    (args.output_dir / "results.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"rows": len(rows), "ok": sum(row["status"] == "ok" for row in rows)}))


if __name__ == "__main__":
    main()
