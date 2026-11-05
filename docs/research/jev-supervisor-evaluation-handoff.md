# Jev 수퍼바이저 평가 인수인계

> 기준일 2026-11-05 · 작업 브랜치 `docs/supervisor-luna-selection` · 기준 HEAD `43d5c4a7bc0f1e5a58d3e5435aec759eba42cbfb` · 로컬 미커밋 상태의 실행·검증 스냅샷

## 목적과 현재 결론

SojaFit 수퍼바이저 후보 `typesafe/jev-1.14`를 기존 5개 후보와 같은 동결 평가셋 70문항에서 1회 비교했다. Jev는 질문 유형 정확도에서 `openai/gpt-6-luna`보다 5.71%p 낮았지만, 오류 없이 70건을 완료했고 비용·지연시간·schema 안정성이 크게 나았다.

현재 확정할 수 있는 결론은 다음 두 가지다.

1. 질문 유형 정확도만 보면 `openai/gpt-6-luna`가 가장 높다.
2. 현재 수퍼바이저처럼 고정된 분류·라우팅만 맡기면 `typesafe/jev-1.14`가 비용·속도·안정성 면에서 가장 유력하다.

아직 Jev를 최종 수퍼바이저로 확정하지 않았다. `Jev 기본 분류 → 낮은 confidence만 Luna 재판정`은 현재 결과에서 나온 후속 실험 제안이며 운영 정책이 아니다.

## 작업 위치와 Git 주의사항

- 저장소: `C:\Users\user\Documents\ChatGPT\3차 프로젝트 2\proj3-b`
- 브랜치: `docs/supervisor-luna-selection`
- 기준 HEAD: `43d5c4a7bc0f1e5a58d3e5435aec759eba42cbfb`
- 작업 트리에 기존 수퍼바이저 비교, 서비스 문서, 평가 결과를 포함한 미커밋 변경과 새 파일이 함께 있다.
- `git reset --hard`, `git clean`, 강제 checkout, 기존 결과 폴더 덮어쓰기를 하지 않는다.
- commit, push, PR 생성, 병합은 사용자에게 별도 승인을 받은 뒤 수행한다.
- `.env`의 `OPENROUTER_API_KEY`는 값이 아니라 존재 여부만 확인하며 출력·복사·문서화를 금지한다.

## 평가 조건

| 항목 | 값 |
|---|---|
| 요청 모델 | `typesafe/jev-1.14` |
| 실제 snapshot | `typesafe/jev-1.14-20261014` |
| provider | `TypeSafe` |
| API | OpenRouter Decisions API `POST /api/alpha/decisions` |
| 평가셋 | `evals/dataset_v2.jsonl` |
| 평가셋 SHA-256 | `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9` |
| 실행 범위 | 70문항 × 1회 |
| objective 분모 | `question_type` gold가 있는 35문항 |
| 비교 제외 | gold가 없는 나머지 35문항의 Question Type Accuracy |
| provider policy | ZDR, `data_collection=deny`, fallback 금지 |
| 본 테스트 비용 상한 | US$0.01 |

표 읽는 법: `snapshot`은 응답에 기록된 실제 모델 버전, `provider`는 호출을 처리한 공급자, `API`는 요청 경로다. `objective 분모`는 유형 정답이 있어 정확도를 채점한 문항 수다. `provider policy`는 데이터 보관·수집과 다른 공급자로의 자동 우회를 제한한 요청 조건이며, 비용 상한은 실제 지출액이 아니다.

Jev 요청은 한 번에 다음 typed question 5개를 보낸다.

- `question_type`
- `needs_circuit`
- `needs_datasheet`
- `needs_approved_case`
- `next_action`

세 evidence 응답을 기존 `required_evidence` 목록으로 바꾸고, `reason_code`는 `question_type`에서 결정적으로 만든다. gold, `expected`, `why`, `gold_chunks`는 모델 입력에 포함하지 않는다.

## Jev 본 테스트 실측

| Metric | Result |
|---|---:|
| Completion Rate | 70/70, 1.000 |
| Schema Valid Rate | 70/70, 1.000 |
| Question Type Accuracy | 33/35, 0.942857 |
| Question Type Macro-F1 | 0.947222 |
| p50 Latency | 0.422초 |
| p95 Latency | 0.593초 |
| Input Tokens | 64,026 |
| Output Tokens | 14,926 |
| 본 테스트 비용 | US$0.002689092 |
| 문항당 비용 | 약 US$0.000038416 |
| 재시도 | 0 |
| 실행 오류 | 0 |

표 읽는 법: `Completion Rate`는 최종 성공 또는 확정 실패가 기록된 문항 / 70, `Schema Valid Rate`는 다음 노드가 읽을 수 있는 유효 결정 / 70이다. `Question Type Accuracy`는 유형 정답이 있는 35문항 중 맞힌 비율, `Question Type Macro-F1`은 유형별 F1을 같은 비중으로 평균한 값이다. `p50 Latency`는 문항별 처리 시간 중앙값, `p95 Latency`는 95백분위수다. `Input Tokens`·`Output Tokens`는 기록된 입력·출력 토큰 총합, 비용은 이 본 테스트에서 보고된 호출 비용 합계다. 재시도와 실행 오류가 0이라는 뜻은 이 실행에서 추가 호출과 확정 실패가 없었다는 뜻이다.

오분류는 2건이며 모두 `rating`을 `candidate_judge`로 분류했다.

| Case ID | Gold | Prediction | Confidence | 주요 확률 |
|---|---|---|---:|---|
| `draft30-e04` | `rating` | `candidate_judge` | 0.53 | candidate_judge 0.61, rating 0.35 |
| `draft30-m05` | `rating` | `candidate_judge` | 0.40 | candidate_judge 0.50, rating 0.48 |

표 읽는 법: `Case ID`는 평가 문항 ID, `Gold`는 평가셋의 정답 유형, `Prediction`은 Jev가 고른 유형이다. `Confidence`와 `주요 확률`은 API가 보고한 선택 점수·후보별 값이며 실제 정답일 확률이 검증됐다는 뜻은 아니다. `rating`은 부품 정격·특성 질문, `candidate_judge`는 제시한 후보의 대체 가능성 판단이다.

## 기존 5개 모델과 비교

같은 동결 70문항의 Stage 1 1회 결과다. DeepSeek은 Rate Limit 3회 후 중단되어 품질 비교에서 제외한다.

| 모델 | Accuracy | Macro-F1 | Schema Valid | 오류 | reported cost | p50 |
|---|---:|---:|---:|---:|---:|---:|
| `openai/gpt-6-luna` | 1.000 | 1.000 | 0.943 | 4 | US$0.0109729 | 2.805초 |
| `typesafe/jev-1.14` | 0.943 | 0.947 | 1.000 | 0 | US$0.002689092 | 0.422초 |
| `anthropic/claude-haiku-5.5` | 0.629 | 0.724 | 0.686 | 22 | US$0.0294164 | 2.367초 |
| `cohere/command-a-plus` | 0.229 | 0.356 | 0.286 | 50 | US$0.0840432 | 4.406초 |
| `meta/muse-glimmer-30b` | 0.029 | 0.071 | 0.014 | 69 | US$0.07502582 | 5.055초 |
| `deepseek/deepseek-v4.1-flash` | 비교 불가 | 비교 불가 | 비교 불가 | Rate Limit 3회 | - | - |

표 읽는 법: `Accuracy`는 gold가 있는 35문항의 질문 유형 정답률, `Macro-F1`은 네 유형 F1의 동일 가중 평균, `Schema Valid`는 전체 70문항의 유효 결정 비율이다. `오류`는 최종 실패 문항 수, `reported cost`는 저장된 usage가 보고한 비용의 합계, `p50`은 문항별 처리 시간 중앙값이다. `비교 불가`는 1차 실행이 조기 중단돼 70문항 품질을 비교할 수 없다는 뜻이고, `-`는 비교할 측정값이 없다는 뜻이다.

Jev는 Luna보다 정확도가 5.71%p 낮지만 reported cost가 약 75.5% 낮고, p50은 약 6.6배, p95는 약 21.7배 빠르다. Schema Valid 비교는 Jev의 Decisions API typed answer와 생성형 모델의 JSON schema 출력 방식 차이를 포함하므로 순수한 모델 지능 비교로 해석하지 않는다.

## confidence 후속 관찰

현재 35개 labeled case에서 `question_type confidence < 0.60`인 문항은 2건이고 두 오분류가 모두 포함됐다. 그러나 `0.60`은 현재 결과를 본 뒤 찾은 값이라 이 결과만으로 운영 threshold로 확정하면 과적합이다.

후속 실험에서는 `0.60`을 사전 등록한 뒤 새로운 반복 실행 또는 별도 검증셋에서 다음을 측정한다.

- escalation rate
- 오류 포착률
- Jev 단독 대비 cascade accuracy
- 전체 비용과 p50·p95
- Luna fallback 실패·timeout 처리

## 파일과 무결성

### 실행 코드와 테스트

- `evals/runners/run_supervisor_jev.py` — Jev 전용 request, typed-answer 변환, ZDR preflight, smoke, 부분 저장, 호출 전 비용 추정 차단, summary. `--max-usd`는 실제 청구액의 절대 상한이 아니며 한 job의 실제 비용으로 초과할 수 있음
- `tests/evals/test_supervisor_jev.py` — gold 격리, schema 검증, 비용 예약, live gate, Decisions catalog, canonical snapshot 검사
- `docs/superpowers/specs/2026-11-04-jev-supervisor-evaluation-design.md` — 승인된 평가 설계
- `docs/superpowers/plans/2026-11-04-jev-supervisor-evaluation.md` — 테스트 우선 구현 계획

### Jev 결과

경로: `evals/results/supervisor/2026-11-04-jev-stage1-ready-v1/`

| 파일 | SHA-256 |
|---|---|
| `manifest.json` | `7809337bcae5f9f68f7a54bc4c626adcfb92e6e17e47df59e74b29b30f00f9ea` |
| `smoke.json` | `091292b3efe386b9c1f9e0be8bd108ee56db7b36e45abc63e55882647a96aae4` |
| `rows.json` | `d515d8cb9f24686b3791799cf5e6b88910b5d354bb270f3694ab8b8d04787e50` |
| `summary.json` | `8a8ed057c3f36547cabd07f588ddfe7a94611a755cbcbd27402c04462fb14c6e` |

표 읽는 법: 왼쪽은 Jev 1차 평가의 계획·smoke·문항별 원시 행·집계 파일이고, 오른쪽 `SHA-256`은 각 파일의 바이트를 식별하는 해시다. 해시만으로 API 호출이나 값의 정확성을 독립 증명하지는 않는다.

기존 5개 모델 비교 결과는 `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json`에 있다.

## 실행 중 발견하고 수정한 사항

1. OpenRouter model catalog는 기본 호출 시 text 출력 모델만 반환해 Jev를 누락했다. preflight를 `output_modalities=decisions`와 `zdr=true` 조합으로 수정했다.
2. 요청 ID는 `typesafe/jev-1.14`지만 응답은 canonical snapshot `typesafe/jev-1.14-20261014`를 반환했다. 동일 1.14의 8자리 날짜 snapshot만 허용하고 1.13·유사 ID는 거부하도록 검사한다.
3. 첫 smoke 호출은 모델·schema 모두 성공했지만 2번 문제로 로컬에서 오류로 잘못 분류됐다. 수정 뒤 smoke를 한 번 더 실행해 `complete`를 확인했다. 두 smoke의 합계 비용은 US$0.000072996이다.
4. 본 테스트 70건은 재시도와 오류 없이 끝났고 비용은 US$0.002689092다.

## 검증 상태

- 마지막 전체 회귀 테스트: `316 passed, 26 skipped`
- 마지막 Jev 전용 테스트: `20 passed`
- 본 테스트: 70 rows, 70 complete, 0 error, 0 retry
- result provider: 전부 `TypeSafe`
- result actual model: 전부 `typesafe/jev-1.14-20261014`
- commit·push·PR·병합: 수행하지 않음

새 채팅에서는 먼저 다음 명령으로 현재 파일이 유지됐는지 확인한다.

```powershell
Set-Location 'C:\Users\user\Documents\ChatGPT\3차 프로젝트 2\proj3-b'
git status --short
uv run --no-sync pytest tests/evals/test_supervisor_jev.py -q
```

기존 결과를 다시 만드는 명령은 비용이 발생하므로 사용자 승인 없이 실행하지 않는다. 재현이 승인되면 기존 폴더를 덮어쓰지 말고 날짜가 다른 새 결과 폴더를 사용한다.

```powershell
uv run --no-sync python -m evals.runners.run_supervisor_jev plan evals/results/supervisor/<새-결과-폴더>
uv run --no-sync python -m evals.runners.run_supervisor_jev smoke evals/results/supervisor/<새-결과-폴더> --max-usd 0.01 --confirm-live
uv run --no-sync python -m evals.runners.run_supervisor_jev run evals/results/supervisor/<새-결과-폴더> --max-usd 0.01 --confirm-live
```

## 다음 작업 권장 순서

1. 이 문서와 두 summary JSON을 읽고 수치가 유지됐는지 확인한다.
2. 목표가 Jev 단독 확정인지 Jev-Luna cascade 검증인지 사용자에게 확인한다.
3. cascade라면 `confidence < 0.60`을 사전 등록하고, 현재 runner를 덮어쓰지 않는 별도 계획·runner·결과 폴더를 만든다.
4. 새 테스트를 먼저 실패시킨 뒤 최소 구현하고 API 없이 계획과 비용 상한을 검증한다.
5. 유료 실행 전에 사용자에게 문항 수, 호출 수, 최대 비용, 중단 조건을 보여 주고 승인을 받는다.
6. 결과에는 70문항 실행값과 gold 35문항 objective score를 분리하고, threshold가 현재 run에서 정해졌다는 한계를 기록한다.
7. 최종 모델 또는 cascade 정책은 새 검증 결과 뒤에만 확정한다.

## 새 채팅 시작용 요청문

아래 문구를 새 채팅에 그대로 붙여 넣을 수 있다.

```text
작업 경로는 C:\Users\user\Documents\ChatGPT\3차 프로젝트 2\proj3-b 이다.
먼저 docs/research/jev-supervisor-evaluation-handoff.md를 전부 읽고, 그 문서가 가리키는 Jev summary와 기존 5개 모델 stage1_summary를 대조해 현재 상태를 확인해라.

기존 작업 트리는 미커밋 변경이 많으므로 reset, clean, 강제 checkout, 기존 결과 폴더 덮어쓰기를 하지 마라. commit, push, PR, 병합도 별도 승인 없이 하지 마라. OPENROUTER_API_KEY 값은 출력하지 마라.

현재 Jev 단독 결과와 Luna 결과를 바탕으로 다음 단계인 Jev 기본 분류 + 낮은 confidence만 Luna 재판정하는 cascade 검증을 이어갈 것이다. confidence 0.60은 기존 run을 보고 정한 사후 값이므로 확정값으로 취급하지 말고, 새 반복 또는 별도 검증에서 사전 등록해 확인해야 한다.

먼저 파일·hash·테스트·dirty worktree를 read-only로 확인하고, cascade 평가의 문항 수, 호출 수, 최대 비용, 성공 기준, 중단 조건, 새 파일 경로를 제안해라. 내가 승인하기 전에는 API 호출이나 유료 테스트를 실행하지 마라.
```

## 남은 판단

- Jev를 단독 수퍼바이저로 둘지, Luna fallback을 둘지.
- fallback 기준을 confidence 하나로 할지 probability margin과 함께 쓸지.
- 35개 labeled case를 그대로 반복할지, 별도 holdout을 추가할지.
- Jev의 `required_evidence`와 `next_action`을 objective로 채점할 gold를 추가할지.
- 최종 선택 뒤 현재 브랜치의 미커밋 결과를 어떤 단위로 commit·PR 할지.
