# 수퍼바이저 모델 5종 비교 사후등록과 결과 (1차)

- 상태: 이력
- 기준일: 2026-11-12 (작성 2026-11-04, 후보별 실행과 결과 확인 뒤)
- 기준 커밋: 6707002
- 정본 여부: 정본(1차 실험의 실제 조건·변경·채점 범위·결과). 계약의 정본은 [supervisor-model-comparison.md](supervisor-model-comparison.md). 이 문서는 실행 전 사전 등록을 대신하지 않는다
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [supervisor-stage2-six-models.md](supervisor-stage2-six-models.md), [supervisor-stage3-six-models.md](supervisor-stage3-six-models.md), 재현 검증 사전 등록 #29 [preregister.md](../../evals/guides/preregister.md)

서비스가 지금 쓰는 모델: Supervisor는 `anthropic/claude-haiku-5.5`다(ADR 0017이 ADR 0014의 Sonnet을 바꿈; `backend/services/langfuse_prompts.py:33` `NODE_MODELS`, [SPEC.md](../../SPEC.md) 2절). 이 실험이 고른 `openai/gpt-6-luna`는 서비스에서 채점 모델로 쓰인다. 실험상 선정과 서비스 모델은 다르다.

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 대상 | 수퍼바이저(질문 유형·다음 경로 결정) 후보 5종, 동결 `evals/dataset_v2.jsonl` 70문항, 후보별 `run_index=1` | `stage1_summary.json` `scope` |
| 기록된 출력 | 계획 350 중 283 | 같은 파일 `scope.recorded_outputs` |
| 실험상 선정 | `openai/gpt-6-luna`(차순위 `anthropic/claude-haiku-5.5`) | 같은 파일 `selected_model_id`, 7절 |
| 서비스 적용 | Supervisor = Haiku | ADR 0017 |
| 원시 | `evals/results/supervisor/2026-11-04-stage1-v1/{stage1_summary,provider_evidence}.json`, 후보별 `rows_*.json` | |

선정 대상이 아닌 것: 최종 답변 생성 모델, judge 모델, 전체 그래프 구조, 서브에이전트 수.

## 2. 조건

| 항목 | 값 |
|---|---|
| 평가셋 | `evals/dataset_v2.jsonl`, SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`(`evals/FROZEN.json`과 일치) |
| 문항 | 70건(관련 35, 비관련 35) |
| 모델 입력 | 실제 사용자 입력과 고정 system prompt. `question_type` gold, `expected`, `why`, `gold_chunks`, 모범 답변은 전달하지 않음 |
| 출력 계약 | `question_type`, `required_evidence`, `next_action`, `reason_code`. JSON schema 불통과는 `ValidationError`로 기록, 문항당 최대 2회 재시도, SDK 자동 재시도 없음 |
| 개인정보 | OpenRouter ZDR endpoint만, `data_collection=deny`, `require_parameters=true`, provider fallback 금지 |
| 실제 provider | Haiku = Google, Luna = Azure, DeepSeek = Morph, Muse = DeepInfra, Cohere = Cohere |
| 호출 인자 | Haiku: `temperature` 없이 `max_tokens`. Luna: `temperature` 없이 `max_completion_tokens`. 나머지: `temperature=0`, `max_tokens` |
| 저장 | raw prompt·raw response·예외 원문은 결과에 저장하지 않음 |

실행 중 확인·변경:
1. 처음 manifest는 최대 3회 실행을 지원했으나 선정에는 70문항 1회만 썼다.
2. Haiku와 Luna의 최초 smoke `NotFoundError`는 모델 부재가 아니라 endpoint generation parameter와 `require_parameters=true`의 충돌이었다. parameter를 endpoint 계약에 맞춘 뒤 다시 확인했다.
3. `deepseek/deepseek-v4.1-flash`는 `RateLimitError` 3회 연속으로 3/70에서 provider stop됐다.
4. schema 불일치는 호출 실패가 아니라 해당 문항의 output 실패로 기록했다.
5. pairwise judge, robustness, end-to-end, 추가 반복은 선정 수치에 포함하지 않았다.

## 3. 채점 범위

- `Schema Valid Rate`: 후보별 planned 70문항 전체가 분모. 실패·누락을 빼지 않는다.
- `Question Type Accuracy`, `Macro-F1`: `question_type` gold가 있는 35문항만.
- `required_evidence`, `next_action`, 비관련 35문항의 route는 사람 합의 gold가 없어 점수화하지 않았다.
- provider 중단 후보는 0점이 아니라 `Not Comparable`.
- 비용: `Raw Calls`는 최초 호출과 schema 재시도를 포함한 API 호출 수. `Reported Cost Sum`은 provider가 `usage.cost`를 반환한 호출만 합산. `Budget-Accounted Cost`는 미보고 호출에 보수적 예약 비용을 더한 값. 어느 쪽도 실제 총 청구액이라고 표시하지 않는다. p50·p95는 output별 wall-clock.
- 선정 순서(지표를 합산 점수로 합치지 않음): (1) 70문항 실행 완료 (2) `Schema Valid Rate` (3) `Question Type Accuracy`·`Macro-F1` (4) `Raw Calls`·`Budget-Accounted Cost` (5) 품질 조건을 통과한 후보 사이의 latency.

## 4. 결과

판정 출처: 자동 집계(결정적 채점기, 사람·LLM 판정 없음). 값은 `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json`.

| 모델 | provider | 기록 출력 | schema 유효 | `Schema Valid Rate` | 유형 정확도(35) | Macro-F1 | Raw Calls | `Budget-Accounted Cost` | p50 | p95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | Google | 70 | 48 | 0.686 | 22/35 = 0.629 | 0.724 | 121 | $0.0314 | 2.37초 | 7.79초 |
| `openai/gpt-6-luna` | Azure | 70 | 66 | 0.943 | 35/35 = 1.0 | 1.0 | 83 | $0.0135 | 2.80초 | 12.86초 |
| `deepseek/deepseek-v4.1-flash` | Morph | 3 | 0 | 없음(`provider_stopped`, `Not Comparable`) | 없음 | 없음 | 3 | $0.0018 | 0.30초 | 1.20초 |
| `meta/muse-glimmer-30b` | DeepInfra | 70 | 1 | 0.014 | 1/35 = 0.029 | 0.071 | 205 | $0.0824 | 5.05초 | 8.60초 |
| `cohere/command-a-plus` | Cohere | 70 | 20 | 0.286 | 8/35 = 0.229 | 0.356 | 177 | $0.0875 | 4.41초 | 6.07초 |

오류: Haiku `ValidationError` 22, Luna `ValidationError` 3·`APITimeoutError` 1, DeepSeek `RateLimitError` 3, Muse `ValidationError` 67·`APITimeoutError` 2, Cohere `ValidationError` 50.

## 5. 결정

- 실험상 선정: `openai/gpt-6-luna`. 완료 후보 중 schema 안정성과 질문 유형 분류가 가장 높았고 Haiku보다 raw call과 budget-accounted cost가 낮았다. p50·p95 latency는 Haiku보다 느렸으나 수퍼바이저에서는 구조화 출력과 route 정확도를 우선했다.
- `deepseek/deepseek-v4.1-flash`는 품질 열위가 아니라 provider stop 때문에 선택할 수 없는 상태로 남았다.
- 서비스 적용은 이 실험과 별개다. Supervisor는 Haiku로 정해졌다(ADR 0017, 사전 등록 #46, #47).

## 6. 한계

- 원 실험에는 별도 번호의 실행 전 사전 등록이 없었다.
- gold가 없는 필드는 객관 점수로 비교하지 못했다.
- 한 번 실행한 결과라 반복 안정성을 측정하지 않았다.
- supervisor만의 결과이며 end-to-end 서비스 성공률을 입증하지 않는다.
- 집계 JSON은 결과 요약이며 문항별 원시 증거가 아니다. 문항별 값은 `rows_*.json`에 있다. OpenRouter 사용 내역이나 provider 서명 로그가 없어 API 호출 자체를 외부에서 독립적으로 증명할 수 없다.
