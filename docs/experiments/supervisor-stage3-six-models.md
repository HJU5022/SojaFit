# 수퍼바이저 6종 3차 공동 평가 사전 등록

상태: **사전 등록 조건 고정** · 등록일: 2026-11-05 · 등록 번호: `#36`

이 문서는 3차 결과를 보기 전에 실행·채점 조건을 고정한다. 1·2차 결과는 이미 알려진 값이며 새 문항의 성능을 뜻하지 않는다. 사전 등록 작성 당시 3차 API 호출과 결과는 없었다.

## Why

- **대상**: SojaFit 수퍼바이저 모델의 질문 분류·다음 동작·비용을 검토하는 평가 담당자.
- **문제**: 2차에서 `typesafe/jev-1.14`는 형식상 유효 결정 70/70이었지만, 스스로 `out_of_scope`로 분류한 6건 중 4건의 다음 동작이 `refuse`가 아니었다. `--max-usd`도 실제 청구액의 절대 상한은 아니다.
- **측정 목적**: 같은 동결 문항에서 여섯 후보의 3차 결과와 1·2차 대비 변화, 형식 성공과 라우팅 일관성을 분리해 기록한다.

## Goal

- **모델**: `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus`, `typesafe/jev-1.14`.
- **규모**: 동결 `evals/dataset_v2.jsonl` 70문항 × 여섯 모델 × `run_index=3` 한 번 = 최대 420 planned outputs. 1·2차 원시 행은 3차 점수의 분모에 섞지 않는다.
- **성공 기준**: 6종 각각 70문항의 완료 또는 중단 이유가 남고, 문항별 결과·오류·비용 근거·3차 전용 집계와 1~3차의 같은 문항 대조가 생성된다. 실패 문항도 결과 행으로 남긴다.
- **Out of Scope**: 기존 Luna 선정 자동 변경, Jev 프롬프트 또는 출력 변환 수정, 평가셋·gold 수정, 새로운 모델·judge·검색 호출, 35개 비관련 문항의 답변 적절성 정답률 주장.

## What

1. `evals/FROZEN.json`과 v2 SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`를 확인한다. 새 결과 폴더의 manifest에서 모델·문항·회차·5종 prompt/code hash·Jev typed question 계약 hash를 확인한다. Jev manifest에는 실행기 파일 hash가 없으므로 아래에 고정한 코드를 별도로 대조한다.
2. 각 모델의 현재 catalog ZDR 노출, provider policy, 실제 model/provider를 smoke에서 다시 확인한다. 이전 회차 smoke로 이번 회차의 provider를 자동 확정하지 않는다.
3. 모델별로 `run_index=3`의 70문항만 실행한다. 호출 자체가 3번 연속 실패한 모델, policy/model/provider 불일치, 시간·호출·비용 관리값 도달 시 그 모델의 추가 호출을 멈춘다. 문항별 형식 실패는 오류 행으로 남기고 다음 문항으로 간다.
4. 원시 행에서 3차 전용 지표를 계산하고 1·2차 원시 행과 같은 문항 ID로 대조한다. 5종 실행기의 기본 summary는 3회 계획 분모를 쓰므로 3차 70문항 점수로 그대로 인용하지 않는다.

## How

- **고정 조건**: v2 입력 전체, 기존 5종의 `SYSTEM_PROMPT`·JSON schema·출력 상한 256과 모델별 기존 호출 인자(일반 후보는 `temperature=0`, Haiku는 temperature 생략, Luna는 `max_completion_tokens` 사용), Jev의 기존 typed question 계약, ZDR·`data_collection=deny`·fallback 금지, 호출당 timeout 45초를 유지한다. Jev와 5종의 API·출력 계약 차이를 표에 표시한다. 프롬프트·변환·모델 버전을 바꾸면 이 3차와 같은 조건의 반복으로 취급하지 않고 새 등록을 만든다.
- **코드 차이**: Jev 실행기의 `NaN`·무한대 입력 차단과 보고 비용 초과 후 중단은 2차 측정 뒤 추가됐다. 질문 계약과 typed answer 변환은 그대로지만 실행 안전장치의 버전은 다르므로 1·2차와 비교할 때 이 차이를 명시한다. 비용 또는 provider 중단이 생긴 문항은 품질 변화로 해석하지 않는다.
- **채점 분모**: 70문항 전부 시도한다. `Question Type Accuracy`와 `Question Type Macro-F1`은 `question_type` gold가 있는 관련 35문항만 채점하며 실패는 오답이다. 나머지 비관련 35문항은 유형 정답률에서 `unscored`로 둔다. gold·`expected`·`why`·`gold_chunks`는 모델에 전송하지 않는다.
- **라우팅 일관성**: 여섯 모델 모두에서 `question_type=out_of_scope`라고 **예측한** 유효 행을 분모로, 그중 `next_action=refuse`가 아닌 행을 `Inconsistent Action`으로 센다. 분모가 0이면 비율은 `Not Applicable`이다. 이 값은 모델 내부 출력의 일관성이지 사람 정답과 대조한 범위 밖 탐지율이 아니다. 기존 2차 Jev 4/6 오류는 이미 본 참고값이며 3차 점수에 섞지 않는다.
- **3회 일치**: 각 모델의 1·2·3차에서 같은 문항 ID가 모두 유효한 경우에만 결정 전체의 `Three-Run Exact Agreement`, `Question Type Flip Rate`, `Next Action Flip Rate`를 계산한다. 각 지표에 완전한 3행을 가진 문항 수와 빠진 문항 수를 함께 표시한다. 오류·미실행을 일치나 불일치로 임의 환산하지 않는다.
- **운영 지표**: `Completion Rate`, `Schema Valid Rate`, `Raw Calls`, 오류 종류·수, `Reported Cost Sum`, `Budget-Accounted Cost`, 문항별 p50·p95 Latency를 모델별로 기록한다. 5종과 Jev의 비용·schema 계약 차이와 미보고 usage를 별도로 표시한다.
- **비용 관리 계획값**: 2차와 같은 본 실행 모델별 US$0.10 · 0.10 · 0.07 · 0.30 · 0.30 · 0.01(위 순서), 합계 US$0.88. smoke 계획값은 US$0.004 · 0.004 · 0.002 · 0.011 · 0.011 · 0.001, 합계 US$0.033. 합계 계획값 US$0.913이다. 실행 직전 catalog 가격과 첫 문항 예약액을 재확인하고 부족하면 호출하지 않고 계획을 다시 검토한다. Jev `--max-usd`는 입력 비용 추정에 근거한 다음 job 차단값으로, 실제 청구액의 절대 상한이 아니다. 보고 비용 초과는 행을 저장하고 `budget_exceeded`로 멈춘다. 전체 실제 청구액은 외부 청구 근거 없이는 확정하지 않는다.

| Model ID | Smoke Planned Limit | Main Planned Limit |
|---|---:|---:|
| `anthropic/claude-haiku-5.5` | US$0.004 | US$0.10 |
| `openai/gpt-6-luna` | US$0.004 | US$0.10 |
| `deepseek/deepseek-v4.1-flash` | US$0.002 | US$0.07 |
| `meta/muse-glimmer-30b` | US$0.011 | US$0.30 |
| `cohere/command-a-plus` | US$0.011 | US$0.30 |
| `typesafe/jev-1.14` | US$0.001 | US$0.01 |

표 읽는 법: `Model ID`는 정확한 호출 대상 모델 ID, `Smoke Planned Limit`은 첫 문항의 모델·provider·형식 확인에 쓰는 비용 관리 계획값, `Main Planned Limit`은 70문항 실행에 쓰는 비용 관리 계획값이다. 두 값은 실제 청구액이나 절대 지출 보장이 아니다.

실행 명령은 준비 단계에서 **기록만** 한다. 5종은 위 표의 각 `Model ID`와 해당 금액을 넣어 `uv run --no-sync python -m evals.runners.run_supervisor_models smoke evals/results/supervisor/2026-11-05-stage3-five-v1 --model <Model ID> --max-usd <Smoke Planned Limit> --max-seconds 60 --max-tokens 256 --confirm-live`를 수행한 뒤, 통과한 모델만 `uv run --no-sync python -m evals.runners.run_supervisor_models run evals/results/supervisor/2026-11-05-stage3-five-v1 --model <Model ID> --run-index 3 --max-usd <Main Planned Limit> --max-seconds 7200 --max-tokens 256 --confirm-live`로 실행한다. Jev는 같은 순서로 `uv run --no-sync python -m evals.runners.run_supervisor_jev smoke evals/results/supervisor/2026-11-05-jev-stage3-v1 --max-usd 0.001 --timeout 45 --confirm-live`, `uv run --no-sync python -m evals.runners.run_supervisor_jev run evals/results/supervisor/2026-11-05-jev-stage3-v1 --max-usd 0.01 --timeout 45 --max-seconds 7200 --confirm-live`를 사용한다. 실제 실행 전 catalog·ZDR·가격·manifest hash를 다시 검사한다.
- **시간·호출 계획값**: 모델별 최대 70 planned outputs, 형식 재시도 최대 2회, 최대 210 raw calls, 본 실행 최대 7,200초. smoke는 문항 1건과 재시도 최대 2회다. 상한 도달 후 자동 증액·재실행하지 않는다.
- **결과 격리**: 5종은 `evals/results/supervisor/2026-11-05-stage3-five-v1/`, Jev는 `evals/results/supervisor/2026-11-05-jev-stage3-v1/`에 새로 저장한다. 1·2차 원시 결과와 이번 manifest를 덮어쓰지 않는다. 문항별 행에는 원문 입력·raw response·비밀값·gold를 넣지 않는다.
- **Jev 코드 고정**: 준비 시점 `OSC` commit `500213f`의 `evals/runners/run_supervisor_jev.py`를 LF 줄바꿈으로 정규화한 SHA-256은 `291a3367856d5650b50925ae649254330fd230b766d1751ddb03f899b08a5e1f`다. Jev manifest 자체는 이 hash를 자동 검사하지 않으므로 live 실행 직전에 수동 대조하고 다르면 실행하지 않는다.
- **해석**: 같은 70문항의 세 번째 측정이므로 독립 평가셋 일반화 근거가 아니다. 순위는 35문항 유형 정답률만이 아니라 라우팅 오류·형식 실패·비용·지연·3회 안정성을 함께 보고 설명한다. 이번 결과만으로 운영 모델을 자동 변경하지 않는다.

### 3차 결과표 양식

| Model ID | Completion Rate | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Inconsistent Action | Comparable Three-Run Cases | Three-Run Exact Agreement | Question Type Flip Rate | Next Action Flip Rate | Raw Calls | Budget-Accounted Cost | p95 Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `openai/gpt-6-luna` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `deepseek/deepseek-v4.1-flash` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `meta/muse-glimmer-30b` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `cohere/command-a-plus` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |
| `typesafe/jev-1.14` | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured | Not Measured |

표 읽는 법: `Model ID`는 정확한 모델 ID다. `Completion Rate`는 최종 성공·확정 실패 행 수 / 70, `Schema Valid Rate`는 형식상 유효한 결정 수 / 70, `Question Type Accuracy`는 gold 35문항의 유형 정답률, `Question Type Macro-F1`은 네 유형 F1의 동일 가중 평균이다. `Inconsistent Action`은 모델이 스스로 범위 밖이라고 예측한 행 중 거절하지 않은 수 / 그 예측 행 수다. `Comparable Three-Run Cases`는 같은 모델·문항의 1·2·3차가 모두 유효한 문항 수 / 70이다. `Three-Run Exact Agreement`는 그 비교 가능한 문항 중 세 결정 전체가 같은 비율이며, 두 `Flip Rate`는 같은 분모에서 질문 유형 또는 다음 동작이 달라진 비율이다. `Raw Calls`는 재시도 포함 호출 수, `Budget-Accounted Cost`는 보고 비용과 미보고 호출 예약액을 합친 관리값, `p95 Latency`는 문항 처리 시간의 95백분위수다. `Not Measured`는 아직 실행하지 않았다는 뜻이다.

## AC (Given-When-Then)

- **AC-01** GIVEN 동결 v2와 새 manifest WHEN 준비를 검사하면 THEN 5종 각각 `run_index=3` 70건, Jev `run_index=3` 70건이 중복 없이 존재하고 합계 420건이다.
- **AC-02** GIVEN API 없는 준비 WHEN plan·단위 테스트를 실행하면 THEN 유료 호출 0회이며 원시 1·2차 행은 바뀌지 않는다.
- **AC-03** GIVEN 한 모델의 `out_of_scope` 예측과 다음 동작 WHEN 3차 원시 행을 집계하면 THEN 범위 밖 예측 수와 그중 `refuse` 외 동작 수·문항 ID를 별도로 보고하고 `Schema Valid Rate`를 고쳐 쓰지 않는다.
- **AC-04** GIVEN 1·2·3차 행 WHEN 같은 문항 ID를 짝지으면 THEN 3회 모두 유효한 문항만 일치·flip 지표의 분모가 되며 누락·실패는 별도 수로 표시한다.
- **AC-05** GIVEN 유료 호출 조건 WHEN ZDR·model/provider·manifest·Jev 실행기 hash·가격·예산 관리값이 맞지 않으면 THEN 추가 호출 없이 중단하고 이유를 기록한다. Jev 한 job에서 실제 보고 비용이 계획값을 넘으면 그 행을 저장하고 추가 job을 중단한다.
