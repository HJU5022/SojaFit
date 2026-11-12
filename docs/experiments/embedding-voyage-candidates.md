# Voyage 임베딩 후보 추가 계약

- 상태: 폐기
- 기준일: 2026-11-12 (설계 2026-11-02)
- 기준 커밋: 6707002
- 정본 여부: 비정본. 대체: 사전 등록 #25 R1 비교로 서비스는 `voyage-4-large` 1024차원 ([SPEC.md](../../SPEC.md) 6절, [EVAL_REPORT.md](../../EVAL_REPORT.md) 1-4절, [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md))
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [embedding-candidate-runner.md](embedding-candidate-runner.md)

## 1. 폐기 사유와 확인 결과

| 항목 | 값 | 근거 |
|---|---|---|
| 설계 내용 | 로컬 `voyageai/voyage-4-nano`와 OpenRouter `voyageai/voyage-4`를 1024차원, query/document 분리 조건으로 평가 | 아래 2절 |
| 구현·시험 | 없음. 후보 평가기와 시험 파일이 저장소에 없다 | `evals/runners/benchmark_embeddings.py:28` |
| 입력 표본 | `embedding_real_pdf_smoke_v0.jsonl`(`evals/` 아래) 없음 | 저장소 목록 |
| 원시 결과 | Voyage 4 Nano, OpenRouter Voyage 4 평가기의 원시 JSON 없음. 사전 등록 #16 격자에는 `voyage-4`, `voyage-4-large`, `voyage-4-lite`의 결과가 있다 | `evals/results/embedding/grid_embed_voyage_4*_2026-11-02.json` |
| 서비스 임베딩 | `voyage-4-large` 1024차원, 차원 없는 `halfvec` | `SPEC.md` 6절 |

## 2. 설계 계약(구현되지 않음)

| 항목 | 값 |
|---|---|
| 공통 표본 | 실제 PDF smoke JSONL: PDF 3건, 156청크, 질의 9건 |
| 공통 검색 | L2 정규화 dense 코사인, k=5, BM25·필터·리랭커 없음 |
| Nano | 모델 ID `voyageai/voyage-4-nano`, 모델·코드 revision `5fb34e870f49f19e79c94d5e118f5ee730133279`, `truncate_dim=1024`, `attn_implementation=sdpa`, `encode_query`·`encode_document`, `HF_HUB_OFFLINE=1` 재실행 |
| API | OpenRouter `voyageai/voyage-4`, 문서 `input_type=document`, 질의 `input_type=query`, `dimensions=1024`, 단가 $0.06/M tokens(실행 전 재확인), `backend/services/llm.py::embed_texts` 경계, 자동 재시도 0 |
| API 정책 차단 | ZDR·data-policy가 endpoint를 제외하면 계정 정책을 바꾸지 않고 오류·retry 0을 기록하며 Recall@5·MRR·비용 실측값을 만들지 않는다 |
| 범위 밖 | 서비스 기본 임베딩 변경, DB `vector(1536)` 이전, OpenRouter 계정 정책 변경, 전체 1,360건 본평가, 최종 모델 선정, Voyage 계열 간 공유 벡터 공간 검증 |

성공 호출과 응답 차원 검증 전에는 Voyage 4를 최종 모델로 선정하지 않는다. Nano와 API 점수는 서로 다른 후보로 보고 한 모델의 점수를 다른 모델에 옮기지 않는다.
