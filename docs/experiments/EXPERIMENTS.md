# experiments

## 역할
- 이 폴더: 실험·평가 작업서를 둡니다. 무엇을 어떤 조건으로 잴지 정한 계약입니다.
- 넣는 것: `<english-kebab>.md` 작업서. 기능 작업서와 같은 다섯 섹션(Why, Goal, What, How, AC)으로 측정 대상, 조건, 지표, 성공 기준, Out of Scope를 적습니다. 문서 첫머리에 구현·원시 결과가 `main`에 있는지 상태 줄로 적습니다.
- 넣지 않는 것: 기능 작업서(`../specs/`), 조사·실측 기록(`../research/`), 결정(`../adr/`), 결과 기대 수치(`../../evals/preregister.md`), 원시 결과(`../../evals/results/`, `../../scripts/results/`).
- 담당: 그 실험의 담당

## 파일
- `embedding-model-baseline.md` — 임베딩 모델 4종의 예비 기준선(30청크·18질의 프록시 표본)
- `embedding-candidate-runner.md` — 임베딩 후보 확장 평가기 설계. 상태: 설계 계약만 있고 구현·테스트·2026-11-02 원시 결과는 `main`에 없음
- `embedding-voyage-candidates.md` — Voyage 4 Nano·Voyage 4 후보 추가 계약. 상태: 설계 계약만 있고 구현·테스트·원시 JSON은 `main`에 없음
- `corpus-storage-budget.md` — 원본 코퍼스 유지와 halfvec 저장·HNSW 제거 검증 작업서
- `evaluation-draft-30.md` — 난이도별 평가 문항 30건 검수 초안의 범위·형식·확인 기준
- `evaluation-draft-52.md` — 정보 부족 분류 기준과 현재 50건 초안 작업서(파일명의 52는 당시 이력)
- `answer-refusal-scorer.md` — 답변·거절 5지표 규칙 기반 채점기 설계와 수용 기준. 상태: 구현(`evals/runners/score_answer.py`)과 회귀 테스트(`tests/evals/test_score_answer.py`) 반영
- `supervisor-model-comparison.md` — 수퍼바이저 후보 5종의 70문항 1회 비교 방법과 선정 결론. 실험상 최종 선정은 `openai/gpt-6-luna`, 서비스 적용은 조장 소유 정본 갱신 뒤 수행
