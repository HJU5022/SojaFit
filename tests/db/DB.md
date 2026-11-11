# db

## 역할
- 넣는 것: DB 문서 · 스키마 도구 시험. 일회용 PostgreSQL에 서비스 스키마를 적용한 결과로 확인한다.
- 넣지 않는 것: 저장소 · API의 DB 시험(`tests/projects/`, `tests/conversations/`, `tests/api/`), 코퍼스 검색 시험(`tests/rag/`).
- 담당: 서비스·운영

## 파일
- `DB.md` — 이 문서
- `test_initdb_files.py` — Compose가 적용하는 최상위 SQL 목록 회귀 검사
- `test_schema_docs.py` — `scripts/db/gen_schema_docs.py`: 서비스 표 21개 · 제약 · ERD 선이 DB와 같은지, `--check`가 어긋남(칸 기본값 변경)을 잡는지, 설명 없는 새 칸에서 멈추는지, 자동 생성 표시가 있는 커밋된 `db/schema` 문서가 DB와 글자까지 같은지

`uv run pytest -q tests/db`. `TEST_AUTH_DATABASE_URL`로 지정한 격리 시험 DB에서만 실행하고(시험이 새 DB를 만들었다 지운다), URL이 없으면 건너뛴다. 운영·공유 DB URL을 설정하지 않는다.
