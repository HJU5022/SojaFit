# Supervisor V0 Langfuse 결과 가져오기

## Why

- **페르소나**: 세 수퍼바이저 후보의 평가 결과를 비교하는 SojaFit 개발자
- **상황**: 2026-11-06에 끝난 13문항 평가 결과는 로컬 JSON에만 있다.
- **문제**: Langfuse 화면에서 모델별 문항 결과와 같은 규칙 기반 점수를 나란히 비교할 수 없다.
- **측정 지표**: Dataset 항목 13개, Experiment 3개, 각 항목의 결정적 점수 7개가 로컬 결과와 일치한다.

## Goal

- **해결 목표**: 기존 Supervisor V0 결과를 새 모델 호출 없이 Langfuse Dataset과 Experiment로 가져온다.
- **성공 기준**: 입력 13개와 정답 13개를 한 Dataset에 기록하고, 세 모델의 39개 결과에 점수 273개(39 × 7)를 기록한다. 모델별 점수 평균은 로컬 `summary.json`과 일치해야 한다.
- **Out of Scope**: 모델 재호출, 원본 응답 복원, 기존 호출을 실시간 Langfuse trace로 가장하기, LLM-as-a-judge, 프롬프트 등록·배포, 모델 선정.

## What

**Happy Path**
1. 동결 기록으로 Supervisor V0 13문항의 hash와 건수를 확인한다.
2. 세 결과 파일의 dataset·contract hash와 case 집합을 확인한다.
3. `sojafit-supervisor-v0` Dataset에 입력·정답·case metadata를 기록한다.
4. 모델별로 저장된 결정을 반환하는 Experiment를 한 번 실행한다.
5. 문항마다 형식, 네 필드, 의미, 전체 일치 점수를 결정적으로 기록한다.
6. Dataset·Experiment 식별자와 URL을 로컬 영수증에 저장한다.

**Edge Cases**

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

**AC-01 · 외부 호출 없는 계획 확인**
- GIVEN: 동결 표본과 세 결과 파일이 정상이다.
- WHEN: `plan`을 실행한다.
- THEN: Dataset 13개, Experiment 3개, 예상 점수 273개를 출력하고 Langfuse 쓰기를 하지 않는다.

**AC-02 · 무결성 오류 선차단**
- GIVEN: hash 또는 case 집합이 다르다.
- WHEN: `plan` 또는 `import`를 실행한다.
- THEN: Dataset을 만들기 전에 오류로 종료한다.

**AC-03 · 결과 가져오기**
- GIVEN: Langfuse 인증값과 `--confirm-langfuse-write`가 있다.
- WHEN: `import`를 실행한다.
- THEN: Dataset 1개와 Experiment 3개를 만들고 각 문항에 7개 점수를 기록한다.

**AC-04 · 로컬 결과와 점수 일치**
- GIVEN: 가져오기가 끝났다.
- WHEN: 세 Experiment의 점수를 집계한다.
- THEN: 일곱 점수 평균이 로컬 결정적 집계와 일치한다.

**AC-05 · 중복 실행 방지**
- GIVEN: 성공 영수증이 이미 있다.
- WHEN: 같은 `import` 명령을 다시 실행한다.
- THEN: 새 Experiment를 기록하지 않고 중단한다.
