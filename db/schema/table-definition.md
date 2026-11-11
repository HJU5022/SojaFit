# SojaFit DB 표 정의서

<!-- 자동 생성: scripts/db/gen_schema_docs.py. 직접 고치지 않는다(표 설명은 그 파일의 TABLES, 구조는 DB). -->

- 구조(타입 · NULL · 기본값 · 제약 · 인덱스)는 실제 DB에서 읽은 값이고, 목적 · 칸 의미는 `scripts/db/gen_schema_docs.py`의 `TABLES`에 있다. 그림은 [erd.md](erd.md).
- FK 정의에 `ON DELETE`가 없으면 `NO ACTION`이다. 서비스 표 21개.

| 스키마.표 | 목적 |
|---|---|
| `public.users` | 계정 |
| `public.auth_sessions` | 로그인 세션 |
| `public.auth_login_attempts` | 계정별 로그인 실패 · 잠금 |
| `public.auth_login_ip_attempts` | IP별 로그인 실패 · 잠금 |
| `public.auth_signup_attempts` | IP별 하루 가입 요청 수(데모 모드 전용) |
| `public.auth_google_states` | Google OAuth 일회용 상태 |
| `public.auth_google_identities` | Google 신원 ↔ 사용자 연결 |
| `public.projects` | 프로젝트 |
| `public.circuits` | 프로젝트의 정규화 회로(1:1) |
| `public.threads` | 프로젝트 안의 대화 |
| `public.runs` | 질문 한 번의 실행과 공개 결과 |
| `public.messages` | 화면 대화 기록 |
| `public.approvals` | 사람의 후보 승인(스냅샷의 유일한 사본) |
| `public.quotes` | 승인에서 만든 가격 없는 견적 |
| `public.approved_cases` | 화면의 승인 사례 목록(사용자가 지울 수 있는 표시 행) |
| `public.app_migrations` | 마이그레이션 적용 이력(우리 것) |
| `sojafit_agent.threads` | 분석 서비스의 대화 상태 기계 |
| `sojafit_agent.messages` | 분석 문맥용 사용자 입력 + 어시스턴트 답 |
| `sojafit_agent.analysis_events` | 내용 없는 운영 기록 |
| `sojafit_agent.analysis_usage` | 사용자 · 날짜별 LLM 예약 사용량 |
| `sojafit_agent.analysis_service_usage` | 서비스 전체 날짜별 예약 토큰 |

## `public.users`

- **목적**: 계정

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL |  | 계정 번호(내부 키) |
| `login_id` | character varying(100) | NOT NULL |  | 로그인 이메일(소문자). 구글 가입도 같은 칸에 이메일 저장 |
| `password_hash` | character varying(255) | NOT NULL |  | scrypt 해시. Google 전용은 'google-login-only', 로컬 데모 버튼은 'demo-button-login-only' 표식(비밀번호 로그인 불가) |
| `is_active` | boolean | NOT NULL | true | 비활성이면 로그인 · 세션 불가 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 가입 시각 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 수정 시각 |
| `role` | text | NOT NULL | 'user'::text | admin \| user |

| 제약 | 종류 | 정의 |
|---|---|---|
| `users_pkey` | PK | `PRIMARY KEY (id)` |
| `users_login_id_key` | UNIQUE | `UNIQUE (login_id)` |
| `users_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['admin'::text, 'user'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `users_login_id_key` | `UNIQUE btree (login_id)` |
| `users_pkey` | `UNIQUE btree (id)` |

## `public.auth_sessions`

- **목적**: 로그인 세션

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `token_hash` | character(64) | NOT NULL |  | 세션 토큰의 SHA-256(원문 저장 안 함) |
| `user_id` | bigint | NOT NULL |  | 소유 계정 |
| `expires_at` | timestamp with time zone | NOT NULL |  | 절대 만료 시각 |
| `last_seen_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 마지막 사용 시각(유휴 만료 판단) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_sessions_pkey` | PK | `PRIMARY KEY (token_hash)` |
| `auth_sessions_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |

| 인덱스 | 정의 |
|---|---|
| `auth_sessions_pkey` | `UNIQUE btree (token_hash)` |
| `ix_auth_sessions_expires` | `btree (expires_at)` |
| `ix_auth_sessions_user` | `btree (user_id)` |

## `public.auth_login_attempts`

- **목적**: 계정별 로그인 실패 · 잠금

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `login_hash` | character(64) | NOT NULL |  | 이메일의 SHA-256 |
| `failed_count` | integer | NOT NULL | 0 | 집계 창 안의 실패 횟수 |
| `locked_until` | timestamp with time zone | NULL |  | 잠금 끝 시각 |
| `window_started_at` | timestamp with time zone | NULL |  | 15분 집계 창 시작 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_login_attempts_pkey` | PK | `PRIMARY KEY (login_hash)` |

| 인덱스 | 정의 |
|---|---|
| `auth_login_attempts_pkey` | `UNIQUE btree (login_hash)` |

## `public.auth_login_ip_attempts`

- **목적**: IP별 로그인 실패 · 잠금

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `ip_hash` | character(64) | NOT NULL |  | 클라이언트 IP 키의 SHA-256 |
| `failed_count` | integer | NOT NULL | 0 | 실패 횟수 |
| `window_started_at` | timestamp with time zone | NULL |  | 집계 창 시작 |
| `locked_until` | timestamp with time zone | NULL |  | 잠금 끝 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_login_ip_attempts_pkey` | PK | `PRIMARY KEY (ip_hash)` |

| 인덱스 | 정의 |
|---|---|
| `auth_login_ip_attempts_pkey` | `UNIQUE btree (ip_hash)` |

## `public.auth_signup_attempts`

- **목적**: IP별 하루 가입 요청 수(데모 모드 전용)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `ip_hash` | character(64) | NOT NULL |  | IP 키 해시 |
| `day` | date | NOT NULL |  | UTC 날짜 |
| `signup_count` | integer | NOT NULL | 1 | 그날 가입 요청 수(상한 3) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_signup_attempts_pkey` | PK | `PRIMARY KEY (ip_hash, day)` |
| `auth_signup_attempts_signup_count_check` | CHECK | `CHECK ((signup_count >= 1))` |

| 인덱스 | 정의 |
|---|---|
| `auth_signup_attempts_pkey` | `UNIQUE btree (ip_hash, day)` |

## `public.auth_google_states`

- **목적**: Google OAuth 일회용 상태

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

| 인덱스 | 정의 |
|---|---|
| `auth_google_states_pkey` | `UNIQUE btree (state_hash)` |

## `public.auth_google_identities`

- **목적**: Google 신원 ↔ 사용자 연결

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `issuer` | text | NOT NULL |  | https://accounts.google.com |
| `subject` | text | NOT NULL |  | Google 계정 식별자(sub) |
| `user_id` | bigint | NOT NULL |  | 연결된 계정(사용자당 1개) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `auth_google_identities_pkey` | PK | `PRIMARY KEY (issuer, subject)` |
| `auth_google_identities_user_id_key` | UNIQUE | `UNIQUE (user_id)` |
| `auth_google_identities_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |

| 인덱스 | 정의 |
|---|---|
| `auth_google_identities_pkey` | `UNIQUE btree (issuer, subject)` |
| `auth_google_identities_user_id_key` | `UNIQUE btree (user_id)` |

## `public.projects`

- **목적**: 프로젝트

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('projects_id_seq'::regclass) | 프로젝트 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `name` | text | NOT NULL |  | 이름(공백 제거 1~200자) |
| `source_kind` | text | NOT NULL |  | demo \| upload |
| `demo_id` | text | NULL |  | 데모 회로 이름(데모일 때만, DB가 6개 이름 목록으로 검사) |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 만든 시각 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 이름 변경 · 대화 활동 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `pk_projects` | PK | `PRIMARY KEY (id)` |
| `fk_projects_user` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `ck_projects_demo` | CHECK | `CHECK (((source_kind = 'demo'::text) = (demo_id IS NOT NULL)))` |
| `ck_projects_name` | CHECK | `CHECK (((name = btrim(name)) AND ((char_length(name) >= 1) AND (char_length(name) <= 200))))` |
| `ck_projects_source_kind` | CHECK | `CHECK ((source_kind = ANY (ARRAY['demo'::text, 'upload'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `ix_projects_user_updated` | `btree (user_id, updated_at DESC, id DESC)` |
| `pk_projects` | `UNIQUE btree (id)` |

## `public.circuits`

- **목적**: 프로젝트의 정규화 회로(1:1)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `project_id` | bigint | NOT NULL |  | 프로젝트(1:1, 키) |
| `connections` | jsonb | NOT NULL |  | 정규화한 회로(부품 · 넷 JSON) |
| `source_sha256` | text | NOT NULL |  | 원본 넷리스트 SHA-256(원문은 저장 안 함) |
| `parser_version` | text | NOT NULL |  | 회로 변환기 버전 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP |  |

| 제약 | 종류 | 정의 |
|---|---|---|
| `pk_circuits` | PK | `PRIMARY KEY (project_id)` |
| `fk_circuits_project` | FK | `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE` |
| `ck_circuits_connections` | CHECK | `CHECK ((jsonb_typeof(connections) = 'object'::text))` |
| `ck_circuits_parser_version` | CHECK | `CHECK ((char_length(btrim(parser_version)) > 0))` |
| `ck_circuits_sha256` | CHECK | `CHECK ((source_sha256 ~ '^[0-9a-f]{64}$'::text))` |

| 인덱스 | 정의 |
|---|---|
| `pk_circuits` | `UNIQUE btree (project_id)` |

## `public.threads`

- **목적**: 프로젝트 안의 대화

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | 대화 UUID(URL에 노출) |
| `project_id` | bigint | NOT NULL |  | 소속 프로젝트 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 만든 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_pkey` | PK | `PRIMARY KEY (id)` |
| `threads_project_id_fkey` | FK | `FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE` |

| 인덱스 | 정의 |
|---|---|
| `ix_threads_project` | `btree (project_id)` |
| `threads_pkey` | `UNIQUE btree (id)` |

| 트리거 | 정의 |
|---|---|
| `trg_threads_purge_checkpoints` | `CREATE TRIGGER trg_threads_purge_checkpoints BEFORE DELETE ON public.threads FOR EACH ROW EXECUTE FUNCTION sojafit_agent.purge_thread_checkpoints()` |

## `public.runs`

- **목적**: 질문 한 번의 실행과 공개 결과

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | run UUID(URL에 노출) |
| `thread_id` | uuid | NOT NULL |  | 소속 대화 |
| `status` | text | NOT NULL |  | running \| requires_input \| completed \| refused \| failed |
| `safe_result` | jsonb | NULL |  | 공개 결과 JSON(answer · question_type · price_parts · interrupt · judgement · evidence). 모양을 DB CHECK 함수가 재귀 검사 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시작 |
| `updated_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 마지막 변경 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `runs_pkey` | PK | `PRIMARY KEY (id)` |
| `runs_id_thread_id_key` | UNIQUE | `UNIQUE (id, thread_id)` |
| `runs_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE` |
| `ck_runs_safe_result` | CHECK | `CHECK (((safe_result IS NULL) OR ((jsonb_typeof(safe_result) = 'object'::text) AND (safe_result ?& ARRAY['answer'::text, 'question_type'::text, 'price_parts'::text, 'interrupt'::text, 'judgement'::text, 'evidence'::text]))))` |
| `runs_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['running'::text, 'requires_input'::text, 'completed'::text, 'refused'::text, 'failed'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `ix_runs_active` | `UNIQUE btree (thread_id) WHERE (status = ANY (ARRAY['running'::text, 'requires_input'::text]))` |
| `ix_runs_thread` | `btree (thread_id)` |
| `runs_id_thread_id_key` | `UNIQUE btree (id, thread_id)` |
| `runs_pkey` | `UNIQUE btree (id)` |

## `public.messages`

- **목적**: 화면 대화 기록

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('messages_id_seq'::regclass) | 메시지 번호 |
| `thread_id` | uuid | NOT NULL |  | 대화 |
| `run_id` | uuid | NOT NULL |  | run(대화와 함께 복합 FK) |
| `role` | text | NOT NULL |  | user \| assistant |
| `content` | text | NOT NULL |  | 질문 · 답 글 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `messages_pkey` | PK | `PRIMARY KEY (id)` |
| `messages_run_id_thread_id_fkey` | FK | `FOREIGN KEY (run_id, thread_id) REFERENCES runs(id, thread_id) ON DELETE CASCADE` |
| `messages_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE` |
| `messages_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `ix_messages_run` | `btree (run_id)` |
| `ix_messages_thread` | `btree (thread_id)` |
| `messages_pkey` | `UNIQUE btree (id)` |

## `public.approvals`

- **목적**: 사람의 후보 승인(스냅샷의 유일한 사본)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approvals_id_seq'::regclass) | 승인 번호 |
| `user_id` | bigint | NOT NULL |  | 승인한 사용자 |
| `message_id` | bigint | NOT NULL |  | 승인한 어시스턴트 메시지(고유, 메시지당 1건) |
| `candidate_part` | text | NOT NULL |  | 승인한 후보 품번의 **표시 이름**(판정 결과가 보여 준 그대로. 예 'TSC 1N4007G'). 승인 JSON에서 꺼낸 칸 |
| `verdict` | text | NOT NULL |  | 승인한 판정 IDENTICAL \| SPEC_EQUIVALENT \| ROLE_SUFFICIENT. 승인 JSON에서 꺼낸 칸 |
| `part_number` | text | NOT NULL |  | 견적용 **식별 품번**: 제조사 이름(TSC 등)을 떼고 남은 공백(주문 코드)은 '-'(예 '1N4007G', '1N4148-A0G'). 승인 JSON에서 꺼낸 칸 |
| `snapshot` | jsonb | NOT NULL |  | 승인 시점의 {answer, question_type, candidate, evidence} 증빙 JSON. **스냅샷의 유일한 사본**. 가격 · 재고 키는 CHECK 함수가 거부 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 승인 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approvals_pkey` | PK | `PRIMARY KEY (id)` |
| `approvals_id_user_id_key` | UNIQUE | `UNIQUE (id, user_id)` |
| `approvals_message_id_key` | UNIQUE | `UNIQUE (message_id)` |
| `approvals_message_id_fkey` | FK | `FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE` |
| `approvals_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `approvals_snapshot_check` | CHECK | `CHECK (((jsonb_typeof(snapshot) = 'object'::text) AND (NOT quote_snapshot_has_forbidden_key(snapshot))))` |
| `ck_approvals_candidate_part` | CHECK | `CHECK (((char_length(candidate_part) >= 1) AND (char_length(candidate_part) <= 100)))` |
| `ck_approvals_part_number` | CHECK | `CHECK ((part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'::text))` |
| `ck_approvals_verdict` | CHECK | `CHECK ((verdict = ANY (ARRAY['IDENTICAL'::text, 'SPEC_EQUIVALENT'::text, 'ROLE_SUFFICIENT'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `approvals_id_user_id_key` | `UNIQUE btree (id, user_id)` |
| `approvals_message_id_key` | `UNIQUE btree (message_id)` |
| `approvals_pkey` | `UNIQUE btree (id)` |
| `ix_approvals_user` | `btree (user_id)` |

## `public.quotes`

- **목적**: 승인에서 만든 가격 없는 견적

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('quotes_id_seq'::regclass) | 견적 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(한 승인에 견적 여러 건 가능, UNIQUE 없음) |
| `part_number` | text | NOT NULL |  | 견적 품번(공백 없는 영문 · 숫자 · . _ + / -, CHECK) |
| `quantity` | integer | NOT NULL |  | 수량 1~100000 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 저장 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `quotes_pkey` | PK | `PRIMARY KEY (id)` |
| `quotes_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `quotes_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `quotes_part_number_check` | CHECK | `CHECK ((part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$'::text))` |
| `quotes_quantity_check` | CHECK | `CHECK (((quantity >= 1) AND (quantity <= 100000)))` |

| 인덱스 | 정의 |
|---|---|
| `ix_quotes_approval` | `btree (approval_id)` |
| `ix_quotes_user` | `btree (user_id)` |
| `quotes_pkey` | `UNIQUE btree (id)` |

## `public.approved_cases`

- **목적**: 화면의 승인 사례 목록(사용자가 지울 수 있는 표시 행)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL | nextval('approved_cases_id_seq'::regclass) | 사례 번호 |
| `user_id` | bigint | NOT NULL |  | 소유자 |
| `approval_id` | bigint | NOT NULL |  | 근거 승인(고유). 후보 이름 · 판정은 approvals에서 읽는다 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `approved_cases_pkey` | PK | `PRIMARY KEY (id)` |
| `approved_cases_approval_id_key` | UNIQUE | `UNIQUE (approval_id)` |
| `approved_cases_approval_id_user_id_fkey` | FK | `FOREIGN KEY (approval_id, user_id) REFERENCES approvals(id, user_id) ON DELETE CASCADE` |
| `approved_cases_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |

| 인덱스 | 정의 |
|---|---|
| `approved_cases_approval_id_key` | `UNIQUE btree (approval_id)` |
| `approved_cases_pkey` | `UNIQUE btree (id)` |
| `ix_approved_cases_user` | `btree (user_id)` |

## `public.app_migrations`

- **목적**: 마이그레이션 적용 이력(우리 것)

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `version` | text | NOT NULL |  | 적용한 변경의 이름 |
| `applied_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 적용 시각 |
| `note` | text | NOT NULL | ''::text | 한 줄 설명 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `app_migrations_pkey` | PK | `PRIMARY KEY (version)` |

| 인덱스 | 정의 |
|---|---|
| `app_migrations_pkey` | `UNIQUE btree (version)` |

## `sojafit_agent.threads`

- **목적**: 분석 서비스의 대화 상태 기계

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | **public.threads.id와 같은 UUID이며 FK**(대화를 지우면 같이 지워짐) |
| `user_id` | bigint | NOT NULL |  | 소유자(CASCADE). 소유 조회를 빠르게 하려고 둔 의도된 비정규화 |
| `target` | text | NOT NULL |  | 교체 대상 부품 참조(예: D1) |
| `version` | integer | NOT NULL | 0 | 질문 차수(새 질문마다 +1) |
| `retries` | integer | NOT NULL | 0 | 같은 질문의 재시도 횟수(상한 2) |
| `status` | text | NOT NULL | 'NEW'::text | NEW \| RUNNING \| WAITING \| DONE \| FAILED |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |
| `input_record` | jsonb | NULL |  | 현재 차수의 원문 질문 · 조건 · 재개 답(JSON) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `threads_pkey` | PK | `PRIMARY KEY (id)` |
| `fk_agent_threads_thread` | FK | `FOREIGN KEY (id) REFERENCES threads(id) ON DELETE CASCADE` |
| `threads_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `threads_status_check` | CHECK | `CHECK ((status = ANY (ARRAY['NEW'::text, 'RUNNING'::text, 'WAITING'::text, 'DONE'::text, 'FAILED'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `agent_threads_owner` | `btree (user_id, created_at DESC)` |
| `threads_pkey` | `UNIQUE btree (id)` |

## `sojafit_agent.messages`

- **목적**: 분석 문맥용 사용자 입력 + 어시스턴트 답

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | bigint | NOT NULL |  | 번호 |
| `thread_id` | uuid | NOT NULL |  | 분석 대화 |
| `role` | text | NOT NULL |  | user \| assistant |
| `checkpoint_id` | text | NULL |  | 그 답을 만든 LangGraph 체크포인트(thread_id와 함께 중복 방지 UNIQUE 색인, 값이 있을 때만) |
| `content` | text | NOT NULL |  | 사용자는 '사용 조건: …' 접두 + 질문 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `messages_pkey` | PK | `PRIMARY KEY (id)` |
| `messages_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE` |
| `messages_role_check` | CHECK | `CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text])))` |

| 인덱스 | 정의 |
|---|---|
| `agent_messages_checkpoint` | `UNIQUE btree (thread_id, checkpoint_id) WHERE (checkpoint_id IS NOT NULL)` |
| `agent_messages_thread` | `btree (thread_id, id)` |
| `messages_pkey` | `UNIQUE btree (id)` |

## `sojafit_agent.analysis_events`

- **목적**: 내용 없는 운영 기록

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `id` | uuid | NOT NULL |  | UUID |
| `thread_id` | uuid | NOT NULL |  | 분석 대화 |
| `version` | integer | NOT NULL |  | 질문 차수 |
| `request_id` | text | NOT NULL |  | X-Request-ID |
| `mode` | text | NOT NULL |  | real \| demo |
| `status` | text | NOT NULL |  | 결과 상태 |
| `elapsed_ms` | integer | NOT NULL |  | 사람 대기 제외 실행 시간 |
| `stages` | jsonb | NOT NULL |  | 단계별 ms(내용 없음) |
| `trace_id` | text | NOT NULL |  | Langfuse trace id |
| `trace_delivery` | text | NOT NULL |  | queued 등 전달 상태 |
| `created_at` | timestamp with time zone | NOT NULL | CURRENT_TIMESTAMP | 시각 |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_events_pkey` | PK | `PRIMARY KEY (id)` |
| `analysis_events_thread_id_fkey` | FK | `FOREIGN KEY (thread_id) REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE` |

| 인덱스 | 정의 |
|---|---|
| `agent_events_thread` | `btree (thread_id, created_at DESC)` |
| `analysis_events_pkey` | `UNIQUE btree (id)` |

## `sojafit_agent.analysis_usage`

- **목적**: 사용자 · 날짜별 LLM 예약 사용량

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
| `analysis_usage_pkey` | PK | `PRIMARY KEY (user_id, day)` |
| `analysis_usage_user_id_fkey` | FK | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` |
| `analysis_usage_reserved_tokens_check` | CHECK | `CHECK ((reserved_tokens >= 0))` |
| `analysis_usage_reserved_usd_check` | CHECK | `CHECK ((reserved_usd >= (0)::numeric))` |

| 인덱스 | 정의 |
|---|---|
| `analysis_usage_pkey` | `UNIQUE btree (user_id, day)` |

## `sojafit_agent.analysis_service_usage`

- **목적**: 서비스 전체 날짜별 예약 토큰

| 칸 | 타입 | NULL | 기본값 | 의미 |
|---|---|---|---|---|
| `day` | date | NOT NULL |  | UTC 날짜 |
| `reserved_tokens` | bigint | NOT NULL | 0 | 서비스 전체 예약 토큰(상한 2,000,000) |

| 제약 | 종류 | 정의 |
|---|---|---|
| `analysis_service_usage_pkey` | PK | `PRIMARY KEY (day)` |
| `analysis_service_usage_reserved_tokens_check` | CHECK | `CHECK ((reserved_tokens >= 0))` |

| 인덱스 | 정의 |
|---|---|
| `analysis_service_usage_pkey` | `UNIQUE btree (day)` |

## 코퍼스 · LangGraph 표(이 문서 범위 밖)

서비스 표가 아니라 이 문서의 그림 · 정의에 넣지 않는다. 이름만 적는다.

- 코퍼스(`public`, `db/002` · `009`): `source_documents` · `document_chunks` · `chunk_embeddings` · `chunk_embedding_bits`
- LangGraph 라이브러리(`sojafit_agent`, `PostgresSaver` · `PostgresStore`가 만든다): `checkpoints` · `checkpoint_blobs` · `checkpoint_writes` · `checkpoint_migrations` · `store` · `store_vectors` · `store_migrations` · `vector_migrations`
