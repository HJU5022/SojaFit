# 수퍼바이저 후보 6종 3차 실측 결과와 최종 후보 3종

- 상태: 이력 (당시 비교 결과. 현재 Supervisor 모델은 `anthropic/claude-haiku-5.5`이며 [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)이 [ADR 0014](../adr/0014-supervisor는-sonnet-서브에이전트는-haiku-채점은-luna.md)의 Sonnet을 대체했다. 코드: `backend/services/langfuse_prompts.py:33` `NODE_MODELS["supervisor"]`)
- 기준일: 2026-11-05 (측정일), 현재 모델 확인 2026-11-12
- 기준 커밋: 사전 등록 `d10a30b`(유료 호출 전 로컬 커밋. 원격 공개 시점으로 실행 전 등록을 독립 증명하지는 않는다)
- 정본 여부: 정본(3차 측정값과 후보 3종 기록). 지표 정의의 정본은 [2차 결과](supervisor-stage2-results.md)의 2절. 측정 계약의 정본은 [supervisor-stage3-six-models.md](../experiments/supervisor-stage3-six-models.md)(사전 등록 #36)
- 관련 문서: [2차 결과](supervisor-stage2-results.md), [사전 등록 계약](../experiments/supervisor-stage3-six-models.md)

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 입력 | 동결 `evals/dataset_v2.jsonl` 70문항, SHA-256 `81582c59…146bb09a9`. gold 35문항만 유형 채점 | 파일 해시 재계산 일치 |
| 실행 | 후보 6종 × 70문항 × 1회(`run_index=3`). 6종 모두 70문항 시도 | 원시 행 6개 파일 |
| 3차 호출·비용 합계 | Raw Calls 855회, Budget-Accounted Cost US$0.239294618 (smoke 제외) | `stage3_summary.json` 모델별 합 |
| 유형 정답이 가장 많은 후보 | Luna, Jev 각 33/35 | 3절 |
| 형식 통과 70/70 후보 | Jev | 3절 |
| 최종 후보 | `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5` (순위 없음) | 5절 |
| 판정 출처 | 모든 지표는 실행기가 저장한 행에서 코드(`evals/runners/report_supervisor_stage3.py`)로 재계산한 값. 사람 판정과 별도 LLM judge 지표는 없음 | `evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json` |

현재 서비스 모델(확인 2026-11-12): Supervisor Haiku, 종합 `synth` Sonnet, 근거 채점 `grade` Luna, 그 밖 노드 Haiku (`backend/services/langfuse_prompts.py:33-34`). 5절의 최종 후보는 서비스 채택 모델 확정과 구별한다.

## 2. 방법과 재계산

- 사전 등록 #36, 계약 [supervisor-stage3-six-models.md](../experiments/supervisor-stage3-six-models.md). 집계 JSON에 1~3차 원시 파일 해시와 모델별 수치·문항 ID가 있다.
- 재계산 명령(API 호출 없음): `uv run --no-sync python -m evals.runners.report_supervisor_stage3 evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`. 테스트: `tests/evals/test_supervisor_stage3_report.py`.
- 원시 행에서 직접 다시 센 Schema Valid·Accuracy·p50·p95·범위 밖 불일치 수가 3.1절 표와 모두 일치한다.
- 3차 원시 JSON은 `.gitattributes`의 `-text`로 줄바꿈 변환 없이 보존된다. 아래 SHA-256은 원시 바이트 해시이며 6개 파일과 집계 JSON(`77139315…e4659`) 모두 일치한다.
- 실행 기록(사전 등록 커밋, 모델별 인자·시작/종료 시각·경과 시간·종료 코드·원시 파일 해시)은 집계 JSON의 `execution`에 있다.

## 3. 결과

### 3.1 실측표

| Model ID | Schema Valid | Accuracy | Macro-F1 | Raw Calls | Errors | Reported Cost Sum | Budget-Accounted Cost | p50 | p95 |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 50/70 | 23/35 | 0.758 | 120 | ValidationError 20 | US$0.028076900 | US$0.030994100 | 2.187초 | 7.891초 |
| `openai/gpt-6-luna` | 65/70 | 33/35 | 0.960 | 86 | ValidationError 5 | US$0.012115500 | US$0.013300100 | 3.281초 | 15.078초 |
| `deepseek/deepseek-v4.1-flash` | 7/70 | 2/35 | 0.125 | 200 | ValidationError 63 | US$0.025543294 | US$0.026067446 | 5.406초 | 8.219초 |
| `meta/muse-glimmer-30b` | 1/70 | 1/35 | 0.071 | 206 | ValidationError 68, RateLimitError 1 | US$0.077216780 | US$0.080733380 | 8.828초 | 11.735초 |
| `cohere/command-a-plus` | 21/70 | 8/35 | 0.343 | 173 | ValidationError 49 | US$0.083025600 | US$0.085510500 | 4.188초 | 5.765초 |
| `typesafe/jev-1.14` | 70/70 | 33/35 | 0.947 | 70 | 없음 | US$0.002689092 | US$0.002689092 | 0.422초 | 0.454초 |

6종 모두 Attempted Outputs 70/70, Completion Rate 70/70이다. 비용 합계에 smoke는 포함하지 않는다. 실제 청구액과 smoke 전체 비용은 확인하지 않았다.

### 3.2 호출·형식·시간

| Model ID | Provider | Main Test Status | First-Pass Schema | Retry Rate | API Error Rate | Elapsed Time | Input Tokens | Output Tokens | Reported Cost Calls |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | Google | complete_with_errors | 41/70 | 29/70 | 0/70 | 251.875초 | 166,224 | 22,909 | 110 |
| `openai/gpt-6-luna` | Azure | complete_with_errors | 60/70 | 10/70 | 0/70 | 325.875초 | 56,385 | 12,954 | 80 |
| `deepseek/deepseek-v4.1-flash` | Relace | complete_with_errors | 5/70 | 65/70 | 0/70 | 398.375초 | 108,951 | 49,793 | 196 |
| `meta/muse-glimmer-30b` | DeepInfra | complete_with_errors | 1/70 | 68/70 | 1/70 | 622.234초 | 91,217 | 52,470 | 205 |
| `cohere/command-a-plus` | Cohere | complete_with_errors | 17/70 | 53/70 | 0/70 | 261.485초 | 68,337 | 41,683 | 168 |
| `typesafe/jev-1.14` | TypeSafe | complete | 70/70 | 0/70 | 0/70 | 30.625초 | 64,026 | 14,927 | 70 |

Elapsed Time은 catalog 확인을 포함한 본 실행 process 경과 시간이다. 생성형 5종은 재시도 뒤 성공한 행에 앞선 실패 usage가 남지 않아 Reported Cost Calls가 Raw Calls보다 작을 수 있다.

### 3.3 라우팅 일관성

범위 밖(`out_of_scope`)으로 스스로 분류한 유효 행 중 거절(`refuse`) 외 동작을 고른 비율이다. gold와 대조한 거절 정확도가 아니다.

| Model ID | 범위 밖 분류 | 거절 외 동작 | 문항과 동작 |
|---|---:|---:|---|
| `anthropic/claude-haiku-5.5` | 7 | 0/7 | 없음 |
| `openai/gpt-6-luna` | 7 | 0/7 | 없음 |
| `deepseek/deepseek-v4.1-flash` | 5 | 0/5 | 없음 |
| `meta/muse-glimmer-30b` | 0 | 해당 없음(0/0) | 없음 |
| `cohere/command-a-plus` | 2 | 0/2 | 없음 |
| `typesafe/jev-1.14` | 6 | 4/6 | `draft30-m06`: `circuit_agent`, `draft30-h09`·`draft30-h10`·`draft50-n18`: `search_agent` |

### 3.4 1~3차 안정성

비교 가능 문항은 세 회차 모두 형식상 유효한 문항이다. 나머지 열의 분모는 그 수다. 같은 오류를 반복해도 일치율이 높을 수 있으므로 비교 가능 문항이 적은 행의 일치율을 성능으로 읽지 않는다. `required_evidence` 배열 순서는 보존하고 객체 키 순서만 정규화했다.

| Model ID | 비교 가능 문항 | 3회 완전 일치 | 유형 뒤바뀜 | 다음 동작 뒤바뀜 |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 42/70 | 34/42 | 1/42 | 1/42 |
| `openai/gpt-6-luna` | 64/70 | 58/64 | 1/64 | 0/64 |
| `deepseek/deepseek-v4.1-flash` | 0/70 | 해당 없음 | 해당 없음 | 해당 없음 |
| `meta/muse-glimmer-30b` | 1/70 | 1/1 | 0/1 | 0/1 |
| `cohere/command-a-plus` | 17/70 | 17/17 | 0/17 | 0/17 |
| `typesafe/jev-1.14` | 70/70 | 60/70 | 0/70 | 4/70 |

### 3.5 1·2·3차 점수와 공급자

| Model ID | Accuracy 1차 | 2차 | 3차 | Schema Valid 1차 | 2차 | 3차 | Provider 1차 | 2차 | 3차 |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| `anthropic/claude-haiku-5.5` | 22/35 | 21/35 | 23/35 | 48/70 | 46/70 | 50/70 | Google | Google | Google |
| `openai/gpt-6-luna` | 35/35 | 34/35 | 33/35 | 66/70 | 65/70 | 65/70 | Azure | Azure | Azure |
| `deepseek/deepseek-v4.1-flash` | 비교 불가(3/70 시도, 유효 0) | 29/35 | 2/35 | 비교 불가 | 62/70 | 7/70 | 미기록 | Morph | Relace |
| `meta/muse-glimmer-30b` | 1/35 | 1/35 | 1/35 | 1/70 | 1/70 | 1/70 | DeepInfra | DeepInfra | DeepInfra |
| `cohere/command-a-plus` | 8/35 | 9/35 | 8/35 | 20/70 | 21/70 | 21/70 | Cohere | Cohere | Cohere |
| `typesafe/jev-1.14` | 33/35 | 33/35 | 33/35 | 70/70 | 70/70 | 70/70 | TypeSafe | TypeSafe | TypeSafe |

`비교 불가`는 1차에 공급자 오류로 70문항을 완료하지 못해 점수를 직접 비교할 수 없다는 뜻이다. 같은 Model ID에서 공급자가 바뀌면 형식 지원·지연·제공 조건이 달라질 수 있으므로 점수 차이를 모델 자체 변화로만 해석하지 않는다.

### 3.6 DeepSeek 출력 길이 진단

| 회차 | Provider | Schema Valid | 마지막 종료 사유가 length인 형식 실패 | 출력 토큰 256개로 끝난 형식 실패 시도 |
|---|---|---:|---:|---:|
| 2 | Morph | 62/70 | 8/8 | 24/24 |
| 3 | Relace | 7/70 | 63/63 | 189/189 |

3차 gold 35문항 중 33문항이 형식 실패했고, 유효한 2문항은 모두 유형 정답이었다. 프롬프트·출력 상한 256·실행 로직은 유지됐고, 두 manifest의 실행기 해시 차이는 LF/CRLF 줄바꿈 차이였다. 공급자 변경과 출력 제한 도달이 함께 관찰됐다. 내부 추론 설정이나 JSON 처리 차이와의 인과는 이 자료로 확정하지 않는다.

### 3.7 2차에서 3차로 달라진 gold 문항

집계 JSON `three_run_comparison.stage2_to_stage3_labeled_changes`의 건수와 같다(Haiku 6, Luna 1, DeepSeek 30, Muse 0, Cohere 3, Jev 0).

| Model ID | Case ID | Gold | 2차 | 3차 |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | draft30-e05 | rating | rating | error |
| `anthropic/claude-haiku-5.5` | draft50-n02 | candidate_judge | error | candidate_judge |
| `anthropic/claude-haiku-5.5` | draft50-n07 | candidate_judge | error | candidate_judge |
| `anthropic/claude-haiku-5.5` | draftv2-n04 | candidate_find | candidate_find | error |
| `anthropic/claude-haiku-5.5` | draftv2-n06 | candidate_find | error | candidate_find |
| `anthropic/claude-haiku-5.5` | draftv2-n10 | candidate_find | error | candidate_find |
| `openai/gpt-6-luna` | draft50-n06 | candidate_judge | candidate_judge | rating |
| `cohere/command-a-plus` | draft30-m07 | rating | error | rating |
| `cohere/command-a-plus` | draft50-n06 | candidate_judge | candidate_judge | error |
| `cohere/command-a-plus` | draft52-n21 | rating | rating | error |

DeepSeek 30건은 모두 3차에서 error로 바뀐 문항이다. 2차 값이 gold와 같은 유형이던 문항이 27건, 다른 유형(`draft30-m05`, `draft50-n06`, `draft52-n21`)이던 문항이 3건이다. 문항 ID와 값은 집계 JSON에서 읽는다. `next_action`만 달라진 문항은 집계 JSON의 뒤바뀜 목록에 있다.

### 3.8 gold 유형별 F1

| Model ID | candidate_find | candidate_judge | rating | role |
|---|---:|---:|---:|---:|
| `anthropic/claude-haiku-5.5` | 0.947 | 0.333 | 0.750 | 1.000 |
| `openai/gpt-6-luna` | 1.000 | 0.941 | 0.900 | 1.000 |
| `deepseek/deepseek-v4.1-flash` | 0.000 | 0.000 | 0.000 | 0.500 |
| `meta/muse-glimmer-30b` | 0.000 | 0.000 | 0.000 | 0.286 |
| `cohere/command-a-plus` | 0.000 | 0.000 | 0.462 | 0.909 |
| `typesafe/jev-1.14` | 1.000 | 0.900 | 0.889 | 1.000 |

## 4. 결정에 미치는 영향

- 이 결과는 서비스 Supervisor 모델을 정하지 않는다. 현재 모델 결정은 [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)이고, 근거는 v3 50문항 4세트 측정과 사전 등록 #46~#50이다.
- 사전 등록의 "2차와 크게 다르지 않다"에 수치 허용 범위가 없어, 가설 통과 여부를 자동 판정하지 않는다.

## 5. 최종 후보 3종

3차 결과 확인 뒤 최종 후보를 3종으로 정했다. 순위는 없다. 이 결정은 사전 등록의 선정 규칙으로 소급하지 않으며 서비스 채택 모델 확정과 구별한다. 6종의 코드·실측·원시 근거는 보존한다.

| Model ID | 상태 | 근거 |
|---|---|---|
| `openai/gpt-6-luna` | 최종 후보 | 1~3차 유형 정답 35·34·33/35, 형식 통과 66·65·65/70 |
| `typesafe/jev-1.14` | 최종 후보 | 세 회차 유형 정답 33/35, 형식 통과 70/70. 3차 동작 불일치 4/6은 후속 검증 항목 |
| `anthropic/claude-haiku-5.5` | 최종 후보 | 세 회차 유형 정답 22·21·23/35, 형식 통과 48·46·50/70의 실측과 한계를 함께 보존 |
| `deepseek/deepseek-v4.1-flash` | 제외 | 세 회차 실행 안정성 부족. 1차 공급자 중단, 2·3차 공급자 변경과 3차 출력 제한 실패(3.6절). 모델 자체의 보편적 성능 저하로 단정하지 않음 |
| `cohere/command-a-plus` | 제외 | 세 회차 유형 정답 8·9·8/35, 형식 통과 20·21·21/70. 현재 계약의 실패 반복 |
| `meta/muse-glimmer-30b` | 제외 | 세 회차 모두 유형 정답 1/35, 형식 통과 1/70 |

최종 후보의 프롬프트·동작 제약·출력 상한을 바꿔 실행하면 별도 조건 변경 실험으로 등록한다. 기존 호출 실행기의 후보 목록은 과거 결과 재현을 위해 유지한다. Jev 기본 분류 뒤 낮은 confidence만 Luna로 재판정하는 방식은 제안일 뿐 운영 정책도 사전 등록 실험도 아니다.

## 6. 한계

1. 같은 동결 70문항을 3회 반복했다. 유형 gold 35문항이라 한 문항이 약 2.86%p다. 1~2문항 차이는 달라진 문항을 보는 근거이지 모델 우열의 근거가 아니다. 나머지 35개 문항의 올바른 거절 여부와 실서비스 그래프 성능은 이번 측정으로 입증하지 않는다.
2. Jev(typed answer 변환)와 생성형 5종(JSON 생성)은 계약이 다르다. 형식 성공과 전체 decision 일치율을 같은 생성 능력으로 해석하지 않는다.
3. 공급자가 회차마다 달라질 수 있다(3.5절). 모델 자체 변화와 분리해 해석해야 한다.
4. Jev 실행기는 2차 뒤 비용 초과 중단과 비유한 인자 차단이 추가됐고 프롬프트·변환 계약은 유지됐다. `--max-usd`는 입력 비용 추정으로 다음 job을 막는 값이라 마지막 job의 실제 비용이 계획값을 넘을 수 있다.
5. 생성형 5종 raw `summary`는 3회 전체 계획의 210건 분모를 쓴다. 이 문서의 값은 `run_index=3` 행만 재계산했다. `configured_max_calls=630`은 1~3차 전체 계획값이다. 이번 job 70건은 각 최대 3회라 실제 210호출 이하다.
6. 5종 smoke 파일은 usage 비용을 보존하지 않아 smoke 총 비용을 확정할 수 없다. Jev smoke의 보고 비용은 해당 `smoke.json`에서 읽는다.
7. 5종 manifest의 `code_sha256`은 실행 전 파일의 원시 바이트 해시다. 집계 JSON의 `execution_code_sha256_lf`·`analysis_code_sha256_lf`는 LF 정규화 해시라 CRLF checkout의 원시 해시와 직접 비교할 수 없다. 1·2차 원시 파일 해시는 집계 JSON에서 LF 정규화 값으로 쓴다.
8. 실제 청구액은 외부 청구서와 대조하지 않았다.

## 7. 증거 파일

경로는 저장소 루트 기준. SHA-256은 원시 바이트 기준.

| 파일 | SHA-256 |
|---|---|
| `evals/results/supervisor/2026-11-05-stage3-five-v1/rows_anthropic__claude-haiku-5.5.json` | `a59a05cf868e80f6c4b55c654f3a934de90b6bbd46d15782d8b0edade2d67bf1` |
| `evals/results/supervisor/2026-11-05-stage3-five-v1/rows_openai__gpt-6-luna.json` | `d06fa53bcefde71a6ed953585582093d36efb95ab6edf10d3c635b06ad3a7a77` |
| `evals/results/supervisor/2026-11-05-stage3-five-v1/rows_deepseek__deepseek-v4.1-flash.json` | `0cfa2069c245466bbabd7bbb30fd8d8c65df1c465c884b437b1a87bece0b71df` |
| `evals/results/supervisor/2026-11-05-stage3-five-v1/rows_meta__muse-glimmer-30b.json` | `7bf2a7c5bfba3ec33ee3157ad54a83a6e2426886ce73e2c2202503dcf652effc` |
| `evals/results/supervisor/2026-11-05-stage3-five-v1/rows_cohere__command-a-plus.json` | `f42f91056ba8521a268d0440eb2be0c78ee26901883e726e40443ca6f411bf78` |
| `evals/results/supervisor/2026-11-05-jev-stage3-v1/rows.json` | `5b514dc28fd17a8290c1dcfd849173cc718ffbfb43057f1330243464d606e1a1` |
| `evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json` | `77139315fb0b99a2d5441fe2c5b728f90984850763f6846f2b32237cfc5e4659` |
