# 수퍼바이저 6종 3차 공동 평가 결과

측정일: 2026-11-05 · 상태: 3차 실행 종료

## 범위와 재계산 근거

- 동결 v2 70문항, SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`. 모델별 `run_index=3` 한 번만 실행했다. 유형 gold 35문항만 Accuracy·Macro-F1로 채점한다.
- 사전 등록 #33: [3차 계약](../experiments/supervisor-stage3-six-models.md), 유료 호출 전 로컬 커밋 `d10a30b`. 원격 공개 시점으로 실행 전 등록을 독립 증명했다고 주장하지 않는다.
- [3차 집계 JSON](../../evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json) SHA-256 `77139315fb0b99a2d5441fe2c5b728f90984850763f6846f2b32237cfc5e4659`. 1~3차 원시 파일과 3차 metadata의 hash, 모델별 수치·문항 ID를 담는다.
- 출처 hash 정책: 기존 1·2차 파일은 Git checkout의 줄바꿈 차이를 제외한 LF 정규화 SHA-256을 사용한다. 3차 JSON은 .gitattributes의 -text로 원시 바이트를 보존하고 그 SHA-256을 기록한다. 기존 회차 원시 파일과 3차 호출 결과의 내용은 수정하지 않았다.
- `execution.json`에 모델별 명령 인자·시작/종료 시각·process 경과 시간·종료 코드·원시 파일 hash를 보존했다. `preflight.json`에는 공개 catalog 가격·ZDR 노출·첫 문항 예약액을 기록했다.
- 재계산: `uv run --no-sync python -m evals.runners.report_supervisor_stage3 evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`. 집계기는 API를 호출하지 않으며 두 보고서도 같은 JSON에서 생성한다.

## PR 검토용 근거 구성

3차 사전 등록·두 manifest·공개 catalog preflight·6종 smoke·문항별 원시 행·실행 metadata·정정 집계 JSON·이 보고서와 간단 보고서를 보존한다. 기존 모델 호출 실행기는 저장소의 `run_supervisor_models.py`·`run_supervisor_jev.py`·`backend/services/llm.py`이며 source hash는 집계 JSON에 있다. 새 `report_supervisor_stage3.py`와 `tests/evals/test_supervisor_stage3_report.py`는 분모·라우팅 오류·3회 coverage 및 2차 정정 수치의 재계산을 검증한다.

## 3차 실측표

| Model ID | Attempted Outputs | Completion Rate | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Raw Calls | Errors | Reported Cost Sum (USD) | Budget-Accounted Cost (USD) | p50 Latency (s) | p95 Latency (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 70/70 | 70/70 | 50/70 | 23/35 | 0.758 | 120 | ValidationError 20 | 0.028076900 | 0.030994100 | 2.187 | 7.891 |
| `openai/gpt-6-luna` | 70/70 | 70/70 | 65/70 | 33/35 | 0.960 | 86 | ValidationError 5 | 0.012115500 | 0.013300100 | 3.281 | 15.078 |
| `deepseek/deepseek-v4.1-flash` | 70/70 | 70/70 | 7/70 | 2/35 | 0.125 | 200 | ValidationError 63 | 0.025543294 | 0.026067446 | 5.406 | 8.219 |
| `meta/muse-glimmer-30b` | 70/70 | 70/70 | 1/70 | 1/35 | 0.071 | 206 | ValidationError 68, RateLimitError 1 | 0.077216780 | 0.080733380 | 8.828 | 11.735 |
| `cohere/command-a-plus` | 70/70 | 70/70 | 21/70 | 8/35 | 0.343 | 173 | ValidationError 49 | 0.083025600 | 0.085510500 | 4.188 | 5.765 |
| `typesafe/jev-1.14` | 70/70 | 70/70 | 70/70 | 33/35 | 0.947 | 70 | 없음 | 0.002689092 | 0.002689092 | 0.422 | 0.454 |

표 읽는 법: Attempted Outputs는 호출을 시도한 고유 문항 수 / 70, Completion Rate는 성공·확정 실패 행 수 / 70이다. Schema Valid Rate는 형식상 유효한 결정 수 / 70이며 라우팅 정답을 보장하지 않는다. Question Type Accuracy는 gold 35문항의 정답 수 / 35, Macro-F1은 네 gold 유형 F1의 동일 가중 평균이다. Raw Calls는 재시도 포함 호출 수, Errors는 최종 오류 종류·수다. Reported Cost Sum은 저장된 usage 비용 합계, Budget-Accounted Cost는 보고 비용과 미보고 호출 예약액의 관리값이다. p50·p95 Latency는 nearest-rank 방식의 50·95백분위수이며 단위는 초다. 미완료 모델의 전체 정확도는 Not Comparable로 표시한다.

본 실행의 Raw Calls 합계는 855회, Budget-Accounted Cost 합계는 US$0.239294618000다. smoke는 포함하지 않는다. 기록 비용은 실제 전체 청구액의 독립 증명이 아니다.

## 호출·형식·시간 상세

| Model ID | Provider | Actual Model | Main Test Status | First-Pass Schema Success Rate | Retry Rate | API Error Rate | Elapsed Time (s) |
|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | Google | anthropic/claude-haiku-5.5 | complete_with_errors | 41/70 | 29/70 | 0/70 | 251.875 |
| `openai/gpt-6-luna` | Azure | openai/gpt-6-luna | complete_with_errors | 60/70 | 10/70 | 0/70 | 325.875 |
| `deepseek/deepseek-v4.1-flash` | Relace | deepseek/deepseek-v4.1-flash | complete_with_errors | 5/70 | 65/70 | 0/70 | 398.375 |
| `meta/muse-glimmer-30b` | DeepInfra | meta/muse-glimmer-30b | complete_with_errors | 1/70 | 68/70 | 1/70 | 622.234 |
| `cohere/command-a-plus` | Cohere | cohere/command-a-plus | complete_with_errors | 17/70 | 53/70 | 0/70 | 261.485 |
| `typesafe/jev-1.14` | TypeSafe | typesafe/jev-1.14-20261014 | complete | 70/70 | 0/70 | 0/70 | 30.625 |

표 읽는 법: Provider·Actual Model은 응답에 기록된 공급자·모델 ID다. Main Test Status는 실행기 종료 상태이며 complete_with_errors는 일부 최종 형식 오류가 남아도 모든 job을 처리했다는 뜻이다. First-Pass Schema Success Rate는 첫 시도에 형식을 통과한 수 / 70, Retry Rate는 재시도한 문항 수 / 70, API Error Rate는 형식·예산 차단 외 호출 오류 문항 수 / 70이다. Elapsed Time은 catalog 확인을 포함한 본 실행 process의 경과 시간이다.

| Model ID | Input Tokens (recorded) | Output Tokens (recorded) | Reported Cost Calls |
|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 166224 | 22909 | 110 |
| `openai/gpt-6-luna` | 56385 | 12954 | 80 |
| `deepseek/deepseek-v4.1-flash` | 108951 | 49793 | 196 |
| `meta/muse-glimmer-30b` | 91217 | 52470 | 205 |
| `cohere/command-a-plus` | 68337 | 41683 | 168 |
| `typesafe/jev-1.14` | 64026 | 14927 | 70 |

표 읽는 법: Input/Output Tokens (recorded)는 저장된 usage의 입력·출력 토큰 합계다. Reported Cost Calls는 비용 필드가 남은 usage record 수다. 생성형 5종은 재시도 뒤 성공한 문항의 앞선 실패 usage를 모두 보존하지 않으므로 전체 Raw Calls·실제 전체 청구액과 같지 않을 수 있다.

## Routing Consistency

| Model ID | Predicted out_of_scope | Inconsistent Action | Case IDs and Actions |
|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 7 | 0/7 | 없음 |
| `openai/gpt-6-luna` | 7 | 0/7 | 없음 |
| `deepseek/deepseek-v4.1-flash` | 5 | 0/5 | 없음 |
| `meta/muse-glimmer-30b` | 0 | Not Applicable (0/0) | 없음 |
| `cohere/command-a-plus` | 2 | 0/2 | 없음 |
| `typesafe/jev-1.14` | 6 | 4/6 | draft30-m06: circuit_agent; draft30-h09: search_agent; draft30-h10: search_agent; draft50-n18: search_agent |

표 읽는 법: Predicted out_of_scope는 모델이 스스로 범위 밖이라고 분류한 유효 행 수다. Inconsistent Action은 그중 refuse 외 동작을 고른 수 / 범위 밖 예측 수이며, 분모 0은 Not Applicable이다. 이 지표는 내부 출력의 일관성으로, gold와 대조한 범위 밖 탐지·거절 정확도가 아니다. Case IDs and Actions는 해당 문항 ID와 선택 동작이다.

## 1~3차 안정성

| Model ID | Comparable Three-Run Cases | Three-Run Exact Agreement | Question Type Flip Rate | Next Action Flip Rate |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 42/70 | 34/42 | 1/42 | 1/42 |
| `openai/gpt-6-luna` | 64/70 | 58/64 | 1/64 | 0/64 |
| `deepseek/deepseek-v4.1-flash` | 0/70 | Not Applicable (0/0) | Not Applicable (0/0) | Not Applicable (0/0) |
| `meta/muse-glimmer-30b` | 1/70 | 1/1 | 0/1 | 0/1 |
| `cohere/command-a-plus` | 17/70 | 17/17 | 0/17 | 0/17 |
| `typesafe/jev-1.14` | 70/70 | 60/70 | 0/70 | 4/70 |

표 읽는 법: Comparable Three-Run Cases는 세 회차 모두 형식상 유효한 문항 수 / 70이다. 나머지 세 지표의 분모는 그 비교 가능한 문항 수다. Exact Agreement는 decision 전체가 같은 문항 비율, 두 Flip Rate는 질문 유형·다음 동작이 한 번이라도 달라진 비율이다. 같은 오류를 반복해도 일치율이 높을 수 있다. 비교 가능한 문항이 적을 때 높은 일치율을 전체 성능으로 해석하지 않는다. 객체 키 순서만 정규화하고 required_evidence 배열의 순서는 보존한다.

## 1·2·3차 점수 대조

| Model ID | Stage 1 Accuracy | Stage 2 Accuracy | Stage 3 Accuracy | Stage 1 Schema Valid Rate | Stage 2 Schema Valid Rate | Stage 3 Schema Valid Rate |
|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 22/35 | 21/35 | 23/35 | 48/70 | 46/70 | 50/70 |
| `openai/gpt-6-luna` | 35/35 | 34/35 | 33/35 | 66/70 | 65/70 | 65/70 |
| `deepseek/deepseek-v4.1-flash` | Not Comparable (3/70 attempted, 0 valid) | 29/35 | 2/35 | Not Comparable (3/70 attempted, 0 valid) | 62/70 | 7/70 |
| `meta/muse-glimmer-30b` | 1/35 | 1/35 | 1/35 | 1/70 | 1/70 | 1/70 |
| `cohere/command-a-plus` | 8/35 | 9/35 | 8/35 | 20/70 | 21/70 | 21/70 |
| `typesafe/jev-1.14` | 33/35 | 33/35 | 33/35 | 70/70 | 70/70 | 70/70 |

표 읽는 법: 각 Stage의 Accuracy는 같은 gold 35문항에서 유형을 맞힌 수, Schema Valid Rate는 전체 70문항의 형식 통과 수다. provider 중단 등으로 일부만 실행한 회차는 두 지표 모두 Not Comparable로 표시한다. 괄호의 attempted는 계획 대비 실제 시도 문항 수, valid는 형식상 유효 결정 수이며 완주 결과와 직접 비교하지 않는다.

| Model ID | Stage 1 Provider | Stage 2 Provider | Stage 3 Provider |
|---|---|---|---|
| `anthropic/claude-haiku-5.5` | Google | Google | Google |
| `openai/gpt-6-luna` | Azure | Azure | Azure |
| `deepseek/deepseek-v4.1-flash` | Not Recorded | Morph | Relace |
| `meta/muse-glimmer-30b` | DeepInfra | DeepInfra | DeepInfra |
| `cohere/command-a-plus` | Cohere | Cohere | Cohere |
| `typesafe/jev-1.14` | TypeSafe | TypeSafe | TypeSafe |

표 읽는 법: Provider는 각 회차 응답에 기록된 실제 공급자다. 같은 Model ID에서도 공급자가 바뀌면 형식 지원·지연·모델 제공 조건이 달라질 수 있으므로 점수 차이를 모델 자체 변화로만 해석하지 않는다. Not Recorded는 공급자 정보가 남지 않았다는 뜻이다.

### DeepSeek 출력 길이 진단

| Run | Provider | Schema Valid Rate | Length-Limited Validation Failures | Validation Attempts at 256 Tokens |
|---|---|---|---|---|
| 2 | Morph | 62/70 | 8/8 | 24/24 |
| 3 | Relace | 7/70 | 63/63 | 189/189 |

표 읽는 법: Run은 회차, Provider는 실제 공급자, Schema Valid Rate는 형식 통과 / 70이다. Length-Limited Validation Failures는 마지막 종료 사유가 length인 형식 실패 수 / 전체 형식 실패 수다. Validation Attempts at 256 Tokens는 형식 실패 문항의 저장된 시도 usage 중 출력 토큰 256개인 수 / 해당 usage record 수다.

3차 gold 35문항 중 33문항은 형식 실패했고 유효한 두 문항은 모두 유형 정답이었다. 프롬프트·출력 상한 256·실행 로직은 유지됐으며, 두 manifest의 실행기 hash 차이는 LF/CRLF 줄바꿈 차이로 확인했다. 공급자 변경과 출력 제한 도달이 함께 관찰됐지만, 내부 추론 설정이나 JSON 처리 차이의 인과관계는 이 자료로 확정하지 않는다.

### 2차에서 3차로 달라진 labeled 문항

| Model ID | Case ID | Gold | Stage 2 | Stage 3 |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | draft30-e05 | rating | rating | error |
| `anthropic/claude-haiku-5.5` | draft50-n02 | candidate_judge | error | candidate_judge |
| `anthropic/claude-haiku-5.5` | draft50-n07 | candidate_judge | error | candidate_judge |
| `anthropic/claude-haiku-5.5` | draftv2-n04 | candidate_find | candidate_find | error |
| `anthropic/claude-haiku-5.5` | draftv2-n06 | candidate_find | error | candidate_find |
| `anthropic/claude-haiku-5.5` | draftv2-n10 | candidate_find | error | candidate_find |
| `openai/gpt-6-luna` | draft50-n06 | candidate_judge | candidate_judge | rating |
| `deepseek/deepseek-v4.1-flash` | draft30-e02 | role | role | error |
| `deepseek/deepseek-v4.1-flash` | draft30-e03 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft30-e05 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft30-e08 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft30-m02 | role | role | error |
| `deepseek/deepseek-v4.1-flash` | draft30-m03 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft30-m04 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft30-m05 | rating | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft30-m07 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft30-h01 | role | role | error |
| `deepseek/deepseek-v4.1-flash` | draft30-h02 | role | role | error |
| `deepseek/deepseek-v4.1-flash` | draft30-h04 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft30-h05 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n02 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n03 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n04 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n05 | rating | rating | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n06 | candidate_judge | out_of_scope | error |
| `deepseek/deepseek-v4.1-flash` | draft50-n08 | candidate_judge | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draft52-n21 | rating | candidate_judge | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n01 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n02 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n03 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n04 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n05 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n06 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n07 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n08 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n09 | candidate_find | candidate_find | error |
| `deepseek/deepseek-v4.1-flash` | draftv2-n10 | candidate_find | candidate_find | error |
| `cohere/command-a-plus` | draft30-m07 | rating | error | rating |
| `cohere/command-a-plus` | draft50-n06 | candidate_judge | candidate_judge | error |
| `cohere/command-a-plus` | draft52-n21 | rating | rating | error |

표 읽는 법: Gold는 동결된 질문 유형, Stage 2·3은 저장된 질문 유형 또는 실패 상태다. 같은 정오라도 예측 유형이 달라지면 포함하며, next_action만 달라진 문항은 집계 JSON의 flip 목록에서 확인한다.

## 3차 유형별 F1

| Model ID | candidate_find | candidate_judge | rating | role |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 0.947 | 0.333 | 0.750 | 1.000 |
| `openai/gpt-6-luna` | 1.000 | 0.941 | 0.900 | 1.000 |
| `deepseek/deepseek-v4.1-flash` | 0.000 | 0.000 | 0.000 | 0.500 |
| `meta/muse-glimmer-30b` | 0.000 | 0.000 | 0.000 | 0.286 |
| `cohere/command-a-plus` | 0.000 | 0.000 | 0.462 | 0.909 |
| `typesafe/jev-1.14` | 1.000 | 0.900 | 0.889 | 1.000 |

표 읽는 법: candidate_find는 후보 찾기, candidate_judge는 특정 후보 판단, rating은 정격·특성, role은 회로 역할 질문이다. 각 값은 해당 유형의 정밀도와 재현율을 함께 반영한 F1이며 1에 가까울수록 높다.

## 원시 결과 무결성

| Raw Result File | SHA-256 |
|---|---|
| evals/results/supervisor/2026-11-05-stage3-five-v1/rows_anthropic__claude-haiku-5.5.json | a59a05cf868e80f6c4b55c654f3a934de90b6bbd46d15782d8b0edade2d67bf1 |
| evals/results/supervisor/2026-11-05-stage3-five-v1/rows_openai__gpt-6-luna.json | d06fa53bcefde71a6ed953585582093d36efb95ab6edf10d3c635b06ad3a7a77 |
| evals/results/supervisor/2026-11-05-stage3-five-v1/rows_deepseek__deepseek-v4.1-flash.json | 0cfa2069c245466bbabd7bbb30fd8d8c65df1c465c884b437b1a87bece0b71df |
| evals/results/supervisor/2026-11-05-stage3-five-v1/rows_meta__muse-glimmer-30b.json | 7bf2a7c5bfba3ec33ee3157ad54a83a6e2426886ce73e2c2202503dcf652effc |
| evals/results/supervisor/2026-11-05-stage3-five-v1/rows_cohere__command-a-plus.json | f42f91056ba8521a268d0440eb2be0c78ee26901883e726e40443ca6f411bf78 |
| evals/results/supervisor/2026-11-05-jev-stage3-v1/rows.json | 5b514dc28fd17a8290c1dcfd849173cc718ffbfb43057f1330243464d606e1a1 |

표 읽는 법: Raw Result File은 3차 문항별 원시 파일 경로, SHA-256은 그 파일 바이트의 식별값이다. 해시 자체가 API 호출·정답·실제 청구를 독립 증명하지는 않는다. 나머지 metadata와 1·2차 원본의 hash는 집계 JSON에 있다.

## 최종 후보 모델

3차 결과 확인 후 사용자 결정으로 최종 후보를 `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5`의 3종으로 확정했다. 아래 표는 후보 유지·탈락 상태를 기록하며 순위를 부여하지 않는다. 이 결정은 사전 등록의 선정 규칙으로 소급하지 않으며 서비스 채택 모델 확정과 구별한다. 기존 여섯 모델의 코드·실측·원시 근거는 보존한다.

| Model ID | Final Candidate Status | Basis |
|---|---|---|
| `openai/gpt-6-luna` | Final Candidate | 1~3차 유형 정답 35·34·33/35, 형식 통과 66·65·65/70. 최종 후보로 유지. |
| `typesafe/jev-1.14` | Final Candidate | 세 회차 유형 정답 33/35·형식 통과 70/70. 최종 후보로 유지하며 3차 동작 불일치 4/6도 후속 검증 항목으로 보존. |
| `anthropic/claude-haiku-5.5` | Final Candidate | 사용자 결정으로 최종 후보에 유지. 세 회차 유형 정답 22·21·23/35, 형식 통과 48·46·50/70의 실측과 한계도 함께 보존. |
| `deepseek/deepseek-v4.1-flash` | Excluded | 사용자는 세 회차 실행의 안정성이 부족하다고 판단해 탈락 결정. 1차 provider 중단, 2·3차 공급자 변경과 3차 출력 제한 실패를 기록하며 모델 자체의 보편적 성능 저하로 단정하지 않음. |
| `cohere/command-a-plus` | Excluded | 세 회차 유형 정답 8·9·8/35, 형식 통과 20·21·21/70. 현재 계약의 실패가 반복돼 최종 후보에서 제외. |
| `meta/muse-glimmer-30b` | Excluded | 세 회차 모두 유형 정답 1/35·형식 통과 1/70으로 최종 후보에서 제외. |

표 읽는 법: Final Candidate Status의 Final Candidate는 후속 비교를 위한 최종 후보, Excluded는 최종 후보에서 탈락했다는 뜻이다. Basis는 관찰한 실측과 사용자 결정의 근거이며 순위나 서비스 채택 완료를 뜻하지 않는다.

최종 후보의 프롬프트·동작 제약·출력 상한을 바꿔 실행한다면 별도 조건 변경 실험으로 등록한다. 기존 호출 실행기의 후보 목록은 과거 결과 재현을 위해 유지한다.

## 해석 제한

- 같은 동결 70문항을 반복했다. 35개 비관련 문항의 올바른 거절 여부와 독립 평가셋·실서비스 그래프 성능은 이번 측정으로 입증하지 않는다.
- 유형 gold는 35문항이어서 한 문항이 약 2.86%p다. 1~2문항 차이는 달라진 문항을 확인하는 근거이며 일반적인 모델 우열의 확정 근거로 삼지 않는다.
- Jev의 typed answer와 결정적 출력 변환은 다른 5종의 JSON 생성과 다르다. 형식 성공과 전체 decision 일치율을 동일한 생성 능력으로 해석하지 않는다.
- 모델별 provider가 회차마다 달라질 수 있다. 특히 실행 metadata의 공급자 차이가 있으면 모델 자체 변화와 분리해 해석해야 한다.
- Jev 실행기는 2차 뒤 비용 초과 중단·비유한 인자 차단이 추가됐다. 프롬프트·변환 계약은 유지했다. --max-usd는 입력 비용 추정에 의한 다음 job 차단값이며 마지막 job의 실제 비용이 계획값을 넘을 수 있다.
- 생성형 5종 raw summary는 세 회차 전체 계획의 210건 분모를 사용하므로 이 보고서는 원시 run_index=3 행만 재계산했다. configured_max_calls=630은 전체 1~3차 계획의 값이고, 이번 selected_run_indices=[3]의 job 70건은 각 최대 3회로 실제 210호출 이하다.
- 5종 smoke 파일은 usage 비용을 보존하지 않아 실제 smoke 총 비용을 확정할 수 없다. Jev smoke의 보고 비용은 해당 smoke.json에서 확인한다.
- 5종 manifest의 code_sha256은 실행 전 파일 원시 바이트 hash다. 집계 JSON의 execution_code_sha256_lf·analysis_code_sha256_lf는 줄바꿈을 LF로 정규화한 hash이므로 CRLF checkout의 원시 hash와 직접 비교하지 않는다.
- 사전 등록의 ‘2차와 크게 다르지 않다’에 수치 허용 범위가 없으므로 가설 통과 여부나 운영 모델 변경을 자동 판정하지 않는다. 실측 차이와 실패 문항을 그대로 기록한다.
