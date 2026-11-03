"""Evaluate managed embedding APIs on the frozen 100-document TSC sample.

The card body input and vector cache stay outside Git. Public artifacts contain
only selection metadata, hashes, ranks, metrics, latency, token usage and cost.
This is a post-hoc sample comparison, not the preregistered 1,360-document run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from backend.rag.retrieve import positive_top, rrf, tokens
from backend.services.llm import embed_texts
from evals.run_retrieval import gold_locations


DATASET_SHA256 = "2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b"
SAMPLE_CHUNKS_SHA256 = "0b4c81ee9bf64120a07ff7f5dd3fc766f1215ffe7076440d56733c95eab8d030"
SAMPLE_DOCUMENTS = 100
SAMPLE_CARDS = 4305
SAMPLE_UNIQUE_TEXTS = 4056
RETRIEVAL_QUESTIONS = 19
QWEN_INSTRUCTION = (
    "Given a Korean electronics engineering query, retrieve the English "
    "datasheet passage containing the exact part number, electrical rating, "
    "package, test condition, or replacement constraint."
)


@dataclass(frozen=True)
class ApiModel:
    dimension: int
    price_per_million_usd: float
    input_type: bool = False
    query_prefix: str = ""
    document_prefix: str = ""
    qwen_instruction: bool = False
    omit_dimensions: bool = False


MODELS = {
    "openai/text-embedding-3-small": ApiModel(1536, 0.02),
    "baai/bge-m3": ApiModel(1024, 0.01, omit_dimensions=True),
    "voyageai/voyage-4-lite": ApiModel(1024, 0.02, input_type=True),
    "voyageai/voyage-4": ApiModel(1024, 0.06, input_type=True),
    "qwen/qwen3-embedding-8b": ApiModel(1024, 0.01, qwen_instruction=True),
    "intfloat/multilingual-e5-large": ApiModel(
        1024, 0.01, query_prefix="query: ", document_prefix="passage: "
    ),
    "perplexity/pplx-embed-v1-0.6b": ApiModel(1024, 0.004, input_type=True),
    "amazon/titan-embed-text-v2": ApiModel(1024, 0.02),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def prepare_texts(model_id: str, texts: list[str], role: str) -> list[str]:
    if role not in {"query", "document"}:
        raise ValueError(f"invalid embedding role: {role}")
    spec = MODELS[model_id]
    if role == "query" and spec.qwen_instruction:
        return [f"Instruct: {QWEN_INSTRUCTION}\nQuery: {text}" for text in texts]
    prefix = spec.query_prefix if role == "query" else spec.document_prefix
    return [prefix + text for text in texts]


def embedding_options(model_id: str, role: str) -> dict:
    spec = MODELS[model_id]
    return {
        "input_type": role if spec.input_type else None,
        "dimensions": None if spec.omit_dimensions else spec.dimension,
    }


def call_embedding(model_id: str, texts: list[str], role: str):
    options = embedding_options(model_id, role)
    vectors, used, provider, api_model = embed_texts(
        prepare_texts(model_id, texts, role),
        model_id=model_id,
        input_type=options["input_type"],
        dimensions=options["dimensions"],
    )
    return np.asarray(vectors, dtype=np.float32), int(used), provider, api_model


def load_inputs(chunks_path: Path, dataset_path: Path, selection_path: Path):
    if file_sha256(chunks_path) != SAMPLE_CHUNKS_SHA256:
        raise ValueError("100-document chunk hash mismatch")
    if file_sha256(dataset_path) != DATASET_SHA256:
        raise ValueError("frozen dataset hash mismatch")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection["dataset_sha256"] != DATASET_SHA256:
        raise ValueError("selection dataset hash mismatch")
    if selection["chunks_sha256"] != SAMPLE_CHUNKS_SHA256:
        raise ValueError("selection chunk hash mismatch")
    if selection["documents"] != SAMPLE_DOCUMENTS:
        raise ValueError("selection document count mismatch")

    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line]
    unique_rows: list[dict] = []
    unique_by_sha: dict[str, int] = {}
    card_to_unique: list[int] = []
    for row in chunks:
        key = row["sha256"]
        if key not in unique_by_sha:
            unique_by_sha[key] = len(unique_rows)
            unique_rows.append(row)
        card_to_unique.append(unique_by_sha[key])
    if len(chunks) != SAMPLE_CARDS or len(unique_rows) != SAMPLE_UNIQUE_TEXTS:
        raise ValueError(f"sample contract mismatch: cards={len(chunks)}, unique={len(unique_rows)}")

    dataset = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line]
    targets = []
    for row in dataset:
        locations = sorted(set(gold_locations(row["gold_chunks"]))) if row["kind"] == "relevant" else []
        if locations:
            targets.append((row, locations))
    if len(dataset) != 50 or len(targets) != RETRIEVAL_QUESTIONS:
        raise ValueError(f"dataset contract mismatch: rows={len(dataset)}, targets={len(targets)}")
    return chunks, unique_rows, np.asarray(card_to_unique), targets


def update_ledger(path: Path, model_id: str, tokens_used: int, cost: float, cost_ceiling: float) -> None:
    ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "models": {},
    }
    next_cost = ledger["total_cost_usd"] + cost
    if next_cost > cost_ceiling:
        raise RuntimeError(f"approved cost ceiling would be exceeded: {next_cost:.6f} > {cost_ceiling}")
    ledger["total_tokens"] += tokens_used
    ledger["total_cost_usd"] = next_cost
    model = ledger["models"].setdefault(model_id, {"tokens": 0, "cost_usd": 0.0})
    model["tokens"] += tokens_used
    model["cost_usd"] += cost
    atomic_json(path, ledger)


def embed_documents(model_id: str, texts: list[str], work_dir: Path, batch_size: int, token_ceiling: int, cost_ceiling: float, ledger_path: Path):
    spec = MODELS[model_id]
    model_dir = work_dir / model_id.replace("/", "__")
    model_dir.mkdir(parents=True, exist_ok=True)
    vector_path = model_dir / "vectors.f32"
    progress_path = model_dir / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {
        "next_index": 0,
        "tokens": 0,
        "cost_usd": 0.0,
        "seconds": 0.0,
    }
    mode = "r+" if vector_path.exists() else "w+"
    vectors = np.memmap(vector_path, dtype=np.float32, mode=mode, shape=(len(texts), spec.dimension))
    provider = None
    api_model = None
    for start in range(progress["next_index"], len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        started = time.perf_counter()
        batch, used, provider, api_model = call_embedding(model_id, texts[start:end], "document")
        elapsed = time.perf_counter() - started
        if batch.shape != (end - start, spec.dimension):
            raise ValueError(f"unexpected embedding shape: {batch.shape}")
        norms = np.linalg.norm(batch, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError("zero document embedding")
        batch /= norms
        next_tokens = progress["tokens"] + used
        if next_tokens > token_ceiling:
            raise RuntimeError(f"model token ceiling exceeded: {next_tokens} > {token_ceiling}")
        cost = used / 1_000_000 * spec.price_per_million_usd
        update_ledger(ledger_path, model_id, used, cost, cost_ceiling)
        vectors[start:end] = batch
        vectors.flush()
        progress = {
            "next_index": end,
            "tokens": next_tokens,
            "cost_usd": progress["cost_usd"] + cost,
            "seconds": progress["seconds"] + elapsed,
        }
        atomic_json(progress_path, progress)
    return vectors, progress, provider, api_model


def ranking_row(ranking: list[int], item: dict, gold: list, chunks: list[dict]) -> dict:
    gold_docs = {document for document, _ in gold}
    gold_locations_set = set(gold)
    top = ranking[:5]
    top_locations = {(chunks[index]["doc"], chunks[index]["page"]) for index in top}
    rank = next((position for position, index in enumerate(ranking, 1) if chunks[index]["doc"] in gold_docs), None)
    return {
        "id": item["id"],
        "rank": rank,
        "page_hit": bool(top_locations & gold_locations_set),
        "all_gold_locations_hit": gold_locations_set <= top_locations,
        "top": [
            {"file": chunks[index]["doc"], "page": chunks[index]["page"], "idx": chunks[index]["idx"]}
            for index in top
        ],
    }


def summarize(rows: list[dict]) -> dict:
    count = len(rows)
    return {
        "recall_at_5": sum(row["rank"] is not None and row["rank"] <= 5 for row in rows) / count,
        "mrr": sum(1 / row["rank"] for row in rows if row["rank"]) / count,
        "page_hit_at_5": sum(row["page_hit"] for row in rows) / count,
        "multi_evidence_recall_at_5": sum(row["all_gold_locations_hit"] for row in rows) / count,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def evaluate_queries(model_id: str, vectors, chunks: list[dict], card_to_unique: np.ndarray, targets: list, ledger_path: Path, cost_ceiling: float):
    spec = MODELS[model_id]
    bm25 = BM25Okapi([tokens(row["text"]) for row in chunks])
    ids = np.arange(len(chunks))
    rows = {"bm25": [], "dense": [], "hybrid": []}
    query_api_ms = []
    retrieval_local_ms = []
    query_tokens = 0
    query_cost = 0.0
    provider = None
    api_model = None
    for item, gold in targets:
        question = item.get("question") or item["input"]
        started = time.perf_counter()
        query_vectors, used, provider, api_model = call_embedding(model_id, [question], "query")
        query_api_ms.append((time.perf_counter() - started) * 1000)
        query = query_vectors[0]
        norm = np.linalg.norm(query)
        if norm == 0:
            raise ValueError("zero query embedding")
        query /= norm
        cost = used / 1_000_000 * spec.price_per_million_usd
        update_ledger(ledger_path, model_id, used, cost, cost_ceiling)
        query_tokens += used
        query_cost += cost

        started = time.perf_counter()
        dense_scores = np.asarray(vectors) @ query
        card_scores = dense_scores[card_to_unique]
        dense = [int(index) for index in np.argsort(-card_scores, kind="stable")]
        keyword = [int(index) for index in positive_top(bm25.get_scores(tokens(question)), ids, 50)]
        hybrid = [int(index) for index, _ in rrf(dense[:50], keyword)]
        retrieval_local_ms.append((time.perf_counter() - started) * 1000)
        for name, ranking in (("bm25", keyword), ("dense", dense), ("hybrid", hybrid)):
            rows[name].append(ranking_row(ranking, item, gold, chunks))
    return {
        "metrics": {name: summarize(group) for name, group in rows.items()},
        "rows": rows,
        "query_tokens": query_tokens,
        "query_cost_usd": query_cost,
        "query_api_ms_p50": statistics.median(query_api_ms),
        "query_api_ms_p95": percentile(query_api_ms, 0.95),
        "retrieval_local_ms_p50": statistics.median(retrieval_local_ms),
        "provider": provider,
        "api_model": api_model,
    }


def sanitized_error(error: Exception) -> str:
    message = str(error).lower()
    if "zdr" in message or "data policy" in message:
        return "endpoint blocked by configured ZDR/data-policy guardrails"
    if "429" in message or "overloaded" in message:
        return "provider returned HTTP 429 overload"
    if "api_key" in message or "api key" in message:
        return "required API key is not configured"
    return str(error)[:200]


def run(args) -> dict:
    model_id = args.model
    spec = MODELS[model_id]
    chunks, unique_rows, card_to_unique, targets = load_inputs(args.chunks, args.dataset, args.selection)
    ledger_path = args.work_dir / "budget_ledger.json"
    started = time.perf_counter()
    vectors, progress, provider, api_model = embed_documents(
        model_id,
        [row["text"] for row in unique_rows],
        args.work_dir,
        args.batch_size,
        args.token_ceiling,
        args.total_cost_ceiling,
        ledger_path,
    )
    query_result = evaluate_queries(
        model_id, vectors, chunks, card_to_unique, targets, ledger_path, args.total_cost_ceiling
    )
    total_tokens = progress["tokens"] + query_result["query_tokens"]
    total_cost = progress["cost_usd"] + query_result["query_cost_usd"]
    return {
        "status": "ok",
        "evaluation_level": "frozen_100_document_sample",
        "decision_support": True,
        "formal_full_corpus_evaluation": False,
        "model": model_id,
        "provider": query_result["provider"] or provider,
        "api_model": query_result["api_model"] or api_model,
        "dimension": spec.dimension,
        "dataset_sha256": DATASET_SHA256,
        "chunks_sha256": SAMPLE_CHUNKS_SHA256,
        "documents": SAMPLE_DOCUMENTS,
        "cards": SAMPLE_CARDS,
        "unique_texts": SAMPLE_UNIQUE_TEXTS,
        "questions": RETRIEVAL_QUESTIONS,
        "document_tokens": progress["tokens"],
        "query_tokens": query_result["query_tokens"],
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "document_seconds": progress["seconds"],
        "normalized_1000_chunk_seconds": progress["seconds"] / SAMPLE_UNIQUE_TEXTS * 1000,
        "normalized_1000_chunk_cost_usd": progress["cost_usd"] / SAMPLE_UNIQUE_TEXTS * 1000,
        "query_api_ms_p50": query_result["query_api_ms_p50"],
        "query_api_ms_p95": query_result["query_api_ms_p95"],
        "retrieval_local_ms_p50": query_result["retrieval_local_ms_p50"],
        "vector_payload_22000_float32_mib": 22000 * spec.dimension * 4 / 1024**2,
        "metrics": query_result["metrics"],
        "rows": query_result["rows"],
        "retry_count": 0,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("evals/dataset_v1.jsonl"))
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("evals/results/embedding_hybrid_frozen100_selection_2026-11-02.json"),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--token-ceiling", type=int, default=700_000)
    parser.add_argument("--total-cost-ceiling", type=float, default=0.10)
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
            "model": args.model,
            "error_type": type(error).__name__,
            "error_message": sanitized_error(error),
            "retry_count": 0,
        }
    atomic_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
