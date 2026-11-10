# 목표(to-be) 서비스 표 정의서

- 기준: [`db/020_service_baseline.sql`](../../020_service_baseline.sql)을 빈 Postgres(16 · 17)에 적용한 결과를 `pg_catalog`에서 자동 생성했다(칸 · 타입 · 키 · 인덱스). 의미 · 차이는 손으로 적었다.
- 상태: **정운 확정 전 초안**. "필수 + 권장" 단계(P1 + P2)가 끝난 뒤의 구조다. 단계 구분은 [`../REDESIGN.md`](../REDESIGN.md), 근거와 선택지는 [`design.md`](design.md), 그림은 [`erd.md`](erd.md).
- 현재 구조와의 비교는 [`../as-is/tables.md`](../as-is/tables.md). 범위 밖(코퍼스 4표 · LangGraph 표)은 그대로다.

| 스키마.표 | 목적 | as-is와의 차이 |
|---|---|---|
| `public.users` | 계정 | display_name 삭제(코드 · 화면 0건 사용) |
| `public.auth_sessions` | 로그인 세션 | 인덱스 2개 추가: `ix_auth_sessions_user`(계정 삭제 FK 검사) · `ix_auth_sessions_expires`(만료 세션 청소) |
| `public.auth_login_attempts` | 계정별 로그인 실패 · 잠금 | 변경 없음 |
| `public.auth_login_ip_attempts` | IP별 로그인 실패 · 잠금 | 변경 없음(두 표를 하나로 합치는 안은 보류) |
| `public.auth_signup_attempts` | IP별 하루 가입 요청 수(데모 모드 전용) | 변경 없음(이메일 가입 경로를 지울 때 같이 삭제 — 보류) |
| `public.auth_google_states` | Google OAuth 일회용 상태 | 변경 없음 |
| `public.auth_google_identities` | Google 신원 ↔ 사용자 연결 | 변경 없음 |
| `public.projects` | 프로젝트 | `ck_projects_demo`를 "데모일 때만 demo_id"로 단순화(6개 이름 목록 제거) |
| `public.circuits` | 프로젝트의 정규화 회로(1:1) | 변경 없음. **회로 연결의 유일한 사본**이 된다(분석용 사본 삭제) |
| `public.threads` | 프로젝트 안의 대화 | 변경 없음. `sojafit_agent.threads`가 이 표를 FK로 참조하고, 행 삭제 시 체크포인트 삭제 트리거가 붙음 |
| `public.runs` | 질문 한 번의 실행과 공개 결과 | `ck_runs_safe_result` 단순화(재귀 검사 함수 `conversation_json_matches` 삭제). 저장 데이터 · API 모양은 그대로 |
| `public.messages` | 화면 대화 기록 | 변경 없음 |
| `public.approvals` | 사람의 후보 승인(스냅샷의 유일한 사본) | `candidate_part` · `verdict` · `part_number` 칸 3개와 CHECK 3개 추가. 가격 키 검사 함수는 이 표에만 건다 |
| `public.quotes` | 승인에서 만든 가격 없는 견적 | `snapshot` 삭제(아무도 읽지 않던 복사본) |
| `public.approved_cases` | 화면의 승인 사례 목록(사용자가 지울 수 있는 표시 행) | `snapshot` 삭제. 목록은 approvals를 JOIN해서 읽음 |
| `public.app_migrations` | 마이그레이션 적용 이력(우리 것) | **신규**. Supabase 도구의 `supabase_migrations.schema_migrations`(초기 5건)와 별개 |
| `sojafit_agent.threads` | 분석 서비스의 대화 상태 기계 | `id`가 `public.threads(id)` FK(CASCADE), `circuit_id` 삭제, `user_id` FK RESTRICT → CASCADE |
| `sojafit_agent.messages` | 분석 문맥용 사용자 입력 + 어시스턴트 답 | 변경 없음(분석 코드가 문맥으로 읽어서 합치지 않음) |
| `sojafit_agent.analysis_events` | 내용 없는 운영 기록 | 변경 없음 |
| `sojafit_agent.analysis_usage` | 사용자 · 날짜별 LLM 예약 사용량 | 변경 없음 |
| `sojafit_agent.analysis_service_usage` | 서비스 전체 날짜별 예약 토큰 | 변경 없음 |
| ~~`public.auth_google_pending`~~ | (삭제) | 승인 대기 표(11-10 자동 연결 결정으로 안 씀, 이메일 평문 포함) — 코드 제거 뒤 `migrate_prod_2b` |
| ~~`sojafit_agent.circuits`~~ | (삭제) | 분석용 회로 사본(connections 복사 + 항상 빈 netlist) — `public.circuits`를 읽는다 |
| ~~`sojafit_agent.approvals`~~ | (삭제) | 옛 /workspace 승인 경로(0행) — 코드 제거 뒤 |

라이브러리가 만드는 `sojafit_agent.store` · `store_vectors` · `checkpoint*`는 이 표 목록에 없고 건드리지 않는다.


## `public.users`

- **목적**: 계정
- **as-is와의 차이**: display_name 삭제(코드 · 화면 0건 사용)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL |  | 계정 번호(내부 키) |
| `login_id` | character varying(100) | NOT NULL |  | 로그인 이메일(소문자). 구글 가입도 같은 칸에 이메일 저장 |
| `password_hash` | character varying(255) | NOT NULL |  | scrypt 해시. Google 전용은 'google-login-only', 로컬 데모 버튼은 'demo-button-login-only' 표식(비밀번호 로그인 불가) |
| `is_active` | boolean | NOT NULL | true | 비활성이면 로그인 · 세션 불가 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 가입 시각 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 수정 시각 |
| `role` | text | NOT NULL | 'user'::text | admin | user |

| 제약 | 종류 | 정의 |
|---|---|---|
| `users_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['admin'::text, 'user'::text])))` |
| `users_pkey` | PK | `PRIMARY KEY (id)` |
| `users_login_id_key` | UNIQUE | `UNIQUE (login_id)` |

| 인덱스 | 정의 |
|---|---|
| `users_login_id_key` | `UNIQUE btree (login_id)` |

## `public.auth_sessions`

- **목적**: 로그인 세션
- **as-is와의 차이**: 인덱스 2개 추가: `ix_auth_sessions_user`(계정 삭제 FK 검사) · `ix_auth_sessions_expires`(만료 세션 청소)

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

| 인덱스 | 정의 |
|---|---|
| `ix_auth_sessions_expires` | `btree (expires_at)` |
| `ix_auth_sessions_user` | `btree (user_id)` |

## `public.auth_login_attempts`

- **목적**: 계정별 로그인 실패 · 잠금
- **as-is와의 차이**: 변경 없음

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

- **목적**: IP별 로그인 실패 · 잠금
- **as-is와의 차이**: 변경 없음(두 표를 하나로 합치는 안은 보류)

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

- **목적**: IP별 하루 가입 요청 수(데모 모드 전용)
- **as-is와의 차이**: 변경 없음(이메일 가입 경로를 지울 때 같이 삭제 — 보류)

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

- **목적**: Google OAuth 일회용 상태
- **as-is와의 차이**: 변경 없음

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

## `public.auth_google_identities`

- **목적**: Google 신원 ↔ 사용자 연결
- **as-is와의 차이**: 변경 없음

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

| 인덱스 | 정의 |
|---|---|
| `auth_google_identities_user_id_key` | `UNIQUE btree (user_id)` |

## `public.projects`

- **목적**: 프로젝트
- **as-is와의 차이**: `ck_projects_demo`를 "데모일 때만 demo_id"로 단순화(6개 이름 목록 제거)

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
| `ck_projects_demo` | CHECK | `CHECK (((source_kind = 'demo'::text) = (demo_id IS NOT NULL)))` |
| `ck_projects_name` | CHECK | `CHECK (((name = btrim(name)) AND ((char_length(name) >= 1) AND (char_length(name) <= 200))))` |
| `ck_projects_source_kind` | CHECK | `CHECK ((source_kind = ANY (ARRAY['demo'::text, 'upload'::text])))` |
| `fk_projects_user` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `pk_projects` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 |
|---|---|
| `ix_projects_user_updated` | `btree (user_id, updated_at DESC, id DESC)` |

## `public.circuits`

- **목적**: 프로젝트의 정규화 회로(1:1)
- **as-is와의 차이**: 변경 없음. **회로 연결의 유일한 사본**이 된다(분석용 사본 삭제)

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

- **목적**: 프로젝트 안의 대화
- **as-is와의 차이**: 변경 없음. `sojafit_agent.threads`가 이 표를 FK로 참조하고, 행 삭제 시 체크포인트 삭제 트리거가 붙음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | 대화 UUID(URL에 노출) |
| `project_id` | bigint | NOT NULL |  | 소속 프로젝트 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 만든 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_project_id_fkey` | FK | `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE` |
| `threads_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 |
|---|---|
| `ix_threads_project` | `btree (project_id)` |

## `public.runs`

- **목적**: 질문 한 번의 실행과 공개 결과
- **as-is와의 차이**: `ck_runs_safe_result` 단순화(재귀 검사 함수 `conversation_json_matches` 삭제). 저장 데이터 · API 모양은 그대로

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
| `ck_runs_safe_result` | CHECK | `CHECK (((safe_result IS NULL) OR ((jsonb_typeof(safe_result) = 'object'::text) AND (safe_result ?& ARRAY['answer'::text, 'questio…` |
| `runs_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['running'::text, 'requires_input'::text, 'completed'::text, 'refused'::text, 'failed'::text])))` |
| `runs_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE` |
| `runs_pkey` | PK | `PRIMARY KEY (id)` |
| `runs_id_thread_id_key` | UNIQUE | `UNIQUE (id, thread_id)` |

| 인덱스 | 정의 |
|---|---|
| `ix_runs_active` | `UNIQUE btree (thread_id) WHERE (status = ANY (ARRAY['running'::text, 'requires_input'::text]))` |
| `ix_runs_thread` | `btree (thread_id)` |
| `runs_id_thread_id_key` | `UNIQUE btree (id, thread_id)` |

## `public.messages`

- **목적**: 화면 대화 기록
- **as-is와의 차이**: 변경 없음

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

| 인덱스 | 정의 |
|---|---|
| `ix_messages_run` | `btree (run_id)` |
| `ix_messages_thread` | `btree (thread_id)` |

## `public.approvals`

- **목적**: 사람의 후보 승인(스냅샷의 유일한 사본)
- **as-is와의 차이**: `candidate_part` · `verdict` · `part_number` 칸 3개와 CHECK 3개 추가. 가격 키 검사 함수는 이 표에만 건다

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approvals_id_seq'::regclass) | 승인 번호 |
| `user_id` | bigint | NOT NULL |  | 승인한 사용자 |
| `message_id` | bigint | NOT NULL |  | 승인한 어시스턴트 메시지(고유, 메시지당 1건) |
| `candidate_part` | text | NOT NULL |  | 승인한 후보 품번의 **표시 이름**(판정 결과가 보여 준 그대로. 예 'TSC 1N4007G'). 승인 JSON에서 꺼낸 칸 |
| `verdict` | text | NOT NULL |  | 승인한 판정 IDENTICAL | SPEC_EQUIVALENT | ROLE_SUFFICIENT. 승인 JSON에서 꺼낸 칸 |
| `part_number` | text | NOT NULL |  | 견적용 **식별 품번**: 제조사 이름(TSC 등)을 떼고 남은 공백(주문 코드)은 '-'(예 '1N4007G', '1N4148-A0G'). 승인 JSON에서 꺼낸 칸 |
| `snapshot` | jsonb | NOT NULL |  | 승인 시점의 {answer, question_type, candidate, evidence} 증빙 JSON. **스냅샷의 유일한 사본**. 가격 · 재고 키는 CHECK 함수가 거부 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 승인 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approvals_snapshot_check` | CHECK | `CHECK (((jsonb_typeof(snapshot) = 'object'::text) AND (NOT quote_snapshot_has_forbidden_key(snapshot))))` |
| `ck_approvals_candidate_part` | CHECK | `CHECK (((char_length(candidate_part) >= 1) AND (char_length(candidate_part) <= 100)))` |
| `ck_approvals_part_number` | CHECK | `CHECK ((part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'::text))` |
| `ck_approvals_verdict` | CHECK | `CHECK ((verdict = ANY (ARRAY['IDENTICAL'::text, 'SPEC_EQUIVALENT'::text, 'ROLE_SUFFICIENT'::text])))` |
| `approvals_message_id_fkey` | FK | `FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE` |
| `approvals_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `approvals_pkey` | PK | `PRIMARY KEY (id)` |
| `approvals_id_user_id_key` | UNIQUE | `UNIQUE (id, user_id)` |
| `approvals_message_id_key` | UNIQUE | `UNIQUE (message_id)` |

| 인덱스 | 정의 |
|---|---|
| `approvals_id_user_id_key` | `UNIQUE btree (id, user_id)` |
| `approvals_message_id_key` | `UNIQUE btree (message_id)` |
| `ix_approvals_user` | `btree (user_id)` |

## `public.quotes`

- **목적**: 승인에서 만든 가격 없는 견적
- **as-is와의 차이**: `snapshot` 삭제(아무도 읽지 않던 복사본)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('quotes_id_seq'::regclass) | 견적 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(승인 하나에서 견적 여러 건 가능: 승인당 UNIQUE 없음) |
| `part_number` | text | NOT NULL |  | 견적 품번(공백 없는 영문 · 숫자 · . _ + / -, CHECK) |
| `quantity` | integer | NOT NULL |  | 수량 1~100000 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 저장 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `quotes_part_number_check` | CHECK | `CHECK ((part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'::text))` |
| `quotes_quantity_check` | CHECK | `CHECK (((quantity >= 1) AND (quantity <= 100000)))` |
| `quotes_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `quotes_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `quotes_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 |
|---|---|
| `ix_quotes_approval` | `btree (approval_id)` |
| `ix_quotes_user` | `btree (user_id)` |

## `public.approved_cases`

- **목적**: 화면의 승인 사례 목록(사용자가 지울 수 있는 표시 행)
- **as-is와의 차이**: `snapshot` 삭제. 목록은 approvals를 JOIN해서 읽음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approved_cases_id_seq'::regcla… | 사례 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(고유). 후보 이름 · 판정은 approvals에서 읽는다 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approved_cases_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `approved_cases_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `approved_cases_pkey` | PK | `PRIMARY KEY (id)` |
| `approved_cases_approval_id_key` | UNIQUE | `UNIQUE (approval_id)` |

| 인덱스 | 정의 |
|---|---|
| `approved_cases_approval_id_key` | `UNIQUE btree (approval_id)` |
| `ix_approved_cases_user` | `btree (user_id)` |

## `public.app_migrations`

- **목적**: 마이그레이션 적용 이력(우리 것)
- **as-is와의 차이**: **신규**. Supabase 도구의 `supabase_migrations.schema_migrations`(초기 5건)와 별개

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `version` | text | NOT NULL |  | 적용한 변경의 이름 |
| `applied_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 적용 시각 |
| `note` | text | NOT NULL | ''::text | 한 줄 설명 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `app_migrations_pkey` | PK | `PRIMARY KEY (version)` |

## `sojafit_agent.threads`

- **목적**: 분석 서비스의 대화 상태 기계
- **as-is와의 차이**: `id`가 `public.threads(id)` FK(CASCADE), `circuit_id` 삭제, `user_id` FK RESTRICT → CASCADE

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | **public.threads.id와 같은 UUID이며 FK**(대화를 지우면 같이 지워짐) |
| `user_id` | bigint | NOT NULL |  | 소유자(CASCADE). 소유 조회를 빠르게 하려고 둔 의도된 비정규화 |
| `target` | text | NOT NULL |  | 교체 대상 부품 참조(예: D1) |
| `version` | integer | NOT NULL | 0 | 질문 차수(새 질문마다 +1) |
| `retries` | integer | NOT NULL | 0 | 같은 질문의 재시도 횟수(상한 2) |
| `status` | text | NOT NULL | 'NEW'::text | NEW | RUNNING | WAITING | DONE | FAILED |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |
| `input_record` | jsonb | NULL |  | 현재 차수의 원문 질문 · 조건 · 재개 답(JSON) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['NEW'::text, 'RUNNING'::text, 'WAITING'::text, 'DONE'::text, 'FAILED'::text])))` |
| `fk_agent_threads_thread` | FK | `FOREIGN KEY (id) REFERENCES threads(id) ON DELETE CASCADE` |
| `threads_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `threads_pkey` | PK | `PRIMARY KEY (id)` |

| 인덱스 | 정의 |
|---|---|
| `agent_threads_owner` | `btree (user_id, created_at DESC)` |

## `sojafit_agent.messages`

- **목적**: 분석 문맥용 사용자 입력 + 어시스턴트 답
- **as-is와의 차이**: 변경 없음(분석 코드가 문맥으로 읽어서 합치지 않음)

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

| 인덱스 | 정의 |
|---|---|
| `agent_messages_checkpoint` | `UNIQUE btree (thread_id, checkpoint_id) WHERE (checkpoint_id IS NOT NULL)` |
| `agent_messages_thread` | `btree (thread_id, id)` |

## `sojafit_agent.analysis_events`

- **목적**: 내용 없는 운영 기록
- **as-is와의 차이**: 변경 없음

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

| 인덱스 | 정의 |
|---|---|
| `agent_events_thread` | `btree (thread_id, created_at DESC)` |

## `sojafit_agent.analysis_usage`

- **목적**: 사용자 · 날짜별 LLM 예약 사용량
- **as-is와의 차이**: 변경 없음

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

- **목적**: 서비스 전체 날짜별 예약 토큰
- **as-is와의 차이**: 변경 없음

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `day` | date | NOT NULL |  | UTC 날짜 |
| `reserved_tokens` | bigint | NOT NULL | 0 | 서비스 전체 예약 토큰(상한 2,000,000) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_service_usage_reserved_tokens_check` | CHECK | `CHECK ((reserved_tokens >= 0))` |
| `analysis_service_usage_pkey` | PK | `PRIMARY KEY (day)` |

## 함수 · 트리거

| 이름 | 하는 일 |
|---|---|
| `public.quote_snapshot_has_forbidden_key` | 승인 스냅샷에 가격 · 재고 키가 있으면 거부(`approvals.snapshot` CHECK) |
| `sojafit_agent.purge_thread_checkpoints` + 트리거 `trg_threads_purge_checkpoints`(`public.threads` BEFORE DELETE) | 대화 행이 어떤 경로로 지워져도 FK를 걸 수 없는 LangGraph 체크포인트 3표의 같은 thread 행을 지운다. 표가 없으면 건너뜀 |
| `sojafit_agent.purge_inactive_projects` | 60일 지난 프로젝트 삭제(나머지는 cascade). 옛 137줄 → 약 40줄 |
| `sojafit_agent.purge_log_records` | 30일 지난 운영 기록 + **만료 세션** 청소(세션은 신규) |
