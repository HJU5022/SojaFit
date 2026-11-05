# 수퍼바이저 모델 2차 평가 간단 보고서

작성일: 2026-11-05 · 상태: 2차 실측 보고서

## 평가 개요

동결된 `evals/dataset_v2.jsonl` 70문항(SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`)을 6개 모델에서 각 1회 재측정했다. 여섯 모델 모두 70문항을 시도했다. `Question Type Accuracy`는 gold가 있는 35문항으로 계산하고, 나머지 35문항은 채점하지 않았다. 평가 조건은 [2차 사전 등록](../experiments/supervisor-stage2-six-models.md)을 따른다.

## 주요 실측값

| Model ID | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Raw Calls | Budget-Accounted Cost | p95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 46/70 | 21/35 | 0.678 | 132 | US$0.034696100 | 7.500초 |
| `openai/gpt-6-luna` | 65/70 | 34/35 | 0.987 | 84 | US$0.012544100 | 13.156초 |
| `deepseek/deepseek-v4.1-flash` | 62/70 | 29/35 | 0.882 | 94 | US$0.008050050 | 33.266초 |
| `meta/muse-glimmer-30b` | 1/70 | 1/35 | 0.071 | 208 | US$0.077155040 | 5.938초 |
| `cohere/command-a-plus` | 21/70 | 9/35 | 0.393 | 173 | US$0.085608900 | 6.157초 |
| `typesafe/jev-1.14` | 70/70 | 33/35 | 0.947 | 70 | US$0.002689092 | 0.438초 |

표 읽는 법: `Model ID`는 실제 비교한 모델의 전체 이름이다. `Schema Valid Rate`는 70문항 중 다음 노드가 읽을 수 있는 결정을 낸 비율, `Question Type Accuracy`는 유형 정답이 있는 35문항 중 유형을 맞힌 비율이다. `Question Type Macro-F1`은 네 질문 유형의 F1을 같은 비중으로 평균한 값이며 1에 가까울수록 좋다. `Raw Calls`는 재시도를 포함한 실제 호출 횟수다. `Budget-Accounted Cost`는 보고된 비용과 미보고 호출의 예약액을 합친 예산 관리값, `p95 Latency`는 문항별 처리 시간의 95백분위수다.

Jev는 Decisions API의 typed answer를 사용하고 나머지 5종은 Chat Completions JSON을 사용하므로, `Schema Valid Rate`를 동일한 JSON 생성 능력으로 해석할 수는 없다. `Budget-Accounted Cost`는 실제 전체 청구액과 같지 않다. 본 테스트 6종의 합계는 US$0.220743282로 등록 상한 US$0.88 이내다.

## 1차 대비 확인된 변화

- `openai/gpt-6-luna`: Accuracy **35/35 → 34/35**, Schema Valid Rate **66/70 → 65/70**. 줄어든 1건(`draft30-e05`)은 오분류가 아니라 형식 검증 실패다.
- `typesafe/jev-1.14`: Accuracy **33/35 → 33/35**, Schema Valid Rate **70/70 → 70/70**. 오분류 문항 `draft30-e04`, `draft30-m05`도 동일하다.
- `deepseek/deepseek-v4.1-flash`: 1차에는 provider 오류로 **3/70에서 중단**됐지만 2차에는 **70/70을 시도**했다. 1차의 품질 점수와 직접 증감을 계산할 수는 없다.
- `anthropic/claude-haiku-5.5`는 Accuracy **22/35 → 21/35**, `cohere/command-a-plus`는 **8/35 → 9/35**로 각각 1문항 변했다. `meta/muse-glimmer-30b`는 **1/35**로 같았다. 이 정도 변화만으로 성능 개선·악화를 단정하지 않는다.

## 해석과 한계

2차에서는 `openai/gpt-6-luna`가 채점된 질문 유형을 가장 많이 맞혔다(34/35). `typesafe/jev-1.14`는 유효 결정 70/70과 가장 낮은 `Budget-Accounted Cost`·p95 Latency를 기록했다. 이 결과만으로 기존 Luna 선정 결정을 변경하지 않는다.

Jev의 유효 결정 70/70은 출력 형식 기준이다. Jev가 `out_of_scope`로 분류한 6건 중 4건은 `next_action=refuse`가 아닌 검색·회로 노드를 골랐다. 이 `Routing Consistency` 오류는 [상세 결과](supervisor-stage2-results.md)에 문항 ID와 함께 기록했으며, 프롬프트를 바꾼 결과로 재해석하지 않는다.

두 회차는 **같은 문항**을 사용하므로 독립 평가셋 성능을 증명하지 않는다. 정확도는 gold가 있는 35문항에 한정된다. `Safety-Failure Case Count`는 별도 사람 판정이 없어 `Not Measured`다. 생성형 5종의 저장된 usage에는 일부 이전 schema 재시도 비용이 빠질 수 있어 실제 전체 청구액을 확정할 수 없다.
Jev의 `--max-usd`도 호출 전 입력 비용 추정으로 다음 job을 차단하는 관리값이며, 마지막 job의 실제 비용이 추정보다 크면 계획값을 넘을 수 있다. 이번 저장 결과가 계획값을 넘었다는 뜻은 아니다.

## 근거

- [2차 상세 결과와 원시 파일별 SHA-256](supervisor-stage2-results.md)
- [2차 사전 등록](../experiments/supervisor-stage2-six-models.md)
- 2차 전용 집계: `../../evals/results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json` (SHA-256 `2c4ef11f52a8467c390af8e34ec3ae9e77fc958876b79ccc974973b6d6f8570b`)
