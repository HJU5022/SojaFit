# 난이도별 평가 문항 30건 검수 초안

- 상태: 이력
- 기준일: 2026-11-12 (작성 2026-10-30)
- 기준 커밋: 6707002
- 정본 여부: 비정본. 현재 평가셋의 정본은 `evals/dataset_v1.jsonl`과 [FROZEN.json](../../evals/FROZEN.json). 이 30건은 `draft_50.jsonl`을 거쳐 2026-11-02 v1에 동결됐다
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [evaluation-draft-52.md](evaluation-draft-52.md), [draft_30_review.md](../../evals/drafts/reviews/draft_30_review.md), [evals/drafts/DRAFTS.md](../../evals/drafts/DRAFTS.md), [ADR 0003](../adr/0003-평가셋-v1을-50건으로-동결.md)

## 1. 질문과 범위

| 항목 | 내용 |
|---|---|
| 질문 | 회로 확보와 코퍼스 근거 확보를 구분해, 확인하지 않은 정답을 동결하지 않고 질문 30건을 검수할 수 있는가 |
| 구성 | 난이도 쉬움·중간·어려움 각 10건(MCU 없는 단순 회로 / ATtiny85 / Pro Micro). 난이도마다 관련 의도 5건, 비관련 의도 5건. 실제 `kind`는 검수 전 null |
| 위치 | `evals/drafts/sets/draft_30.jsonl`(30행), 검수표 `evals/drafts/reviews/draft_30_review.md` |
| 범위 밖 | 서비스 지원 범위·판정 기준 변경, 확정 정답, 색인·모델 호출·평가 측정·동결 |

## 2. 조건

| 항목 | 규칙 |
|---|---|
| JSONL 키 | 평가 고정 키를 유지하되 `kind`, `expected`, `why`, `corpus_version`은 null, `gold_chunks`는 빈 목록 |
| 행 내용 | `input`, 회로 NET 경로·SHA256, 연결 JSON 경로, `target`, `assumptions`, `question` |
| 의도 칸 | `planned_kind`, `planned_irrelevant_type`은 의도이고, `review_expectation`은 제안이다. 확정 `expected`가 아니다 |
| 모델 입력 | 회로, 대상, 필요한 사용 조건, 자연스러운 질문만. `planned_kind`, `review_expectation`, `review_only_context`, `negative_fixture`, 자료 부재 시 답변 지시는 넣지 않는다. 질문에 "없으면 거절" 같은 채점 방향을 미리 쓰지 않는다 |
| 회로 | 원본 회로·NET을 수정하지 않는다. 필요한 전원·점퍼·부하 조건만 `assumptions`와 `input`에 담는다 |
| 부재 확인 | 의도적으로 없는 품번·문서·개정판을 묻는 문항을 포함한다. 검수자 전용 부재 확인 조건을 `negative_fixture`에 두고, 고정 코퍼스에서 확인한 뒤에만 비관련으로 확정한다. 허위 PDF 생성·원본 변조는 하지 않는다 |
| 유사 문항 | `family`로 묶고 난이도는 계획값으로만 표시 |
| 제조사 | 원래 제조사를 모르는 부품과 허용 제조사 후보를 동일품으로 취급하지 않는다 |

## 3. 수용 기준

| 조건 | 기대 | 확인 |
|---|---|---|
| JSONL 구조 | 고유 ID 30개, 난이도별 10개, 의도별 5/5, 비관련 4유형 | [실측] `planned_kind`·`difficulty` 집계: easy/medium/hard 각 relevant 5 + irrelevant 5, `planned_irrelevant_type` 4유형 |
| 확정 정답 필드 | `kind`가 30행 모두 null, `gold_chunks` 30행 모두 빈 목록 | [실측] |
| 회로 경로·target | NET 해시가 일치하고 연결 JSON에 target이 존재 | 미확인 |
| Markdown·JSONL | 30개 질문·가정·검수 방향이 같고 로컬 링크가 유효 | 미확인 |
| 기존 v1·SPEC | 이 작업에서 변경하지 않음 | 미확인 |
| 모델 입력 누출 | 위 2절 금지 항목이 `input`에 없음 | 미확인 |

## 4. 한계

- 비관련 의도 구성: JSONL의 `planned_irrelevant_type`은 초기 계획대로 15건(`out_of_domain` 3, `unknown_entity` 4, `missing_attribute` 5, `wrong_period` 3)이다. 검수표(`draft_30_review.md:13`)는 11-01에 e08(SS34)·m07(BZX84C3V3)의 데이터시트가 코퍼스에 있어 관련으로 바꿔 관련 17·비관련 13(`unknown_entity` 2)이 됐다고 적는다. 두 파일이 서로 다르다.
- 판정 출처: 이 30건의 정답 초안·1차·2차 판정 기록은 [draft_50_review.md](../../evals/drafts/reviews/draft_50_review.md)에 있다(1차 하정운, 2차 김재훈, 2026-11-02 합의; `:5`). 이 문서에는 판정 결과가 없다.
- 위 3절의 "미확인" 항목은 이번에 대조하지 않았다.
