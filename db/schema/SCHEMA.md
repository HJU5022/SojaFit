# schema

## 역할
- 이 폴더: DB 표 설계를 설명하는 문서를 둡니다. SQL은 두지 않습니다.
- 넣는 것: 표 목록·관계 문서(`erd.md`), 업무 표 설계 초안(`table-definition.md`). SQL로 표를 바꾸면 같은 PR에서 고칩니다.
- 넣지 않는 것: 자동 실행 초기화 SQL(`db/`, Compose가 최상위 `.sql`만 실행), 수동 SQL(`db/manual/`).
- 담당: 서비스·운영 (RAG 표는 검색·데이터)

## 파일
- `SCHEMA.md` — 이 문서
- `erd.md` — 표마다 하는 일 한 줄과 만든 곳
- `table-definition.md` — 업무 표(회로·판정·견적)의 컬럼·관계·제약 설계 초안과 검토 항목. 열의 정본은 SQL입니다
