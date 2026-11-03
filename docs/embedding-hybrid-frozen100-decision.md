# 동결 100문서 표본 임베딩 결정 근거

- 평가셋: 동결 50건 중 데이터시트 정답이 있는 19질의
- 코퍼스: TSC 데이터시트 100건, 4,305카드(고유 본문 4,056개)
- 검색: BM25 단독, dense 단독, BM25 top-50 + dense top-50 RRF(k=60)
- 최초 비교 제외: 품번 필터, 리랭커, HNSW. 후속 비교에서만 고정 API 리랭커를 추가
- 데이터셋 SHA-256: `2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b`
- 청크 SHA-256: `0b4c81ee9bf64120a07ff7f5dd3fc766f1215ffe7076440d56733c95eab8d030`

| 모델 | Dense R@5 / MRR | Hybrid R@5 / MRR | Hybrid 쪽 / 다중근거 | 질의 p50 / p95 | 1,000청크 시간 / 비용 | 차원 / 22K float32 |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3 Embedding 8B | .789 / .537 | **.895 / .695** | **.632** / .263 | 668 / 1,525ms | 55.22s / $0.001388 | 1024 / 85.94MiB |
| Perplexity Embed V1 0.6B | **.842 / .699** | .842 / **.763** | .368 / **.316** | 718 / **829ms** | **12.12s / $0.000551** | 1024 / 85.94MiB |
| OpenAI text-embedding-3-small | .789 / .655 | .789 / .675 | .368 / .263 | 845 / 1,009ms | 30.57s / $0.002579 | 1536 / 128.91MiB |
| multilingual-e5-large | .632 / .502 | .737 / .695 | .526 / .263 | 1,343 / 2,615ms | 38.16s / $0.001551 | 1024 / 85.94MiB |
| Amazon Titan Embed V2 | .632 / .412 | .737 / .614 | .421 / .211 | 694 / 884ms | 64.13s / $0.002599 | 1024 / 85.94MiB |

BM25 단독은 Recall@5 5/19(.263), MRR .133이다.

## 고정 API 리랭커를 추가했을 때

후속 실험은 임베딩 모델별 Dense·BM25·RRF 조건을 유지하고 RRF 상위 50개만 같은 `qwen/qwen3-reranker-8b` API로 다시 정렬했다. 후보 hit@50은 리랭커가 정답을 Top 5로 올릴 수 있는 상한이며, 최종 MRR은 기존 표와 같은 Top-5 범위다.

| 임베딩 모델 | 후보 hit@50 | RRF R@5 / MRR | 리랭킹 R@5 / MRR | 리랭킹 쪽 / 다중근거 | p95 / 증분 비용 |
|---|---:|---:|---:|---:|---:|
| Qwen3 Embedding 8B | 1.000 | .895 / .695 | .947 / .798 | **.895 / .526** | 1.85초 / $0.058630 |
| Perplexity Embed V1 0.6B | 1.000 | .842 / .763 | **1.000** / .739 | .737 / .368 | 1.99초 / $0.060424 |
| OpenAI text-embedding-3-small | .947 | .789 / .675 | .895 / .829 | .737 / .474 | 1.46초 / $0.054183 |
| multilingual-e5-large | 1.000 | .737 / .695 | **1.000 / .868** | .737 / .421 | 1.57초 / $0.058692 |
| Amazon Titan Embed V2 | 1.000 | .737 / .614 | .895 / .833 | .684 / .316 | **1.32초** / $0.054099 |

리랭커는 임베딩 모델의 후보 생성 품질을 대체하지 않는다. OpenAI는 `draft50-n08`의 정답이 RRF 상위 50에 없어 최종 Top 5로 복구하지 못했다. 반대로 E5는 RRF Top 5 성능이 낮았지만 정답이 후보 50 안에는 모두 있어 리랭커 뒤 문서 Recall@5 1.000과 MRR .868이 됐다.

하나의 절대 1위도 생기지 않았다. 문서 Recall@5·MRR은 E5+Qwen 리랭커가 가장 높고, 정확한 쪽·다중근거 동시 회수는 Qwen Embedding 8B+Qwen 리랭커가 가장 높다. SojaFit은 쪽·표·행 인용과 복수 조건 근거가 중요하므로 현재 **서비스 적합 우선 확정 후보는 Qwen Embedding 8B+Qwen 리랭커**, **문서 검색 대조 후보는 E5+Qwen 리랭커**로 둔다. 이는 전체 1,360문서 본평가 전의 후보 지정이지 런타임 확정이 아니다.

Perplexity는 Recall@5가 .842에서 1.000으로 올랐지만 MRR은 .763에서 .739로 낮아졌다. Qwen도 `draft50-n08`이 RRF 5위에서 리랭킹 Top 5 밖으로 밀렸다. 따라서 “리랭커를 붙이면 모든 문항과 지표가 개선된다”고 해석하지 않는다.

## 기존 Dense-only 비교와 이번 Hybrid 비교의 차이

기존 표와 이번 표는 모델 이름만 보고 점수를 이어 붙이면 안 된다. 입력 코퍼스, 질의, gold, 검색 방식, 실행 위치와 일부 모델 ID가 다르기 때문이다. **이번 표 안의 다섯 성공 모델끼리는 직접 비교할 수 있지만, 기존 표의 수치와 이번 표의 수치는 증거 수준이 다른 별도 실험**이다.

| 축 | 기존 Dense-only 예비 비교 | 이번 동결 100문서 비교 |
|---|---|---|
| 목적 | 후보를 넓게 거르는 smoke/proxy | 동결 질의로 API 후보의 선택 근거 마련 |
| 질의 | 합성 30청크·18질의 또는 실제 PDF 3건·9질의 | 동결 50건 중 데이터시트 gold가 있는 19질의 |
| 검색 코퍼스 | 합성 30청크 또는 실제 PDF 3건·156카드 | 실제 TSC PDF 100건·4,305카드(고유 본문 4,056개) |
| 검색 방식 | dense cosine top-5 | BM25 단독, dense 단독, BM25 top-50 + dense top-50의 RRF(k=60) |
| gold | 주로 질의당 단일 청크 | 문서·쪽 단위 복수 gold와 다중 근거 포함 |
| 필터·리랭커 | 없음 | 없음. 품번 필터도 넣지 않음 |
| 실행 위치 | 로컬 모델은 RTX 5060 Laptop GPU, API 후보는 별도 proxy | 성공 5종 모두 OpenRouter 관리형 API |
| 지연의 의미 | 로컬 GPU 또는 작은 proxy의 API 지연 | 4,056개 고유 본문 색인과 19개 API 질의의 실측 |
| 공식성 | 비동결 예비 결과 | 질의는 동결됐지만 코퍼스는 사후 고정 100문서 표본 |

### Dense와 Hybrid가 재는 것

- Dense는 한국어 질문과 영문 데이터시트 문장의 의미적 유사도를 임베딩 하나로 순위화한다.
- BM25는 품번, 전압·전류 기호, 패키지명처럼 정확히 겹치는 영문·숫자 토큰을 찾는다.
- Hybrid는 두 점수를 직접 더하지 않는다. Dense 상위 50개와 BM25 양수 점수 상위 50개의 **순위만** RRF로 합쳐 최종 top-5를 만든다.
- 따라서 Hybrid 결과에는 임베딩 모델의 품질뿐 아니라 BM25 토큰화와 RRF 후보 결합 효과도 포함된다. 임베딩 모델 자체의 차이는 Dense 열을 함께 봐야 한다.

이번 BM25 단독 성능은 Recall@5 5/19, MRR .133으로 낮다. 한국어 조사·설명은 BM25 영문·숫자 토크나이저에서 대부분 사라지고, 품번이 반복되는 표지·자매 데이터시트가 올라오기 때문이다. 그럼에도 Dense가 놓친 일부 문서에는 정확 품번 토큰이 보완 신호가 됐다.

| 모델 | Dense → Hybrid Recall@5 | Dense → Hybrid MRR | Dense → Hybrid 쪽 적중 | Dense → Hybrid 다중근거 |
|---|---:|---:|---:|---:|
| Qwen3 Embedding 8B | .789 → **.895** (+2문항) | .537 → **.695** | .632 → .632 | **.474 → .263** |
| Perplexity Embed V1 0.6B | .842 → .842 | .699 → **.763** | .474 → .368 | .211 → **.316** |
| OpenAI text-embedding-3-small | .789 → .789 | .655 → .675 | .421 → .368 | .263 → .263 |
| multilingual-e5-large | .632 → **.737** (+2문항) | .502 → **.695** | .421 → **.526** | .158 → **.263** |
| Amazon Titan Embed V2 | .632 → **.737** (+2문항) | .412 → **.614** | .263 → **.421** | .105 → **.211** |

Hybrid가 모든 지표를 개선한 것은 아니다. Qwen은 문서 Recall과 첫 정답 순위가 좋아졌지만, 필요한 모든 gold가 top-5에 함께 들어오는 다중 근거 Recall은 낮아졌다. Perplexity와 OpenAI도 쪽 적중이 낮아졌다. 그러므로 Qwen 선정은 “Hybrid가 전 지표에서 우승”이 아니라, **문서 누락 방지와 정확한 쪽 적중을 우선한 품질 선택**이다. 다중 근거 동시 회수가 최우선이면 Perplexity와 Qwen을 별도 게이트로 다시 비교해야 한다.

### 기존 후보와 이름이 비슷해도 같은 모델이 아닌 경우

- 기존 Qwen/Qwen3-Embedding-0.6B는 로컬 0.6B 모델이고, 이번 qwen/qwen3-embedding-8b는 OpenRouter의 8B API 모델이다. 파라미터 규모, 운영 endpoint와 지연이 다르므로 기존 0.6B 점수를 8B에 이전하지 않았다.
- 기존 intfloat/multilingual-e5-large-instruct 로컬 결과와 이번 intfloat/multilingual-e5-large API 결과는 모델 ID와 query 형식이 다르다. 이번에는 API 모델 권장 query:/passage: 접두어로 새로 측정했다.
- 기존 BGE-M3·KURE-v1·Voyage 4 Nano의 로컬 GPU 점수는 이번 관리형 API 점수가 아니다. KURE와 Nano는 이번 API 평가군에 없고, BGE API는 공급자 429로 완료되지 않았다.
- Perplexity Embed V1 0.6B와 Amazon Titan V2는 이번 표본에서 새로 추가한 관리형 API 대조군이다.
- Voyage 4와 Voyage 4 Lite는 ZDR 정책 때문에 embedding을 받지 못했으므로 기존 조사 결과나 0점으로 순위를 채우지 않았다.

### 과거 3문서 Hybrid에서 성능이 낮아진 것과 모순되지 않는 이유

기존 실제 PDF 3건·156카드·9질의 smoke에서는 BM25 단독 hit@5가 0이었고, RRF가 품번 반복 카드를 올려 다섯 로컬 모델 모두 dense보다 나빠졌다. 이번에는 정답·자매 문서와 고정 혼동 문서를 포함한 100문서·19질의에서 BM25가 5문항을 맞혔고, Qwen·E5·Titan이 dense에서 놓친 문서를 보완했다. 표본과 질의가 달라진 결과이므로 “Hybrid는 항상 좋다” 또는 “항상 나쁘다”로 일반화하지 않는다.

### 직접 비교할 수 있는 범위

1. 이번 표의 성공 5종은 동일한 데이터셋 SHA-256과 청크 SHA-256, 같은 BM25·RRF 조건을 사용했으므로 서로 비교할 수 있다.
2. 모델별 query/document 형식은 해당 모델의 권장 계약에 맞췄다. 이는 실제 운영 성능 비교에는 필요하지만 순수 아키텍처만 바꾸는 실험은 아니다.
3. 기존 Dense-only 표는 후보 발굴 이력으로 남기며, 이번 모델 순위에 수치를 합산하거나 평균내지 않는다.
4. 이번 결과도 1,360문서 전체 본평가가 아니므로 전체 코퍼스 성능으로 표현하지 않는다.

## 표본 범위 결정

리랭커 없는 검색의 품질 우선 1순위는 `qwen/qwen3-embedding-8b`다. Hybrid Recall@5가 17/19로 가장 높고, 정확한 데이터시트 쪽 적중도 12/19로 가장 높다. 1024차원이라 현재 1536차원 기준선보다 벡터 원시 용량도 약 33% 작다.

비용·첫 정답 순위·지연 우선 대안은 `perplexity/pplx-embed-v1-0.6b`다. Hybrid MRR .763, p95 829ms, 1,000청크 환산 비용 $0.000551로 가장 유리하다. 다만 Recall@5는 16/19, 쪽 적중은 7/19다.

리랭커를 운영 구성에 포함하면 Qwen+Qwen 리랭커와 E5+Qwen 리랭커를 전체 코퍼스에서 다시 비교한다. 현재 코드 기본값은 변경하지 않는다. 임베딩과 리랭커를 실제 기본값으로 확정하려면 운영 비용·p95 게이트, API allowlist, 1024차원 Migration과 ADR을 별도 변경해야 한다.

## 재현 자료와 공개 범위

- 평가기: [`evals/evaluate_frozen_embedding_sample.py`](../evals/evaluate_frozen_embedding_sample.py)
- 표본 선택·해시: [`embedding_hybrid_frozen100_selection_2026-11-02.json`](../evals/results/embedding_hybrid_frozen100_selection_2026-11-02.json)
- 비교 요약: [`embedding_hybrid_frozen100_summary_2026-11-02.json`](../evals/results/embedding_hybrid_frozen100_summary_2026-11-02.json)
- 모델별 원시 순위: `evals/results/embedding_hybrid_frozen100_*_2026-11-02.json`
- 리랭커 평가기: [`evals/evaluate_frozen_reranker.py`](../evals/evaluate_frozen_reranker.py)
- 리랭커 비교 요약: [`rerank_hybrid_frozen100_summary_2026-11-02.json`](../evals/results/rerank_hybrid_frozen100_summary_2026-11-02.json)
- 리랭커 모델별 원시 순위: `evals/results/rerank_hybrid_frozen100_*_2026-11-02.json`
- 출처 메타데이터: `evals/embedding_frozen100_catalog_v1.csv`, `evals/embedding_frozen100_manifest_v1.jsonl`

카드 본문 `chunks.jsonl`, Docling 파싱 JSON, 벡터 `vectors.f32`, API 키와 provider 원문 응답은 Git에 넣지 않는다. selection에 기록한 청크 SHA-256과 같은 로컬 입력을 준비한 뒤 아래 형식으로 재생성한다.

```bash
uv run python -m evals.evaluate_frozen_embedding_sample \
  --model qwen/qwen3-embedding-8b \
  --chunks LOCAL_CHUNKS.jsonl \
  --work-dir LOCAL_WORK \
  --output LOCAL_RESULT.json
```

키가 없으면 `not_run_no_key`, provider 과부하·ZDR 차단이면 구조화 오류와 retry 0을 기록한다. 재실행 전에 현재 단가·예상 토큰·비용 상한을 다시 확인한다.

## 실행 실패

- `baai/bge-m3`: 공급자 과부하 429, retry 0. 품질 0점으로 처리하지 않음.
- `voyageai/voyage-4-lite`, `voyageai/voyage-4`: 계정과 guardrail의 ZDR 정책으로 endpoint 제외. 정책 변경 없음.

## 한계

이 결과는 동결 질의를 사용했지만 100문서 사후 표본이다. 사전 등록된 1,360문서 전체 본평가는 아니므로, **표본 범위의 모델 결정 근거**로 사용한다. 전체 코퍼스 점수라고 표시해서는 안 된다.

총 API 사용량은 2,843,356토큰, 비용은 $0.035611288다.

후속 리랭커 실험의 증분 사용량은 1,439,981토큰, 비용은 $0.28602983이다. Qwen 실행 중 HTTP 503 한 번은 자동 재시도하지 않았고, 사용자 승인 뒤 완료 11건을 재사용해 남은 8건만 수동 1회 재개했다.
