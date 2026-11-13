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
| 배포 HTTP 인젝션 T4 흔들림 | 토큰 한도 상향 배포 뒤 재측정 전 | EVAL_REPORT 11장 3행 |
| 승인 대기 시간 | 값 없음 | EVAL_REPORT 11장 4행 |
| Langfuse 캡처, 시연 영상 파일 | 없음 | [DELIVERABLES.md](DELIVERABLES.md) |

순위와 한계 표의 정본은 EVAL_REPORT 11장이다.

## 6. 코드로 되돌린 결정 (2026-11-13 추가)

Supervisor 모델을 Sonnet 5.5에서 Haiku 5.5로 바꾸는 시도(사전 등록 #46, 2026-11-09)를 측정 뒤 되돌렸다.

| 항목 | 내용 | 근거 |
|---|---|---|
| 왜 바꾸려 했나 | Sonnet Supervisor가 v3 세트당 LLM 비용의 약 80%였다(세트당 약 $0.17) | `evals/guides/preregister.md` #46 "왜" |
| 받지 않는 조건(측정 전 기록) | 질문 종류 불일치 2개 이상, 무관 거절 실패 1개 이상, 통과 48/50 이하면 되돌린다 | `evals/guides/preregister.md` #46 |
| 결과 | 통과 47 · 45/50, 무관 거절 23 · 24/25(v3-31 · v3-34 · v3-32에 답함). 조건에 걸려 커밋 `077f6e4`로 되돌림 | `evals/guides/preregister.md` #46 측정 결과, `README.md` 3절 |
| 원인 | 사실 확인이 "코퍼스에 없음"이라 했는데 판정을 시킴, 질문 종류는 맞혔는데 찾기를 RAG 에이전트로 보냄 | [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md) 이유 |
| 그 뒤 | 같은 Haiku를 프롬프트 판단 순서와 "찾기면 Spec 에이전트" 코드 규칙을 더해 다시 채택(#47 ~ #50, ADR 0017). v3 4세트 50/50이나 이 세트는 고친 문항을 담아 독립 확인이 아니다 | [ADR 0017](../adr/0017-supervisor를-haiku로-바꾸고-찾기-질문은-코드가-판정-에이전트로-맞춘다.md) 결과 |

교훈으로 모델만 바꾸면 비용은 줄어도 거절 경계가 깨졌고, 경계를 코드가 지키게 한 뒤에야 같은 모델이 통과했다. 이 해석은 위 ADR의 서술을 요약한 것이다.

## 7. 채택하지 않은 실험

| 실험 | 결과 | 근거 |
|---|---|---|
| Supervisor 재계획 끄기(`SUPERVISOR_REPLAN` off, 9문항) | 9/9 유지, 평균 8.32 → 9.48초로 느려져 폐기 | [speed-p95-levers-2026-11-11.md](../experiments/speed-p95-levers-2026-11-11.md) 3절 |
| 검색 방식을 bm25만으로(`RETRIEVE_METHOD`, 9문항) | 8/9 유지, 평균 10.89 → 8.24초, 폐기(기본 hybrid 유지) | 같은 문서 |
| 문서 후보 수 3(`FIND_N_DOCS=3`, 7문항) | 7/7 유지, p95 15.3 → 10.9초, 보류(5 유지) | 같은 문서 |
| RAG partial 재검색 끄기(`DOCS_RETRY_PARTIAL`, 6문항) | 6/6 유지, p95 11.1 → 10.1초, 기본 유지(끄기 폐기) | 같은 문서 |
| 임베딩 후보 확장 평가기 | 구현 없음(조사만) | [embedding-candidate-investigation.md](../research/embedding-candidate-investigation.md) |

폐기한 레버는 코드 기본값을 바꾸지 않고 실험용 환경변수로만 남았다(같은 문서 3.1절).

## 8. 판정자와 채점 도구의 한계 (2026-11-13 추가)

| 한계 | 내용 | 근거 |
|---|---|---|
| 판정자가 팀원뿐 | v3 판정자는 심태현 · 하정운이고 외부 검토자는 없다. 외부 검토자 1명의 검토는 미실시 | [v3_judging_record.md](../../evals/drafts/reviews/v3_judging_record.md), [evaluation-prep.md](../reference/evaluation-prep.md) |
| 판정 기록이 사후 작성 | v3 판정 당시 기록(노션, 시트, 메시지)이 없다. 문항별 수정 이력과 초안-최종 차이를 되살릴 수 없다 | [v3_judging_record.md](../../evals/drafts/reviews/v3_judging_record.md) 머리말, 남은 한계 |
| 비교 대상이 정답 초안과 같은 도구 | Codex가 정답 초안(하정운 검수, 1차 심태현·최종 하정운 판정)과 비교 대상 양쪽에 쓰여 Codex 점수에 유리할 수 있다 | [TALLY.md](../../evals/results/graph/2026-11-12-codex-v3-50/TALLY.md) 5절 |
| Codex 집계는 규칙 기반 | 결론 방향과 핵심 값까지만 보고 쪽 인용은 보지 않는다. 사람 판정 필요 5건은 대기 | [TALLY.md](../../evals/results/graph/2026-11-12-codex-v3-50/TALLY.md) 1~3절 |
| 청크-원본 대조 검사기가 놓치는 오류 | 숫자 끝자리를 바꾼 가짜 청크 110개 중 쪽 수준 91개(83%)만 잡았다. 같은 쪽 다른 행 값으로 바뀐 오류는 배제하지 못한다 | [chunk_source_check/README.md](../../evals/results/d10/chunk_source_check/README.md) "검사기의 한계" |

## 9. 남은 일

D12 마감(11/17)이 이 글에 요구하는 항목 중 아직 없는 것이다.

| 항목 | 현재 | 이유 |
|---|---|---|
| 막지 못한 것(인젝션) | 5절 표와 EVAL_REPORT 6장 참조만 있고 이 글에 사례를 따로 쓰지 않았다 | 저장소 근거는 있으나(EVAL_REPORT 6장 "믿지 않기로 한 것", 11장 3행) 이번에 대조하지 않았다 |
| 점수 판정에 쓴 LLM 판정자(Luna)의 한계 | 이 글에 없음 | 저장소에서 Luna의 판정 오류를 측정한 기록을 찾지 못했다 |
