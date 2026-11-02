# DB ERD

## 기본 규칙

- 표를 만들거나 바꾸는 SQL PR에서 이 문서도 같이 고칩니다.
- 열의 정본은 SQL입니다. 여기에는 표마다 하는 일 한 줄과 만드는 곳만 적습니다.
- 우리가 만드는 표와 라이브러리가 만드는 표를 나눠 적습니다.

## 그림

표가 정해지면 mermaid `erDiagram`으로 그립니다.

## 우리가 만드는 표

| 표 | 하는 일 | 만드는 SQL |
|---|---|---|
| `source_documents` | 코퍼스 문서(데이터시트)의 출처·개정판·해시·파서 | `002_rag_corpus.sql` |
| `document_chunks` | 검색 카드의 본문·쪽·표 이름·행 | `002_rag_corpus.sql` |
| `chunk_embeddings` | 기본 `vector(1536)`과 HNSW; 선택적으로 복제 DB에서 `halfvec(1536)` 전환 시험. 수동 전환 뒤 HNSW 없음 | `002_rag_corpus.sql`, 수동 `halfvec.sql.manual` |
| `users` | 로그인 사용자와 관리자·일반 사용자 역할 | `003_auth.sql`, `006_user_roles.sql` |
| `auth_sessions` | 사용자 세션 해시와 만료 시각 | `003_auth.sql` |
| `auth_login_attempts` | 로그인 시도 제한 | `003_auth.sql`, `005_auth_attempt_window.sql` |
| (정할 것) | 승인된 견적서 등 업무 표 | `004_create_business_tables.sql.draft`(Migration 1 초안) 검토 뒤 |

문서·청크 표는 코퍼스 SQL, 사용자 표는 인증 SQL이 생성합니다. Migration 1 초안(`004_create_business_tables.sql.draft`)은 이 표들을 참조합니다.

## 라이브러리가 만드는 표

`langgraph-checkpoint-postgres` 3.2.0의 `setup()`이 만듭니다. 우리 SQL에서 만들지 않습니다.

| 표 | 만드는 곳 | 하는 일 |
|---|---|---|
| `checkpoints` | `PostgresSaver` | thread별 그래프 상태(체크포인트) |
| `checkpoint_blobs` | `PostgresSaver` | 체크포인트의 채널 값 |
| `checkpoint_writes` | `PostgresSaver` | 재개할 때 쓰는 노드의 중간 쓰기 |
| `checkpoint_migrations` | `PostgresSaver` | 체크포인트 스키마 버전 |
| `store` | `PostgresStore` | 사용자별 장기 기억. namespace는 `("memories", user_id)`(`backend/memory.py`) |
| `store_vectors` | `PostgresStore` | 기억의 임베딩(인덱스를 설정할 때) |
| `store_migrations`, `vector_migrations` | `PostgresStore` | Store 스키마 버전 |
