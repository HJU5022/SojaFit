# D8 단계별 응답 시간·비용 측정의 원본과 재현

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본. 측정값의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 8장. 이 문서는 8장 숫자의 원본 파일, 재현 명령, 단계 시간을 낼 수 있는 길, 측정하지 않은 항목을 정리한다
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [speed-p95-levers-2026-11-11.md](speed-p95-levers-2026-11-11.md), [scripts/eval/EVAL.md](../../scripts/eval/EVAL.md)

## 1. 질문과 범위

과제 가이드 D8은 검색, 리랭킹, 생성, 승인 대기 단계별 응답 시간과 비용을 현재 코드로 재고 원시 결과와 한 줄 재현 명령을 요구한다. 8장의 LLM 단계 표 일부는 판정 읽기 3번 다수결 시절 코드(`93a497c`) 값이고 현재 코드(판정 읽기 1번)와 다르다.

## 2. 8장 숫자의 원본

| 8장의 숫자 | 원본 | 비고 |
|---|---|---|
| 질문 임베딩, DB+BM25+RRF, 리랭킹 시간, `retrieve()` 전체, rerank 호출당 토큰 | `evals/results/retrieval/service_stages_2026-11-04.json`(이전 값), `service_stages_2026-11-11.json`(현재 코드) | 20문항 |
| 현재 코드 50문항 단계별 p50·p95·호출 수·비용 | `evals/results/graph/2026-11-11-d8-stages/set1.json`, `stage_summary.json`, 재실행 `evals/results/graph/2026-11-11-d8-stages-rerun/set1.json` | `stage_summary.json`: 50/50 통과, p50 4.9초, p95 10.7초, Supervisor p50 1.525초·p95 2.488초, 그래프 안 검색 n=15 p50 1.396초·p95 5.192초 |
| 이전 값(3번 다수결, `93a497c`) 4세트 | `evals/results/graph/2026-11-10-v3-haiku-sets/gate-v3_draft-1110-{0033,0034,0040,0041}-set1.json`, `summary_4sets_93a497c.json` | 비용(`usd`)은 Langfuse 토큰 집계라 세트 파일에는 없고 summary에만 있다 |
| 이전 값 병합 뒤 2세트 | `gate-dataset_v3-1110-{0111,0112}-set1.json`, `summary_merged_2sets_f2b914e.json` | |
| 이전 값 LLM 단계별 | `stage_costs_gate-v3_draft-1110-0040-set1.json` | 만든 스크립트가 저장소에 없어 재생성 명령 없음 |
| 복사 경위와 해시 | `evals/results/graph/2026-11-10-v3-haiku-sets/sources_2026-11-11.json` | 저장소 밖 실험 폴더에서 복사 |
| rerank-3 가격(100만 토큰당 0.05달러) | Voyage 가격표(웹) | 저장소에 가격 파일이 없다. 토큰 수는 `service_stages_*.json`에 있고 곱셈은 `scripts/eval/stage_report.py`의 `RERANK_USD_PER_TOKEN` |

p50 정의가 둘이다. `run_gate`의 세트 파일 `summary.p50_s`는 `sorted(latency)[n//2]`이고, `stage_report.py`와 `stage_summary.json`의 p50은 진짜 중앙값이다. p95는 가장 가까운 순위(올림(0.95n)번째)로 같다.

## 3. 재현 명령

| 무엇 | 명령 | 조건 |
|---|---|---|
| 현재 코드 v3 50문항 1세트 | `uv run --env-file .env python -m evals.runners.run_gate evals/dataset_v3.jsonl --out <새 결과 폴더> --sets 1 --keep-going` | 운영 DB 읽기, OpenRouter, Voyage 키. 유료 |
| 단계별 집계 | `uv run python -m scripts.eval.stage_report evals/results/graph/2026-11-11-d8-stages/set1.json evals/results/graph/2026-11-11-d8-stages-rerun/set1.json --retrieval evals/results/retrieval/service_stages_2026-11-11.json` | 모델 호출 없음 |
| `retrieve()` 단계별 | `uv run --env-file .env python -m evals.runners.run_retrieval_service --stages 20 --out evals/results/retrieval/<새 이름>.json` | 운영 DB, Voyage |
| 승인 대기 | `uv run --env-file .env python -m scripts.eval.approval_wait_report --since 2026-11-11 --exclude-users <스모크 계정 id>` | 읽기 전용 DB 연결 |
| 배포 API 한 흐름(서버 시간) | `uv run python scripts/smoke/http_smoke.py --base-url https://<배포 주소> --confirm-live` | 문항 v3-01 하나. 재개와 승인을 자동으로 바로 보내므로 사람 대기 시간이 아니다 |

## 4. 단계 시간을 낼 수 있는 길

| 단계 | 평가 실행기(`run_gate`) | 서비스(`analysis_events.stages`) |
|---|---|---|
| 검색 | 문항 행의 `stages` | `search` 한 칸. 임베딩·리랭킹으로 쪼개지 않는다. 쪼갠 값은 `run_retrieval_service --stages`(`retrieve()` 단독)만 낸다 |
| LLM 단계별 | 문항 행의 `llm_call_log`, `voyage` | 노드 단위만. 호출 단위는 `backend/services/service_trace.py`가 켜진 경우 Langfuse에서 읽는다 |
| 판정 코드 | 문항 행의 `stages`(`대체 부품 판정` 등) | `대체 부품 판정` 노드와 `specs`·`find` 칸 |
| 승인 대기 | 해당 없음 | 칸 없음. DB 시각에서 계산 |

`stages`는 API 응답에 나오지 않는다. DB `sojafit_agent.analysis_events`를 읽어야 한다(`approval_wait_report.py`가 읽는다).

승인 대기 계산: 재개 대기 = 재개 행 `created_at − elapsed_ms` − 앞 행 `created_at`(앞 행이 WAITING일 때). 승인 대기 = `approvals.created_at` − 승인 직전 DONE 행의 `created_at`. 스모크 계정의 자동 재개·승인(응답 직후 요청, 3초 이내)은 사람 대기에서 뺀다.

## 5. 비용 가정

- 가격 근거: `backend/services/llm.py` `MODEL_RATES`(Haiku 5.5, Sonnet 5.5). 서비스 예약 기본 단가 `ANALYSIS_PROMPT_RATE`, `ANALYSIS_COMPLETION_RATE`는 표에 없는 모델에만 쓰인다(`backend/conversations/memory_service.py:176`).
- 예약 상한은 실제 청구와 다르다. 서비스는 호출 전에 입력 바이트 + 8192 + 출력 토큰으로 최대 비용을 예약하고 돌려주지 않는다. 한 분석의 상한은 $0.50, 사용자 하루는 $3와 `USER_DAILY_TOKENS` 5,000,000이다(`memory_service.py:55`).
- 서비스 분석은 호출 간격 2초 제한(`ANALYSIS_MIN_INTERVAL_SECONDS`)이 있어 연달아 보낼 때 간격을 둔다.
- 8장 비용은 OpenRouter 가격 × Langfuse 토큰이며 실제 청구액과 대조하지 않았다.

## 6. 한계

- 승인 대기 값은 측정하지 않았다(EVAL_REPORT 11장 4행: 실사용 3회 뒤 채우기로 미룸). 운영 DB의 `analysis_events`·`approvals` 실제 행 수는 확인하지 못했다.
- `JUDGE_READ_VOTES`는 현재 코드에서 읽는 곳이 없다([실측] `backend/` grep 0건, `backend/multi_agent/agents/judge.py:124` 주석: 읽기는 한 번). 환경변수는 `tests/`와 `evals/runners/run_injection_baseline.py`가 설정만 한다. 배포 리비전이 3번 읽기 코드인지는 확인하지 못했다(`README.md` 맨 위 표의 리비전 기준).
- 이전 값 4세트의 집계 스크립트와 `exp-haiku-1109/*`, 회의록의 질문 종류별 비용·판정 질문 타임라인(v3-01, v3-20) 원본은 저장소에 없다.
- Voyage 질문 임베딩 단가는 저장소에 없다. 질문이 짧아 0.0001달러 미만으로 본다 [추정].
- 배포 API 반복 측정(`http_smoke.py`는 v3-01, v3-30 둘뿐)과 서비스 경로에서 `retrieve()` 안쪽 단계 시간 기록은 구현하지 않았다.
- 서비스가 승인 대기를 직접 남기려면 `analysis_events`에 질문 시각 칸 또는 `runs`에 상태 전이 이력이 필요하다. DB 스키마 변경이라 범위 밖이다.
