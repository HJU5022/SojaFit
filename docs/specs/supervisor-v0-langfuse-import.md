# Supervisor V0 Langfuse 결과 가져오기

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(평가 결과의 정본: [EVAL_REPORT.md](../../EVAL_REPORT.md), 원시: `evals/results/supervisor/2026-11-06-prompt-v0-v1/`)
- 관련 문서: `evals/runners/RUNNERS.md`, `evals/samples/supervisor_prompt_v0_frozen.json`

## Why

- 페르소나: 세 수퍼바이저 후보의 평가 결과를 비교하는 SojaFit 개발자
- 상황: Supervisor V0 13문항 평가 결과(`evals/results/supervisor/2026-11-06-prompt-v0-v1/`)가 로컬 JSON으로 있다.
- 문제: Langfuse 화면에서 모델별 문항 결과와 같은 규칙 기반 점수를 나란히 비교할 수 없다.
- 측정 지표: Dataset 항목 13개, Experiment 3개, 각 항목의 결정적 점수 7개가 로컬 결과와 일치한다.

## Goal

- 해결 목표: 기존 Supervisor V0 결과를 새 모델 호출 없이 Langfuse Dataset과 Experiment로 가져온다.
- 성공 기준: 입력 13개와 정답 13개를 한 Dataset에 기록하고, 세 모델의 39개 결과에 점수 273개(39 × 7)를 기록한다. 모델별 점수 평균은 로컬 `summary.json`과 일치해야 한다.
- Out of Scope: 모델 재호출, 원본 응답 복원, 기존 호출을 실시간 Langfuse trace로 가장하기, LLM-as-a-judge, 프롬프트 등록·배포, 모델 선정.

## What

### Happy Path
1. 동결 기록으로 Supervisor V0 13문항의 hash와 건수를 확인한다.
2. 세 결과 파일의 dataset·contract hash와 case 집합을 확인한다.
3. `sojafit-supervisor-v0` Dataset에 입력·정답·case metadata를 기록한다.
4. 모델별로 저장된 결정을 반환하는 Experiment를 한 번 실행한다.
5. 문항마다 형식, 네 필드, 의미, 전체 일치 점수를 결정적으로 기록한다.
6. Dataset·Experiment 식별자와 URL을 로컬 영수증에 저장한다.

### Edge Cases

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | dataset hash 또는 contract hash 불일치 | 외부 쓰기 전에 중단 |
| EC-02 | case 누락·중복·추가 | 외부 쓰기 전에 중단 |
| EC-03 | Langfuse 인증 실패 | 중단하고 로컬 결과는 변경하지 않음 |
| EC-04 | 같은 Dataset 항목 재실행 | 고정 UUID로 upsert |
| EC-05 | 가져오기 영수증이 이미 존재 | 기본적으로 중단하여 Experiment 중복 기록 방지 |
| EC-06 | 일부 외부 쓰기 뒤 실패 | 실패를 보고하고 자동 재시도하지 않음 |

## How

- 실행기: `evals/runners/import_supervisor_prompt_v0_langfuse.py`
- 로컬 확인: `uv run python -m evals.runners.import_supervisor_prompt_v0_langfuse plan`
- 외부 쓰기: `uv run python -m evals.runners.import_supervisor_prompt_v0_langfuse import --confirm-langfuse-write`
- Dataset 이름: `sojafit-supervisor-v0`
- Dataset input: `user_request`, `current_state`, `external_material`
- Dataset expected output: `question_type`, `required_evidence`, `next_action`, `reason_code`
- Experiment 이름: `supervisor-v0-{luna|haiku|jev}-{provider}-2026-11-06`
- 점수: `schema_valid`, `question_type_correct`, `required_evidence_exact`, `next_action_correct`, `reason_code_correct`, `semantic_valid`, `exact_decision_match`
- 모든 점수는 `0` 또는 `1`이며 저장된 결과와 정답만 비교한다.
- Experiment trace metadata에 `imported_existing_result=true`를 남긴다. 원래 호출 trace라는 표현은 쓰지 않는다.
- 비밀값과 원본 모델 응답은 Dataset, Experiment output, 영수증에 넣지 않는다.

## AC (Given-When-Then)

| AC | Given-When-Then | 시험 |
|---|---|---|
| AC-01 외부 호출 없는 계획 확인 | 동결 표본과 세 결과 파일이 정상일 때 `plan`은 Dataset 13개, Experiment 3개, 예상 점수 273개를 출력하고 Langfuse 쓰기를 하지 않는다 | `tests/evals/test_import_supervisor_prompt_v0_langfuse.py::test_build_plan_has_fixed_scope_and_no_gold_in_input` |
| AC-02 무결성 오류 선차단 | hash 또는 case 집합이 다르면 Dataset을 만들기 전에 오류로 종료한다 | `test_hash_mismatch_stops_before_any_client_write` |
| AC-03 결과 가져오기 | 인증값과 `--confirm-langfuse-write`가 있으면 Dataset 1개와 Experiment 3개를 만들고 문항마다 점수 7개를 기록한다 | `test_import_uses_saved_rows_and_creates_three_experiments` |
| AC-04 로컬 결과와 점수 일치 | 세 Experiment의 일곱 점수 평균이 로컬 결정적 집계와 일치한다 | 영수증 `external_verification`(아래 구현 상태) |
| AC-05 중복 실행 방지 | 성공 영수증이 있으면 같은 `import`는 새 Experiment를 기록하지 않고 중단한다 | `test_existing_receipt_blocks_external_write` |

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 실행기 | 구현 | `evals/runners/import_supervisor_prompt_v0_langfuse.py` |
| 외부 쓰기 | 실행됨: Dataset 13항목, Experiment 3개, 점수 273개, 모델 호출 0 | `evals/results/supervisor/2026-11-06-prompt-v0-v1/langfuse_import.json`(`dataset_item_count`, `score_count`, `model_calls_performed`) |
| 항목별 점수 합 | schema_valid 39, question_type_correct 38, required_evidence_exact 37, next_action_correct 35, reason_code_correct 38, semantic_valid 34, exact_decision_match 33 (각 39 중) | 같은 파일 `external_verification.score_value_sums` |

## 한계

- 영수증의 `external_verification`은 가져오기 실행기가 쓴 값이다. Langfuse 화면에서 별도로 대조하지 않았다.
- 로컬 `summary.json` 평균과 Langfuse 집계의 일치(AC-04)는 대조하지 않았다.
