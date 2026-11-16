# 평가 준비 점검표

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(기존 문서에 없는 평가 축과 준비 항목만 보충). 게이트의 정본은 [GATES.md](../GATES.md), 평가 방식과 결과의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md), 평가셋 동결은 [dataset-guide.md](../../evals/guides/dataset-guide.md)
- 관련 문서: [REFERENCE.md](REFERENCE.md), [market-user-journey.md](../research/market-user-journey.md)

새 팀 규칙이나 수치 합격선을 만들지 않는다. 공식 정확도·Recall·응답 시간 합격 수치는 공개되지 않았다. 팀 목표와 지표 분모·오류 처리 기준은 기능 정본과 평가 보고서에 둔다.

## 1. 배점

| 축 | 배점 |
|---|---:|
| 문제와 시장 근거 | 15 |
| RAG 품질 | 25 |
| 에이전트 설계와 신뢰성 | 25 |
| 배포와 운영 | 20 |
| 증거 패키지와 발표 | 15 |

## 2. 추가 근거 항목

| 항목 | 상태 | 근거 | 남은 일 |
|---|---|---|---|
| 채용 역할·후보 그룹 분석 | 충족 | 반복 업무와 요구 역량 표: [market-user-journey.md 1-2절](../research/market-user-journey.md)(50개 역할·후보 그룹, 2026-11-12 자료). 선정 50건은 2026-11-12 사용자가 수동 검증하고 모두 이상 없다고 확인했다. 현재 평가에는 이 50건을 사용한다(이전 문서 `evaluation-prep.md:17`의 서술). 원문 모음: [sojafit-domain-jobs-2026-11-12.md](../research/sojafit-domain-jobs-2026-11-12.md)(총 72개 역할·후보 그룹, 확인 기준 2026-11-12) | 과거 주제서의 10-29 237건 집계: 개별 행 `docs/research/evidence/job-postings/merged.json`(237행 [실측]), 집계 [job-postings-summary.md](../research/evidence/job-postings-summary.md)([EVIDENCE.md](../research/evidence/EVIDENCE.md) 14~15행). [TOPIC.md](../TOPIC.md) 7행은 당시 제출 이력으로 보존한다고 적는다 |
| 사용자·지불 주체의 사실과 가설 구분 | 충족 | 확인 사실 5건(2-1절), 미검증 가설 4건(2-2절), 페르소나 2종(3-1절), 6단계 고객 여정 맵(4절), 범용 챗봇과 동일 질문 5개 비교 설계(5절), 비교 결과는 [EVAL_REPORT.md](../../EVAL_REPORT.md) 10장 | |
| 외부 검토자 1명의 서비스·근거 검토 | 미충족 | 검토 시나리오와 기록 양식만 [market-user-journey.md 6절](../research/market-user-journey.md)에 있고 기록 칸이 비어 있다 | D10 전에 실시하고 피드백·반영 여부를 기록 |
| 임베딩 시간·비용 | 충족 | 코퍼스 문서 1,360건의 서로 다른 본문 45,898개를 `text-embedding-3-small`로 5,391,648토큰, 12.6분에 임베딩([jeongun.md:747](../worklog/jeongun.md), 2026-11-01). 같은 본문·토큰 수의 2026-11-02 재실행은 773.6초([grid_2026-11-02.json](../../evals/results/embedding/grid_2026-11-02.json) `meta.embed_logs.te3s`). 서비스의 현재 임베딩은 `voyage-4-large`([SPEC.md](../../SPEC.md) 6절) | 현재 임베딩의 시간·비용은 이 표에 없다 |
| 검색·생성·승인 대기의 컨텍스트 경계, 근거 부족 시 재검색·종료 조건, 인용의 실제 문서 존재 검증 | 코드·문서 충족, 발표 설명 미실시 | 재검색 상한 2회: `backend/multi_agent/contracts.py:19` `MAX_SEARCHES`. 서브에이전트는 메모장 전체가 아니라 지시서와 필요한 입력만 받는다: `backend/multi_agent/MULTI_AGENT.md` "구조". 통과 청크 밖 번호 인용(`fake_citations`)과 무인용 문장(`uncited_sentences`): `backend/graph/nodes.py:460`. 정답 근거 일치 채점: `evals/runners/score_answer.py`. 승인 대기 interrupt: [SPEC.md](../../SPEC.md) 2절 | 발표에서 설명 |
| 전원 발표 파트와 현장 입력 연습(정상·경계·방어 3종) | 미충족 | | 발표 자료와 리허설 2회([deliverables/DELIVERABLES.md](../deliverables/DELIVERABLES.md) "남은 일") |

## 3. 가산 선택

필수 게이트가 모두 충족된 경우만 적용하며 합계 적용 상한은 +10점이다. 선택 여부와 실제 결과를 기록하고 필수 구현을 가산으로 중복 계산하지 않는다.

| 항목 | 배점 | 별도로 보여야 할 것 |
|---|---:|---|
| 자동화 | +5 | 증분 추가·갱신, 완전 목록일 때만 삭제, 중복 실행 방지, 정시 실행 기록·실패 알림 |
| 파인튜닝 | +5 | 도메인 학습 데이터·학습 결과, 동일 평가셋의 베이스 비교·실제 출력 |
| GraphRAG | +3 | 벡터 검색이 지는 질문 유형, 그래프 적용 전후 비교 |
| MCP + Skill | +3 | 3차 RAG의 MCP 실제 호출과 도메인 Skill 실제 사용, 같은 평가셋의 Skill 유무 비교 |

기존 2차 MCP·Skill을 그대로 가져온 것만으로는 신규 가산 근거가 되지 않는다.

## 4. 한계

- 배점과 가산 값은 과제 가이드 기준이다. 저장소 안에서는 `docs/research/market-user-journey.md:6`이 1축 15점을 인용할 뿐이며 나머지는 대조하지 못했다.
- 가산 항목 4개 중 어느 것을 선택했는지, 선택 결과는 이 저장소 문서에 기록돼 있지 않다.
- 237건, 50개 분석, 72개 모음의 관계는 각 문서가 적은 값만 위에 옮겼고 이 문서는 해석하지 않는다.
- "선정 50건 수동 검증" 문장은 사람의 확인을 서술한 것이며 저장소에 검증 기록 파일은 없다.
