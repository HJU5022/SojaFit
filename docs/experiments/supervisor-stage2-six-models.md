# 수퍼바이저 6종 2차 공동 평가 사전 등록

- 상태: 이력
- 기준일: 2026-11-12 (등록 2026-11-05, API 호출 전 조건 고정)
- 기준 커밋: 6707002
- 정본 여부: 정본(2차 실험의 조건·지표·예산 계획값). 결과의 정본은 [supervisor-stage2-results.md](../research/supervisor-stage2-results.md)와 `evals/results/supervisor/2026-11-05-*`
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [supervisor-model-comparison.md](supervisor-model-comparison.md), [supervisor-stage3-six-models.md](supervisor-stage3-six-models.md), 등록 번호 #32 [preregister.md](../../evals/guides/preregister.md)(`:502`)

서비스가 지금 쓰는 모델: Supervisor는 `anthropic/claude-haiku-5.5`(ADR 0017), 채점은 `openai/gpt-6-luna`다(`backend/services/langfuse_prompts.py:33`, [SPEC.md](../../SPEC.md) 2절). 이 실험은 서비스 모델을 바꾸지 않는다.

등록 번호: 실행 전 로컬 기록은 `#29`였으나 `main`의 기존 `#29`와 중복돼 `#32`로 구분했다. 대상·지표·중단 조건·기대값은 번호 정정으로 바뀌지 않았다. `main`의 `#30`은 Luna·Haiku 두 모델의 재측정 프로토콜이며 이 6종 실행으로 대체하지 않는다. 원격 커밋 시각만으로 작성 순서를 독립 증명할 수는 없다.

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 같은 동결 70문항을 6종에 2차로 실행하면 유효 결정 비율, 비용, 지연이 1차와 어떻게 달라지는가 | |
| 모델 | `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus`, `typesafe/jev-1.14` | |
| 규모 | 6모델 × 70문항 × `run_index=2` = 최대 420 planned outputs. 1차 70행을 2차 결과로 재사용하지 않는다 | |
| 결과 | [supervisor-stage2-results.md](../research/supervisor-stage2-results.md) | |
| 원시 | 5종 `evals/results/supervisor/2026-11-05-stage2-five-v1/`, Jev `evals/results/supervisor/2026-11-05-jev-stage2-v1/`, 비교 `evals/results/supervisor/2026-11-05-stage2-comparison-v1/` | |

## 2. 가설과 범위

- Jev는 Decisions API를 써서 다른 5종과 출력 방식이 다르다. 1차 Jev 값은 이미 알려져 있고(아래 5절) 2차 실행도 독립 평가셋 성능을 입증하지 않는다.
- 범위 밖: 현재 `openai/gpt-6-luna` 선정 결론 변경, Jev-Luna cascade, confidence threshold 적용(1차에서 관찰한 Jev confidence 0.60을 자동 정책으로 쓰지 않음), 검색·임베딩 평가, 3차 반복, 새 gold 작성.

## 3. 조건

| 항목 | 규칙 |
|---|---|
| 평가셋 | `evals/dataset_v2.jsonl`, SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`를 `evals/FROZEN.json`과 실행 전 대조 |
| 채점 | gold가 있는 35문항만 Accuracy·Macro-F1. 나머지 35문항은 `unscored`. gold·`expected`·`why`·`gold_chunks`는 모델에 보내지 않음 |
| 출력 계약 | 5종은 Chat Completions JSON. Jev는 typed answer 5개를 `question_type`, `required_evidence`, `next_action`, `reason_code`로 변환. `Schema Valid Rate`는 다음 노드가 읽을 수 있는 결정의 비율이며 JSON 생성 능력과 같은 지표가 아니다 |
| 실행 | 두 실행기를 새 결과 폴더에 plan하고 manifest의 model·dataset·contract·`run_index`를 확인. 5종 manifest에 다른 회차도 있으므로 `--run-index 2`로 제한 |
| 개인정보 | 모델별 ZDR, `data_collection=deny`, fallback 금지, 실제 model·provider를 smoke에서 확인. Jev snapshot은 `typesafe/jev-1.14-YYYYMMDD` 형식의 같은 1.14만 허용 |
| 중단 | 호출이 지속적으로 실패하는 모델, 비용·시간·호출 상한, privacy 검증 실패 시 해당 모델 중단. 문항별 schema 실패는 행에 기록하고 계속 |
| 보관 | 새 run ID. 1차 폴더(`evals/results/supervisor/2026-11-04-stage1-v1/`, `evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/`)를 덮어쓰지 않음. 원문 입력·raw response·비밀값은 결과 파일에 넣지 않음 |
| 보고 지표 | `Question Type Accuracy`, `Macro-F1`, `Completion Rate`, `Schema Valid Rate`, `Raw Calls`, `Reported Cost Sum` 또는 `Actual Total Cost`, `Budget-Accounted Cost`, `p50 Latency`, `p95 Latency`, 오류 유형. 1차와 2차를 별도 열로, 정의가 다른 비용 필드는 합치지 않음 |

## 4. 예산 (계획값, 실제 지출이 아님)

모델당 70 planned outputs, schema 재시도 최대 2회, raw call 최대 210회, 실행 시간 최대 7,200초, 호출당 timeout 45초. 합계 본 실행 $0.88, smoke $0.033, 전체 $0.913.

| 모델 | 본 실행 상한 USD | 첫 호출 예약액 USD | 적용 smoke 상한 USD |
|---|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 0.10 | 0.001203 | 0.004 |
| `openai/gpt-6-luna` | 0.10 | 0.001203 | 0.004 |
| `deepseek/deepseek-v4.1-flash` | 0.07 | 0.00061175 | 0.002 |
| `meta/muse-glimmer-30b` | 0.30 | 0.0035322 | 0.011 |
| `cohere/command-a-plus` | 0.30 | 0.003609 | 0.011 |
| `typesafe/jev-1.14` | 0.01 | 별도 Decisions 예약식 | 0.001 |

- 첫 호출 예약액은 첫 질문을 최대 재시도까지 보낼 때 호출 전에 잡는 비용이다. 기존 smoke 상한 $0.001이 일부 모델의 첫 호출 예약액보다 작아 유료 호출 전에 위 smoke 상한으로 정정했다.
- Jev `--max-usd`는 호출 전 입력 비용 추정으로 다음 job 허용을 정하므로 실제 비용이 추정보다 큰 마지막 job은 계획값을 넘을 수 있다. 실제 청구액의 절대 상한이 아니다. 이후 실행 코드는 보고 비용이 초과하면 해당 행을 저장하고 `budget_exceeded`로 멈추며 `NaN`·무한대 인자를 호출 전에 거부한다. 이 보완을 적용해 2차를 다시 측정하지는 않았다.

## 5. 1차 참고값

`typesafe/jev-1.14`: Question Type Accuracy 33/35, Macro-F1 0.947222, Completion Rate 70/70, Schema Valid Rate 70/70, Actual Total Cost $0.002689092, p95 Latency 0.593초. 기존 5종의 1차 수치는 [stage1_summary.json](../../evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json), Jev는 `evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/summary.json`을 따른다. 2차 보고 때 모델별 1차와 2차의 정오 변화 문항 ID를 함께 기록한다.

## 6. 수용 기준

| 조건 | 기대 |
|---|---|
| 동결 평가셋과 새 manifest의 job 계수 | 6종 각각 70건의 `run_index=2` 대상, 중복 ID 없음 |
| Jev 2차 행 집계 | 2차 행만 70건 분모와 gold 35건 분모에 사용 |
| endpoint·privacy·manifest 불일치 또는 상한 도달 | 추가 호출 없이 중단하고 이유 기록 |
| 한 문항 schema 오류가 2회 재시도 후에도 실패 | 오류 행으로 기록하고 다음 문항 진행 |
| 2차 비교표 | 1차/2차, 70건 전체/35건 gold, 보고 비용/예약 비용, Jev API 차이를 구별 가능 |

## 7. 한계

- 결과표 양식은 이 문서에 두지 않았다(실측값은 결과 문서에 있다).
- 같은 70문항의 두 번째 실행이라 독립 평가셋 일반화 근거가 아니다.
- 실제 청구액은 외부 청구 근거가 없으면 확정하지 않는다.
