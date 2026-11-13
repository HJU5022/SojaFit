# experiments

## 역할
- 이 폴더: 사전 등록한 실험의 계획과 결과를 둡니다(질문, 조건, 결과, 결정, 한계). 문서마다 첫머리 헤더(상태, 기준일, 기준 커밋, 정본 여부, 관련 문서)가 상태의 정본입니다.
- 넣는 것: `<english-kebab>.md` 실험 기록(사전 등록 계약, 사후등록, 측정 계획, 측정 결과, 평가셋 초안 작업서, 채점기 계약).
- 넣지 않는 것: 기능 작업서(`../specs/`), 선택지 비교·조사 보고(`../research/`), 결정(`../adr/`), 결과 기대 수치(`../../evals/guides/preregister.md`), 원시 결과(`../../evals/results/`, `../../scripts/results/`).
- 담당: 그 실험의 담당

## 파일

| 파일 | 유형 | 한 줄 설명 |
|---|---|---|
| `answer-refusal-scorer.md` | 실험 기록 | 답변·거절 5지표 규칙 기반 채점기의 분류 규칙과 수용 기준 |
| `c2-defense-recheck.md` | 실험 기록 | C2 방어 수정 전후 정상군·C1·C2 재검증 조건과 결과 |
| `corpus-storage-budget.md` | 실험 기록 | 원본 코퍼스 유지와 halfvec 저장·HNSW 제거 검증 |
| `d8-stage-remeasure-plan.md` | 실험 기록 | D8 단계별 응답 시간·비용 측정의 원본 목록과 재현 명령 |
| `embedding-model-baseline.md` | 실험 기록 | 임베딩 모델 4종의 프록시 표본 예비 기준선 |
| `evaluation-draft-30.md` | 실험 기록 | 난이도별 평가 문항 30건 검수 초안의 범위와 형식 |
| `evaluation-draft-52.md` | 실험 기록 | 정보 부족 분류 기준과 본편 50건·예비 2건 구성 |
| `injection-baseline-plan.md` | 실험 기록 | 인젝션 기준선: T1~T7 짝 측정 계약과 실행 현황 |
| `injection-baseline-preflight.md` | 실험 기록 | 인젝션 기준선 준비 관문과 무료 검증 |
| `speed-p95-levers-2026-11-11.md` | 실험 기록 | D8 p95 레버 A/B와 채택·폐기 |
| `supervisor-model-comparison.md` | 실험 기록 | 수퍼바이저 후보 5종 70문항 1차 비교의 사전 등록 계약 |
| `supervisor-model-comparison-postregistration.md` | 실험 기록 | 1차 비교의 실제 조건, 결과, 사후등록 |
| `supervisor-stage2-six-models.md` | 실험 기록 | 6종 70문항 2차 공동 평가 사전 등록(#32) |
| `supervisor-stage3-six-models.md` | 실험 기록 | 6종 70문항 3차 공동 평가 사전 등록(#33) |
| `thread-memory-operations.md` | 실험 기록 | thread·승인 기억 운영 검증 합격 기준과 절차 |
