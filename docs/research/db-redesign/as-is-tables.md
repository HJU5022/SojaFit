# 현재(as-is) 서비스 표 정의서

- 기준: **운영 DB(Supabase) 구조를 11-10 밤에 읽기 전용으로 뽑은 것**(칸 · 타입 · 키 · 인덱스는 `pg_catalog`에서 자동 생성, 의미 · 소유 코드는 손으로 적음). 행 내용은 읽지 않았다.
- 범위: 서비스 표 25개(`public` 16 + `sojafit_agent` 9). 코퍼스 4표(`source_documents` · `document_chunks` · `chunk_embeddings` · `chunk_embedding_bits`)와 LangGraph 체크포인트 표(`checkpoints` · `checkpoint_blobs` · `checkpoint_writes` · `*_migrations`)는 범위 밖이다.
- 새 구조와의 비교는 [`to-be-tables.md`](to-be-tables.md), 그림은 [`as-is-erd.md`](as-is-erd.md).

| 스키마.표 | 행 | 크기 | 목적 |
|---|---|---|---|
| `public.users` | 5 | 48 KB | 계정. 비밀번호 계정, Google 가입 계정(표식 해시), 로컬 데모 버튼 계정, 관리자가 모두 이 표 하나 |
| `public.auth_sessions` | 10 | 56 KB | 로그인 세션. 쿠키 토큰의 SHA-256 해시만 저장(원문 없음). 절대 8시간, 유휴 2시간(11-10 자동 연결 브랜치 … |
| `public.auth_login_attempts` | 0 | 24 KB | 계정(이메일 해시)별 로그인 실패 횟수와 잠금(5회 → 15분) |
| `public.auth_login_ip_attempts` | 0 | 24 KB | IP(해시)별 로그인 실패 횟수와 잠금(15분 30회) |
| `public.auth_signup_attempts` | 1 | 24 KB | IP(해시)별 하루 가입 요청 수. 이메일 가입은 DEMO_MODE=1에서만 열려 운영에서는 쓰이지 않음 |
| `public.auth_google_states` | 0 | 32 KB | Google OAuth 시작~콜백 사이의 일회용 상태(state · PKCE verifier · nonce). 10분 뒤 만료 |
| `public.auth_google_pending` | 1 | 32 KB | Google 계정을 기존 관리자에 연결해 달라는 승인 대기 요청(15분). 11-10 자동 연결 결정으로 콜백이 더 이상 만… |
| `public.auth_google_identities` | 2 | 48 KB | Google 계정(issuer + subject)과 사용자의 연결. 사용자 1명에 Google 신원 1개 |
| `public.projects` | 11 | 48 KB | 사용자가 만든 프로젝트(= 회로 하나를 검토하는 작업 단위). 데모 회로 또는 업로드한 넷리스트 |
| `public.circuits` | 11 | 112 KB | 프로젝트의 정규화된 회로(부품 · 연결). 넷리스트 원문은 저장하지 않음. 프로젝트와 1:1 |
| `public.threads` | 10 | 40 KB | 프로젝트 안의 대화(화면의 '새 대화'). 질문 · 실행의 묶음 |
| `public.runs` | 10 | 112 KB | 질문 한 번의 실행과 공개 결과(safe_result). GET /api/runs/{id}의 응답 원본 |
| `public.messages` | 18 | 96 KB | 화면에 보이는 대화 기록(사용자 질문 · 어시스턴트 답) |
| `public.approvals` | 3 | 112 KB | 사람이 후보 하나를 승인한 기록. 승인 시점의 판정 스냅샷(JSON) 보관. 메시지당 1건 |
| `public.quotes` | 3 | 64 KB | 승인에서 만든 가격 없는 견적(품번 · 수량). 승인당 UNIQUE는 없어 한 승인에서 여러 건 가능 |
| `public.approved_cases` | 3 | 64 KB | 화면의 '승인 사례' 목록. 승인과 같이 만들고 사용자가 지울 수 있음. 새 분석에 기억으로 넘기지 않음(11-09 중단) |
| `sojafit_agent.circuits` | 10 | 168 KB | 분석 서비스용 회로 사본. 대화 하나당 1행(id = 대화 UUID), public.circuits.connections의 … |
| `sojafit_agent.threads` | 10 | 48 KB | 분석 서비스의 대화 상태 기계(version · retries · status · 현재 입력 기록). id = public.… |
| `sojafit_agent.messages` | 26 | 104 KB | 분석 문맥용 사용자 입력(이전 입력 최대 12개를 프롬프트에 붙임)과 어시스턴트 답 |
| `sojafit_agent.approvals` | 0 | 80 KB | (옛 /workspace 화면의 승인 기록). 11-10에 화면을 지운 뒤 부르는 곳이 없음 |
| `sojafit_agent.analysis_events` | 14 | 88 KB | 내용 없이 요청 · 단계별 지연만 남기는 운영 기록(Langfuse trace id 포함) |
| `sojafit_agent.analysis_usage` | 2 | 56 KB | 사용자 · UTC 날짜별 LLM 호출 예약 비용(USD) · 예약 토큰 · 호출 간격. 일일 한도 판단 |
| `sojafit_agent.analysis_service_usage` | 1 | 24 KB | UTC 날짜별 서비스 전체 예약 토큰. 서비스 일일 한도 판단 |
| `sojafit_agent.store` | 0 | 56 KB | LangGraph Store(사용자 사실 3칸 장기 기억). 라이브러리가 만드는 표 |
| `sojafit_agent.store_vectors` | 0 | 16 KB | LangGraph Store의 의미 검색 색인(vector 1024). 라이브러리가 만드는 표 |

## `public.users`

- **목적**: 계정. 비밀번호 계정, Google 가입 계정(표식 해시), 로컬 데모 버튼 계정, 관리자가 모두 이 표 하나
- **쓰는 코드**: backend/auth.py (signup · google_signup · provision · admin_set_active · deactivate_admin · delete_account · delete_provisioned_user)
- **행 수 / 크기**: 5행 / 48 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL |  | 계정 번호(내부 키) |
| `login_id` | character varying(100) | NOT NULL |  | 로그인 이메일(소문자). 구글 가입도 같은 칸에 이메일 저장 |
| `password_hash` | character varying(255) | NOT NULL |  | scrypt 해시. Google 전용은 'google-login-only', 로컬 데모 버튼은 'demo-button-login-only' 표식(비밀번호 로그인 불가) |
| `display_name` | character varying(100) | NULL |  | 표시 이름(코드 · 화면 0건 사용, 모두 NULL) |
| `is_active` | boolean | NOT NULL | true | 비활성이면 로그인 · 세션 불가 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 가입 시각 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 수정 시각 |
| `role` | text | NOT NULL | 'user'::text | admin | user |

| 제약 | 종류 | 정의 |
|---|---|---|
| `users_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['admin'::text, 'user'::text])))` |
| `users_pkey` | PK | `PRIMARY KEY (id)` |
| `users_login_id_key` | UNIQUE | `UNIQUE (login_id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `users_login_id_key` | `btree (login_id)` | 16 KB | 40 |

## `public.auth_sessions`

- **목적**: 로그인 세션. 쿠키 토큰의 SHA-256 해시만 저장(원문 없음). 절대 8시간, 유휴 2시간(11-10 변경)
- **쓰는 코드**: backend/auth.py (authenticate · demo_session · google_session · current_user · logout)
- **행 수 / 크기**: 10행 / 56 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `token_hash` | character(64) | NOT NULL |  | 세션 토큰의 SHA-256(원문 저장 안 함) |
| `user_id` | bigint | NOT NULL |  | 소유 계정 |
| `expires_at` | timestamp with time zone | NOT NULL |  | 절대 만료 시각 |
| `last_seen_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 마지막 사용 시각(유휴 만료 판단) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_sessions_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `auth_sessions_pkey` | PK | `PRIMARY KEY (token_hash)` |

## `public.auth_login_attempts`

- **목적**: 계정(이메일 해시)별 로그인 실패 횟수와 잠금(5회 → 15분)
- **쓰는 코드**: backend/auth.py (authenticate · delete_account)
- **행 수 / 크기**: 0행 / 24 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `login_hash` | character(64) | NOT NULL |  | 이메일의 SHA-256 |
| `failed_count` | integer | NOT NULL | 0 | 집계 창 안의 실패 횟수 |
| `locked_until` | timestamp with time zone | NULL |  | 잠금 끝 시각 |
| `window_started_at` | timestamp with time zone | NULL |  | 15분 집계 창 시작 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_login_attempts_pkey` | PK | `PRIMARY KEY (login_hash)` |

## `public.auth_login_ip_attempts`

- **목적**: IP(해시)별 로그인 실패 횟수와 잠금(15분 30회)
- **쓰는 코드**: backend/auth.py (authenticate)
- **행 수 / 크기**: 0행 / 24 KB
- **비고**: auth_login_attempts와 칸 구성이 거의 같음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `ip_hash` | character(64) | NOT NULL |  | 클라이언트 IP 키의 SHA-256 |
| `failed_count` | integer | NOT NULL | 0 | 실패 횟수 |
| `window_started_at` | timestamp with time zone | NULL |  | 집계 창 시작 |
| `locked_until` | timestamp with time zone | NULL |  | 잠금 끝 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_login_ip_attempts_pkey` | PK | `PRIMARY KEY (ip_hash)` |

## `public.auth_signup_attempts`

- **목적**: IP(해시)별 하루 가입 요청 수. 이메일 가입은 DEMO_MODE=1에서만 열려 운영에서는 쓰이지 않음
- **쓰는 코드**: backend/auth.py (signup)
- **행 수 / 크기**: 1행 / 24 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `ip_hash` | character(64) | NOT NULL |  | IP 키 해시 |
| `day` | date | NOT NULL |  | UTC 날짜 |
| `signup_count` | integer | NOT NULL | 1 | 그날 가입 요청 수(상한 3) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_signup_attempts_signup_count_check` | CHECK | `CHECK ((signup_count >= 1))` |
| `auth_signup_attempts_pkey` | PK | `PRIMARY KEY (ip_hash, day)` |

## `public.auth_google_states`

- **목적**: Google OAuth 시작~콜백 사이의 일회용 상태(state · PKCE verifier · nonce). 10분 뒤 만료
- **쓰는 코드**: backend/auth.py (create_google_state · consume_google_state)
- **행 수 / 크기**: 0행 / 32 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `state_hash` | text | NOT NULL |  | state의 해시 |
| `browser_hash` | text | NOT NULL |  | 브라우저 쿠키 해시(다른 브라우저의 콜백 거부) |
| `verifier` | text | NOT NULL |  | PKCE verifier |
| `nonce` | text | NOT NULL |  | ID 토큰 nonce |
| `expires_at` | timestamp with time zone | NOT NULL |  | 10분 뒤 만료 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_google_states_pkey` | PK | `PRIMARY KEY (state_hash)` |

## `public.auth_google_pending`

- **목적**: Google 계정을 기존 관리자에 연결해 달라는 승인 대기 요청(15분). 11-10 자동 연결 결정으로 콜백이 더 이상 만들지 않음
- **쓰는 코드**: backend/auth.py (request_google_link · approve_google_link · google_pending_email), CLI --approve-google
- **행 수 / 크기**: 1행 / 32 KB
- **비고**: 죽을 표

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `request_id` | text | NOT NULL |  | 승인 요청 번호 |
| `issuer` | text | NOT NULL |  | Google issuer |
| `subject` | text | NOT NULL |  | Google 계정 식별자(sub) |
| `email` | text | NOT NULL |  | 구글이 확인한 이메일 |
| `expires_at` | timestamp with time zone | NOT NULL |  | 15분 뒤 만료 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_google_pending_pkey` | PK | `PRIMARY KEY (request_id)` |

## `public.auth_google_identities`

- **목적**: Google 계정(issuer + subject)과 사용자의 연결. 사용자 1명에 Google 신원 1개
- **쓰는 코드**: backend/auth.py (google_signup · approve_google_link · revoke_google_link · google_session)
- **행 수 / 크기**: 2행 / 48 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `issuer` | text | NOT NULL |  | https://accounts.google.com |
| `subject` | text | NOT NULL |  | Google 계정 식별자(sub) |
| `user_id` | bigint | NOT NULL |  | 연결된 계정(사용자당 1개) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_google_identities_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `auth_google_identities_pkey` | PK | `PRIMARY KEY (issuer, subject)` |
| `auth_google_identities_user_id_key` | UNIQUE | `UNIQUE (user_id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `auth_google_identities_user_id_key` | `btree (user_id)` | 16 KB | 59 |

## `public.projects`

- **목적**: 사용자가 만든 프로젝트(= 회로 하나를 검토하는 작업 단위). 데모 회로 또는 업로드한 넷리스트
- **쓰는 코드**: backend/projects/repository.py (create_upload · create_demo · rename_owned · delete_owned)
- **행 수 / 크기**: 11행 / 48 KB
- **비고**: 소유권 JOIN의 허브

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('projects_id_seq'::regclass) | 프로젝트 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `name` | text | NOT NULL |  | 이름(공백 제거 1~200자) |
| `source_kind` | text | NOT NULL |  | demo | upload |
| `demo_id` | text | NULL |  | 데모 회로 이름(데모일 때만, DB가 6개 이름 목록으로 검사) |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 만든 시각 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 이름 변경 · 대화 활동 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `ck_projects_demo` | CHECK | `CHECK ((((source_kind = 'demo'::text) AND (demo_id IS NOT NULL) AND (demo_id = ANY (ARRAY['breadboard_supply'::text, 'mosfet_driv…` |
| `ck_projects_name` | CHECK | `CHECK (((name = btrim(name)) AND ((char_length(name) >= 1) AND (char_length(name) <= 200))))` |
| `ck_projects_source_kind` | CHECK | `CHECK ((source_kind = ANY (ARRAY['demo'::text, 'upload'::text])))` |
| `fk_projects_user` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `pk_projects` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `ix_projects_user_updated` | `btree (user_id, updated_at DESC, id DESC)` | 16 KB | 33 |

## `public.circuits`

- **목적**: 프로젝트의 정규화된 회로(부품 · 연결). 넷리스트 원문은 저장하지 않음. 프로젝트와 1:1
- **쓰는 코드**: backend/projects/repository.py (create_upload · create_demo)
- **행 수 / 크기**: 11행 / 112 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `project_id` | bigint | NOT NULL |  | 프로젝트(1:1, 키) |
| `connections` | jsonb | NOT NULL |  | 정규화한 회로(부품 · 넷 JSON) |
| `source_sha256` | text | NOT NULL |  | 원본 넷리스트 SHA-256(원문은 저장 안 함) |
| `parser_version` | text | NOT NULL |  | 회로 변환기 버전 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP |  |

| 제약 | 종류 | 정의 |
|---|---|---|
| `ck_circuits_connections` | CHECK | `CHECK ((jsonb_typeof(connections) = 'object'::text))` |
| `ck_circuits_parser_version` | CHECK | `CHECK ((char_length(btrim(parser_version)) > 0))` |
| `ck_circuits_sha256` | CHECK | `CHECK ((source_sha256 ~ '^[0-9a-f]{64}$'::text))` |
| `fk_circuits_project` | FK | `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE` |
| `pk_circuits` | PK | `PRIMARY KEY (project_id)` |

## `public.threads`

- **목적**: 프로젝트 안의 대화(화면의 '새 대화'). 질문 · 실행의 묶음
- **쓰는 코드**: backend/conversations/repository.py (create_thread)
- **행 수 / 크기**: 10행 / 40 KB
- **비고**: 분석 서비스의 sojafit_agent.threads와 같은 UUID

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | 대화 UUID(URL에 노출) |
| `project_id` | bigint | NOT NULL |  | 소속 프로젝트 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 만든 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_project_id_fkey` | FK | `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE` |
| `threads_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `ix_threads_project` | `btree (project_id)` | 16 KB | 265 |

## `public.runs`

- **목적**: 질문 한 번의 실행과 공개 결과(safe_result). GET /api/runs/{id}의 응답 원본
- **쓰는 코드**: backend/conversations/repository.py (start · finish · resume)
- **행 수 / 크기**: 10행 / 112 KB
- **비고**: 대화당 진행 중 run은 1개(부분 고유 인덱스)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | run UUID(URL에 노출) |
| `thread_id` | uuid | NOT NULL |  | 소속 대화 |
| `status` | text | NOT NULL |  | running | requires_input | completed | refused | failed |
| `safe_result` | jsonb | NULL |  | 공개 결과 JSON(answer · question_type · price_parts · interrupt · judgement · evidence). 모양을 DB CHECK 함수가 재귀 검사 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시작 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 마지막 변경 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `runs_safe_result_check` | CHECK | `CHECK (((safe_result IS NULL) OR (conversation_json_matches(safe_result, '{"answer": "string", "evidence": {"$array": {"row": "st…` |
| `runs_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['running'::text, 'requires_input'::text, 'completed'::text, 'refused'::text, 'failed'::text])))` |
| `runs_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE` |
| `runs_pkey` | PK | `PRIMARY KEY (id)` |
| `runs_id_thread_id_key` | UNIQUE | `UNIQUE (id, thread_id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `ix_runs_active` | `btree (thread_id) WHERE (status = ANY (ARRAY['running'::text, 'requires_input'::text]))` | 16 KB | 18 |
| `ix_runs_thread` | `btree (thread_id)` | 16 KB | 55 |
| `runs_id_thread_id_key` | `btree (id, thread_id)` | 16 KB | 41 |

## `public.messages`

- **목적**: 화면에 보이는 대화 기록(사용자 질문 · 어시스턴트 답)
- **쓰는 코드**: backend/conversations/repository.py (start · finish)
- **행 수 / 크기**: 18행 / 96 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('messages_id_seq'::regclass) | 메시지 번호 |
| `thread_id` | uuid | NOT NULL |  | 대화 |
| `run_id` | uuid | NOT NULL |  | run(대화와 함께 복합 FK) |
| `role` | text | NOT NULL |  | user | assistant |
| `content` | text | NOT NULL |  | 질문 · 답 글 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `messages_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text])))` |
| `messages_run_id_thread_id_fkey` | FK | `FOREIGN KEY (run_id, thread_id) REFERENCES runs(id, thread_id) ON DELETE CASCADE` |
| `messages_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE` |
| `messages_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `ix_messages_run` | `btree (run_id)` | 16 KB | 8 |
| `ix_messages_thread` | `btree (thread_id)` | 16 KB | 110 |

## `public.approvals`

- **목적**: 사람이 후보 하나를 승인한 기록. 승인 시점의 판정 스냅샷(JSON) 보관. 메시지당 1건
- **쓰는 코드**: backend/services/quote.py (approve)
- **행 수 / 크기**: 3행 / 112 KB
- **비고**: snapshot이 3곳에 같은 모양으로 복제됨

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approvals_id_seq'::regclass) | 승인 번호 |
| `user_id` | bigint | NOT NULL |  | 승인한 사용자 |
| `message_id` | bigint | NOT NULL |  | 승인한 어시스턴트 메시지(고유, 메시지당 1건) |
| `snapshot` | jsonb | NOT NULL |  | {answer, question_type, candidate(후보 판정 + part_number), evidence} JSON. 가격 · 재고 키는 CHECK 함수가 거부 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 승인 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approvals_snapshot_check` | CHECK | `CHECK (((jsonb_typeof(snapshot) = 'object'::text) AND (NOT quote_snapshot_has_forbidden_key(snapshot))))` |
| `approvals_message_id_fkey` | FK | `FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE` |
| `approvals_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `approvals_pkey` | PK | `PRIMARY KEY (id)` |
| `approvals_id_user_id_key` | UNIQUE | `UNIQUE (id, user_id)` |
| `approvals_message_id_key` | UNIQUE | `UNIQUE (message_id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `approvals_id_user_id_key` | `btree (id, user_id)` | 16 KB | 23 |
| `approvals_message_id_key` | `btree (message_id)` | 16 KB | 174 |
| `ix_approvals_user` | `btree (user_id)` | 16 KB | 5 |

## `public.quotes`

- **목적**: 승인에서 만든 가격 없는 견적(품번 · 수량). 승인당 UNIQUE는 없어 한 승인에서 여러 건 가능
- **쓰는 코드**: backend/services/quote.py (create_quote)
- **행 수 / 크기**: 3행 / 64 KB
- **비고**: snapshot 칸을 아무도 읽지 않음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('quotes_id_seq'::regclass) | 견적 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(승인당 UNIQUE 없음) |
| `part_number` | text | NOT NULL |  | 견적 품번(공백 없는 영문 · 숫자 · . _ + / -, CHECK) |
| `quantity` | integer | NOT NULL |  | 수량 1~100000 |
| `snapshot` | jsonb | NOT NULL |  | 승인 스냅샷의 복사본(읽는 코드 없음) |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 저장 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `quotes_part_number_check` | CHECK | `CHECK ((part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'::text))` |
| `quotes_quantity_check` | CHECK | `CHECK (((quantity >= 1) AND (quantity <= 100000)))` |
| `quotes_snapshot_check` | CHECK | `CHECK (((jsonb_typeof(snapshot) = 'object'::text) AND (NOT quote_snapshot_has_forbidden_key(snapshot))))` |
| `quotes_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `quotes_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `quotes_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `ix_quotes_approval` | `btree (approval_id)` | 16 KB | 13 |
| `ix_quotes_user` | `btree (user_id)` | 16 KB | 9 |

## `public.approved_cases`

- **목적**: 화면의 '승인 사례' 목록. 승인과 같이 만들고 사용자가 지울 수 있음. 새 분석에 기억으로 넘기지 않음(11-09 중단)
- **쓰는 코드**: backend/services/quote.py (approve · list_cases · delete_case)
- **행 수 / 크기**: 3행 / 64 KB
- **비고**: snapshot 중복

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approved_cases_id_seq'::regcla… | 사례 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(고유) |
| `snapshot` | jsonb | NOT NULL |  | 승인 스냅샷의 복사본. 목록은 candidate.part · verdict만 읽음 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approved_cases_snapshot_check` | CHECK | `CHECK (((jsonb_typeof(snapshot) = 'object'::text) AND (NOT quote_snapshot_has_forbidden_key(snapshot))))` |
| `approved_cases_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `approved_cases_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `approved_cases_pkey` | PK | `PRIMARY KEY (id)` |
| `approved_cases_approval_id_key` | UNIQUE | `UNIQUE (approval_id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `approved_cases_approval_id_key` | `btree (approval_id)` | 16 KB | 0 |
| `ix_approved_cases_user` | `btree (user_id)` | 16 KB | 11 |

## `sojafit_agent.circuits`

- **목적**: 분석 서비스용 회로 사본. 대화 하나당 1행(id = 대화 UUID), public.circuits.connections의 복사본
- **쓰는 코드**: backend/conversations/memory_service.py (ensure_thread · delete_analysis_threads)
- **행 수 / 크기**: 10행 / 168 KB
- **비고**: 중복 저장. netlist 칸은 운영에서 전부 빈 글자

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | 대화 UUID와 같은 값 |
| `user_id` | bigint | NOT NULL |  | 소유자(RESTRICT) |
| `filename` | text | NOT NULL |  | 넷리스트 파일 이름 · 프로젝트 이름 |
| `netlist` | text | NOT NULL |  | 넷리스트 원문(React 경로는 빈 글자만 넣음) |
| `connections` | jsonb | NOT NULL |  | public.circuits.connections의 복사본 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `circuits_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `circuits_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `agent_circuits_owner` | `btree (user_id, created_at DESC)` | 16 KB | 43 |

## `sojafit_agent.threads`

- **목적**: 분석 서비스의 대화 상태 기계(version · retries · status · 현재 입력 기록). id = public.threads.id
- **쓰는 코드**: backend/conversations/memory_service.py (ensure_thread · message · resume · _invoke · _finish)
- **행 수 / 크기**: 10행 / 48 KB
- **비고**: public.threads와 FK 없이 같은 UUID로만 연결

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | public.threads.id와 같은 UUID |
| `user_id` | bigint | NOT NULL |  | 소유자(RESTRICT) |
| `circuit_id` | uuid | NOT NULL |  | 분석용 회로 사본(id와 같은 값) |
| `target` | text | NOT NULL |  | 교체 대상 부품 참조(예: D1) |
| `version` | integer | NOT NULL | 0 | 질문 차수(새 질문마다 +1) |
| `retries` | integer | NOT NULL | 0 | 같은 질문의 재시도 횟수(상한 2) |
| `status` | text | NOT NULL | 'NEW'::text | NEW | RUNNING | WAITING | DONE | FAILED |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |
| `input_record` | jsonb | NULL |  | 현재 차수의 원문 질문 · 조건 · 재개 답(JSON) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['NEW'::text, 'RUNNING'::text, 'WAITING'::text, 'DONE'::text, 'FAILED'::text])))` |
| `threads_circuit_id_fkey` | FK | `FOREIGN KEY (circuit_id) REFERENCES sojafit_agent.circuits(id) ON DELETE RESTRICT` |
| `threads_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT` |
| `threads_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `agent_threads_owner` | `btree (user_id, created_at DESC)` | 16 KB | 7 |

## `sojafit_agent.messages`

- **목적**: 분석 문맥용 사용자 입력(이전 입력 최대 12개를 프롬프트에 붙임)과 어시스턴트 답
- **쓰는 코드**: backend/conversations/memory_service.py (message · resume · _finish)
- **행 수 / 크기**: 26행 / 104 KB
- **비고**: public.messages와 역할이 갈려 있음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL |  | 번호 |
| `thread_id` | uuid | NOT NULL |  | 분석 대화 |
| `role` | text | NOT NULL |  | user | assistant |
| `checkpoint_id` | text | NULL |  | 그 답을 만든 LangGraph 체크포인트(중복 방지 고유 색인) |
| `content` | text | NOT NULL |  | 사용자는 '사용 조건: …' 접두 + 질문 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `messages_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text])))` |
| `messages_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE` |
| `messages_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `agent_messages_checkpoint` | `btree (thread_id, checkpoint_id) WHERE (checkpoint_id IS NOT NULL)` | 16 KB | 67 |
| `agent_messages_thread` | `btree (thread_id, id)` | 16 KB | 94 |

## `sojafit_agent.approvals`

- **목적**: (옛 /workspace 화면의 승인 기록). 11-10에 화면을 지운 뒤 부르는 곳이 없음
- **쓰는 코드**: backend/conversations/memory_service.py (_approve, 호출 없음)
- **행 수 / 크기**: 0행 / 80 KB
- **비고**: 죽은 표, 0행

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `thread_id` | uuid | NOT NULL |  | 분석 대화 |
| `version` | integer | NOT NULL |  | 차수 |
| `snapshot` | jsonb | NOT NULL |  | 승인 JSON |
| `approved_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |
| `memory_status` | text | NOT NULL | 'active'::text | active | revoked | deleted(옛 기억 표식) |
| `correction` | text | NOT NULL | ''::text | 정정 메모 |
| `memory_updated_at` | timestamp with time zone | NULL |  | 표식 변경 시각(코드 참조 0) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approvals_memory_status_check` | CHECK | `CHECK ((memory_status = ANY (ARRAY['active'::text, 'revoked'::text, 'deleted'::text])))` |
| `approvals_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE` |
| `approvals_pkey` | PK | `PRIMARY KEY (thread_id, version)` |

## `sojafit_agent.analysis_events`

- **목적**: 내용 없이 요청 · 단계별 지연만 남기는 운영 기록(Langfuse trace id 포함)
- **쓰는 코드**: backend/conversations/memory_service.py (_record_event)
- **행 수 / 크기**: 14행 / 88 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | UUID |
| `thread_id` | uuid | NOT NULL |  | 분석 대화 |
| `version` | integer | NOT NULL |  | 질문 차수 |
| `request_id` | text | NOT NULL |  | X-Request-ID |
| `mode` | text | NOT NULL |  | real | demo |
| `status` | text | NOT NULL |  | 결과 상태 |
| `elapsed_ms` | integer | NOT NULL |  | 사람 대기 제외 실행 시간 |
| `stages` | jsonb | NOT NULL |  | 단계별 ms(내용 없음) |
| `trace_id` | text | NOT NULL |  | Langfuse trace id |
| `trace_delivery` | text | NOT NULL |  | queued 등 전달 상태 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_events_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE` |
| `analysis_events_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `agent_events_thread` | `btree (thread_id, created_at DESC)` | 16 KB | 88 |

## `sojafit_agent.analysis_usage`

- **목적**: 사용자 · UTC 날짜별 LLM 호출 예약 비용(USD) · 예약 토큰 · 호출 간격. 일일 한도 판단
- **쓰는 코드**: backend/conversations/memory_service.py (_budget · _token_room)
- **행 수 / 크기**: 2행 / 56 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `user_id` | bigint | NOT NULL |  | 사용자 |
| `day` | date | NOT NULL |  | UTC 날짜 |
| `reserved_usd` | numeric(16,10) | NOT NULL | 0 | 예약 비용(청구액 아님, 환불 안 함) |
| `attempts` | integer | NOT NULL | 1 | 그날 시도 수 |
| `next_allowed` | timestamp with time zone | NOT NULL |  | 다음 허용 시각(호출 간격) |
| `reserved_tokens` | bigint | NOT NULL | 0 | 예약 토큰(상한 사용자 200,000 → 운영 1,000,000) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_usage_reserved_tokens_check` | CHECK | `CHECK ((reserved_tokens >= 0))` |
| `analysis_usage_reserved_usd_check` | CHECK | `CHECK ((reserved_usd >= (0)::numeric))` |
| `analysis_usage_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `analysis_usage_pkey` | PK | `PRIMARY KEY (user_id, day)` |

## `sojafit_agent.analysis_service_usage`

- **목적**: UTC 날짜별 서비스 전체 예약 토큰. 서비스 일일 한도 판단
- **쓰는 코드**: backend/conversations/memory_service.py (_budget)
- **행 수 / 크기**: 1행 / 24 KB

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `day` | date | NOT NULL |  | UTC 날짜 |
| `reserved_tokens` | bigint | NOT NULL | 0 | 서비스 전체 예약 토큰(상한 2,000,000) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_service_usage_reserved_tokens_check` | CHECK | `CHECK ((reserved_tokens >= 0))` |
| `analysis_service_usage_pkey` | PK | `PRIMARY KEY (day)` |

## `sojafit_agent.store`

- **목적**: LangGraph Store(사용자 사실 3칸 장기 기억). 라이브러리가 만드는 표
- **쓰는 코드**: LangGraph PostgresStore · memory_service._delete_store
- **행 수 / 크기**: 0행 / 56 KB
- **비고**: 라이브러리 소유 — 스키마는 건드리지 않음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `prefix` | text | NOT NULL |  | namespace(예: (user_id, 'profile')) |
| `key` | text | NOT NULL |  | 키 |
| `value` | jsonb | NOT NULL |  | 값 JSON |
| `created_at` | timestamp with time zone | NULL | CURRENT_TIMESTAMP |  |
| `updated_at` | timestamp with time zone | NULL | CURRENT_TIMESTAMP |  |
| `expires_at` | timestamp with time zone | NULL |  | 만료 |
| `ttl_minutes` | integer | NULL |  | 수명(분) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `store_pkey` | PK | `PRIMARY KEY (prefix, key)` |

| 인덱스 | 정의 | 크기 | 사용 횟수 |
|---|---|---|---|
| `idx_store_expires_at` | `btree (expires_at) WHERE (expires_at IS NOT NULL)` | 8 KB | 0 |
| `store_prefix_idx` | `btree (prefix text_pattern_ops)` | 16 KB | 157 |

## `sojafit_agent.store_vectors`

- **목적**: LangGraph Store의 의미 검색 색인(vector 1024). 라이브러리가 만드는 표
- **쓰는 코드**: LangGraph PostgresStore
- **행 수 / 크기**: 0행 / 16 KB
- **비고**: 라이브러리 소유

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `prefix` | text | NOT NULL |  | namespace |
| `key` | text | NOT NULL |  | 키 |
| `field_name` | text | NOT NULL |  | 색인한 칸 |
| `embedding` | vector(1024) | NULL |  | vector(1024) |
| `created_at` | timestamp with time zone | NULL | CURRENT_TIMESTAMP |  |
| `updated_at` | timestamp with time zone | NULL | CURRENT_TIMESTAMP |  |

| 제약 | 종류 | 정의 |
|---|---|---|
| `store_vectors_prefix_key_fkey` | FK | `FOREIGN KEY (prefix, key) REFERENCES sojafit_agent.store(prefix, key) ON DELETE CASCADE` |
| `store_vectors_pkey` | PK | `PRIMARY KEY (prefix, key, field_name)` |

## 함수

| 스키마.함수 | 하는 일 |
|---|---|
| `public.conversation_json_matches` | `runs.safe_result` JSON의 모양을 재귀로 검사(CHECK가 부름) |
| `public.quote_snapshot_has_forbidden_key` | 승인 · 견적 스냅샷에 가격 · 재고 키가 있으면 거부(CHECK가 부름) |
| `public.rls_auto_enable` | Supabase 기본 함수(표 생성 시 RLS 자동 켜기) |
| `sojafit_agent.purge_inactive_projects` | 60일 지난 프로젝트 · 분석 기록 청소(앱이 새 분석 시작 때 부름) |
| `sojafit_agent.purge_log_records` | 30일 지난 운영 기록 청소 |
