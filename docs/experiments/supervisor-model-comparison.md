# 수퍼바이저 모델 5종 비교

상태: 동결 v2 70문항 1회 비교를 완료했고, 실측 결과를 근거로 `openai/gpt-6-luna`를 수퍼바이저 모델로 최종 확정함.

## Why

- **페르소나**: SojaFit의 수퍼바이저 모델을 품질뿐 아니라 안정성·안전성·비용까지 근거로 선택해야 하는 에이전트·평가 담당자
- **상황**: 수퍼바이저는 사용자 입력을 읽고 질문 종류, 필요한 근거, 다음 실행 경로를 정한다. 현재 노드 그림은 참고안이며 최종 그래프와 서브에이전트 수는 확정되지 않았다.
- **문제**:
  1. 공개 benchmark만으로는 실제 70문항에서의 route 정확도, 실패 처리, 비용을 알 수 없다.
  2. 생성 모델과 judge를 같은 역할로 쓰거나 주관적 점수 하나로 합치면 모델 편향과 평가 기준 변경을 발견하기 어렵다.
  3. 값싼 모델도 반복 route 변경, schema 오류, hallucinated citation 때문에 재시도와 후속 호출이 늘면 전체 비용이 더 커질 수 있다.
- **측정 지표**: objective routing, schema 성공, latency와 cost를 서로 분리해 측정한다.

## Goal

- **해결 목표**: 아래 5개 모델을 동결 `evals/dataset_v2.jsonl` 70문항에 같은 입력·출력 계약으로 1회씩 실행하고, 실측 품질·실패·비용·latency를 비교해 수퍼바이저 모델을 확정한다.
- **실행 규모**: `5 models × 70 cases × 1 run = 350` planned outputs. retry와 실패 호출은 output 수에 섞지 않고 별도 집계한다.
- **후보 모델**:
  - `anthropic/claude-haiku-5.5`
  - `openai/gpt-6-luna`
  - `deepseek/deepseek-v4.1-flash`
  - `meta/muse-glimmer-30b`
  - `cohere/command-a-plus`
- **성공 기준**:
  - 각 후보는 70문항 결과 또는 명시적인 provider stop 기록을 가져야 한다.
  - 결과표의 모든 값에 source type, 분자, 분모, 계산식, direction이 연결되어야 한다.
  - safety gate를 하나라도 위반한 모델은 평균 점수와 관계없이 채택 후보에서 제외한다.
  - 최종 비교는 operational eligibility → schema valid rate → objective accuracy → cost → latency 순으로 하며 임의의 단일 종합 점수를 만들지 않는다.
- **Out of Scope**:
  - 참고 노드 그림을 최종 그래프로 확정하거나 서브에이전트 수를 결정하는 일
  - embedding, retrieval, reranker 후보를 다시 선택하는 일
  - 동결 파일 `evals/dataset_v2.jsonl` 또는 `evals/FROZEN.json`을 수정하는 일
  - main LLM과 judge LLM을 같은 비교 결과로 동시에 확정하는 일

## What

**Happy Path**

1. 평가셋 hash, prompt version, output schema, provider endpoint, privacy policy, generation parameters와 가격 snapshot을 실행 전에 manifest에 고정한다.
2. 동결 파일과 분리된 label file에 `question_type`, `required_evidence`, `next_action`, `reason_code`의 사람이 합의한 gold를 저장한다. 동결 파일의 `expected`, `why`, `gold_chunks`는 모델 입력에 넣지 않는다.
3. 5개 모델을 각각 독립 process에서 70문항씩 1회 실행하고 parsed output, usage, latency, retry, error를 기록한다. raw response는 저장하지 않는다.
4. deterministic scorer로 objective routing과 schema 결과를 계산한다.
5. measured, calculated, estimated 값을 구분한 결과표를 작성한 뒤 모델을 선택한다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | `dataset_v2.jsonl`의 비관련 35건처럼 `question_type`이 비어 있음 | 실행 전에 별도 label file에서 route gold를 두 사람이 합의한다. 동결 파일은 수정하지 않는다. |
| EC-02 | JSON/schema parsing 실패 | 원문과 parse error를 보존하고 고정 횟수만 retry한다. first pass와 final success를 따로 센다. |
| EC-03 | provider timeout, 429, 5xx | 자동 fallback 없이 구조화된 failure로 기록한다. 같은 model ID의 다른 provider로 조용히 바꾸지 않는다. |
| EC-04 | ZDR 또는 data collection 조건을 만족하는 endpoint가 없음 | 해당 모델 실행을 fail closed하고 품질 0점으로 환산하지 않는다. `Not Measured`와 차단 이유를 기록한다. |
| EC-05 | reasoning token 또는 cache token을 provider가 제공하지 않음 | 0으로 쓰지 않고 `Not Reported`로 기록한다. reported total과 local calculation을 구분한다. |
| EC-06 | 실제 청구 비용을 즉시 확인할 수 없음 | usage와 고정 가격 snapshot으로 `Estimated Cost`를 계산하되 `Actual Total Cost`와 섞지 않는다. |
| EC-07 | model ID는 같지만 endpoint나 revision이 실행 중 변경됨 | manifest fingerprint가 바뀐 run을 중단하고 별 run으로 분리한다. |
| EC-08 | pairwise judge가 A 위치를 일관되게 선호함 | A/B 위치를 바꿔 두 번 평가하고 `Position-Swap Consistency`를 보고한다. |
| EC-09 | judge와 사람 판정이 크게 다름 | judge 점수를 최종 정답으로 쓰지 않고 불일치 문항을 사람이 재검토한다. |
| EC-10 | retrieval 또는 tool 오류를 supervisor가 근거 없음으로 잘못 해석함 | route와 failure reason을 함께 채점하고 안전 실패로 별도 기록한다. |

## How

### 1. 고정 입력과 출력 계약

- **Dataset**: `evals/dataset_v2.jsonl`, 70건(`relevant=35`, `irrelevant=35`)
- **현재 `question_type` 분포**: `candidate_find=10`, `candidate_judge=9`, `rating=10`, `role=6`, 빈 값 35
- **반복**: 모델·문항마다 1회.
- **수퍼바이저 입력**: 실제 사용자 입력과 고정된 최소 system prompt만 사용한다. gold label, `expected`, `why`, `gold_chunks`, 모범 답변은 전달하지 않는다.
- **수퍼바이저 출력**:

```json
{
  "question_type": "candidate_find | candidate_judge | rating | role | out_of_scope | insufficient_information",
  "required_evidence": ["circuit", "datasheet", "approved_case"],
  "next_action": "circuit_agent | search_agent | judge_answer_agent | refuse",
  "reason_code": "string"
}
```

- 실제 최종 노드명이 달라져도 비교 기간에는 위 evaluation contract를 바꾸지 않는다. 계약을 바꾸면 새 experiment version으로 처음부터 실행한다.

### 2. 실행 조건

| Condition | Fixed value or rule |
|---|---|
| Model IDs | 위 5개 full model ID만 사용하고 별칭을 쓰지 않음 |
| Temperature | 지원 endpoint에는 `0`; `anthropic/claude-haiku-5.5`·`openai/gpt-6-luna` ZDR endpoint에는 parameter를 보내지 않음 |
| Top P | provider가 허용하면 `1`; 무시 여부 기록 |
| Max Output Tokens | 모든 후보에 같은 256-token cap. API 이름은 endpoint 계약에 따라 `max_tokens` 또는 `max_completion_tokens` |
| Timeout | 모든 후보에 같은 값으로 고정 |
| Retry | 동일 횟수·동일 backoff, retry call은 단계별 planned output과 분리 |
| Fallback | 없음 |
| Provider | model별 ZDR endpoint, `sort=price`, 공개 catalog 단가의 `max_price`를 실행 전에 고정하고 provider ID 기록 |
| Privacy | ZDR 요구, data collection 불허, 충족하지 않으면 실행 중단 |
| Prompt | 같은 prompt text와 prompt hash |
| Process | `LLM_MODEL` import-time binding을 피하도록 model별 독립 process |
| Cache | cache 사용 여부·read/write token을 기록하고 조건을 섞지 않음 |

endpoint availability, model revision, pricing, ZDR는 시간에 따라 바뀔 수 있으므로 실행 직전에 다시 확인한다. 확인값은 모델 능력 측정값이 아니라 run metadata다.

### 3. 평가 방식

#### Method A — Deterministic Objective Scoring

gold와 구조화 출력을 정확 대조한다. `question_type`, `required_evidence`, `next_action`, judge route가 대상이며 자유 서술의 문체는 채점하지 않는다.

#### Method B — Robustness and Failure Handling

원문 70건과 별도로 의미를 보존한 perturbation 및 provider/tool failure scenario를 실행한다. 품번, 전압, 극성, 파일명처럼 의미를 바꾸는 변형은 금지한다. perturbation 생성 규칙과 hash를 결과 보기 전에 고정한다.

#### Method C — Blind Pairwise Comparison

5개 후보의 모든 조합은 10쌍이다. 70문항 전체를 A/B 위치 교환까지 평가하면 `10 pairs × 70 cases × 2 positions = 1,400` judge decisions이다. 이는 이번 supervisor 선택 실측에 포함하지 않았다.

- 비교 화면에서 model ID, provider, 비용을 숨긴다.
- objective gold가 있는 필드는 deterministic score가 우선한다.
- pairwise는 reason quality, evidence sufficiency, actionable routing처럼 규칙만으로 판정하기 어려운 항목에 한정한다.
- judge model은 후보 5종 중 자동 선택하지 않고 별도 preregistration으로 정한다.
- 사람 표본 판정으로 judge bias를 확인하며, A/B swap 결과가 다르면 tie 또는 human review로 보낸다.

#### Method D — End-to-End Evaluation

supervisor-only gate를 통과한 후보에 같은 retrieval, reranker, tools, answer prompt를 연결한다. 기존 답변·거절 5지표와 전체 성공률을 측정한다. downstream 차이를 supervisor 성능으로 해석하려면 supervisor 이외 조건이 모두 같아야 한다.

#### Method E — Operational Measurement

각 API response의 provider usage와 local monotonic clock으로 token, actual/estimated cost, latency, error를 기록한다. public price나 vendor benchmark는 `[Public Specification]`으로만 표시하고 measured value를 대신하지 않는다.

### 4. source type

| Source Type | 뜻 |
|---|---|
| `[Public Specification]` | provider 문서의 context, price, policy, endpoint 정보 |
| `[Measured]` | 이번 고정 run에서 직접 기록한 response, usage, latency, error |
| `[Human Judgment]` | model ID를 가린 사람 판정 |
| `[LLM Judge]` | 독립 judge의 구조화 판정 |
| `[Calculated]` | measured count·usage에서 아래 식으로 계산한 값 |
| `[Estimated]` | 실제 청구액이 없어 고정 가격 snapshot으로 추정한 값 |

### 5. 실측값 표에 쓰는 metric 정의

모든 rate는 `numerator / denominator`와 제외 ID를 함께 저장한다. 방향은 `↑`가 높을수록 좋음, `↓`가 낮을수록 좋음이다.

#### Objective routing

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `Question Type Accuracy` | `question_type` gold가 있는 문항에서 예측이 정확히 같은 비율. run별로 계산하고 mean·min·max를 보고 | correct labeled cases / all labeled cases in that run | ↑ |
| `Question Type Macro-F1` | class 크기와 무관하게 각 `question_type` F1을 동일 가중 평균 | mean(per-class F1) | ↑ |
| `Per-Class Precision` | 특정 class로 보낸 결과 중 실제 그 class인 비율 | TP / (TP + FP) | ↑ |
| `Per-Class Recall` | 특정 class gold 중 올바르게 그 class로 보낸 비율 | TP / (TP + FN) | ↑ |
| `Per-Class F1` | 특정 class의 precision과 recall 조화평균 | 2PR / (P + R) | ↑ |
| `Required Evidence Exact Match` | `required_evidence` set이 gold set과 완전히 같은 비율 | exact set matches / scored cases | ↑ |
| `Under-Call Rate` | 필요한 evidence를 하나 이상 누락한 비율 | cases missing gold evidence / scored cases | ↓ |
| `Over-Call Rate` | 불필요한 evidence를 하나 이상 요구한 비율 | cases adding non-gold evidence / scored cases | ↓ |
| `Next Action Accuracy` | `next_action`이 gold route와 같은 비율 | correct actions / scored cases | ↑ |
| `Judge Route Compliance` | judge가 필요한 문항만 `judge_answer_agent`로 보내고 bypass하지 않은 비율 | compliant judge routes / judge-required cases | ↑ |

#### Schema and completion

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `First-Pass Schema Success Rate` | retry 전 첫 response가 schema를 만족한 비율 | first-pass valid outputs / attempts | ↑ |
| `Final Schema Success Rate` | 허용 retry 후 최종 output이 schema를 만족한 비율 | final valid outputs / cases | ↑ |
| `Retry Rate` | 한 번 이상 retry한 case 비율 | retried cases / cases | ↓ |
| `Mean Retry Count` | case당 평균 추가 호출 횟수 | total retry calls / cases | ↓ |
| `Completion Rate` | timeout·API error 없이 최종 결과가 생긴 비율 | completed cases / cases | ↑ |

#### Robustness and safety

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `Original Accuracy` | 원문 set의 objective accuracy | correct original cases / original cases | ↑ |
| `Perturbed Accuracy` | 의미 보존 변형 set의 objective accuracy | correct perturbed cases / perturbed cases | ↑ |
| `Performance Drop` | 변형으로 감소한 accuracy | Original Accuracy - Perturbed Accuracy | ↓ |
| `Robustness Retention Rate` | 원문 성능 중 변형 뒤 유지한 비율 | Perturbed Accuracy / Original Accuracy | ↑ |
| `Failure-Handling Accuracy` | timeout·tool error·empty result를 정해진 route/reason으로 처리한 비율 | correct failure handling / failure scenarios | ↑ |
| `Safety-Failure Case Count` | 하나 이상의 safety gate를 위반한 서로 다른 case 수 | count(unique failed case IDs) | ↓ |
| `Safety-Failure Event Count` | 한 case에서 여러 위반을 각각 센 총 event 수 | count(all safety violations) | ↓ |
| `Safety-Failure Rate` | safety violation case 비율 | failed cases / safety-scored cases | ↓ |
| `Evidence Preservation Rate` | route 과정에서 품번·수치·극성·사용 조건을 바꾸지 않은 비율 | preserved cases / evidence-bearing cases | ↑ |

#### Pairwise and judge validation

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `Pairwise Win Rate` | tie를 0.5로 두었을 때 상대 후보 대비 이긴 비율 | (wins + 0.5 × ties) / decisions | ↑ |
| `Position-Swap Consistency` | A/B 위치를 바꿔도 의미상 같은 승자를 고른 비율 | consistent swapped pairs / swapped pairs | ↑ |
| `Human Inter-Rater Agreement` | 두 사람의 raw 동일 판정 비율 | identical human labels / reviewed labels | ↑ |
| `Cohen's Kappa` | 두 사람 판정의 우연 일치를 보정한 값 | standard Cohen's kappa | ↑ |
| `Human-LLM Judge Agreement` | 사람 합의와 독립 judge 판정이 같은 비율 | matching decisions / reviewed decisions | ↑ |

#### End-to-end answer

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `Cited Gold Rate` | 관련 문항에서 정답 문서·쪽 또는 필요한 netlist를 인용한 비율 | cited_gold / relevant cases | ↑ |
| `Wrong Citation Rate` | 관련 문항에서 잘못되거나 존재하지 않는 근거를 인용한 비율 | wrong_citation / relevant cases | ↓ |
| `Over-Refusal Rate` | 답할 근거가 있는 관련 문항을 거절한 비율 | over_refusal / relevant cases | ↓ |
| `Correct Refusal Rate` | 비관련 문항을 근거 없이 단정하지 않고 거절한 비율 | correct_refusal / irrelevant cases | ↑ |
| `Hallucination Risk Rate` | 비관련 문항에 답을 생성하거나 근거를 꾸민 비율 | hallucination_risk / irrelevant cases | ↓ |
| `End-to-End Success Rate` | 문항별 사전 정의한 route·근거·최종 답 조건을 모두 만족한 비율 | successful cases / all cases | ↑ |

#### Usage, cost, latency, and health

| Metric | Definition | Formula | Direction |
|---|---|---|---|
| `Input Tokens` | provider가 보고한 input token 합계 | sum(reported input tokens) | ↓ |
| `Output Tokens` | provider가 보고한 output token 합계 | sum(reported output tokens) | ↓ |
| `Reasoning Tokens` | provider가 별도 보고한 reasoning token 합계 | sum(reported reasoning tokens) | ↓ |
| `Cache Read Tokens` | cache에서 읽은 것으로 provider가 보고한 token 합계 | sum(reported cache read tokens) | 참고 |
| `Cache Write Tokens` | cache에 쓴 것으로 provider가 보고한 token 합계 | sum(reported cache write tokens) | 참고 |
| `Actual Total Cost` | provider billing/response가 실제로 보고한 총비용 | sum(actual reported cost) | ↓ |
| `Estimated Total Cost` | 고정 price snapshot과 usage로 계산한 비용 | token classes × snapshotted unit prices | ↓ |
| `Cost per Case` | 완료 여부와 무관한 전체 case당 비용 | total cost / attempted cases | ↓ |
| `Cost per Successful Case` | end-to-end 성공 1건을 얻는 데 든 비용 | total cost / successful cases | ↓ |
| `p50 Latency` | supervisor API wall-clock latency 중앙값 | percentile(latency, 50) | ↓ |
| `p95 Latency` | supervisor API wall-clock latency 95백분위수 | percentile(latency, 95) | ↓ |
| `End-to-End Case Latency` | supervisor부터 최종 응답까지 case별 wall-clock 시간 | end time - start time | ↓ |
| `API Error Rate` | timeout·429·5xx·connection error case 비율 | API error cases / attempted cases | ↓ |
| `Endpoint Health` | 고정 endpoint가 요청을 받아 정상 response를 반환할 수 있는 상태 | healthy checks / scheduled checks | ↑ |

`Endpoint Health`는 모델 품질 점수가 아니다. 장애 시간과 모델 출력 오류를 구분하기 위한 운영값이다.

#### Statistical comparison

| Metric | Definition | Formula or method | Interpretation |
|---|---|---|---|
| `95% Confidence Interval` | 70문항 표본에서 metric 불확실성을 나타내는 구간 | question ID를 cluster로 둔 bootstrap | 구간이 넓으면 순위 확정에 주의 |
| `McNemar p-value` | 같은 문항에서 두 모델의 correct/incorrect 차이를 비교 | paired McNemar test | accuracy 차이의 paired evidence |
| `Sign Test p-value` | pairwise 승패가 한쪽으로 치우쳤는지 비교 | ties 제외 two-sided sign test | 주관 평가의 방향성 evidence |

세 run은 210개의 독립 문항이 아니다. run별 metric의 mean·min·max를 보고하고, 후속 비교의 confidence interval은 question ID를 cluster로 둔다. 실패·누락 run은 accuracy와 stability 분모에서 빼지 않는다. p-value만으로 모델을 선택하지 않는다.

### 6. safety gate

다음은 1건이라도 발생하면 해당 모델을 채택 후보에서 제외하고 원인을 검토한다.

- ZDR/data collection 조건을 충족하지 않는 endpoint로 평가 데이터를 전송함
- 입력의 품번, 수치, 극성, 사용 조건을 route reason에서 다른 값으로 바꿈
- judge가 필요한 판정을 우회해 승인·대체 가능을 단정함
- 사람 승인 전 견적·사례를 저장하거나 저장 route를 선택함
- retrieval/tool error를 근거 없음과 혼동해 안전하지 않은 답 route를 선택함
- 허용되지 않은 tool 또는 외부 endpoint를 호출함
- 존재하지 않는 citation이나 승인 사례를 있다고 단정함

### 7. 결과표

#### 7-1. 2026-11-04 Partial Measured Main Test

아래 값은 smoke가 아니라 동결 v2 70문항×3회 본 테스트 manifest의 실제 `run` 결과다. 다만 rate limit과 사전 승인한 예약비용 상한으로 모델마다 서로 다른 지점에서 멈췄으므로 **부분 본 테스트 실측값**이며 최종 모델 순위로 사용하지 않는다. `anthropic/claude-haiku-5.5`와 `openai/gpt-6-luna`는 smoke에서 `NotFoundError`가 발생해 본 테스트를 시작하지 않았다.

| Model ID | Source Type | Main Test Status | Planned Outputs | Recorded Outputs | Schema Success | Schema Failure | Other Stop Output |
|---|---|---|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | `[Measured]` | `Not Started — original smoke NotFoundError; routing-fix smoke complete` | 210 | 0 | 0 | 0 | 0 |
| `openai/gpt-6-luna` | `[Measured]` | `Not Started — original smoke NotFoundError; routing-fix smoke complete` | 210 | 0 | 0 | 0 | 0 |
| `deepseek/deepseek-v4.1-flash` | `[Measured]` | `RateLimit Paused` | 210 | 126 | 106 | 17 | 3 `RateLimitError` |
| `meta/muse-glimmer-30b` | `[Measured]` | `Budget Stopped` | 210 | 83 | 3 | 79 | 1 `EvaluationLimitError` |
| `cohere/command-a-plus` | `[Measured]` | `Budget Stopped` | 210 | 96 | 28 | 67 | 1 `EvaluationLimitError` |

`Schema Success Rate` 분모는 provider 응답을 받고 최종 schema 성공 또는 실패가 확정된 outputs다. `Planned Completion`은 schema 성공 outputs / 계획 210이며, 아직 실행하지 못한 outputs도 미완료로 남긴다.

| Model ID | Schema Success Rate | Planned Completion | Raw Calls | Input Tokens | Output Tokens | p50 Latency | p95 Latency | Partial Reported Cost | Reserved Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `deepseek/deepseek-v4.1-flash` | 86.179% (106/123) | 50.476% (106/210) | 183 | 122,845 | 27,826 | 6.594s | 32.859s | $0.010942 (148 usage records) | $0.112012 |
| `meta/muse-glimmer-30b` | 3.659% (3/82) | 1.429% (3/210) | 241 | 97,845 | 61,410 | 12.031s | 19.594s | $0.087437 (240 usage records) | $0.849317 |
| `cohere/command-a-plus` | 29.474% (28/95) | 13.333% (28/210) | 235 | 85,194 | 56,338 | 4.765s | 7.578s | $0.110065 (229 usage records) | $0.847466 |

`Partial Reported Cost`는 provider가 cost를 반환한 usage records만 합산한 부분값이다. smoke 비용과 usage가 없는 호출은 포함하지 않으므로 `Actual Total Cost`로 승격하지 않는다. `Reserved Cost`는 실행 전 보수적으로 잡은 상한 소비량이며 청구액이 아니다. latency는 기록된 본 테스트 output row 기준이다.

부분 runner summary는 다음과 같다. 미실행 labeled case도 `Question Type Accuracy`에서 오답으로, 미완료 case도 agreement 분모 70에 포함된다. 모델마다 실행된 case prefix가 다르므로 아래 값으로 모델 간 최종 우열을 정하지 않는다.

| Model ID | Question Type Accuracy mean (min–max) | Question Type Macro-F1 mean | Three-Run Exact Agreement | Incomplete Three-Run Cases |
|---|---:|---:|---:|---:|
| `deepseek/deepseek-v4.1-flash` | 0.600 (0.571–0.629) | 0.682 | 0.429 | 38/70 |
| `meta/muse-glimmer-30b` | 0.029 (0.029–0.029) | 0.071 | 0.014 | 69/70 |
| `cohere/command-a-plus` | 0.152 (0.143–0.171) | 0.255 | 0.114 | 62/70 |

원시 parsed output과 집계 파일은 `evals/results/supervisor/2026-11-04-preflight-v5/`, 실행 상태 요약은 같은 폴더의 `evaluation_outcome.json`에 있다. 실행 중인 smoke·본 테스트 프로세스는 0개다.

2026-11-04 routing parameter 수정 뒤 새 manifest `evals/results/supervisor/2026-11-04-routing-fix-smoke-v1/`에서 다시 확인했다. `anthropic/claude-haiku-5.5`는 `Google`, `openai/gpt-6-luna`는 `Azure` provider에서 actual model ID와 schema output을 포함한 smoke를 완료했다. 이 두 호출은 본 테스트 output에 포함하지 않는다.

#### 7-2. Final Supervisor Model Selection

**선정 모델은 `openai/gpt-6-luna`다.** 이 결정은 `evals/results/supervisor/2026-11-04-stage1-v1/`의 후보별 70문항 1회 실행을 근거로 한다. 이 모델은 수퍼바이저의 질문 분류와 다음 route 결정을 맡는 모델이며, 최종 답변 생성 모델을 선정한 것은 아니다.

선정 기준은 서로 다른 metric을 임의 가중합하지 않고 다음 순서로 적용했다.

1. **Operational Eligibility**: 70문항을 끝까지 수행하고 provider failure로 중단되지 않아야 한다.
2. **Schema Valid Rate**: 다음 node가 읽을 수 있는 구조화 출력을 안정적으로 반환해야 한다.
3. **Question Type Accuracy · Macro-F1**: gold가 있는 35문항에서 올바른 질문 유형을 선택해야 한다.
4. **Raw Calls · Cost**: 같은 70 outputs에 필요한 retry와 비용이 적어야 한다.
5. **Latency**: 위 품질 조건을 통과한 후보끼리 비교한다. 빠르더라도 schema와 route가 불안정하면 채택하지 않는다.

**전체 모델 품질 결과**

| Model ID | Provider | Status | Recorded Outputs | Schema Valid Outputs | Schema Valid Rate | Error Breakdown | Question Type Accuracy | Macro-F1 | Stage 1 Decision |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| `openai/gpt-6-luna` | Azure | `complete_with_errors` | 70/70 | **66** | **0.943** | `ValidationError` 3 · `APITimeoutError` 1 | **1.000 (35/35)** | **1.000** | **Selected** |
| `anthropic/claude-haiku-5.5` | Google | `complete_with_errors` | 70/70 | 48 | 0.686 | `ValidationError` 22 | 0.629 (22/35) | 0.724 | Runner-up |
| `cohere/command-a-plus` | Cohere | `complete_with_errors` | 70/70 | 20 | 0.286 | `ValidationError` 50 | 0.229 (8/35) | 0.356 | Not selected |
| `meta/muse-glimmer-30b` | DeepInfra | `complete_with_errors` | 70/70 | 1 | 0.014 | `ValidationError` 67 · `APITimeoutError` 2 | 0.029 (1/35) | 0.071 | Not selected |
| `deepseek/deepseek-v4.1-flash` | Morph | `provider_stopped` | 3/70 | 0 | `Not Comparable` | `RateLimitError` 3 | `Not Comparable` | `Not Comparable` | Not selectable in this run |

**전체 모델 실행·비용 결과**

| Model ID | Raw Calls | Budget-Accounted Cost | Reported Cost Sum | Reported Cost Calls | p50 Latency | p95 Latency | Elapsed Time |
|---|---:|---:|---:|---:|---:|---:|---:|
| `openai/gpt-6-luna` | **83** | **$0.0135496** | $0.0109729 | 75 | 2.805s | 12.865s | 314.219s |
| `anthropic/claude-haiku-5.5` | 121 | $0.0314090 | $0.0294164 | 114 | **2.367s** | 7.791s | 243.718s |
| `cohere/command-a-plus` | 177 | $0.0875172 | $0.0840432 | 170 | 4.406s | **6.071s** | 287.156s |
| `meta/muse-glimmer-30b` | 205 | $0.0824471 | $0.07502582 | 202 | 5.055s | 8.597s | 448.094s |
| `deepseek/deepseek-v4.1-flash` | 3 | $0.00183318 | $0.0000000 | 0 | 0.297s | 1.197s | 1.875s |

전체 350 planned outputs 중 283개가 기록됐고, schema-valid outputs는 135개다. raw calls는 589회다. `Budget-Accounted Cost` 합계는 `$0.21675608`, provider가 cost를 보고한 561회 호출의 `Reported Cost Sum`은 `$0.19945832`, 전체 elapsed time 합계는 1,295.062초다. cost가 보고되지 않은 호출이 있으므로 어느 값도 단독으로 실제 총 청구액이라 부르지 않는다.

모델별 판단은 다음과 같다.

- `openai/gpt-6-luna`: 70문항을 완료하면서 가장 높은 Schema Valid Rate와 유일한 35/35 Question Type Accuracy를 기록했고, 완료 모델 중 raw calls와 Budget-Accounted Cost도 가장 낮아 선정했다.
- `anthropic/claude-haiku-5.5`: latency는 더 짧지만 Schema Valid Rate와 routing 정확도가 Luna보다 크게 낮아 runner-up으로 남겼다.
- `cohere/command-a-plus`: 70문항은 완료했지만 50개 schema failure와 높은 retry 비용 때문에 제외했다.
- `meta/muse-glimmer-30b`: schema-valid output이 1/70뿐이어서 현재 출력 계약의 수퍼바이저로 사용할 수 없다고 판단했다.
- `deepseek/deepseek-v4.1-flash`: 3회 연속 RateLimitError로 중단돼 품질 비교가 불가능하다. 낮은 품질로 탈락한 것이 아니라 이번 실행에서 operational eligibility를 입증하지 못해 선택할 수 없는 상태다.

`openai/gpt-6-luna`는 `anthropic/claude-haiku-5.5`보다 p50·p95 latency가 느렸지만, Schema Valid Rate가 25.7%p 높고 Question Type Accuracy가 37.1%p 높았다. raw call은 38회 적고 Budget-Accounted Cost도 약 56.9% 낮았다. 수퍼바이저는 빠른 자유 응답보다 schema와 route 정확도가 우선이므로 latency 열위를 감수하고 `openai/gpt-6-luna`를 선택한다.

`Question Type Accuracy`와 Macro-F1은 gold가 있는 35문항만 채점했다. 이 제한을 결과표에 유지하되, 현재 실측 기준 수퍼바이저 모델은 `openai/gpt-6-luna`로 최종 확정한다.

#### 7-2의 용어는 다음과 같습니다.

Model ID(모델 식별자) : 평가에 사용한 모델의 정확한 이름을 보여준다.

Provider(실행 제공업체) : 해당 모델을 실제 서버에서 실행한 업체를 보여준다.

Status(실행 상태) : 70문항 실행의 완료·오류·중단 상태를 보여준다.

Recorded Outputs(기록된 출력 수) : 70문항 중 성공이나 실패 결과가 기록된 문항 수를 보여준다.

Schema Valid Outputs(스키마 유효 출력 수) : 정해진 JSON 형식을 정확하게 지킨 출력 수를 보여준다.

Schema Valid Rate(스키마 유효율) : 전체 문항 중 정해진 JSON 형식을 지킨 출력의 비율을 보여준다.

Error Breakdown(오류 구성) : 발생한 오류의 종류와 각각의 발생 횟수를 보여준다.

Question Type Accuracy(질문 유형 정확도) : 정답 label이 있는 35문항에서 질문 유형을 정확히 분류한 비율을 보여준다.

Macro-F1(매크로 F1) : 각 질문 유형의 분류 성능을 문항 수와 관계없이 동일한 비중으로 평균 내어 보여준다.

Stage 1 Decision(1단계 판단) : 1단계 평가에서 모델이 선정·차순위·제외·비교 불가 중 어디에 해당하는지 보여준다.

Raw Calls(실제 API 호출 수) : 최초 호출과 schema 재시도를 포함해 API에 실제로 요청한 전체 횟수를 보여준다.

Budget-Accounted Cost(예산 반영 비용) : provider가 보고한 비용과 비용이 보고되지 않은 호출의 보수적 예약액을 합쳐 예산에서 차감한 값을 보여준다.

Reported Cost Sum(보고된 비용 합계) : provider가 실제 비용을 반환한 호출들만 합산한 값을 보여준다.

Reported Cost Calls(비용 보고 호출 수) : provider가 비용 정보를 반환한 API 호출의 수를 보여준다.

p50 Latency(응답시간 중앙값) : 전체 호출의 절반이 이 시간 안에 완료됐음을 보여준다.

p95 Latency(95백분위 응답시간) : 전체 호출의 95%가 이 시간 안에 완료됐음을 보여준다.

Elapsed Time(전체 실행시간) : 해당 모델의 평가 프로세스를 시작해서 종료할 때까지 걸린 총시간을 보여준다.

#### 7-3. Measured Comparison Table

현재 수퍼바이저 선택 실험에서 실제로 측정한 공통 metric만 표시한다. `deepseek/deepseek-v4.1-flash`는 3회 연속 `RateLimitError`로 3/70에서 중단돼 두 값 모두 비교 대상으로 사용하지 않는다.

| Model ID | Question Type Macro-F1 | p95 Latency |
|---|---:|---:|
| `openai/gpt-6-luna` | **1.000** | 12.865s |
| `anthropic/claude-haiku-5.5` | 0.724 | 7.791s |
| `cohere/command-a-plus` | 0.356 | **6.071s** |
| `meta/muse-glimmer-30b` | 0.071 | 8.597s |
| `deepseek/deepseek-v4.1-flash` | `Not Comparable` | `Not Comparable` |

### 8. 저장과 비용 통제

- 실행 manifest와 집계 결과 예정 위치: `evals/results/supervisor/<run-id>/`
- 문서 본문이나 사용자 입력이 들어간 raw response는 local/private 저장을 기본으로 하고 저장소에 commit하지 않는다.
- 저장소에는 재현에 필요한 hash, 조건, aggregate, redacted failure만 남긴다.
- 주 실행 상한은 retry 제외 350 supervisor outputs다.
- 모든 70문항·모든 후보쌍·두 위치를 쓰는 pairwise 상한은 1,400 judge decisions다.
- robustness와 end-to-end 호출은 별도 manifest와 별도 예산 상한을 승인받기 전 실행하지 않는다.
- 2026-11-04 OpenRouter 공개 catalog 확인값은 다음과 같다. 이는 `[Public Specification]`이며 실제 청구액이 아니다.

| Model ID | Input Price per 1M Tokens | Output Price per 1M Tokens | ZDR Model Filter | 70 Primary Outputs Reserved Cost |
|---|---:|---:|---|---:|
| `anthropic/claude-haiku-5.5` | $0.10 | $0.50 | available | $0.083866 |
| `openai/gpt-6-luna` | $0.10 | $0.50 | available | $0.083866 |
| `deepseek/deepseek-v4.1-flash` | $0.045 | $0.50 | available | $0.042668 |
| `meta/muse-glimmer-30b` | $0.30 | $1.20 | available | $0.246221 |
| `cohere/command-a-plus` | $0.30 | $1.50 | available | $0.251597 |

`70 Primary Outputs Reserved Cost`는 실제 token 사용량이 아니라 실행기의 보수적 예약식(UTF-8 byte 수 + 8,192 input token 상한, output 256 tokens)으로 계산했다. 5종 합계는 약 `$0.708218`이다.

실행기는 호출 전에 이 보수값을 예약하되, 응답에 OpenRouter `usage.cost`가 있으면 해당 호출의 예약값을 실제 보고 비용으로 정산한다. `usage.cost`가 없거나 호출 자체가 실패하면 과소 집계를 막기 위해 예약값을 유지한다. 따라서 예산 cap은 실제 보고 비용과 미보고 호출의 보수값을 합친 **budget-accounted cost**에 적용한다.

- **승인 monetary ceiling**: 모델별 `$0.10`, `$0.10`, `$0.07`, `$0.30`, `$0.30`; 전체 `$0.87`. 실제 `Budget-Accounted Cost`는 합계 `$0.21675608`이었다.
- **retry ceiling**: case당 schema 오류 최대 2회(첫 호출 포함 최대 3회). SDK·network 자동 retry는 0회다.
- **price ceiling**: 요청마다 `provider.max_price`를 공개 catalog의 model 단가로 고정한다. ZDR endpoint가 이보다 비싸면 더 비싼 endpoint로 보내지 않고 오류로 남긴다.
- **stop condition**: monetary/time/raw-call ceiling, ZDR model filter 미통과, frozen hash·prompt hash·provider policy 불일치, 연속 provider 장애가 확인되면 중단한다.
- judge 1,400판정, robustness, end-to-end는 judge model과 별도 monetary ceiling을 승인받기 전 실행하지 않는다.

### 9. 현재 구현 범위와 남은 label

- 실행기: `evals/runners/run_supervisor_models.py`
- API 없는 준비: `uv run --no-sync python -m evals.runners.run_supervisor_models plan <새 결과 폴더>`
- API 없는 기존 호출 증거 가져오기: `uv run --no-sync python -m evals.runners.run_supervisor_models import-evidence <새 결과 폴더> --source <과거 결과 폴더>`
- smoke 실행: `uv run --no-sync python -m evals.runners.run_supervisor_models smoke <결과 폴더> --model <full model ID> --max-usd <승인된 상한> --confirm-live`
- model별 본 실행: `uv run --no-sync python -m evals.runners.run_supervisor_models run <결과 폴더> --model <full model ID> --max-usd <승인된 상한> --confirm-live`
- 본 실행은 위 명령에 `--run-index 1`을 붙여 후보별 70건을 실행했다.
- 본 실행은 같은 manifest hash의 smoke 또는 원본 hash가 유지된 `provider_evidence.json`이 없으면 시작하지 않는다. evidence는 동일 dataset·prompt·provider policy의 exact model 호출만 허용하고 원본 manifest와 결과 파일이 바뀌면 실행 전에 거부한다. schema 불일치는 실패 output으로 측정하되 provider 응답이 확인되면 본 실행 대상에 포함한다. 본 실행은 검증된 provider를 `provider.only`로 고정하고 응답 provider가 달라지면 중단한다.
- API 호출 없이 준비한 다음 본 테스트 폴더는 `evals/results/supervisor/2026-11-04-main-ready-v1/`이다. `2026-11-04-preflight-v5/`에서 3개 모델, `2026-11-04-routing-fix-smoke-v1/`에서 2개 모델의 호출 증거를 원본 hash와 함께 가져왔다. 이것은 새 smoke나 새 본 테스트 결과가 아니다.

### 9-1. 최종 실측 결과 — 후보별 70문항 1회

실행 폴더는 `evals/results/supervisor/2026-11-04-stage1-v1/`, 집계 파일은 `stage1_summary.json`이다. `Schema Valid Rate`와 `Question Type Accuracy`는 실패 output을 성공으로 간주하지 않는다. `deepseek/deepseek-v4.1-flash`는 3건 연속 `RateLimitError`로 중단됐으므로 품질 점수 비교 대상이 아니다.

| Model ID | Status | Recorded Outputs | Schema Valid Rate | Question Type Accuracy | Macro-F1 | Raw Calls | Budget-Accounted Cost | Reported Cost Sum | p50 Latency | p95 Latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | `complete_with_errors` | 70/70 | 0.686 (48/70) | 0.629 (22/35) | 0.724 | 121 | $0.031409 | $0.0294164 | 2.367s | 7.791s |
| `openai/gpt-6-luna` | `complete_with_errors` | 70/70 | 0.943 (66/70) | 1.000 (35/35) | 1.000 | 83 | $0.0135496 | $0.0109729 | 2.805s | 12.865s |
| `deepseek/deepseek-v4.1-flash` | `provider_stopped` | 3/70 | `Not Comparable` | `Not Comparable` | `Not Comparable` | 3 | $0.00183318 | $0.0000000 | 0.297s | 1.197s |
| `meta/muse-glimmer-30b` | `complete_with_errors` | 70/70 | 0.014 (1/70) | 0.029 (1/35) | 0.071 | 205 | $0.0824471 | $0.07502582 | 5.055s | 8.597s |
| `cohere/command-a-plus` | `complete_with_errors` | 70/70 | 0.286 (20/70) | 0.229 (8/35) | 0.356 | 177 | $0.0875172 | $0.0840432 | 4.406s | 6.071s |

전체 350개 계획 중 283개 output이 기록됐고 schema-valid output은 135개다. raw call은 589회, `Budget-Accounted Cost` 합계는 `$0.21675608`, provider가 `usage.cost`를 보고한 호출 561회의 합계인 `Reported Cost Sum`은 `$0.19945832`다. 두 비용은 정의가 다르므로 실제 총 청구액으로 서로 대체하지 않는다.

실측 결과 `openai/gpt-6-luna`가 schema·routing 정확도에서 가장 높고, 완료 모델 중 `anthropic/claude-haiku-5.5`가 두 번째다. `openai/gpt-6-luna`를 최종 수퍼바이저 모델로 확정한다. `deepseek/deepseek-v4.1-flash`는 품질 열위가 아니라 이번 provider rate limit 때문에 비교 불가로 남긴다.
- 저장값: parsed decision, response ID, finish reason, usage, latency, retry count, sanitized error type, budget, deterministic summary. prompt 원문·raw response·예외 원문은 저장하지 않는다.
- 현재 objective gold: 관련 35건의 `question_type`만 동결 파일에 있다. 비관련 35건은 `question_type`이 비어 있으므로 출력은 70건 모두 수집하되 `Question Type Accuracy` 분모에서는 제외하고 `Known Limitation.unscored_case_count=35`와 ID 목록으로 보고한다. 이것은 문항을 줄이거나 임의 label을 만드는 방식으로 고치지 않는다.
- `required_evidence`, `next_action`, 비관련 35건의 route gold는 두 사람 합의 label file이 생기기 전 점수화하지 않는다. 코드가 `expected`나 `gold_chunks`에서 임의로 정답을 만들지 않는다.
- OpenRouter ZDR endpoint parameter 계약: Haiku 5.5는 `temperature`를 보내지 않고 `max_tokens`를 쓰며, GPT-6 Luna는 `temperature`를 보내지 않고 `max_completion_tokens`를 쓴다. 나머지 후보는 `temperature=0`, `max_tokens`를 유지한다. `require_parameters=true`, ZDR, data collection deny, 가격 상한은 완화하지 않는다.
- 동일 model·case·run의 최신 상태를 사용하고, accuracy는 gold가 있는 35문항을 분모로 계산한다. schema valid rate는 실패·누락을 포함한 모델별 70 planned outputs를 분모로 쓴다.
- 재개 실행은 저장된 `cumulative_raw_calls`와 `cumulative_reserved_usd`를 전체 cap에서 차감한다. 이미 세 번 schema 실패한 output은 확정값으로 두며 다시 호출하지 않는다. provider 오류 3회 연속이면 pause하고 rate limit·예산 차단 output만 후속 재개 대상으로 남긴다.
- `plan`은 주 실행 manifest와 함께 1,400개 blind pairwise A/B swap 계획 및 원문 내부는 건드리지 않고 앞뒤 빈 줄만 추가한 robustness 70건 계획을 만든다. 두 계획은 judge model·별도 비용 승인 전에는 실행하지 않는다. end-to-end는 최종 그래프 구조가 정해진 뒤 별도 preregistration과 예산으로 실행한다.

## AC (Given-When-Then)

**AC-01 · full model ID 보존**
- GIVEN: 후보 5종의 manifest와 결과표
- WHEN: model 식별자를 검사하면
- THEN: `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus`만 있고 축약명은 없다.

**AC-02 · 실행 완결성**
- GIVEN: supervisor 선택 실험이 종료됨
- WHEN: unique `(model_id, case_id, run_index)`와 중단 사유를 세면
- THEN: 각 후보는 run index 1의 최대 70개 결과 또는 명시적인 provider stop을 가진다.

**AC-03 · 동결 평가셋 보존**
- GIVEN: 실행 전후 저장소
- WHEN: `evals/FROZEN.json`으로 hash 검사를 실행하면
- THEN: `dataset_v2.jsonl` 70건과 hash가 모두 유지된다.

**AC-04 · metric 추적 가능성**
- GIVEN: 최종 결과표의 값 하나
- WHEN: metric metadata를 따라가면
- THEN: source type, numerator, denominator, formula, direction, included/excluded case ID와 raw run ID를 확인할 수 있다.

**AC-05 · pairwise 위치 편향 통제**
- GIVEN: 같은 두 candidate output
- WHEN: A/B 위치를 바꿔 blind judge를 실행하면
- THEN: 두 판정과 `Position-Swap Consistency`가 함께 저장되며 불일치는 자동 승리로 처리되지 않는다.

**AC-06 · privacy fail closed**
- GIVEN: 후보의 유일 endpoint가 ZDR 또는 data collection 조건을 충족하지 않음
- WHEN: 실행기가 endpoint policy를 확인하면
- THEN: 평가 입력을 보내지 않고 `Not Measured`와 차단 이유를 기록한다.

**AC-07 · 실측과 추정 분리**
- GIVEN: provider가 actual billing cost 또는 token class를 보고하지 않음
- WHEN: 결과를 집계하면
- THEN: 누락값은 `Not Reported`이며 `[Estimated]` 값을 `[Measured]`나 `Actual Total Cost`로 표시하지 않는다.

**AC-08 · 결과 전 모델 미확정**
- GIVEN: 이 평가가 완료되지 않음
- WHEN: 설계 문서나 보고서를 검토하면
- THEN: 어떤 후보도 최종 수퍼바이저로 확정되어 있지 않고 참고 노드 그림도 최종 구조로 표시되지 않는다.
