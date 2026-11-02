# specs

## 역할
- 이 폴더: 루트 `SPEC.md`에 없는 기능이 생길 때, 그 기능을 에이전트에게 시키기 전에 쓰는 작업서를 둡니다.
- 넣는 것: `<english-kebab>.md` 작업서.
- 넣지 않는 것: 기능별 수용 기준(SPEC.md 한 곳에 둡니다), 결정 기록(`docs/adr/`).
- 담당: 그 기능을 구현하는 담당

## 파일
- `_example.md` — 강사 스캐폴드의 작업서 예시. 형식 예시로 둡니다(AGENTS.md가 가리킴)
- `embedding-candidate-runner.md` — 기본 실행 후보 9종, Voyage 확장 2종과 조사 전용 2종의 어댑터·라이선스·테스트 설계
- `embedding-voyage-candidates.md` — Voyage 4 Nano·Voyage 4의 1,024차원 입력 계약, 평가 경계와 API 정책 차단 처리
- `embedding-model-baseline.md` — 임베딩 모델 4종의 예비 기준선 작업서
- `evaluation-draft-30.md` — 난이도별 평가 문항 30건 검수 초안의 범위·형식·확인 기준
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색의 작업서
