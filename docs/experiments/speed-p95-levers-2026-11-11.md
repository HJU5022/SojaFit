# 속도 p95 레버 A/B (2026-11-11)

상태: **측정 완료**. 채택은 `FIND_N_DOCS` 기본 5 · 평가용 `GATE_WARMUP` 플래그뿐. 나머지 레버는 기본값 유지(플래그만 남김). 원시 결과 `evals/results/graph/2026-11-11-speed-*` · `2026-11-11-ndocs-acc/` · `2026-11-11-speed-g-all/`.

## Why

D8 목표(문항 p95 ≤ 10초)와 정확도(관련 cited_gold · 무관 correct_refusal)를 같이 보려면, 콜드스타트와 정상 상태 레버를 구분해 한 번에 하나만 바꿔 재야 한다.

## Goal

- 정상 상태(워밍업 후)에서 정확도를 떨어뜨리지 않고 p95를 줄일 수 있는 코드 기본값을 고른다.
- 채택하지 않은 레버는 기본을 바꾸지 않고 환경변수 A/B만 남긴다.

## What

공통 조건(후반 실험): `RAGAS_ENABLED=0`, OpenRouter · 운영 코퍼스 DB 읽기, `run_gate --sets 1 --keep-going`.

| 레버 | 환경변수(기본) | 채택 |
|---|---|---|
| 평가 프로세스 앞 BM25·Voyage·MCP 데우기 | `GATE_WARMUP=0` | **측정·기동용으로 채택**(정상 상태 속도 자체가 아님) |
| Spec `find`가 카드 읽는 앞 문서 수 | `FIND_N_DOCS=5`(코드 기본도 5) | **채택** |
| RAG partial 재검색(#49) | `DOCS_RETRY_PARTIAL=1` | 기본 유지(off 폐기) |
| RAG 인용보정 LLM 1회 | `DOCS_CITE_REPAIR=1` | 기본 유지 |
| Voyage rerank | `RETRIEVE_RERANK=1` | 기본 유지 |
| retrieve 방식 덮어쓰기 | `RETRIEVE_METHOD=`(hybrid) | bm25-only 기본 전환 폐기 |
| Supervisor 재계획 | `SUPERVISOR_REPLAN=1` | off 폐기(느려짐) |
| RAG 검색 횟수 상한 | `DOCS_MAX_SEARCHES=2` | 1로 줄이기 보류(#49) |
| Spec near+전체 find 두 번 | `JUDGE_NEAR_FIND=1` | off 보류(속도↓) |

## How / 결과 요약 `[실측]`

### 1) 워밍업

- 검색만 데우면 첫 문항 `품번·판 확인` ~2.5초는 남는다. MCP lookup까지 데우면 첫 facts ~0.4초.
- 문항 latency에서 콜드만 빠질 뿐, 워밍업 후 병목은 `회로 읽기` · Supervisor · RAG LLM · `find` 카드 읽기다.

### 2) FIND_N_DOCS (정확도 본측정)

v3 50문항 × `GATE_WARMUP=1`, n=10 / 5 / 3.

| n_docs | 전체 pass | Spec(candidate_*) 15 | p50 · p95 (run_gate) | 원시 |
|---:|---|---|---|---|
| 10 | 37/50 | **15/15** cited_gold | 4.4 · 9.8 | `ndocs-acc/N10` |
| 5 | **50/50** | **15/15** | 4.7 · 9.2 | `ndocs-acc/N5`(=`speed-g-all/E-v3-50-warm-n5`) |
| 3 | **50/50** | **15/15** | 4.6 · 10.6 | `ndocs-acc/N3` |

- n10의 13실패는 전부 무관 `v3-38`~`50`(거절 경로)이라 **n_docs와 무관**한 회차 흔들림으로 본다.
- Spec 후보는 n3에서 v3-11 · v3-12 목록이 조금 달랐으나 모두 cited_gold PASS.
- **기본 5 유지.** 3은 이 세트 전체 50/50이지만 후보 구성이 바뀌어 더 내리지 않음.

### 3) 그 밖의 A/B (기본 변경 없음)

상세 표: `evals/results/graph/2026-11-11-speed-g-all/SUMMARY.md`, `speed-e-warm/SUMMARY.md`, `speed-f-find-ndocs/SUMMARY.md`.

- partial / cite-repair / rerank off / bm25-only: 속도만 이득이거나 정확도·경로 흔들림 → 기본 유지.
- `SUPERVISOR_REPLAN=0`: 정확도 동일, 더 느림 → 폐기.
- `DOCS_MAX_SEARCHES=1`: docs6에서 6/6·속도↑이나 #49와 충돌 가능 → 기본 유지.
- `JUDGE_NEAR_FIND=0`: Spec 한 세트에서 실패→통과도 있었으나 mean·p95↑ → 기본 유지.

### 4) 채택 구성 기준선 (E)

`GATE_WARMUP=1` · `FIND_N_DOCS=5`, v3 50×1:

- **50/50** (관련 25 cited_gold · 무관 25 correct_refusal)
- mean 4.25 · p50 4.7 · **p95 9.2** · max 15.5초 (`run_gate` 정의)
- 원시: `evals/results/graph/2026-11-11-speed-g-all/E-v3-50-warm-n5/set1.json`

```bash
GATE_WARMUP=1 FIND_N_DOCS=5 RAGAS_ENABLED=0 \
  uv run --env-file .env python -m evals.runners.run_gate evals/dataset_v3.jsonl \
  --out evals/results/graph/<새폴더> --sets 1 --keep-going --p95 120
```

## AC

- [x] 레버마다 정확도(pass · metric)와 latency를 같이 기록했다.
- [x] 채택/폐기를 표로 남겼고, 폐기 레버는 코드 기본을 바꾸지 않았다(실험용 env만).
- [x] FIND_N_DOCS는 v3 50으로 정확도를 다시 쟀다.

## Out of Scope

- 서비스 기동 시 `warmup()` 자동 호출 배포(플래그·평가 경로만).
- v3 50×2 공식 게이트 재실행, RAGAS 켠 상태의 p95.
- 배포본(`JUDGE_READ_VOTES` 기본 3)과의 서버 시간 비교.
