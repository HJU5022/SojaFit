# 임베딩 후보 13종 조사

- 상태: 이력
- 기준일: 2026-11-02
- 기준 커밋: 없음(로컬 탐색 실험. 2026-10-30 프록시 원시 파일만 레포에 있음)
- 정본 여부: 비정본. 후보 선정 근거의 정본은 [embedding-grid-eval-2026-11-02.md](embedding-grid-eval-2026-11-02.md), [EVAL_REPORT.md](../../EVAL_REPORT.md) 1-4절, [ADR 0004](../adr/0004-임베딩-1536차원은-임시-결정.md). 서비스 임베딩은 `voyage-4-large` 1024차원이다(`backend/rag/retrieve.py:29`)
- 관련 문서: [model-licenses.md](model-licenses.md)(고정 revision, 라이선스), [embedding-candidate-runner.md](../experiments/embedding-candidate-runner.md)

## 1. 질문과 결론

질문: 후보 13종을 목록에 넣은 이유는 무엇이고, 각각 어디까지 실행했고, 왜 멈췄는가.

13종을 같은 수준으로 평가하지 않았다. 증거 수준은 아래와 같다.

| 증거 수준 | 후보 수 | 후보 | 뜻 |
|---|---:|---|---|
| 합성 프록시 수치 있음 | 4 | text-embedding-3-small, BGE-M3, KURE-v1, Qwen3-Embedding-0.6B | 합성 30청크, 18질의. 원시 JSON이 레포에 있다(3절) |
| 실제 PDF smoke 수치 있음, 원시 없음 | 5 | BGE-M3, KURE-v1, Qwen3, E5, Voyage 4 Nano | 실제 PDF 3건, 156청크, 질의 9건. 수치는 이 문서 5절 한계에만 둔다 |
| 호환성 확인에서 차단 | 4 | GTE, Jina v3, Nomic, Arctic | 환경 또는 의존성 문제로 품질 수치 없음 |
| API 정책에서 차단 | 1 | Voyage 4(OpenRouter 경유) | 계정 ZDR/data-policy와 endpoint 불일치로 404 |
| 조사 전용 | 2 | EmbeddingGemma, Jina v4 | 약관·라이선스·자원 조건으로 실행 제외 |

모든 수치는 2차 판정과 평가셋 동결 전 탐색 결과다. 프록시 JSON의 `eligible_for_final_model_decision`은 `false`다. 모델 선정은 동결 평가셋 격자 본평가(`grid_2026-11-02.json`)가 한다.

## 2. 방법

| 단계 | 내용 |
|---|---|
| 1 | 공식 모델 저장소의 고정 revision에서 모델 카드, 라이선스·약관, 차원, 입력 형식, 원격 코드 여부를 확인한다. revision과 라이선스는 [model-licenses.md](model-licenses.md)가 정본이다 |
| 2 | 실행 후보는 모델 revision과 외부 코드 revision을 40자리 커밋 SHA로 고정한다 |
| 3 | 모델별 query/document 형식을 먼저 고정하고 공통 dense cosine k=5 평가기에 등록한다 |
| 4 | 다운로드·API 비용과 중단 조건을 기록한 뒤 프록시를 실행한다. 오류가 난 후보는 자동 재시도하지 않고 오류 단계와 원인을 JSON으로 보존한다 |
| 5 | 성공 후보는 실제 TSC PDF 3건을 Docling과 card chunker로 만든 156청크와 한국어 질의 9건으로 오프라인 재측정한다(`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `--network none`) |

같은 계열 이름을 같은 모델로 보지 않는다. 로컬 `multilingual-e5-large-instruct` 결과는 OpenRouter `intfloat/multilingual-e5-large`에, 로컬 `voyage-4-nano` 결과는 API `voyage-4`에 옮길 수 없다. API 결과에는 모델 ID, provider 정책, 실행일, 차원, 입력 형식, 비용, 지연을 함께 기록한다.

## 3. 합성 프록시 결과(레포에 원시 있음)

합성 30청크, 18질의, dense only. 원시: `evals/results/embedding/embedding_<모델>_proxy[_offline]_2026-10-30.json`.

| 후보 | 차원 | Recall@5 | MRR | 1,000청크 임베딩 시간 | 원시 |
|---|---:|---:|---:|---:|---|
| text-embedding-3-small | 1536 | 1.000 | 0.907 | 7.02초 | `embedding_text_embedding_3_small_proxy_2026-10-30.json` (총 45,699토큰, 비용 $0.00091398) |
| BAAI/bge-m3 | 1024 | 1.000 | 0.863 | 5.95초 | `embedding_bge_m3_proxy_offline_2026-10-30.json` |
| nlpai-lab/KURE-v1 | 1024 | 1.000 | 0.894 | 5.68초 | `embedding_kure_v1_proxy_offline_2026-10-30.json` |
| Qwen/Qwen3-Embedding-0.6B | 1024 | 1.000 | 0.875 | 3.83초 | `embedding_qwen3_0_6b_proxy_offline_2026-10-30.json` |

로컬 3종은 NVIDIA GeForce RTX 5060 Laptop GPU에서 실행했다. 합성 표본 수치이므로 실제 PDF 결과와 직접 비교하지 않는다.

## 4. 후보별 조사

| # | 후보 | 넣은 이유 | 실행 범위와 중단·제외 이유 | 이후 |
|---|---|---|---|---|
| 1 | `text-embedding-3-small` | API 기준선. 로컬 GPU 없이 사용 | 중앙 API 경계 `backend/services/llm.py::embed_texts`로 합성 프록시만 실행. 실제 PDF smoke는 신규 API 과금이 없는 범위로 승인되어 로컬 후보만 실행. 키 없는 데모의 BM25-only 결과는 API 임베딩 품질이 아니어서 대체 점수로 쓰지 않음 | 격자 본평가 기준 칸 |
| 2 | `BAAI/bge-m3` | 다국어·긴 문맥 로컬 기준선, MIT | 별도 query instruction 없이 1,024차원. 프록시와 실제 PDF smoke 실행. 3문서, 9질의 smoke는 로딩·검색 계약 확인 수준 | 격자에 포함하지 않음 |
| 3 | `nlpai-lab/KURE-v1` | 한국어 질의 특화 로컬 후보, MIT | 1,024차원, 일반 query/document 입력. 실제 PDF smoke에서 MRR이 성공 5종 중 가장 높았다(값은 5절 표). 품번이 질의에 직접 들어 있어 한국어 특화 효과로 단정할 수 없고, 성공 후보 전부가 패키지와 전력 다중 근거 질문을 top-5에서 놓침 | 격자 본평가 포함 |
| 4 | `Qwen/Qwen3-Embedding-0.6B` | 0.6B급 다국어 instruct 후보, Apache-2.0 | 영문 query instruction을 결과 확인 전에 고정. 문서는 원문, 질의는 instruction + 한국어 질문. instruction 문구는 smoke에서 조정하지 않음 | 격자 본평가 포함 |
| 5 | `Alibaba-NLP/gte-multilingual-base` | 305M, 768차원 경량 다국어, Apache-2.0 | 외부 코드 `Alibaba-NLP/new-impl` revision 고정. attention을 `eager`로 바꾼 1회 재검증에도 CUDA device-side assert 발생. 재시도 0회로 중단 | 호환성 차단. 고정 CPU 환경 또는 검증된 CUDA·PyTorch 조합이 필요 |
| 6 | `intfloat/multilingual-e5-large-instruct` | 다국어 instruct 대조군, MIT | 고정 영문 검색 instruction, 1,024차원. 입력 512토큰 제한. 실제 PDF smoke 실행 | 속도 대조군 |
| 7 | `jinaai/jina-embeddings-v3` | retrieval task 어댑터, CC BY-NC 4.0이라 연구용 대조군 | `sentence-transformers==3.1.0`이 오프라인 uv 캐시에 없어 환경 해석 단계에서 중단. 모델 실행 미시작 | 품질 미측정 연구 후보. 운영 추천에서 제외 |
| 8 | `nomic-ai/nomic-embed-text-v2-moe` | 다국어 MoE, Apache-2.0 | README가 `megablocks`를 커밋 미고정 Git URL로 설치하도록 요구. 재현성·공급망 조건 위반으로 설치 전 중단(`UnpinnedDependencyError`) | 호환되는 `megablocks` 커밋을 특정한 뒤에만 재실행 |
| 9 | `Snowflake/snowflake-arctic-embed-m-v2.0` | 경량 검색 특화 다국어, Apache-2.0 | 모델 설정이 가리키는 `sentence-transformers==2.7.0`이 오프라인 uv 캐시에 없어 중단 | 호환성 차단. 고정 구버전 의존성을 격리 환경에서 검토한 뒤 재실행 |
| 10 | `google/embeddinggemma-300m` | 300M 경량 | 가중치 접근에 Gemma 약관 동의가 필요하고 재배포 조건 검토가 끝나지 않아 실행 제외. 원시 결과 없음 | 약관 동의 주체, 상업 사용·재배포 조건 확인 전에는 실행하지 않음 |
| 11 | `jinaai/jina-embeddings-v4` | 최신 다국어·멀티모달 연구 비교 | Qwen Research License라 상업 후보 아님. 약 7.89GB. 실행 제외. 원시 결과 없음 | 상업 후보 비교에서 제외 |
| 12 | `voyageai/voyage-4-nano` | Voyage 4 계열 Apache-2.0 오픈 가중치, 32K 문맥, 256~2,048 가변 차원 | 모델·원격 코드 revision 고정. 원격 코드 3,491자에서 프로세스·네트워크·동적 실행·파일 쓰기 패턴을 정적 검색. `sdpa`, 1,024차원, `encode_query`/`encode_document`. 실제 PDF smoke 실행 | 로컬 연구 기준점. 공식 Voyage API와 공유 embedding 공간이라는 주장은 교차 검증하지 않음 |
| 13 | `voyageai/voyage-4` | OpenRouter의 다국어 균형형 API, Nano와 1,024차원 | `embed_texts` allowlist에 추가, `input_type` document/query, `dimensions=1024`, 자동 재시도 0. 첫 명령은 `PYTHONPATH` 누락으로 API 호출 전 실패(오류 JSON 보존). OpenRouter가 ZDR/data-policy guardrail 때문에 유일 endpoint를 제외해 404. 정책·계정 설정은 바꾸지 않음 | OpenRouter 경유는 품질 수치 없음. Voyage API 직접 호출로는 격자 본평가에 포함됨 |

격자 본평가에 들어간 6종은 text-embedding-3-small, KURE-v1, Qwen3-Embedding-0.6B, voyage-4-lite, voyage-4, voyage-4-large다. `voyage-4-lite`는 이 13종 조사표에 없고 본평가에서 추가된 후보다.

## 5. 한계

- 아래 표의 실제 PDF smoke 수치는 레포에 원시 JSON이 없다(`evals/results/embedding_<모델>_real_pdf_smoke_2026-11-02.json` 식별자는 로컬 산출물 이름이며 현재 레포의 파일이 아니다). 확인할 수 없는 값이다.
- 2026-11-02 확장 평가기, 입력 표본, 테스트는 이 레포에 없다. 이 조사 결과만으로는 재현·감사할 수 없다.
- Qwen3의 실제 PDF smoke 값은 별도 로컬 기록이 있으나 대응 원시가 없고, 1,000청크 시간 10.37초는 Windows 30청크 원시값 10.372056초와 같아 실제 PDF 재측정값인지 확인할 수 없다. 원시가 없는 3.63초 재측정 기록도 근거에서 제외한다.
- CPU, Cloud Run 지연은 측정하지 않았다. 3문서, 9질의 smoke는 표본이 작다.

원시가 없는 실제 PDF smoke 수치(미확인):

| 후보 | Recall@5 | MRR | 1,000청크 시간 | 비고 |
|---|---:|---:|---:|---|
| BAAI/bge-m3 | 0.889 | 0.753 | 17.60초 | |
| nlpai-lab/KURE-v1 | 0.889 | 0.808 | 18.05초 | 성공 5종 중 MRR 최고 |
| intfloat/multilingual-e5-large-instruct | 0.778 | 0.575 | 5.23초 | 1N5817 VF 조건 gold가 10위 |
| voyageai/voyage-4-nano | 0.889 | 0.744 | 5.29초 | 질의 p50/p95 53.9/80.5 ms. BZT52C2V4 패키지·전력 다중 근거 질문의 첫 gold 9위 |
