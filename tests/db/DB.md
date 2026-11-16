# db

## 역할
- 이 폴더: DB SQL·문서·스키마 도구 시험. 일회용 PostgreSQL에 SQL을 적용한 결과로 확인한다.
- 넣는 것: `scripts/db/gen_schema_docs.py` 시험, HTTP를 거치지 않는 `db/*.sql` 단독 시험(`test_public_grants.py`).
- 넣지 않는 것: 저장소·API의 DB 시험(`tests/projects/`, `tests/conversations/`, `tests/api/`), 코퍼스 검색 시험(`tests/rag/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/db`. `TEST_AUTH_DATABASE_URL`로 지정한 격리 시험 DB에서만 실행하고(시험이 새 DB를 만들었다 지운다) URL이 없으면 건너뛴다. 운영·공유 DB URL을 설정하지 않는다.

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `DB.md` | 이 문서 |
| `test_public_grants.py` | `db/026_revoke_public_grants_and_rls.sql`을 격리 PostgreSQL에서: 공개 역할 권한 회수, 재실행 동일, 소유자는 RLS 뒤에도 읽기·쓰기, anon은 코퍼스 표를 못 읽음, LangGraph 체크포인트·Store 표 동작 |
| `test_schema_docs.py` | `scripts/db/gen_schema_docs.py`: 서비스 표·제약·ERD 선이 DB와 같은지, `--check`가 어긋남(칸 기본값 변경)을 잡는지, 설명 없는 새 칸에서 멈추는지, 커밋된 `db/schema` 문서가 자동 생성 표시를 달고 DB와 글자까지 같은지 |
