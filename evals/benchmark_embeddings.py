"""비동결 프록시 표본(embedding_sample_v0.jsonl, 30청크·18질의)으로 dense 임베딩 후보를 거르는 재현용 예비 측정.

동결 평가셋(dataset_v1.jsonl) 평가가 아니며, 이 결과만으로 최종 모델을 정하지 않는다.
"""

from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import json
import os
import statistics
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    provider: str
    revision: str | None
    license_id: str
    expected_dimension: int
    runnable: bool
    commercial_candidate: bool
    research_only: bool
    trust_remote_code: bool = False
    code_revision: str | None = None
    document_mode: str = "plain"
    query_mode: str = "plain"
    price_per_million_usd: float = 0.0


@dataclass(frozen=True)
class ApiModelSpec:
    model_id: str
    dimension: int
    price_per_million_usd: float


API_MODELS = {
    "openai/text-embedding-3-small": ApiModelSpec(
        "openai/text-embedding-3-small", 1536, 0.02
    ),
    "voyageai/voyage-4": ApiModelSpec("voyageai/voyage-4", 1024, 0.06),
    "baai/bge-m3": ApiModelSpec("baai/bge-m3", 1024, 0.01),
}


MODEL_CATALOG = {
    "text-embedding-3-small": ModelSpec(
        "text-embedding-3-small",
        "text-embedding-3-small",
        "api",
        None,
        "OpenAI/OpenRouter service terms",
        1536,
        True,
        True,
        False,
        price_per_million_usd=0.02,
    ),
    "voyage-4": ModelSpec(
        "voyage-4",
        "voyageai/voyage-4",
        "api",
        None,
        "OpenRouter service terms",
        1024,
        True,
        True,
        False,
        document_mode="voyage_document",
        query_mode="voyage_query",
        price_per_million_usd=0.06,
    ),
    "voyage-4-nano": ModelSpec(
        "voyage-4-nano",
        "voyageai/voyage-4-nano",
        "huggingface",
        "5fb34e870f49f19e79c94d5e118f5ee730133279",
        "Apache-2.0",
        1024,
        True,
        True,
        False,
        trust_remote_code=True,
        code_revision="5fb34e870f49f19e79c94d5e118f5ee730133279",
        document_mode="voyage_document",
        query_mode="voyage_query",
    ),
    "bge-m3": ModelSpec(
        "bge-m3",
        "BAAI/bge-m3",
        "huggingface",
        "5617a9f61b028005a4858fdac845db406aefb181",
        "MIT",
        1024,
        True,
        True,
        False,
    ),
    "kure-v1": ModelSpec(
        "kure-v1",
        "nlpai-lab/KURE-v1",
        "huggingface",
        "8b418a58414668e75532ed045c22d9ca018ae2b2",
        "MIT",
        1024,
        True,
        True,
        False,
    ),
    "qwen3-embedding-0.6b": ModelSpec(
        "qwen3-embedding-0.6b",
        "Qwen/Qwen3-Embedding-0.6B",
        "huggingface",
        "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        "Apache-2.0",
        1024,
        True,
        True,
        False,
        query_mode="qwen_instruction",
    ),
    "gte-multilingual-base": ModelSpec(
        "gte-multilingual-base",
        "Alibaba-NLP/gte-multilingual-base",
        "huggingface",
        "9bbca17d9273fd0d03d5725c7a4b0f6b45142062",
        "Apache-2.0",
        768,
        True,
        True,
        False,
        trust_remote_code=True,
        code_revision="40ced75c3017eb27626c9d4ea981bde21a2662f4",
    ),
    "multilingual-e5-large-instruct": ModelSpec(
        "multilingual-e5-large-instruct",
        "intfloat/multilingual-e5-large-instruct",
        "huggingface",
        "274baa43b0e13e37fafa6428dbc7938e62e5c439",
        "MIT",
        1024,
        True,
        True,
        False,
        query_mode="e5_instruction",
    ),
    "jina-embeddings-v3": ModelSpec(
        "jina-embeddings-v3",
        "jinaai/jina-embeddings-v3",
        "huggingface",
        "ab036b023d30b4d1138c4c3bfa9f0c445ab455d6",
        "CC-BY-NC-4.0",
        1024,
        True,
        False,
        True,
        trust_remote_code=True,
        code_revision="bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3",
        document_mode="jina_passage",
        query_mode="jina_query",
    ),
    "nomic-embed-text-v2-moe": ModelSpec(
        "nomic-embed-text-v2-moe",
        "nomic-ai/nomic-embed-text-v2-moe",
        "huggingface",
        "1066b6599d099fbb93dfcb64f9c37a7c9e503e85",
        "Apache-2.0",
        768,
        True,
        True,
        False,
        trust_remote_code=True,
        code_revision="7710840340a098cfb869c4f65e87cf2b1b70caca",
        document_mode="nomic_passage",
        query_mode="nomic_query",
    ),
    "snowflake-arctic-embed-m-v2.0": ModelSpec(
        "snowflake-arctic-embed-m-v2.0",
        "Snowflake/snowflake-arctic-embed-m-v2.0",
        "huggingface",
        "95c2741480856aa9666782eb4afe11959938017f",
        "Apache-2.0",
        768,
        True,
        True,
        False,
        trust_remote_code=True,
        code_revision="95c2741480856aa9666782eb4afe11959938017f",
        query_mode="arctic_query",
    ),
    "embeddinggemma-300m": ModelSpec(
        "embeddinggemma-300m",
        "google/embeddinggemma-300m",
        "huggingface",
        "57c266a740f537b4dc058e1b0cda161fd15afa75",
        "Gemma",
        768,
        False,
        False,
        True,
        document_mode="excluded",
        query_mode="excluded",
    ),
    "jina-embeddings-v4": ModelSpec(
        "jina-embeddings-v4",
        "jinaai/jina-embeddings-v4",
        "huggingface",
        "853c867b65b749f3c3c72a06868140d842e04f06",
        "Qwen-Research",
        2048,
        False,
        False,
        True,
        trust_remote_code=True,
        code_revision="853c867b65b749f3c3c72a06868140d842e04f06",
        document_mode="excluded",
        query_mode="excluded",
    ),
}


def runnable_model_keys() -> list[str]:
    return sorted(key for key, spec in MODEL_CATALOG.items() if spec.runnable)


def validate_model_catalog(catalog: dict[str, ModelSpec] = MODEL_CATALOG) -> None:
    for key, spec in catalog.items():
        if key != spec.key:
            raise ValueError(f"catalog key mismatch: {key}")
        if spec.provider == "huggingface" and spec.runnable:
            revision = spec.revision or ""
            if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
                raise ValueError(f"immutable revision required: {key}")
        if spec.research_only and spec.commercial_candidate:
            raise ValueError(f"research-only model cannot be commercial: {key}")
        if spec.trust_remote_code:
            code_revision = spec.code_revision or ""
            if len(code_revision) != 40 or any(
                c not in "0123456789abcdef" for c in code_revision
            ):
                raise ValueError(f"immutable code revision required: {key}")


validate_model_catalog()
MODELS = {key: MODEL_CATALOG[key].model_id for key in runnable_model_keys()}

ELECTRONICS_TASK = (
    "Given a Korean electronics engineering query, retrieve the English datasheet "
    "passage containing the exact part number, electrical rating, package, test "
    "condition, or replacement constraint."
)
ELECTRONICS_QUERY_INSTRUCTION = f"Instruct: {ELECTRONICS_TASK}\nQuery: "
VOYAGE_QUERY_PROMPT = "Represent the query for retrieving supporting documents: "
VOYAGE_DOCUMENT_PROMPT = "Represent the document for retrieval: "

def proxy_metadata(sample_kind: str) -> dict:
    if sample_kind not in {"synthetic", "real_pdf"}:
        raise ValueError(f"invalid sample kind: {sample_kind}")
    is_real = sample_kind == "real_pdf"
    return {
        "evaluation_level": "proxy_real_pdf_smoke" if is_real else "proxy_smoke_test",
        "retrieval_mode": "dense_only",
        "corpus_is_real": is_real,
        "latency_corpus_vectors_are_repeated": True,
        "eligible_for_final_model_decision": False,
    }


PROXY_METADATA = proxy_metadata("synthetic")


def prepare_encode_call(
    spec: ModelSpec,
    texts: list[str],
    role: str,
) -> tuple[list[str], dict]:
    if not spec.runnable:
        raise ValueError(f"model is not runnable: {spec.key}")
    if role not in {"document", "query"}:
        raise ValueError(f"invalid role: {role}")

    mode = spec.document_mode if role == "document" else spec.query_mode
    if mode == "plain":
        return texts, {}
    if mode == "qwen_instruction":
        return [ELECTRONICS_QUERY_INSTRUCTION + text for text in texts], {}
    if mode == "e5_instruction":
        return [f"Instruct: {ELECTRONICS_TASK}\nQuery: {text}" for text in texts], {}
    if mode == "jina_passage":
        return texts, {"task": "retrieval.passage", "prompt_name": "retrieval.passage"}
    if mode == "jina_query":
        return texts, {"task": "retrieval.query", "prompt_name": "retrieval.query"}
    if mode == "nomic_passage":
        return texts, {"prompt_name": "passage"}
    if mode == "nomic_query":
        return texts, {"prompt_name": "query"}
    if mode == "arctic_query":
        return texts, {"prompt_name": "query"}
    if mode in {"voyage_document", "voyage_query"}:
        return texts, {}
    raise ValueError(f"unsupported encoding mode: {mode}")


def prompt_for_mode(mode: str) -> str | None:
    if mode in {"qwen_instruction", "e5_instruction"}:
        return ELECTRONICS_QUERY_INSTRUCTION
    if mode == "voyage_query":
        return VOYAGE_QUERY_PROMPT
    if mode == "voyage_document":
        return VOYAGE_DOCUMENT_PROMPT
    return None


def model_metadata(spec: ModelSpec) -> dict:
    return {
        "model_key": spec.key,
        "model_name": spec.model_id,
        "model_revision": spec.revision,
        "license_id": spec.license_id,
        "commercial_candidate": spec.commercial_candidate,
        "research_only": spec.research_only,
        "trust_remote_code": spec.trust_remote_code,
        "code_revision": spec.code_revision,
        "document_mode": spec.document_mode,
        "query_mode": spec.query_mode,
        "document_prompt": prompt_for_mode(spec.document_mode),
        "query_prompt": prompt_for_mode(spec.query_mode),
    }


def runtime_metadata() -> dict:
    package_versions = {}
    for package in ("numpy", "sentence-transformers", "torch", "transformers", "openai"):
        try:
            package_versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            package_versions[package] = None
    return {
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "runtime_packages": package_versions,
    }


def error_metadata(error: Exception, stage: str) -> dict:
    return {
        "error_type": type(error).__name__,
        "error_message": str(error)[:300],
        "error_stage": stage,
        "retry_count": 0,
    }


def api_key_available(spec: ModelSpec, env: Mapping[str, str] = os.environ) -> bool:
    if spec.key == "voyage-4":
        return bool(env.get("OPENROUTER_API_KEY"))
    return bool(env.get("OPENAI_API_KEY") or env.get("OPENROUTER_API_KEY"))


def api_request_options(model_id: str, role: str) -> dict:
    spec = API_MODELS[model_id]
    if role not in {"query", "document"}:
        raise ValueError(f"invalid embedding role: {role}")
    if model_id == "voyageai/voyage-4":
        return {"input_type": role, "dimensions": spec.dimension}
    if model_id == "openai/text-embedding-3-small":
        return {"dimensions": spec.dimension}
    return {}


def api_error_result(model_id: str, error: Exception, sample_kind: str = "synthetic") -> dict:
    spec = API_MODELS[model_id]
    return {
        "status": "error",
        **proxy_metadata(sample_kind),
        "model_key": model_id,
        "model_name": model_id,
        "dimension": spec.dimension,
        **error_metadata(error, "model_evaluation"),
        **runtime_metadata(),
    }


def runtime_model_kwargs(spec: ModelSpec) -> dict:
    if spec.key == "gte-multilingual-base":
        return {"attn_implementation": "eager"}
    if spec.key == "voyage-4-nano":
        return {"attn_implementation": "sdpa"}
    return {}


def runtime_sentence_transformer_kwargs(spec: ModelSpec) -> dict:
    if spec.key == "voyage-4-nano":
        return {"truncate_dim": spec.expected_dimension}
    return {}


def load_local_model(spec: ModelSpec):
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    if spec.provider != "huggingface" or not spec.runnable:
        raise ValueError(f"local runnable model required: {spec.key}")
    code_kwargs = (
        {"code_revision": spec.code_revision} if spec.code_revision is not None else {}
    )
    model_kwargs = {**runtime_model_kwargs(spec), **code_kwargs}
    sentence_transformer_kwargs = runtime_sentence_transformer_kwargs(spec)
    if os.getenv("HF_HUB_OFFLINE") == "1":
        source = snapshot_download(
            repo_id=spec.model_id,
            revision=spec.revision,
            local_files_only=True,
        )
        return SentenceTransformer(
            source,
            trust_remote_code=spec.trust_remote_code,
            local_files_only=True,
            model_kwargs=model_kwargs,
            config_kwargs=code_kwargs,
            **sentence_transformer_kwargs,
        )
    return SentenceTransformer(
        spec.model_id,
        revision=spec.revision,
        trust_remote_code=spec.trust_remote_code,
        model_kwargs=model_kwargs,
        config_kwargs=code_kwargs,
        **sentence_transformer_kwargs,
    )


def encode_role(model, spec: ModelSpec, texts: list[str], role: str, batch_size: int):
    prepared, options = prepare_encode_call(spec, texts, role)
    if spec.key == "voyage-4-nano":
        encoder = model.encode_query if role == "query" else model.encode_document
    else:
        encoder = model.encode
    return encoder(
        prepared,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        **options,
    )


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


def evaluate_local(
    model_key: str,
    sample: Path,
    batch_size: int,
    sample_kind: str = "synthetic",
) -> dict:
    import torch

    chunks, queries = load_sample(sample)
    spec = MODEL_CATALOG[model_key]
    started = time.perf_counter()
    model = load_local_model(spec)
    load_seconds = time.perf_counter() - started
    device = str(model.device)

    encode_role(model, spec, ["warm up"], "document", batch_size)
    chunk_texts = [row["text"] for row in chunks]
    started = time.perf_counter()
    chunk_vectors = encode_role(model, spec, chunk_texts, "document", batch_size)
    sample_embed_seconds = time.perf_counter() - started
    if int(chunk_vectors.shape[1]) != spec.expected_dimension:
        raise ValueError(
            f"unexpected embedding dimension for {spec.key}: "
            f"{chunk_vectors.shape[1]} != {spec.expected_dimension}"
        )

    repeated = (chunk_texts * ((1000 + len(chunk_texts) - 1) // len(chunk_texts)))[:1000]
    started = time.perf_counter()
    encode_role(model, spec, repeated, "document", batch_size)
    embed_1000_seconds = time.perf_counter() - started

    def encode_query(text: str):
        return encode_role(model, spec, [text], "query", batch_size)[0]

    metrics = retrieval_metrics(
        chunk_vectors,
        chunks,
        queries,
        encode_query,
    )
    return {
        "status": "ok",
        **proxy_metadata(sample_kind),
        **model_metadata(spec),
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
        **metrics,
    }


def evaluate_api(
    model_key: str,
    sample: Path,
    sample_kind: str = "synthetic",
) -> dict:
    import numpy as np
    from backend.services.llm import embed_texts

    chunks, queries = load_sample(sample)
    if model_key in MODEL_CATALOG:
        spec = MODEL_CATALOG[model_key]
        request_model_id = (
            "openai/text-embedding-3-small"
            if model_key == "text-embedding-3-small"
            else spec.model_id
        )
        expected_dimension = spec.expected_dimension
        price_per_million_usd = spec.price_per_million_usd
    else:
        api_spec = API_MODELS[model_key]
        request_model_id = api_spec.model_id
        expected_dimension = api_spec.dimension
        price_per_million_usd = api_spec.price_per_million_usd
    api_provider = ""
    api_model = ""

    def embed(texts: list[str], role: str) -> tuple[np.ndarray, int]:
        nonlocal api_provider, api_model
        options = (
            api_request_options(request_model_id, role)
            if request_model_id in API_MODELS
            else {}
        )
        raw_vectors, total_tokens, api_provider, api_model = embed_texts(
            texts,
            model_id=request_model_id,
            **options,
        )
        vectors = np.asarray(raw_vectors, dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors, total_tokens

    chunk_texts = [row["text"] for row in chunks]
    started = time.perf_counter()
    chunk_vectors, sample_tokens = embed(chunk_texts, "document")
    sample_embed_seconds = time.perf_counter() - started
    if int(chunk_vectors.shape[1]) != expected_dimension:
        raise ValueError(
            f"unexpected embedding dimension for {model_key}: "
            f"{chunk_vectors.shape[1]} != {expected_dimension}"
        )

    repeated = (chunk_texts * ((1000 + len(chunk_texts) - 1) // len(chunk_texts)))[:1000]
    started = time.perf_counter()
    _, embed_1000_tokens = embed(repeated, "document")
    embed_1000_seconds = time.perf_counter() - started

    query_tokens = 0

    def encode_query(text: str):
        nonlocal query_tokens
        vectors, tokens = embed([text], "query")
        query_tokens += tokens
        return vectors[0]

    metrics = retrieval_metrics(chunk_vectors, chunks, queries, encode_query)
    total_tokens = sample_tokens + embed_1000_tokens + query_tokens
    return {
        "status": "ok",
        **proxy_metadata(sample_kind),
        "model_key": model_key,
        "model_name": request_model_id,
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
        "embed_1000_cost_usd": embed_1000_tokens / 1_000_000 * price_per_million_usd,
        "query_tokens_total": query_tokens,
        "query_cost_usd_mean": (
            query_tokens / len(queries) / 1_000_000 * price_per_million_usd
        ),
        "total_tokens": total_tokens,
        "total_cost_usd": total_tokens / 1_000_000 * price_per_million_usd,
        "device": f"{api_provider} API",
        **metrics,
    }


def run_model(
    model_key: str,
    sample: Path,
    batch_size: int,
    env: Mapping[str, str] = os.environ,
    sample_kind: str = "synthetic",
) -> dict:
    spec = MODEL_CATALOG[model_key]
    runtime = runtime_metadata()
    if not spec.runnable:
        raise ValueError(f"model is not runnable: {model_key}")
    if spec.provider == "api":
        if not api_key_available(spec, env):
            return {
                "status": "not_run_no_key",
                **proxy_metadata(sample_kind),
                **model_metadata(spec),
                **runtime,
            }
        try:
            return {
                **evaluate_api(model_key, sample, sample_kind),
                **model_metadata(spec),
                **runtime,
            }
        except Exception as error:
            return {
                "status": "error",
                **proxy_metadata(sample_kind),
                **model_metadata(spec),
                **error_metadata(error, "model_evaluation"),
                **runtime,
            }
    try:
        return {
            **evaluate_local(model_key, sample, batch_size, sample_kind),
            **runtime,
        }
    except Exception as error:
        return {
            "status": "error",
            **proxy_metadata(sample_kind),
            **model_metadata(spec),
            **error_metadata(error, "model_evaluation"),
            **runtime,
        }


def run_api_model(
    model_id: str,
    sample: Path,
    sample_kind: str = "synthetic",
) -> dict:
    try:
        return {
            **evaluate_api(model_id, sample, sample_kind),
            **runtime_metadata(),
        }
    except Exception as error:
        return api_error_result(model_id, error, sample_kind)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", choices=sorted(set(runnable_model_keys()) | set(API_MODELS)), required=True
    )
    parser.add_argument("--sample", type=Path, default=Path("evals/embedding_sample_v0.jsonl"))
    parser.add_argument("--sample-kind", choices=["synthetic", "real_pdf"], default="synthetic")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.model in API_MODELS:
        result = run_api_model(args.model, args.sample, args.sample_kind)
    else:
        result = run_model(
            args.model, args.sample, args.batch_size, sample_kind=args.sample_kind
        )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
