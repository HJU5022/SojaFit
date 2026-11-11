# db

## 역할
- 이 폴더: Compose가 DB 컨테이너를 처음 만들 때 이름순으로 실행하는 초기화 SQL만 바로 아래에 둡니다. Compose가 `./db`를 Postgres 초기화 폴더로 마운트해 **최상위 `.sql`만** 실행하므로 `legacy/` · `migrations/` · `manual/`의 SQL은 자동 실행되지 않습니다.
- 넣는 것: 새 DB 첫 기동용 SQL(확장 · 코퍼스 · 서비스 표 기준선 · 공개 권한 회수). 운영 DB를 옮기는 SQL은 `migrations/`, 기준선 이전의 옛 증분 SQL(이력)은 `legacy/`. 코퍼스 데이터 적재는 SQL이 아니라 `backend/rag/pipeline/ingest.py`가 합니다. 데모 계정(A · B, 비밀번호 없음)은 SQL 시드가 아니라 `DEMO_MODE=1`에서 첫 데모 로그인 때 앱이 만듭니다. 그 밖의 계정은 `/signup` 가입이나 `python -m backend.auth`로 만듭니다. 실제 비밀번호는 저장소에 두지 않습니다.
- 넣지 않는 것: 표 설계 문서(`db/schema/`), 평가용 계정 비밀번호(강사에게 따로 제출), 원본 문서(`data/corpus/`), 자동 실행하면 안 되는 SQL(`db/manual/`).
- 담당: 서비스·운영 (RAG 스키마·스냅샷·인덱스 SQL은 검색·데이터)

## 실행과 주의
- 구조(11-11 재설계 M 단계, [결정]): 서비스 표는 증분 파일 20여 개가 아니라 **기준선 한 파일**(`020_service_baseline.sql`)이 만든다. 옛 `003`~`025` · `027`~`029`는 `legacy/`로 옮겨 이력만 남겼고 **어디에서도 실행하지 않는다**. 기준선은 옛 체인 + 운영 이전 SQL을 적용한 결과와 구조가 같다(`scripts/db/verify_chain/verify_chain.sh`가 차이 0줄을 확인한다).
- 빈 DB 볼륨을 처음 만들 때 실행 순서: `000_init.sql` → `002_rag_corpus.sql` → `008_multi_dim_embeddings.sql` → `009_chunk_embedding_bits.sql` → `012_document_category.sql` → `020_service_baseline.sql` → `026_revoke_public_grants_and_rls.sql`. 번호 `001`·`003`~`007`·`010`·`011`·`013`~`019`·`021`~`025`는 `db/` 바로 아래에 일부러 없습니다(서비스 표는 기준선이 대체, `007` 데모 시드는 앱으로 이동, `011` 사양 표는 ADR 0016으로 폐기).
- Compose의 `thread-setup`은 DB healthcheck 뒤 `python -m backend.conversations.memory_service --setup`을 실행해 **LangGraph 표(PostgresSaver/PostgresStore 내부 표)만** 만듭니다. 서비스 표는 만들지 않으며 SQL 파일을 적용하지도 않습니다. `vector` 확장이 이미 설치된 DB면 사용자 사실 의미 색인 표(`store_vectors`·`vector_migrations`)도 `sojafit_agent`에 만듭니다.
- Compose의 `corpus-load`는 같은 DB healthcheck 뒤 `python -m backend.rag.pipeline.ingest data/demo/snapshot/manifest.jsonl data/demo/snapshot/chunks.jsonl /tmp/vectors --chunks-only`(`RAG_VECTOR_TYPE=halfvec`)로 데모 코퍼스 스냅샷(42문서 · 청크 1,556개)을 `source_documents` · `document_chunks`에 넣습니다. 임베딩은 넣지 않습니다.
- **볼륨 주의**: 이미 초기화된 DB 볼륨에는 초기화 SQL이 다시 적용되지 않습니다. **028 이전(옛 구조) 로컬 볼륨은 새 코드와 맞지 않으므로 `docker compose down -v`로 지우고 다시 만들어야 합니다**(`down -v`는 DB 볼륨의 데이터를 지웁니다. 보존할 데이터가 있는 환경에서는 실행하지 않습니다).
- 기존 DB(운영)는 기준선을 쓰지 않고 `migrations/`의 이전 SQL을 순서대로 적용합니다(expand → 새 코드 배포 → contract). 각 파일 끝이 이력 표 `public.app_migrations`에 한 줄을 남깁니다. 새 DB의 기준선은 `2026-11-service-baseline` 한 줄을 남깁니다([결정] D6: 우리 이력 표를 쓰고 Supabase `supabase_migrations`는 건드리지 않음).
- 2026-11-09 사양 표(`part_specifications`)를 버렸다(ADR 0016). 이미 만든 로컬 볼륨에는 표가 남으므로 필요하면 따로 지운다. 같은 날 운영 DB에는 코퍼스 교체 뒤 0행에서 한 문서(document_id=8, B2104) 70행을 다시 넣었다.

### 실행 기록

- 2026-11-09 사양 표(`part_specifications`)를 버렸다(ADR 0016). 만들던 `011_part_specifications.sql`을 지웠고, 운영 DB의 표는 11-09에 지웠다. 이미 만든 로컬 볼륨에는 표가 남으므로 필요하면 따로 지운다(이 폴더에 `DROP` SQL은 두지 않았다). 같은 날 운영 DB에는 코퍼스 교체 뒤 0행에서 한 문서(document_id=8, B2104) 70행을 다시 넣은 기록이 있다(`docs/worklog/sth.md`).
- 실행 SQL과 초안은 세 자리 접두사를 사용합니다. 번호는 파일 실행 순서이며 기존 문서의 논리적 Migration 1·2 명칭과는 별개입니다. `001`·`004`·`011`은 `db/`에 일부러 없습니다. `001`은 비워 두었고, `004`는 옛 업무 표 초안(`manual/004_create_business_tables.sql.draft`, 018~020으로 대체돼 적용하지 않음)이며, `011`(부품 사양 표)은 11-09에 지웠습니다. 빈 번호를 채우거나 번호를 당기지 마세요. 이미 적용한 파일의 이름과 번호는 바꾸지 않습니다.
- 빈 DB 볼륨은 위의 7개 SQL을 파일명 순서로 적용합니다. 데모 계정 A · B는 `DEMO_MODE=1`에서 첫 데모 로그인 때 앱이 만듭니다.
- Compose의 `thread-setup`은 DB healthcheck 뒤 `python -m backend.conversations.memory_service --setup`을 실행한다. 013~017 · 022 · 023을 멱등 적용하고 PostgresSaver/PostgresStore의 내부 표를 준비한 뒤 API가 시작된다. `vector` 확장이 이미 설치된 DB면 사용자 사실 의미 색인 표(`store_vectors`·`vector_migrations`)도 `sojafit_agent`에 만든다(확장은 설치하지 않음, SPEC 8.5). 이 서비스는 Compose 로컬 `db`에 연결하며 앱 일반 기동에는 DDL을 넣지 않는다. 기존 DB에 명령을 수동 실행할 때는 대상·권한·적용 이력을 먼저 확인한다.
- Compose의 `corpus-load`는 같은 DB healthcheck 뒤 `python -m backend.rag.pipeline.ingest data/demo/snapshot/manifest.jsonl data/demo/snapshot/chunks.jsonl /tmp/vectors --chunks-only`(`RAG_VECTOR_TYPE=halfvec`)로 데모 코퍼스 스냅샷(42문서 · 청크 1,556개)을 `source_documents` · `document_chunks`에 넣는다. 임베딩은 넣지 않는다. thread-setup과 함께 돌고, api는 두 서비스가 모두 성공한 뒤 시작한다. 이미 있는 문서 · 청크는 건너뛰므로 다시 떠도 행이 늘지 않는다.
- Compose 초기화는 이 폴더 바로 아래 파일만 실행하므로 `manual/`의 SQL은 자동 실행되지 않습니다. 옛 업무 표 초안(`manual/004_create_business_tables.sql.draft`)은 018~020이 업무 표(프로젝트 · 회로 · 대화 · 실행 · 메시지 · 승인 · 견적 · 승인 사례)를 만들면서 대체됐습니다. 초안의 `circuits`가 018과 충돌하므로 적용하지 않고 이력으로만 둡니다.
- 이미 초기화된 DB 볼륨에는 추가·변경한 초기화 SQL이 자동으로 적용되지 않습니다. 기존 DB의 구조와 적용 이력을 확인하고 별도 마이그레이션 방식을 정합니다(아래 "기존 DB 인증 스키마 적용 전 점검").
- `docker compose down -v`는 DB 볼륨의 데이터를 삭제합니다. 기존 데이터를 보존해야 하는 환경에서는 실행하지 않습니다.

## 파일
- `016_memory_controls.sql` — 승인 원본과 분리된 기억 참조 상태·사용자 정정 메모
- `017_analysis_events.sql` — 요청·thread·trace 연결, 처리 결과와 단계 지연 (내용 제외)
- `021_auth_ip_limits.sql` — 클라이언트 IP 한도 표 2개(IP 원문 없이 키 해시만). `auth_signup_attempts`는 IP별 UTC 하루 가입 요청 수, `auth_login_ip_attempts`는 IP별 15분 로그인 실패 수·잠금(열은 `auth_login_attempts`와 같음). RLS를 켜고 공개 역할 권한을 회수한다. 다시 실행해도 아무것도 바꾸지 않는다. 기존 DB에는 자동 적용되지 않는다. [주의] 이 표가 없으면 비밀번호 로그인과 가입이 모두 503이 되므로, 이 코드를 배포하기 전에 대상 DB에 먼저 적용한다
  - 11-09 팀 Supabase 적용: 이 파일을 한 트랜잭션으로 직접 실행했다(Supabase 마이그레이션 기록 `supabase_migrations`에는 남지 않음). 적용 뒤 두 표 0행 · RLS 켜짐 · `anon` · `authenticated`의 SELECT · INSERT 권한 없음, `users` 5행 그대로를 확인했다
- `023_retention.sql` — 보관 기간 청소 함수 2개(11-09 결정, SPEC 8.5). `sojafit_agent.purge_inactive_projects(keep_days DEFAULT 60, batch_size DEFAULT 20)`: 마지막 활동(이름 변경 · 대화 · run · 승인 · 견적) 뒤 60일 지난 React 프로젝트와 같은 UUID 분석 기록 · checkpoint, React 대화에 딸리지 않은 분석 thread(자기 활동 기준), thread 없는 분석 회로(올린 뒤 60일)를 단계마다 최대 batch_size개 지운다. `sojafit_agent.purge_log_records(keep_days DEFAULT 30, batch_size DEFAULT 200)`: 분석 사건 · 하루 사용량(사용자 · 서비스) · 가입 시도(날짜 기준)와 창 · 잠금이 끝난 로그인 시도(계정 · IP)를 표마다 최대 batch_size개 지운다. 둘 다 트랜잭션 advisory lock으로 한 곳만 청소하고, 공개 역할의 EXECUTE를 회수한다. 앱은 새 분석(질문)을 시작할 때 부르고, Supabase pg_cron으로 하루 한 번 부를 수도 있다(켜지 않음). React 표가 없는 DB에서 프로젝트 함수는 아무것도 지우지 않는다. [주의] 기존 DB에는 자동 적용되지 않고, 함수가 없으면 분석 서비스가 시작하지 않는다(준비 명령 안내 오류). 이 코드를 배포하기 전에 022 다음에 적용한다
- `024_projects_demo_c01.sql` — 데모 프로젝트 허용 목록(`ck_projects_demo`)에 c01(`attiny85_time_switch`)을 더한다(11-10). 빈 볼륨은 018이 이미 새 목록이라 결과가 같고, 018을 먼저 적용한 기존 DB(운영 Supabase · 조원 로컬)에 이 파일을 적용한다.
- `025_runs_safe_result_preferred_mount.sql` — 분석 결과 저장 검사(`runs_safe_result_check`)의 판정 형식에 `preferred_mount`를 더한다(11-10). 판정이 붙은 run이 모르는 칸으로 거부돼 503이던 문제. 빈 볼륨은 019가 이미 새 형식이고, 기존 DB에 이 파일을 적용한다.
- `legacy/026_projects_catalog_demo.sql` — 과거 회로 카탈로그 제약 변경 이력. 새 DB에는 기준선의 `ck_projects_demo`를 적용한다. 실제 허용 ID는 `data/circuits/catalog.json`을 읽는 서버가 검증한다.
- `022_token_limits.sql` — 하루 LLM 토큰 상한(사용자 200,000 · 서비스 전체 2,000,000, UTC)의 예약 토큰 카운터. `sojafit_agent.analysis_usage`에 `reserved_tokens` 열, 날짜별 한 행 `sojafit_agent.analysis_service_usage`(공개 역할 권한 회수). 공급자 청구 토큰이 아니라 USD 예약과 같은 위쪽 경계의 합이다. 다시 실행해도 아무것도 바꾸지 않고 준비 명령이 015 뒤에 적용한다. [주의] 기존 DB에는 자동 적용되지 않는다. 이 열 · 표가 없으면 분석 서비스가 시작하지 않으므로(준비 명령 안내 오류) 이 코드를 배포하기 전에 대상 DB에 먼저 적용한다
- `015_analysis_limits.sql` — 비공개 사용자별 UTC 일일 예약액·빈도 제한 표. 실패도 예약액은 보존하며 실제 청구액과 구분
- `014_thread_inputs.sql` — threads.input_record nullable JSONB 추가. 기존 원본·행을 수정하지 않고 setup 명령에서 013 뒤 적용
- `013_agent_memory.sql` — 비공개 sojafit_agent 스키마의 업로드·thread·대화 이력·승인 원본. 라이브러리 내부 표는 별도 setup CLI가 생성
- `000_init.sql` — pgvector 확장 생성
- `002_rag_corpus.sql` — 코퍼스 문서·청크·임베딩 테이블과 관련 인덱스
- `008_multi_dim_embeddings.sql` — 임베딩 열을 차원 없는 halfvec으로 바꿔 3-small(1536)·voyage-4-large(1024) 행을 함께 둠. HNSW 인덱스를 지움. 기존 DB에는 자동 적용되지 않으므로 용량을 확인한 뒤 별도로 적용(`scripts/db/voyage_rollout.py migrate`)
- `009_chunk_embedding_bits.sql` — voyage-4-large 임베딩의 1비트 코드 표(`chunk_embedding_bits`)를 만들고 기존 행에서 채움. dense 1단계 Hamming 후보 거르기용(사전 등록 #27). 인덱스 없음. 기존 DB에는 008 뒤에 별도로 적용
- `012_document_category.sql` — `source_documents`에 문서 분류 열(`category`, NULL 허용)을 더함. 값은 분류 이름(예: `schottky-rectifier`)이고 `ingest.py`가 채운다. 기존 DB에는 따로 적용
- `020_service_baseline.sql` — **서비스 표 기준선**: `public` 16표(users · auth_* 5 · projects · circuits · threads · runs · messages · approvals · quotes · approved_cases · app_migrations)와 `sojafit_agent` 5표(threads · messages · analysis_events · analysis_usage · analysis_service_usage), 체크포인트 삭제 트리거, 보관 기간 청소 함수 2개, 모든 서비스 표 RLS ON(정책 0). `-- @@AGENT@@` 줄 앞은 public 표만(시험이 격리 스키마에 적용). 코퍼스 · LangGraph 표는 포함하지 않음
- `026_revoke_public_grants_and_rls.sql` — 공개 역할(anon · authenticated)의 권한을 모두 회수하고(코퍼스 표 4개 · 시퀀스 · 우리 함수 · public 기본 권한) 앱 표(public · sojafit_agent)의 RLS를 켠다(11-10 운영 DB 점검). 소유자 · 슈퍼유저는 RLS를 우회해 서버 동작은 그대로다. 역할이 없는 DB(compose · CI)는 RLS만 켠다. 여러 번 돌려도 같다
- `legacy/` — 기준선 이전의 옛 증분 서비스 SQL 20개(`003`~`025` · `027`~`029`)와 설명. 이력용이며 실행하지 않는다(운영 이전 되돌리기가 일부를 다시 읽는다). [LEGACY.md](legacy/LEGACY.md)
- `migrations/` — 운영 DB 이전 SQL(expand · contract P1 · contract P2 · 선택 2b · 되돌리기). 새 DB가 아니라 이미 서비스 표가 있는 DB용. [MIGRATIONS.md](migrations/MIGRATIONS.md)
- `redesign/` — 서비스 DB 재설계(11-11) 설계 문서(현재 · 목표 구조, 영향 지도)와 일회용 Postgres 16 · 17 검증 스크립트. 요약은 `redesign/REDESIGN.md`
- `manual/` — 자동 실행하지 않는 SQL(옛 업무 표 초안 이력, halfvec 수동 전환). [MANUAL.md](manual/MANUAL.md)
- `schema/` — 표 설계 문서(`erd.md`, `table-definition.md`는 DB에서 자동 생성). [SCHEMA.md](schema/SCHEMA.md)


## 백업 복원 (새 DB · 새 Supabase 프로젝트로 옮길 때)
- 순서는 **구조 → 데이터 → 제약 · 인덱스**다. 새 기준선 DB, 이전 SQL을 적용한 DB, 되돌린 DB의 백업(`pg_dump -Fc`)은 빈 DB에 한 번에 `pg_restore`해도 오류가 없다(`db/redesign/verify/rd_test7.sh`가 PG16 · 17에서 확인). 명령: `pg_restore -d <새 DB> --no-owner --no-privileges --exit-on-error 파일.dump`.
- **이전 SQL을 적용하기 전의 옛 구조에서 받은 백업**은 한 번에 복원하면 `approvals` COPY가 `function quote_snapshot_has_forbidden_key does not exist`로 실패한다(재귀 함수에 `search_path`가 없고 `pg_restore`는 복원 중 `search_path`를 비움). 그때는 세 번에 나눠 복원한다:
  1. `pg_restore -d <새 DB> --no-owner --no-privileges --section=pre-data 파일.dump`
  2. `psql <새 DB> -c 'ALTER FUNCTION public.quote_snapshot_has_forbidden_key(jsonb) SET search_path = "$user", public' -c 'ALTER FUNCTION public.conversation_json_matches(jsonb, jsonb) SET search_path = "$user", public'`
  3. `pg_restore ... --section=data 파일.dump`, 이어서 `pg_restore ... --section=post-data 파일.dump`
- 운영에서 `migrate_prod_1_expand.sql`(E0)을 적용한 뒤 받은 백업은 위 2번이 이미 들어 있어 한 번에 복원된다. 새 프로젝트에서는 `vector` 확장이 필요하다(덤프에 `CREATE EXTENSION`이 들어 있고, Supabase는 `extensions` 스키마에 설치된다).
- **복원 뒤 권한 복구(필수)**: `--no-privileges` 복원은 함수의 `REVOKE ... FROM PUBLIC`을 되살리지 않아, 복원한 함수(`sojafit_agent.purge_inactive_projects` · `purge_log_records` · `purge_thread_checkpoints`, `public.quote_snapshot_has_forbidden_key` 등)가 PUBLIC 실행 가능이 된다. 복원 직후 **`db/026`을 다시 실행하고 `db/migrations/post_restore_privileges.sql`을 실행**한다: `psql <새 DB> -v ON_ERROR_STOP=1 -f db/026_revoke_public_grants_and_rls.sql -f db/migrations/post_restore_privileges.sql`. 이 파일이 우리 함수 전부의 PUBLIC(과 `anon` · `authenticated`) 실행 권한을 회수하고, PUBLIC 실행 가능 함수 0 · 공개 역할 표 권한 0 · RLS 꺼진 표 0이 아니면 `EXCEPTION`으로 멈춘다. `rd_test7.sh`가 복원 → 이 절차 뒤 권한 지문(함수 PUBLIC 실행 · 표 RLS · PUBLIC 표 권한)이 원본과 같아지는 것을 확인한다.
- **이전 전 백업은 3단계 `--section` 순서를 어기기 쉽다**(`pre-data` 뒤 함수 설정을 건너뛰고 바로 `data`로 가면 `approvals` COPY가 실패). 순서 요약:
  ```
  1) pg_restore --section=pre-data   2) ALTER FUNCTION ... SET search_path (위 2번 두 문장)
  3) pg_restore --section=data       4) pg_restore --section=post-data
  5) psql -f db/026_revoke_public_grants_and_rls.sql -f db/migrations/post_restore_privileges.sql
  ```
- 백업 파일은 질문 · 답 · 이메일을 담으므로 저장소에 두지 않는다.

## 팀 Supabase 적재 현황 스냅샷 (2026-11-05 기록)

> 이 절은 2026-11-05의 조회 기록이며 지금 상태가 아닙니다. 그 뒤의 변경(11-09 코퍼스 교체와 사양 표 삭제, 11-09 `021_auth_ip_limits.sql` 적용 등)은 아래 표에 반영하지 않았습니다.

> 조회 시각: 2026-11-05 20:37:12 KST. 로컬 `.env`가 가리키는 팀 Supabase PostgreSQL에 읽기 전용 트랜잭션으로 접속해 `public` 스키마의 테이블별 `count(*)`와 비민감 집계만 확인했습니다. 문서 본문·이메일·비밀번호 해시·세션 토큰 해시·Google 식별자 원문은 읽거나 기록하지 않았습니다. 아래 수치는 적재·로그인·만료 정리에 따라 바뀌는 시점 스냅샷이며 운영 감사 로그가 아닙니다.

### RAG 코퍼스

| 테이블 | 행 수 | 확인한 비민감 분류 |
|---|---:|---|
| `source_documents` | 1,360 | `DATASHEET` 1,360건 |
| `document_chunks` | 52,244 | 문서 청크 |
| `chunk_embeddings` | 52,244 | `voyage-4-large` 52,244건 |
| `chunk_embedding_bits` | 52,244 | 같은 청크의 1비트 검색 코드 |

문서 1,360건에서 청크 52,244건이 적재돼 있고, 각 청크에 `voyage-4-large` 임베딩과 1비트 코드가 한 건씩 있습니다.

### 사용자·인증

| 테이블 | 행 수 | 조회 당시 상태 |
|---|---:|---|
| `users` | 5 | 활성 관리자 3명, 활성 일반 사용자 2명 |
| `auth_sessions` | 5 | 활성 1건, 만료 4건 |
| `auth_login_attempts` | 0 | 실패 집계·잠금 행 없음 |
| `auth_google_identities` | 1 | 기존 관리자와 승인된 Google 계정 연결 1건 |
| `auth_google_pending` | 0 | 활성·만료 승인 대기 행 없음 |
| `auth_google_states` | 2 | 활성 0건, 만료 2건 |

활성 세션 1건은 시험 Cloud Run에서 Google 관리자 로그인 후 발급된 세션입니다. `auth_google_identities`는 연결을 철회할 때까지 유지하지만, `auth_sessions`·`auth_google_states`·`auth_google_pending`은 로그인 처리와 만료 정리에 따라 바뀌는 임시 상태입니다. 전용 로그인 성공·실패 감사 이력 테이블은 없습니다.

후속 인증 검증(2026-11-05 21:48:13 KST)에서는 자동화 탭과 일반 탭을 섞은 최초 로그아웃 시험에서 남은 관리자 ID 5의 세션 1건을 사용자 승인 후 정리하고, 일반 Chrome 탭 하나에서 다시 시험했습니다. Google 로그인 후 `/api/auth/me`가 `user_id=5`, `role=admin`을 반환했고, 같은 탭에서 로그아웃한 뒤 브라우저는 `401`, DB의 해당 사용자 세션은 0건이 됐으며 Google 연결 1건은 유지됐습니다. 이어 같은 관리자 계정의 기존 ID·PW 로그인도 `/api/auth/me`에서 같은 ID·역할을 반환했고, DB에 활성 세션 1건·로그인 실패 행 0건·Google 연결 1건이 확인됐습니다. 비밀번호·쿠키·토큰·Google 식별자 원문은 조회하거나 기록하지 않았습니다.

연결 철회 검증(2026-11-05 21:54:04 KST)에서는 사용자 승인 후 관리자 ID 5의 `auth_google_identities` 1건을 삭제했고 사용자 계정·관리자 역할·비밀번호 해시는 유지됐습니다. 철회 뒤 같은 Google 계정으로 로그인했을 때 관리자 세션 없이 `auth_google_pending` 1건만 생성됐습니다. 검증 이메일과 기존 관리자 로그인 ID가 일치하고 활성 요청이 정확히 1건인 것을 확인한 뒤 관리자 ID 5에 다시 승인했으며, 최종 상태는 Google 연결 1건·활성 승인 대기 0건·세션 0건입니다. 따라서 연결 철회는 Google 로그인 경로와 기존 세션만 제거하고 ID·PW 계정은 유지하며, 재승인 자체는 세션을 자동 발급하지 않습니다.

### 조회 당시 `public` 스키마에서 확인되지 않은 영역

- `manual/004_create_business_tables.sql.draft`의 업무 테이블 11개(`circuits`, `parts`, `analysis_runs`, `candidate_evaluations`, `quotes` 등)는 생성·적재되지 않았습니다. 이 초안은 뒤에 018~020으로 대체됐습니다.
- LangGraph가 만드는 `checkpoints`·`checkpoint_blobs`·`checkpoint_writes`·`checkpoint_migrations`와 Store의 `store`·`store_vectors`·마이그레이션 표는 아직 생성·적재되지 않았습니다.
- 위 미생성 판정은 조회 당시 팀 DB의 `public` 스키마 기준입니다. 다른 스키마나 외부 저장소의 데이터 존재 여부를 뜻하지 않습니다.

## 기존 DB(운영) 적용 전 점검

1. 대상이 공유·운영 DB인지 확인하고 백업과 복구 경로를 확인합니다(`migrations/migrate_prod_1_expand.sql` 머리의 `pg_dump` 명령). 비밀번호·접속 문자열은 기록하지 않습니다.
2. 이전 순서와 되돌리기는 [`migrations/MIGRATIONS.md`](migrations/MIGRATIONS.md)를 따릅니다. 운영·공유 DB에 기준선 · 초기화 SQL을 자동 적용하거나 볼륨을 삭제하지 않습니다.
3. `008` · `009`(임베딩 열 전환, 비트 표)는 용량을 확인한 뒤 `scripts/db/voyage_rollout.py`로 따로 적용합니다.
