# 임베딩 모델 4종 예비 기준선

- 상태: 이력
- 기준일: 2026-11-12 (측정 2026-10-30)
- 기준 커밋: 6707002
- 정본 여부: 비정본. 임베딩 선택의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 1장(1-3 격자 본평가, 1-4 서비스 설정 선정)과 [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md)
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [embedding-candidate-investigation.md](../research/embedding-candidate-investigation.md), [evals/samples/SAMPLES.md](../../evals/samples/SAMPLES.md)

## 1. 질문과 결론

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 공개 벤치마크로는 영문 부품명·기호와 한국어 질의가 섞인 검색 품질, 비용, 오프라인 배포성을 알 수 없다. 본평가에 올릴 후보 4종을 같은 표본·검색 조건으로 줄일 수 있는가 | |
| 표본 | 30청크, 18질의. 실제 코퍼스가 아니라 공식 제품표의 대표 사양을 재서술한 프록시 | `evals/samples/embedding_sample_v0.jsonl`(48행) |
| 결과 | 4종 모두 Recall@5 1.0. MRR은 3.2절 | 3.2절 |
| 결정 | 최종 모델은 정하지 않았다. 이후 본평가는 사전 등록 #16 격자(`EVAL_REPORT.md` 1-3), 서비스 선택은 #25(`voyage-4-large` 1024차원) | `EVAL_REPORT.md` 1-3, 1-4, `SPEC.md` 6절 |

## 2. 조건

| 항목 | 규칙 |
|---|---|
| 후보 | `text-embedding-3-small`(OpenRouter API), `BAAI/bge-m3`, `nlpai-lab/KURE-v1`, `Qwen/Qwen3-Embedding-0.6B`(로컬, `cuda:0`) |
| 검색 | L2 정규화 dense 벡터의 내적 top-5, 리랭커·BM25 없음 |
| 지표 | 질의당 gold 1개. `Recall@5` = hit 질의 수 / 전체 질의 수, `MRR` = 첫 gold 순위 역수의 평균 |
| Qwen 질의 형식 | 문서는 원문, 질의에만 고정한 영문 instruction을 붙인다(`benchmark_embeddings.py` `QWEN_QUERY_PROMPT`). 결과를 본 뒤 문구를 바꾸지 않는다 |
| 지연 | warm-up 뒤 wall-clock. 1,000청크 임베딩과, 질의 1건 + 22,000개 exact matrix search(반복 벡터)를 구분. API와 로컬은 실행 환경이 달라 모델 자체 속도로 해석하지 않는다 |
| 비용 | API는 실제 usage가 없을 때 평균 350토큰/청크와 공식 단가의 추정치 |
| 용량 | pgvector `vector` float32 원시 벡터만 계산. 본문·메타데이터·행 오버헤드·인덱스 제외 |
| 결과 표기 | 모든 원시에 `proxy_smoke_test`, `dense_only`, `corpus_is_real=false`, `latency_corpus_vectors_are_repeated=true`, `eligible_for_final_model_decision=false` |

실행 불가 처리: 키가 없으면 `not_run_no_key`로 기록하고 0점으로 쓰지 않는다. 로컬 캐시가 없고 오프라인이면 온라인 다운로드로 바꾸지 않고 실패시킨다. 정답 청크 id가 표본에 없으면 측정 전에 `ValueError`로 멈춘다(`benchmark_embeddings.py` `load_sample`). 데모 모드(`DEMO_MODE=1`)의 미등록 질의는 API·벡터 검색 없이 BM25-only로 근거를 찾고 `live_vector_search=false`를 표시한다.

## 3. 결과

### 3.1 원시 파일

`evals/results/embedding/embedding_{text_embedding_3_small,bge_m3,kure_v1,qwen3_0_6b}_proxy_2026-10-30.json`과 오프라인 재실행 `..._proxy_offline_2026-10-30.json`(로컬 3종).

### 3.2 값

| 모델 | 차원 | Recall@5 | MRR | 1,000청크 임베딩 시간 | 22,000 exact 검색 p50 | 장치 |
|---|---:|---:|---:|---:|---:|---|
| `text-embedding-3-small` | 1536 | 1.0 | 0.907 | 7.0초 | 919ms | OpenAI API(추정 비용 $0.0008778) |
| `BAAI/bge-m3` | 1024 | 1.0 | 0.863 | 5.9초 | 47ms | cuda:0 |
| `nlpai-lab/KURE-v1` | 1024 | 1.0 | 0.894 | 5.8초 | 64ms | cuda:0 |
| `Qwen/Qwen3-Embedding-0.6B` | 1024 | 1.0 | 0.875 | 10.4초 | 44ms | cuda:0 |

로컬 3종의 오프라인 재실행(`HF_HUB_OFFLINE`)은 Recall@5와 MRR이 같다. 표본 18질의에서 Recall@5는 변별력이 없다.

## 4. 수용 기준

| 조건 | 기대 |
|---|---|
| 모든 질의에 gold가 있는 평가 | Recall@5, MRR, 질의별 첫 gold 순위를 JSON에 기록 |
| API 키 또는 로컬 캐시 없음 | 0점 대신 미실행 상태와 사유 |
| 모델을 한 번 내려받은 뒤 `HF_HUB_OFFLINE=1` 새 프로세스 | 다운로드 없이 같은 지표 |
| `DEMO_MODE=1`, 저장된 응답 없는 질의 | 외부 API·벡터 검색 없이 BM25-only 근거와 추출형 답, `live_vector_search=false` |

## 5. 한계

- 프록시 표본이다. 실제 코퍼스, 동결 평가셋, 공식 Recall·MRR이 아니며 최종 모델 결정 근거가 아니다.
- 원시 JSON의 `sample` 칸은 옛 경로(`evals/` 바로 아래의 `embedding_sample_v0.jsonl`)를 가리킨다. 파일은 지금 `evals/samples/embedding_sample_v0.jsonl`에 있다.
- API 모델의 지연·비용은 추정치이며 실행 환경이 로컬 모델과 다르다.
