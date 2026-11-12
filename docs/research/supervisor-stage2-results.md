# 수퍼바이저 후보 6종 2차 실측 결과

- 상태: 이력 (당시 비교 결과. 현재 Supervisor 모델은 `anthropic/claude-haiku-5.5`이며 [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)이 [ADR 0014](../adr/0014-supervisor는-sonnet-서브에이전트는-haiku-채점은-luna.md)의 Sonnet을 대체했다. 코드: `backend/services/langfuse_prompts.py:33` `NODE_MODELS["supervisor"]`)
- 기준일: 2026-11-05 (측정일), 현재 모델 확인 2026-11-12
- 기준 커밋: 사전 등록 커밋 미확인(한계 1). 원시 결과 경로는 아래 표
- 정본 여부: 정본(2차 측정값). 측정 계약의 정본은 [supervisor-stage2-six-models.md](../experiments/supervisor-stage2-six-models.md)와 `evals/guides/preregister.md` #32
- 관련 문서: [3차 결과](supervisor-stage3-results.md), [사전 등록 계약](../experiments/supervisor-stage2-six-models.md)

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 입력 | 동결 `evals/dataset_v2.jsonl` 70문항, SHA-256 `81582c59…146bb09a9` | 파일 해시 재계산 일치 |
| 채점 대상 | `question_type` gold가 있는 35문항. 나머지 35문항은 채점하지 않음 | `evals/dataset_v2.jsonl` |
| 실행 | 후보 6종 × 70문항 × 1회(`run_index=2`). 6종 모두 70문항 시도 | 원시 행 6개 파일 |
| 유형 정답이 가장 많은 후보 | `openai/gpt-6-luna` 34/35 | 아래 3절 |
| 형식 통과 70/70 후보 | `typesafe/jev-1.14` (유형 정답 33/35) | 아래 3절 |
| 6종 예산 관리 비용 합계 | US$0.220743282 (등록 상한 US$0.88 이내) | `stage2_summary_v2.json` 모델별 `budget_accounted_cost` 합 |
| 판정 출처 | 유형 정답·형식 통과·비용·지연은 모두 실행기가 저장한 행에서 코드로 재계산한 값. 사람 판정과 별도 LLM judge 지표는 없음 | `evals/results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json` |

현재 서비스 모델(확인 2026-11-12): Supervisor `anthropic/claude-haiku-5.5`, 종합 `synth` `anthropic/claude-sonnet-5.5`, 근거 채점 `grade` `openai/gpt-6-luna`, 그 밖 노드 Haiku (`backend/services/langfuse_prompts.py:33-34`). 이 문서의 측정은 선정 결과가 아니다.

## 2. 방법과 환경

| 항목 | 값 | 근거 |
|---|---|---|
| 후보 | Haiku 5.5, GPT-6 Luna, DeepSeek V4.1 Flash, Muse Glimmer 30B, Command A+, Jev 1.14 | `stage2_summary_v2.json` |
| 생성형 5종 호출 | Chat Completions JSON 출력, 문항당 최대 3회 시도 | 원시 행 `retry_count`, `evals/runners/run_supervisor_models.py` |
| Jev 호출 | OpenRouter Decisions API typed answer 5개(`question_type`, `needs_circuit`, `needs_datasheet`, `needs_approved_case`, `next_action`). 응답을 `required_evidence`와 `reason_code`로 코드가 변환. 실제 snapshot `typesafe/jev-1.14-20261014`, ZDR·`data_collection=deny`·fallback 금지 | 원시 행 `typed_answers`, `actual_model`, `evals/runners/run_supervisor_jev.py` |
| 모델 입력 | question만. gold·expected·why·gold_chunks는 넣지 않음 | `tests/evals/test_supervisor_jev.py`(Jev), 사전 등록 계약 |
| 공급자 | 6종 모두 응답에 기록된 공급자: Google, Azure, Morph, DeepInfra, Cohere, TypeSafe (순서는 3절 표 순서) | 원시 행 `provider` |

지표 정의 (3차 문서도 이 표를 쓴다).

| 지표 | 정의 |
|---|---|
| Attempted Outputs | 시도한 고유 문항 / 70 |
| Completion Rate | 성공 또는 확정 실패가 최종 행으로 기록된 문항 / 70 |
| Schema Valid Rate | 다음 노드가 읽을 수 있는 유효 결정 수 / 70 |
| Question Type Accuracy | gold 35문항 중 유형을 맞힌 수. 실패 문항은 오답 |
| Question Type Macro-F1 | gold 네 유형(`candidate_find`, `candidate_judge`, `rating`, `role`)의 F1 동일 가중 평균 |
| Raw Calls | 재시도 포함 호출 수 |
| Reported Cost Sum | 저장된 usage에 비용이 있는 응답의 합 |
| Budget-Accounted Cost | Reported Cost Sum에 미보고 호출의 예약액을 더한 예산 관리값. 실제 청구액이 아니다 |
| p50 / p95 Latency | 문항별 전체 처리 시간(재시도 포함)의 50·95 백분위수(nearest-rank) |
| First-Pass Schema Success Rate / Retry Rate | 첫 시도에 형식 통과한 문항 / 70, 재시도한 문항 / 70 |
| API Error Rate | timeout·429·5xx·연결 오류가 확정된 문항 / 70. `ValidationError`와 분리 |

## 3. 결과

### 3.1 실측표

원시 행에서 직접 재계산한 Schema Valid·Accuracy·p50·p95·범위 밖 불일치 수가 아래 표와 모두 일치한다. 나머지 열은 `stage2_summary_v2.json` 값이다.

| Model ID | Schema Valid | Accuracy | Macro-F1 | Raw Calls | Errors | Reported Cost Sum | Budget-Accounted Cost | p50 | p95 |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 46/70 | 21/35 (0.600) | 0.678 | 132 | ValidationError 24 | US$0.030679400 | US$0.034696100 | 2.812초 | 7.500초 |
| `openai/gpt-6-luna` | 65/70 | 34/35 (0.971) | 0.987 | 84 | ValidationError 5 | US$0.011756000 | US$0.012544100 | 3.141초 | 13.156초 |
| `deepseek/deepseek-v4.1-flash` | 62/70 | 29/35 (0.829) | 0.882 | 94 | ValidationError 8 | US$0.007154758 | US$0.008050050 | 7.313초 | 33.266초 |
| `meta/muse-glimmer-30b` | 1/70 | 1/35 (0.029) | 0.071 | 208 | ValidationError 69 | US$0.077155040 | US$0.077155040 | 5.110초 | 5.938초 |
| `cohere/command-a-plus` | 21/70 | 9/35 (0.257) | 0.393 | 173 | ValidationError 49 | US$0.083046000 | US$0.085608900 | 4.437초 | 6.157초 |
| `typesafe/jev-1.14` | 70/70 | 33/35 (0.943) | 0.947 | 70 | 없음 | US$0.002689092 | US$0.002689092 | 0.407초 | 0.438초 |

6종 모두 Attempted Outputs 70/70, Completion Rate 70/70이다. Safety-Failure Case Count는 사람 판정 label이 없어 측정하지 않았다(0이 아니다).

### 3.2 호출·형식·토큰

| Model ID | Provider | Main Test Status | First-Pass Schema | Retry Rate | API Error Rate | Input Tokens | Output Tokens | Reported Cost Calls | Elapsed Time |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | Google | complete_with_errors | 36/70 | 34/70 | 0/70 | 179,394 | 25,480 | 118 | 267.609초 |
| `openai/gpt-6-luna` | Azure | complete_with_errors | 61/70 | 9/70 | 0/70 | 56,385 | 12,235 | 80 | 309.625초 |
| `deepseek/deepseek-v4.1-flash` | Morph | complete_with_errors | 57/70 | 13/70 | 0/70 | 73,697 | 15,815 | 86 | 771.219초 |
| `meta/muse-glimmer-30b` | DeepInfra | complete_with_errors | 1/70 | 69/70 | 0/70 | 92,432 | 53,238 | 208 | 353.609초 |
| `cohere/command-a-plus` | Cohere | complete_with_errors | 16/70 | 54/70 | 0/70 | 68,285 | 41,707 | 168 | 281.594초 |
| `typesafe/jev-1.14` | TypeSafe | complete | 70/70 | 0/70 | 0/70 | 64,026 | 14,930 | 70 | 미기록 |

`complete_with_errors`는 70문항을 모두 시도했고 일부 문항에 최종 형식 오류가 남았다는 뜻이다. Muse의 smoke는 `schema_error`였지만 모델 호출과 공급자 확인은 성공했고 본 실행에서 문항별 실패로 측정했다. Jev 실행기는 process 전체 경과 시간을 저장하지 않았다.

### 3.3 gold 유형별 F1

| Model ID | candidate_find | candidate_judge | rating | role |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 0.889 | 0.000 | 0.824 | 1.000 |
| `openai/gpt-6-luna` | 1.000 | 1.000 | 0.947 | 1.000 |
| `deepseek/deepseek-v4.1-flash` | 1.000 | 0.706 | 0.824 | 1.000 |
| `meta/muse-glimmer-30b` | 0.000 | 0.000 | 0.000 | 0.286 |
| `cohere/command-a-plus` | 0.000 | 0.200 | 0.462 | 0.909 |
| `typesafe/jev-1.14` | 1.000 | 0.900 | 0.889 | 1.000 |

### 3.4 Jev 라우팅 일관성

| 범위 밖(`out_of_scope`) 자체 분류 | `next_action=refuse` | 거절 외 동작 | 문항 |
|---:|---:|---:|---|
| 6/70 | 2/6 | 4/6 | `draft30-m06`(`circuit_agent`), `draft30-h09`·`draft30-h10`·`draft50-n18`(`search_agent`) |

저장된 행의 `decision` 두 필드를 대조한 값이다. 다른 5종의 같은 지표(범위 밖 분류 수, 거절 외 동작 수): Haiku 7 중 0, Luna 7 중 0, DeepSeek 9 중 0, Muse 0, Cohere 2 중 0 (행에서 재계산).

### 3.5 1차(2026-11-04)와의 대조

| Model ID | 1차 Accuracy | 2차 Accuracy | 1차 Schema Valid | 2차 Schema Valid |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 22/35 | 21/35 | 48/70 | 46/70 |
| `openai/gpt-6-luna` | 35/35 | 34/35 | 66/70 | 65/70 |
| `deepseek/deepseek-v4.1-flash` | 비교 불가(3/70에서 `RateLimitError` 3회로 공급자 중단) | 29/35 | 비교 불가 | 62/70 |
| `meta/muse-glimmer-30b` | 1/35 | 1/35 | 1/70 | 1/70 |
| `cohere/command-a-plus` | 8/35 | 9/35 | 20/70 | 21/70 |
| `typesafe/jev-1.14` | 33/35 | 33/35 | 70/70 | 70/70 |

1차 값 출처: `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json`(생성형 5종), `evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/summary.json`(Jev).

- Luna의 2차 Accuracy 34/35에서 빠진 `draft30-e05`는 오분류가 아니라 3회 시도 뒤 `ValidationError`가 된 문항이다.
- Jev 오분류 2건(`draft30-e04`, `draft30-m05`)은 1차와 같은 문항이다. 둘 다 gold `rating`을 `candidate_judge`로 분류했다(1차 confidence 0.53, 0.40).
- 1차 Jev(2026-11-04): p50 0.422초, p95 0.593초, 비용 US$0.002689092, 입력 64,026·출력 14,926 토큰, 재시도 0. 1차 Luna의 reported cost US$0.0109729 대비 Jev는 약 75.5% 낮다(1차 Luna 값은 `stage1_summary.json`의 `reported_cost_sum`에서 읽음).
- 1차에서 `question_type confidence < 0.60`인 gold 문항은 2건이고 두 오분류가 모두 포함됐다. 이 값은 결과를 본 뒤 찾은 기준이라 운영 임계값의 근거가 아니다. 사전 등록한 반복 측정은 아직 없다.
- 1차 오분류 2건의 `question_type` 확률(`evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/rows.json`): `draft30-e04`는 candidate_judge 0.61, rating 0.35, `draft30-m05`는 candidate_judge 0.50, rating 0.48. 확률이 정답일 확률로 검증된 것은 아니다.
- Jev 호출은 모델 카탈로그를 `output_modalities=decisions`로 조회한다(`backend/services/llm.py:346-348`). 응답 snapshot `typesafe/jev-1.14-20261014`처럼 1.14의 8자리 날짜 snapshot만 허용한다(`tests/evals/test_supervisor_jev.py:515`).
- 확인하지 않은 후속(Jev 기본 분류 + 낮은 confidence만 Luna 재판정): 사전 등록한 임계값으로 escalation 비율, 오류 포착률, Jev 단독 대비 정확도, 비용·p50·p95, fallback 실패·timeout 처리를 재야 한다. 측정 기록 없음.

## 4. 결정에 미치는 영향

- 이 결과는 Supervisor 모델을 정하지 않는다. 현재 모델 결정은 [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)(Haiku, v3 50문항 측정)이다.
- 3차 이후 최종 후보 3종 결정은 [3차 결과](supervisor-stage3-results.md)의 5절에 있다.

## 5. 한계

1. 사전 등록 커밋 해시는 이 문서가 인용하지 않는다. 계약 문서와 `preregister.md` #32에서 확인한다.
2. 같은 동결 70문항을 1·2차에 반복했다. 독립 평가셋 성능이 아니다. gold가 35문항이라 한 문항이 약 2.86%p다.
3. Jev(typed answer 변환)와 생성형 5종(JSON 생성)은 호출 계약이 달라 Schema Valid Rate를 같은 생성 능력으로 읽을 수 없다.
4. 생성형 5종은 재시도 뒤 성공한 행에 앞선 실패 시도의 usage가 남지 않아 Reported Cost Sum과 토큰이 실제보다 작을 수 있다. 실제 청구액은 외부 청구서와 대조하지 않았다. smoke 실제 비용은 5종이 `미보고`, Jev는 US$0.000036498이며 6종 합계에 포함하지 않았다.
5. Jev `--max-usd`는 호출 전 입력 비용 추정으로 다음 job을 막는 값이다. 마지막 job의 실제 비용이 추정보다 크면 초과할 수 있다. 저장된 결과가 계획값을 넘지는 않았다.
6. 생성형 5종 원시 파일의 `summary`는 3회 계획의 210건 분모를 쓴다. 이 문서의 값은 `run_index=2` 행 70건만 다시 계산했다.
7. 원시 파일 SHA-256은 CRLF 줄바꿈 기준이다(아래). LF checkout에서는 LF를 CRLF로 바꾼 뒤 해시가 일치한다(6개 원시 파일과 집계 JSON 모두 확인). 5종 manifest의 `code_sha256`은 실행 시점 바이트 해시이며, 현재 checkout에서 기존 manifest를 그대로 재실행할 수 있다고 보장하지 않는다. Jev manifest는 실행기 파일 해시를 기록하지 않았다.

## 6. 증거 파일

경로는 저장소 루트 기준. SHA-256은 CRLF 줄바꿈 기준.

| 파일 | SHA-256 |
|---|---|
| `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_anthropic__claude-haiku-5.5.json` | `1b77f40058dff3531eef6da4f18b383fb3fba9582b8b578fbe7ab3a3b87a1a00` |
| `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_openai__gpt-6-luna.json` | `f2cb9e85c979f73f52e7e0c9625b464e3e4d433c940aed03322654d65a4eb7fa` |
| `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_deepseek__deepseek-v4.1-flash.json` | `d618dfd94b80b4fafe43bc5c85c47b0d62fe5e91eb13b24c9a70f58262e1fd6a` |
| `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_meta__muse-glimmer-30b.json` | `fa582cebd5392304a170944ad570fce55dff79b3cf2d6a32135d1ccdc2e484d7` |
| `evals/results/supervisor/2026-11-05-stage2-five-v1/rows_cohere__command-a-plus.json` | `396bffb19627acf52d3c2021fd86029781c57b96fe1cd04db5b6aeb4b268bdac` |
| `evals/results/supervisor/2026-11-05-jev-stage2-v1/rows.json` | `f1995ce2b442d1f7dc72d427a7ffcb2fcf9c1b63dd9a27ee015ee109d4fa0d2d` |
| `evals/results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json` | `2c4ef11f52a8467c390af8e34ec3ae9e77fc958876b79ccc974973b6d6f8570b` |

2차 전용 집계는 `stage2_summary_v2.json`이다. 모델·공급자, 원시 파일 해시, 지표, 1차 대비 정오 변화 문항 ID가 있다. 이전 파생 파일 `stage2_summary.json`은 `Completion Rate`를 유효 결정 / 70으로 잘못 정의해 근거에서 뺐고 저장소에 없다.
