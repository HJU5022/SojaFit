# db

## 역할
- 이 폴더: Compose가 DB 컨테이너를 처음 만들 때 이름순으로 실행하는 초기화 SQL만 바로 아래에 둡니다. 스키마 문서는 `schema/`, 자동 실행하지 않는 SQL은 `manual/`에 둡니다. Compose가 `./db`를 Postgres 초기화 폴더로 마운트해 최상위 `.sql`만 실행하므로 SQL을 하위 폴더로 옮기지 않습니다.
- 넣는 것: 확장·스키마·인덱스 생성 SQL. 코퍼스 데이터 적재는 SQL이 아니라 `backend/rag/pipeline/ingest.py`가 합니다. 로컬 Compose 데모 계정(데모 사용자 A · B, 비밀번호 없음)은 `007_demo_accounts.sql`이 데모 모드에서 만들고, 그 밖의 계정은 `/signup` 가입이나 `python -m backend.auth`로 만듭니다. 실제 비밀번호는 저장소에 넣지 않습니다.
- 넣지 않는 것: 표 설계 문서(`db/schema/`), 평가용 계정 비밀번호(강사에게 따로 제출), 원본 문서(`data/corpus/`), 자동 실행하면 안 되는 SQL(`db/manual/`).
- 담당: 서비스·운영 (RAG 스키마·스냅샷·인덱스 SQL은 검색·데이터)

## 실행과 주의
- 2026-11-09 사양 표(`part_specifications`)를 버렸다(ADR 0016). 만들던 `011_part_specifications.sql`을 지웠고, 운영 DB의 표는 11-09에 지웠다. 이미 만든 로컬 볼륨에는 표가 남으므로 필요하면 따로 지운다(이 폴더에 `DROP` SQL은 두지 않았다). 같은 날 운영 DB에는 코퍼스 교체 뒤 0행에서 한 문서(document_id=8, B2104) 70행을 다시 넣은 기록이 있다(`docs/worklog/sth.md`).
- 실행 SQL과 초안은 세 자리 접두사를 사용합니다. 번호는 파일 실행 순서이며 기존 문서의 논리적 Migration 1·2 명칭과는 별개입니다. `001`·`004`·`011`은 `db/`에 일부러 없습니다. `001`은 비워 두었고, `004`는 업무 표 초안으로 `manual/004_create_business_tables.sql.draft`에 있으며, `011`(부품 사양 표)은 11-09에 지웠습니다. 빈 번호를 채우거나 번호를 당기지 마세요. 이미 적용한 파일의 이름과 번호는 바꾸지 않습니다.
- 빈 DB 볼륨을 처음 만들 때 실행 SQL은 파일명 순서로 적용됩니다. 현재 순서는 `000_init.sql` → `002_rag_corpus.sql` → `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql` → `007_demo_accounts.sql` → `008_multi_dim_embeddings.sql` → `009_chunk_embedding_bits.sql` → `010_google_auth.sql` → `012_document_category.sql` → `013_agent_memory.sql` → `014_thread_inputs.sql` → `015_analysis_limits.sql` → `016_memory_controls.sql` → `017_analysis_events.sql` → `018_projects.sql` → `019_conversations.sql` → `020_approvals_quotes.sql` → `021_auth_ip_limits.sql` → `022_token_limits.sql` → `023_retention.sql`입니다. 데모 모드(`DEMO_MODE=1`)면 데모 사용자 A · B를 만들고, 아니면 계정을 만들지 않습니다.
- Compose의 `thread-setup`은 DB healthcheck 뒤 `python -m backend.conversations.memory_service --setup`을 실행한다. 013~017 · 022 · 023을 멱등 적용하고 PostgresSaver/PostgresStore의 내부 표를 준비한 뒤 API가 시작된다. `vector` 확장이 이미 설치된 DB면 사용자 사실 의미 색인 표(`store_vectors`·`vector_migrations`)도 `sojafit_agent`에 만든다(확장은 설치하지 않음, SPEC 8.5). 이 서비스는 Compose 로컬 `db`에 연결하며 앱 일반 기동에는 DDL을 넣지 않는다. 기존 DB에 명령을 수동 실행할 때는 대상·권한·적용 이력을 먼저 확인한다.
- Compose의 `corpus-load`는 같은 DB healthcheck 뒤 `python -m backend.rag.pipeline.ingest data/demo/snapshot/manifest.jsonl data/demo/snapshot/chunks.jsonl /tmp/vectors --chunks-only`(`RAG_VECTOR_TYPE=halfvec`)로 데모 코퍼스 스냅샷(42문서 · 청크 1,556개)을 `source_documents` · `document_chunks`에 넣는다. 임베딩은 넣지 않는다. thread-setup과 함께 돌고, api는 두 서비스가 모두 성공한 뒤 시작한다. 이미 있는 문서 · 청크는 건너뛰므로 다시 떠도 행이 늘지 않는다.
- Compose 초기화는 이 폴더 바로 아래 파일만 실행하므로 `manual/`의 SQL은 자동 실행되지 않습니다. 업무 표 초안(`manual/004_create_business_tables.sql.draft`)은 코퍼스 SQL과 인증 SQL이 먼저 필요하며, 자동 실행 전 파일 순서·마이그레이션 이력 방식을 확정해야 합니다.
- 이미 초기화된 DB 볼륨에는 추가·변경한 초기화 SQL이 자동으로 적용되지 않습니다. `007_demo_accounts.sql`도 새 볼륨 생성 때만 자동 실행됩니다(기존 로컬 볼륨에는 데모 사용자 A · B가 없어 버튼 로그인이 404입니다). 기존 DB의 구조와 적용 이력을 확인하고 별도 마이그레이션 방식을 정합니다(아래 "기존 DB 인증 스키마 적용 전 점검").
- `docker compose down -v`는 DB 볼륨의 데이터를 삭제합니다. 기존 데이터를 보존해야 하는 환경에서는 실행하지 않습니다.

## 파일
- `016_memory_controls.sql` — 승인 원본과 분리된 기억 참조 상태·사용자 정정 메모
- `017_analysis_events.sql` — 요청·thread·trace 연결, 처리 결과와 단계 지연 (내용 제외)
- `021_auth_ip_limits.sql` — 클라이언트 IP 한도 표 2개(IP 원문 없이 키 해시만). `auth_signup_attempts`는 IP별 UTC 하루 가입 요청 수, `auth_login_ip_attempts`는 IP별 15분 로그인 실패 수·잠금(열은 `auth_login_attempts`와 같음). RLS를 켜고 공개 역할 권한을 회수한다. 다시 실행해도 아무것도 바꾸지 않는다. 기존 DB에는 자동 적용되지 않는다. [주의] 이 표가 없으면 비밀번호 로그인과 가입이 모두 503이 되므로, 이 코드를 배포하기 전에 대상 DB에 먼저 적용한다
  - 11-09 팀 Supabase 적용: 이 파일을 한 트랜잭션으로 직접 실행했다(Supabase 마이그레이션 기록 `supabase_migrations`에는 남지 않음). 적용 뒤 두 표 0행 · RLS 켜짐 · `anon` · `authenticated`의 SELECT · INSERT 권한 없음, `users` 5행 그대로를 확인했다
- `023_retention.sql` — 보관 기간 청소 함수 2개(11-09 결정, SPEC 8.5). `sojafit_agent.purge_inactive_projects(keep_days DEFAULT 60, batch_size DEFAULT 20)`: 마지막 활동(이름 변경 · 대화 · run · 승인 · 견적) 뒤 60일 지난 React 프로젝트와 같은 UUID 분석 기록 · checkpoint, React 대화에 딸리지 않은 분석 thread(자기 활동 기준), thread 없는 분석 회로(올린 뒤 60일)를 단계마다 최대 batch_size개 지운다. `sojafit_agent.purge_log_records(keep_days DEFAULT 30, batch_size DEFAULT 200)`: 분석 사건 · 하루 사용량(사용자 · 서비스) · 가입 시도(날짜 기준)와 창 · 잠금이 끝난 로그인 시도(계정 · IP)를 표마다 최대 batch_size개 지운다. 둘 다 트랜잭션 advisory lock으로 한 곳만 청소하고, 공개 역할의 EXECUTE를 회수한다. 앱은 새 분석(질문)을 시작할 때 부르고, Supabase pg_cron으로 하루 한 번 부를 수도 있다(켜지 않음). React 표가 없는 DB에서 프로젝트 함수는 아무것도 지우지 않는다. [주의] 기존 DB에는 자동 적용되지 않고, 함수가 없으면 분석 서비스가 시작하지 않는다(준비 명령 안내 오류). 이 코드를 배포하기 전에 022 다음에 적용한다
- `022_token_limits.sql` — 하루 LLM 토큰 상한(사용자 200,000 · 서비스 전체 2,000,000, UTC)의 예약 토큰 카운터. `sojafit_agent.analysis_usage`에 `reserved_tokens` 열, 날짜별 한 행 `sojafit_agent.analysis_service_usage`(공개 역할 권한 회수). 공급자 청구 토큰이 아니라 USD 예약과 같은 위쪽 경계의 합이다. 다시 실행해도 아무것도 바꾸지 않고 준비 명령이 015 뒤에 적용한다. [주의] 기존 DB에는 자동 적용되지 않는다. 이 열 · 표가 없으면 분석 서비스가 시작하지 않으므로(준비 명령 안내 오류) 이 코드를 배포하기 전에 대상 DB에 먼저 적용한다
- `015_analysis_limits.sql` — 비공개 사용자별 UTC 일일 예약액·빈도 제한 표. 실패도 예약액은 보존하며 실제 청구액과 구분
- `014_thread_inputs.sql` — threads.input_record nullable JSONB 추가. 기존 원본·행을 수정하지 않고 setup 명령에서 013 뒤 적용
- `013_agent_memory.sql` — 비공개 sojafit_agent 스키마의 업로드·thread·대화 이력·승인 원본. 라이브러리 내부 표는 별도 setup CLI가 생성
- `000_init.sql` — pgvector 확장 생성
- `002_rag_corpus.sql` — 코퍼스 문서·청크·임베딩 테이블과 관련 인덱스
- `003_auth.sql` — 사용자·인증 세션·로그인 시도 테이블
- `005_auth_attempt_window.sql` — 로그인 실패 집계 시간 컬럼 추가
- `006_user_roles.sql` — 계정 역할 추가. 기존 계정은 일반 사용자로 유지하며 관리자는 `python -m backend.auth --role admin`으로 따로 만든다
- `007_demo_accounts.sql` — 데모 모드(`DEMO_MODE=1`)에서만 로컬 데모 전용 일반 사용자 2개(`demo-a@example.test` · `demo-b@example.test`, 평가 계정 아님)를 만든다. 비밀번호 해시 칸에는 scrypt 형식이 아닌 표식(`backend/auth.py` `DEMO_PASSWORD_HASH`)을 넣어 비밀번호 로그인은 늘 실패하고, 데모 모드의 버튼 로그인(`POST /api/auth/demo-login`)만 이 표식을 가진 계정에 세션을 준다. 저장소에 비밀번호 · 해시를 두지 않는다(11-09). 새 볼륨 초기화 때 한 번 실행
- `008_multi_dim_embeddings.sql` — 임베딩 열을 차원 없는 halfvec으로 바꿔 3-small(1536)·voyage-4-large(1024) 행을 함께 둠. HNSW 인덱스를 지움. 기존 DB에는 자동 적용되지 않으므로 용량을 확인한 뒤 별도로 적용. 열이 halfvec(n)이면 `USING` 없이 차원 표시만 떼 표를 다시 쓰지 않는다(`scripts/db/voyage_rollout.py migrate`가 filenode 전후로 확인)
- `009_chunk_embedding_bits.sql` — voyage-4-large 임베딩의 1비트 코드 표(`chunk_embedding_bits`)를 만들고 기존 행에서 채움. dense 1단계 Hamming 후보 거르기용(사전 등록 #27). 인덱스 없음. 기존 DB에는 008 뒤에 별도로 적용하며, 다시 실행해도 있는 행은 그대로
- `010_google_auth.sql` — Google 관리자 로그인용 일시 상태·승인 대기·계정 연결 테이블 및 공개 권한 제한. 기존 DB에는 자동 적용되지 않으며, 적용 전 마이그레이션·복구를 별도로 검토한다.
- `012_document_category.sql` — `source_documents`에 문서 분류 열(`category`, NULL 허용)을 더함. 값은 분류 이름(예: `schottky-rectifier`, `pipeline/specs.py`의 `family`)이고 `ingest.py`가 문서를 넣을 때 채운다. 다시 실행해도 아무것도 바꾸지 않는다. 빈 Compose 볼륨에서만 자동 실행되므로 이미 있는 DB에는 따로 적용하고 기존 행은 청크 파일에서 채운다.
- `019_conversations.sql` — 프로젝트 소유 대화·메시지·실행 및 접근 제한, 공개 결과 중첩 키·타입과 품번 검증. 체크포인트는 같은 UUID의 사용자 분석 thread로 `sojafit_agent` 스키마에 둔다(`013_agent_memory.sql`과 setup CLI). 기존·공유 DB에는 자동 적용하지 않는다.
- `020_approvals_quotes.sql` — 사람 승인·가격 없는 견적·승인 사례, 소유자 인덱스·삭제 cascade·공개 권한 제한과 중첩 가격·재고 키 거절. 기존·공유 DB에는 자동 적용하지 않는다.
- `018_projects.sql` — 사용자 소유 프로젝트와 정규화 회로 1:1 저장. 사용자·프로젝트 삭제 cascade, 소유자별 목록 인덱스, 명시적 CHECK, 공개 역할 및 sequence 권한 회수, RLS(공개 정책 없음). 새 빈 볼륨에서 017 다음 실행하며 기존 볼륨·공유 DB에는 자동 적용하지 않는다. `manual/004_create_business_tables.sql.draft`의 옛 `circuits`와 충돌하므로 초안을 그대로 적용하지 않는다. 현재 서버는 데모 생성만 제공한다.
- `manual/` — 자동 실행하지 않는 SQL(업무 표 초안, halfvec 수동 전환). [MANUAL.md](manual/MANUAL.md)
- `schema/` — 표 설계 문서(`erd.md`, `table-definition.md`). [SCHEMA.md](schema/SCHEMA.md)

## 팀 Supabase 적재 현황 스냅샷

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

### 현재 `public` 스키마에서 확인되지 않은 영역

- `manual/004_create_business_tables.sql.draft`의 업무 테이블 11개(`circuits`, `parts`, `analysis_runs`, `candidate_evaluations`, `quotes` 등)는 아직 생성·적재되지 않았습니다.
- LangGraph가 만드는 `checkpoints`·`checkpoint_blobs`·`checkpoint_writes`·`checkpoint_migrations`와 Store의 `store`·`store_vectors`·마이그레이션 표는 아직 생성·적재되지 않았습니다.
- 위 미생성 판정은 조회 당시 팀 DB의 `public` 스키마 기준입니다. 다른 스키마나 외부 저장소의 데이터 존재 여부를 뜻하지 않습니다.

## 기존 DB 인증 스키마 적용 전 점검

1. 대상이 공유·운영 DB인지 확인하고, 현재 적용 이력과 백업·복구 경로를 담당자와 확인합니다. 비밀번호·접속 문자열은 기록하지 않습니다.
2. 읽기 전용으로 현재 스키마와 필요한 컬럼·제약을 확인합니다. 예시:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'auth_sessions', 'auth_login_attempts');

SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('users', 'auth_sessions', 'auth_login_attempts')
ORDER BY table_name, ordinal_position;

SELECT conrelid::regclass AS table_name, conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN (SELECT oid FROM pg_class WHERE relnamespace = 'public'::regnamespace
  AND relname IN ('users', 'auth_sessions', 'auth_login_attempts'))
ORDER BY conrelid::regclass::text, conname;
```

3. 테이블이 모두 없는 경우, 별도 빈 테스트 DB에서 `003_auth.sql`, `005_auth_attempt_window.sql`, `006_user_roles.sql` 순서로 적용하고 로그인 테스트를 먼저 확인합니다. 이미 일부 또는 전체가 있으면 해당 정의·데이터·이력을 비교해 필요한 후속 마이그레이션을 별도로 작성합니다. `CREATE TABLE IF NOT EXISTS`만으로 기존 구조의 일치를 보장하지 않습니다.
4. 적용 경로와 이력 관리 방식은 팀 검토 후 확정합니다. 운영·공유 DB에 자동 적용하거나 볼륨을 삭제하지 않습니다.

- 이미 `auth_login_attempts`가 있으면 `window_started_at` 존재 여부와 적용 이력을 확인합니다. 컬럼이 없고 다른 구조가 인증 코드와 일치하는 경우에만 검토된 `005_auth_attempt_window.sql` 적용을 계획합니다. 존재한다면 무조건 다시 실행하지 않습니다. 기존 데이터를 지우지 않고 테스트 DB에서 먼저 확인합니다. 애플리케이션 갱신 전 DB 마이그레이션이 선행돼야 합니다.
- `006_user_roles.sql`도 기존 `users.role` 유무와 이력을 확인한 뒤 한 번만 적용합니다. 기존 계정은 `user`로 유지합니다. 새 API 코드보다 먼저 반영해야 합니다.
- `007_demo_accounts.sql`은 새 Compose 볼륨에서만 자동 실행되며 서비스 DB에는 적용하지 않습니다. 시드 SQL은 이미 있는 계정의 비밀번호나 역할을 덮어쓰지 않습니다(같은 이메일로 가입한 계정은 표식이 없어 버튼으로 들어갈 수 없음).
