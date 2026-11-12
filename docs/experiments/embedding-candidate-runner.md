# 임베딩 후보 확장 평가기 설계

- 상태: 폐기
- 기준일: 2026-11-12 (설계 2026-11-02)
- 기준 커밋: 6707002
- 정본 여부: 비정본. 대체: 임베딩 후보 비교는 사전 등록 #16 격자 [EVAL_REPORT.md](../../EVAL_REPORT.md) 1-3절과 서비스 설정 선정 1-4절. 후보 조사 기록은 [embedding-candidate-investigation.md](../research/embedding-candidate-investigation.md), 라이선스는 [model-licenses.md](../research/model-licenses.md)
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [embedding-model-baseline.md](embedding-model-baseline.md), [embedding-voyage-candidates.md](embedding-voyage-candidates.md)

## 1. 폐기 사유와 확인 결과

| 항목 | 값 | 근거 |
|---|---|---|
| 설계 내용 | 기본 실행 후보 9종과 Voyage 확장 2종(실행 11종), 조사 전용 2종을 한 평가기의 어댑터로 관리 | 아래 2절 |
| 구현 | 없음. `evals/runners/benchmark_embeddings.py`의 `MODELS`는 4종(`bge-m3`, `kure-v1`, `qwen3-embedding-0.6b`, `text-embedding-3-small`)뿐이다 | `benchmark_embeddings.py:28` |
| 시험 | 시험 파일 `test_benchmark_embeddings.py` 없음 | 저장소 목록 |
| 원시 결과 | 2026-11-02 확장 평가 원시 JSON 없음 | `evals/results/embedding/` |
| 임베딩 선택 경로 | 사전 등록 #16 격자(`evals/runners/run_embedding_grid.py`)와 R1 비교(#25)로 `voyage-4-large` 1024차원 선택 | `EVAL_REPORT.md` 1-3, 1-4, [SPEC.md](../../SPEC.md) 6절 |

## 2. 설계 계약(구현되지 않음)

목표: 공통 측정 로직(Recall@5, MRR, 지연)은 두고 모델별 로딩·질의·문서 형식만 어댑터로 분리한다. 평가셋 2차 판정과 동결 전 결과는 최종 모델 결정에 쓰지 않는다.

| 구분 | 모델 | 라이선스·약관 | 실행 분류 |
|---|---|---|---|
| API 기준선 | `text-embedding-3-small` | OpenAI/OpenRouter 서비스 약관 | 운영 후보 |
| API 확장 | `voyageai/voyage-4` | OpenRouter 서비스 약관 | 평가용 실행 후보 |
| 로컬 확장 | `voyageai/voyage-4-nano` | Apache-2.0 | 상업 후보, 로컬 |
| 다국어 기준선 | `BAAI/bge-m3` | MIT | 운영 후보 |
| 한국어 특화 | `nlpai-lab/KURE-v1` | MIT | 운영 후보 |
| instruct/decoder | `Qwen/Qwen3-Embedding-0.6B` | Apache-2.0 | 운영 후보 |
| 경량 다국어 | `Alibaba-NLP/gte-multilingual-base` | Apache-2.0 | 운영 후보 |
| instruct 대조군 | `intfloat/multilingual-e5-large-instruct` | MIT | 운영 후보 |
| 비상업 대조군 | `jinaai/jina-embeddings-v3` | CC BY-NC 4.0 | 연구용 후보 |
| MoE 다국어 | `nomic-ai/nomic-embed-text-v2-moe` | Apache-2.0 | 운영 후보 |
| 경량 검색 특화 | `Snowflake/snowflake-arctic-embed-m-v2.0` | Apache-2.0 | 운영 후보 |
| 조사 전용 | `google/embeddinggemma-300m` | Gemma 약관, 접근 전 동의 | 실행 제외 |
| 조사 전용 | `jinaai/jina-embeddings-v4` | Qwen Research License, 약 7.89GB | 실행 제외 |

| 모델 계열 | 문서 | 질의 |
|---|---|---|
| BGE, KURE, GTE | 원문 | 원문 |
| Qwen3 | 원문 | 프록시에서 고정한 영문 instruction + 질의 |
| multilingual-E5 | 원문 | 한 문장 고정 검색 instruction + 질의 |
| Jina v3 | `retrieval.passage` task | `retrieval.query` task |
| Nomic v2 | 모델 카드의 document prefix | 모델 카드의 query prefix |
| Arctic v2 | 원문 | 공식 `query` prompt |

| 상황 | 처리(설계) |
|---|---|
| API 키 없음 | `not_run_no_key`, 로컬 모델로 자동 대체하지 않음 |
| 오프라인 캐시에 revision 없음 | 네트워크로 자동 전환하지 않고 실패 |
| `trust_remote_code=True` 필요 | 불변 revision이 없으면 로드 거부 |
| 입력 형식 미등록 | 일반 인코딩으로 추측하지 않고 등록 오류 |
| 출력 차원이 선언값과 다름 | 유효 점수로 기록하지 않음 |
| 연구용 모델 점수가 가장 높음 | 결과는 보존하되 운영 후보로 추천하지 않음 |
| 평가셋 미동결 | 프록시 실행만 허용, `eligible_for_final_model_decision=false` |

Hugging Face 후보는 40자리 불변 커밋 SHA만 허용한다(`main`, 태그 금지). 입력 형식은 결과를 본 뒤 바꾸지 않는다.

## 3. 한계

- 표의 라이선스·revision 값은 설계 당시 값이며 이 저장소에서 다시 확인하지 않았다. 라이선스 확인 결과는 `docs/research/model-licenses.md`를 따른다.
