# 수퍼바이저 모델 5종 비교 사후등록

- 작성 시점: 2026-11-04, 후보별 실행과 결과 확인 뒤
- 대상 실험: 동결 v2 70문항을 사용한 수퍼바이저 후보 5종 1회 비교
- 목적: 실제로 적용한 조건, 실행 중 변경, 채점 범위, 중단과 선정 기준을 결과와 분리해 고정한다.
- 성격: 완료된 실험의 이력 기록이다. 실행 전에 기준을 고정하는 사전등록을 대신하지 않는다.

## 1. 실험 목적

SojaFit 수퍼바이저가 사용자 입력을 읽고 질문 유형과 다음 실행 경로를 정할 때 사용할 모델을 선정한다. 최종 답변 생성 모델, judge 모델, 전체 그래프 구조와 서브에이전트 수는 이 실험에서 선정하지 않았다.

## 2. 실제 비교 후보

- `anthropic/claude-haiku-5.5`
- `openai/gpt-6-luna`
- `deepseek/deepseek-v4.1-flash`
- `meta/muse-glimmer-30b`
- `cohere/command-a-plus`

## 3. 실제 평가 입력

- 평가셋: `evals/dataset_v2.jsonl`
- 동결 SHA-256: `81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9`
- 문항 수: 70건(`relevant=35`, `irrelevant=35`)
- 모델 입력: 실제 사용자 입력과 고정 system prompt
- 모델에 전달하지 않은 값: `question_type` gold, `expected`, `why`, `gold_chunks`, 모범 답변
- 실행 횟수: 최종 선정에 사용한 값은 후보별 run index 1 한 번이다.

## 4. 실제 출력 계약

- `question_type`
- `required_evidence`
- `next_action`
- `reason_code`

정해진 JSON schema를 통과하지 못한 출력은 `ValidationError`로 기록했다. schema 오류는 문항당 최대 두 번 재시도했고 SDK 자동 재시도는 사용하지 않았다.

## 5. 실제 provider·privacy 조건

- OpenRouter ZDR endpoint만 허용했다.
- `data_collection=deny`, `require_parameters=true`, provider fallback 금지를 유지했다.
- `anthropic/claude-haiku-5.5`는 Google, `openai/gpt-6-luna`는 Azure, `deepseek/deepseek-v4.1-flash`는 Morph, `meta/muse-glimmer-30b`는 DeepInfra, `cohere/command-a-plus`는 Cohere provider에서 실행됐다.
- Haiku에는 `temperature` 없이 `max_tokens`, Luna에는 `temperature` 없이 `max_completion_tokens`, 나머지 후보에는 `temperature=0`과 `max_tokens`를 사용했다.
- raw prompt, raw response와 예외 원문은 결과에 저장하지 않았다.

## 6. 실행 중 확인·변경된 사항

1. 처음 manifest는 최대 3회 실행을 지원했지만 최종 선정에는 다섯 후보의 70문항 1회 실행만 사용했다.
2. Haiku와 Luna의 최초 smoke `NotFoundError`는 모델 부재가 아니라 endpoint generation parameter와 `require_parameters=true`의 충돌이었다. parameter를 endpoint 계약에 맞춘 뒤 호출 가능 여부를 다시 확인했다.
3. `deepseek/deepseek-v4.1-flash`는 run index 1에서 `RateLimitError`가 3회 연속 발생해 3/70에서 provider stop으로 중단됐다.
4. schema 불일치는 호출 자체 실패가 아니라 해당 문항의 output 실패로 기록했다.
5. pairwise judge, robustness, end-to-end와 추가 반복 실행은 최종 선정 수치에 포함하지 않았다.

## 7. 실제 채점 범위

- `Schema Valid Rate`: 후보별 planned 70문항 전체가 분모다. 실패와 누락을 분모에서 제외하지 않았다.
- `Question Type Accuracy`: 동결 파일에 `question_type` gold가 있는 35문항만 채점했다.
- `Macro-F1`: 같은 35문항의 질문 유형별 F1을 같은 비중으로 평균했다.
- `required_evidence`, `next_action`, 비관련 35문항의 route는 사람 합의 gold가 없어 점수화하지 않았다.
- provider 중단 후보는 품질 점수를 0점으로 환산하지 않고 `Not Comparable`로 처리했다.

## 8. 실제 비용·latency 처리

- `Raw Calls`: 최초 호출과 schema 재시도를 포함한 API 호출 수다.
- `Reported Cost Sum`: provider가 `usage.cost`를 반환한 호출만 합산했다.
- `Budget-Accounted Cost`: reported cost가 없는 호출에는 보수적 예약 비용을 유지해 합산했다.
- 두 비용 중 어느 것도 단독으로 실제 총 청구액이라고 표시하지 않았다.
- p50·p95 latency는 저장된 output별 wall-clock 시간을 사용했다.

## 9. 실제 선정 순서

지표를 단일 가중 점수로 합치지 않고 다음 순서로 판단했다.

1. 70문항 실행을 끝까지 수행했는가
2. `Schema Valid Rate`
3. `Question Type Accuracy`와 `Macro-F1`
4. `Raw Calls`와 `Budget-Accounted Cost`
5. 위 품질 조건을 통과한 후보 사이의 latency

## 10. 실제 결론

- 최종 선정: `openai/gpt-6-luna`
- 차순위: `anthropic/claude-haiku-5.5`
- 선택 이유: Luna가 완료 후보 중 schema 안정성과 질문 유형 분류가 가장 높았고, Haiku보다 raw call과 budget-accounted cost가 낮았다. p50·p95 latency는 Haiku보다 느렸지만 수퍼바이저에서는 구조화 출력과 route 정확도를 우선했다.
- `deepseek/deepseek-v4.1-flash`는 품질 열위로 탈락한 것이 아니라 이번 provider stop 때문에 선택할 수 없는 상태로 남겼다.

서비스 기본값 적용은 이 실험과 별개다. 현재 정본인 ADR 0010과 `SPEC.md`는 임시 Haiku 설정이며, 조장 소유 정본 갱신 뒤 Luna 적용을 별도 변경해야 한다.

## 11. 근거 파일

- 전체 실험·결과 문서: `docs/experiments/supervisor-model-comparison.md`
- 경량 집계: `evals/results/supervisor/2026-11-04-stage1-v1/stage1_summary.json`
- 재현 검증 사전등록: `evals/guides/preregister.md` #29

현재 PR의 집계 JSON은 결과 요약이며 문항별 원시 증거가 아니다. #29에 등록한 경량 evidence를 생성하고 재계산해야 표의 수치 추적 가능성 검증이 완성된다.

## 12. 알려진 한계

- 원 실험에는 별도 번호의 실행 전 사전등록이 없었다.
- gold가 없는 필드는 객관 점수로 비교하지 못했다.
- 한 번 실행한 결과이므로 반복 안정성을 측정하지 않았다.
- supervisor-only 결과이며 end-to-end 서비스 성공률을 증명하지 않는다.
- OpenRouter 사용 내역이나 provider 서명 로그가 없으면 API 호출 자체를 외부에서 독립적으로 증명할 수 없다.
