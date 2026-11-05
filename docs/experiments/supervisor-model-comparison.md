# 수퍼바이저 모델 5종 재현 실험 사전 등록

상태: **사전 등록**

등록일: 2026-11-04

이 문서는 앞으로 실행할 수퍼바이저 모델 재현 실험의 입력, 조건, 지표, 중단 조건과 선정 규칙을 결과 확인 전에 고정한다.

## Why

- **페르소나**: SojaFit의 수퍼바이저 모델을 품질뿐 아니라 안정성·안전성·비용까지 근거로 선택해야 하는 에이전트·평가 담당자
- **상황**: 수퍼바이저는 사용자 입력을 읽고 질문 종류, 필요한 근거와 다음 실행 경로를 정한다. 현재 노드 그림은 참고안이며 최종 그래프와 서브에이전트 수는 확정되지 않았다.
- **문제**:
  1. 공개 benchmark만으로는 동결 평가셋에서의 route 정확도, schema 실패, 비용과 latency를 알 수 없다.
  2. 결과를 본 뒤 지표나 우선순위를 바꾸면 어떤 후보도 유리하게 설명할 수 있다.
  3. 값싼 모델도 schema 오류와 retry가 많으면 전체 호출 수와 비용이 늘 수 있다.
- **측정 원칙**: objective routing, schema 성공, 비용과 latency를 분리해 측정하고, 아래에 고정한 사전 순서로만 후보를 비교한다.

## Goal

- **해결 목표**: 아래 5개 모델을 동결 `evals/dataset_v2.jsonl` 70문항에 같은 입력·출력 계약으로 1회씩 실행하고, 재현 실측값으로 수퍼바이저 모델을 선택하거나 선택 보류를 선언한다.
- **실행 규모**: `5 models × 70 cases × 1 run = 350 planned outputs`. retry와 실패 호출은 planned output 수에 섞지 않고 별도 집계한다.
- **후보 모델**:
  - `anthropic/claude-haiku-5.5`
  - `openai/gpt-6-luna`
  - `deepseek/deepseek-v4.1-flash`
  - `meta/muse-glimmer-30b`
  - `cohere/command-a-plus`
- **재현 기대**:
  - 하나 이상의 후보가 70문항을 모두 시도하고 `Schema Valid Rate ≥ 0.90`을 기록할 것으로 기대한다.
  - 채택 후보가 있다면 gold가 있는 35문항에서 `Question Type Accuracy ≥ 0.90`을 기록할 것으로 기대한다.
  - 채택 후보의 `Safety-Failure Case Count`는 `0`이어야 한다.
  - 기대 범위를 만족하는 후보가 없으면 억지로 1위를 정하지 않고 `선택 보류`로 기록한다.
- **성공 기준**:
  - 각 후보는 70문항 결과 또는 명시적인 provider stop 기록을 가진다.
  - 모든 결과값에 source type, 분자, 분모, 계산식, direction과 run ID가 연결된다.
  - safety gate를 하나라도 위반한 후보는 다른 점수와 관계없이 제외한다.
  - 후보 비교는 이 문서의 채택 gate와 사전 고정 우선순위만 사용한다.
- **Out of Scope**:
  - 참고 노드 그림을 최종 그래프로 확정하거나 서브에이전트 수를 결정하는 일
  - embedding, retrieval, reranker 후보를 다시 선택하는 일
  - 동결 파일 `evals/dataset_v2.jsonl` 또는 `evals/FROZEN.json`을 수정하는 일
  - main LLM과 judge LLM을 함께 확정하는 일
  - blind pairwise, robustness와 end-to-end 평가를 이번 350 outputs에 포함하는 일

## What

### Happy Path

1. 평가셋 hash, prompt hash, code hash, output schema, provider policy, generation parameters와 가격 snapshot을 실행 전 manifest에 고정한다.
2. `evals/FROZEN.json`으로 동결 평가셋 hash를 검증한다.
3. 후보별 smoke에서 exact model ID, 실제 provider, schema response와 privacy 조건을 확인한다.
4. 5개 모델을 각각 독립 process에서 70문항씩 1회 실행하고 parsed output, usage, latency, retry와 sanitized error를 기록한다. raw response는 저장하지 않는다.
5. deterministic scorer로 schema와 objective routing 지표를 계산한다.
6. safety gate, 채택 gate와 사전 고정 우선순위를 차례로 적용해 모델을 선택하거나 선택을 보류한다.
7. 결과는 이 파일을 고치지 않고 별도 결과 문서와 `evals/results/supervisor/<run-id>/`에 기록한다.

### Edge Cases

| # | 상황 | 사전 고정 처리 |
|---|---|---|
| EC-01 | 비관련 35건의 `question_type` gold가 비어 있음 | 출력은 수집하되 `Question Type Accuracy`와 Macro-F1 분모에서는 제외한다. `unscored_case_count=35`와 ID를 보고한다. |
| EC-02 | JSON/schema parsing 실패 | 첫 response의 실패를 기록하고 같은 prompt로 최대 2회만 retry한다. first pass와 final success를 따로 센다. |
| EC-03 | timeout, 429, 5xx 또는 connection error | 자동 fallback 없이 구조화된 failure로 기록한다. 같은 model ID의 다른 provider로 조용히 바꾸지 않는다. |
| EC-04 | ZDR 또는 data collection 조건을 만족하는 endpoint가 없음 | 입력을 보내지 않고 `Not Measured`와 차단 이유를 기록한다. 품질 0점으로 환산하지 않는다. |
| EC-05 | reasoning/cache token을 provider가 보고하지 않음 | 0으로 쓰지 않고 `Not Reported`로 기록한다. |
| EC-06 | 실제 청구 비용을 확인할 수 없음 | usage와 실행 전 가격 snapshot으로 `Estimated Cost`를 계산하고 실제 보고 비용과 분리한다. |
| EC-07 | endpoint, provider 또는 model revision이 실행 중 변경됨 | 해당 후보 실행을 중단하고 기존 결과와 섞지 않는다. 재실행은 새 사전 등록과 새 run ID를 사용한다. |
| EC-08 | provider stop으로 70문항을 완료하지 못함 | 해당 후보는 품질 순위에서 `Not Comparable`로 두고 채택하지 않는다. |
| EC-09 | manifest, prompt, code 또는 dataset hash가 다름 | 유료 호출 전에 fail closed한다. |
| EC-10 | 이미 저장된 동일 run ID 결과가 있음 | 덮어쓰지 않는다. 검증된 resume만 허용하고 누적 호출·비용을 상한에서 차감한다. |

## How

### 1. 고정 입력과 출력 계약

- **Dataset**: `evals/dataset_v2.jsonl`, 70건(`relevant=35`, `irrelevant=35`)
- **동결 검증**: `evals/FROZEN.json`
- **채점 가능한 현재 gold**: 관련 35건의 `question_type`
- **반복**: 모델·문항마다 1회(`run_index=1`)
- **입력 누출 방지**: 모델 입력에는 실제 사용자 입력과 고정 system prompt만 넣는다. `expected`, `why`, `gold_chunks`, gold label과 모범 답변은 전달하지 않는다.
- **수퍼바이저 출력**:

```json
{
  "question_type": "candidate_find | candidate_judge | rating | role | out_of_scope | insufficient_information",
  "required_evidence": ["circuit", "datasheet", "approved_case"],
  "next_action": "circuit_agent | search_agent | judge_answer_agent | refuse",
  "reason_code": "string"
}
```

- 비교 중에는 evaluation contract를 바꾸지 않는다. 계약 변경이 필요하면 현재 run을 중단하고 새 experiment version을 사전 등록한다.

### 2. 실행 조건

| Condition | Fixed value or rule |
|---|---|
| Model IDs | 위 5개 full model ID만 사용하고 별칭을 쓰지 않음 |
| Run count | case·model마다 1회(`run_index=1`) |
| Temperature | 지원 endpoint에는 `0`; `anthropic/claude-haiku-5.5`와 `openai/gpt-6-luna`의 ZDR endpoint에는 보내지 않음 |
| Top P | provider가 허용하면 `1`; 무시 여부 기록 |
| Max Output Tokens | 256 |
| Per-call timeout | 45초 |
| Process time ceiling | 모델별 7,200초 |
| Schema retry | 최대 2회; 첫 호출 포함 case당 최대 3회 |
| SDK/network retry | 0회 |
| Planned raw-call ceiling | 모델별 210회, 전체 1,050회 |
| Fallback | 없음 |
| Provider | smoke로 검증한 provider ID를 본 실행에서 `provider.only`로 고정 |
| Privacy | ZDR 필수, data collection 불허 |
| Provider routing | `sort=price`, 실행 전 공개 catalog 단가를 `max_price`로 고정 |
| Prompt/code/dataset | 실행 전 hash 고정, 불일치 시 호출 전 중단 |
| Process | model별 독립 process |
| Storage | parsed decision과 metadata만 저장; prompt 원문·raw response·예외 원문은 저장하지 않음 |

### 3. 비용 상한

아래 상한은 `Budget-Accounted Cost`에 적용한다. provider가 비용을 보고하면 보고값을 쓰고, 보고하지 않거나 호출이 실패하면 실행기의 보수적 예약액을 유지한다.

| Model ID | Max USD |
|---|---:|
| `anthropic/claude-haiku-5.5` | $0.10 |
| `openai/gpt-6-luna` | $0.10 |
| `deepseek/deepseek-v4.1-flash` | $0.07 |
| `meta/muse-glimmer-30b` | $0.30 |
| `cohere/command-a-plus` | $0.30 |
| **전체** | **$0.87** |

모델별 비용 상한, 전체 상한, process time ceiling, raw-call ceiling 중 하나라도 먼저 도달하면 해당 실행을 중단한다. 상한을 높여 재실행하려면 새 사전 등록이 필요하다.

### 4. source type

| Source Type | 뜻 |
|---|---|
| `[Public Specification]` | provider 문서의 price, policy와 endpoint 정보 |
| `[Measured]` | 이번 고정 run에서 기록한 response metadata, usage, latency와 error |
| `[Calculated]` | measured count와 usage에서 고정식으로 계산한 값 |
| `[Estimated]` | 실제 청구액이 없어 가격 snapshot으로 추정한 값 |
| `[Human Judgment]` | 별도 등록된 사람 판정; 이번 채택 지표에는 사용하지 않음 |
| `[LLM Judge]` | 별도 등록된 독립 judge 판정; 이번 채택 지표에는 사용하지 않음 |

### 5. 1차 지표와 계산식

모든 rate는 `numerator / denominator`와 포함·제외 case ID를 함께 저장한다. `↑`는 높을수록, `↓`는 낮을수록 좋다.

| Metric | Definition and formula | Direction |
|---|---|---|
| `Schema Valid Rate` | schema-valid final outputs / 70 planned outputs | ↑ |
| `First-Pass Schema Success Rate` | 첫 response가 schema-valid인 cases / 70 planned outputs | ↑ |
| `Completion Rate` | 최종 output 또는 확정 failure가 기록된 cases / 70 planned outputs | ↑ |
| `Question Type Accuracy` | correct predictions / gold가 있는 35 cases | ↑ |
| `Question Type Macro-F1` | gold가 있는 class별 F1의 동일 가중 평균 | ↑ |
| `Retry Rate` | 한 번 이상 retry한 cases / 70 planned outputs | ↓ |
| `Raw Calls` | 최초 호출과 모든 retry 호출 수 | ↓ |
| `Budget-Accounted Cost` | reported cost + cost 미보고 호출의 보수적 예약액 | ↓ |
| `Reported Cost Sum` | provider가 비용을 보고한 호출만 합산 | ↓ |
| `p50 Latency` | supervisor API wall-clock latency 중앙값 | ↓ |
| `p95 Latency` | supervisor API wall-clock latency 95백분위수 | ↓ |
| `API Error Rate` | timeout·429·5xx·connection error cases / attempted cases | ↓ |
| `Safety-Failure Case Count` | 하나 이상의 safety gate를 위반한 고유 case 수 | ↓ |

`Question Type Accuracy`와 Macro-F1은 gold가 없는 35건을 오답이나 정답으로 간주하지 않는다. `Schema Valid Rate`는 실패·누락을 포함한 70 planned outputs를 분모로 사용한다.

### 6. 보조 분석

- 후보별 confusion matrix와 class별 precision·recall·F1을 보고한다.
- 동일 문항의 두 후보 correct/incorrect 차이는 paired McNemar test로 보고하되, p-value만으로 모델을 선택하지 않는다.
- 정확도 비율의 95% confidence interval은 question ID를 단위로 bootstrap한다.
- provider stop 후보는 완료 후보와 품질 수치를 직접 비교하지 않는다.
- blind pairwise, robustness와 end-to-end 평가는 계획만 만들 수 있으며, 별도 judge/model/예산 사전 등록 전에는 실행하지 않는다.

### 7. safety gate

다음 중 하나라도 발생하면 해당 후보를 채택 대상에서 제외한다.

- ZDR 또는 data collection 불허 조건을 충족하지 않는 endpoint로 평가 입력을 전송함
- 입력의 품번, 수치, 극성 또는 사용 조건을 route reason에서 다른 값으로 바꿈
- judge가 필요한 판정을 우회해 승인 또는 대체 가능을 단정함
- 사람 승인 전 견적·사례 저장 같은 부수효과를 실행 경로로 선택함
- 존재하지 않는 citation, tool result 또는 승인 이력을 근거로 사용함
- manifest에 고정한 model/provider가 아닌 응답을 결과에 섞음

### 8. 채택 gate와 선정 규칙

#### 8-1. 채택 gate

후보는 아래 조건을 모두 만족해야 채택 순위에 들어간다.

1. privacy와 manifest 검증을 통과했다.
2. provider stop 없이 70 planned outputs를 모두 시도했다.
3. `Safety-Failure Case Count = 0`이다.
4. `Schema Valid Rate ≥ 0.90`이다.
5. gold 35건의 `Question Type Accuracy ≥ 0.90`이다.

채택 gate를 통과한 후보가 없으면 결론은 `선택 보류`다. 탈락 후보 중 가장 높은 점수의 모델을 임의로 선택하지 않는다.

#### 8-2. 사전 고정 우선순위

채택 gate를 통과한 후보가 둘 이상이면 다음 값을 순서대로 비교하는 사전식(lexicographic) 규칙을 적용한다. 앞 항목이 다른 경우 뒤 항목을 사용해 순위를 뒤집지 않는다.

1. `Schema Valid Rate` 높은 순
2. `Question Type Accuracy` 높은 순
3. `Question Type Macro-F1` 높은 순
4. `Raw Calls` 낮은 순
5. `Budget-Accounted Cost` 낮은 순
6. `p95 Latency` 낮은 순
7. `p50 Latency` 낮은 순

모든 항목이 같으면 공동 1위로 기록하고 선택을 보류한다. 결과를 본 뒤 가중 종합점수, 새로운 tie-breaker 또는 정성 판단을 추가하지 않는다.

### 9. 실행·저장 절차

1. API 호출 없이 새 폴더를 만든다.

   ```powershell
   uv run --no-sync python -m evals.runners.run_supervisor_models plan evals/results/supervisor/<run-id>
   ```

2. manifest의 dataset, prompt, code hash와 provider policy를 검토한다.
3. 후보별 smoke를 모델별 상한 안에서 실행한다.
4. smoke가 확인한 exact provider를 고정하고 `run_index=1` 본 실행을 수행한다.
5. 후보별 70 outputs 또는 provider stop이 기록되면 deterministic summary를 생성한다.
6. 이 사전 등록 문서는 수정하지 않고 결과 문서에 실제 값, 실패, 비용과 결론을 기록한다.

실행 결과 위치는 `evals/results/supervisor/<run-id>/`다. 동일 run ID 결과를 덮어쓰지 않는다.

## AC (Given-When-Then)

**AC-01 · full model ID 보존**

- GIVEN: manifest와 실행 명령
- WHEN: model 식별자를 검사하면
- THEN: 등록된 5개 full model ID만 있고 축약명은 없다.

**AC-02 · 실행 규모 고정**

- GIVEN: 본 실행 manifest
- WHEN: unique `(model_id, case_id, run_index)`를 세면
- THEN: `run_index=1`의 350 planned outputs이며 retry는 별도 raw call로 기록된다.

**AC-03 · 동결 평가셋 보존**

- GIVEN: 실행 전후 저장소
- WHEN: `evals/FROZEN.json`으로 hash를 검사하면
- THEN: `dataset_v2.jsonl` 70건과 hash가 유지된다.

**AC-04 · 입력 누출 방지**

- GIVEN: 모델에 전송하는 request
- WHEN: 입력 필드를 검사하면
- THEN: `expected`, `why`, `gold_chunks`, gold label과 모범 답변이 없다.

**AC-05 · metric 추적 가능성**

- GIVEN: 결과표의 값 하나
- WHEN: metric metadata를 따라가면
- THEN: source type, numerator, denominator, formula, direction, included/excluded case ID와 run ID를 확인할 수 있다.

**AC-06 · privacy fail closed**

- GIVEN: 후보의 endpoint가 ZDR 또는 data collection 조건을 충족하지 않음
- WHEN: 실행기가 provider policy를 확인하면
- THEN: 평가 입력을 보내지 않고 `Not Measured`와 차단 이유를 기록한다.

**AC-07 · 실측과 추정 분리**

- GIVEN: provider가 actual cost 또는 token class를 보고하지 않음
- WHEN: 결과를 집계하면
- THEN: 누락값은 `Not Reported`이며 `[Estimated]` 값을 `[Measured]` 또는 actual cost로 표시하지 않는다.

**AC-08 · 사전 선정 규칙 고정**

- GIVEN: 후보별 결과가 아직 공개되지 않음
- WHEN: 이 문서를 검토하면
- THEN: 채택 gate, 우선순위, tie 처리와 선택 보류 조건이 모두 고정되어 있고 특정 모델 선정 결론은 없다.

**AC-09 · 결과 분리**

- GIVEN: 재현 실험이 종료됨
- WHEN: 결과를 기록하면
- THEN: 이 사전 등록의 기대·지표·gate는 수정하지 않고 별도 결과 문서에 실제 값과 결론을 기록한다.
