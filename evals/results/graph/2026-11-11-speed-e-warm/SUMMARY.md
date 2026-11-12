# speed-e-warm 실측 (GATE_WARMUP=1 공통)
조건: mixed 9문항, RAGAS off, DOCS_RETRY_PARTIAL=1, DOCS_CITE_REPAIR=1
| run | pass | mean | p50 | p95 | 비고 |
|---|---:|---:|---:|---:|---|
| E0_hybrid_rerank | 8/9 | 10.89 | 9.6 | 28.4 | 기준선 hybrid+rerank |
| E1_no_rerank | 8/9 | 8.08 | 8.6 | 11.5 | RETRIEVE_RERANK=0 |
| E2_bm25 | 8/9 | 8.24 | 7.3 | 14.8 | RETRIEVE_METHOD=bm25 |

## 문항별 latency_s

| id | E0 | E1 | E2 | E0ok | E1ok | E2ok | E0 search_ms | E2 search_ms |
|---|---:|---:|---:|---|---|---|---:|---:|
| v3-01 | 6.3 | 8.6 | 6.6 | True | False | True | 0 | 0 |
| v3-03 | 6.0 | 5.6 | 5.5 | True | True | True | 1186 | 395 |
| v3-16 | 10.9 | 4.8 | 6.4 | True | True | True | 2652 | 762 |
| v3-20 | 16.3 | 11.5 | 9.4 | True | True | True | 5399 | 1719 |
| v3-21 | 9.6 | 8.9 | 7.3 | True | True | True | 2276 | 863 |
| v3-24 | 4.2 | 9.0 | 8.1 | True | True | True | 0 | 0 |
| v3-25 | 10.2 | 7.5 | 10.1 | True | True | True | 0 | 0 |
| v3-41 | 6.1 | 5.9 | 6.0 | True | True | True | 1134 | 523 |
| v3-15 | 28.4 | 10.9 | 14.8 | False | True | False | 5236 | 0 |

## 판정
- E0: GATE_WARMUP=1 기준선. p95=28.4는 v3-15 한 건(FAIL).
- E1: 검색 합 시간 감소(rerank ~0.3–0.4s/회). pass 8/9 동일이나 실패 문항이 v3-15→v3-01로 바뀜(경로·판정 흔들림). **기본 off 폐기**, 플래그만 유지.
- E2: bm25-only pass 8/9, p95=14.8(v3-15 `over_refusal`). 검색 합은 뚜렷히 줄음(예: v3-20 5399→1719ms). p95·실패는 Spec 경로라 검색 방식과 무관. Recall 목표(ADR 0015) 때문에 **기본 bm25 폐기**, `RETRIEVE_METHOD` 플래그만 유지.
- 공통 결론: 워밍업 후 남는 p95는 RAG LLM·다중 검색·Spec(`회로 읽기`/판정)이지 Voyage rerank 한 칸이 아님. 다음 실험 후보도 그쪽.
