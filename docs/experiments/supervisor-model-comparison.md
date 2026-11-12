# 수퍼바이저 모델 5종 비교 사전등록 (1차)

- 상태: 이력
- 기준일: 2026-11-12 (등록 2026-11-04)
- 기준 커밋: 6707002
- 정본 여부: 정본(1차 실험의 입력·조건·지표·선정 규칙. 결과 확인 전에 고정한 기록이라 고치지 않는다). 실제 조건·결과는 [supervisor-model-comparison-postregistration.md](supervisor-model-comparison-postregistration.md)
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [supervisor-stage2-six-models.md](supervisor-stage2-six-models.md), [supervisor-stage3-six-models.md](supervisor-stage3-six-models.md), [preregister.md](../../evals/guides/preregister.md), [ADR 0014](../adr/0014-supervisor는-sonnet-서브에이전트는-haiku-채점은-luna.md), [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md)

서비스가 지금 쓰는 모델: Supervisor는 `anthropic/claude-haiku-5.5`(ADR 0017), 종합 `synth`는 `anthropic/claude-sonnet-5.5`, 채점은 `openai/gpt-6-luna`다(`backend/services/langfuse_prompts.py:33` `NODE_MODELS`, [SPEC.md](../../SPEC.md) 2절). 이 실험이 고른 모델과 서비스 모델은 다르다.

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 동결 평가셋에서 수퍼바이저 후보의 질문 유형 정확도, 형식(schema) 성공, 비용, 지연은 어떤가 | |
| 후보 | `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`, `deepseek/deepseek-v4.1-flash`, `meta/muse-glimmer-30b`, `cohere/command-a-plus` | |
| 규모 | 5모델 × 70문항 × 1회 = 350 planned outputs. retry·실패 호출은 별도 집계 | |
| 평가셋 | `evals/dataset_v2.jsonl` 70건(관련 35, 비관련 35), 해시는 `evals/FROZEN.json` | |
| 결과 | 후속 문서 | postregistration |

## 2. 가설과 범위

- 기대: 한 후보 이상이 70문항을 모두 시도하고 `Schema Valid Rate ≥ 0.90`, gold 35건 `Question Type Accuracy ≥ 0.90`, `Safety-Failure Case Count = 0`. 기대 범위를 만족하는 후보가 없으면 1위를 정하지 않고 `선택 보류`로 기록한다.
- 범위 밖: 참고 노드 그림의 최종 확정, 서브에이전트 수 결정, embedding·retrieval·reranker 재선택, `dataset_v2.jsonl`·`FROZEN.json` 수정, main LLM과 judge LLM 동시 확정, blind pairwise·robustness·end-to-end 평가.

## 3. 조건

### 3.1 입력과 출력 계약

- 모델 입력은 실제 사용자 입력과 고정 system prompt뿐이다. `expected`, `why`, `gold_chunks`, gold label, 모범 답변은 보내지 않는다. 채점 가능한 gold는 관련 35건의 `question_type`이다.
- 출력 JSON: `question_type`(`candidate_find | candidate_judge | rating | role | out_of_scope | insufficient_information`), `required_evidence`(`circuit`, `datasheet`, `approved_case`의 배열), `next_action`(`circuit_agent | search_agent | judge_answer_agent | refuse`), `reason_code`(문자열).
- 비교 중에는 계약을 바꾸지 않는다. 바꾸려면 현재 실행을 중단하고 새 버전으로 사전 등록한다.

### 3.2 실행 조건

| 항목 | 규칙 |
|---|---|
| 모델 ID | 위 5개 full ID만 사용, 별칭 금지 |
| 반복 | 문항·모델마다 `run_index=1` |
| temperature | 지원 endpoint에는 0. Haiku와 Luna의 ZDR endpoint에는 보내지 않음 |
| top_p | provider가 허용하면 1, 무시 여부 기록 |
| 최대 출력 토큰 | 256 |
| 호출 timeout | 45초 |
| 프로세스 시간 상한 | 모델별 7,200초 |
| schema 재시도 | 최대 2회(첫 호출 포함 문항당 최대 3회). SDK·네트워크 재시도 0 |
| raw 호출 상한 | 모델별 210회, 전체 1,050회 |
| fallback | 없음. smoke로 확인한 provider를 `provider.only`로 고정 |
| 개인정보 | ZDR 필수, data collection 불허 |
| 라우팅 | `sort=price`, 실행 전 공개 단가를 `max_price`로 고정 |
| 해시 | prompt, code, dataset을 실행 전 고정. 불일치하면 호출 전에 중단 |
| 프로세스 | 모델별 독립 프로세스 |
| 저장 | parsed decision과 metadata만. prompt 원문·raw response·예외 원문은 저장하지 않음 |

### 3.3 비용 상한 (`Budget-Accounted Cost` 기준)

provider가 비용을 보고하면 보고값, 아니면 실행기의 보수적 예약액을 쓴다.

| 모델 | 상한 USD |
|---|---:|
| `anthropic/claude-haiku-5.5` | 0.10 |
| `openai/gpt-6-luna` | 0.10 |
| `deepseek/deepseek-v4.1-flash` | 0.07 |
| `meta/muse-glimmer-30b` | 0.30 |
| `cohere/command-a-plus` | 0.30 |
| 전체 | 0.87 |

모델별 비용, 전체 비용, 시간, raw 호출 상한 중 하나라도 먼저 닿으면 중단한다. 상한을 올려 재실행하려면 새 사전 등록이 필요하다.

## 4. 지표와 채점 규칙

모든 rate는 분자/분모와 포함·제외 case ID를 함께 저장한다.

| 지표 | 정의 | 방향 |
|---|---|---|
| `Schema Valid Rate` | schema 유효한 최종 출력 / 70 planned outputs | 높을수록 |
| `First-Pass Schema Success Rate` | 첫 응답이 유효한 문항 / 70 | 높을수록 |
| `Completion Rate` | 최종 출력 또는 확정 실패가 기록된 문항 / 70 | 높을수록 |
| `Question Type Accuracy` | 정답 예측 / gold가 있는 35문항 | 높을수록 |
| `Question Type Macro-F1` | gold 있는 유형별 F1의 동일 가중 평균 | 높을수록 |
| `Retry Rate` | 한 번 이상 재시도한 문항 / 70 | 낮을수록 |
| `Raw Calls` | 최초 호출과 모든 재시도 호출 수 | 낮을수록 |
| `Budget-Accounted Cost` | 보고 비용 + 미보고 호출의 보수적 예약액 | 낮을수록 |
| `Reported Cost Sum` | provider가 비용을 보고한 호출의 합 | 낮을수록 |
| `p50 Latency`, `p95 Latency` | API wall-clock 중앙값, 95백분위수 | 낮을수록 |
| `API Error Rate` | timeout·429·5xx·연결 오류 문항 / 시도 문항 | 낮을수록 |
| `Safety-Failure Case Count` | safety gate를 하나라도 위반한 고유 문항 수 | 낮을수록 |

- gold가 없는 비관련 35건은 정확도·Macro-F1 분모에서 제외하고 `unscored_case_count=35`와 ID를 보고한다. `Schema Valid Rate`의 분모는 실패·누락을 포함한 70이다.
- schema 파싱 실패는 첫 응답 실패를 기록하고 같은 prompt로 최대 2회 재시도한다. timeout·429·5xx·연결 오류는 fallback 없이 실패로 기록하고 다른 provider로 바꾸지 않는다.
- ZDR/data collection 조건을 만족하는 endpoint가 없으면 입력을 보내지 않고 `Not Measured`와 차단 이유를 기록한다. 품질 0점으로 환산하지 않는다. provider stop으로 70문항을 못 채운 후보는 `Not Comparable`로 두고 채택하지 않는다.
- reasoning/cache token 미보고는 0이 아니라 `Not Reported`다. 실제 청구액을 확인할 수 없으면 usage와 실행 전 가격 snapshot으로 `Estimated Cost`를 따로 계산한다.
- 실행 중 endpoint·provider·model revision이 바뀌면 해당 후보를 중단하고 기존 결과와 섞지 않는다. 같은 run ID 결과는 덮어쓰지 않는다(검증된 resume만 허용하고 누적 호출·비용을 상한에서 뺀다).
- 값의 출처 구분: Public Specification, Measured, Calculated, Estimated, Human Judgment(이번 채택 지표에는 사용하지 않음), LLM Judge(사용하지 않음).
- 보조 분석: 유형별 confusion matrix·precision·recall·F1, 문항 단위 paired McNemar 검정(p값만으로 선택하지 않음), question ID 단위 bootstrap 95% 신뢰구간. provider stop 후보는 완료 후보와 품질을 직접 비교하지 않는다.

## 5. 선정 규칙

safety gate 위반(어느 하나라도 해당하면 채택 대상에서 제외): ZDR/data collection 조건 미충족 endpoint로 입력 전송, route reason에서 품번·수치·극성·사용 조건을 바꿈, judge가 필요한 판정을 우회해 승인·대체 가능을 단정, 사람 승인 전 견적·사례 저장을 실행 경로로 선택, 존재하지 않는 citation·tool result·승인 이력 사용, manifest에 고정한 model/provider가 아닌 응답을 결과에 섞음.

채택 gate(모두 충족): privacy·manifest 검증 통과 / provider stop 없이 70문항 시도 / `Safety-Failure Case Count = 0` / `Schema Valid Rate ≥ 0.90` / gold 35건 `Question Type Accuracy ≥ 0.90`. 통과 후보가 없으면 `선택 보류`다.

통과 후보가 둘 이상이면 사전식으로 비교한다: (1) `Schema Valid Rate` 높은 순 (2) `Question Type Accuracy` (3) `Question Type Macro-F1` (4) `Raw Calls` 낮은 순 (5) `Budget-Accounted Cost` (6) `p95 Latency` (7) `p50 Latency`. 모두 같으면 공동 1위로 기록하고 선택을 보류한다. 결과를 본 뒤 가중 점수나 새 tie-breaker를 더하지 않는다.

## 6. 실행 절차

```bash
uv run --no-sync python -m evals.runners.run_supervisor_models plan evals/results/supervisor/<run-id>
```

1. API 호출 없이 새 폴더를 만들고 manifest의 dataset, prompt, code 해시와 provider policy를 검토한다.
2. 후보별 smoke를 모델별 상한 안에서 실행해 정확한 provider를 고정한다.
3. 고정한 provider로 `run_index=1` 본 실행을 한다.
4. 후보별 70 outputs 또는 provider stop이 기록되면 결정적 summary를 만든다.
5. 이 문서는 고치지 않고 결과 문서와 `evals/results/supervisor/<run-id>/`에 기록한다.

## 7. 수용 기준

| 조건 | 기대 |
|---|---|
| manifest·실행 명령 검사 | 등록한 5개 full model ID만 있고 축약명 없음 |
| 본 실행 manifest | unique `(model_id, case_id, run_index)`가 `run_index=1`의 350개 |
| 실행 전후 `FROZEN.json` 해시 검사 | `dataset_v2.jsonl` 70건과 해시 유지 |
| 모델 전송 request | `expected`, `why`, `gold_chunks`, gold label, 모범 답변 없음 |
| 결과표의 값 하나 | source type, 분자, 분모, 계산식, 방향, 포함·제외 ID, run ID로 추적 가능 |
| endpoint가 ZDR/data collection 조건 미충족 | 입력을 보내지 않고 `Not Measured`와 차단 이유 |
| provider가 비용·token class 미보고 | `Not Reported`, 추정값을 실측으로 표시하지 않음 |
| 이 문서 | 채택 gate, 우선순위, tie 처리, 선택 보류 조건이 고정돼 있고 특정 모델 선정 결론이 없음 |

## 8. 한계

- 이 문서는 결과를 담지 않는다. 결과는 `evals/results/supervisor/2026-11-04-stage1-v1/`와 후속 문서에 있다.
- 사전 등록 번호 없이 작성됐다(후속 문서가 밝힌 한계). 재현 검증은 사전 등록 #29.
