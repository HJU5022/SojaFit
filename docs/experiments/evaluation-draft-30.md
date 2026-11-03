# 난이도별 평가 문항 30건 검수 초안

## Why
- 평가 담당자가 모은 회로를 실제 질문으로 검수할 수 있어야 한다.
- 문항 작성자와 합의한 난이도는 MCU 없는 단순 회로 / ATtiny85 / Pro Micro다.
- 회로 확보와 코퍼스 근거 확보를 구분하고, 확인하지 않은 정답을 동결하지 않는다.

## Goal
- 초안 30건, 쉬움·중간·어려움 각 10건을 작성한다.
- 각 난이도에서 관련 의도 5건·비관련 의도 5건을 배치한다. 실제 kind는 검수 전 null이다.
- 비관련 의도 13건은 out_of_domain 3, unknown_entity 2, missing_attribute 5, wrong_period 3으로 구성한다. unknown_entity는 처음 4건이었으나 e08(SS34)·m07(BZX84C3V3)의 데이터시트가 코퍼스에 있어 11-01에 관련으로 바꿨다.
- Out of Scope: 서비스 지원 범위·판정 기준 변경, 확정 정답, 색인·모델 호출·평가 측정·동결.

## What
- 검수자는 Markdown에서 질문·가정·예상 답변 방향·검수 필요 자료를 읽고 수정한다.
- 같은 내용의 JSONL은 평가 고정 키를 유지하되 kind·expected·why·corpus_version은 null로 둔다.
- 특정 문서·개정판이 없다는 가정은 현재 자료의 확정 사실이 아니라 검수할 분류 의도로 기록한다.
- 유사 문항은 family로 묶고 난이도는 계획값으로만 표시한다.
- 사용자 질문은 자연스럽게 작성한다. 근거 부재 시 거절·대체 인용 금지·시험 조건 확인 같은 채점 방향을 질문에 미리 지시하지 않는다.

## How
- 위치: evals/drafts/sets/draft_30.jsonl, evals/drafts/reviews/draft_30_review.md. 기존 v1·연습 10건은 보존한다.
- 각 행에 input, 회로 NET 경로·SHA256, 연결 JSON 경로, target, assumptions, question을 기록한다.
- planned_kind·planned_irrelevant_type은 의도, review_expectation은 제안이며 확정 expected가 아니다.
- 원래 제조사를 모르는 부품과 허용 제조사 후보를 동일품으로 취급하지 않는다.
- 원본 회로·NET을 수정하지 않는다. 사용자에게 필요한 전원·점퍼·부하 조건만 assumptions와 input에 담는다. 메타 지침·정답 힌트는 review_only_context로 분리하고 모델에 제공하지 않는다.
- 의도적으로 없는 품번·문서·개정판을 요청하는 문항을 포함한다. negative_fixture에는 검수자 전용 부재 확인 조건을 기록하고, 고정 코퍼스에서 확인한 뒤에만 비관련을 확정한다. 허위 PDF 생성·원본 변조는 하지 않는다.
- 초안은 실행·동결하지 않는다. 독립 질문 작성 여부와 2인 검수는 별도 확인한다.

## AC
- Given JSONL, When 구조 확인, Then 고유 ID 30개·난이도별 10개·의도별 5/5·비관련 4유형의 계획 수량이 일치한다.
- Given 회로 경로·target, When 파일 대조, Then NET 해시가 일치하고 연결 JSON에 target이 존재한다.
- Given 초안, When 확인, Then 확정 정답 필드가 null·gold_chunks가 빈 목록이고 검수용 표시가 있다.
- Given Markdown, When 대조, Then JSONL의 30개 질문·가정·검수 방향과 같고 로컬 링크가 유효하다.
- Given 기존 v1·SPEC, When diff 확인, Then 이 작업에서 변경하지 않는다.

- Given 모델 입력, When 누출 확인, Then planned_kind·review_expectation·review_only_context·negative_fixture 및 자료 없을 때의 답변 지시가 input에 포함되지 않는다.
