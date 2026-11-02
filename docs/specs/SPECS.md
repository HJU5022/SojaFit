# specs

## 역할
- 이 폴더: 루트 `SPEC.md`에 없는 기능이 생길 때, 그 기능을 에이전트에게 시키기 전에 쓰는 작업서를 둡니다.
- 넣는 것: `<english-kebab>.md` 작업서.
- 넣지 않는 것: 기능별 수용 기준(SPEC.md 한 곳에 둡니다), 결정 기록(`docs/adr/`).
- 담당: 그 기능을 구현하는 담당

## 파일
- `_example.md` — 강사 스캐폴드의 작업서 예시. 형식 예시로 둡니다(AGENTS.md가 가리킴)
- `embedding-model-baseline.md` — 임베딩 모델 4종의 예비 기준선 작업서
- `evaluation-draft-30.md` — 난이도별 평가 문항 30건 검수 초안의 범위·형식·확인 기준
- `evaluation-draft-52.md` — 정보 부족 분류 기준·52건 확장 이력과 현재 50건(25/25) 구성·예비 이관
- `corpus-storage-budget.md` — 원본 코퍼스 유지·축소 도구 적용 보류·halfvec 저장/float32 검색·HNSW 제거와 실측 경계
- `rag-pipeline.md` — 데이터시트 수집·파싱·청킹·적재와 하이브리드 검색의 작업서
