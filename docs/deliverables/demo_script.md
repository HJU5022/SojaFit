# 시연 영상 스크립트

- 상태: 계획
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(촬영 순서). 영상 파일은 없다
- 관련 문서: [DELIVERABLES.md](DELIVERABLES.md), [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md), [GATES.md](../GATES.md)(G7), [EVAL_REPORT.md](../../EVAL_REPORT.md) 6장

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 목표 길이 | 3분 이내 | 가이드 G7 |
| 구성 | 정상 경로 1개 약 110초 + 실패 경로 1개 약 50초 | 3절, 4절 |
| 근거 재료 | 배포 스모크 28단계 [smoke_..._232814.json](../../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232814.json), 키 없는 데모 질문 [DEMO.md](../../scripts/demo/DEMO.md), 거절·인젝션 EVAL_REPORT 6장 | |
| 촬영 | 안 함 | |

## 2. 촬영 환경 (둘 중 하나)

| 경로 | 주소 | 계정 | 비고 |
|---|---|---|---|
| A 배포 | `README.md`의 Cloud Run `/login` | 평가용·데모 계정(비밀번호는 영상에 넣지 않음) | `DEMO_MODE=0`이면 Google 또는 비밀번호 계정. 데모 회로 버튼이 없다 |
| B 로컬 키 없음 | `docker compose up --build` 뒤 `localhost:8000` | "데모 사용자 A" 버튼 | 기록 재생. LLM 키 불필요(`docker-compose.yml`의 `DEMO_MODE` 기본 1) |

권장: B로 정상·실패를 찍고, 맨 앞 5초에 A의 `/health`와 로그인 화면을 한 컷 보인다.

## 3. 정상 경로 장면

보여 줄 것: 로그인 → 회로 → 판정 질문 → 조건 질문 정지 → 재개 → 승인 → 견적.

| 장면 | 초 | 화면 | 말·동작 | 근거 |
|---:|---|---|---|---|
| 1 | 0–8 | `/health` 또는 로그인 | 배포(또는 로컬)에서 로그인한다 | README 맨 위 표 |
| 2 | 8–25 | 작업대·프로젝트 | ATtiny85 Time Switch, 대상 D1. 로컬이면 데모 회로로 시작 | `scripts/demo/DEMO.md` |
| 3 | 25–45 | 질문 전송 | v3-01: D1을 1N4007G로 바꿔도 되는지. 조건 질문(`requires_input`)에서 멈춤을 보인다 | `evals/dataset_v3.jsonl` v3-01 |
| 4 | 45–70 | 재개 | 허용 전압강하 등 준비한 답을 넣고 재개. 판정표와 쪽·표·행 인용 | `DEMO.md` |
| 5 | 70–95 | 승인·견적 | 후보 승인 201, 같은 승인 다시 409, 견적 저장 | 스모크 28단계 |
| 6 | 95–110 | (선택) 다른 창 B | B로 들어가면 A의 프로젝트·대화가 보이지 않는다(격리). 시간이 없으면 생략 | G4 |

## 4. 실패 경로 장면 (하나만 선택)

보여 줄 것: 거절이 정상 동작임을 한 컷.

| 선택 | 입력 | 기대 | 근거 |
|---|---|---|---|
| 1 범위 밖 | v3-30(릴레이·비다이오드 질문) | `refused`, 지어낸 대체품 없음 | `evals/dataset_v3.jsonl` v3-30(`out_of_domain`) |
| 2 없는 품번 | v3-36(LL4149) | 코퍼스에 없음 → 거절 | v3-36(`unknown_entity`), `DEMO.md` |
| 3 판정 충돌 방어 | C2(코드 불충족 + 거짓 적합 주장) | 최종 답에 사용 권고 0 | [claim_consistency_d9_recheck_2026-11-12.json](../../evals/results/threads/claim_consistency_d9_recheck_2026-11-12.json), `EVAL_REPORT.md:542`(원시 `semantic_summary`는 `pending_manual_review`) |

권장: 선택 1. 촬영이 가장 짧고 스모크·데모에 이미 있다.

## 5. 영상에 넣지 않는 것

- 비밀번호, 쿠키, API 키, 평가용 계정 문자열
- 실패를 버그로 포장하는 멘트(거절·정지는 게이트 시나리오)
- 새 기능 설명, 긴 슬라이드 인트로(제품 한 줄만)

## 6. 남은 일

| 항목 | 내용 |
|---|---|
| 촬영 | 영상 파일 촬영(D11 11/16). 원본과 동결 시점 커밋 SHA, 배포 리비전 번호를 함께 남긴다 |
| 영상 링크 | `README.md` 표 "시연 영상" 칸에 링크(저장소 안 또는 외부 URL) |
| 이 문서 | 촬영 뒤 상태를 `현행`으로 바꾸고 촬영일을 적는다 |
| 게이트 | `../GATES.md` G7 상태 갱신 |
