# 수퍼바이저 모델 5종 비교

상태: 동결 v2 70문항을 후보별 1회 비교했으며, 이 실험의 최종 선정 모델은 `openai/gpt-6-luna`다. 이 PR은 평가 방법, 경량 집계 JSON, 모델별 핵심 실측값과 선정 결론만 기록한다.

## Why

- **페르소나**: SojaFit의 수퍼바이저 모델을 품질뿐 아니라 안정성·비용까지 근거로 선택해야 하는 에이전트·평가 담당자
- **상황**: 수퍼바이저는 사용자 입력을 읽고 질문 종류, 필요한 근거, 다음 실행 경로를 정한다.
- **문제**:
  1. 공개 benchmark만으로는 실제 평가 문항에서의 route 정확도와 schema 안정성을 알 수 없다.
  2. 저렴한 모델도 schema 오류와 재시도가 많으면 전체 비용과 지연이 커질 수 있다.
  3. 품질·비용·latency를 한 점수로 합치면 어떤 이유로 모델을 선택했는지 설명하기 어렵다.

## Goal

- 아래 후보 5종을 같은 70문항과 같은 입력·출력 계약으로 1회씩 비교한다.
- 후보별 schema 준수, 질문 유형 분류, 호출 실패, 비용, latency를 분리해서 판단한다.
- 실험 결과로 수퍼바이저 모델 하나를 선정하되, 최종 답변 생성 모델이나 전체 멀티에이전트 구조까지 확정하지 않는다.

### 후보 모델

- `anthropic/claude-haiku-5.5`
- `openai/gpt-6-luna`
- `deepseek/deepseek-v4.1-flash`
- `meta/muse-glimmer-30b`
- `cohere/command-a-plus`

## What

### 평가 대상

- 평가셋: 동결 `evals/dataset_v2.jsonl` 70문항
- 실행 횟수: 후보별 1회
- 입력: 실제 사용자 입력과 동일한 본문
- 출력: 질문 유형, 필요한 근거, 다음 행동, reason code를 담은 고정 JSON schema
- 제외: retrieval, reranker, 최종 답변 생성, LLM judge, pairwise 비교, robustness, end-to-end 평가

### 공통 조건

| Condition | Value |
|---|---|
| Dataset | Frozen v2, 70 cases |
| Runs per Model | 1 |
| Provider Route | OpenRouter ZDR endpoint only |
| Data Collection | deny |
| Provider Fallback | disabled |
| SDK Retry | disabled |
| Schema Retry | bounded |
| Prompt | identical for all candidates |
| Gold Exposure | prohibited |

### Metric 정의

| Metric | Meaning | Direction |
|---|---|---:|
| `Recorded Outputs` | 실행 결과가 성공 또는 실패로 기록된 문항 수 | ↑ |
| `Schema Valid Outputs` | 정해진 JSON schema를 통과한 출력 수 | ↑ |
| `Schema Valid Rate` | 전체 문항 중 schema를 통과한 비율 | ↑ |
| `Question Type Accuracy` | gold label이 있는 문항에서 질문 유형을 맞힌 비율 | ↑ |
| `Macro-F1` | 질문 유형별 F1을 같은 비중으로 평균한 값 | ↑ |
| `Error Breakdown` | 오류 종류별 발생 횟수 | 참고 |
| `Raw Calls` | 최초 호출과 schema 재시도를 합친 실제 호출 수 | ↓ |
| `Budget-Accounted Cost` | 보고된 비용과 미보고 호출의 보수적 예약액을 합친 예산 차감값 | ↓ |
| `Reported Cost Sum` | provider가 비용을 보고한 호출만 합친 값 | ↓ |
| `p50 Latency` | 호출 지연시간 중앙값 | ↓ |
| `p95 Latency` | 호출 지연시간 95백분위수 | ↓ |

## How

### 입력 격리

- 모델에는 평가 문항의 사용자 입력만 전달한다.
- `expected`, `gold_chunks`, 정답 label, 모범 답변은 전달하지 않는다.
- 질문 유형 gold가 없는 문항도 실행 대상에는 포함하지만 정확도 분모에는 넣지 않는다.

### 호출 정책

- 후보별 정확한 full model ID를 사용한다.
- ZDR과 `data_collection=deny`를 만족하는 endpoint만 허용한다.
- provider fallback을 금지한다.
- 호출·시간·비용·schema retry에 상한을 둔다.
- provider 오류가 연속으로 발생하면 해당 후보 실행을 중단하고 실패 이유를 남긴다.

### 저장 경계

- 이 PR에는 평가 방법, 모델별 핵심 실측값, 경량 집계 JSON과 선정 결론만 남긴다.
- 실행 코드, manifest, 모델별 parsed output은 포함하지 않는다.
- 사용자 입력, raw prompt, raw response, 예외 원문, API key는 문서에 기록하지 않는다.
- 집계 원본은 `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json` 한 파일로 제한한다.

## Measured Results

`Question Type Accuracy`와 `Macro-F1`은 gold label이 있는 35문항을 분모로 한다. `deepseek/deepseek-v4.1-flash`는 provider 중단으로 품질 비교 대상에서 제외한다.

| Model ID | Schema Valid Rate | Question Type Accuracy | Macro-F1 | Raw Calls | Budget-Accounted Cost | p95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| `openai/gpt-6-luna` | **0.943** | **1.000** | **1.000** | **83** | **$0.0135496** | 12.865s |
| `anthropic/claude-haiku-5.5` | 0.686 | 0.629 | 0.724 | 121 | $0.0314090 | 7.791s |
| `cohere/command-a-plus` | 0.286 | 0.229 | 0.356 | 177 | $0.0875172 | **6.071s** |
| `meta/muse-glimmer-30b` | 0.014 | 0.029 | 0.071 | 205 | $0.0824471 | 8.597s |
| `deepseek/deepseek-v4.1-flash` | `Not Comparable` | `Not Comparable` | `Not Comparable` | 3 | $0.00183318 | `Not Comparable` |

`Budget-Accounted Cost`는 provider가 보고한 비용과 비용이 보고되지 않은 호출의 보수적 예약액을 합친 예산 차감값이며 실제 총 청구액과 같다고 단정하지 않는다.

## Final Supervisor Model Selection

이 실험의 최종 선정 모델은 `openai/gpt-6-luna`다.

선정 기준은 metric을 임의 가중합하지 않고 다음 우선순위로 적용했다.

1. 70문항 실행을 끝까지 수행할 수 있는가
2. 다음 node가 읽을 수 있는 schema를 안정적으로 반환하는가
3. gold가 있는 문항에서 질문 유형을 올바르게 분류하는가
4. 같은 결과를 얻기 위한 재시도와 비용이 적은가
5. 위 품질 조건을 통과한 후보 사이에서 latency가 낮은가

`openai/gpt-6-luna`는 완료 후보 중 schema 안정성과 질문 유형 분류가 가장 좋았고, 차순위보다 적은 호출과 낮은 예산 차감으로 결과를 냈다. latency는 차순위보다 불리했지만 수퍼바이저에서는 빠른 자유 응답보다 안정적인 구조화 출력과 route 정확도가 우선이므로 이 차이를 수용했다.

이 결론의 범위는 수퍼바이저의 질문 분류와 다음 route 선택이다. 최종 답변 생성 모델을 선정한 것이 아니며, 전체 그래프와 서브에이전트 수를 확정한 것도 아니다.

현재 서비스 정본은 ADR 0010과 `SPEC.md`의 임시 Haiku 설정이다. `OSC` 브랜치는 주요 문서와 ADR을 직접 수정할 수 없으므로, Luna를 서비스 기본값으로 적용하는 변경은 조장이 정본을 갱신한 뒤 별도로 수행한다.

## Known Limitations

- `Question Type Accuracy`와 `Macro-F1`은 gold label이 있는 문항만 채점한다.
- `required_evidence`, `next_action`, 비관련 문항의 route는 사람 합의 gold가 없어 점수화하지 않는다.
- provider 중단 후보는 품질 열위로 단정하지 않고 이번 실행에서 비교 불가로 남긴다.
- 이 실험은 supervisor-only 비교이며 end-to-end 서비스 성공률을 증명하지 않는다.

## AC (Given-When-Then)

### AC-01 · full model ID 보존

- GIVEN: 후보 목록을 검토할 때
- WHEN: model 식별자를 확인하면
- THEN: 다섯 후보가 축약되지 않은 full model ID로 기록되어 있다.

### AC-02 · 동일 조건 비교

- GIVEN: 후보별 실행 조건을 비교할 때
- WHEN: dataset, prompt, schema, provider policy를 확인하면
- THEN: 모델 ID 외 조건이 동일하다.

### AC-03 · 동결 평가셋 보존

- GIVEN: 평가 전후 저장소를 비교할 때
- WHEN: `evals/FROZEN.json`으로 검사하면
- THEN: `dataset_v2.jsonl` 70문항과 동결 hash가 유지된다.

### AC-04 · privacy fail closed

- GIVEN: 후보 endpoint가 ZDR 또는 data collection 조건을 충족하지 않을 때
- WHEN: 실행 여부를 결정하면
- THEN: 평가 입력을 보내지 않고 차단 이유를 기록한다.

### AC-05 · 선정 범위 구분

- GIVEN: 실험 결론과 서비스 정본을 함께 검토할 때
- WHEN: `openai/gpt-6-luna` 선정 문구를 확인하면
- THEN: 실험상 수퍼바이저 선정임이 명시되고, 서비스 기본값과 최종 그래프는 조장 소유 정본 갱신 전까지 확정된 것으로 표시하지 않는다.
