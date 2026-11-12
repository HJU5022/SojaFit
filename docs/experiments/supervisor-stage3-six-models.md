# 수퍼바이저 6종 3차 공동 평가 사전등록

- 상태: 이력
- 기준일: 2026-11-12 (등록 2026-11-05, 3차 결과를 보기 전에 조건 고정)
- 기준 커밋: 6707002
- 정본 여부: 정본(3차 실험의 조건·지표·예산 계획값). 결과의 정본은 [supervisor-stage3-results.md](../research/supervisor-stage3-results.md)와 `evals/results/supervisor/2026-11-05-*`
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [supervisor-stage2-six-models.md](supervisor-stage2-six-models.md), [supervisor-model-comparison.md](supervisor-model-comparison.md), 등록 번호 #33 [preregister.md](../../evals/guides/preregister.md)(`:513`)

서비스가 지금 쓰는 모델: Supervisor는 `anthropic/claude-haiku-5.5`(ADR 0017), 채점은 `openai/gpt-6-luna`다(`backend/services/langfuse_prompts.py:33`, [SPEC.md](../../SPEC.md) 2절). 이번 결과로 운영 모델을 자동 변경하지 않는다.

등록 번호는 #33이다(이전 문서의 `#36`은 오기. `preregister.md:538`의 #36은 채점기 기준선).

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 같은 동결 문항에서 여섯 후보의 3차 결과와 1·2차 대비 변화, 형식 성공과 라우팅 일관성을 분리해 볼 수 있는가. 2차에서 `typesafe/jev-1.14`는 형식상 유효 결정 70/70이었으나 스스로 `out_of_scope`로 분류한 6건 중 4건의 다음 동작이 `refuse`가 아니었다 | 2차 결과 문서 |
| 모델 | 2차와 같은 6종 | |
| 규모 | 70문항 × 6모델 × `run_index=3` = 최대 420 planned outputs. 1·2차 원시 행은 3차 점수 분모에 섞지 않는다 | |
| 결과 | [supervisor-stage3-results.md](../research/supervisor-stage3-results.md) | |
| 원시 | 5종 `evals/results/supervisor/2026-11-05-stage3-five-v1/`, Jev `evals/results/supervisor/2026-11-05-jev-stage3-v1/`, 비교 `evals/results/supervisor/2026-11-05-stage3-comparison-v1/` | |

범위 밖: 기존 Luna 선정 자동 변경, Jev 프롬프트·출력 변환 수정, 평가셋·gold 수정, 새 모델·judge·검색 호출, 비관련 35문항의 답변 적절성 정답률 주장.

## 2. 조건

| 항목 | 규칙 |
|---|---|
| 평가셋 | `evals/FROZEN.json`과 v2 SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9` 확인. 새 결과 폴더 manifest의 모델·문항·회차·5종 prompt/code 해시·Jev typed question 계약 해시 확인 |
| 고정 | 5종은 기존 `SYSTEM_PROMPT`·JSON schema·출력 상한 256과 모델별 호출 인자(일반 후보 `temperature=0`, Haiku는 temperature 생략, Luna는 `max_completion_tokens`). Jev는 기존 typed question 계약. ZDR·`data_collection=deny`·fallback 금지·호출당 timeout 45초. 프롬프트·변환·모델 버전을 바꾸면 같은 조건의 반복이 아니라 새 등록 |
| 코드 차이 | Jev 실행기의 `NaN`·무한대 입력 차단과 보고 비용 초과 후 중단은 2차 측정 뒤 추가됐다. 1·2차와 비교할 때 이 차이를 명시하고, 비용·provider 중단이 생긴 문항은 품질 변화로 해석하지 않는다 |
| Jev 코드 해시 | 준비 시점 `OSC` commit `500213f`의 `evals/runners/run_supervisor_jev.py`를 LF로 정규화한 SHA-256 `291a3367856d5650b50925ae649254330fd230b766d1751ddb03f899b08a5e1f`. Jev manifest는 이 해시를 자동 검사하지 않으므로 live 실행 직전에 수동 대조하고 다르면 실행하지 않는다 |
| smoke | 각 모델의 현재 catalog ZDR 노출, provider policy, 실제 model/provider를 다시 확인. 이전 회차 smoke로 이번 회차 provider를 확정하지 않음 |
| 중단 | 호출이 3번 연속 실패, policy/model/provider 불일치, 시간·호출·비용 관리값 도달 시 해당 모델의 추가 호출 중단. 문항별 형식 실패는 오류 행으로 기록 |
| 결과 격리 | 위 원시 폴더에 새로 저장. 1·2차 원시 결과와 이번 manifest를 덮어쓰지 않음. 문항별 행에 원문 입력·raw response·비밀값·gold를 넣지 않음 |

## 3. 채점 규칙

| 항목 | 규칙 |
|---|---|
| 분모 | 70문항 전부 시도. `Question Type Accuracy`·`Macro-F1`은 gold가 있는 관련 35문항만, 실패는 오답. 비관련 35문항은 `unscored`. gold·`expected`·`why`·`gold_chunks`는 모델에 보내지 않음 |
| 라우팅 일관성 | 모델이 `question_type=out_of_scope`로 예측한 유효 행을 분모로, 그중 `next_action≠refuse`를 `Inconsistent Action`으로 센다. 분모 0이면 `Not Applicable`. 모델 내부 출력의 일관성이며 사람 정답과 대조한 범위 밖 탐지율이 아니다. 2차 Jev 4/6은 참고값이고 3차 점수에 섞지 않는다 |
| 3회 일치 | 1·2·3차에서 같은 문항 ID가 모두 유효한 경우에만 `Three-Run Exact Agreement`, `Question Type Flip Rate`, `Next Action Flip Rate`를 계산한다. 각 지표에 완전한 3행을 가진 문항 수와 빠진 문항 수를 함께 표시. 오류·미실행을 일치·불일치로 환산하지 않음 |
| 운영 지표 | `Completion Rate`, `Schema Valid Rate`, `Raw Calls`, 오류 종류·수, `Reported Cost Sum`, `Budget-Accounted Cost`, 문항별 p50·p95 Latency. 5종과 Jev의 비용·schema 계약 차이와 미보고 usage를 별도 표시 |
| 해석 | 같은 70문항의 세 번째 측정이라 독립 평가셋 일반화 근거가 아니다. 순위는 유형 정답률만이 아니라 라우팅 오류·형식 실패·비용·지연·3회 안정성을 함께 보고 설명한다 |

## 4. 예산 (계획값, 실제 지출이 아님)

2차와 같다. 모델당 70 planned outputs, 형식 재시도 최대 2회, 최대 210 raw calls, 본 실행 최대 7,200초, smoke는 문항 1건과 재시도 최대 2회. 상한 도달 뒤 자동 증액·재실행하지 않는다. 실행 직전 catalog 가격과 첫 문항 예약액을 재확인하고 부족하면 호출하지 않는다. Jev `--max-usd`는 실제 청구액의 절대 상한이 아니며, 보고 비용 초과 행은 저장하고 `budget_exceeded`로 멈춘다.

| 모델 | smoke 계획값 USD | 본 실행 계획값 USD |
|---|---:|---:|
| `anthropic/claude-haiku-5.5` | 0.004 | 0.10 |
| `openai/gpt-6-luna` | 0.004 | 0.10 |
| `deepseek/deepseek-v4.1-flash` | 0.002 | 0.07 |
| `meta/muse-glimmer-30b` | 0.011 | 0.30 |
| `cohere/command-a-plus` | 0.011 | 0.30 |
| `typesafe/jev-1.14` | 0.001 | 0.01 |
| 합계 | 0.033 | 0.88 (전체 0.913) |

## 5. 실행 명령

```bash
# 5종: <Model ID>와 금액은 4절 표의 값. smoke 통과 모델만 run 실행
uv run --no-sync python -m evals.runners.run_supervisor_models smoke evals/results/supervisor/2026-11-05-stage3-five-v1 --model <Model ID> --max-usd <smoke 계획값> --max-seconds 60 --max-tokens 256 --confirm-live
uv run --no-sync python -m evals.runners.run_supervisor_models run evals/results/supervisor/2026-11-05-stage3-five-v1 --model <Model ID> --run-index 3 --max-usd <본 실행 계획값> --max-seconds 7200 --max-tokens 256 --confirm-live
# Jev
uv run --no-sync python -m evals.runners.run_supervisor_jev smoke evals/results/supervisor/2026-11-05-jev-stage3-v1 --max-usd 0.001 --timeout 45 --confirm-live
uv run --no-sync python -m evals.runners.run_supervisor_jev run evals/results/supervisor/2026-11-05-jev-stage3-v1 --max-usd 0.01 --timeout 45 --max-seconds 7200 --confirm-live
```

`--confirm-live`는 유료 호출이다. 실행 직전에 catalog·ZDR·가격·manifest 해시를 다시 검사한다.

## 6. 수용 기준

| 조건 | 기대 |
|---|---|
| 동결 v2와 새 manifest | 5종 각각 `run_index=3` 70건, Jev 70건이 중복 없이 존재, 합계 420건 |
| API 없는 준비의 plan·단위 테스트 | 유료 호출 0회, 1·2차 원시 행 불변 |
| 한 모델의 `out_of_scope` 예측과 다음 동작 집계 | 범위 밖 예측 수와 그중 `refuse` 외 동작 수·문항 ID를 별도 보고하고 `Schema Valid Rate`를 고쳐 쓰지 않음 |
| 1·2·3차 행의 같은 문항 ID 짝짓기 | 3회 모두 유효한 문항만 일치·flip 지표의 분모, 누락·실패는 별도 수 |
| ZDR·model/provider·manifest·Jev 해시·가격·예산 불일치 | 추가 호출 없이 중단하고 이유 기록. Jev 한 job에서 보고 비용이 계획값을 넘으면 그 행을 저장하고 추가 job 중단 |

## 7. 한계

- 결과표 양식은 이 문서에 두지 않았다(실측값은 결과 문서에 있다).
- 사전 등록 작성 당시 3차 API 호출과 결과는 없었다.
