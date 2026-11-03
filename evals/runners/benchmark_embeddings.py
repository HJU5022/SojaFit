"""비동결 프록시 표본(30청크·18질의)으로 dense 임베딩 후보를 거르는 재현용 예비 측정. 임베딩 담당이 손으로 돌린다.

- 역할: 후보 모델이 작은 표본에서 정답 청크를 상위 5위 안에 올리는가(Recall@5), 몇 위에 올리는가(MRR),
  표본 임베딩·1000건 임베딩·22,000벡터 정확 검색의 시간은 얼마인가를 잰다.
- 하지 않는 일: 동결 평가셋(dataset_v1.jsonl) 평가가 아니다. 이 결과만으로 최종 모델을 정하지 않는다
  (PROXY_METADATA의 eligible_for_final_model_decision=False). 하이브리드·BM25 검색, 실제 코퍼스는 재지 않는다.
- 출처: evals/guides/preregister.md "임베딩 호환성·실제 PDF 탐색 이력" 표(#9~#15), ADR 0004(1536차원은 임시),
  docs/research/embedding-candidate-investigation.md, evals/EVALS.md.
- 입력: --sample(기본 evals/samples/embedding_sample_v0.jsonl). 줄마다 type이 chunk(id·text) 또는 query(id·text·gold).
- 원시 결과: --output으로 준 json 경로(관례: evals/results/embedding/embedding_<모델>_proxy_<날짜>.json). 안 주면 표준출력에만 찍는다.
- 필요한 것: 로컬 모델(bge-m3·kure-v1·qwen3-embedding-0.6b)은 sentence-transformers·torch(pyproject에 없어 따로 설치)와 모델 내려받기.
  text-embedding-3-small은 OPENAI_API_KEY 또는 OPENROUTER_API_KEY(유료, 표본 30건+1000건+질의 18건)와 backend.services.llm.

실행(저장소 루트에서): uv run python -m evals.runners.benchmark_embeddings --model bge-m3 --output evals/results/embedding/embedding_bge_m3_proxy_<날짜>.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path


# 명령줄 이름(--model) -> 실제 모델 이름. text-embedding-3-small만 로컬이 아니라 API다
MODELS = {
    "bge-m3": "BAAI/bge-m3",
    "kure-v1": "nlpai-lab/KURE-v1",
    "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
    "text-embedding-3-small": "text-embedding-3-small",
}

# [왜] Qwen3 임베딩은 질의에만 지시문을 붙여야 검색용 벡터가 나온다(문서 쪽에는 붙이지 않는다)
QWEN_QUERY_PROMPT = (
    "Instruct: Given a Korean electronics engineering query, retrieve the English "
    "datasheet passage containing the exact part number, electrical rating, package, "
    "test condition, or replacement constraint.\nQuery: "
)

# 결과 json에 항상 같이 적는다. 이 측정이 본평가가 아님을 파일만 봐도 알게 하려는 표시다
PROXY_METADATA = {
    "evaluation_level": "proxy_smoke_test",
    "retrieval_mode": "dense_only",
    "corpus_is_real": False,
    "latency_corpus_vectors_are_repeated": True,
    "eligible_for_final_model_decision": False,
}


def load_sample(path: Path) -> tuple[list[dict], list[dict]]:
    """표본 jsonl을 (청크 목록, 질의 목록)으로 나눈다."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    chunks = [row for row in rows if row["type"] == "chunk"]
    queries = [row for row in rows if row["type"] == "query"]
    chunk_ids = {row["id"] for row in chunks}
    # [주의] 정답 id가 청크에 없으면 순위를 구할 수 없으므로 측정 전에 멈춘다(ValueError)
    missing = {gold for row in queries for gold in row["gold"] if gold not in chunk_ids}
    if missing:
        raise ValueError(f"missing gold chunks: {sorted(missing)}")
    return chunks, queries


def percentile(values: list[float], fraction: float) -> float:
    """가장 가까운 순위 방식의 백분위수(fraction=0.95면 p95)를 구한다. values는 비어 있으면 안 된다."""
    ordered = sorted(values)
    # 정렬한 값에서 (개수-1)*비율 번째 칸을 반올림해 고른다. 범위를 벗어나지 않게 0~마지막으로 자른다
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def retrieval_metrics(chunk_vectors, chunks: list[dict], queries: list[dict], encode_query) -> dict:
    """질의마다 정답 첫 순위를 구해 Recall@5·MRR과 22,000벡터 정확 검색 지연(p50·p95)을 계산한다.

    - Recall@5 = 정답 청크가 상위 5위 안에 든 질의 비율. MRR = 정답 첫 순위의 역수(1/순위)의 평균(1위면 1, 2위면 0.5).
    - [주의] 지연은 표본 벡터를 22,000개로 반복해 만든 가짜 코퍼스에서 질의 임베딩 + 내적 + 상위 5개 선별까지 잰다.
      순위는 반복하지 않은 원래 표본 벡터로 구한다(반복본으로 구하면 같은 청크가 겹쳐 순위가 틀어진다).
    - chunk_vectors는 정규화된 벡터(청크 수 x 차원)이며 chunks와 같은 순서, encode_query는 질의를 정규화된 벡터로 바꾸는 함수다.
    """
    import numpy as np

    # 22,000은 지연 비교용으로 고정한 가상 코퍼스 크기다(실제 코퍼스 카드 수가 아니다). 청크 수로 나눠 올림한 만큼 타일링한 뒤 22,000개로 자른다
    repeats = (22000 + len(chunks) - 1) // len(chunks)
    corpus_22k = np.tile(chunk_vectors, (repeats, 1))[:22000]
    ranks: list[int] = []  # 질의마다 정답이 처음 나온 순위(1부터)
    query_latencies_ms: list[float] = []
    query_results: list[dict] = []
    chunk_id_by_row = [row["id"] for row in chunks]
    for row in queries:
        started = time.perf_counter()
        query_vector = encode_query(row["text"])
        scores = corpus_22k @ query_vector  # 정규화된 벡터끼리의 내적 = 코사인 유사도
        _ = np.argpartition(scores, -5)[-5:]  # 상위 5개만 골라내는 비용까지 시간에 넣는다(전체 정렬보다 싸다)
        elapsed_ms = (time.perf_counter() - started) * 1000
        query_latencies_ms.append(elapsed_ms)

        sample_scores = chunk_vectors @ query_vector
        order = np.argsort(-sample_scores)  # 점수 높은 순서의 행 번호
        ranked_ids = [chunk_id_by_row[index] for index in order]
        # 정답이 여럿이면 가장 높은 순위 하나를 쓴다. index는 0부터라 +1
        rank = min(ranked_ids.index(gold) + 1 for gold in row["gold"])
        ranks.append(rank)
        query_results.append({"id": row["id"], "first_gold_rank": rank, "top5": ranked_ids[:5]})
    return {
        # Recall@5: 5위 안에 든 질의 수 / 전체 질의 수
        "recall_at_5": sum(rank <= 5 for rank in ranks) / len(ranks),
        "mrr": statistics.fmean(1 / rank for rank in ranks),
        "query_22k_exact_ms_p50": percentile(query_latencies_ms, 0.50),
        "query_22k_exact_ms_p95": percentile(query_latencies_ms, 0.95),
        "query_results": query_results,
    }


def evaluate_local(model_key: str, sample: Path, batch_size: int) -> dict:
    """sentence-transformers 로컬 모델 하나(model_key는 MODELS의 키)로 표본을 측정해 조건·지표 dict를 돌려준다."""
    import torch
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    chunks, queries = load_sample(sample)
    model_name = MODELS[model_key]
    model_source = model_name
    if os.getenv("HF_HUB_OFFLINE") == "1":  # [왜] 오프라인 재현용: 이미 내려받은 스냅샷만 쓰고 네트워크를 부르지 않는다
        model_source = snapshot_download(repo_id=model_name, local_files_only=True)
    started = time.perf_counter()
    model = SentenceTransformer(model_source)
    load_seconds = time.perf_counter() - started
    device = str(model.device)

    # [왜] 첫 호출은 초기화 비용이 섞여 시간이 부풀므로, 한 번 먼저 돌려 둔 뒤 재기 시작한다
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

    # 1000건 임베딩 시간용: 표본 30청크를 올림 횟수만큼 반복해 정확히 1000개로 자른다
    repeated = (chunk_texts * ((1000 + len(chunk_texts) - 1) // len(chunk_texts)))[:1000]
    started = time.perf_counter()
    model.encode(repeated, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    embed_1000_seconds = time.perf_counter() - started

    # [주의] 지시문은 qwen3에만, 질의에만 붙인다(문서에 붙이면 비교 조건이 달라진다)
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
    """text-embedding-3-small API로 표본을 측정해 지표와 토큰 수·추정 비용 dict를 돌려준다."""
    # [주의] 유료 호출이다: 표본 30건 1회 + 1000건 1회 + 질의 18건(질의마다 1회). 비용은 $0.02/1M 토큰으로 추정한다
    import numpy as np
    from backend.services.llm import embed_texts

    chunks, queries = load_sample(sample)
    api_provider = ""
    api_model = ""

    def embed(texts: list[str]) -> tuple[np.ndarray, int]:
        nonlocal api_provider, api_model
        raw_vectors, total_tokens, api_provider, api_model = embed_texts(texts)
        vectors = np.asarray(raw_vectors, dtype=np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)  # [왜] 로컬 모델과 같이 길이 1로 맞춰야 내적이 코사인이 된다
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
    """인자를 읽어 모델 하나를 측정하고 결과를 표준출력과(--output이 있으면) 파일에 쓴다."""
    # [주의] --output 경로에 이미 파일이 있으면 말없이 덮어쓴다. 날짜를 바꿔 적어 이전 원시 결과를 지키지 않도록 한다
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--sample", type=Path, default=Path("evals/samples/embedding_sample_v0.jsonl"))
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
