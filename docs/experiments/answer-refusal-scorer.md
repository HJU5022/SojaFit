# 답변·거절 5지표 채점기 (Answer & Refusal 5-Metric Scorer)

상태: 구현(`evals/runners/score_answer.py`)과 회귀 테스트(`tests/evals/test_score_answer.py`) 반영.

## Why

- **페르소나**: 줄기 그래프(`evals/runners/run_graph.py`)와 Skill 비교 실행기(`evals/runners/run_skill_pair.py`)의 결과를 동결 평가셋(`evals/dataset_v1.jsonl` 50건, `evals/dataset_v2.jsonl` 70건)으로 재측정·비교하는 평가·문서 담당자와 에이전트 담당자
- **상황**: `evals/runners/run_retrieval.py`는 검색 지표(문서 Recall@k, MRR, Page Hit@k)만 재고, `evals/runners/run_graph.py`는 실행 경로·검색 횟수·허위 인용 번호(`fake_citations`)·인용 누락 문장(`uncited_sentences`)만 기록한다.
- **문제**:
  1. `EVAL_REPORT.md` 2장과 G5가 요구하는 **답변·거절 5지표**(정답 근거 인용률, 오답 근거, 과잉 거절, 올바른 거절, 환각 위험)를 하나의 일관된 기준으로 계산하는 코드가 없다.
  2. `evals/guides/dataset-guide.md`와 `SPEC.md` 4절이 정한 `relevant + NOT_VERIFIED` 문항(`n01, n02`: 후보 문서 근거는 있으나 사용자 동작 조건 부족으로 판정이 `NOT_VERIFIED`인 관련 문항)을 단순 문자열(`"문서로 확인 안 됨"`)만 보고 채점하면 정답대로 답해도 **과잉 거절**로 잘못 집계된다.
  3. 인용 번호(`[7]`, `[넷리스트]`)가 통과 청크 안에 있는지만 보면(`fake_citations == []`), 실제로 인용한 청크가 `gold_chunks`의 정답 문서·쪽 또는 넷리스트와 맞는지(`정답 근거 인용률` 대 `오답 근거`) 구분할 수 없다.
- **측정 지표**: 동결 `dataset_v1.jsonl` 50건(관련 25·비관련 25) 및 `dataset_v2.jsonl` 70건(관련 35·비관련 35)에 대해 5지표의 문항별 분류가 누락·중복 없이 합산 모수와 맞아떨어지고, `n01·n02` 및 인용 일치·불일치 경계 테스트를 100% 통과한다.

## Goal

- **해결 목표**: 평가셋 문항(`item`)과 그래프 실행 결과(`state`)를 받아 문항별 5지표 판정과 전체 요약(비율·건수·문항 ID 목록)을 결정적(규칙 기반, LLM 호출 0회)으로 계산하는 채점 모듈 `evals/runners/score_answer.py`를 구현하고 `evals/runners/run_graph.py`의 트레이스 점수에 연결한다.
- **성공 기준**:
  - 관련 문항(v1 25건, v2 35건)마다 정확히 `cited_gold`(정답 근거 인용), `wrong_citation`(오답 근거), `over_refusal`(과잉 거절) 셋 중 하나로 분류되어 세 건수의 합이 평가 대상 관련 문항 수와 일치한다.
  - 비관련 문항(v1 25건, v2 35건)마다 정확히 `correct_refusal`(올바른 거절) 또는 `hallucination_risk`(환각 위험) 둘 중 하나로 분류되어 두 건수의 합이 평가 대상 비관련 문항 수와 일치한다.
  - `evals/exclusions.json`에 등록된 제외 문항이 있으면 지표 분모에서 빼고 제외 건수·ID를 함께 보고한다.
- **Out of Scope**:
  - LLM-as-judge를 통한 자유 서술 문장의 의미적 정답 일치 채점(생성 모델과 같은 모델로 채점하면 후한 점수가 나오고 API 비용이 들므로, 이 모듈은 결정적 근거·거절·인용 대조만 수행하며 의미 채점 한계는 `EVAL_REPORT.md` 2장에 명시한다).
  - 동결 평가셋(`evals/dataset_v1.jsonl`, `evals/dataset_v2.jsonl`, `evals/FROZEN.json`) 수정.

## What

**Happy Path**
1. 채점기는 평가셋 문항 `item`(`id`, `input`, `kind`, `irrelevant_type`, `expected`, `gold_chunks`, `question_type`)과 그래프 최종 상태 `state`(`path`, `answer`, `docs`, `passed`, `check`, `target_part`)를 입력받는다.
2. 문항의 `gold_chunks`에서 요구 근거를 두 부류로 뽑는다:
   - 데이터시트 근거 `gold_locations`: `evals/runners/run_retrieval.py`의 `gold_locations()`와 같이 `(PDF 파일명, 페이지 번호)` 집합
   - 회로 넷리스트 근거 `needs_netlist`: `gold_chunks` 문자열 중 `.net` 경로가 들어 있는 항목 존재 여부
3. 응답이 거절인지 답변인지 판별한다:
   - `path`의 마지막 노드가 `"거절"`이거나, `answer`가 빈 문자열이거나, `answer`가 `"문서로 확인 안 됨"`으로 시작하거나 `"범위 밖"` 거절 문구이면 **거절 응답(`is_refusal=True`)**으로 본다.
   - 단, **예외(`relevant + NOT_VERIFIED`)**: `item["kind"] == "relevant"`이고 `item["expected"]`에 `"NOT_VERIFIED"`(또는 `"문서로 확인 안 됨"`)가 정답 판정으로 명시된 문항(예: `n01, n02`, 또는 부가 판정이 `NOT_VERIFIED`인 `e08, m04, m05, h04, h05`)에서:
     - 그래프가 `"거절"` 노드로 끝나 아예 데이터시트/회로 근거 인용 없이 멈췄거나, 생성 노드가 근거 인용 없이 `"문서로 확인 안 됨"` 한 줄만 냈다면 후보 정격·조건 근거를 제시하지 못했으므로 **과잉 거절(`over_refusal`)**이다.
     - 생성 노드가 근거 번호(`[청크번호]` 또는 `[넷리스트]`)를 인용해 후보 정격·조건을 설명하면서 `NOT_VERIFIED`/`문서로 확인 안 됨`을 포함했다면 거절이 아니라 **답변 응답(`is_refusal=False`)**으로 보고 아래 인용 근거 대조(4번)로 넘긴다.
4. 관련 문항(`kind == "relevant"`) 채점:
   - `is_refusal == True`이면 **과잉 거절(`over_refusal`)**.
   - `is_refusal == False`이면 실제로 인용한 유효 근거(`check["used"]`, 없으면 `citations(answer)`와 통과 청크·넷리스트 교집합)를 확인한다:
     - 허위 인용(`check["fake_citations"]`)이 1개 이상이거나, 인용한 유효 근거가 하나도 없으면(`used == []`) **오답 근거(`wrong_citation`)**.
     - 인용한 청크들의 `(file, page)` 집합과 `[넷리스트]` 인용 여부를 `gold_chunks`와 대조한다:
       - 데이터시트 근거가 있는 문항(`gold_locations`가 비어 있지 않음): 인용한 청크 중 최소 1장이 `gold_locations`의 `(file, page)`와 일치해야 한다.
       - 회로 넷리스트만 근거인 문항(`gold_locations`가 비어 있고 `needs_netlist`가 참, 예: `e01, e02, m01, m02, h01, h02`): `"[넷리스트]"`를 인용해야 한다.
       - 위 조건을 만족하고 허위 인용이 없으면 **정답 근거 인용(`cited_gold`)**, 아니면 **오답 근거(`wrong_citation`)**.
5. 비관련 문항(`kind == "irrelevant"`) 채점:
   - `is_refusal == True`이고 근거 번호를 붙여 수치·판정을 단정하지 않았으면 **올바른 거절(`correct_refusal`)**.
   - `is_refusal == False`(거절하지 않고 답변을 생성함)이면 **환각 위험(`hallucination_risk`)**.
6. 문항 묶음 채점(`score_dataset`)은 제외 목록(`exclusions.json`)을 뺀 뒤 5지표 각각의 분자·분모·비율과 문항 ID 목록, 열린 정답 후보 찾기 문항(`candidate_find_ids`)을 돌려준다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | `n01, n02`처럼 `kind="relevant"`이고 `expected` 첫 문장이 `판정은 문서로 확인 안 됨(NOT_VERIFIED)`인데, 답변이 `"문서로 확인 안 됨"`으로 시작하지만 뒤에 정답 청크(`[1]`)를 인용해 시험 조건 차이를 설명함 | 유효 인용(`used`)이 있으면 단순 시작 문자열로 `over_refusal` 처리하지 않고 인용 근거를 대조해 정답 페이지이면 `cited_gold`로 채점한다 |
| EC-02 | `n01, n02`에서 검색 실패로 `"거절"` 노드로 끝났거나 인용 없이 `"문서로 확인 안 됨"`만 출력함 | 후보 정격과 부족한 조건 근거를 전혀 제시하지 못했으므로 `over_refusal`로 채점한다 |
| EC-03 | 관련 문항에서 정답 청크(`[2]`)도 인용했지만 동시에 넘긴 적 없는 번호(`[999]`, `fake_citations`)도 인용함 | 없는 근거를 지어내 인용했으므로 `cited_gold`로 인정하지 않고 `wrong_citation`으로 채점한다 |
| EC-04 | 관련 문항에서 같은 PDF(`1N5817 SERIES_H2104.pdf`)를 인용했으나 정답 페이지(1쪽)이 아닌 다른 쪽(2쪽이나 표지 `page=None`)만 인용함 | `(file, page)`가 `gold_locations`와 일치하지 않으므로 `wrong_citation`으로 채점한다 |
| EC-05 | `evals/exclusions.json`에 제외 문항 ID가 등록되어 있음 | 해당 ID는 5지표 분자·분모에서 모두 제외하고 `excluded_ids`에 기록한다 |
| EC-06 | `run_skill_pair.py` 결과처럼 한 문항에 `without` / `with` 두 답변이 들어 있음 | 각 모드별로 `(state + answer/check)`를 합쳐 같은 `score_item()` 함수로 동일하게 채점할 수 있게 지원한다 |
| EC-07 | 판정 길 답(`check["judgement"]`가 참, 코드 틀 답)은 `[n]` 대신 사양 표 행의 문서 · 쪽 · 표 · 행을 인용함 | 판정 결과(`judgement`)의 인용 `(document, page)`를 `[n]` 인용 위치와 같은 방식으로 `gold_locations`와 대조한다. 인용이 없으면 `wrong_citation`(11-06, 사전 등록 #39 · #40) |

## How

- **모듈 위치**: `evals/runners/score_answer.py`
- **핵심 함수 계약**:
  - `score_item(item: dict, state: dict) -> dict`
  - `score_dataset(items: list[dict], states_by_id: dict[str, dict], *, excluded_ids: set[str] | None = None) -> dict`
  - `evals/runners/run_graph.py` 연동:
    - `run_scores(state, seconds, llm_calls, item=None)`: 선택 인자 `item`이 주어지면 `answer_metric`(`CATEGORICAL`, 5지표 중 하나)을 함께 돌려주어 Langfuse 트레이스에 평가 점수가 바로 연결되게 한다(G6 충족 보강). 기존 `run_scores(state, seconds, llm_calls)` 3인자 호출 호환성은 그대로 유지한다.
- **CLI 실행**:
  - `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [결과 저장 json]`

## AC (Given-When-Then)

**AC-01 · 데이터시트 관련 문항 정답 근거 인용(`cited_gold`)**
- GIVEN: `kind="relevant"`, `gold_chunks=["1N5817 SERIES_H2104.pdf, 1쪽, ..."]`인 문항과 통과 청크 `chunk_id=7`(`1N5817 SERIES_H2104.pdf`, 1쪽)을 `[7]`로 인용하고 허위 인용이 없는 생성 응답
- WHEN: `score_item(item, state)`를 호출하면
- THEN: `metric == "cited_gold"`이고 `is_refusal is False`이다.

**AC-02 · 회로 전용 관련 문항 넷리스트 인용(`cited_gold` 대 `wrong_citation`)**
- GIVEN: `kind="relevant"`이고 `gold_chunks`에 `.net`만 있는 역할 질문(`e01`)
- WHEN: 응답이 `[넷리스트]`를 인용하면 `cited_gold`이고, 인용이 없거나 허위 인용이 있으면 `wrong_citation`이다.

**AC-03 · 관련 문항 오답 근거(`wrong_citation`)**
- GIVEN: `kind="relevant"`, 정답이 `1N5817 SERIES_H2104.pdf` 1쪽인 문항
- WHEN: 응답이 다른 문서나 다른 쪽(2쪽 또는 표지 `page=None`)만 인용했거나 `fake_citations`가 1개 이상이면
- THEN: `metric == "wrong_citation"`이다.

**AC-04 · 관련 문항 과잉 거절(`over_refusal`)과 `NOT_VERIFIED` 예외 구분**
- GIVEN: `kind="relevant"`이고 `expected`에 `NOT_VERIFIED`가 포함된 `n01` 문항
- WHEN: 그래프가 `"거절"` 노드로 끝나거나 근거 인용 없이 `"문서로 확인 안 됨"`만 답하면 `metric == "over_refusal"`이고, 정답 청크(`1N5817 SERIES_H2104.pdf` 1쪽)를 `[1]`로 인용하며 `"문서로 확인 안 됨(NOT_VERIFIED)"`을 설명하면 `metric == "cited_gold"`이다.

**AC-05 · 비관련 문항 올바른 거절(`correct_refusal`) 대 환각 위험(`hallucination_risk`)**
- GIVEN: `kind="irrelevant"`인 비관련 문항(`out_of_domain`, `unknown_entity`, `missing_attribute`, `wrong_period`)
- WHEN: 거절 노드로 끝나거나 생성 노드가 `"문서로 확인 안 됨"`으로 거절하면 `metric == "correct_refusal"`이고, 거절하지 않고 일반 답변을 내면 `metric == "hallucination_risk"`이다.

**AC-06 · 평가셋(v1 50건·v2 70건) 집계 분모 보존 및 제외 문항 처리**
- GIVEN: 관련·비관련 반반 평가셋(`dataset_v1.jsonl` 50건, `dataset_v2.jsonl` 70건)과 `excluded_ids={"draft50-n15"}`
- WHEN: `score_dataset()`을 실행하면
- THEN: 관련 세 지표 건수 합과 비관련 두 지표 건수 합(`n15` 제외)이 정확히 일치하고 비율이 계산된다.
