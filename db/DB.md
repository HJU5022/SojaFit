# db

## 역할
- 이 폴더: Compose가 DB 컨테이너를 처음 만들 때 이름순으로 실행하는 초기화 SQL만 바로 아래에 둔다. 하위 폴더의 SQL은 자동 실행되지 않는다.
- 넣는 것: 새 DB 첫 기동용 SQL(확장 · 코퍼스 · 서비스 표 기준선 · 공개 권한 회수 · 인증). 운영 DB를 옮기는 SQL은 `migrations/`, 기준선 이전의 옛 증분 SQL(이력)은 `legacy/`, 자동 실행하지 않는 SQL은 `manual/`.
- 넣지 않는 것: 표 설계 문서(`schema/`), 평가용 계정 비밀번호(저장소 밖으로 따로 제출), 원본 문서(`data/corpus/`). 코퍼스 데이터 적재는 SQL이 아니라 `backend/rag/pipeline/ingest.py`가 한다. 데모 계정(A · B, 비밀번호 없음)은 SQL 시드가 아니라 `DEMO_MODE=1`에서 첫 데모 로그인 때 앱이 만든다. 그 밖의 계정은 `/signup` 가입이나 `python -m backend.auth`로 만든다. 실제 비밀번호는 저장소에 두지 않는다.
- 담당: 서비스·운영 (RAG 스키마·스냅샷·인덱스 SQL은 검색·데이터)

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `DB.md` | 폴더 설명 | 이 문서 |
| `000_init.sql` | 초기화 SQL | PostgreSQL 확장(pgvector) 생성 |
| `002_rag_corpus.sql` | 초기화 SQL | 코퍼스 문서·청크·임베딩 표와 인덱스 |
| `008_multi_dim_embeddings.sql` | 초기화 SQL | 임베딩 열을 차원 없는 `halfvec`으로 바꿔 `text-embedding-3-small`(1536)·`voyage-4-large`(1024) 행을 함께 둠. HNSW 인덱스 제거 |
| `009_chunk_embedding_bits.sql` | 초기화 SQL | `voyage-4-large` 임베딩의 1비트 코드 표 `chunk_embedding_bits`(dense 1단계 Hamming 후보용, preregister #27). 인덱스 없음 |
| `012_document_category.sql` | 초기화 SQL | `source_documents`에 문서 분류 열 `category`(NULL 허용, `ingest.py`가 채움) |
| `020_service_baseline.sql` | 초기화 SQL | 서비스 표 기준선: `public` 16표(users · auth_* 5 · projects · circuits · threads · runs · messages · approvals · quotes · approved_cases · app_migrations)와 `sojafit_agent` 5표(threads · messages · analysis_events · analysis_usage · analysis_service_usage), 체크포인트 삭제 트리거, 보관 기간 청소 함수 2개, 모든 서비스 표 RLS ON(정책 0). 코퍼스·LangGraph 표는 포함하지 않음 |
| `026_projects_catalog_demo.sql` | 초기화 SQL | 6개 데모 ID 고정 CHECK를 제거하고 `source_kind`와 `demo_id`의 관계만 DB가 검사. 허용 ID는 `data/circuits/catalog.json`을 읽는 서버가 검증 |
| `026_revoke_public_grants_and_rls.sql` | 초기화 SQL | 공개 역할(`anon` · `authenticated`)의 권한 회수(코퍼스 표 4개 · 시퀀스 · 우리 함수 · public 기본 권한)와 앱 표(`public` · `sojafit_agent`)의 RLS ON. 역할이 없는 DB(compose · CI)는 RLS만 켬. 여러 번 실행해도 같음 |
| `027_google_user_login.sql` | 초기화 SQL | 일반 Google 계정의 NULL 비밀번호 허용, 관리자 비밀번호 필수 |
| `029_email_account_security.sql` | 초기화 SQL | 이메일 인증 시각, 일회용 challenge, 발송 한도 |
| `030_google_onboarding.sql` | 초기화 SQL | 명시적 Google 가입, 재확인 연결, 관리자 승인 대기(`auth_google_pending`) |
| `031_circuit_versions.sql` | 초기화·기존 DB 추가 SQL | 불변 `project_circuit_versions`와 대화별 회로 고정. 기존 회로·대화를 v1으로 backfill(빈 회로 v0), 새 버전·대화 트리거, RLS·공개 권한 회수. 재실행 가능하며 적용 호출자가 트랜잭션을 연다 |
| `032_approval_reselection.sql` | 초기화·기존 DB 추가 SQL | 승인 snapshot/견적을 보존하고 사례 삭제 뒤 새 승인 이력을 허용. message_id UNIQUE를 조회 인덱스로 전환. 활성 승인 1건은 새 QuoteService의 run 행 잠금과 활성 사례 검사로 직렬화 |
| `033_thread_titles.sql` | 초기화·기존 DB 추가 SQL | 대화 이름 칸 `threads.title`(NULL 허용, 공백 제거 1~200자 CHECK `ck_threads_title`)만 더함. NULL이면 화면은 첫 질문으로 만든 이름을 보임. 기존 행은 바꾸지 않고 재실행 가능 |
| `034_admin_audit.sql` | 초기화·기존 DB 추가 SQL | 관리자 작업 이력 표 `admin_audit`(처리한 관리자 FK, 대상 id와 가린 이메일(FK 없음, 탈퇴 처리 뒤에도 남음), 작업 unmask·deactivate·activate·delete, 연 칸, 가림 해제 사유 5~500자). 앱은 INSERT·SELECT, 1년 지난 행은 새 분석 시작 때 지움(SPEC 8.5). RLS ON·공개 역할 권한 회수, 재실행 가능 |
| `035_circuit_schematics.sql` | 초기화·기존 DB 추가 SQL | 업로드한 KiCad 회로도 원문 표 `circuit_schematics`(프로젝트 · 회로 버전 복합 PK, `project_circuit_versions`에 FK CASCADE, 파일 이름 1~255자, 원문 5 MiB 이하). 그림(PNG)은 저장하지 않음. 앱은 업로드 트랜잭션에서 INSERT, 그림 요청 때 소유자 조건으로 SELECT(#52). RLS ON·공개 역할 권한 회수, 재실행 가능 |
| `legacy/` | 하위 폴더 | 기준선 이전의 옛 증분 SQL 이력. [LEGACY.md](legacy/LEGACY.md) |
| `migrations/` | 하위 폴더 | 이미 서비스 표가 있는 운영 DB용 이전·점검·되돌리기 SQL. [MIGRATIONS.md](migrations/MIGRATIONS.md) |
| `manual/` | 하위 폴더 | 자동 실행하지 않는 수동 SQL. [MANUAL.md](manual/MANUAL.md) |
| `schema/` | 하위 폴더 | 실제 스키마에서 생성한 ERD·표 정의서. [SCHEMA.md](schema/SCHEMA.md) |

## SQL이 실행되는 방식

| 분류 | 위치 | 어떻게 실행되나 | 파일 수 |
|---|---|---|---:|
| 자동 | `db/*.sql` (이 폴더 바로 아래) | `docker-compose.yml`의 `db` 서비스가 `./db`를 `/docker-entrypoint-initdb.d`(읽기 전용)로 마운트한다(`docker-compose.yml:66-67`). Postgres 이미지는 데이터 폴더가 비어 있을 때 첫 기동에만 이 폴더 바로 아래의 `.sql`을 파일 이름순으로 실행한다 | 16 |
| 수동(운영 이전) | `db/migrations/` | `psql`로 사람이 단계마다 직접 실행. 새 DB는 쓰지 않는다 | 10 |
| 수동(기타) | `db/manual/` | `.sql`(1)은 사람이 직접 실행, `.draft`·`.manual`(2)은 실행하지 않는 이력 | 3 |
| 이력 | `db/legacy/` | 실행하지 않는다. `scripts/db/verify_chain/verify_chain.sh`와 `migrate_prod_4_rollback.sql`이 읽는다 | 21 |

- 하위 폴더의 SQL은 마운트된 폴더 안에 있어도 이미지가 건너뛴다. 확장자 `.draft`·`.manual`은 실행 대상이 아니다.
- 자동 실행 순서(이름순): `000_init` → `002_rag_corpus` → `008_multi_dim_embeddings` → `009_chunk_embedding_bits` → `012_document_category` → `020_service_baseline` → `026_projects_catalog_demo` → `026_revoke_public_grants_and_rls` → `027_google_user_login` → `029_email_account_security` → `030_google_onboarding` → `031_circuit_versions` → `032_approval_reselection` → `033_thread_titles` → `034_admin_audit` → `035_circuit_schematics`.
- 이 폴더에 없는 번호: `001`, `003`~`007`, `010`, `011`, `013`~`019`, `021`~`025`, `028`. 서비스 표는 기준선이 대체했고(옛 파일은 `legacy/`), `007` 데모 시드는 앱으로 옮겼고, `011` 사양 표는 ADR 0016으로 폐기했고, `004`는 `manual/`의 초안이다.
- 같은 번호를 쓰는 파일(번호 `020`, `026`, `027`, `029`). 번호는 종류가 다른 파일끼리 겹친다. 어느 쪽이 현행인지는 위치로 구분한다.

| 번호 | `db/` 바로 아래(현행, 자동 실행) | `db/legacy/`(이력, 실행 안 함) |
|---|---|---|
| 020 | `020_service_baseline.sql` | `020_approvals_quotes.sql` |
| 026 | `026_projects_catalog_demo.sql`, `026_revoke_public_grants_and_rls.sql` (같은 폴더에 두 개) | 없음 |
| 027 | `027_google_user_login.sql` | `027_service_redesign_p1.sql` |
| 029 | `029_email_account_security.sql` | `029_drop_google_pending.sql` |

## 실행과 주의

- 승인 재선택032는 새 QuoteService 코드를 먼저 반영한 뒤 기존 DB에 `psql -1 -v ON_ERROR_STOP=1 -f db/032_approval_reselection.sql`로 적용한다. 행은 보존되며 재실행 가능하다. 이미 여러 승인 이력을 만든 메시지가 있으면 옛 UNIQUE를 무조건 복원할 수 없다. 기준선의 승인 제약은032 이후 상태를 포함한다.

- 대화 이름033은 칸 하나를 더하는 추가 변경이라 코드보다 먼저 적용해도 된다. 기존 DB에는 `psql -1 -v ON_ERROR_STOP=1 -f db/033_thread_titles.sql`로 적용하고, 되돌릴 때는 `ALTER TABLE threads DROP COLUMN IF EXISTS title;`(고친 이름만 사라진다). 새 코드는 이 칸이 없는 DB에서 대화 목록·상세를 읽지 못하므로 코드 배포 전에 적용한다.

- 관리자 작업 이력034는 새 표 하나를 더하는 추가 변경이다. 새 코드(활성 상태 변경 · 가림 해제 · 탈퇴 처리가 이 표에 쓴다)보다 먼저 기존 DB에 `psql -1 -v ON_ERROR_STOP=1 -f db/034_admin_audit.sql`로 적용한다. 되돌릴 때는 `DROP TABLE IF EXISTS admin_audit; DELETE FROM app_migrations WHERE version='034-admin-audit';`(관리자 작업 이력이 사라진다).

- 업로드 회로도035는 새 표 하나를 더하는 추가 변경이다. 새 코드(프로젝트 응답의 `schematic_file`이 이 표를 읽는다)보다 먼저 기존 DB에 `psql -1 -v ON_ERROR_STOP=1 -f db/035_circuit_schematics.sql`로 적용한다. 되돌릴 때는 `DROP TABLE IF EXISTS circuit_schematics; DELETE FROM app_migrations WHERE version='035-circuit-schematics';`(올린 회로도 원문이 사라지고 원본 회로도 창은 웹 검색으로 돌아간다). 새 코드는 이 표가 없는 DB에서 프로젝트를 읽지 못한다.

- 새 DB의 서비스 표는 증분 파일이 아니라 기준선 한 파일(`020_service_baseline.sql`)이 만든다. 기준선은 옛 체인에 운영 이전 SQL을 적용한 결과와 구조가 같다(`scripts/db/verify_chain/verify_chain.sh`가 차이 0줄을 확인). [결정] 11-11 재설계 M 단계.
- `020_service_baseline.sql` 80행의 주석("`auth_google_pending`은 만들지 않는다")은 `030_google_onboarding.sql` 적용 전의 상태다. 새 DB는 `030`이 `auth_google_pending`을 만든다.
- 기존 DB에는 기준선이나 `legacy/` SQL을 다시 실행하지 않는다. 추가 인증 SQL(`027`·`029`·`030`)과 회로 버전 SQL(`031`)의 적용은 따로 검토한다. `031`만 기존 DB에 추가할 때는 한 트랜잭션(`psql -1 -v ON_ERROR_STOP=1 -f db/031_circuit_versions.sql`)으로 적용한다. 기존 데이터·해시·연결을 삭제하거나 재작성하지 않는다.
- Compose의 `thread-setup`은 DB healthcheck 뒤 `python -m backend.conversations.memory_service --setup`을 실행해 LangGraph 표(PostgresSaver/PostgresStore 내부 표)만 만든다. 서비스 표는 만들지 않고 SQL 파일을 적용하지도 않는다. `vector` 확장이 이미 설치된 DB면 사용자 사실 의미 색인 표(`store_vectors` · `vector_migrations`)도 `sojafit_agent`에 만든다.
- Compose의 `corpus-load`는 같은 DB healthcheck 뒤 `python -m backend.rag.pipeline.ingest data/demo/snapshot/manifest.jsonl data/demo/snapshot/chunks.jsonl /tmp/vectors --chunks-only`(`RAG_VECTOR_TYPE=halfvec`)로 데모 코퍼스 스냅샷을 `source_documents` · `document_chunks`에 넣는다. 임베딩은 넣지 않는다. 스냅샷 규모: [SNAPSHOT.md](../data/demo/snapshot/SNAPSHOT.md).
- 볼륨: 이미 초기화된 DB 볼륨에는 초기화 SQL이 다시 적용되지 않는다. `028` 이전(옛 구조)의 로컬 볼륨은 새 코드와 맞지 않으므로 `docker compose down -v`로 지우고 다시 만든다. `down -v`는 DB 볼륨의 데이터를 지우므로 보존할 데이터가 있는 환경에서는 실행하지 않는다.
- 기존 DB(운영)는 기준선을 쓰지 않고 `migrations/`의 이전 SQL을 순서대로 적용한다(expand → 새 코드 배포 → contract). 각 파일 끝이 이력 표 `public.app_migrations`에 한 줄을 남긴다. 새 DB의 기준선은 `2026-11-service-baseline` 한 줄을 남긴다([결정] D6: 자체 이력 표를 쓰고 Supabase `supabase_migrations`는 건드리지 않음).
- 사양 표(`part_specifications`)는 ADR 0016으로 폐기했다. 이미 만든 로컬 볼륨에는 표가 남으므로 필요하면 따로 지운다.

### 경고

- `migrations/migrate_prod_2b_optional_drop_dead_auth.sql`은 실행하지 않는다. `auth_google_pending`은 `030_google_onboarding.sql`이 만드는 활성 표이고(`backend/auth.py`가 읽고 쓴다), 이 파일을 실행하면 운영 표가 삭제된다. 030을 쓰는 버전에서는 실행 대상이 아니다.

## 기존 DB(운영) 적용 전 점검

1. 대상이 공유·운영 DB인지 확인하고 백업과 복구 경로를 확인한다(`migrations/migrate_prod_1_expand.sql` 머리의 `pg_dump` 명령). 비밀번호·접속 문자열은 기록하지 않는다.
2. 이전 순서와 되돌리기는 [MIGRATIONS.md](migrations/MIGRATIONS.md)를 따른다. 운영·공유 DB에 기준선·초기화 SQL을 자동 적용하거나 볼륨을 삭제하지 않는다.
3. `008` · `009`(임베딩 열 전환, 비트 표)는 용량을 확인한 뒤 `scripts/db/voyage_rollout.py`로 따로 적용한다. 기존 DB에는 자동 적용되지 않는다.

## 백업 복원 (새 DB · 새 Supabase 프로젝트로 옮길 때)

- 순서는 구조 → 데이터 → 제약 · 인덱스다. 새 기준선 DB, 이전 SQL을 적용한 DB, 되돌린 DB의 백업(`pg_dump -Fc`)은 빈 DB에 한 번에 `pg_restore`해도 오류가 없다(`scripts/db/verify_redesign/rd_test7.sh`가 PG16 · 17에서 확인). 명령: `pg_restore -d <새 DB> --no-owner --no-privileges --exit-on-error 파일.dump`.
- 이전 SQL을 적용하기 전의 옛 구조에서 받은 백업은 한 번에 복원하면 `approvals` COPY가 `function quote_snapshot_has_forbidden_key does not exist`로 실패한다(재귀 함수에 `search_path`가 없고 `pg_restore`는 복원 중 `search_path`를 비움). 세 번에 나눠 복원한다:
  1. `pg_restore -d <새 DB> --no-owner --no-privileges --section=pre-data 파일.dump`
  2. `psql <새 DB> -c 'ALTER FUNCTION public.quote_snapshot_has_forbidden_key(jsonb) SET search_path = "$user", public' -c 'ALTER FUNCTION public.conversation_json_matches(jsonb, jsonb) SET search_path = "$user", public'`
  3. `pg_restore ... --section=data 파일.dump`, 이어서 `pg_restore ... --section=post-data 파일.dump`
- 운영에서 `migrate_prod_1_expand.sql`(E0)을 적용한 뒤 받은 백업은 위 2번이 이미 들어 있어 한 번에 복원된다. 새 프로젝트에는 `vector` 확장이 필요하다(덤프에 `CREATE EXTENSION`이 들어 있고, Supabase는 `extensions` 스키마에 설치한다).
- 복원 뒤 권한 복구(필수): `--no-privileges` 복원은 함수의 `REVOKE ... FROM PUBLIC`을 되살리지 않아, 복원한 함수(`sojafit_agent.purge_inactive_projects` · `purge_log_records` · `purge_thread_checkpoints`, `public.quote_snapshot_has_forbidden_key` 등)가 PUBLIC 실행 가능이 된다. 복원 직후 `db/026_revoke_public_grants_and_rls.sql`을 다시 실행하고 `db/migrations/post_restore_privileges.sql`을 실행한다: `psql <새 DB> -v ON_ERROR_STOP=1 -f db/026_revoke_public_grants_and_rls.sql -f db/migrations/post_restore_privileges.sql`. `post_restore_privileges.sql`은 우리 함수 전부의 PUBLIC(과 `anon` · `authenticated`) 실행 권한을 회수하고, PUBLIC 실행 가능 함수 0 · 공개 역할 표 권한 0 · RLS 꺼진 표 0이 아니면 `EXCEPTION`으로 멈춘다. `rd_test7.sh`가 복원 → 이 절차 뒤 권한 지문(함수 PUBLIC 실행 · 표 RLS · PUBLIC 표 권한)이 원본과 같아지는 것을 확인한다.
- 이전 전 백업은 `--section` 순서를 어기기 쉽다(`pre-data` 뒤 함수 설정을 건너뛰고 바로 `data`로 가면 `approvals` COPY가 실패한다). 순서 요약:
  ```
  1) pg_restore --section=pre-data   2) ALTER FUNCTION ... SET search_path (위 2번 두 문장)
  3) pg_restore --section=data       4) pg_restore --section=post-data
  5) psql -f db/026_revoke_public_grants_and_rls.sql -f db/migrations/post_restore_privileges.sql
  ```
- 백업 파일은 질문 · 답 · 이메일을 담으므로 저장소에 두지 않는다.
