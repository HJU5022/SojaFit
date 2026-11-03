# Voyage 임베딩 후보 추가 계약

> **상태: 설계 계약만 포함.** Voyage allowlist와 입력 어댑터 구현, 테스트, 실제 PDF 표본과 원시 JSON은 현재 `main`에 없다. 로컬 실행·차단 이력은 [embedding-candidate-investigation.md](../research/embedding-candidate-investigation.md)에 있으며 최종 선정 근거가 아니다.

## Why

- **페르소나**: 한국어 전자공학 질문으로 영문 TSC 데이터시트 근거를 검색할 임베딩 담당자
- **상황**: 기존 실행 후보 9종과 조사 전용 2종에 로컬 오픈 가중치 `voyage-4-nano`와 OpenRouter API `voyage-4`를 비교 후보로 추가한다.
- **문제**:
  1. Nano의 로컬 결과와 Voyage 4 API 결과는 같은 계열이어도 같은 모델 점수로 간주할 수 없다.
  2. 두 모델 모두 query/document 입력 구분과 가변 차원을 사용하므로 입력 계약을 고정해야 한다.
  3. API 정책 차단을 품질 실패로 기록하면 후보 비교가 왜곡된다.
- **측정 지표**: 실제 PDF smoke Recall@5·MRR, 1,000청크 임베딩 시간 또는 비용, 질의 p50/p95, 오프라인 재현 여부, API 성공·차단 상태

## Goal

- **해결 목표**: 기존 공통 평가기를 유지하면서 Voyage 두 후보를 1,024차원·query/document 분리 조건으로 평가하고, 실행 수준과 운영 가능성을 분리해 기록한다.
- **성공 기준**:
  - registry가 기본 실행 후보 9종에 Voyage 2종을 더한 실행 후보 11종과 조사 전용 2종을 관리한다.
  - Nano는 모델·원격 코드 revision을 같은 40자리 SHA로 고정하고 `encode_query`·`encode_document`를 사용한다.
  - Nano의 성공 결과에는 실제 query/document 모드와 자동 prompt, 1,024차원, 오프라인 상태가 기록된다.
  - Voyage 4 API는 OpenRouter 모델 ID, `input_type`, 1,024차원, 단가, retry 0을 고정한다.
  - API 정책·endpoint 차단은 오류 상태로 보존하고 Recall@5·MRR을 생성하지 않는다.
- **Out of Scope**: 서비스 기본 임베딩 변경, DB `vector(1536)` Migration, OpenRouter 계정의 ZDR/data-policy 변경, 전체 1,360건 본평가, 최종 모델 선정, Voyage 계열 간 공유 벡터 공간 검증

## What

### Happy Path

1. 평가기가 고정된 실제 PDF smoke JSONL을 읽는다.
2. Nano는 문서와 질의를 각각 전용 encoder로 1,024차원 인코딩한다.
3. API 모델은 문서에 `document`, 질의에 `query` 입력 유형과 1,024차원을 요청한다.
4. 공통 dense cosine `k=5`로 Recall@5·MRR·지연을 계산한다.
5. 모델 ID·revision·라이선스·입력 모드·prompt·실행 환경을 결과 JSON에 기록한다. 실행 환경에는 Python과 `numpy`·`sentence-transformers`·`torch`·`transformers`·`openai` 버전을 포함하며, 설치되지 않은 패키지는 `null`로 기록한다.

### Edge Cases

| ID | 상황 | 처리 |
|---|---|---|
| EC-01 | OpenRouter 키 없음 | 호출하지 않고 `not_run_no_key`로 기록한다. |
| EC-02 | ZDR·data-policy가 endpoint를 제외함 | 계정 정책을 바꾸지 않고 오류·retry 0을 기록하며 품질 지표는 만들지 않는다. |
| EC-03 | API가 `input_type`·차원 계약을 거부함 | 해당 요청을 오류로 남기고 다른 형식으로 자동 재시도하지 않는다. |
| EC-04 | Nano 고정 snapshot이 오프라인 캐시에 없음 | 온라인으로 자동 전환하지 않고 명시적으로 실패한다. |
| EC-05 | 출력 차원이 1,024가 아님 | 품질 지표를 유효 결과로 저장하지 않는다. |
| EC-06 | Nano와 API 점수가 다름 | 서로 다른 후보로 보고 한 모델의 점수를 다른 모델에 이전하지 않는다. |

## How

- 공통 표본: `evals/embedding_real_pdf_smoke_v0.jsonl`의 PDF 3건·156청크·질의 9건
- 공통 검색: L2 정규화 dense cosine, `k=5`, BM25·필터·리랭커 없음
- Nano:
  - 모델 ID `voyageai/voyage-4-nano`
  - 모델·코드 revision `5fb34e870f49f19e79c94d5e118f5ee730133279`
  - `truncate_dim=1024`, `attn_implementation=sdpa`
  - `encode_query`·`encode_document`, `HF_HUB_OFFLINE=1` 재실행
- API:
  - OpenRouter 모델 ID `voyageai/voyage-4`
  - 문서 `input_type=document`, 질의 `input_type=query`, `dimensions=1024`
  - 공개 단가 `$0.06/M tokens`는 실행 전 다시 확인
  - `backend/services/llm.py::embed_texts` 경계만 사용하고 자동 재시도 0
- 서비스 경계: Voyage 2종은 평가 후보다. 현재 서비스 적재·검색과 DB는 `text-embedding-3-small`·`vector(1536)`을 유지한다. Voyage를 서비스 기본값으로 채택하려면 동결 본평가 뒤 별도 ADR·Migration·런타임 설정이 필요하다.

## AC

### AC-01 · 후보 수와 분류

- GIVEN: 임베딩 후보 registry
- WHEN: 실행·조사 후보를 분류함
- THEN: 실행 후보 11종과 조사 전용 후보 2종이며 Voyage 2종이 실행 후보에 포함됨

### AC-02 · Nano 입력 계약과 결과 메타데이터

- GIVEN: 고정 Nano snapshot과 실제 PDF smoke
- WHEN: 문서와 질의를 인코딩함
- THEN: 전용 encoder·1,024차원을 사용하고 결과에 두 입력 모드와 자동 prompt가 기록됨

### AC-03 · Nano 오프라인 재현

- GIVEN: 고정 snapshot 캐시
- WHEN: 네트워크 없이 같은 표본을 재실행함
- THEN: 같은 Recall@5·MRR을 내고 `hf_hub_offline=true`를 기록함

### AC-04 · API 입력 계약

- GIVEN: 정책상 허용된 OpenRouter endpoint
- WHEN: Voyage 4 문서와 질의를 호출함
- THEN: 각 역할의 `input_type`과 1,024차원을 사용하고 실제 응답 차원을 검증함

성공 호출과 응답 차원 검증 전에는 Voyage 4를 최종 모델로 선정하지 않는다.

### AC-05 · API 정책 차단

- GIVEN: 계정 ZDR·data-policy가 endpoint를 제외함
- WHEN: Voyage 4 평가를 한 번 요청함
- THEN: 오류·retry 0을 기록하고 Recall@5·MRR·비용 실측값을 생성하지 않음

### AC-06 · 서비스 기본값 보존

- GIVEN: Voyage 후보 평가 변경
- WHEN: 현재 서비스의 적재·검색 구성을 확인함
- THEN: `text-embedding-3-small`·`vector(1536)` 기본값은 바뀌지 않음
