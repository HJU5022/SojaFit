# 임베딩 후보 13종 개별 조사·평가 기록

확인일: 2026-11-02

## 이 문서의 범위

이 문서는 후보 13종을 모두 같은 수준으로 평가했다는 뜻이 아니다. 각 후보를 목록에 넣은 이유, 실제로 수행한 조사와 실행, 중단하거나 조사 전용으로 남긴 이유, 다음 평가 조건을 구분한다. 라이선스 원문과 공개 범위는 [model-licenses.md](model-licenses.md), 공통 실행 조건과 결과 수치는 루트 [EVAL_REPORT.md](../../EVAL_REPORT.md)를 따른다.

> **상태**: 이 문서는 로컬 탐색 실험의 조사·결과 기록만 보존한다. 2026-11-02 확장 평가기, 입력 표본, 테스트와 `evals/results/embedding_*_2026-11-02.json` 원시 파일은 이번 문서 변경에 포함하지 않았다. 아래의 해당 경로는 로컬 실험 산출물 식별자이며 현재 `main`의 파일을 뜻하지 않는다. 따라서 2026-11-02 상세값은 **로컬 탐색·원시 미반영** 상태이며, 현재 저장소만으로 재현·감사하거나 최종 모델 선정 증거로 승격할 수 없다.

| 증거 수준 | 모델 수 | 뜻 |
|---|---:|---|
| 실제 PDF smoke 완료 | 5 | 같은 실제 PDF 3건·156청크·질의 9건에서 Recall@5·MRR을 얻음 |
| 합성 프록시만 완료 | 1 | 초기 30청크·18질의에서만 수치를 얻었고 실제 PDF 비교에는 넣지 않음 |
| 호환성 확인에서 차단 | 4 | 실행을 시도·검토했지만 환경 또는 의존성 문제로 품질 수치를 만들지 못함 |
| API 정책에서 차단 | 1 | OpenRouter 요청은 도달했지만 계정 ZDR/data-policy와 endpoint가 맞지 않아 품질 수치를 만들지 못함 |
| 조사 전용 | 2 | 약관·라이선스·자원 조건 때문에 이번 실행 대상에서 미리 제외함 |

모든 수치는 2차 판정과 평가셋 동결 전 탐색 결과다. `eligible_for_final_model_decision=false`이며 최종 모델 선정 근거로 단독 사용하지 않는다.

## 운영 전제와 결과 해석

2026-11-02 조사 당시 서비스 적재·검색은 `text-embedding-3-small` API와 `vector(1536)`을 사용했다. 이 문서의 로컬 실행과 추가 API allowlist는 당시 후보의 품질·입력 계약·오프라인 재현성을 확인한 기록이며 현재 서비스 기본값을 정하지 않는다. 이후 사전 등록 #25와 ADR 0004 갱신으로 현재 서비스 코드는 `voyage-4-large` 1024차원·차원 없는 `halfvec`을 사용한다. 현재 계약과 선정 근거는 루트 `SPEC.md` 6절과 `EVAL_REPORT.md` 1-4절을 따른다.

같은 계열 이름도 같은 모델로 간주하지 않는다. 현재 로컬 `multilingual-e5-large-instruct` 결과를 OpenRouter의 `intfloat/multilingual-e5-large`에 이전할 수 없고, 로컬 `voyage-4-nano` 결과도 API `voyage-4`의 결과가 아니다. API provider가 사용하는 revision·정밀도·양자화·정규화·입력 전처리를 공개하지 않거나 바꿀 수 있으므로 최종 결과에는 모델 ID, provider 정책, 실행일, 차원, 입력 형식, 비용과 지연을 함께 기록한다.

## 공통 조사 과정

1. 공식 모델 저장소와 고정 revision에서 모델 카드, 라이선스·약관, 차원, 입력 형식, 원격 코드 여부를 확인했다.
2. 실행 후보는 모델 revision과 필요한 외부 코드 revision을 40자리 커밋 SHA로 고정했다.
3. 모델별 query/document 형식을 먼저 고정하고 공통 dense cosine `k=5` 평가기에 등록했다.
4. 다운로드·API 비용과 중단 조건을 기록한 뒤 프록시를 실행했다. 오류가 난 후보는 자동 재시도하지 않고 오류 단계와 원인을 JSON으로 보존했다.
5. 실행 성공 후보는 실제 TSC PDF 3건을 기존 Docling·card chunker로 만든 156청크와 사전 고정한 한국어 질의 9건에서 오프라인으로 다시 측정했다.

## 1. `text-embedding-3-small`

- **후보로 넣은 이유**: 현재 프로젝트의 API 기준선이며 로컬 GPU·모델 배포 없이 사용할 수 있어 품질과 운영 복잡도의 기준점이 된다.
- **조사·실행 과정**: OpenAI/OpenRouter 서비스 약관과 1,536차원 출력을 확인했다. 중앙 API 경계인 `backend/services/llm.py::embed_texts`를 사용해 합성 30청크·18질의 프록시를 실행했다.
- **확인된 결과**: 합성 프록시 Recall@5 `1.000`, MRR `0.907`, 총 45,699토큰, 비용 `$0.00091398`이다.
- **실제 PDF에서 멈춘 이유**: 실제 PDF smoke는 신규 API 과금을 발생시키지 않는 범위로 승인되어 로컬 후보만 실행했다. 키 없는 데모의 BM25-only 결과는 API 임베딩 품질을 나타내지 않으므로 대체 점수로 쓰지 않았다.
- **현재 판단·다음 조건**: 합성 표본 수치만 있어 실제 PDF 4종과 직접 비교할 수 없다. 동결 평가셋과 전체 청크가 준비되면 예상 토큰·비용 상한을 먼저 제시하고 별도 승인을 받아 기준선으로 실행한다.
- **증거**: `evals/results/embedding/embedding_text_embedding_3_small_proxy_2026-10-30.json`

## 2. `BAAI/bge-m3`

- **후보로 넣은 이유**: 다국어·긴 문맥을 지원하는 널리 쓰이는 로컬 검색 기준선이며 MIT 라이선스로 상업 후보에 둘 수 있다.
- **조사·실행 과정**: 모델 revision `5617a9f...`을 고정하고 별도 query instruction 없이 1,024차원 dense embedding으로 측정했다. RTX 5060 Laptop GPU에서 실행한 뒤 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `--network none`으로 재현했다.
- **확인된 결과**: 실제 PDF smoke Recall@5 `0.889`, MRR `0.753`, 1,000청크 `17.60초`다.
- **여기까지만 한 이유**: 3문서·9질의는 모델 로딩과 검색 계약을 확인하는 smoke일 뿐이고 2차 판정·전체 코퍼스가 준비되지 않았다.
- **현재 판단·다음 조건**: 본평가 대상이다. 동결된 동일 입력에서 API 기준선과 BM25 결합 조건을 고정해 다시 측정한다.
- **증거**: `evals/results/embedding_bge-m3_real_pdf_smoke_2026-11-02.json`

## 3. `nlpai-lab/KURE-v1`

- **후보로 넣은 이유**: 한국어 질의에 특화된 로컬 후보여서 한국어 질문과 영문 데이터시트 사이 검색에 이점이 있는지 확인할 가치가 있다. MIT 라이선스다.
- **조사·실행 과정**: revision `8b418a5...`, 1,024차원, 일반 query/document 입력을 고정했다. BGE와 같은 GPU·표본·검색 조건에서 실행하고 완전 오프라인 재실행을 확인했다.
- **확인된 결과**: 실제 PDF smoke Recall@5 `0.889`, MRR `0.808`, 1,000청크 `18.05초`로 성공 5종 중 MRR이 가장 높았다.
- **여기까지만 한 이유**: 표본이 작고 품번이 질의에 직접 들어 있어 한국어 특화 효과라고 단정할 수 없다. 모든 성공 후보가 패키지와 전력의 다중 근거 질문을 top-5에서 놓쳤다.
- **현재 판단·다음 조건**: 본평가 대상이지만 현재 수치만으로 선정하지 않는다. 동결 50건과 전체 코퍼스에서 다중 근거 Recall@5까지 비교한다.
- **증거**: `evals/results/embedding_kure-v1_real_pdf_smoke_2026-11-02.json`

## 4. `Qwen/Qwen3-Embedding-0.6B`

- **후보로 넣은 이유**: 0.6B급 최신 다국어 instruct 후보이며 질의 목적을 명시할 수 있어 부품 정격·패키지·시험 조건 검색에 유리할 가능성이 있다. Apache-2.0이다.
- **조사·실행 과정**: revision `97b0c61...`과 영문 query instruction을 결과 확인 전에 고정했다. 문서는 원문, 질의는 instruction과 한국어 질문을 결합했으며 같은 GPU·표본에서 오프라인 실행했다.
- **확인된 결과**: 저장소에 있는 30청크 원시 결과는 Recall@5 `1.000`, MRR `0.875`, 1,000청크 `3.83초`다. 별도 로컬 기록에는 실제 PDF smoke 값과 `10.37초`가 적혀 있지만 대응 원시 JSON이 없고, 이 시간은 기존 Windows 30청크 원시값 `10.372056...초`와 같아 실제 PDF 재측정값인지 확인할 수 없다. 원시가 없는 `3.63초` 재측정 기록도 제출 근거에서 제외한다.
- **여기까지만 한 이유**: instruction 유무·문구는 별도 실험 변수이고 결과를 본 뒤 바꾸면 공정하지 않다. 현재 smoke에서 문구를 조정하지 않았다.
- **현재 판단·다음 조건**: 고정 instruction 그대로 본평가한 뒤, 필요할 때만 별도 사전등록으로 instruction A/B를 수행한다.
- **증거**: `evals/results/embedding/embedding_qwen3_0_6b_proxy_offline_2026-10-30.json`. 실제 PDF smoke 식별자 `evals/results/embedding_qwen3-embedding-0.6b_real_pdf_smoke_2026-11-02.json`은 저장소에 없으므로 증거가 아니라 미반영 로컬 기록이다.

## 5. `Alibaba-NLP/gte-multilingual-base`

- **후보로 넣은 이유**: 305M·768차원의 경량 다국어 후보여서 BGE와 품질이 비슷하면 DB 용량과 배포 자원을 줄일 가능성이 있다. Apache-2.0이다.
- **조사·실행 과정**: 모델 revision `9bbca17...`과 외부 코드 `Alibaba-NLP/new-impl` revision `40ced75...`을 함께 고정했다. 원격 코드를 정적 점검하고, 첫 CUDA 오류 뒤 attention 구현만 `eager`로 바꿔 사전등록한 1회 호환성 재검증을 했다.
- **중단 이유**: 변경 후에도 CUDA device-side assert가 발생했다. 같은 오류의 반복 실행은 품질 증거를 만들지 못하고 GPU 상태만 불안정하게 할 수 있어 재시도 0회로 중단했다.
- **현재 판단·다음 조건**: 품질 0점이나 탈락이 아니라 `호환성 차단`이다. 고정된 CPU 환경 또는 검증된 CUDA·PyTorch 조합을 별도 준비한 뒤 같은 표본으로 다시 실행해야 한다.
- **증거**: `evals/results/embedding_gte-multilingual-base_compat_2026-11-02.json`

## 6. `intfloat/multilingual-e5-large-instruct`

- **후보로 넣은 이유**: 다국어 검색에서 널리 쓰이는 instruct 계열 대조군으로, 최신 후보의 결과가 기존 계열보다 실제로 나은지 비교할 기준이 된다. MIT 라이선스다.
- **조사·실행 과정**: revision `274baa4...`, 1,024차원, 고정 영문 검색 instruction을 사용했다. 같은 실제 PDF 표본·GPU에서 실행하고 오프라인 재현을 확인했다.
- **확인된 결과**: 실제 PDF smoke Recall@5 `0.778`, MRR `0.575`, 1,000청크 `5.23초`다.
- **여기까지만 한 이유**: 입력 길이 512토큰 제한과 작은 smoke만으로 운영 이점·손실을 판단할 수 없다. 현재 결과에서는 1N5817 VF 조건 gold가 10위였다.
- **현재 판단·다음 조건**: 속도 대조군으로 본평가에 유지한다. 실제 청크가 512토큰 계약을 넘지 않는지도 함께 검증한다.
- **증거**: `evals/results/embedding_multilingual-e5-large-instruct_real_pdf_smoke_2026-11-02.json`

## 7. `jinaai/jina-embeddings-v3`

- **후보로 넣은 이유**: 다국어 retrieval task 어댑터를 제공해 기술적 비교 가치는 있지만 CC BY-NC 4.0이므로 상업 운영 후보가 아닌 연구용 대조군이다.
- **조사·실행 과정**: 모델 revision `ab036b0...`과 외부 코드 revision `bd55a5e...`을 고정하고 `retrieval.query`·`retrieval.passage` task를 등록했다. 고정 모델 조건이 요구하는 Sentence Transformers 3.1.0 조합으로 오프라인 재검증을 준비했다.
- **중단 이유**: 승인된 오프라인 uv 캐시에 `sentence-transformers==3.1.0`이 없어 환경 해석 단계에서 멈췄다. 네트워크로 패키지를 임의 추가하지 않았고 모델 실행 자체가 시작되지 않았다.
- **현재 판단·다음 조건**: 품질 미측정 연구 후보다. 비상업 연구 비교가 여전히 필요할 때만 고정 패키지를 검토·캐시한 별도 환경에서 실행하며 운영 추천에는 포함하지 않는다.
- **증거**: `evals/results/embedding_jina-embeddings-v3_compat_2026-11-02.json`

## 8. `nomic-ai/nomic-embed-text-v2-moe`

- **후보로 넣은 이유**: 다국어 MoE 구조와 query/document prefix를 사용하는 상업 가능 Apache-2.0 후보라서 구조가 다른 대조군 가치가 있다.
- **조사·실행 과정**: 모델 revision `1066b65...`과 Nomic BERT 코드 revision `7710840...`을 고정하고 공식 query/document prefix를 등록했다. 오류 후 고정 README의 runtime extras를 검토했다.
- **중단 이유**: README가 `megablocks`를 커밋이 고정되지 않은 Git URL에서 설치하도록 요구했다. 알 수 없는 최신 외부 코드를 실행 환경에 넣으면 재현성과 공급망 안전 조건을 위반하므로 설치 전에 중단했다.
- **현재 판단·다음 조건**: 품질 0점이 아니라 `UnpinnedDependencyError`로 차단됐다. 호환되는 `megablocks` 커밋을 특정하고 코드를 검토한 뒤에만 다시 실행한다.
- **증거**: `evals/results/embedding_nomic-embed-text-v2-moe_compat_2026-11-02.json`

## 9. `Snowflake/snowflake-arctic-embed-m-v2.0`

- **후보로 넣은 이유**: 경량 검색 특화 다국어 후보이며 Apache-2.0이라 운영 후보로 검토할 수 있다.
- **조사·실행 과정**: 모델과 저장소 내부 코드 revision을 `95c2741...`로 고정하고 공식 `query` prompt를 등록했다. 첫 warmup 오류 뒤 모델 설정이 가리키는 Sentence Transformers 2.7.0·Transformers 4.39.3 조합을 확인했다.
- **중단 이유**: 승인된 오프라인 uv 캐시에 `sentence-transformers==2.7.0`이 없어 환경 해석 단계에서 중단했다. 임의 버전으로 실행해 모델 문제와 환경 문제를 섞지 않았다.
- **현재 판단·다음 조건**: 품질 미측정 호환성 차단 후보다. 고정된 구버전 의존성을 별도 격리 환경에서 보안·호환성 검토한 뒤 재실행한다.
- **증거**: `evals/results/embedding_snowflake-arctic-embed-m-v2.0_compat_2026-11-02.json`

## 10. `google/embeddinggemma-300m`

- **후보로 넣은 이유**: 300M급 경량 후보라 로컬 자원·응답 시간 측면의 조사 가치는 있다.
- **조사 과정**: 공식 저장소 revision `57c266a...`, 모델 카드, Gemma 약관과 접근 조건을 확인하고 후보 registry에는 메타데이터만 등록했다.
- **조사만 한 이유**: 가중치 접근 전에 Gemma 약관 동의가 필요하고 재배포 조건 검토도 끝나지 않았다. 사용자 계정의 약관 동의나 gated 모델 다운로드를 임의로 대신할 수 없어 실행 대상에서 제외했다.
- **현재 판단·다음 조건**: 약관 동의 주체, 상업 사용·재배포 조건, 가중치 배포 방식을 팀이 확인한 뒤에만 다운로드 예산과 실행 승인을 별도로 받는다.
- **증거**: [model-licenses.md](model-licenses.md)와 [embedding-candidate-runner.md](../experiments/embedding-candidate-runner.md)의 조사 전용 설계. Recall@5·MRR 원시 결과는 없다.

## 11. `jinaai/jina-embeddings-v4`

- **후보로 넣은 이유**: 최신 다국어·멀티모달 계열의 연구 비교 후보로 조사 범위를 넓히기 위해 포함했다.
- **조사 과정**: 공식 저장소 revision `853c867...`, Qwen Research License, 모델 카드에 따른 약 7.89GB 규모를 확인하고 실행 제외 메타데이터로 등록했다.
- **조사만 한 이유**: 연구 라이선스라 상업 운영 후보가 아니며 다른 후보보다 다운로드·저장·GPU 부담이 크다. 동결 전 작은 smoke를 위해 큰 가중치를 받는 실익이 낮아 실행하지 않았다.
- **현재 판단·다음 조건**: 상업 후보 비교에서는 계속 제외한다. 연구 목적이 명확하고 별도 용량·시간 예산이 승인될 때만 연구 결과표용으로 실행한다.
- **증거**: [model-licenses.md](model-licenses.md)와 [embedding-candidate-runner.md](../experiments/embedding-candidate-runner.md)의 조사 전용·연구용 설계. Recall@5·MRR 원시 결과는 없다.

## 12. `voyageai/voyage-4-nano`

- **후보로 넣은 이유**: Voyage 4 계열의 Apache-2.0 오픈 가중치 모델로, 32K 문맥과 256~2,048 가변 차원을 지원하면서 로컬 실행이 가능하다. 기존 1,024차원 후보와 같은 DB 조건으로 비교할 수 있다.
- **조사·실행 과정**: 모델과 원격 코드 revision을 `5fb34e8...`로 함께 고정했다. 원격 코드 3,491자에서 프로세스·네트워크·동적 실행·파일 쓰기 패턴을 정적 검색한 뒤 `sdpa`, 1,024차원, `encode_query`/`encode_document`를 고정했다. RTX 5060 Laptop GPU에서 실제 PDF smoke를 실행하고 `--network none`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`로 재실행했다.
- **확인된 결과**: Recall@5 `0.889`, MRR `0.744`, 1,000청크 `5.29초`, 질의 p50/p95 `53.9/80.5ms`다. BZT52C2V4 패키지·전력 다중 근거 질문의 첫 gold는 9위였다.
- **여기까지만 한 이유**: 실제 문서 3건·질의 9건의 비동결 smoke이고 CPU·Cloud Run 지연은 측정하지 않았다. 공식 Voyage API 계열과 공유 embedding 공간이라는 주장도 이번 로컬 실험에서는 교차 검증하지 않았다.
- **현재 판단·다음 조건**: 로컬 연구 기준점으로 유지한다. 외부 관리형 API만 사용하면 endpoint 확인 전에는 운영 후보가 아니지만, 팀이 자체 추론 API를 운영하면 운영 후보가 될 수 있다. 512차원·양자화는 필요할 때 별도 사전등록으로 분리한다.
- **증거**: `evals/results/embedding_voyage-4-nano_real_pdf_smoke_2026-11-02.json`, `evals/results/embedding_voyage-4-nano_real_pdf_smoke_offline_2026-11-02.json`

## 13. `voyageai/voyage-4`

- **후보로 넣은 이유**: OpenRouter에서 제공하는 다국어 Voyage 4 균형형 API 모델로, `text-embedding-3-small`과 API 품질·비용을 비교하고 Nano와 같은 1,024차원으로 맞출 수 있다.
- **조사·실행 과정**: 중앙 `embed_texts` 경계의 allowlist에 추가하고 문서 `input_type=document`, 질의 `input_type=query`, `dimensions=1024`, 자동 재시도 0을 고정했다. 첫 명령은 API 호출 전 `PYTHONPATH` 누락으로 실패해 오류 JSON을 보존했고, 실행 환경만 교정해 한 번 요청했다.
- **중단 이유**: OpenRouter가 계정의 ZDR/data-policy guardrail 때문에 사용 가능한 유일 endpoint를 제외해 404를 반환했다. 개인정보 정책을 낮추거나 계정 설정을 바꾸지 않고 중단했다. 성공 embedding과 usage가 없어 Recall@5·MRR·비용은 측정하지 못했다.
- **현재 판단·다음 조건**: 품질 탈락이 아니라 `API 정책 차단`이다. API 전용 운영 전제에서는 우선 검증할 성능 후보지만 아직 Recall@5·MRR이 없어 1위로 선정할 수 없다. 팀이 OpenRouter 데이터 정책 변경을 별도 승인하거나 직접 Voyage API 키를 제공한 경우에만 다시 실행한다.
- **증거**: `evals/results/embedding_voyage-4_real_pdf_smoke_import_error_2026-11-02.json`, `evals/results/embedding_voyage-4_real_pdf_smoke_2026-11-02.json`

## 다음 본평가에서의 처리

- **외부 관리형 API 우선 대상**: `text-embedding-3-small`, `voyageai/voyage-4`, `baai/bge-m3`. Qwen3-Embedding-0.6B는 실행 시점의 provider·가격·입력 계약을 확인한 뒤 추가한다.
- **미평가 저비용 API 후보**: `voyageai/voyage-4-lite`. 현재 13종 조사·결과 수에는 포함하지 않으며, 추가할 때는 별도 사전등록과 비용 승인을 거친다.
- **자체 추론 API 후보 겸 로컬 연구 기준점**: KURE-v1, Voyage 4 Nano와 이번에 로컬로 실행한 Qwen·E5. 자체 API로 배포할 수 있지만 로컬 수치를 운영 endpoint 점수로 이전하지 않고 서버 지연·비용을 다시 측정한다.
- **API 정책 해결 필요**: Voyage 4. ZDR/data-policy 설정은 별도 팀 승인이 있을 때만 변경한다.
- **환경을 해결한 뒤 추가할 후보**: GTE, Nomic, Arctic. 환경 변경 자체를 먼저 기록하고 같은 동결 입력을 사용한다.
- **연구 결과로만 분리**: Jina v3. 점수가 높아도 운영 기본 모델로 추천하지 않는다.
- **별도 승인 전 실행하지 않음**: EmbeddingGemma, Jina v4.
- **삭제 규칙**: 2차 판정과 전체 후보 평가 및 최종 모델 확정 전에는 캐시·가중치를 삭제하지 않는다. 확정 뒤에도 정확한 경로와 회수 용량을 제시하고 별도 확인을 받은 다음 탈락 후보만 삭제한다.
