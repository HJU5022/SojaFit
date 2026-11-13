# schema

## 역할
- 이 폴더: DB 표 설계를 설명하는 문서를 둡니다. SQL은 두지 않습니다.
- 넣는 것: 표 목록·관계 문서(`erd.md`), 서비스 표 정의서(`table-definition.md`). SQL로 표를 바꾸면 같은 PR에서 고칩니다.
- 넣지 않는 것: 자동 실행 초기화 SQL(`db/`, Compose가 최상위 `.sql`만 실행), 수동 SQL(`db/manual/`).
- 담당: 서비스·운영 (RAG 표는 검색·데이터)

## 파일

| 파일 | 유형 | 설명 |
|---|---|---|
| `SCHEMA.md` | 폴더 설명 | 이 문서 |
| `erd.md` | 생성 문서 | 서비스 표의 ERD(mermaid)와 표마다 하는 일 |
| `table-definition.md` | 생성 문서 | 서비스 표의 칸 · 제약 · 인덱스 · 트리거 정의서 |

- 두 생성 문서는 `uv run python scripts/db/gen_schema_docs.py`가 새 기준선 DB의 `pg_catalog`에서 만든다. 직접 고치지 않고, SQL을 바꾸면 다시 생성한다(`tests/db/test_schema_docs.py`가 SQL과의 어긋남을 실패로 잡는다).

## 보안 · 권한 (`db/026_revoke_public_grants_and_rls.sql` · `db/020_service_baseline.sql`)
- 정책: 공개 역할(`anon` · `authenticated`)은 모든 앱 표 · 시퀀스 · 우리 함수에 권한 0, 앱 표(`public` · `sojafit_agent`)는 모두 RLS ON(정책 없음 = 기본 거부). 두 겹이다.
- 이유: 서버는 DB 소유자 연결(운영 `postgres`, compose `app`)로만 접속하고 Supabase Data API · 공개 역할을 쓰지 않는다. 소유자 · 슈퍼유저는 RLS를 우회하므로 서버 동작은 그대로다(`FORCE`는 쓰지 않는다).
- 기본 권한: Supabase 기본값은 `public`에 새로 만드는 표 · 시퀀스 · 함수가 공개 역할 권한을 자동으로 받는다. 026이 이 연결 역할의 기본 권한에서 공개 역할을 뺀다. 새 표를 만드는 SQL은 따로 `REVOKE`를 쓰지 않아도 되지만, 표를 만들 때 RLS는 직접 켠다(`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
- LangGraph가 만드는 표(`sojafit_agent.checkpoint*` · `store*` · `*_migrations`)도 같은 정책이다. BYPASSRLS 없는 일반 소유자 역할로 RLS ON 뒤 `setup` · put · get이 되는 것을 시험으로 확인했다(`tests/api/test_public_grants.py`). 서버가 켜질 때마다 `setup`이 다시 불려도 RLS는 유지된다.
- 안 건드리는 것: 스키마 USAGE(Supabase 기본값), `service_role`(프로젝트 관리자 키 역할), Supabase가 만든 함수 `rls_auto_enable`.
- 확인: 026 파일 머리의 쿼리 둘이 모두 0행이어야 한다.
