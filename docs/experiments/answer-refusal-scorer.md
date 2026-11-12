# 답변·거절 5지표 채점기

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(5지표 분류 규칙과 채점기 계약). 측정값의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md)
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [evals/runners/RUNNERS.md](../../evals/runners/RUNNERS.md), [dataset-guide.md](../../evals/guides/dataset-guide.md)

## 1. 질문과 범위

| 항목 | 내용 | 근거 |
|---|---|---|
| 질문 | 답변·거절 5지표(정답 근거 인용, 오답 근거, 과잉 거절, 올바른 거절, 환각 위험)를 한 기준으로 결정적으로 계산할 수 있는가 | `evals/runners/score_answer.py` |
| 대상 평가셋 | 동결 v1 50건(관련 25, 비관련 25), v2 70건(관련 35, 비관련 35) | `evals/FROZEN.json` |
| 호출 | LLM 호출 0회(규칙 기반) | `score_answer.py` |
| 범위 밖 | LLM 판정자를 쓴 자유 서술 의미 채점, 동결 평가셋 수정 | |

## 2. 채점 규칙

입력은 평가셋 문항 `item`(`id`, `input`, `kind`, `irrelevant_type`, `expected`, `gold_chunks`, `question_type`)과 그래프 최종 상태 `state`(`path`, `answer`, `docs`, `passed`, `check`, `target_part`)다. 문항 하나는 아래 표에서 정확히 하나의 지표로 분류된다.

| kind | 조건 | 지표 |
|---|---|---|
| relevant | 거절 응답 | `over_refusal` |
| relevant | 답변이고 유효 인용이 있으며 허위 인용이 없고, 인용 근거가 `gold_chunks`와 일치 | `cited_gold` |
| relevant | 답변이지만 허위 인용 1개 이상, 유효 인용 없음, 또는 정답 근거와 불일치 | `wrong_citation` |
| irrelevant | 거절 응답 | `correct_refusal` |
| irrelevant | 거절하지 않고 답변 | `hallucination_risk` |

정답 근거 일치 규칙: 데이터시트 근거(`gold_locations`, `(PDF 파일명, 쪽)` 집합)가 있으면 인용 청크 중 최소 1장이 일치해야 한다. 근거가 회로 넷리스트(`gold_chunks`에 `.net` 경로)뿐이면 `[넷리스트]`를 인용해야 한다.

거절 응답 판별(`is_refusal_response`, `score_answer.py:69`): `path` 마지막 노드가 `거절`, 답이 빈 문자열, 범위 밖 안내로 시작하거나, `문서로 확인 안 됨`으로 시작하면서 유효 인용이 없는 경우. `문서로 확인 안 됨`으로 시작해도 유효한 근거 번호를 인용해 조건 부족(`NOT_VERIFIED`)을 설명하면 거절이 아니라 답변이다(문항 n01, n02).

| # | 경계 사례 | 처리 | 시험 |
|---|---|---|---|
| 1 | `NOT_VERIFIED` 문항에서 `문서로 확인 안 됨`으로 시작하나 정답 청크를 인용해 설명 | 인용 근거를 대조해 `cited_gold` | `test_ac04_relevant_not_verified_distinguishes_cited_explanation_from_bare_refusal` |
| 2 | `NOT_VERIFIED` 문항에서 거절 노드로 끝나거나 인용 없이 `문서로 확인 안 됨`만 출력 | `over_refusal` | 같은 시험 |
| 3 | 정답 청크와 함께 넘기지 않은 번호(허위 인용)를 인용 | `wrong_citation` | `test_ac03_relevant_wrong_page_or_fake_citation_is_wrong_citation` |
| 4 | 같은 PDF의 다른 쪽(또는 표지 `page=None`)만 인용 | `wrong_citation` | 같은 시험 |
| 5 | 제외 문항 ID 등록 | 5지표 분자·분모에서 제외하고 `excluded_ids`에 기록 | `test_ac06_score_dataset_denominators_and_exclusions_on_v1_and_v2` |
| 6 | 한 문항에 `without`/`with` 두 답(Skill 비교 실행기) | 모드별로 같은 `score_item()` 사용 | `score_answer.py:195` `_extract_states`, `:221` `main` |
| 7 | 판정 길 답(`check["judgement"]` 참)은 `[n]` 대신 사양 표 행의 문서·쪽을 인용 | 판정 결과의 `(document, page)`를 `[n]` 인용과 같은 방식으로 대조. 판정은 `results`, 찾기는 답에 나간 후보 `shown`만 센다. 사전 등록 #39, #40 | `test_judge_answer_citing_gold_page_is_cited_gold`, `test_judge_answer_citing_other_page_is_wrong_citation`, `test_find_answer_counts_only_shown_candidates`, `test_combined_answer_counts_both_chunk_and_spec_table_citations` |

## 3. 구현

| 항목 | 내용 |
|---|---|
| 모듈 | `evals/runners/score_answer.py`: `score_item(item, state)`, `score_dataset(items, states_by_id, *, excluded_ids=None)` |
| 실행기 연동 | `evals/runners/run_graph.py:31` `run_scores(state, seconds, llm_calls, item=None)`. `item`을 주면 `answer_metric`(CATEGORICAL)을 함께 돌려 Langfuse 트레이스 점수에 붙인다. 3인자 호출은 그대로 동작 |
| CLI | `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [결과 저장 json]` |
| 제외 목록 | `evals/` 아래 `exclusions.json`을 읽는다(`score_answer.py:25`). 파일이 저장소에 없으므로 제외 문항은 0이다 |

## 4. 수용 기준과 시험

| AC | 조건 | 기대 | 시험(`tests/evals/test_score_answer.py`) |
|---|---|---|---|
| 01 | 데이터시트 근거 관련 문항, 정답 청크를 인용하고 허위 인용 없음 | `cited_gold`, 거절 아님 | `test_ac01_datasheet_relevant_cited_gold` |
| 02 | 넷리스트만 근거인 관련 문항 | `[넷리스트]` 인용이면 `cited_gold`, 없거나 허위 인용이면 `wrong_citation` | `test_ac02_circuit_only_relevant_requires_netlist_citation` |
| 03 | 정답 쪽이 아닌 근거만 인용 또는 허위 인용 | `wrong_citation` | `test_ac03_...` |
| 04 | `NOT_VERIFIED` 관련 문항 | 경계 사례 1, 2 | `test_ac04_...` |
| 05 | 비관련 문항(`out_of_domain`, `unknown_entity`, `missing_attribute`, `wrong_period`) | 거절이면 `correct_refusal`, 답변이면 `hallucination_risk` | `test_ac05_irrelevant_correct_refusal_vs_hallucination_risk` |
| 06 | v1 50건, v2 70건 집계 | 관련 세 지표 합과 비관련 두 지표 합이 제외 문항을 뺀 모수와 일치 | `test_ac06_...` |
| 연동 | `item`을 준 `run_scores` | `answer_metric` 포함 | `test_run_graph_scores_include_answer_metric_when_item_given` |

시험 실행 [실측]: `tests/evals/test_score_answer.py`와 `tests/evals/test_saved_defense_replay.py`를 함께 돌려 19 passed(2026-11-12, 오프라인).

## 5. 결과

이 문서에는 측정값이 없다. 5지표 측정값은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 2, 3, 4장이 정본이다.

## 6. 한계

- 의미 채점이 없다. 인용한 청크가 정답 쪽과 일치하는지만 보고 답 문장이 정답 내용과 같은지는 보지 않는다. 한계 서술은 `EVAL_REPORT.md` 2장.
- 경계 사례 1~2의 `NOT_VERIFIED` 예외는 코드(`is_refusal_response`)에서 문항 종류와 무관하게 적용된다.
- AC 문장과 시험 함수의 대응은 이름으로 연결했고 문장별 본문 대조는 하지 않았다.
