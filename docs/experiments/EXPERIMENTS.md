# experiments

## 역할
- 이 폴더: 실험·평가 작업서를 둡니다. 무엇을 어떤 조건으로 잴지 정한 계약입니다.
- 넣는 것: `<english-kebab>.md` 작업서. 기능 작업서와 같은 다섯 섹션(Why, Goal, What, How, AC)으로 측정 대상, 조건, 지표, 성공 기준, Out of Scope를 적습니다. 문서 첫머리에 구현·원시 결과가 `main`에 있는지 상태 줄로 적습니다.
- 넣지 않는 것: 기능 작업서(`../specs/`), 조사·실측 기록(`../research/`), 결정(`../adr/`), 결과 기대 수치(`../../evals/guides/preregister.md`), 원시 결과(`../../evals/results/`, `../../scripts/results/`).
- 담당: 그 실험의 담당

## 파일
- `speed-p95-levers-2026-11-11.md` — D8 p95 레버 A/B. `GATE_WARMUP`(측정용) · `FIND_N_DOCS=5` 채택, 나머지 기본 유지. v3 50×1 기준선 50/50 · p95 9.2초. 상태: 측정 완료
- `injection-baseline-preflight.md` — STH/main dbe7177 기준 네 준비 관문 구현·30개 준비 검사·실제 격리 합성 적재·386개 관련 회귀. 유료 실행 없음
- `d8-stage-remeasure-plan.md` — D8 단계별 응답 시간 · 비용 재측정 준비. 8장 숫자의 원본 목록 · 재현 명령 · 서비스와 평가 실행기별 단계 시간 경로 · 승인 대기 계산 SQL 초안 · 후보 설계별 비용 견적 · 필요한 코드 변경. 모델 호출 없음, 측정은 미실행
- `injection-baseline-plan.md` — T1~T7 고정 짝·사람 채점·110개 job와 준비10턴·공식 단가·예상/예약 예산·유료 승인 전제 T1/T3 독립4작업노출탐색계약·별도$2승인/예산포함.
- `thread-memory-operations.md` — thread·기억 품질/병렬/복원/비용 검증 명령·합격 기준·실행 경계
- `c2-defense-recheck.md` — 조장 수정 후 고정 정상군/C1/C2의 입력·모델·무료 호환성·유료 실행 명령·전후 의미 비교·중단/예산·증거 보관 절차. 수정 후 무료 재생(4 passed)까지 반영, 실제 모델 재측정은 미실행
- `embedding-model-baseline.md` — 임베딩 모델 4종의 예비 기준선(30청크·18질의 프록시 표본)
- `embedding-candidate-runner.md` — 임베딩 후보 확장 평가기 설계. 상태: 설계 계약만 있고 구현·테스트·2026-11-02 원시 결과는 `main`에 없음
- `embedding-voyage-candidates.md` — Voyage 4 Nano·Voyage 4 후보 추가 계약. 상태: 설계 계약만 있고 구현·테스트·원시 JSON은 `main`에 없음
- `corpus-storage-budget.md` — 원본 코퍼스 유지와 halfvec 저장·HNSW 제거 검증 작업서
- `evaluation-draft-30.md` — 난이도별 평가 문항 30건 검수 초안의 범위·형식·확인 기준
- `evaluation-draft-52.md` — 정보 부족 분류 기준과 현재 50건 초안 작업서(파일명의 52는 당시 이력)
- `answer-refusal-scorer.md` — 답변·거절 5지표 규칙 기반 채점기 설계와 수용 기준. 상태: 구현(`evals/runners/score_answer.py`)과 회귀 테스트(`tests/evals/test_score_answer.py`) 반영
- `supervisor-model-comparison.md` — 수퍼바이저 후보 5종의 70문항 1회 비교 방법·경량 집계·선정 규칙(결과 확인 전에 고정, 선정 결론은 없음)
- `supervisor-model-comparison-postregistration.md` — 완료된 수퍼바이저 후보 5종 비교의 실제 조건·실행 중 변경·채점 범위·선정 기준·한계를 기록한 사후등록. 실험상 최종 선정은 `openai/gpt-6-luna`(10절), 서비스 적용은 조장 소유 정본 갱신 뒤 수행
- `supervisor-stage2-six-models.md` — 기존 5종과 Jev의 2차 70문항 공동 평가 계약(#32). 실측은 `../research/supervisor-stage2-results.md`
- `supervisor-stage3-six-models.md` — 같은 6종·동결 70문항의 3차 `run_index=3` 공동 평가 계약(#33). 실측은 `../research/supervisor-stage3-results.md`
