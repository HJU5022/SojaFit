# 평가 리포트

> 제출물입니다. 최종 제출(11/17 24:00)까지 작성합니다. 숫자가 나빠도 괜찮습니다. **재고, 원인을 알고, 무엇을 시도했는지**가 평가 대상입니다. 버린 시도도 적으세요.
>
> 이 문서의 숫자는 `evals/results/`의 원시 결과와 Langfuse 트레이스에서 나온 것만 씁니다.

## 1. 코퍼스와 인덱스 (G3)

| 항목 | 내용 |
|---|---|
| 산업과 문서 종류 | 제조(전자부품). Taiwan Semiconductor 다이오드 데이터시트 PDF(분류 13개, 품번 9,589개) |
| 서로 다른 문서 수 / 서로 다른 청크 수 | 문서 1,360건(7,725쪽) / 청크는 청킹 확정 뒤 기록 (문서 50건 이상 / 청크 1만 개 이상. 청크는 본문 sha256 기준) |
| 문서 파싱 방식 (PDF, 표, 스캔 중) | PDF·표. Docling 2.145.0(OCR 끔)으로 모든 쪽을 파싱하고 합친 칸을 채운 뒤, 표 숫자를 pdfplumber 글자와 두 방향으로 대조. Docling 숫자 중 원문에 있는 비율 99.993%(93,940/93,947), 표 영역 원문 숫자 중 Docling에 있는 비율 99.89%(93,493/93,600). 원시 결과 `evals/results/parse_gpu_*_2026-11-01.*` |
| 청킹 방식과 크기, 겹침 | 3종 비교 중(개선 2가 후보), D2 검색 점수로 확정 |
| 임베딩 모델과 선택 근거 | |
| 벡터DB와 선택 이유, 한계 | |
| manifest 위치 | `data/manifest.jsonl` |

### 1-1. 임베딩 모델 예비 기준선 (2026-10-30)

> **선택용 본평가가 아닌 프록시 smoke test입니다.** 실제 데이터시트 청크가 아직 없어서(22,000청크는 계획 때 추정한 규모) 공식 제품표의 대표 사양을 재서술한 30청크·18질의를 사용했습니다. Recall@5가 포화되므로 MRR과 운영 조건으로 후보만 줄이고, TSC 1,360건 실제 청크에서 사람이 `gold_chunks`를 붙인 뒤 다시 결정합니다. 표본 원문은 [TSC 1N5817–1N5819](https://services.ts.com.tw/storage/resources/datasheet/1N5817%20SERIES_H2104.pdf), [TSC Selection Guide](https://web.ts.com.tw/zh_cn/tsc-taiwan-semiconductor-2025-selection-guide-12th/), [Infineon BAT165](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bat165-datasheet-en.pdf), [Infineon AF Schottky](https://www.infineon.com/assets/row/public/documents/24/76/infineon-pg-sod323-2-1-bas3010a03we6327htsa1-pd-en.pdf)를 대조했습니다.

평가 조건: dense cosine, 리랭커 없음, gold 1개/질의, RTX 5060 Laptop GPU 8GB, warm-up 뒤 측정. 로컬 질의 지연은 질의 임베딩과 22,000개 float32 벡터 exact search를 합친 값입니다. 22,000개 지연용 행렬은 30개 표본 벡터를 반복해 만들었으므로 검색 품질이 아니라 연산 지연만 참고합니다. 실제 서비스의 BM25·메타데이터 필터·리랭커를 넣지 않은 `dense-only` 결과이며 G5 본평가로 세지 않습니다.

| 후보 | Recall@5 | MRR | 1,000청크 임베딩 | 질의 1건 p50 / p95 | 차원 | 22,000벡터 원시 / 계획 용량 | 운영 조건 |
|---|---:|---:|---:|---:|---:|---:|---|
| `text-embedding-3-small` | **1.000** | **0.907** | 7.02초 / $0.000878¹ | 918.7 / 1,205.1 ms | 1,536 | 135.2 MB / 약 203 MB² | OpenRouter API. 모델 이미지 불필요 |
| `BAAI/bge-m3` | **1.000** | 0.863 | 5.95초, 증분 API 비용 $0 | **30.9** / 90.1 ms⁵ | 1,024 | 90.1 MB / 약 135 MB² | 모델 스냅샷 2.1 GB; CUDA 런타임 포함 이미지 약 7.8 GB³; 오프라인 통과 |
| `nlpai-lab/KURE-v1` | **1.000** | **0.894** | 5.68초, 증분 API 비용 $0 | 31.9 / **52.4 ms**⁵ | 1,024 | 90.1 MB / 약 135 MB² | 모델 스냅샷 2.1 GB; CUDA 런타임 포함 이미지 약 7.8 GB³; 오프라인 통과 |
| `Qwen/Qwen3-Embedding-0.6B` | **1.000** | 0.875 | **3.83초**, 증분 API 비용 $0 | 61.8 / 82.9 ms⁵ | 1,024 | 90.1 MB / 약 135 MB² | 고정 영문 query instruction 사용; 캐시 1.125 GiB; 오프라인 통과⁴ |

1. 표본 1,000청크의 실제 usage는 43,890토큰, $0.000878이었습니다. 실제 데이터시트 청크를 평균 350토큰으로 계획하면 1,000청크 $0.007, 22,000청크 최초 색인 $0.154입니다. 전체 프록시 평가는 45,699토큰, $0.000914였습니다. OpenRouter 공식 문서도 `openai/text-embedding-3-small`을 $0.02/1M tokens로 제공합니다: [OpenRouter embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings), [model pricing](https://openrouter.ai/openai/text-embedding-3-small/providers). 기본 차원 1,536과 최대 입력 8,192토큰은 [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)와 일치합니다.
2. 원시는 `차원 × 4 bytes × 22,000`입니다. 계획 용량은 행·메타데이터·HNSW 여유로 원시의 1.5배를 잡은 추정이며 본문 저장량은 제외합니다.
3. 이 PC의 캐시된 단일 revision(2.1 GB) + 측정용 CUDA/Python 패키지(5.6 GB) + base image(0.07 GB)의 비압축 합계 추정입니다. 실제 배포 Dockerfile 빌드 크기는 별도 측정해야 합니다.
4. Qwen은 revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`을 사용했습니다. TEI 1.7.2 linux/amd64 registry manifest의 압축 layer 합계는 GPU 0.57 GiB, CPU 0.22 GiB이며 모델 캐시는 별도입니다. 이미지를 pull·빌드하지 않았으므로 로컬 비압축 이미지 크기로 표기하지 않습니다. 저장소 표준인 Docker `uv run --offline --isolated` 재실행 결과는 Recall@5 1.000/MRR 0.875, 1,000청크 3.83초, 질의 p50/p95 61.8/82.9 ms였습니다. 최초 Windows 임시 환경 결과(10.37초, 43.7/49.0 ms)는 실행 환경이 달라 비교표에서 제외하고 원시 JSON으로만 보존합니다.
5. 로컬 세 모델의 지연은 RTX 5060 Laptop GPU 8GB에서 측정한 값이며 2026-10-30 배포 기준 Cloud Run의 CPU 1 vCPU·메모리 512 MiB 값이 아닙니다. BGE·KURE 모델 스냅샷만 약 2.1 GB이고 Qwen 캐시도 1.125 GiB이므로 로컬 모델을 Cloud Run에 올리려면 512 MiB보다 메모리를 늘리고 CPU 환경에서 지연을 별도로 재측정해야 합니다.

세 로컬 모델은 캐시 준비 후 새 프로세스에서 `HF_HUB_OFFLINE=1`로 같은 Recall@5/MRR이 나오는 것을 확인했습니다. BGE·KURE는 `uv run --offline`도 함께 사용했고, Qwen은 캐시 snapshot의 로컬 경로를 직접 로드해 `transformers`의 불필요한 모델 정보 조회를 막았습니다. Hugging Face 문서상 오프라인 모드는 캐시에 없는 파일을 자동으로 받지 않고 실패합니다: [HF_HUB_OFFLINE](https://github.com/huggingface/huggingface_hub/blob/main/docs/source/en/package_reference/environment_variables.md#hf_hub_offline).

**키 없는 데모 규칙**: API 모델을 선택해도 데모 요청에서 임의의 다른 임베딩 모델로 바꾸지 않습니다. 승인한 데모 질의는 입력 해시로 `data/demo/`의 top-k 청크 ID와 응답을 재생합니다. 기록에 없는 질의는 API·벡터 검색을 호출하지 않고 BM25-only로 근거를 찾은 뒤 근거 문장을 추출해 반환합니다. 화면과 응답에는 `demo_mode=true`, `live_vector_search=false`, 검색 모드, 모델·코퍼스 버전을 표시합니다. 실제 API 응답 원본은 저장하지 않습니다.

**예비 선택**: 프로젝트 기본 후보는 `text-embedding-3-small`로 둡니다. 네 모델 모두 Recall@5가 포화됐고 MRR 차이도 표본 18질의에서 나온 값이므로 품질 우위로 단정하지 않습니다. 대신 22,000청크(계획 때 추정 규모) 최초 색인 계획비용이 $0.154로 작고 CUDA 모델 이미지를 배포하지 않아도 되는 점을 선택 근거로 삼습니다. 약 0.9초의 질의 지연과 키·외부 서비스 의존은 손해입니다. `KURE-v1`은 로컬 1순위, Qwen은 KURE보다 MRR이 0.019 낮지만 캐시가 작고 질의 p95가 양호한 4번째 후보로 유지합니다. `bge-m3`는 같은 로컬 운영비에서 KURE보다 MRR이 낮아 본평가 우선순위가 가장 낮습니다. 이 선택은 TSC 1,360건 실제 청크 본평가 전까지 잠정이며 `chunk_embeddings.embedding`의 `vector(N)`과 Migration 2는 그 뒤에 확정합니다.

**다음 본평가**: TSC 데이터시트 1,360건의 실제 청크에서 예비 기본 선택인 `BM25 + text-embedding-3-small`을 기준선으로 두고 임베딩 후보 구성만 KURE와 Qwen으로 각각 바꿉니다. 청킹, BM25 가중치, 제조사·문서 종류 필터, top-k, 리랭커는 고정합니다. Qwen의 영문 query instruction도 프록시에서 사용한 문구로 고정하며 결과를 본 뒤 튜닝하지 않습니다. 단일 gold MRR 외에 한 판정에 필요한 모든 근거가 Top 5에 함께 들어오는 다중 근거 Recall@5를 측정합니다. 기대 범위와 회귀 위험은 `evals/PREREGISTER.md` #1·#2에 등록했습니다.

**원문 대조 3건 이상**: 파싱 결과를 원문과 나란히 놓고 틀어진 곳을 적습니다.

대조 방법: 원문 쪽을 화면으로 띄워 정답 값 41개를 만들고(텍스트 레이어로 숫자 재확인, 하정운이 약 절반을 원문과 다시 대조해 틀린 값 없음), 값과 그 값을 해석하는 데 필요한 기호·품번·조건이 파싱 결과의 같은 행(줄)에 있으면 맞은 것으로 셉니다. 원시 결과는 `evals/results/parser_accuracy_2026-11-01.json`, 정답표는 `evals/results/parser_truth_2026-11-01.json`입니다(2026-11-01, 도커 linux/aarch64 CPU).

| # | 문서 | 원문에서 본 것 | 파싱 결과 | 틀어진 곳 |
|---|---|---|---|---|
| 1 | TSC 1N5817 SERIES_H2104, 1~2쪽 | 최대 정격 표의 VRRM 1N5817/18/19 = 20/30/40 V, IF 1 A·IFSM 30 A는 세 품번 공통(합친 칸). 전기 특성 표의 VF 최대 0.45/0.55/0.60 V @ IF = 1A, TJ = 25°C(조건·기호 칸이 세 행에 걸침) | Docling 14/14, pdfplumber 11/14, pdftotext 10/14 | 합친 칸의 기호(VF, IR)가 한 행에만 남아 나머지 행의 값과 떨어짐. pdfplumber 기본값은 아래첨자를 떼어 `I = 1A, T = 25°C F J`로 냄(`text_y_tolerance=6`에서 해결) |
| 2 | TSC 1N4148 SERIES_K2301, 1~2쪽 | PD 500 mW·VRRM 100 V·IF 150 mA·IFSM 2 A·IFRM 450 mA는 세 품번 공통. VF는 품번·조건별(1N4148은 IF = 10mA에서 최대 1 V), IR은 VR = 20V 25 nA, 75V 5 µA | Docling 13/13, pdfplumber 11/13, pdftotext 9/13 | Docling도 세 품번 공통 값을 가운데 열(1N4448)에만 넣고 나머지 열을 비움. 어느 도구든 합친 칸 채우기가 필요함. µA 단위는 다섯 도구 모두 유지 |
| 3 | TSC BZT52C2V4 SERIES_G1804, 1~2쪽 | 품번이 행인 43행 표. BZT52C3V6 행은 VZ 3.42/3.60/3.78 V @ IZT 5 mA, ZZT 90 Ω, IR 4.5 µA @ VR 1.0 V | Docling·pdfplumber·pdftotext 14/14 | pypdf는 칸마다 줄을 나눠 품번과 값이 떨어짐(0/14). PyMuPDF는 6/14 |

**파서 5종 비교** (위 3건 18쪽 + 13개 분류 비례 표본 100건 573쪽)

| 도구 | 해석 가능 값 (41개) | 공통 값을 모든 품번 열에 채움 (12개) | 쪽당 시간 (표본 100건) |
|---|---:|---:|---:|
| Docling 2.145.0 (OCR 끔) | **41** | 7 | 4.58초 (첫 실행 모델 로딩 41.9초 별도) |
| pdfplumber 0.11.10 | 36 | 4 | 0.067초 |
| pdftotext 22.12.0 | 33 | 표 구조 없음 | 0.003초 |
| PyMuPDF 2.0 | 23 | 4 | 0.337초 |
| pypdf 6.21.4 | 22 | 표 구조 없음 | 0.022초 |

µ·°C·아래첨자 검사는 다섯 도구 모두 통과했습니다. 다섯 도구 모두 PDF에 들어 있는 글자를 꺼내므로(OCR 아님) 숫자 자체는 같았고, 차이는 표의 행·열 구조에서 났습니다.

**청킹 후보 대리 지표** (위 3건의 Docling 파싱 결과, 검색 점수는 D2에서 잼, 원시 결과 `evals/results/chunking_proxy_2026-11-01.json`)

| 단계 | 방법 | 조각 수 | 평균 길이 | 값과 해석 글자가 같은 조각 (41개) | 그 조각에 문서 품번까지 (41개) |
|---|---|---:|---:|---:|---:|
| 개선 전 | 고정 길이 1000자, 겹침 100자 | 33 | 724자 | 41 | 31 |
| 개선 1 | Docling HybridChunker 기본값 | 100 | 538자 | 8 | 2 |
| 개선 2 | 표 한 행 = 조각 하나 + [파일·쪽·표 제목] 이름표 + PDF별 품번 표지 | 162 | 354자 | 41 | 41 |

개선 1은 표 칸마다 표 제목을 되풀이해 기본 토크나이저 512토큰 한도에서 표가 갈리고 기호와 값이 다른 조각으로 떨어졌습니다. "같은 조각" 판정은 조각이 클수록 유리하므로 개선 전의 41은 검색 점수로 다시 확인합니다.

## 2. 평가셋 (G5)

| 항목 | v1 | v2 |
|---|---|---|
| 동결일 | 11/3 | 11/6 |
| 건수 (관련 / 비관련) | | |
| 비관련 4종 건수 (도메인 밖 / 없는 대상 / 없는 항목 / 기간 다름) | | |
| sha256 | | |
| 코퍼스 버전과 정답 기준일 | | |
| 정답을 정한 사람과 기준 | | |
| 질문을 쓴 사람과 정답 청크를 찾은 사람이 다른가 | | |
| 동결 뒤 지표에서 뺀 문항 수와 사유 (`evals/exclusions.json`) | | |

**측정 축** (아래 5개를 나눠 보고하고 하나의 정확도로 합치지 않습니다. 필요하면 Recall@k, MRR을 더합니다)

| 지표 | 뜻 | 관련/비관련 |
|---|---|---|
| 정답 근거 인용률 | 답하고, 인용한 근거가 정답 근거와 일치 | 관련 |
| 오답 근거 | 답했지만 인용한 근거가 틀림 | 관련 |
| 과잉 거절 | 답이 있는데 거절 | 관련 |
| 올바른 거절 | 답이 없어서 거절 | 비관련 |
| 환각 위험 | 답이 없는데 답함 | 비관련 |

**판정 방식과 한계**: (정확 일치 / 규칙 기반 / LLM-as-judge. judge 모델은 생성 모델과 달라야 합니다. 이 방식이 무엇을 못 보는지, 측정이 제대로 되는지 확인한 과정을 적습니다. 결과가 직관과 크게 어긋날 때는 결론보다 측정 도구를 먼저 의심하세요.)

## 3. 검색 개선 전후 (사전 등록, 한 번에 하나만)

> **한 번 재고 끝내면 G5는 미충족입니다.** 바꾸기 전에 `evals/PREREGISTER.md`에 기대를 적고, 같은 평가셋으로 다시 재서 **어느 문항이 회귀했는지** 보여야 합니다.
>
> 전후 차이가 1~4문항이면 "개선"이라 쓰지 마세요. 달라진 문항 목록과 부호 검정(또는 문항 수가 적어 구별할 수 없다는 한계)을 같이 적습니다. 개선이 없거나 악화여도 사전 등록과 원인 분석이 있으면 불이익이 없습니다.

| # | 바꾼 것 (하나) | 사전 등록한 기대 | 지표 (전 → 후) | 달라진 문항 수 (좋아짐 / 나빠짐) | 회귀한 문항 | 판단 |
|---|---|---|---|---|---|---|
| 0 | 베이스라인 (v1, 11/3) | | | | | |
| 1 | | | | | | KEEP / DISCARD |
| 2 | | | | | | KEEP / DISCARD |

### 3-1. 회귀한 문항 분석

(어떤 입력에서 무엇이 어떻게 무너졌고 왜 그랬는지)

## 4. 에이전트: 단일 대 멀티, 승인과 재개 (G4)

단일 에이전트 기준 점수(D4)를 v2로 다시 재고, Supervisor와 서브에이전트로 나눈 뒤(D5) 같은 v2로 비교합니다. **개선이 없었다면 없었다고 적으세요.**

| 구성 | 지표 | 비용 | 지연 | 비고 |
|---|---|---|---|---|
| 단일 에이전트 | | | | |
| Supervisor + 서브에이전트 | | | | |

| 항목 | 내용 |
|---|---|
| 역할 분리와 컨텍스트 격리 | |
| 사람 승인(interrupt) 지점과 이유 | |
| 체크포인트 재개를 확인한 방법 | |
| 로그인 사용자 2명의 대화와 기억이 섞이지 않음을 확인한 방법 | |

## 5. 검색 실패 유형 분석

| 유형 | 예시 질문 | 원인 | 조치 | 남은 한계 |
|---|---|---|---|---|
| | | | | |

## 6. 신뢰 경계

코퍼스에 심은 간접 인젝션과 출처 유출 시험 **3건 이상**, 막지 못한 것은 코드로 보강합니다.

| # | 시험 (코퍼스에 심은 문장) | 기대 | 실제 | 조치 |
|---|---|---|---|---|
| 1 | | | | |

## 7. 관측 (G6)

| 항목 | 상태 |
|---|---|
| 트레이스에 입출력, 모델, 토큰, 지연, 비용이 남는가 | |
| 평가 점수가 트레이스에 연결되어 있는가 | |
| `user_id`, `session_id`를 붙였는가 | |
| 느림의 원인을 트레이스로 가려낸 사례 | |

<!-- 대시보드 스크린샷 3장 이상. 트레이스 상세 1장 포함 -->

## 8. 비용과 응답 시간 (현재 코드로 단계별 실측)

| 단계 | p50 | p95 | 요청당 비용 |
|---|---|---|---|
| 검색 | | | |
| 리랭킹 | | | |
| 생성 | | | |
| 전체 | | | |

**왜 이 모델과 이 구성인가** (한 문장): ("제일 좋아서"가 아니라 "이 정도 품질 손실을 이 정도 비용 절감과 바꿀 만하다고 봤다")

## 9. 재현 명령

평가자가 샘플 몇 문항을 다시 돌려 숫자가 맞는지 봅니다.

```bash
# 최초 1회 캐시 준비(네트워크 사용): MODEL은 bge-m3, kure-v1, qwen3-embedding-0.6b 중 하나입니다.
docker run --rm --gpus all -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --isolated --with sentence-transformers --with torch python evals/benchmark_embeddings.py --model MODEL

# 캐시 준비 뒤 오프라인 재현
docker run --rm --gpus all -e HF_HUB_OFFLINE=1 -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --offline --isolated --with sentence-transformers --with torch python evals/benchmark_embeddings.py --model MODEL

# API 프록시 재실행: .env의 OPENROUTER_API_KEY를 사용하며 소액 과금됩니다.
docker run --rm --env-file .env -v "${PWD}:/workspace" -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --isolated --with openai --with numpy python evals/benchmark_embeddings.py --model text-embedding-3-small
```

## 10. 대체재와의 비교

같은 질문 5개를 범용 챗봇과 우리 서비스에 나란히 넣습니다.

| # | 질문 | 범용 챗봇 | 우리 서비스 | 차이 |
|---|---|---|---|---|
| 1 | | | | |

## 11. 지금 이 서비스의 가장 큰 약점

("없습니다"는 자기 서비스를 모른다는 뜻입니다. 발표에서 반드시 묻습니다.)
