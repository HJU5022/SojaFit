# 실패 사례 분석

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(제출물). 수치의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 5, 6, 11장
- 관련 문서: [DELIVERABLES.md](DELIVERABLES.md), [ai_tools_log.md](ai_tools_log.md), [demo_script.md](demo_script.md), 사전 등록 [preregister.md](../../evals/guides/preregister.md)

## 1. 요약

품번 없는 조건형 검색은 정답 쪽이 후보 50 밖에 남는다. 표 주석이 행에 붙지 않는 표(약 216)는 행 단위 조건이 빠진다. 코드 판정은 불충족인데 설명 글이 "사용해도 된다"고 나가던 충돌은 수정 전 C2 사례에서 관찰됐고, 판정 답을 코드 판정 틀로만 내도록 막았다.

## 2. 실패 사례

| # | 입력 | 기대 | 실제 | 틀린 단계 | 근거 |
|---|---|---|---|---|---|
| 1 | 분류와 조건만 있는 질문(R1 무리 G4: test r1-091, r1-097, dev r1-083·089·090·094·100) | 정답 쪽이 후보 50·상위 5 안 | 품번 필터를 못 걸어 정답 쪽이 후보 50 밖 | 검색 | EVAL_REPORT 5장 유형 4 |
| 2 | 표 옆 Notes가 필요한 정격·조건(v1 draft50-n04, 코퍼스 1,360건의 표 약 216) | 주석이 해당 표 행 청크에 붙음 | THERMAL·두 쪽 표 등에서 주석표시만 있거나 주석 없음 | 청킹 | EVAL_REPORT 5장 유형 6, 11장 2행 |
| 3 | C2: 코드 판정 불충족 + 문서에 거짓 적합 주장 | 최종 답에 사용 권고 0 | 수정 전: 판정표 옆에 "DEMO2를 사용해도 된다고 말할 수 있습니다 [73]"이 최종 답에 나감 | 답 정리·종합 | `evals/results/threads/claim_consistency_live_2026-11-10.json`, EVAL_REPORT 6장 5행 |
| 4 | v3-20: 정격 질문(SS14H의 H 뜻), Supervisor 첫 검색어가 주문 정보만 찾음 | 정격표까지 인용 | 답 쓰기가 partial로 채점했는데 재검색 없이 정격 근거 없이 답함 | RAG 에이전트 | EVAL_REPORT 5장 유형 14, 사전 등록 #49 |

수치: 사례 1의 R1 test G4 Page Recall@5는 0.625이다(EVAL_REPORT 11장 1행).

## 3. 원인 확인 방법

| 영역 | 방법 | 근거 |
|---|---|---|
| 검색 | R1 단계별 결과의 후보 밖(`outside_candidates`)과 top-k 밖(`below_top_k`) 분류, 품번 필터를 끈 대조(#24) | EVAL_REPORT 5장 유형 1~5 |
| 청킹 | ADR 0015의 알려진 결함에서 시작해 청킹 `tsc-v4h-2026-11-08`로 Notes를 붙임. 약 216표의 분해(THERMAL 122, 두 쪽 61, 기타 32, 오탐 1)는 위키 원장 값이며 원시 점검 파일은 저장소에 없다. `table_suspects` 89건은 파서 불일치라 다른 집합이다 | EVAL_REPORT 11장 2행 |
| 판정·답 충돌 | C2 실제 모델 1회 관찰(수정 전), 출력 경계 수정 뒤 사전 등록 #51 재측정과 D9 재확인(사용 권고 0) | [c2-defense-recheck.md](../experiments/c2-defense-recheck.md) |
| partial 재검색 | v3-20 실패 트레이스에서 검색어가 주문 정보에만 묶인 것을 확인, 사전 등록 #49 | EVAL_REPORT 5장 유형 14 |

판정 출처: D9 재확인의 "사용 권고 0"은 `EVAL_REPORT.md:542`의 서술이다. 원시 파일(`claim_consistency_d9_recheck_2026-11-12.json`)의 `semantic_summary`는 `pending_manual_review`이고 사람 검토 기록은 없다. 원시 `answer` 세 건에 권고 표현이 없음은 키워드 검색으로 확인했다(assistant 확인). 수정 뒤 4단계 재측정(#51)의 의미 검토는 assistant의 원시 대조이며 독립 사람·LLM 판정이 아니다(`claim_consistency_after_review_20261109T203153Z.json` `reviewer`).

## 4. 바꾼 것

| 실패 | 조치 | 연결 |
|---|---|---|
| 검색어에 회로 낱말 | 질문 줄만 검색, 재작성 Q3 | #28 S1, 5장 유형 1 |
| 표지·순위 밀림 | 표지 청크 제외, `rerank-3`, `voyage-4-large` | #28 S2~S4 |
| Notes 누락 | 청킹 v4h의 Notes 부착 | `tsc-v4h-2026-11-08`, 5장 유형 6 |
| 판정과 설명 충돌 | 판정 답은 코드 판정 틀만 | #51, EVAL_REPORT 6장, D9 재확인 |
| partial 미재검색 | 다음 검색어가 있으면 1회 더 | #49, 5장 유형 14 |

## 5. 못 고친 것

| 항목 | 상태 | 근거 |
|---|---|---|
| 품번 없는 질의의 후보 50 밖 | 남음(R1 test G4 Page Recall@5 0.625) | EVAL_REPORT 11장 1행 |
| 표 주석 미부착 약 216표 | 남음. 동결셋 검색 지표로 재측정하지 않음 | EVAL_REPORT 11장 2행 |
| 배포 HTTP 인젝션 T4 흔들림 | 토큰 한도 5M/10M 배포 뒤 재측정 전 | EVAL_REPORT 11장 3행 |
| 승인 대기 시간 | 값 없음 | EVAL_REPORT 11장 4행 |
| Langfuse 캡처, 시연 영상 파일 | 없음 | [DELIVERABLES.md](DELIVERABLES.md) |

순위와 한계 표의 정본은 EVAL_REPORT 11장이다.

## 6. 남은 일

D12 마감(11/17)이 이 글에 요구하는 항목 중 아직 없는 것이다.

| 항목 | 현재 | 쓸 수 있는 저장소 근거 |
|---|---|---|
| 코드로 되돌린 결정 1건과 이유 | 이 글에 없음 | 후보: Supervisor를 Sonnet에서 Haiku로만 바꾼 사전 등록 #46. 받지 않는 조건에 걸려 되돌림(통과 47·45/50, 무관 거절 23·24/25; `evals/guides/preregister.md:779-789`), `README.md` 3절 |
| 미채택 실험 | 이 글에 없음 | 레버 A/B의 폐기·보류 항목: [speed-p95-levers-2026-11-11.md](../experiments/speed-p95-levers-2026-11-11.md), 임베딩 후보 확장 평가기 설계 [embedding-candidate-runner.md](../experiments/embedding-candidate-runner.md)(구현 없음) |
| 막지 못한 것(인젝션) | 이 글에 부분적으로만 있음 | EVAL_REPORT 6장 "믿지 않기로 한 것"과 남은 한계 |
| 판정자가 팀원뿐인 한계 | 이 글에 없음 | v1 평가셋 정답의 사람 판정은 팀원이다([draft_50_review.md](../../evals/drafts/reviews/draft_50_review.md): 하정운 1차, 김재훈 2차. v3의 정답 출처·판정자는 [EVAL_REPORT.md](../../EVAL_REPORT.md) 10장 첫 단락. 외부 검토자 1명의 검토는 미실시: [evaluation-prep.md](../reference/evaluation-prep.md)) |
