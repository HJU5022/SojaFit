# 수퍼바이저 2차 6종 공동 평가 사전 등록

상태: **실행 전 준비** · 등록일: 2026-11-05 · API 호출 전 조건 고정

등록 번호 정정: 실행 전 로컬 기록은 `#29`로 작성했으나, PR 준비 중 `main`의 기존 `#29`와 중복됨을 확인해 `#32`로 구분한다. 실험 대상·지표·중단 조건·기대값은 이 번호 정정으로 바꾸지 않는다. 이 문서는 2차 실행 전에 준비한 계약이며, 원격 커밋 시각만으로 작성 순서를 독립 증명할 수는 없다.

`main`의 기존 `#30`은 Luna·Haiku 두 모델의 별도 재측정 프로토콜이다. 이 6종 실행을 `#30`의 실행 결과로 대체하지 않는다.

## Why

- **대상**: SojaFit 수퍼바이저의 질문 분류·라우팅 후보를 비교하는 평가 담당자.
- **문제**: 기존 5종의 1차 결과와 `typesafe/jev-1.14`의 별도 1차 결과만으로는 같은 회차의 재측정값을 볼 수 없다. Jev는 Decisions API를 사용해 다른 5종과 출력 방식도 다르다.
- **측정 목적**: 6종을 동결 70문항에서 각각 한 번 더 실행해 동일 문항의 결과 변화, 유효 결정 비율, 비용과 지연시간을 나란히 기록한다. 1차 결과는 참고 열로만 둔다.

## Goal

- **대상 모델**: `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus`, `typesafe/jev-1.14`.
- **규모**: 6종 × 동결 `evals/dataset_v2.jsonl` 70문항 × 2차 1회 = 최대 420 planned outputs. 기존 5종 실행기의 `run_index=2`와 Jev 실행기의 `run_index=2`만 실행한다. 1차의 70행을 2차 결과로 재사용하지 않는다.
- **성공 기준**: 모델별 실행 완료 또는 명시적 provider stop, 2차의 문항별 행·집계·실패·비용 근거, 1차와 2차를 구분한 6종 비교표가 남는다.
- **Out of Scope**: 현재 `openai/gpt-6-luna` 선정 결론 변경, Jev-Luna cascade, confidence threshold 적용, 검색·임베딩 평가, 3차 반복, 새로운 gold 작성.

## What

1. `evals/FROZEN.json`과 데이터셋 SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`를 실행 전에 대조한다.
2. 두 실행기를 각각 새 결과 폴더에 `plan`하고, manifest의 model·dataset·contract·`run_index`를 확인한다. 5종 manifest에는 다른 회차도 계획돼 있으므로 실제 호출은 `--run-index 2`로 제한한다.
3. 각 모델의 ZDR, `data_collection=deny`, fallback 금지, actual model·provider를 smoke에서 확인한다. Jev의 응답 snapshot은 `typesafe/jev-1.14-YYYYMMDD` 형식의 같은 1.14만 허용한다.
4. 모델별 70건을 실행하고 failure도 행으로 남긴다. 호출 자체가 지속적으로 실패한 모델만 중단하며, 문항별 schema 실패는 행에 기록하고 다음 문항을 계속한다. 비용·시간·호출 상한이나 privacy 검증 실패 시 해당 모델을 중단한다.
5. 최종 표에는 1차와 2차를 별도 열로 표시하고, `Question Type Accuracy`, `Question Type Macro-F1`, `Completion Rate`, `Schema Valid Rate`, `Raw Calls`, `Reported Cost Sum` 또는 `Actual Total Cost`, `Budget-Accounted Cost`, `p50 Latency`, `p95 Latency`, 오류 유형을 출처와 함께 기록한다. cost 필드의 정의가 다르면 합산하거나 같은 명칭으로 바꾸지 않는다.

## How

- **입력·채점**: 같은 동결 70문항을 모두 실행한다. `question_type` gold가 있는 35문항만 Accuracy·Macro-F1에 넣고 나머지 35문항은 `unscored`로 표시한다. gold·`expected`·`why`·`gold_chunks`는 모델에 전송하지 않는다.
- **출력 계약**: 5종은 Chat Completions JSON, Jev는 5개의 typed answer를 기존 `question_type`, `required_evidence`, `next_action`, `reason_code`로 변환한다. `Schema Valid Rate`는 다음 노드가 읽을 수 있는 결정의 비율로 비교하며, 동일한 JSON 생성 능력의 지표로 해석하지 않는다.
- **비교 한계**: 두 API의 prompt·tokenization·provider가 다르다. 1차의 Jev 33/35와 Luna 35/35는 이미 본 값이다. 같은 70문항의 2차 실행도 독립 평가셋 성능을 입증하지 않으며, 현재 1차에서 관찰한 Jev confidence 0.60을 2차 비교의 자동 정책으로 사용하지 않는다.
- **예산 상한**: 본 테스트는 5종 모델별 US$0.10, US$0.10, US$0.07, US$0.30, US$0.30(위 모델 순서), Jev US$0.01로 합계 US$0.88. 최초 smoke 상한은 모델별 US$0.001이었으며, 유료 호출 전 발견한 예약액 불일치에 따라 아래 실행 전 정정값을 적용한다. 각 모델은 70 planned outputs, schema retry 최대 2회, raw call 최대 210회, 실행시간 최대 7,200초, 호출당 timeout 45초다. Jev는 가격·usage가 확인되지 않으면 실제 총 비용으로 표시하지 않는다. 이 상한은 실행 전 검토할 계획값이며 실제 지출이 아니다.

### 실행 전 정정 — smoke 비용 상한

2026-11-05 첫 유료 호출 전 공개 catalog의 현재 단가와 고정 첫 문항으로 계산했다. 기존 US$0.001은 일부 모델에서 첫 호출 예약액보다 작아 smoke가 호출 전 차단된다. 첫 호출 예약액의 최대 3회 schema 시도분을 초과하도록 모델별 smoke 상한만 정정한다. 본 테스트 상한과 다른 조건은 유지한다.

| Model ID | 첫 호출 예약액 | 적용 smoke 상한 |
|---|---:|---:|
| `anthropic/claude-haiku-5.5` | US$0.001203 | US$0.004 |
| `openai/gpt-6-luna` | US$0.001203 | US$0.004 |
| `deepseek/deepseek-v4.1-flash` | US$0.00061175 | US$0.002 |
| `meta/muse-glimmer-30b` | US$0.0035322 | US$0.011 |
| `cohere/command-a-plus` | US$0.003609 | US$0.011 |
| `typesafe/jev-1.14` | 별도 Decisions 예약식 | US$0.001 |

표 읽는 법: `Model ID`는 호출할 모델의 전체 이름이다. `첫 호출 예약액`은 첫 질문을 최대 재시도 횟수까지 보낼 때를 대비해 호출 전에 잡는 비용이며 실제 지출액이 아니다. `적용 smoke 상한`은 모델이 실제 호출되는지만 확인하는 시험에 허용한 최대 예산이다. Jev는 다른 5종과 API·예약식이 달라 첫 호출 예약액을 같은 방식으로 적지 않았다.

smoke 상한 합계 US$0.033, 본 테스트 포함 전체 계획 상한 US$0.913. 상한은 호출 전 보수 예약을 위한 값이며 실제 지출액이 아니다.
- **보관**: 새 run ID를 사용하고 1차의 `evals/results/supervisor/2026-11-04-stage1-v1/` 및 `2026-11-04-jev-stage1-ready-v1/`는 덮어쓰지 않는다. 각 행의 model ID, provider, run index, case ID, status, latency, usage, error type을 보존한다. 원문 입력·raw response·비밀값은 결과 파일에 넣지 않는다.
- **실행 경계**: 현재 단계는 로컬 plan·테스트까지만 한다. smoke와 본 테스트는 별도 지시를 받은 뒤 실행한다.
- **저장소 규칙 확인**: Jev의 Decisions POST와 모델 catalog 조회는 `backend/services/llm.py`를 통한다. 실행기의 manifest 정책·모델 snapshot·provider 확인은 모델 입력을 보내기 전과 응답마다 검사한다. 실제 유료 endpoint의 현재 가용성과 가격은 실행 직전 preflight에서 다시 확인한다.

### 2차 결과표 양식

아래 값은 모두 2차 실행 후 채운다. 1차 값은 별도 출처 열에 두고 2차 실측인 것처럼 복사하지 않는다. 실패·provider stop이면 숫자 `0` 대신 `Not Comparable` 또는 `Not Measured`와 사유를 적는다.

| Model ID | Completion Rate | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Raw Calls | Errors | Reported Cost | Budget-Accounted Cost | p50 Latency | p95 Latency |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `openai/gpt-6-luna` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `deepseek/deepseek-v4.1-flash` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `meta/muse-glimmer-30b` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `cohere/command-a-plus` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `typesafe/jev-1.14` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |

표 읽는 법: `Completion Rate`는 성공 또는 확정 실패가 기록된 문항 / 70, `Schema Valid Rate`는 유효 결정 / 70, `Question Type Accuracy`는 gold가 있는 35문항의 유형 정답률, `Question Type Macro-F1`은 유형별 F1의 동일 가중 평균이다. `Raw Calls`는 재시도 포함 API 호출 수, `Errors`는 최종 오류 종류·수다. `Reported Cost`는 provider가 보고한 비용, `Budget-Accounted Cost`는 보고 비용과 미보고 호출의 예약액을 합친 예산 관리값이다. `p50 Latency`는 문항별 처리 시간 중앙값, `p95 Latency`는 95백분위수다. 여기의 `Not Measured`는 이 실행 전 양식에서 아직 채우지 않은 값이지 실제 결과가 0이라는 뜻이 아니다. 실측값은 결과 문서에 기록한다.

1차 참고값: `typesafe/jev-1.14`의 Question Type Accuracy 33/35, Macro-F1 0.947222, Completion Rate 70/70, Schema Valid Rate 70/70, Actual Total Cost US$0.002689092, p95 Latency 0.593초. 기존 5종의 1차 수치는 아래 출처의 `stage1_summary.json`을 따른다. 2차 보고 시 각 모델의 1차와 2차 정오 변화 문항 ID도 함께 기록한다.

## AC (Given-When-Then)

- **AC-01** GIVEN 동결 평가셋과 새 manifest WHEN job을 세면 THEN 6종 각각 70건의 `run_index=2` 대상이 있고 중복 ID가 없다.
- **AC-02** GIVEN Jev의 2차 행 WHEN 집계하면 THEN 2차 행만 70건 분모와 gold 35건 분모에 사용하며 1차 행은 섞이지 않는다.
- **AC-03** GIVEN 모델의 endpoint·privacy·manifest가 불일치하거나 상한에 도달함 WHEN 실행 직전 검사하면 THEN 추가 호출 없이 중단하고 이유를 남긴다.
- **AC-04** GIVEN 한 문항의 schema 오류 WHEN 최대 2회 재시도해도 실패하면 THEN 해당 문항은 오류 행으로 기록하고 호출 가능한 모델의 다음 문항으로 진행한다.
- **AC-05** GIVEN 2차 비교표 WHEN 수치를 읽으면 THEN 1차/2차, 70건 전체 지표/35건 gold 지표, 실제 보고 비용/보수 예약 비용, Jev API 차이를 구별할 수 있다.

1차 출처: `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json`, `evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/summary.json`, `docs/research/jev-supervisor-evaluation-handoff.md`.
