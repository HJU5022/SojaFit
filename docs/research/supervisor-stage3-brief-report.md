# 수퍼바이저 6종 3차 평가 간단 보고서

측정일: 2026-11-05 · 상태: 3차 실행 종료

동결 v2 70문항을 여섯 모델에서 run_index=3으로 한 번씩 실행했다. 유형 정답률은 관련 gold 35문항만 채점한다. 같은 문항의 반복이므로 독립 평가셋 성능으로 해석하지 않는다.

| Model ID | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Inconsistent Action | Raw Calls | Budget-Accounted Cost (USD) | p95 Latency (s) |
|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 50/70 | 23/35 | 0.758 | 0/7 | 120 | 0.030994100 | 7.891 |
| `openai/gpt-6-luna` | 65/70 | 33/35 | 0.960 | 0/7 | 86 | 0.013300100 | 15.078 |
| `deepseek/deepseek-v4.1-flash` | 7/70 | 2/35 | 0.125 | 0/5 | 200 | 0.026067446 | 8.219 |
| `meta/muse-glimmer-30b` | 1/70 | 1/35 | 0.071 | Not Applicable (0/0) | 206 | 0.080733380 | 11.735 |
| `cohere/command-a-plus` | 21/70 | 8/35 | 0.343 | 0/2 | 173 | 0.085510500 | 5.765 |
| `typesafe/jev-1.14` | 70/70 | 33/35 | 0.947 | 4/6 | 70 | 0.002689092 | 0.454 |

표 읽는 법: Schema Valid Rate는 형식 통과 / 70, Question Type Accuracy는 유형 정답 / 35, Macro-F1은 네 유형 F1 평균이다. Inconsistent Action은 자체 범위 밖 예측 중 거절하지 않은 비율이며 올바른 거절 정답률이 아니다. Raw Calls는 재시도 포함 호출 수, Budget-Accounted Cost는 기록 비용·예약액의 관리값, p95 Latency는 문항별 처리 시간 95백분위수(초)다.

본 실행 비용 관리값 합계는 US$0.239294618000, Raw Calls는 855회다. 실제 청구액과 smoke 비용 전체는 확인하지 않았다.

## 2차 대비 유형 정답 변화

- `anthropic/claude-haiku-5.5`: 21/35 → 23/35; 형식 통과 46/70 → 50/70.
- `openai/gpt-6-luna`: 34/35 → 33/35; 형식 통과 65/70 → 65/70.
- `deepseek/deepseek-v4.1-flash`: 29/35 → 2/35; 형식 통과 62/70 → 7/70.
  Provider도 Morph → Relace로 달라져 점수 변화를 모델 자체에만 귀속할 수 없다.
- `meta/muse-glimmer-30b`: 1/35 → 1/35; 형식 통과 1/70 → 1/70.
- `cohere/command-a-plus`: 9/35 → 8/35; 형식 통과 21/70 → 21/70.
- `typesafe/jev-1.14`: 33/35 → 33/35; 형식 통과 70/70 → 70/70.

## 해석

3회 일치율은 세 회차가 모두 유효한 문항만 비교하며 비교 가능한 문항 수를 함께 보고한다. 형식 성공·유형 정답·라우팅 모순·provider 변화·비용·지연을 함께 확인해야 한다. 이번 결과로 기존 운영 모델 결정을 자동 변경하지 않는다.

사용자 결정에 따른 최종 후보는 `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5`의 3종이다. `deepseek/deepseek-v4.1-flash`는 실행 안정성 부족으로 탈락했고, `cohere/command-a-plus`와 `meta/muse-glimmer-30b`도 최종 후보에서 제외했다. 후보의 순위는 제시하지 않는다. Jev의 동작 불일치 4/6과 Haiku의 형식 실패를 포함한 기존 실측 근거는 전부 보존한다.

[상세 결과·문항 변화·원시 파일 hash](supervisor-stage3-results.md), [3차 사전 등록](../experiments/supervisor-stage3-six-models.md)
