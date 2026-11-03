# API 리랭커 후보 3종 선정 작업서

확인일: 2026-11-03

> **실행 상태: 완료(18/18 성공).** 이 문서는 후보·비교 계약의 정본이며, 아래 `미실행` 표는 결과를 보기 전에 고정한 입력 양식의 역사 기록이다. 최종 수치는 [`EVAL_REPORT.md` 1-4절](../../EVAL_REPORT.md#1-4-임베딩-6종--api-리랭커-3종-재측정-2026-11-03-사전-등록-17), 공개 JSON은 [`evals/results/reranker_matrix_2026-11-03_summary.json`](../../evals/results/reranker_matrix_2026-11-03_summary.json)을 따른다. 평가 1위는 `Qwen3-Embedding-0.6B × Voyage rerank-3`이지만 서비스 기본값 적용은 팀 결정 전까지 보류한다.

## Why

- **페르소나**: 데이터시트 검색 결과에서 정확한 품번·쪽·표·행 근거를 빠르게 확인해야 하는 SojaFit 사용자
- **상황**: 현재 하이브리드 검색은 관련 문서를 후보로 가져오지만, 이름이 비슷한 다른 부품이나 같은 계열의 다른 쪽이 상위에 섞인다.
- **문제**: 임베딩과 BM25가 만든 후보를 그대로 상위 5개로 쓰면 첫 정답 순위와 정확한 쪽 적중이 낮다. 원격 `main`의 기준선은 문서 Recall@5 `0.737`, MRR `0.649`, 쪽 적중@5 `0.368`이다.
- **측정 지표**: 문서 Recall@5, 문서 MRR, 쪽 적중@5, 다중 근거 Recall@5, 리랭크 p50·p95, 질문당 토큰·비용, 좋아진 문항과 회귀한 문항 수

## Goal

- **해결 목표**: 임베딩 6종이 만든 하이브리드 후보에 API 리랭커 3종을 같은 조건으로 적용해, SojaFit에 맞는 리랭커를 숫자와 문항별 근거로 고른다.
- **성공 기준**:
  - 같은 임베딩·같은 후보에서 리랭커 없음 대비 문서 MRR `+0.05` 이상
  - 문서 Recall@5가 기준선보다 낮아지지 않음
  - 리랭크 p95 `2초` 이하
  - 비용·토큰·실패·회귀 문항을 빠짐없이 기록
- **Out of Scope**:
  - 품번 필터와 질문 줄이기 적용
  - 임베딩 모델 변경 또는 재선정
  - 기존 로컬 캐시 삭제 또는 신규 모델 가중치 다운로드
  - 서비스 기본 리랭커 확정, 배포, DB Migration
  - 유료 API의 승인 전 실행

## What

### 후보 1 — Cohere 직접 API `rerank-v4.0-pro`

- Cohere Rerank 5 Pro가 공급사 최신 모델이지만, 기존 후보로 고정한 Rerank 4 Pro의 provider 경로만 바꿔 비교 조건을 유지한다. 평가기 내부 후보명은 기존 표와의 연결을 위해 `cohere/rerank-4-pro`를 유지하고 실제 공식 API 모델 ID는 `rerank-v4.0-pro`를 기록한다.
- 한국어와 영어를 포함한 100개 이상 언어와 32K 문맥을 지원해 한국어 질문과 영문 데이터시트를 연결하는 이번 평가에 적합하다.
- OpenRouter의 동일 모델은 계정 ZDR 정책으로 404가 발생해 모델은 유지하고 provider 경로만 Cohere 공식 API로 바꿨다.
- API: `POST https://api.cohere.com/v2/rerank`
- 인증: `COHERE_API_KEY`
- 공식 근거: [Cohere Rerank API](https://docs.cohere.com/reference/rerank), [Cohere Rerank 모델](https://docs.cohere.com/docs/rerank)

### 후보 2 — Voyage 직접 API `rerank-3`

- Voyage 공식 문서가 현재 최고 정확도·일반 용도 권장 모델로 안내한다.
- 원격 저장소의 기존 실험에서 `text-embedding-3-small` 하이브리드 MRR을 `0.649 → 0.860`으로 높였고 p95가 0.6초 이하였다. 이 값은 재실행 결과가 아니라 기존 비교 기준으로만 사용한다.
- 기존 증거를 같은 평가 조건으로 재검증할 수 있는 연속성 후보로 사용한다.
- OpenRouter ZDR 정책 404를 피하기 위해 모델은 그대로 두고 Voyage 공식 API로 직접 호출한다.
- API: `POST https://api.voyageai.com/v1/rerank`
- 인증: `VOYAGE_API_KEY`
- 공식 근거: [Voyage rerank-3](https://docs.voyageai.com/docs/reranker), [Voyage rerank API](https://docs.voyageai.com/reference/reranker-api)

### 후보 3 — OpenRouter `qwen/qwen3-reranker-8b`

- Qwen3 Reranker 8B는 100개 이상 언어, 긴 문맥, 지시문 인식 기능을 제공한다.
- 공개 가중치 모델이지만 리랭커 평가는 OpenRouter의 통합 rerank API로 호출한다. 새 가중치를 로컬에 받지 않는다.
- 상용 폐쇄형 API 두 종과 다른 계열을 비교하면서도, 이전 Qwen 리랭커 실험과 연결할 수 있는 대조 후보로 사용한다.
- API: `POST https://openrouter.ai/api/v1/rerank`
- 공식 근거: [OpenRouter Qwen 모델 목록](https://openrouter.ai/qwen), [OpenRouter rerank API](https://openrouter.ai/docs/api/api-reference/rerank/create-rerank)

### 후보에서 제외한 모델

| 모델 | 이번 3종에서 제외한 이유 |
|---|---|
| `cohere/rerank-v5.0-pro` | 공급사 최신 모델이지만 기존 Rerank 4 Pro 실패의 provider 경로만 바꾸는 후속 실행에서는 모델까지 바꾸지 않는다. |
| `cohere/rerank-4-fast` | OpenRouter에서 호출할 수 있지만 첫 실험은 같은 세대의 품질 우선 4 Pro만 사용한다. |
| `rerank-3-lite` | 기존 품질 우선 `rerank-3`과 같은 공급자의 경량 변형이므로 초기 3종에서는 중복을 줄인다. |
| `jina-reranker-v3.5` | 최신 다국어 후보지만 3종 제한에서 기존 증거가 있는 Voyage와 API·로컬 양쪽 이력이 있는 Qwen을 우선한다. 필요하면 후속 후보로 사전등록한다. |
| `bge-reranker-v2-m3` | OpenRouter의 현재 리랭커 후보가 아니며, 신규 로컬 가중치 다운로드 금지 조건에도 맞지 않는다. |

## How

### API 키와 신규 다운로드 금지 계약

1. Cohere는 `https://api.cohere.com/v2/rerank`, Qwen은 `https://openrouter.ai/api/v1/rerank`, Voyage는 `https://api.voyageai.com/v1/rerank`로 호출한다.
2. Cohere는 `COHERE_API_KEY`, Qwen은 `OPENROUTER_API_KEY`, Voyage는 `VOYAGE_API_KEY`를 사용한다. provider 실패 시 다른 모델이나 provider로 fallback하지 않는다.
3. 임베딩은 기존 로컬 캐시 또는 OpenRouter API를 사용할 수 있지만 신규 모델 가중치, tokenizer, Hugging Face snapshot은 다운로드하지 않는다.
4. API 호출은 저장소 규칙에 따라 `backend/services/llm.py` 한 곳을 통과한다. 평가기도 이 경계를 재사용한다.
5. 키는 `.env` 또는 배포 환경의 Secret Manager에만 둔다. 문서·코드·결과 JSON·로그에 키나 원문 인증 헤더를 남기지 않는다.
6. OpenRouter 응답에는 모델 ID, 실제 provider, 사용 토큰 또는 search unit, 지연시간, 상태 코드만 필요한 범위로 기록하고 request ID와 원문 응답은 공개 결과에서 제외한다.
7. 자동 재시도는 0회로 시작한다. 429·5xx·timeout은 품질 0점으로 바꾸지 않고 `실행 실패`로 분리한다.
8. 실행 직전에 모델 제공 상태와 단가를 OpenRouter 모델 페이지에서 다시 확인한다. 2026-11-03 조사값은 Voyage `rerank-3` $0.05/M tokens, Qwen3 Reranker 8B $0.20/M tokens, Cohere Rerank 4 Pro $0.0025/search다.

### 비교 조건

- 임베딩 6종: `text-embedding-3-small`, `Qwen3-Embedding-0.6B`, `voyage-4-lite`, `voyage-4`, `voyage-4-large`, `KURE-v1`
- 평가셋: 동결 v1의 데이터시트 근거 관련 19문항
- 검색: Dense 상위 50 + BM25 상위 50, RRF `k=60`, 정확 검색
- 리랭크 입력: 같은 임베딩의 RRF 후보 집합(최대 100개)
- 출력: 상위 5개
- 고정: 코퍼스, 질문 원문, 청킹, 품번 필터 없음, 질문 축약 없음
- 비교 단위: 임베딩 하나를 고정하고 `리랭커 없음`과 리랭커 3종을 비교한다. 서로 다른 임베딩의 점수를 리랭커 효과로 해석하지 않는다.

실제 호출 전 `evals/PREREGISTER.md`에 예상 토큰, 모델별 예상 비용, 전체 비용 상한, timeout과 중단 조건을 기록하고 사용자 승인을 받는다.

### 결과 보고 형식

- `6개 임베딩 × 3개 리랭커 = 18개 조합`을 전부 실행 대상으로 둔다.
- 순위가 높은 조합만 별도 Markdown으로 분리하거나 낮은 점수·실패 조합을 생략하지 않는다.
- 제출용 결과는 루트 `EVAL_REPORT.md`의 단일 표에 18개 조합을 모두 기록한다. 모델별 원시 JSON은 `evals/results/`에 따로 둘 수 있다.
- 행은 결과 순위가 아니라 아래의 고정 모델 순서로 정렬한다. 순위는 전체 행을 공개한 뒤 보조 열로만 계산한다.
- 순위의 주 지표는 리랭크 MRR이다. 표에는 MRR 내림차순의 정확 순위를 기록한다. MRR 차이가 `0.05` 미만인 조합은 해석에서 실질적으로 비슷한 점수대로 보고 p95와 비용을 함께 비교하되, 임의의 종합 점수를 만들지 않는다.
- API 오류·timeout·비용 상한 중단도 행을 삭제하지 않고 `status`와 실패 사유를 기록한다. 측정하지 못한 숫자는 0점 대신 `—`로 표시한다.

아래 표는 사전 고정 양식이므로 `미실행` 값을 사후 수치로 덮어쓰지 않는다. 실행 결과는 위에 연결한 단일 제출 표에서만 관리한다.

| 임베딩 | 리랭커 | status | 기준 Recall@5 | 기준 MRR | 기준 쪽 적중@5 | 기준 다중근거 R@5 | 리랭크 Recall@5 | 리랭크 MRR | ΔMRR | 리랭크 쪽 적중@5 | 리랭크 다중근거 R@5 | p50 | p95 | 토큰 | 비용(USD) | 좋아짐/나빠짐 문항 수 | 회귀 문항 ID | MRR 순위 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `text-embedding-3-small` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `text-embedding-3-small` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `text-embedding-3-small` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `Qwen3-Embedding-0.6B` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `Qwen3-Embedding-0.6B` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `Qwen3-Embedding-0.6B` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-lite` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-lite` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-lite` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-large` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-large` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `voyage-4-large` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `KURE-v1` | Cohere 직접 `rerank-v4.0-pro` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `KURE-v1` | Voyage 직접 `rerank-3` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `KURE-v1` | OpenRouter `qwen/qwen3-reranker-8b` | 미실행 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

## AC (Given-When-Then)

**AC-01 · provider별 키와 신규 다운로드 금지**
- GIVEN: 세 리랭커 중 하나를 평가하거나 서비스에서 호출한다.
- WHEN: 리랭크 요청을 실행한다.
- THEN: Cohere·Voyage는 공식 직접 API, Qwen은 OpenRouter를 사용하며, 기존 임베딩 캐시는 유지할 수 있지만 신규 모델 파일·Hugging Face 캐시는 만들지 않는다.

**AC-02 · 한 번에 하나만 변경**
- GIVEN: 임베딩 하나의 리랭커 없는 후보 순위가 고정돼 있다.
- WHEN: 리랭커 3종을 비교한다.
- THEN: 리랭커 모델 외의 질문·후보·top-k·필터·검색 조건은 동일하다.

**AC-03 · 과금 전 승인**
- GIVEN: 유료 API 평가를 시작하려 한다.
- WHEN: 첫 네트워크 요청을 보내기 전이다.
- THEN: 예상 토큰·비용·상한·중단 조건이 사전등록돼 있고 사용자가 해당 실행을 승인했다.

**AC-04 · 실패와 품질 분리**
- GIVEN: provider가 429, 5xx 또는 timeout을 반환한다.
- WHEN: 결과를 집계한다.
- THEN: 해당 조합을 0점으로 기록하지 않고 실행 실패로 표시하며 자동 재시도하지 않는다.

**AC-05 · 채택 판정**
- GIVEN: 같은 임베딩의 무리랭크와 리랭크 결과가 모두 있다.
- WHEN: 후보 채택을 판단한다.
- THEN: MRR 개선, Recall 회귀, 쪽·다중근거, p95, 비용과 회귀 문항을 함께 보고하고 단일 점수만으로 확정하지 않는다.

**AC-06 · 18개 조합 전부 공개**
- GIVEN: 6개 임베딩과 3개 리랭커의 실행이 끝났거나 일부 조합이 실패했다.
- WHEN: Markdown 결과를 작성한다.
- THEN: `EVAL_REPORT.md`의 한 표에 18개 행을 모두 유지하고, 성공·실패·낮은 점수를 생략하지 않으며 원시 결과 경로와 재현 명령을 함께 연결한다.
