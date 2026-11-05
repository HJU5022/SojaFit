# 수퍼바이저 6종 2차 공동 평가 결과

상태: **2차 실측 완료** · 측정일: 2026-11-05

## 범위와 근거

- 사전 등록: [`../experiments/supervisor-stage2-six-models.md`](../experiments/supervisor-stage2-six-models.md), `evals/guides/preregister.md` #32. 실행 전 로컬 번호 `#29`는 `main`의 기존 등록과 중복되어 번호만 정정했다. 최초 smoke 상한 US$0.001이 현재 단가의 호출 전 예약액보다 낮아, **첫 유료 호출 전에** 후보별 상한을 정정한 이력을 두 문서에 남겼다.
- 동결 입력: `evals/dataset_v2.jsonl` 70문항, SHA-256 `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`. 각 모델은 `run_index=2`에서 70문항을 한 번씩 시도했다. `question_type` gold가 있는 35문항만 Accuracy·Macro-F1을 채점했다.
- 원시 결과: 기존 5종 `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_*.json`; Jev `evals/results/supervisor/2026-11-05-jev-stage2-v1/rows.json`. 문항별 상태·응답 metadata·usage를 보존한다.
- 2차 전용 집계: `evals/results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json`, SHA-256 `2c4ef11f52a8467c390af8e34ec3ae9e77fc958876b79ccc974973b6d6f8570b`. 이 파일에 각 원시 결과의 SHA-256, 모델·provider, 지표 계산값과 1차 대비 정오 변화 문항 ID가 있다. 앞서 만든 `stage2_summary.json`은 `Completion Rate`를 유효 결정/70으로 잘못 정의했으므로 로컬 원본만 보존하고 PR 근거 파일에서는 제외한다.

### 원시 결과 무결성

| Model ID | Raw Result File | SHA-256 |
|---|---|---|
| `anthropic/claude-haiku-5.5` | `2026-11-05-stage2-five-v1/rows_anthropic__claude-haiku-5.5.json` | `1b77f40058dff3531eef6da4f18b383fb3fba9582b8b578fbe7ab3a3b87a1a00` |
| `openai/gpt-6-luna` | `2026-11-05-stage2-five-v1/rows_openai__gpt-6-luna.json` | `f2cb9e85c979f73f52e7e0c9625b464e3e4d433c940aed03322654d65a4eb7fa` |
| `deepseek/deepseek-v4.1-flash` | `2026-11-05-stage2-five-v1/rows_deepseek__deepseek-v4.1-flash.json` | `d618dfd94b80b4fafe43bc5c85c47b0d62fe5e91eb13b24c9a70f58262e1fd6a` |
| `meta/muse-glimmer-30b` | `2026-11-05-stage2-five-v1/rows_meta__muse-glimmer-30b.json` | `fa582cebd5392304a170944ad570fce55dff79b3cf2d6a32135d1ccdc2e484d7` |
| `cohere/command-a-plus` | `2026-11-05-stage2-five-v1/rows_cohere__command-a-plus.json` | `396bffb19627acf52d3c2021fd86029781c57b96fe1cd04db5b6aeb4b268bdac` |
| `typesafe/jev-1.14` | `2026-11-05-jev-stage2-v1/rows.json` | `f1995ce2b442d1f7dc72d427a7ffcb2fcf9c1b63dd9a27ee015ee109d4fa0d2d` |

표 읽는 법: `Model ID`는 평가 요청에 사용한 모델 이름, `Raw Result File`은 해당 모델의 문항별 원시 결과 파일이다. 경로는 모두 `evals/results/supervisor/` 기준이다. `SHA-256`은 파일 바이트를 식별하는 해시이며, 결과의 정확성을 독립적으로 입증하는 값은 아니다.

## 2차 실측표

`Completion Rate`는 **성공 또는 확정 실패가 기록된 문항 / 70**으로 1차와 같은 정의다. `Schema Valid Rate`는 유효한 결정 행 / 70이다. 모든 후보가 70문항을 시도했으며, 실패한 문항은 유효 결정에 넣지 않았다. `Question Type Accuracy`는 실패 문항을 오답으로 계산한 정답 / gold 35문항이다. `Question Type Macro-F1`은 gold의 네 class를 동일 가중했다. 시간은 문항별 전체 호출·재시도 시간의 p50·p95다.

`[Measured]`는 실행기가 기록한 문항별 응답·호출 수·usage·latency, `[Calculated]`는 그 기록과 동결 gold에서 재계산한 비율·F1·비용 합계·백분위수다. `Budget-Accounted Cost`는 실행기의 상한 관리값으로, 실제 청구액과 동일하다고 해석하지 않는다. 이번 표에 사람 판정이나 별도 LLM judge로 새로 측정한 지표는 없다.

| Model ID | Attempted Outputs | Completion Rate | Schema Valid Rate | Question Type Accuracy | Question Type Macro-F1 | Raw Calls | Errors | Reported Cost Sum* | Budget-Accounted Cost | p50 Latency | p95 Latency |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 70/70 | 70/70 | 46/70 | 21/35 (0.600) | 0.678 | 132 | ValidationError 24 | US$0.030679400 | US$0.034696100 | 2.812초 | 7.500초 |
| `openai/gpt-6-luna` | 70/70 | 70/70 | 65/70 | 34/35 (0.971) | 0.987 | 84 | ValidationError 5 | US$0.011756000 | US$0.012544100 | 3.141초 | 13.156초 |
| `deepseek/deepseek-v4.1-flash` | 70/70 | 70/70 | 62/70 | 29/35 (0.829) | 0.882 | 94 | ValidationError 8 | US$0.007154758 | US$0.008050050 | 7.313초 | 33.266초 |
| `meta/muse-glimmer-30b` | 70/70 | 70/70 | 1/70 | 1/35 (0.029) | 0.071 | 208 | ValidationError 69 | US$0.077155040 | US$0.077155040 | 5.110초 | 5.938초 |
| `cohere/command-a-plus` | 70/70 | 70/70 | 21/70 | 9/35 (0.257) | 0.393 | 173 | ValidationError 49 | US$0.083046000 | US$0.085608900 | 4.437초 | 6.157초 |
| `typesafe/jev-1.14` | 70/70 | 70/70 | 70/70 | 33/35 (0.943) | 0.947 | 70 | 0 | US$0.002689092 | US$0.002689092 | 0.407초 | 0.438초 |

표 읽는 법: `Attempted Outputs`는 계획한 70문항 중 실제 시도한 수, `Completion Rate`는 성공 또는 확정 실패가 최종 행으로 기록된 수 / 70이다. `Schema Valid Rate`는 다음 노드가 읽을 수 있는 유효 결정 수 / 70, `Question Type Accuracy`는 유형 정답이 있는 35문항 중 맞힌 수 / 35, `Question Type Macro-F1`은 네 유형의 F1 동일 가중 평균이다. `Raw Calls`는 재시도까지 합친 호출 수, `Errors`는 최종 실패 문항의 오류 종류와 수다. `Reported Cost Sum`은 저장된 usage에 비용이 있는 응답의 합계, `Budget-Accounted Cost`는 미보고 호출의 보수적 예약액까지 합친 예산 관리값이다. `p50 Latency`는 문항별 전체 처리 시간의 중앙값, `p95 Latency`는 95백분위수다. `ValidationError`는 모델 호출은 됐지만 최종 출력 형식이 계약에 맞지 않은 문항을 뜻한다.

### Jev Routing Consistency

| Predicted `out_of_scope` | `next_action=refuse` | Inconsistent Action | Case IDs |
|---:|---:|---:|---|
| 6/70 | 2/6 | 4/6 | `draft30-m06` (`circuit_agent`), `draft30-h09`·`draft30-h10`·`draft50-n18` (`search_agent`) |

표 읽는 법: `Predicted out_of_scope`는 Jev가 스스로 서비스 범위 밖이라고 분류한 문항 수, `next_action=refuse`는 그중 거절 동작을 고른 수다. `Inconsistent Action`은 범위 밖으로 분류하면서 거절 외 동작을 고른 수다. 이 값은 저장된 2차 원시 행의 `decision` 두 필드를 대조한 `[Calculated]` 지표이며, 사람 정답이 없는 35문항의 정답률을 뜻하지 않는다. 기존 `Schema Valid Rate` 70/70은 형식 통과 수치로 유지한다. 다른 5종과 같은 기준의 라우팅 일관성 비교는 이번 표에서 측정하지 않았다.

### 호출·실패 상세

`[Measured]`는 저장된 응답 metadata·행·실행 시간이며, rate와 class별 점수는 해당 행에서 다시 계산한 `[Calculated]` 값이다. 여섯 후보 모두 smoke에서 실제 모델·provider가 확인됐다. Meta의 smoke만 `schema_error`였지만 모델 호출과 provider 확인은 성공했고, 본 테스트의 문항별 실패로 따로 측정했다. 본 테스트에서 호출 자체가 불가능해 중단된 모델은 없다.

| Model ID | Provider | Actual Model | Main Test Status | First-Pass Schema Success Rate | Retry Rate | API Error Rate | Error Breakdown |
|---|---|---|---|---:|---:|---:|---|
| `anthropic/claude-haiku-5.5` | Google | `anthropic/claude-haiku-5.5` | `complete_with_errors` | 36/70 | 34/70 | 0/70 | `ValidationError` 24 |
| `openai/gpt-6-luna` | Azure | `openai/gpt-6-luna` | `complete_with_errors` | 61/70 | 9/70 | 0/70 | `ValidationError` 5 |
| `deepseek/deepseek-v4.1-flash` | Morph | `deepseek/deepseek-v4.1-flash` | `complete_with_errors` | 57/70 | 13/70 | 0/70 | `ValidationError` 8 |
| `meta/muse-glimmer-30b` | DeepInfra | `meta/muse-glimmer-30b` | `complete_with_errors` | 1/70 | 69/70 | 0/70 | `ValidationError` 69 |
| `cohere/command-a-plus` | Cohere | `cohere/command-a-plus` | `complete_with_errors` | 16/70 | 54/70 | 0/70 | `ValidationError` 49 |
| `typesafe/jev-1.14` | TypeSafe | `typesafe/jev-1.14-20261014` | `complete` | 70/70 | 0/70 | 0/70 | 없음 |

표 읽는 법: `Provider`는 실제 요청을 처리한 공급자, `Actual Model`은 응답에 기록된 모델 ID다. `Main Test Status`의 `complete`는 70건 모두 유효하게 완료, `complete_with_errors`는 70건을 시도했으나 일부 문항의 최종 형식 오류가 남았다는 뜻이다. `First-Pass Schema Success Rate`는 재시도 없이 유효한 결정을 낸 문항 / 70, `Retry Rate`는 한 번 이상 재시도한 문항 / 70이다. `API Error Rate`는 timeout·429·5xx·연결 오류가 확정된 문항 / 70, `Error Breakdown`은 최종 오류 종류와 수다. API 오류는 `ValidationError`와 분리한다. `Safety-Failure Case Count`는 별도 사람 판정 label이 없어 `Not Measured`이며 0이라고 주장하지 않는다.

| Model ID | Input Tokens (recorded) | Output Tokens (recorded) | Reported Cost Calls | Elapsed Time |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 179,394 | 25,480 | 118 | 267.609초 |
| `openai/gpt-6-luna` | 56,385 | 12,235 | 80 | 309.625초 |
| `deepseek/deepseek-v4.1-flash` | 73,697 | 15,815 | 86 | 771.219초 |
| `meta/muse-glimmer-30b` | 92,432 | 53,238 | 208 | 353.609초 |
| `cohere/command-a-plus` | 68,285 | 41,707 | 168 | 281.594초 |
| `typesafe/jev-1.14` | 64,026 | 14,930 | 70 | Not Recorded |

표 읽는 법: `Input Tokens (recorded)`·`Output Tokens (recorded)`는 저장된 usage의 입력·출력 토큰 합계다. `Reported Cost Calls`는 저장된 행에 비용이 남은 응답 record 수, `Elapsed Time`은 전체 실행 process의 경과 시간이다. `Not Recorded`는 측정값이 파일에 남지 않았다는 뜻이다. 생성형 5종에서 재시도 뒤 성공한 행은 앞선 실패 응답의 usage를 모두 보존하지 않아 `Reported Cost Calls`가 `Raw Calls`보다 작을 수 있다. Jev 실행기는 전체 process의 `Elapsed Time`을 결과에 보존하지 않았으므로 문항별 latency를 합쳐 같은 값처럼 쓰지 않는다.

### gold class별 F1

| Model ID | candidate_find | candidate_judge | rating | role |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 0.889 | 0.000 | 0.824 | 1.000 |
| `openai/gpt-6-luna` | 1.000 | 1.000 | 0.947 | 1.000 |
| `deepseek/deepseek-v4.1-flash` | 1.000 | 0.706 | 0.824 | 1.000 |
| `meta/muse-glimmer-30b` | 0.000 | 0.000 | 0.000 | 0.286 |
| `cohere/command-a-plus` | 0.000 | 0.200 | 0.462 | 0.909 |
| `typesafe/jev-1.14` | 1.000 | 0.900 | 0.889 | 1.000 |

표 읽는 법: `candidate_find`는 조건에 맞는 대체 후보 찾기, `candidate_judge`는 제시한 후보의 대체 가능성 판단, `rating`은 부품 정격·특성 질문, `role`은 회로 내 역할·연결 질문이다. 각 값은 해당 유형의 F1 점수로, 그 유형을 정답으로 맞힌 정도와 다른 유형을 잘못 그 유형으로 고른 정도를 함께 반영한다. 1.000이 가장 높고 0.000이 가장 낮다.

\* `Reported Cost Sum`은 저장된 행에서 확인되는 usage.cost 합계다. 생성형 5종은 schema 재시도 뒤 성공한 행의 **이전 실패 시도 usage가 행에 모두 남지 않아** 실제 전체 청구액보다 작을 수 있다. 비용 관리에는 호출 시 provider가 보고한 비용과 미보고 호출의 예약액을 합친 `Budget-Accounted Cost`를 썼다. 본 테스트 6종의 이 합계는 US$0.220743282로 등록한 계획값 US$0.88 이내다. Jev의 호출 전 예약은 입력 토큰 비용 추정치만 사용했으므로 `--max-usd`가 실제 지출의 절대 상한을 보장하지 않는다. 호출 실제 비용이 추정보다 크면 마지막 job에서 초과할 수 있다. 5종 smoke artifact는 실제 usage를 저장하지 않으므로 smoke 실제 총 비용은 `Not Reported`; Jev smoke는 US$0.000036498을 보고했다. 위 합계에는 smoke가 없다.

위 표의 `Input Tokens`와 `Output Tokens`도 저장된 usage record의 합계다. 생성형 5종은 저장되지 않은 이전 schema 재시도 usage가 이 값에도 빠질 수 있다.

## 1차와의 대조

| Model ID | 1차 Question Type Accuracy | 2차 Question Type Accuracy | 1차 Schema Valid Rate | 2차 Schema Valid Rate |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 22/35 | 21/35 | 48/70 | 46/70 |
| `openai/gpt-6-luna` | 35/35 | 34/35 | 66/70 | 65/70 |
| `deepseek/deepseek-v4.1-flash` | Not Comparable (3/70에서 provider stop) | 29/35 | Not Comparable | 62/70 |
| `meta/muse-glimmer-30b` | 1/35 | 1/35 | 1/70 | 1/70 |
| `cohere/command-a-plus` | 8/35 | 9/35 | 20/70 | 21/70 |
| `typesafe/jev-1.14` | 33/35 | 33/35 | 70/70 | 70/70 |

표 읽는 법: `Question Type Accuracy`는 gold가 있는 같은 35문항에서 질문 유형을 맞힌 수, `Schema Valid Rate`는 전체 70문항에서 유효한 결정을 낸 수다. `1차`와 `2차`는 같은 문항을 다시 호출한 별도 실행이다. `Not Comparable`은 1차에 provider 오류로 70문항을 완료하지 못해 두 회차의 품질 점수를 직접 비교할 수 없다는 뜻이다.

- Luna의 2차 Accuracy 34/35에서 빠진 `draft30-e05`는 잘못된 질문 유형을 낸 사례가 아니라 세 번의 형식 시도 뒤 `ValidationError`가 된 사례다. 유효한 gold 34건의 분류는 모두 맞았지만, 운영 지표에는 해당 실패를 포함한다.
- Jev의 2차 오분류 2건은 1차와 동일한 `draft30-e04`, `draft30-m05`다. 두 번 모두 같은 문항을 봤으므로 독립 평가셋 성능이나 confidence threshold의 타당성을 입증하지 않는다.
- DeepSeek은 1차에 `RateLimitError` 3회로 3/70에서 멈췄다. 2차는 70/70을 시도해 62건의 유효 결정을 냈지만, 1차와 70문항 짝 비교를 할 수 없다.
- Jev의 Decisions API typed answer와 다른 5종의 Chat Completions JSON 출력은 서로 다른 계약이다. `Schema Valid Rate`는 **다음 노드가 읽을 수 있는 결정 비율**로 비교하며, 모델의 동일한 JSON 생성 능력을 뜻하지 않는다.

## 집계 주의와 현재 결론

기존 5종 실행기의 각 `rows_*.json` 안 `summary`는 3회 전체 계획을 전제로 `Completion Rate`를 210건으로 나누고 미실행 1·3회를 점수 0으로 평균에 포함한다. 이번 실험에는 적용할 수 없어 위 표는 **원시 `run_index=2` 행 70건만** 별도 계산했다. 원본 summary의 `per_run["2"]` Accuracy·Macro-F1은 별도 집계와 일치한다. `Three-Run Exact Agreement`와 Flip Rate는 이번 1회 재측정에서 보고하지 않는다.

5종 manifest의 `code_sha256`은 실행 시점 파일의 원시 바이트 해시다. 현재 Windows checkout의 `run_supervisor_models.py`는 CRLF로 변환되어 그 해시와 다르지만, LF로 정규화한 바이트는 `main`의 `ff4ace1` 코드 blob 및 manifest 해시와 일치한다. 따라서 현재 checkout에서 기존 manifest를 그대로 재실행할 수 있다고 주장하지 않는다. Jev manifest는 동결 데이터셋과 typed question 계약 해시를 고정했지만 실행기 파일 해시는 기록하지 않았다. 이 차이는 원시 행·provider 근거와 별개로 코드 재현의 한계다.

2차에서는 Luna가 gold Accuracy 34/35로 가장 높고, Jev가 33/35와 형식상 유효 결정 70/70, 가장 낮은 기록 비용·지연시간을 남겼다. Jev의 범위 밖 자체 분류 6건 중 4건은 거절하지 않아, 이 수치만으로 운영 라우팅 적합성을 인정할 수 없다. 이번 결과는 기존 Luna 확정 결정을 자동으로 바꾸지 않는다. 모델 변경 또는 cascade는 별도 결정과 검증 대상이다.

유료 평가 본 실행은 6종 모두 70문항을 시도했고, 저장된 `Budget-Accounted Cost`는 등록한 모델별 계획값 이내였다. 실제 전체 청구액은 외부 청구서로 확인하지 않았다.
