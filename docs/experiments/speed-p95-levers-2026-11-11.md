# 속도 p95 레버 A/B

- 상태: 현행
- 기준일: 2026-11-12 (측정 2026-11-11)
- 기준 커밋: 6707002 (측정 시 코드 `9634c5c`, 작업트리에 미커밋 변경 있음: 원시 `summary.git`이 `9634c5c+dirty`)
- 정본 여부: 정본(레버별 A/B 설계와 채택·폐기 결과). 응답 시간 보고의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 8.1절
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [d8-stage-remeasure-plan.md](d8-stage-remeasure-plan.md)

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 정확도(관련 `cited_gold`, 무관 `correct_refusal`)를 떨어뜨리지 않고 문항 p95를 10초 이하로 줄이는 코드 기본값은 무엇인가 | 가이드 D8 목표 |
| 채택 | `FIND_N_DOCS` 기본 5, 평가용 `GATE_WARMUP` 플래그 | 3절 |
| 기본 유지·폐기 | 나머지 7개 레버(3절) | 3절 |
| 채택 구성 기준선(v3 50×1) | 50/50, mean 4.25초, p50 4.7초, p95 9.2초, max 15.5초 | `evals/results/graph/2026-11-11-speed-g-all/E-v3-50-warm-n5/set1.json` [실측] |
| 후속 확인 | 50/50, p50 4.9초, p95 10.0초 | `evals/results/graph/2026-11-12-d9-improve2/set1.json`(코드 `520988c+dirty`) [실측] |

## 2. 조건

- 공통: `RAGAS_ENABLED=0`, OpenRouter, 운영 코퍼스 DB 읽기, `run_gate --sets 1 --keep-going`, 평가셋 v3 또는 그 부분 집합. 후반 실험은 `GATE_WARMUP=1`.
- 한 번에 레버 하나만 바꾼다. 채택하지 않은 레버는 코드 기본값을 바꾸지 않고 환경변수 A/B만 남긴다.
- 재현(채택 구성):

```bash
GATE_WARMUP=1 FIND_N_DOCS=5 RAGAS_ENABLED=0 \
  uv run --env-file .env python -m evals.runners.run_gate evals/dataset_v3.jsonl \
  --out evals/results/graph/<새폴더> --sets 1 --keep-going --p95 120
```

## 3. 결과

### 3.1 레버별

기본값은 코드에서 확인했다(`backend/`·`evals/runners/`의 `os.getenv`). 표본이 6~9문항인 행은 일반화하지 않는다.

| 레버 | 환경변수(코드 기본) | 표본 | 통과 (기준 → 변경) | 시간 (기준 → 변경) | 결정 | 원시 |
|---|---|---|---|---|---|---|
| 평가 프로세스 앞 BM25·Voyage·MCP 데우기 | `GATE_WARMUP`(0) | 3문항 | 3/3, 3/3, 3/3 (cold, warm, warm+MCP) | p50·p95 cold 7.8·8.2, warm 7.8·9.1, warm+MCP 6.5·7.7초 | 측정·기동용으로 채택(정상 상태 속도 자체는 아님) | `evals/results/graph/2026-11-11-speed-s2-warmup/` |
| Spec `find`가 카드 읽는 앞 문서 수 | `FIND_N_DOCS`(5, `backend/rag/card_find.py:434`) | 7문항 | 7/7 → 7/7 | mean 7.5 → 7.0초, p95 10.4 → 9.9초 (n10 → n5) | 채택(기본 5) | `evals/results/graph/2026-11-11-speed-f-find-ndocs/SUMMARY.md` |
| 같은 레버 n3 | `FIND_N_DOCS=3` | 7문항 | 7/7 → 7/7 | mean 7.66 → 7.61초, p95 15.3 → 10.9초 | 보류(5 유지) | `evals/results/graph/2026-11-11-speed-g-all/SUMMARY.md` C |
| RAG partial 재검색(#49) | `DOCS_RETRY_PARTIAL`(1) | 6문항 | 6/6 → 6/6 (off) | p50 8.7 → 6.8초, p95 11.1 → 10.1초 | 기본 유지(off 폐기) | `evals/results/graph/2026-11-11-speed-s1-docs-retry/` |
| RAG 인용보정 LLM 1회 | `DOCS_CITE_REPAIR`(1) | 6문항 | 5/6 → 6/6 (off) | p50 9.2 → 6.9초, p95 15.8 → 9.8초 | 기본 유지 | `evals/results/graph/2026-11-11-speed-s3-cite-repair/` |
| Voyage rerank | `RETRIEVE_RERANK`(1) | 9문항 | 8/9 → 8/9 (rerank off) | mean 10.89 → 8.08초, p95 28.4 → 11.5초. 실패 문항이 v3-15에서 v3-01로 바뀜 | 기본 유지 | `evals/results/graph/2026-11-11-speed-e-warm/SUMMARY.md` |
| retrieve 방식 덮어쓰기 | `RETRIEVE_METHOD`(빈 값, hybrid) | 9문항 | 8/9 → 8/9 (bm25) | mean 10.89 → 8.24초, p95 28.4 → 14.8초 | bm25-only 기본 전환 폐기 | 같은 SUMMARY E2 |
| Supervisor 재계획 | `SUPERVISOR_REPLAN`(1) | 9문항 | 9/9 → 9/9 (off) | mean 8.32 → 9.48초, p95 10.1 → 14.9초 | off 폐기(느려짐) | `evals/results/graph/2026-11-11-speed-g-all/SUMMARY.md` A |
| RAG 검색 횟수 상한 | `DOCS_MAX_SEARCHES`(2) | 6문항 | 6/6 → 6/6 (1회) | mean 10.15 → 8.18초, p95 13.8 → 12.0초 | 기본 유지(#49와 충돌 가능, 표본 작음) | 같은 SUMMARY B |
| Spec near+전체 find 두 번 | `JUDGE_NEAR_FIND`(1) | 7문항 | 6/7 → 7/7 (off) | mean 8.19 → 8.76초, p95 13.2 → 16.8초 | 기본 유지(속도 악화) | 같은 SUMMARY D |

워밍업 관찰: 검색만 데우면 첫 문항 `품번·판 확인` 약 2.5초가 남고, MCP lookup까지 데우면 첫 facts 약 0.4초다. 워밍업 후 병목은 `회로 읽기`, Supervisor, RAG LLM, `find` 카드 읽기다.

### 3.2 FIND_N_DOCS 정확도 본측정 (v3 50문항 × `GATE_WARMUP=1`)

| n_docs | 통과 | Spec(candidate_*) 15 | mean | p50 | p95 | max | 원시 |
|---:|---|---|---:|---:|---:|---:|---|
| 10 | 37/50 (오류 행 13건, 측정 무효) | 15/15 `cited_gold` | 4.12 | 4.4 | 9.8 | 13.8 | `evals/results/graph/2026-11-11-ndocs-acc/N10/set1.json` |
| 5 | 50/50 | 15/15 | 4.25 | 4.7 | 9.2 | 15.5 | `evals/results/graph/2026-11-11-ndocs-acc/N5/set1.json`(= `speed-g-all/E-v3-50-warm-n5`) |
| 3 | 50/50 | 15/15 | 4.51 | 4.6 | 10.6 | 13.6 | `evals/results/graph/2026-11-11-ndocs-acc/N3/set1.json` |

수치 근거: `evals/results/graph/2026-11-11-ndocs-acc/SUMMARY.md`.

n10 무효 판정 [실측]: `evals/results/graph/2026-11-11-ndocs-acc/N10/set1.json`에서 `v3-38`부터 `v3-50`까지 13행(모두 무관 문항)은 `error: OpenAIRateLimitError`(HTTP 429, "anthropic/claude-haiku-5.5 is temporarily rate-limited upstream")이고 `answer_metric`이 None이다. `summary.stopped_at`은 `v3-38`이다. 측정이 공급자 429로 끊긴 것이다. 따라서 n10의 37/50은 n_docs와 정확도의 관계를 보여 주지 않는다. n5와 n3의 50/50 사이에서만 비교할 수 있다. n10 재측정은 하지 않았다.

n5를 유지하는 이유: n3은 이 세트 전체 50/50이지만 p95가 10.6초로 n5(9.2초)보다 길다. n3에서는 v3-11, v3-12의 후보 목록이 n10, n5와 달라지고(v3-11: S1G-K 대신 S1GH, v3-12: HER105G-K 대신 HER106G, `ndocs-acc/SUMMARY.md:45-46`) 두 문항 모두 `cited_gold`로 통과했다. 후보 구성이 바뀌므로 3 아래로 내리지 않는다.

## 4. 수용 기준

| 조건 | 결과 |
|---|---|
| 레버마다 정확도(pass·metric)와 latency를 같이 기록 | 3.1절 |
| 채택·폐기 표, 폐기 레버는 코드 기본을 바꾸지 않고 실험용 env만 | 3.1절, 기본값 코드 확인 |
| `FIND_N_DOCS`는 v3 50문항으로 정확도를 다시 측정 | 3.2절. n10은 429로 무효 |

## 5. 한계

- 위 측정은 작업트리에 미커밋 변경이 있는 상태(`9634c5c+dirty`)에서 했다.
- 표본이 작다(레버 A/B 3~9문항). 같은 문항의 회차 흔들림과 레버 효과를 가르지 못한다.
- n10 정확도(37/50)는 무효이며 재측정하지 않았다. n_docs 10의 정확도 비교는 없다.
- 서비스 기동 시 `warmup()` 자동 호출 배포, v3 50×2 공식 게이트 재실행, RAGAS를 켠 상태의 p95는 측정하지 않았다.
- 배포본과의 서버 시간 비교는 하지 않았다. `JUDGE_READ_VOTES`는 현재 코드에서 읽는 곳이 없다([실측] `backend/` grep 0건, 판정 읽기는 한 번: `backend/multi_agent/agents/judge.py:124`). 배포본이 다른 읽기 횟수로 동작하는지는 확인하지 못했다.
- 비용은 이 측정에서 모으지 않았다.
