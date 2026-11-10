# D8 단계별 응답 시간 · 비용 재측정 계획 (준비 문서, 모델 호출 없음)

상태: 2026-11-11 작성. 구현 · 측정은 아직 하지 않았다. 이 문서는 EVAL_REPORT.md 8장의 숫자가 어디서 나왔는지, 현재 코드로 다시 재려면 무엇이 필요한지, 얼마가 드는지를 코드와 저장소 파일로 확인한 것이다. 유료 실행은 정운 승인 뒤에만 한다.

## Why

과제 가이드 D8 필수 항목은 검색 · 리랭킹 · 생성 · 승인 대기 단계별 응답 시간과 비용을 현재 코드로 재고, 원시 결과와 한 줄 재현 명령을 함께 내라고 한다. 8장의 LLM 단계 표는 3번 다수결 시절 코드(`93a497c`)로 잰 것이라 지금 코드(`963fefe`에서 판정 읽기 1번)와 다르고, 집계 원본이 저장소 밖에 있었다.

## 1. 8장 숫자의 원본

| 8장의 숫자 | 원본 | 상태 |
|---|---|---|
| 질문 임베딩 · DB+BM25+RRF · 리랭킹 시간, `retrieve()` 전체, rerank 호출당 토큰 | `evals/results/retrieval/service_stages_2026-11-04.json`(raw 배열 포함, 커밋 `39229a9`) | 저장소 안에 있음 |
| rerank-3 가격 100만 토큰당 0.05달러 | Voyage 가격표(웹) | 저장소에 가격 파일 없음. 토큰 수만 위 파일에 있고 곱하기는 문서에서 한 것 |
| 4세트 통과 · p50 · p95 · LLM 비용 · 호출 수 | `evals/results/graph/2026-11-10-v3-haiku-sets/gate-v3_draft-1110-{0033,0034,0040,0041}-set1.json`(문항별 행) + `summary_4sets_93a497c.json` | 11-11 저장소로 옮김. 비용(`usd`)은 Langfuse 토큰 집계라 세트 파일에는 없고 summary에만 있음 |
| 병합 뒤 2세트(통과 · p95 · 비용) | `gate-dataset_v3-1110-{0111,0112}-set1.json` + `summary_merged_2sets_f2b914e.json` | 옮김 |
| LLM 단계별 p50 · p95 · 호출 수 · 질문당 비용 | `stage_costs_gate-v3_draft-1110-0040-set1.json`(문항별 행 포함) | 옮김. 만든 스크립트는 남아 있지 않아 재생성 명령 없음 |
| 질문 종류별 비용 · 시간 | 회의록 `D6-2026-11-10/트레이싱/최종-트레이스-링크.md`(저장소 밖) | 저장소에는 없음. 세트 파일의 `trace_url`로 Langfuse에서 열어 본다 |
| 판정 질문 v3-01 타임라인(품번 · 판 확인 2.6초, 판정 읽기 3.6초), v3-20 재검색 | 회의록 캡처 이미지(jpg) | 숫자 원본 없음(이미지만) |
| 병합 뒤 2세트의 "같은 맥에서 다른 작업 5개가 돌던 중" | 없음 | 원본 없음. 사전 등록 #50 줄의 서술뿐 |
| 승인 대기 시간 | 없음 | 측정한 적 없음 |

p50 정의가 둘이다. 세트 파일의 `summary.p50_s`는 실행기 정의 `sorted(latency)[n//2]`이고, `summary_*.json`의 p50은 진짜 중앙값이다. 1세트는 3.5와 2.6으로 다르다(관련 25문항은 느리고 무관 25문항은 1초대라 가운데가 벌어져 있다). 8장은 3.5를 쓴다. p95는 같다.

## 2. 한 줄 재현 명령

| 무엇 | 명령 | 조건 |
|---|---|---|
| 당시 4세트(`93a497c`) | 저장소 밖 `exp-haiku-1109/run_d50.sh`(00:33 · 00:34), `run_r50.sh`(00:40 · 00:41) | `run_gate_traced.py`(Langfuse에 지시문 등록 뒤 `run_gate.main` 호출), 환경 `LAB_FIND=cards LAB_SPECS=cards LAB_READ_VOTES=3 LAB_THINKING=off`. 평가셋 `lab/v3/evals/drafts/v3/v3_draft.jsonl`은 `evals/dataset_v3.jsonl`과 바이트가 같다(cmp 확인). 지금 코드에는 `LAB_*`를 읽는 곳이 없다(`LAB_READ_VOTES`는 `JUDGE_READ_VOTES`로 바뀌고 `963fefe`에서 3번 다수결이 사라짐) |
| 지금 코드 v3 50문항 1세트 | `uv run --env-file .env python -m evals.runners.run_gate evals/dataset_v3.jsonl --out <새 결과 폴더> --sets 1 --keep-going` | 운영 DB 읽기 · OpenRouter · Voyage 키 필요. `run_gate`는 지시문을 Langfuse에 등록하지 않는 점이 당시 `run_gate_traced.py`와 다르다 |
| `retrieve()` 단계별(#28) | `uv run --env-file .env python -m evals.runners.run_retrieval_service --stages 20 --out evals/results/retrieval/<새 이름>.json` | 운영 DB · Voyage. `retrieve.py`는 #28(`39229a9`) 뒤 `fa9ecc0`(11-05, MCP 도구 추가)만 건드렸다. 검색 경로가 같은지는 코드로 다 읽지 못함 |
| 배포 API 한 흐름(서버 시간) | `uv run python scripts/smoke/http_smoke.py --base-url https://<배포 주소> --confirm-live` | 문항 v3-01 한 개만. 실행 · 재개 · 승인의 ms가 나온다(예: `scripts/results/smoke/..._2026-11-11_042439.json`에서 run 6,483 · resume 1,279 · 승인 152ms). 이 스크립트는 재개와 승인을 바로 자동으로 보내므로 사람이 기다린 시간이 아니다 |

배포본(`27a410d`, 브랜치 `rd-final-int`)은 판정 읽기 기본이 아직 3번(`JUDGE_READ_VOTES` 기본 3)이다. `jeongun`은 1번이다. 어느 코드를 "현재"로 잴지 먼저 정해야 한다.

## 3. 단계별로 시간을 낼 수 있는 길

| 단계 | 평가 실행기(`run_gate`) | 서비스 경로(`analysis_events.stages`) | 비고 |
|---|---|---|---|
| 검색: 질문 임베딩 · DB+BM25+RRF · 리랭킹 | 못 냄(문항 행에 단계 시간 없음) | `search`(`timed_tool`) 한 칸. 임베딩 · 리랭킹으로 쪼개지 않음 | 쪼갠 값은 `run_retrieval_service --stages`만 낸다(`retrieve()` 단독) |
| LLM 단계별(Supervisor · 회로 읽기 · 문서 답 · 카드 읽기 · 종합) | 못 냄. Langfuse generation(`trace_url`)을 API로 읽어야 함 | 노드 단위만(`Supervisor`, `RAG 에이전트`, `회로 읽기` 등). LLM 호출 단위는 `analysis_events`에 없음. 11-11 병합된 `backend/services/service_trace.py`가 서비스 분석에 호출별 Langfuse 추적(모델 · 토큰 · 비용 · 시간, 본문 제외)을 붙이므로 그것이 켜져 있으면 Langfuse에서 호출 단위를 읽을 수 있다(실제로 LLM 호출 span이 생기는지, 배포본이 이 코드인지는 확인하지 못함) | LLM 호출은 LangChain 콜백이 아니라 `llm.chat`이라 `AnalysisTimings`에 안 잡힌다 |
| 판정 코드 | 못 냄 | `대체 부품 판정` 노드와 `specs` · `find` 도구 칸 | `품번·판 확인` 노드도 칸이 있다 |
| 승인 대기 | 해당 없음 | 칸 없음. DB 시각으로 계산(아래 4) | 사람이 기다린 시간이라 자동 스크립트로는 못 잰다 |

`AnalysisTimings`(`backend/services/langfuse_prompts.py`)는 그래프 노드 이름 · 시간 · 상태만 모은다. `report()`가 덧붙이는 "건너뜀" 목록 `('plan','search','judge_read','judge','synth','check')`은 옛 영어 노드 이름이라, 지금 한국어 노드 이름에서는 `search`를 뺀 다섯이 늘 0ms 건너뜀 행으로 같이 저장된다. 이 칸들은 지금 의미가 없다.

`stages`는 API 응답에 나오지 않는다(`detail()`이 `events`를 만들지만 `result_dto`가 걸러 냄). DB(`sojafit_agent.analysis_events`)를 읽어야 한다.

## 4. 승인 대기(사람이 기다린 시간) 계산 계획

기다림이 둘이다.

1. 조건 질문(`requires_input`) → 재개: `runs.updated_at`은 재개 때 덮어써지므로 이력이 없다. `analysis_events`는 호출 한 번마다 한 행이고 `created_at`은 호출이 끝난 시각(연결이 autocommit이라 INSERT 시각)이다. 기다림 = 재개 행의 `created_at − elapsed_ms` − 앞 행의 `created_at`.
2. 완료 → 승인: `approvals.created_at` − 마지막 행의 `created_at`.

```sql
-- thread 하나의 서버 처리 시간과 사람 기다림 (읽기 전용 초안, 실행하지 않음)
SELECT version, status, elapsed_ms, created_at,
       created_at - (elapsed_ms * interval '1 millisecond')
         - lag(created_at) OVER (ORDER BY created_at) AS human_wait_before_this_call
FROM sojafit_agent.analysis_events WHERE thread_id = :thread ORDER BY created_at;
```

운영 DB 읽기는 이 작업에서 하지 않았다. 실사용 행이 몇 개인지, 승인까지 간 thread가 있는지 확인하지 못했다. 행이 없으면 계정 두 개로 사람이 직접 눌러 만든 몇 건을 근거로 쓰고, 표본 크기를 함께 적는다.

## 5. 후보 설계와 비용 견적

가격 근거: `backend/services/llm.py` `MODEL_RATES` Haiku 5.5 입력 0.0000001 · 출력 0.0000005 달러/토큰, Sonnet 5.5 입력 0.000002 · 출력 0.00001 [문서]. 서비스 예약 기본 단가 `ANALYSIS_PROMPT_RATE` 0.000003 · `ANALYSIS_COMPLETION_RATE` 0.000015는 표에 없는 모델에만 쓰인다. 호출당 평균은 8장 값에서 거꾸로 계산했다(질문당 비용 × 50 ÷ 호출 수): Supervisor 0.000175달러, 판정 읽기 0.00068달러, 문서 답 0.00040달러, 카드 읽기 0.00050달러(합이 0.047달러로 8장과 같음). 토큰 수는 따로 모으지 않았고 이 비용에서만 어림한다. rerank는 호출당 5,122토큰 평균 × 0.05달러/100만 = 0.00026달러(#28). Voyage 질문 임베딩 가격은 저장소에 없고 질문이 짧아 0.0001달러 미만으로 본다 [추정].

| 설계 | 모델 호출 | 어림 비용 (LLM + rerank) | 근거 | 낼 수 있는 단계 |
|---|---|---|---|---|
| A. 평가 실행기 v3 50문항 1세트, 현재 `jeongun`(읽기 1번) | 약 80번(Supervisor 50 · 회로 읽기 16 · 문서 답 13 · 카드 읽기 1) | 약 0.025 + 0.004 = 약 0.03달러. 3세트면 약 0.09달러 | 판정 읽기를 48번에서 16번으로 줄인 계산 [추정]. 읽기 입력이 같다고 가정 | 문항 전체 시간. 단계별은 코드 변경 뒤 |
| A′. 같은 설계를 3번 다수결로(배포본 `27a410d` 기본) | 약 112번 | 0.044 ~ 0.055 + 약 0.004 = 약 0.05 ~ 0.06달러 | 실측 6세트(4세트 + 병합 뒤 2세트)의 LLM 비용 | 같음 |
| B. 배포 API 10문항 × 3회(서비스 경로) | 1회에 약 30번 → 90번 [추정] | 3번 읽기 약 0.05달러, 1번 읽기 약 0.025달러 | 질문 종류별 평균 비용 × 구성(판정 4 · 찾기 2 · 정격 2 · 거절 2). 종류별 평균은 회의록 링크 표 | 서버 처리 시간(HTTP), DB `stages`, 승인 대기(자동 재개는 사람 대기 아님) |
| C. `retrieve()` 단계별 20문항(#28 다시) | LLM 0번, rerank 20번 | 약 0.005달러 | 20 × 0.00026 | 임베딩 · DB · 리랭킹 분리 |
| D. 승인 대기 | 0번(DB 읽기만) | 0달러 | SQL 4절 | 사람 기다림 |

주의:
- 예약 상한은 실제 청구와 다르다. 서비스는 호출 전에 입력 바이트 + 8192 + 출력 토큰으로 최대 비용을 예약하고 돌려주지 않는다. 한 분석의 상한은 0.50달러, 사용자 하루는 3달러와 100만 예약 토큰(`USER_DAILY_TOKENS`)이다. 호출 한 번이 1.5만 ~ 2.5만 토큰을 예약한다고 보면 설계 B의 90번은 한 계정의 하루 상한을 넘는다 [추정]. 계정을 나누거나 며칠에 걸치거나 5문항 × 3회로 줄여야 한다.
- 서비스 분석은 호출 간격 2초 제한(`ANALYSIS_MIN_INTERVAL_SECONDS`)이 있어 연달아 보낼 때 간격을 둔다.
- 설계 B의 문항 구성과 호출 수는 질문 종류별 평균에서 낸 어림이다. 실제 호출 수는 Langfuse 또는 `analysis_events` 행 수로 확인해야 한다.
- 8장 비용은 OpenRouter 가격 × Langfuse 토큰이고 실제 청구액과 대조하지 않았다.

권장: A(현재 코드 1세트)로 LLM 단계별을 내고, C로 검색을 쪼개고, D와 B의 서버 시간으로 승인 대기를 따로 적는다. 합 약 0.04달러 + 사람 시간.

## 6. 필요한 코드 변경 (목록만, 아직 하지 않음)

1. `run_graph.make_app`/`run_gate`: `AnalysisTimings()`를 콜백에 넣고 `analysis_timings()`로 감싼 뒤, retriever · specs · find를 서비스와 같이 `timed_tool`로 감싸(`memory_service.py` 292 ~ 304행 조립) `row['stages'] = timings.report()`를 결과 행에 쓴다. 서비스와 같은 칸 이름으로 나란히 볼 수 있다.
2. LLM 호출 단위 시간 · 토큰 · 비용(평가 실행기 쪽. 서비스 쪽은 `service_trace.py`가 생기면서 일부 해결 가능성이 있어 먼저 그것을 확인): `llm.chat`(또는 `node_chat`)에서 호출마다 `{노드, 모델, 초, 입력 · 출력 토큰, 공급자 보고 비용}`을 contextvar 목록에 쌓아 결과 행에 쓴다. 공급자 보고 비용은 이미 `budget.reconcile(usage.cost)`로 읽고 있다. 없으면 Langfuse API로 읽는 집계 스크립트를 `scripts/langfuse/`에 저장소 코드로 만들어야 한다(지금 8장 집계 스크립트는 남아 있지 않음).
3. `AnalysisTimings.report()`의 건너뜀 목록을 지금 노드 이름으로 고치거나 없앤다.
4. `retrieve()`를 임베딩 · DB · 리랭크로 쪼갠 시간을 서비스 경로에서도 내려면 `retrieve.py`에 단계 시간 반환(또는 로그)이 필요하다. 지금은 `run_retrieval_service.py`가 `retrieve()` 안쪽 함수를 따로 불러 잰다.
5. 배포 API 반복 측정: `http_smoke.py`는 v3-01 · v3-30 둘뿐이라 문항 목록 · 반복 횟수 인자와 승인 대기 시간을 일부러 넣는 옵션이 필요하다(또는 새 스크립트).
6. 승인 대기를 서비스가 직접 남기려면(선택) `analysis_events`에 질문 시각을 칸으로 두거나 `runs`에 상태 전이 시각 이력이 필요하다. DB 스키마 변경이라 이번 범위 밖이다.

## 7. 확인하지 못한 것

- 운영 DB의 `analysis_events` · `approvals` 실제 행(읽지 않음).
- Langfuse API(키 파일을 읽지 않아 조회하지 않음). 8장 집계는 저장소 밖에서 한 것을 그대로 믿었고, 옮긴 `stage_costs_*` 안의 호출 수 · 비용이 요약 JSON과 같은 것까지만 대조했다.
- 지금 코드(1번 읽기)의 실제 단계별 값, 토큰 수. 위 견적은 3번 읽기 시절 값에서 줄인 어림이다.
- Voyage 가격표 원문과 임베딩 단가.
