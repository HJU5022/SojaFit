# 임베딩 후보 확장 평가기 설계

> **상태: 설계 계약만 포함.** 이 문서는 확장 평가기의 목표·입력 계약·수용 기준을 정의한다. 해당 구현·단위 테스트·2026-11-02 원시 결과는 현재 `main`에 없으므로 아래 성공 기준은 구현 완료를 뜻하지 않는다.

## Why

- **페르소나**: 수집된 TSC 다이오드 코퍼스 표본에서 임베딩 모델을 비교하고 최종 후보를 확정해야 하는 임베딩 담당자
- **상황**: 확장 전 평가기는 `text-embedding-3-small`, `bge-m3`, `KURE-v1`, `Qwen3-Embedding-0.6B` 4종만 지원했다. 조장은 아직 실행하지 않은 모델과 연구용 후보도 비교 기록에 남기도록 요청했다.
- **문제**:
  1. 모델마다 질의와 문서의 입력 형식이 달라 이름만 추가하면 공정한 비교가 되지 않는다.
  2. 일부 모델은 원격 코드, 별도 약관, 비상업 제한이 있어 검색 품질과 운영 가능성을 분리해야 한다.
  3. 평가셋 2차 판정과 동결 전 결과는 최종 모델 결정에 사용할 수 없다.
- **측정 지표**: 후보 등록 누락 0건, 모델별 입력 형식 테스트 통과, 가변 revision 사용 0건, 라이선스·운영 분류 누락 0건

## Goal

- **해결 목표**: 공통 측정 로직은 유지하고 모델별 로딩·질의·문서 형식만 어댑터로 분리해 기본 실행 후보 9종과 Voyage 확장 후보 2종을 같은 결과 형식으로 준비한다. Voyage 추가 계약은 [embedding-voyage-candidates.md](embedding-voyage-candidates.md)를 따른다.
- **성공 기준**:
  - 구현 시 실행 후보 11종과 조사 전용 후보 2종을 문서와 코드에서 같은 이름으로 관리한다.
  - Hugging Face 실행 후보는 공식 저장소의 불변 커밋 SHA를 사용하며 `main`·태그 같은 가변 revision을 허용하지 않는다.
  - API 호출과 모델 다운로드 없이 후보 등록, 입력 형식, 라이선스 분류, 결과 메타데이터를 단위 테스트한다.
  - 기존 4종 프록시의 입력 형식과 결과 JSON 키를 깨뜨리지 않는다.
  - 실제 모델 실행 전 모델별 다운로드량·API 비용·중단 조건을 작업 기록에 남긴다.
- **Out of Scope**: 평가셋 2차 판정, `dataset_v1.jsonl` 동결, 실제 코퍼스 표본 생성, 공식 Recall@5·MRR 측정, 최종 모델 결정, `vector(N)` 또는 Migration 변경. 기본 후보 등록 단계의 모델 다운로드·유료 API 호출은 포함하지 않으며, Voyage 2종의 승인된 smoke 실행과 차단 처리는 확장 계약을 따른다.

## What

### Happy Path

1. 평가기가 후보 key로 모델 명세를 찾는다.
2. 명세의 고정 revision, 라이선스, 운영 분류, 원격 코드 허용 여부를 결과 메타데이터에 기록한다.
3. 문서는 모델이 요구하는 passage/document 형식으로, 질의는 query instruction·prefix·task 형식으로 각각 인코딩한다.
4. 공통 코사인 검색과 Recall@5·MRR·지연 측정 로직을 그대로 사용한다.
5. 캐시 준비 후 `HF_HUB_OFFLINE=1`에서 같은 모델 revision을 다시 불러올 수 있다.
6. 연구용 후보는 품질 결과를 남기되 운영 추천 대상과 분리한다.

### 후보 범위

| 구분 | 모델 | 라이선스·약관 분류 | 실행 분류 |
|---|---|---|---|
| API 기준선 | `text-embedding-3-small` | OpenAI/OpenRouter 서비스 약관 | 운영 후보 |
| API 확장 후보 | `voyageai/voyage-4` | OpenRouter 서비스 약관 | 평가용 실행 후보 |
| 로컬 확장 후보 | `voyageai/voyage-4-nano` | Apache-2.0 | 상업 후보·로컬 실행 |
| 다국어 기준선 | `BAAI/bge-m3` | MIT | 운영 후보 |
| 한국어 특화 | `nlpai-lab/KURE-v1` | MIT | 운영 후보 |
| instruct/decoder | `Qwen/Qwen3-Embedding-0.6B` | Apache-2.0 | 운영 후보 |
| 경량 다국어 | `Alibaba-NLP/gte-multilingual-base` | Apache-2.0 | 운영 후보 |
| instruct 대조군 | `intfloat/multilingual-e5-large-instruct` | MIT | 운영 후보 |
| 비상업 대조군 | `jinaai/jina-embeddings-v3` | CC BY-NC 4.0 | 연구용 후보 |
| MoE 다국어 | `nomic-ai/nomic-embed-text-v2-moe` | Apache-2.0 | 운영 후보 |
| 경량 검색 특화 | `Snowflake/snowflake-arctic-embed-m-v2.0` | Apache-2.0 | 운영 후보 |
| 조사 전용 | `google/embeddinggemma-300m` | Gemma 약관, 접근 전 동의 필요 | 실행 제외 |
| 조사 전용 | `jinaai/jina-embeddings-v4` | Qwen Research License, 약 7.89GB | 실행 제외 |

라이선스 표는 모델 카드의 표기만 복사하지 않고 고정한 revision의 `LICENSE`·`NOTICE`를 다시 확인한다. API 모델은 오픈소스 라이선스 대신 실제 호출 제공자와 적용 약관을 기록한다.

### Edge Cases

| ID | 상황 | 처리 |
|---|---|---|
| EC-01 | API 키가 없음 | 호출하지 않고 `not_run_no_key`로 기록한다. 로컬 모델로 자동 대체하지 않는다. |
| EC-02 | 오프라인 캐시에 revision이 없음 | 네트워크로 자동 전환하지 않고 명시적으로 실패한다. |
| EC-03 | `trust_remote_code=True`가 필요함 | 불변 revision이 없으면 로드를 거부한다. 원격 코드는 검토 대상임을 결과에 기록한다. |
| EC-04 | 모델별 입력 형식이 없음 | 일반 인코딩으로 추측하지 않고 등록 오류로 실패한다. |
| EC-05 | GPU OOM·timeout·모델 오류 | 같은 실행에서 반복하지 않고 실패 상태와 단계만 기록한다. |
| EC-06 | 출력 차원이 선언값과 다름 | 결과를 유효 점수로 기록하지 않고 오류 처리한다. |
| EC-07 | 연구용 모델의 점수가 가장 높음 | 결과는 보존하되 운영 기본 후보로 추천하지 않는다. |
| EC-08 | 조사 전용 모델을 CLI로 요청함 | 실행 후보 목록에 없으므로 인자 검증에서 거부한다. |
| EC-09 | 평가셋이 동결되지 않음 | 프록시 실행만 허용하고 `eligible_for_final_model_decision=false`를 기록한다. |
| EC-10 | 후보별로 서로 다른 코퍼스·검색 조건을 사용함 | 비교 결과를 무효로 보고 공식 비교표에 넣지 않는다. |

## How

### 구성

- `evals/benchmark_embeddings.py`
  - 공통 표본 로딩, 검색, Recall@5·MRR·지연 계산은 유지한다.
  - 후보 명세에는 key, 모델 ID, 불변 revision, 라이선스 ID, 운영 분류, 기대 차원, `trust_remote_code`, 인코딩 방식을 둔다.
  - 모델별 차이는 문서와 질의를 인코딩하는 한 경계에서만 처리한다.
- `tests/test_benchmark_embeddings.py`
  - 실제 모델·API를 호출하지 않고 registry와 입력 변환의 계약을 검사한다.
- `docs/model-licenses.md`
  - 실행 후보와 조사 전용 후보의 출처, revision, 라이선스, 재배포 여부, GitHub 포함 여부를 기록한다.
- [docs/embedding-candidate-investigation.md](../embedding-candidate-investigation.md)
  - 후보 13종의 선정 이유, 실제 조사·실행 과정, 중단 사유, 증거 수준과 다음 평가 조건을 기록한다.

### 인코딩 방식

| 모델 계열 | 문서 | 질의 |
|---|---|---|
| BGE·KURE·GTE | 원문 | 원문 |
| Qwen3 | 원문 | 현재 프록시에서 고정한 영문 instruction + 질의 |
| multilingual-E5 | 원문 | 한 문장짜리 고정 검색 instruction + 질의 |
| Jina v3 | `retrieval.passage` task | `retrieval.query` task |
| Nomic v2 | 공식 모델 카드의 document prefix | 공식 모델 카드의 query prefix |
| Arctic v2 | 원문 | 공식 `query` prompt |

입력 형식은 결과를 본 뒤 수정하지 않는다. 문구를 바꾸는 실험은 `evals/PREREGISTER.md`에 별도로 등록한다.

### 데이터 흐름

```text
고정 표본 JSONL
  → 후보 명세 검증
  → 문서 인코딩
  → 질의 인코딩
  → 공통 cosine top-k
  → Recall@5·MRR·지연
  → 모델·revision·라이선스·실행환경이 포함된 JSON
```

### 실행 경계

- 준비 단계 테스트는 네트워크, API, 모델 캐시를 사용하지 않는다.
- 프록시 모델 실행은 모델별 용량·비용·명령·중단 조건을 먼저 작업 기록에 남기고 조원 확인 후 수행한다.
- 최종 평가는 v1 동결(11-02) 뒤 실제 코퍼스 표본 해시를 고정하고 별도 사전 등록으로 수행한다.
- LLM/API 임베딩 호출은 계속 `backend/services/llm.py::embed_texts`만 사용한다.

## AC

### AC-01 · 후보 등록 완전성

- GIVEN: 평가기 후보 registry를 읽음
- WHEN: 실행 후보와 조사 전용 후보를 검사함
- THEN: 실행 11종과 조사 전용 2종의 key·모델 ID·라이선스·운영 분류가 빠짐없이 존재함

### AC-02 · 불변 revision

- GIVEN: Hugging Face 실행 후보 명세
- WHEN: revision을 검사함
- THEN: 40자리 커밋 SHA이고 `main`·빈 값은 거부됨

### AC-03 · 모델별 입력 형식

- GIVEN: 같은 한국어 전자공학 질의와 영문 데이터시트 문장
- WHEN: 각 후보 어댑터로 질의와 문서를 준비함
- THEN: Qwen·E5·Jina·Nomic·Arctic에는 사전 고정한 서로 다른 형식이 적용되고 BGE·KURE·GTE 문서는 바뀌지 않음

### AC-04 · 연구용 분리

- GIVEN: Jina v3 결과가 가장 높음
- WHEN: 후보 메타데이터를 읽음
- THEN: 결과는 보존되지만 `research_only=true`, `commercial_candidate=false`로 기록됨

### AC-05 · 조사 전용 실행 차단

- GIVEN: EmbeddingGemma 또는 Jina v4 key
- WHEN: 평가 CLI 후보를 검사함
- THEN: 실행 후보에 포함되지 않고 조사 문서에서만 확인됨

### AC-06 · 다운로드 없는 테스트

- GIVEN: API 키·Hugging Face 캐시·네트워크가 없는 테스트 환경
- WHEN: 후보 registry와 입력 형식 테스트를 실행함
- THEN: 외부 호출 없이 통과함

### AC-07 · 동결 전 결과 표시

- GIVEN: 현재 비동결 프록시 표본
- WHEN: 후보 smoke test 결과를 기록함
- THEN: `evaluation_level=proxy_smoke_test`, `eligible_for_final_model_decision=false`가 포함됨
