# 임베딩 6종 x 검색 방식 격자 본평가

- 상태: 현행
- 기준일: 2026-11-02 (측정일)
- 기준 커밋: 98c2fe8 (`grid_2026-11-02.json` `meta.repo_commit`)
- 정본 여부: 정본(임베딩 6종 x 검색 방식 78칸 측정). 요약은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 1-3절, 사전 등록은 [preregister.md](../../evals/guides/preregister.md) #16(동결)
- 관련 문서: [embedding-candidate-investigation.md](embedding-candidate-investigation.md), [model-licenses.md](model-licenses.md), [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md), [evals/docker/DOCKER.md](../../evals/docker/DOCKER.md)

## 1. 질문과 결론

질문: 임베딩 모델과 `vector(N)`을 무엇으로 정할 것인가. 6종 모델 x 검색 방식 x 리랭커 x 질의 글 2종, 78칸을 같은 19문항으로 잰다. 선정 결정은 ADR 0004가 한다. 이 문서는 측정만 담는다.

| 항목 | 값 | 근거 |
|---|---|---|
| 기준 칸(text-embedding-3-small, 하이브리드, `input` 전체, 리랭커 없음) | 문서 Recall@5 0.737, MRR 0.649, 쪽 적중@5 0.368 | `evals/results/embedding/grid_2026-11-02.json` `cells` |
| 하이브리드, 리랭커 없음, `input` 전체에서 MRR 최고 | Qwen3-Embedding-0.6B 0.675 | 같은 파일, 3절 표 |
| 리랭커 효과 | 리랭커 52칸 중 37칸에서 리랭커 없음 대비 MRR이 +0.15 초과(최대 +0.591), 감소한 칸 0 | 같은 파일에서 계산 |
| 사전 등록 #16 기대 대조 | 5절 | |

## 2. 방법과 환경

| 항목 | 값 | 근거 |
|---|---|---|
| 실행 환경 | desktop-gpu(WSL2, RTX 3080 Ti 12GB)의 Docker. 실험 DB `sojafit-embed-db`(PostgreSQL 16.15, pgvector 0.8.7). 앱 DB와 별개 | `grid_2026-11-02.json` `meta.pgvector` |
| 실행 이미지 | `sojafit-embed-run` = 11-01 `sojafit-emb` + psycopg 3.3.6, pgvector 0.5.1, rank-bm25 0.2.2, openai 3.40.0, voyageai | `evals/docker/Dockerfile.embedding_grid:3-5` |
| 저장소 스냅샷 | main `98c2fe8` | `meta.repo_commit` |
| 평가셋 | `evals/dataset_v1.jsonl`(sha256 `2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b`)의 관련 25건 중 데이터시트 gold가 있는 19건. 회로 근거만 있는 6건(e01, e02, m01, m02, h01, h02) 제외 | `meta.dataset_sha256`, `shasum -a 256` 일치 |
| 카드 | `chunks.jsonl`(sha256 `9e62fb6a80eb703ce0d8d98e69669d222c9fc307da36d9b272ae4e51083d4516`) 52,244장. 서로 다른 본문 45,898개, 문서 1,360건 | `meta.chunks_sha256`, `meta.embed_logs` |
| 카드 벡터 | 모델마다 새로 생성. 기존 캐시 미사용 | |
| dense | 실험 DB의 pgvector 정확 검색(`<=>`, 인덱스 없음) 상위 50장 | `evals/runners/run_embedding_grid.py` |
| BM25 | 저장소 `tokens()`와 BM25Okapi 기본값, 상위 50장, 점수 0 제외 | 같은 파일 |
| 하이브리드 | RRF k=60 | |
| 리랭커 | Voyage `rerank-3`, `rerank-3-lite`. 후보 전부를 넣고 상위 5장. 리랭크 988회 호출, 13,831,602토큰, 무료 토큰 안 | `meta.rerank_new_calls`, `meta.rerank_new_tokens` |
| 지표 | `evals/runners/run_retrieval.py`와 같은 기준(문서 순위, 쪽 적중). 다중 근거 Recall@5 = 문항의 모든 gold 쪽이 상위 5에 함께 든 비율 | |
| 원시 결과 | [grid_2026-11-02.json](../../evals/results/embedding/grid_2026-11-02.json)(78칸 요약, 문항별 순위, 상위 5, 단계별 시간), `evals/results/embedding/grid_embed_<모델>_2026-11-02.json` 6개, 리랭크 응답 캐시 `grid_rerank_cache_2026-11-02.jsonl`(988행) | |
| 실행 코드 | `evals/runners/embed_cards.py`(카드 적재, 카드 임베딩), `evals/runners/run_embedding_grid.py`(78칸 측정), `evals/docker/Dockerfile.embedding_grid`, 실행 순서 [DOCKER.md](../../evals/docker/DOCKER.md). 11-02 실행 뒤 저장소 경로에 맞게 import만 고쳤고 다시 돌리지 않았다 | |

## 3. 결과

### 3.1 카드 임베딩

원시: `grid_embed_<모델>_2026-11-02.json`, `meta.embed_logs`.

| 모델 | 차원 | 실행 | 시간 | 토큰 | 비용 |
|---|---:|---|---:|---:|---|
| text-embedding-3-small | 1536 | OpenRouter(`backend/services/llm.py`의 `embed_texts`) | 773.6초 | 5,391,648 | 약 $0.108(단가 $0.02/M로 계산) |
| KURE-v1 | 1024 | RTX 3080 Ti, revision `8b418a58` | 352.8초(불러오기 10.5초) | - | $0 |
| Qwen3-Embedding-0.6B | 1024 | RTX 3080 Ti, revision `97b0c614` | 244.8초(불러오기 9.1초) | - | $0 |
| voyage-4-lite | 1024 | Voyage API | 190.6초 | 5,772,525 | 무료 토큰 안(정가 약 $0.115) |
| voyage-4 | 1024 | Voyage API | 262.3초 | 5,772,525 | 무료 토큰 안(정가 약 $0.346) |
| voyage-4-large | 1024 | Voyage API | 172.6초 | 5,772,525 | 무료 토큰 안(정가 약 $0.693) |

비용은 Voyage 가격표 기준 정가다(embedding $0.02, $0.06, $0.12 per 1M 토큰, 모델마다 2억 토큰 무료) [문서 docs.voyageai.com/docs/pricing].

### 3.2 하이브리드, 리랭커 없음

| 모델 | 질의 글 | 문서 Recall@5 | 문서 MRR | 쪽 적중@5 | 다중 근거 Recall@5 |
|---|---|---:|---:|---:|---:|
| text-embedding-3-small | `input` 전체 | 0.737 | 0.649 | 0.368 | 0.211 |
| KURE-v1 | `input` 전체 | 0.368 | 0.225 | 0.211 | 0.053 |
| Qwen3-Embedding-0.6B | `input` 전체 | 0.789 | 0.675 | 0.632 | 0.368 |
| voyage-4-lite | `input` 전체 | 0.579 | 0.443 | 0.526 | 0.316 |
| voyage-4 | `input` 전체 | 0.579 | 0.382 | 0.421 | 0.263 |
| voyage-4-large | `input` 전체 | 0.526 | 0.403 | 0.368 | 0.211 |
| BM25만(참고) | `input` 전체 | 0.263 | 0.195 | 0.211 | 0.053 |
| text-embedding-3-small | "질문:" 줄 | 1.000 | 0.921 | 0.737 | 0.579 |
| KURE-v1 | "질문:" 줄 | 1.000 | 0.868 | 0.632 | 0.316 |
| Qwen3-Embedding-0.6B | "질문:" 줄 | 1.000 | 0.895 | 0.789 | 0.526 |
| voyage-4-lite | "질문:" 줄 | 1.000 | 0.838 | 0.684 | 0.316 |
| voyage-4 | "질문:" 줄 | 1.000 | 0.829 | 0.737 | 0.526 |
| voyage-4-large | "질문:" 줄 | 0.947 | 0.868 | 0.895 | 0.526 |
| BM25만(참고) | "질문:" 줄 | 1.000 | 0.939 | 0.684 | 0.263 |

### 3.3 78칸 전체

78행이 `grid_2026-11-02.json` `cells`의 `summary`와 일치한다.

| 모델 | 검색 | 리랭커 | 질의 글 | 문서 Recall@5 | 문서 MRR | 쪽 적중@5 | 다중 근거 Recall@5 |
|---|---|---|---|---:|---:|---:|---:|
| (모델 없음) | BM25만 | 없음 | `input` 전체 | 0.263 | 0.195 | 0.211 | 0.053 |
| (모델 없음) | BM25만 | rerank-3 | `input` 전체 | 0.579 | 0.526 | 0.421 | 0.211 |
| (모델 없음) | BM25만 | rerank-3-lite | `input` 전체 | 0.579 | 0.526 | 0.421 | 0.211 |
| (모델 없음) | BM25만 | 없음 | "질문:" 줄 | 1.000 | 0.939 | 0.684 | 0.263 |
| (모델 없음) | BM25만 | rerank-3 | "질문:" 줄 | 0.947 | 0.947 | 0.842 | 0.474 |
| (모델 없음) | BM25만 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.947 | 0.842 | 0.526 |
| text-embedding-3-small | dense만 | 없음 | `input` 전체 | 0.684 | 0.589 | 0.263 | 0.211 |
| text-embedding-3-small | dense만 | rerank-3 | `input` 전체 | 0.842 | 0.765 | 0.632 | 0.474 |
| text-embedding-3-small | dense만 | rerank-3-lite | `input` 전체 | 0.789 | 0.737 | 0.579 | 0.474 |
| text-embedding-3-small | 하이브리드 | 없음 | `input` 전체 | 0.737 | 0.649 | 0.368 | 0.211 |
| text-embedding-3-small | 하이브리드 | rerank-3 | `input` 전체 | 0.895 | 0.860 | 0.737 | 0.474 |
| text-embedding-3-small | 하이브리드 | rerank-3-lite | `input` 전체 | 0.895 | 0.842 | 0.684 | 0.474 |
| text-embedding-3-small | dense만 | 없음 | "질문:" 줄 | 0.789 | 0.546 | 0.421 | 0.263 |
| text-embedding-3-small | dense만 | rerank-3 | "질문:" 줄 | 1.000 | 0.974 | 0.684 | 0.421 |
| text-embedding-3-small | dense만 | rerank-3-lite | "질문:" 줄 | 1.000 | 0.882 | 0.684 | 0.474 |
| text-embedding-3-small | 하이브리드 | 없음 | "질문:" 줄 | 1.000 | 0.921 | 0.737 | 0.579 |
| text-embedding-3-small | 하이브리드 | rerank-3 | "질문:" 줄 | 0.947 | 0.921 | 0.895 | 0.526 |
| text-embedding-3-small | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.921 | 0.842 | 0.526 |
| KURE-v1 | dense만 | 없음 | `input` 전체 | 0.158 | 0.096 | 0.158 | 0.105 |
| KURE-v1 | dense만 | rerank-3 | `input` 전체 | 0.737 | 0.572 | 0.474 | 0.158 |
| KURE-v1 | dense만 | rerank-3-lite | `input` 전체 | 0.737 | 0.658 | 0.474 | 0.158 |
| KURE-v1 | 하이브리드 | 없음 | `input` 전체 | 0.368 | 0.225 | 0.211 | 0.053 |
| KURE-v1 | 하이브리드 | rerank-3 | `input` 전체 | 0.895 | 0.730 | 0.684 | 0.316 |
| KURE-v1 | 하이브리드 | rerank-3-lite | `input` 전체 | 0.895 | 0.816 | 0.684 | 0.316 |
| KURE-v1 | dense만 | 없음 | "질문:" 줄 | 0.526 | 0.311 | 0.316 | 0.158 |
| KURE-v1 | dense만 | rerank-3 | "질문:" 줄 | 0.895 | 0.833 | 0.526 | 0.211 |
| KURE-v1 | dense만 | rerank-3-lite | "질문:" 줄 | 0.895 | 0.860 | 0.526 | 0.211 |
| KURE-v1 | 하이브리드 | 없음 | "질문:" 줄 | 1.000 | 0.868 | 0.632 | 0.316 |
| KURE-v1 | 하이브리드 | rerank-3 | "질문:" 줄 | 0.947 | 0.886 | 0.842 | 0.474 |
| KURE-v1 | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.912 | 0.842 | 0.526 |
| Qwen3-Embedding-0.6B | dense만 | 없음 | `input` 전체 | 0.842 | 0.578 | 0.632 | 0.421 |
| Qwen3-Embedding-0.6B | dense만 | rerank-3 | `input` 전체 | 0.895 | 0.829 | 0.842 | 0.421 |
| Qwen3-Embedding-0.6B | dense만 | rerank-3-lite | `input` 전체 | 0.895 | 0.860 | 0.895 | 0.526 |
| Qwen3-Embedding-0.6B | 하이브리드 | 없음 | `input` 전체 | 0.789 | 0.675 | 0.632 | 0.368 |
| Qwen3-Embedding-0.6B | 하이브리드 | rerank-3 | `input` 전체 | 0.947 | 0.882 | 0.842 | 0.421 |
| Qwen3-Embedding-0.6B | 하이브리드 | rerank-3-lite | `input` 전체 | 0.947 | 0.873 | 0.895 | 0.526 |
| Qwen3-Embedding-0.6B | dense만 | 없음 | "질문:" 줄 | 0.947 | 0.659 | 0.842 | 0.474 |
| Qwen3-Embedding-0.6B | dense만 | rerank-3 | "질문:" 줄 | 1.000 | 0.921 | 0.895 | 0.474 |
| Qwen3-Embedding-0.6B | dense만 | rerank-3-lite | "질문:" 줄 | 1.000 | 0.932 | 0.895 | 0.579 |
| Qwen3-Embedding-0.6B | 하이브리드 | 없음 | "질문:" 줄 | 1.000 | 0.895 | 0.789 | 0.526 |
| Qwen3-Embedding-0.6B | 하이브리드 | rerank-3 | "질문:" 줄 | 0.947 | 0.908 | 0.895 | 0.474 |
| Qwen3-Embedding-0.6B | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.921 | 0.895 | 0.579 |
| voyage-4-lite | dense만 | 없음 | `input` 전체 | 0.526 | 0.392 | 0.526 | 0.211 |
| voyage-4-lite | dense만 | rerank-3 | `input` 전체 | 0.895 | 0.756 | 0.789 | 0.368 |
| voyage-4-lite | dense만 | rerank-3-lite | `input` 전체 | 0.895 | 0.759 | 0.789 | 0.368 |
| voyage-4-lite | 하이브리드 | 없음 | `input` 전체 | 0.579 | 0.443 | 0.526 | 0.316 |
| voyage-4-lite | 하이브리드 | rerank-3 | `input` 전체 | 0.947 | 0.809 | 0.895 | 0.421 |
| voyage-4-lite | 하이브리드 | rerank-3-lite | `input` 전체 | 0.947 | 0.820 | 0.895 | 0.474 |
| voyage-4-lite | dense만 | 없음 | "질문:" 줄 | 0.474 | 0.432 | 0.368 | 0.105 |
| voyage-4-lite | dense만 | rerank-3 | "질문:" 줄 | 0.737 | 0.675 | 0.579 | 0.158 |
| voyage-4-lite | dense만 | rerank-3-lite | "질문:" 줄 | 0.789 | 0.715 | 0.684 | 0.316 |
| voyage-4-lite | 하이브리드 | 없음 | "질문:" 줄 | 1.000 | 0.838 | 0.684 | 0.316 |
| voyage-4-lite | 하이브리드 | rerank-3 | "질문:" 줄 | 0.947 | 0.921 | 0.895 | 0.421 |
| voyage-4-lite | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.886 | 0.895 | 0.579 |
| voyage-4 | dense만 | 없음 | `input` 전체 | 0.474 | 0.300 | 0.316 | 0.211 |
| voyage-4 | dense만 | rerank-3 | `input` 전체 | 0.895 | 0.774 | 0.842 | 0.474 |
| voyage-4 | dense만 | rerank-3-lite | `input` 전체 | 0.895 | 0.756 | 0.842 | 0.474 |
| voyage-4 | 하이브리드 | 없음 | `input` 전체 | 0.579 | 0.382 | 0.421 | 0.263 |
| voyage-4 | 하이브리드 | rerank-3 | `input` 전체 | 0.895 | 0.800 | 0.842 | 0.421 |
| voyage-4 | 하이브리드 | rerank-3-lite | `input` 전체 | 0.895 | 0.765 | 0.842 | 0.421 |
| voyage-4 | dense만 | 없음 | "질문:" 줄 | 0.632 | 0.475 | 0.474 | 0.316 |
| voyage-4 | dense만 | rerank-3 | "질문:" 줄 | 0.789 | 0.750 | 0.684 | 0.316 |
| voyage-4 | dense만 | rerank-3-lite | "질문:" 줄 | 0.842 | 0.761 | 0.789 | 0.421 |
| voyage-4 | 하이브리드 | 없음 | "질문:" 줄 | 1.000 | 0.829 | 0.737 | 0.526 |
| voyage-4 | 하이브리드 | rerank-3 | "질문:" 줄 | 0.895 | 0.855 | 0.789 | 0.421 |
| voyage-4 | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.866 | 0.842 | 0.474 |
| voyage-4-large | dense만 | 없음 | `input` 전체 | 0.526 | 0.332 | 0.526 | 0.211 |
| voyage-4-large | dense만 | rerank-3 | `input` 전체 | 0.789 | 0.763 | 0.737 | 0.368 |
| voyage-4-large | dense만 | rerank-3-lite | `input` 전체 | 0.789 | 0.750 | 0.737 | 0.368 |
| voyage-4-large | 하이브리드 | 없음 | `input` 전체 | 0.526 | 0.403 | 0.368 | 0.211 |
| voyage-4-large | 하이브리드 | rerank-3 | `input` 전체 | 0.895 | 0.868 | 0.842 | 0.368 |
| voyage-4-large | 하이브리드 | rerank-3-lite | `input` 전체 | 0.842 | 0.803 | 0.789 | 0.368 |
| voyage-4-large | dense만 | 없음 | "질문:" 줄 | 0.579 | 0.509 | 0.474 | 0.316 |
| voyage-4-large | dense만 | rerank-3 | "질문:" 줄 | 0.947 | 0.912 | 0.842 | 0.474 |
| voyage-4-large | dense만 | rerank-3-lite | "질문:" 줄 | 1.000 | 0.904 | 0.895 | 0.526 |
| voyage-4-large | 하이브리드 | 없음 | "질문:" 줄 | 0.947 | 0.868 | 0.895 | 0.526 |
| voyage-4-large | 하이브리드 | rerank-3 | "질문:" 줄 | 0.947 | 0.912 | 0.842 | 0.474 |
| voyage-4-large | 하이브리드 | rerank-3-lite | "질문:" 줄 | 0.947 | 0.895 | 0.842 | 0.579 |

### 3.4 질문 1건 단계별 시간(p50 / p95, 초)

| 모델 | 질의 글 | 질문 임베딩 | DB 정확 검색(상위 50) |
|---|---|---:|---:|
| text-embedding-3-small | `input` 전체 | 0.873 / 1.075 | 0.168 / 0.174 |
| text-embedding-3-small | "질문:" 줄 | 0.881 / 1.793 | 0.165 / 0.173 |
| KURE-v1 | `input` 전체 | 0.018 / 0.021 | 0.136 / 0.138 |
| KURE-v1 | "질문:" 줄 | 0.034 / 0.062 | 0.137 / 0.14 |
| Qwen3-Embedding-0.6B | `input` 전체 | 0.05 / 0.063 | 0.135 / 0.137 |
| Qwen3-Embedding-0.6B | "질문:" 줄 | 0.047 / 0.058 | 0.134 / 0.136 |
| voyage-4-lite | `input` 전체 | 0.182 / 0.204 | 0.136 / 0.141 |
| voyage-4-lite | "질문:" 줄 | 0.183 / 0.213 | 0.136 / 0.137 |
| voyage-4 | `input` 전체 | 0.185 / 0.204 | 0.138 / 0.14 |
| voyage-4 | "질문:" 줄 | 0.183 / 0.207 | 0.137 / 0.14 |
| voyage-4-large | `input` 전체 | 0.212 / 0.242 | 0.137 / 0.143 |
| voyage-4-large | "질문:" 줄 | 0.208 / 0.263 | 0.136 / 0.148 |
| BM25 (메모리) | `input` 전체 | - | 0.091 / 0.137 |
| BM25 (메모리) | "질문:" 줄 | - | 0.017 / 0.027 |

| 리랭커 | 후보 | 호출 수 | 리랭크 p50 / p95 |
|---|---|---:|---:|
| rerank-3 | BM25만 후보 | 38 | 0.298 / 0.352 |
| rerank-3 | dense만 후보 | 228 | 0.285 / 0.341 |
| rerank-3 | 하이브리드 후보 | 228 | 0.324 / 0.408 |
| rerank-3-lite | BM25만 후보 | 38 | 0.298 / 0.537 |
| rerank-3-lite | dense만 후보 | 228 | 0.276 / 0.345 |
| rerank-3-lite | 하이브리드 후보 | 228 | 0.310 / 0.468 |

지연은 desktop-gpu에서 잰 값이다. text-embedding-3-small 질문 임베딩은 OpenRouter 왕복, Voyage는 Voyage API 왕복, KURE와 Qwen은 로컬 GPU 값이다. Cloud Run이나 Supabase 값이 아니다.

## 4. 결정에 미치는 영향

서비스 검색 설정은 [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md)가 정한다(사전 등록 #25의 1위 설정, `voyage-4-large` 1024차원). 서비스 코드의 임베딩 모델은 `backend/rag/retrieve.py:29` `EMBED_MODEL = 'voyage-4-large'`다.

## 5. 사전 등록 #16 기대와 대조

기대 수치의 정본은 [preregister.md](../../evals/guides/preregister.md) #16이다.

| 기대 | 측정 | 맞음/틀림 |
|---|---|---|
| 기준 칸: Recall@5 0.84~1.00, MRR 0.70~0.92, 쪽 적중@5 0.50~0.80 | 0.737, 0.649, 0.368 | 셋 다 틀림 |
| 하이브리드 - dense만 MRR +0.00~+0.15 | `input` 전체 6종 +0.051~+0.129, "질문:" 줄 6종 +0.236~+0.557 | `input` 전체 맞음, "질문:" 줄 틀림 |
| BM25만(`input` 전체) Recall@5 0.55~0.95, MRR 0.40~0.85 | 0.263, 0.195 | 틀림 |
| "질문:" 줄 - `input` 전체: BM25만 MRR +0.00~+0.20, 하이브리드 MRR -0.02~+0.10 | BM25만 +0.744, 하이브리드 6종 +0.220~+0.643 | 틀림 |
| 하이브리드, `input` 전체에서 모델 - 3-small: Voyage 3종 -0.05~+0.10, KURE와 Qwen -0.10~+0.05 | Voyage -0.206, -0.267, -0.246. KURE -0.424. Qwen +0.026 | Qwen만 맞음 |
| `voyage-4-large` - `voyage-4-lite` MRR 0.00~+0.08 | -0.040 | 틀림 |
| 리랭커 - 같은 후보 리랭커 없음 MRR +0.00~+0.15 | 52칸 중 15칸 범위 안, 37칸 위(최대 +0.591), 아래 0칸 | 대부분 틀림(더 큼) |
| `rerank-3` - `rerank-3-lite` MRR 0.00~+0.05 | 26쌍 중 12쌍 안, 2쌍 위, 12쌍 아래(-0.086~+0.092) | 반반 |
| 리랭크 p95 질문당 0.5~3초(후보 100장) | 후보 종류별 p95 0.341~0.537초(3.4절) | 대부분 틀림(더 빠름) |

## 6. 한계

- 19문항이다. 한 문항이 MRR을 최대 0.053 움직인다.
- 한 번만 돌렸다. API 모델과 리랭커가 다시 돌려도 같은 순위를 내는지는 확인하지 않았다.
- 비관련 25문항의 거절과 답변 채점은 재지 않았다.
- 품번 필터, HNSW, halfvec은 넣지 않았다.
- 레포에 없는 것: 실행 로그, 78칸 비교 그래프(`compare.html`).
