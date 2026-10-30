"""Small, reproducible dense-embedding baseline for SojaFit.

This is a proxy smoke benchmark, not the frozen project evaluation set.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path


MODELS = {
    "bge-m3": "BAAI/bge-m3",
    "kure-v1": "nlpai-lab/KURE-v1",
    "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
    "text-embedding-3-small": "text-embedding-3-small",
}

QWEN_QUERY_PROMPT = (
    "Instruct: Given a Korean electronics engineering query, retrieve the English "
    "datasheet passage containing the exact part number, electrical rating, package, "
    "test condition, or replacement constraint.\nQuery: "
)

PROXY_METADATA = {
    "evaluation_level": "proxy_smoke_test",
    "retrieval_mode": "dense_only",
    "corpus_is_real": False,
    "latency_corpus_vectors_are_repeated": True,
    "eligible_for_final_model_decision": False,
}


def load_sample(path: Path) -> tuple[list[dict], list[dict]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    chunks = [row for row in rows if row["type"] == "chunk"]
    queries = [row for row in rows if row["type"] == "query"]
    chunk_ids = {row["id"] for row in chunks}
    missing = {gold for row in queries for gold in row["gold"] if gold not in chunk_ids}
    if missing:
        raise ValueError(f"missing gold chunks: {sorted(missing)}")
    return chunks, queries


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def retrieval_metrics(chunk_vectors, chunks: list[dict], queries: list[dict], encode_query) -> dict:
    import numpy as np

    repeats = (22000 + len(chunks) - 1) // len(chunks)
    corpus_22k = np.tile(chunk_vectors, (repeats, 1))[:22000]
    ranks: list[int] = []
    query_latencies_ms: list[float] = []
    query_results: list[dict] = []
    chunk_id_by_row = [row["id"] for row in chunks]
    for row in queries:
        started = time.perf_counter()
        query_vector = encode_query(row["text"])
        scores = corpus_22k @ query_vector
        _ = np.argpartition(scores, -5)[-5:]
        elapsed_ms = (time.perf_counter() - started) * 1000
        query_latencies_ms.append(elapsed_ms)

        sample_scores = chunk_vectors @ query_vector
        order = np.argsort(-sample_scores)
        ranked_ids = [chunk_id_by_row[index] for index in order]
        rank = min(ranked_ids.index(gold) + 1 for gold in row["gold"])
        ranks.append(rank)
        query_results.append({"id": row["id"], "first_gold_rank": rank, "top5": ranked_ids[:5]})
    return {
        "recall_at_5": sum(rank <= 5 for rank in ranks) / len(ranks),
        "mrr": statistics.fmean(1 / rank for rank in ranks),
        "query_22k_exact_ms_p50": percentile(query_latencies_ms, 0.50),
        "query_22k_exact_ms_p95": percentile(query_latencies_ms, 0.95),
        "query_results": query_results,
    }


def evaluate_local(model_key: str, sample: Path, batch_size: int) -> dict:
    import torch
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    chunks, queries = load_sample(sample)
    model_name = MODELS[model_key]
    model_source = model_name
    if os.getenv("HF_HUB_OFFLINE") == "1":
        model_source = snapshot_download(repo_id=model_name, local_files_only=True)
    started = time.perf_counter()
    model = SentenceTransformer(model_source)
    load_seconds = time.perf_counter() - started
    device = str(model.device)

    model.encode(["warm up"], normalize_embeddings=True, show_progress_bar=False)
    chunk_texts = [row["text"] for row in chunks]
    started = time.perf_counter()
    chunk_vectors = model.encode(
        chunk_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    sample_embed_seconds = time.perf_counter() - started

    repeated = (chunk_texts * ((1000 + len(chunk_texts) - 1) // len(chunk_texts)))[:1000]
    started = time.perf_counter()
    model.encode(repeated, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    embed_1000_seconds = time.perf_counter() - started

    query_prompt = QWEN_QUERY_PROMPT if model_key == "qwen3-embedding-0.6b" else None

    def encode_query(text: str):
        return model.encode(
            [text],
            prompt=query_prompt,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

    metrics = retrieval_metrics(
        chunk_vectors,
        chunks,
        queries,
        encode_query,
    )
    return {
        "status": "ok",
        **PROXY_METADATA,
        "model_key": model_key,
        "model_name": model_name,
        "sample": str(sample),
        "chunks": len(chunks),
        "queries": len(queries),
        "dimension": int(chunk_vectors.shape[1]),
        "load_seconds": load_seconds,
        "sample_embed_seconds": sample_embed_seconds,
        "embed_1000_seconds": embed_1000_seconds,
        "device": device,
        "cuda_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "hf_hub_offline": os.getenv("HF_HUB_OFFLINE") == "1",
        "query_prompt": query_prompt,
        **metrics,
    }


def evaluate_openai(sample: Path) -> dict:
    import numpy as np
    from backend.services.llm import embed_texts

    chunks, queries = load_sample(sample)
    api_provider = ""
    api_model = ""

    def embed(texts: list[str]) -> tuple[np.ndarray, int]:
        nonlocal api_provider, api_model
        raw_vectors, total_tokens, api_provider, api_model = embed_texts(texts)
        vectors = np.asarray(raw_vectors, dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors, total_tokens

    chunk_texts = [row["text"] for row in chunks]
    started = time.perf_counter()
    chunk_vectors, sample_tokens = embed(chunk_texts)
    sample_embed_seconds = time.perf_counter() - started

    repeated = (chunk_texts * ((1000 + len(chunk_texts) - 1) // len(chunk_texts)))[:1000]
    started = time.perf_counter()
    _, embed_1000_tokens = embed(repeated)
    embed_1000_seconds = time.perf_counter() - started

    query_tokens = 0

    def encode_query(text: str):
        nonlocal query_tokens
        vectors, tokens = embed([text])
        query_tokens += tokens
        return vectors[0]

    metrics = retrieval_metrics(chunk_vectors, chunks, queries, encode_query)
    total_tokens = sample_tokens + embed_1000_tokens + query_tokens
    return {
        "status": "ok",
        **PROXY_METADATA,
        "model_key": "text-embedding-3-small",
        "model_name": "text-embedding-3-small",
        "api_provider": api_provider,
        "api_model": api_model,
        "sample": str(sample),
        "chunks": len(chunks),
        "queries": len(queries),
        "dimension": int(chunk_vectors.shape[1]),
        "sample_embed_seconds": sample_embed_seconds,
        "embed_1000_seconds": embed_1000_seconds,
        "sample_tokens": sample_tokens,
        "embed_1000_tokens": embed_1000_tokens,
        "embed_1000_cost_usd": embed_1000_tokens / 1_000_000 * 0.02,
        "query_tokens_total": query_tokens,
        "query_cost_usd_mean": query_tokens / len(queries) / 1_000_000 * 0.02,
        "total_tokens": total_tokens,
        "total_cost_usd": total_tokens / 1_000_000 * 0.02,
        "device": "OpenAI API",
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--sample", type=Path, default=Path("evals/embedding_sample_v0.jsonl"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.model == "text-embedding-3-small":
        result = evaluate_openai(args.sample)
    else:
        result = evaluate_local(args.model, args.sample, args.batch_size)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
