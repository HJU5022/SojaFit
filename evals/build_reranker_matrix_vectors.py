"""Build one resumable full-corpus vector cache for the reranker matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np

CHUNKS_SHA256 = "aa4b9576dfe9a0ac27b178efb9575526e0be4f3442f6f59de328501ebf8871a9"
UNIQUE_TEXTS = 45_898
EMBEDDINGS = (
    "text-embedding-3-small",
    "Qwen3-Embedding-0.6B",
    "voyage-4-lite",
    "voyage-4",
    "voyage-4-large",
    "KURE-v1",
)
DIMENSIONS = {name: 1024 for name in EMBEDDINGS}
DIMENSIONS["text-embedding-3-small"] = 1536
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


API_PRICE_PER_MILLION = {
    "text-embedding-3-small": 0.02,
    "voyage-4-lite": 0.02,
    "voyage-4": 0.06,
    "voyage-4-large": 0.12,
}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unique_texts(chunks_path: Path) -> list[str]:
    if file_sha256(chunks_path) != CHUNKS_SHA256:
        raise ValueError("full corpus chunk hash mismatch")
    seen = set()
    texts = []
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["sha256"] not in seen:
            seen.add(row["sha256"])
            texts.append(row["text"])
    if len(texts) != UNIQUE_TEXTS:
        raise ValueError("full corpus unique-text count mismatch")
    return texts


def normalize(vectors, expected_rows: int, dimension: int) -> np.ndarray:
    batch = np.asarray(vectors, dtype=np.float32)
    if batch.shape != (expected_rows, dimension):
        raise ValueError(f"embedding shape mismatch: {batch.shape}")
    if not np.isfinite(batch).all():
        raise ValueError("embedding contains non-finite values")
    norms = np.linalg.norm(batch, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("embedding contains zero vectors")
    return batch / norms


def retrieval_queries(dataset_path: Path) -> list[dict]:
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line]
    result = []
    for row in rows:
        has_pdf_gold = any(re.match(r"(.+?\.pdf),\s*(\d+)쪽", gold) for gold in row["gold_chunks"])
        if row["kind"] == "relevant" and has_pdf_gold:
            result.append({"id": row["id"], "text": row.get("question") or row["input"]})
    return result


def api_batch(embedding: str, texts: list[str]):
    from backend.services.llm import embed_texts, voyage_embed_texts

    input_type = "document" if embedding.startswith("voyage-") else None
    if input_type is not None:
        return voyage_embed_texts(
            texts,
            model_id=embedding,
            input_type=input_type,
            dimensions=DIMENSIONS[embedding],
        )
    return embed_texts(
        texts,
        model_id=API_EMBEDDING_IDS[embedding],
        input_type=input_type,
        dimensions=DIMENSIONS[embedding],
    )


def build(args) -> dict:
    texts = unique_texts(args.chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    progress_path = args.output.with_suffix(".progress.json")
    progress = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.exists()
        else {"embedding": args.embedding, "next_index": 0, "tokens": 0, "cost_usd": 0.0, "batches": 0}
    )
    if progress["embedding"] != args.embedding:
        raise ValueError("vector progress embedding mismatch")
    expected_bytes = UNIQUE_TEXTS * DIMENSIONS[args.embedding] * 4
    if args.output.exists() and args.output.stat().st_size != expected_bytes:
        raise ValueError("existing vector cache size mismatch")
    mode = "r+" if args.output.exists() else "w+"
    vectors = np.memmap(
        args.output,
        dtype=np.float32,
        mode=mode,
        shape=(UNIQUE_TEXTS, DIMENSIONS[args.embedding]),
    )
    model = spec = None
    if args.embedding in LOCAL_EMBEDDING_KEYS:
        if os.getenv("HF_HUB_OFFLINE") != "1" or os.getenv("TRANSFORMERS_OFFLINE") != "1":
            raise RuntimeError("local embedding build requires offline environment flags")
        from evals import benchmark_embeddings as benchmark

        spec = benchmark.MODEL_CATALOG[LOCAL_EMBEDDING_KEYS[args.embedding]]
        model = benchmark.load_local_model(spec)
    started = time.perf_counter()
    for start in range(progress["next_index"], len(texts), args.batch_size):
        end = min(start + args.batch_size, len(texts))
        batch_texts = texts[start:end]
        if args.embedding in API_EMBEDDING_IDS:
            raw, used, provider, actual_model = api_batch(args.embedding, batch_texts)
        else:
            from evals import benchmark_embeddings as benchmark

            raw = benchmark.encode_role(model, spec, batch_texts, "document", args.batch_size)
            used, provider, actual_model = 0, "local-cache", spec.model_id
        batch = normalize(raw, len(batch_texts), DIMENSIONS[args.embedding])
        incremental_cost = used / 1_000_000 * API_PRICE_PER_MILLION.get(args.embedding, 0)
        if progress["cost_usd"] + incremental_cost > args.cost_ceiling:
            raise RuntimeError("embedding cost would exceed the approved ceiling")
        vectors[start:end] = batch
        vectors.flush()
        progress.update(
            {
                "next_index": end,
                "tokens": progress["tokens"] + int(used),
                "cost_usd": progress["cost_usd"] + incremental_cost,
                "batches": progress["batches"] + 1,
                "provider": provider,
                "api_model": actual_model,
            }
        )
        atomic_json(progress_path, progress)
    progress["seconds_this_run"] = time.perf_counter() - started
    progress["status"] = "ok"
    atomic_json(progress_path, progress)
    if args.query_dataset is not None:
        if args.embedding not in LOCAL_EMBEDDING_KEYS or args.query_output is None:
            raise ValueError("local query output requires a local embedding and --query-output")
        from evals import benchmark_embeddings as benchmark

        queries = retrieval_queries(args.query_dataset)
        raw = benchmark.encode_role(
            model, spec, [row["text"] for row in queries], "query", args.batch_size
        )
        query_vectors = normalize(raw, len(queries), DIMENSIONS[args.embedding])
        args.query_output.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.query_output, query_vectors)
        atomic_json(
            args.query_output.with_suffix(".json"),
            {"embedding": args.embedding, "ids": [row["id"] for row in queries]},
        )
    return progress


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding", choices=EMBEDDINGS, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--cost-ceiling", type=float, default=2.0)
    parser.add_argument("--query-dataset", type=Path)
    parser.add_argument("--query-output", type=Path)
    args = parser.parse_args()
    result = build(args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
