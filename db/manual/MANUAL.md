# db/manual

## 역할
- 이 폴더: Compose 초기화가 자동 실행하지 않는 SQL을 둔다. Postgres 이미지는 `db/` 바로 아래 파일만 실행하고 하위 폴더는 건너뛴다([DB.md](../DB.md) "SQL이 실행되는 방식").
- 넣는 것: 적용하지 않는 마이그레이션 초안 이력, 복제 DB에서 손으로 실행하는 전환 SQL.
- 넣지 않는 것: 새 볼륨에서 자동 실행할 초기화 SQL(`db/`에 세 자리 번호로).
- `db/`에 `001`과 `004`가 없는 것은 의도다(`001`은 비워 두고, `004`는 이 폴더의 초안).
- 담당: 서비스·운영 (RAG 저장 형식 SQL은 검색·데이터)

## 파일

| 파일 | 실행 | 설명 |
|---|---|---|
| `MANUAL.md` | | 이 문서 |
| `email_signup_cutover.sql` | 사람이 한 번 실행 | `029`와 새 코드를 검증한 뒤 적용하는 고정 시각 CHECK. 기존 계정을 보존하고 구버전 공개 가입 API의 인증 없는 신규 계정을 차단. 재실행해도 기준 시각 유지. 이전 리비전으로 되돌려도 이 제약은 유지 |
| `004_create_business_tables.sql.draft` | 실행하지 않음 | 업무 테이블 11개의 옛 초안(Migration 1 초안). `db/legacy/018_projects.sql` · `019_conversations.sql` · `020_approvals_quotes.sql`이 업무 표를 만들어 대체했고, 초안의 `circuits`가 `018`과 충돌하므로 적용하지 않음(이력) |
| `halfvec.sql.manual` | 기본 경로 아님 | `008_multi_dim_embeddings.sql` 도입 전 복제 DB에서 쓰던 `halfvec(1536)` 전환 · HNSW 제거 이력. 새 DB의 자동 초기화는 `008`의 차원 없는 `halfvec`을 사용 |
