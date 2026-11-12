# 목표 설계: 원칙 · 선택지 비교 · 결정 근거

- 상태: **정운 확정 전 초안**(11-11). 구현 전에 이 문서의 "결정 항목"(README)을 확정한다.
- 범위: 서비스 표만. 코퍼스 4표와 LangGraph 표는 그대로.
- 고정 조건: HTTP API 응답 모양 불변(프런트 수정 0), 새 DB 첫 기동(compose, G2) · 키 없는 데모 · CI 계속 동작, 동결(11-16 24:00)까지 남은 시간.

## 1. 11-10 밤 추가 조사에서 나온 사실을 어떻게 반영했나

| # | 사실(출처: `db-unknowns-1110.md`) | 반영 |
|---|---|---|
| 1 | Supabase **Data API(PostgREST)가 켜져 있고 `public`에 `anon` USAGE가 있다**. `sojafit_agent`는 노출 안 됨 | 모든 서비스 표를 **RLS ON + 정책 0**, 공개 역할 권한 0으로 만든다(`026`). 새 기준선이 RLS를 **직접 명시**한다(§3 D7). `public`을 비노출 스키마로 옮기는 안은 보류(D10) |
| 2 | 운영에 `ensure_rls` **이벤트 트리거**: `public`의 새 표는 자동 RLS ON. `sojafit_agent` · compose · CI에는 없음 | 기준선 마지막에 21개 표의 `ENABLE ROW LEVEL SECURITY`를 전부 적는다 → 환경마다 같은 결과. 시험: 기준선 + 026 적용 뒤 "공개 권한 0 · RLS OFF 표 0"(§5) |
| 3 | 운영에는 `supabase_migrations.schema_migrations`가 **있다**(5건: 인증 · 구글 · 분석 초기 표). 나머지는 수동 + `--setup`. 레포 SQL 23개는 운영과 서비스 표 차이 0 | **우리 이력 표 `public.app_migrations`를 새로 둔다**(§3 D6). Supabase 표는 5건짜리 과거 기록이라 이어 쓰지 않고 건드리지 않는다. 첫 행에 "레포 000~025 수동 적용분"을 기록 |
| 4 | 프런트가 표 칸에 직접 묶인 곳은 3곳: `runs.safe_result`(JSON 모양 = API 계약), `quotes.part_number`, `approved_cases.snapshot->candidate` | 3곳의 **응답 값을 그대로 유지**한다. `safe_result` 저장 데이터는 안 바뀐다(CHECK만 단순화). `quotes.part_number` 유지. 승인 사례 목록의 `candidate_part · verdict`는 `approvals`의 칸을 JOIN해서 같은 값을 준다 → 프런트 변경 0 |
| 5 | 삭제: `sojafit_agent.circuits/threads → users`는 RESTRICT, `auth_google_pending`(이메일 평문) · `auth_signup_attempts`는 계정 삭제 뒤에도 남음. CLI `--delete-user-id`는 `@example.test` 비활성 일반 계정만 | `sojafit_agent.threads → users`를 **CASCADE**로, `sojafit_agent.circuits` 삭제, `auth_google_pending` 삭제(2b). 대화 행 삭제 시 체크포인트를 지우는 **트리거** 추가(D9). `auth_signup_attempts`는 IP 해시 + 30일 청소라 유지. CLI의 `@example.test` 제한은 그대로(데모 계정 `demo1 · demo2@example.com`을 CLI로 지우려면 허용 범위를 넓혀야 한다 — 선택 사항) |
| 6 | 운영 Postgres **17.11** + pgvector 0.8.2, compose · CI는 **16.15** + 0.8.7 | 기준선 · 이전 SQL · 되돌리기 전부를 **16과 17 양쪽에서 실행**해 확인했다(§5) |
| 7 | 007 데모 시드는 psql 전용(`\getenv`)이고 `DEMO_MODE`에 의존 | 선택지 3개를 비교(D8)하고 **첫 데모 로그인 때 만드는 안**을 추천 |
| 8 | 접속은 `postgres` 역할(BYPASSRLS), Supavisor 풀러, 표 소유자 전부 `postgres`, FORCE RLS 0 | RLS ON은 서비스 동작에 영향 없음(Data API 방어용). **FORCE는 쓰지 않는다**. 분석 서비스의 세션 단위 advisory lock(`pg_try_advisory_lock`)은 풀러가 session 모드(포트 5432)일 때만 안전하다 — 조사가 "5432 = session 모드 [추정]"이라 확인이 필요한 **가정**으로 §6에 적는다 |
| 9 | 연결 풀이 거의 없음(호출마다 새 연결), 한도 60 | 재설계 범위 밖. 설계가 연결 수를 늘리지 않는다(트리거 · FK는 같은 연결 안에서 일한다) |
| 10 | 확장 중 `pgcrypto` · `uuid-ossp`는 쓰이지 않음. `vector`는 운영에서 `extensions` 스키마 | 기준선은 확장을 쓰지 않는다(UUID는 앱이 만들어 넣음). 코퍼스 SQL의 `vector` 스키마 가정은 건드리지 않는다 |

## 2. 설계 원칙

| 원칙 | 규칙 | 현재와의 차이 |
|---|---|---|
| **사실 하나는 한 곳에** | 같은 정보를 두 표에 복사하지 않는다. 필요하면 FK + JOIN | 회로 연결 2곳 · 승인 스냅샷 3곳을 1곳씩으로 |
| **연결은 DB가 보장** | 논리적 연결(같은 UUID)도 FK로 만든다. FK를 걸 수 없는 라이브러리 표는 트리거로 | `public.threads ↔ sojafit_agent.threads` FK 신규, 체크포인트 트리거 신규 |
| **소유자 삭제 = 파생 삭제** | 사용자 · 프로젝트에 딸린 행은 `ON DELETE CASCADE`. `RESTRICT`는 "실수로 지우면 안 되는" 곳에만 | `sojafit_agent.*`의 RESTRICT 3개 → CASCADE(회로 사본은 삭제). 지금은 코드가 순서를 지켜 지워야 했다 |
| **DB는 불변식만, 앱 모양은 앱이** | CHECK는 "깨지면 데이터가 틀리는 것"(키 · 상태 · 품번 형식 · 가격 키 금지)만. 앱의 JSON 세부 모양 · 데모 목록은 앱이 정본 | `conversation_json_matches` 재귀 검사 · 데모 6개 목록 CHECK 제거(11-10에 024 · 025로 두 번 깨짐) |
| **응답에 새는 칸은 칸으로** | API 응답이 읽는 값은 JSON 속이 아니라 칸에 둔다 | 승인의 `candidate_part · verdict · part_number`를 JSON에서 칸으로 |
| **식별자** | 외부에 보이는 대화 · run은 `uuid`(앱이 생성), 나머지는 `bigint`. 이 규칙은 **지금과 같다**(바꾸지 않음) | 변경 없음(바꾸면 API · 프런트가 흔들림) |
| **시간 칸** | `created_at`(만든 시각) · `updated_at`(바뀐 시각, 필요한 표만) · 모두 `timestamptz`. 도메인 시각은 `<동사>_at` | 변경 없음(이미 일관) |
| **FK 칸은 인덱스** | FK 칸 앞에 인덱스(복합 인덱스의 선두 포함). 삭제 cascade가 전체 훑기가 되지 않게 | `auth_sessions.user_id` 인덱스 신규 |
| **이름 규칙** | 새 객체: `pk_ · fk_ · ix_ · uq_ · ck_<표>_<무엇>`. 이미 있는 기본 이름은 바꾸지 않는다(이전 SQL이 이름을 안 바꾸게) | 새 것만 적용 |
| **개인정보** | 이메일 평문은 `users.login_id` 하나만. 질문 · 답은 보관 기간(60일)이 있는 표에만. 해시 키 표는 30일 청소 | `auth_google_pending`(이메일 평문) 삭제 |
| **보안 두 겹** | 모든 서비스 표 RLS ON(정책 0) + 공개 역할 권한 0. 서버는 소유자 연결로만 접속 | 기준선이 RLS를 명시, 권한은 026 |
| **앱은 DDL을 안 돌린다** | 스키마 변경은 이전 SQL로, 앱 시작 때 SQL 파일을 적용하지 않는다(`memory_service.initialize` 7개 파일 적용은 기준선 채택 때 제거) | M 단계 |

## 3. 선택지 비교

비용은 "바꿔야 하는 코드 함수 수 / 시험 수"다(근거는 [`to-be-impact.md`](to-be-impact.md)).

### D1. 화면용 ↔ 분석용 이중 저장 — 추천: **B 최소안**

| 안 | 내용 | 장점 | 단점 · 위험 | 비용 |
|---|---|---|---|---|
| A. 통합 | `sojafit_agent.threads` · `messages`를 `public.threads` · `messages`로 합침 | 대화 상태 표가 하나. 원자성 확보 | 분석 서비스 전체를 다시 씀. 분석 입력 문자열이 바뀌면 **키 없는 데모 기록 재생이 깨짐**. 동결 직전 위험이 가장 큼 | 함수 약 22개 / 시험 60여 개 |
| **B. 최소** | ① `sojafit_agent.threads.id`를 `public.threads(id)`의 FK로(CASCADE) ② `sojafit_agent.circuits`(연결 복사) 삭제 → `public.circuits` 읽기 ③ 죽은 `sojafit_agent.approvals` 삭제 ④ `user_id` FK를 CASCADE로 | 복사본 0, 고아 불가, 삭제가 DB 보장. **분석 서비스의 상태 기계와 문맥은 그대로**라 에이전트 동작 · 재생 불변 | 대화 상태가 아직 두 표(FK로 묶임). 한 요청이 여전히 연결 3개(원자성은 안 생김) | 함수 11개 / 시험 약 25개 |
| C. 현상 유지 + FK만 | 위 ①만 | 코드 변경 0 | 회로 복사본 · 죽은 표 · 이중 연결이 남음 | 함수 0 / 시험 3개 |

B를 고른 이유: A의 이득(원자성)은 크지만 에이전트 입력과 재생 기록을 건드리는 위험이 동결 전에는 감당이 안 된다. B는 A로 가는 **전제(FK, 단일 회로 사본)**를 만들어 나중에 A를 하더라도 되돌릴 일이 없다. C는 거의 공짜지만 복사본 문제가 남는다. B의 ①④는 SQL만이라 P1에 넣고(코드 변경 0), ②③은 코드가 따라와야 해서 P2로 나눴다.

### D2. 승인 스냅샷 3벌 — 추천: **B 단일화**

| 안 | 내용 | 비용 |
|---|---|---|
| A. 현상 | 3곳에 같은 JSON(건당 1.6KB, 100% 동일) | 0 |
| **B. 단일화** | `approvals.snapshot`만 남기고 `quotes` · `approved_cases`의 snapshot 삭제. 목록 · 견적이 읽는 값은 `approvals`의 새 칸(`candidate_part · verdict · part_number`)과 JOIN | 함수 4 / 시험 약 6 |
| C. 승인 사례를 승인에 흡수 | `approved_cases` 표 삭제, `approvals.case_dismissed_at` 칸 | 함수 6 / 시험 약 8. 사례 id가 승인 id로 바뀜(응답은 정수라 프런트 무변경이지만 값이 달라짐) → 보류 |

`quotes.snapshot`은 어느 코드도 읽지 않았고(조사 §4), `approved_cases`는 목록이 `candidate.part · verdict`만 읽는다. 그 둘이 읽던 값을 칸으로 꺼내 `approvals` 한 곳에 두면 증빙 JSON(답 · 근거)은 승인당 1벌만 남는다 = 개인정보가 퍼진 곳도 2곳 줄어든다. `quotes`는 여러 건이 한 승인에서 나올 수 있다(승인당 UNIQUE가 **없다** — 11-10 스모크 설명의 "승인당 견적 1개 DB 제약"은 틀렸고 실제로는 허용된다).

### D3. 죽은 표 · 칸 — 추천: **삭제**(코드 제거와 함께)

`sojafit_agent.approvals`(0행) · `circuits.netlist`(전부 빈 글자) · `users.display_name`(0건 사용). `users.display_name`은 코드가 없어 SQL만(P1). `sojafit_agent.approvals`는 옛 승인 경로 코드(`Conversations.approve · _approve · memories · _current_memories`, `detail()` 일부)와 함께(P2).

### D4. DB CHECK가 앱 JSON 모양을 복제 — 추천: **단순화**

| 안 | 내용 | 비용 |
|---|---|---|
| 유지 | `conversation_json_matches`가 `safe_result` 전체를 재귀 검사 + 데모 6개 이름 CHECK | 0 — 모양이 바뀔 때마다 SQL 수정(11-10에 두 번 서비스가 503) |
| **단순화** | `safe_result`는 "객체 + 필수 키 6개", `projects`는 "데모일 때만 `demo_id`". 세부는 앱 모델(`SafeResult`)이 검증 | 코드 0 / 시험 2(SQL 텍스트를 파싱하던 시험 교체) |
| 제거 | CHECK 없음 | 코드 0 — 앱 버그가 틀린 JSON을 저장해도 DB가 못 잡음 |

DB는 "필수 키가 있는 객체"까지만 막아 저장 데이터를 보호하고, 세부 모양은 응답을 만드는 앱 모델이 정본이다.

**빠지는 검사 한 줄(명시)**: 옛 `safe_result` 재귀 검사는 `price_parts` 항목의 품번 정규식 CHECK도 포함했는데 단순 CHECK는 이를 **뺀다**. 이 형식은 앱의 `SafeResult` 모델(pattern)이 검증하고 DB는 더 이상 막지 않는다(저장된 기존 데이터는 영향 없음). 이미 저장된 데이터는 새 검사를 모두 통과한다(이전 SQL이 사전 점검한다).

### D5. 인증 표 — 추천: **`auth_google_pending`만 삭제(선택 단계 2b)**

| 표 | 처리 | 이유 |
|---|---|---|
| `auth_google_pending` | 삭제 | 11-10 자동 연결 결정으로 콜백이 안 만듦, **이메일 평문** 보유. 코드(`request_google_link` · `approve_google_link` · `google_pending_email` · `/google/pending` · `--approve-google`) 제거 뒤 |
| `auth_signup_attempts` | 유지 | 이메일 가입은 `DEMO_MODE=1` 전용으로 아직 코드가 있음. IP 해시 + 30일 청소. 가입 경로를 지울 때 같이 |
| `auth_login_attempts` + `auth_login_ip_attempts` 합치기 | 보류 | 칸이 거의 같지만 `authenticate` · `delete_account`를 고쳐야 하고 이득이 작음 |

### D6. 마이그레이션 방식과 이력 표 — 추천: **증분 파일 먼저, 기준선 교체는 P2 뒤** → [결정·구현 11-11] P2 뒤 기준선으로 교체함: 새 DB는 `db/020_service_baseline.sql` 한 파일, 옛 증분은 `db/legacy/`(이력), 운영 이전은 `db/migrations/`

| 안 | 내용 | 비용 | 위험 |
|---|---|---|---|
| A. 기준선으로 교체 | `db/003~025`를 `db/020_service_baseline.sql` 하나로. compose initdb · CI · 시험이 이 파일만 읽음. 이후 변경은 번호 파일 | 시험 파일 약 7개, CI, `memory_service.initialize` | 기준선이 P1+P2 완료 상태라 **P2 코드가 끝난 뒤에만** 맞다. 동결 직전에 첫 기동 경로를 바꾼다 |
| **B. 증분 파일(추천 먼저)** | 기존 `000~025`를 그대로 두고 `026`(보안, 만들어 둠) · `027`(P1) · `028`(P2)를 **새 DB용 + 운영 이전용으로 같이 쓴다**(멱등 + 안전한 순서). 이력은 `app_migrations`에 기록 | 시험 파일 0(기존 파일이 안 바뀜) | "한 번에 완성된 스키마가 없는" 구조 부채는 남음 |
| C. 현상 | 파일 23개 + 수동 | 0 | 이력 없음, 4갈래 적용 |

이력 표: **우리 표 `public.app_migrations`**. Supabase의 `supabase_migrations.schema_migrations`는 (a) 초기 5건뿐이고 (b) Supabase 도구 형식이며 (c) compose · CI에는 없다. 우리 표는 세 환경에서 같고 `(version, applied_at, note)`만으로 충분하다. 적용 도구는 만들지 않는다(psql 한 줄, 이력 INSERT는 파일 끝에 포함). **기준선은 만들어 두었으므로**(`db/020_service_baseline.sql`, 16 · 17에서 실행 확인) P2 코드가 끝나고 시간이 남으면 A로 바꾼다.

### D7. RLS를 기준선에서 명시할까 — 추천: **명시**

| 안 | 결과 |
|---|---|
| 명시(추천) | 운영 · compose · CI 모두 서비스 표 21개가 RLS ON. `ensure_rls` 트리거에 기대지 않음 |
| 트리거에 맡김 | 운영은 `public`만 ON, `sojafit_agent` · compose · CI는 OFF — 같은 SQL이 환경마다 다른 상태 |

정책은 만들지 않는다(= 공개 역할 기본 거부). 서버는 BYPASSRLS 역할이라 영향 없다. FORCE는 쓰지 않는다(소유자까지 막으면 서버가 깨진다).

### D8. 데모 계정 시드(007) — 추천: **C. 첫 데모 로그인 때 만든다**

| 안 | 내용 | 비용 |
|---|---|---|
| A. 현상(SQL) | `psql`의 `\getenv`로 `DEMO_MODE`를 읽는 시드. psql로만 실행 가능, CI는 안 씀 | 0 |
| B. 앱 CLI | `python -m backend.auth --seed-demo`를 compose `thread-setup`에서 호출 | 함수 1 + compose 1 / 시험 2 |
| **C. 지연 생성** | `demo_session`이 `DEMO_MODE=1`에서 계정이 없으면 비밀번호 없는 표식 계정을 만든다 | 함수 1 / 시험 2~3. SQL 파일 · CLI · 환경 의존 모두 사라짐 |

C는 안전 조건이 지금과 같다: `DEMO_MODE=1`에서만, 표식 해시(비밀번호 로그인 불가)만. 007 파일과 compose의 `DEMO_MODE` 환경 전달(db 컨테이너) 의존이 없어진다.

### D9. 삭제 정합성 — 추천: **트리거(추가 안전망) + 코드는 그대로**

| 안 | 내용 | 비용 |
|---|---|---|
| 코드만 | `delete_analysis_threads` · `purge_inactive_projects`가 체크포인트를 직접 지움(지금) | 0 — 운영자가 편집기에서 지우면 체크포인트(질문 · 답이 든 JSON)가 고아로 남음 |
| FK | 체크포인트 `thread_id`가 글자라 불가능 | — |
| **트리거** | `public.threads` BEFORE DELETE가 같은 thread의 체크포인트 3표 행을 지움 | SQL만(코드 0). 기존 코드의 직접 삭제와 겹쳐도 무해 |

삭제 경로가 4개(프로젝트 · 계정 · 청소 · 운영자 직접)라 DB 한 곳에서 보장하는 것이 안전하다. 코드의 직접 삭제는 응답의 삭제 건수(`DELETE /api/me`의 `deleted`)를 세는 데 필요해 남긴다. 동작은 §5의 시험으로 확인했다.

### D10. 서비스 표를 `public` 밖으로 — 추천: **보류**

Data API가 `public`을 노출하므로 서비스 표를 `app` 같은 비노출 스키마로 옮기면 노출 자체가 사라진다(`ALTER TABLE ... SET SCHEMA`, 연결 `search_path` 조정). 하지만 SQL 안의 `public.` 정규화 이름(023 · 020 · 청소 함수), 시험의 `search_path` 스키마, 코퍼스 SQL과의 이웃 관계를 모두 확인해야 하고, RLS + 권한 0 두 겹으로 이미 막힌다. 동결 뒤 과제로 둔다.

## 4. 개인정보 · 보관 기간(목표)

| 데이터 | 있는 곳 | 보관 | 삭제 경로 |
|---|---|---|---|
| 이메일 평문 | `users.login_id` | 계정이 있는 동안 | 탈퇴 · 운영자 삭제(`ON DELETE CASCADE`로 파생 전부) |
| 질문 · 답 | `messages.content`, `runs.safe_result`, `approvals.snapshot`(1벌), `sojafit_agent.messages.content`, `threads.input_record`, 체크포인트 | 프로젝트 마지막 활동 후 60일 | 프로젝트 삭제 cascade + 체크포인트 트리거 |
| 회로 연결 | `public.circuits.connections`(1벌) | 〃 | 프로젝트 삭제 cascade |
| 로그인 · 가입 시도(해시) | `auth_login_*` · `auth_signup_attempts` | 30일 | `purge_log_records` |
| 만료 세션 | `auth_sessions` | 만료 1일 뒤 | `purge_log_records`(신규, 지금은 로그인 때만) |
| 사용자 사실 3칸 | LangGraph Store | 직접 지울 때까지 | 코드(`_delete_store`) — 라이브러리 표라 FK 불가 |

as-is 대비: 질문 · 답 사본이 2곳(`quotes` · `approved_cases` 스냅샷) 줄고, 이메일 평문 표 1개(`auth_google_pending`)가 사라지고, 회로 연결 사본이 1곳 줄어든다.

## 5. 시험으로 확인한 것 [실측, 일회용 Postgres 16.15와 17.11 각각]

| 확인 | 결과 |
|---|---|
| `db/020_service_baseline.sql`이 빈 DB에서 오류 없이 실행 | 서비스 표 21개(public 16 + sojafit_agent 5), 함수 · 트리거 정상 |
| 현재 구조(`db/000~025` 적용) + 표본 데이터 → **expand** | 오류 없음. 사전 점검(고아 · 위반 행)이 통과 |
| expand 뒤 **옛 코드**가 새 칸 없이 승인을 INSERT | 통과(NULL 칸 허용) |
| **contract P1**(옛 코드가 넣은 행 백필 포함) | `TSC 1N4007G → 1N4007G`, `TSC SS34 → SS34`, `Taiwan Semiconductor 1N4148 A0G → 1N4148-A0G` |
| expand + P1 + **P2** 뒤 구조가 `baseline`만 적용한 DB와 같은가 | 칸 · 제약 · 인덱스 · 트리거 · 함수 **차이 0**(차이는 RLS 표시뿐: 로컬 DB에는 Supabase `ensure_rls`가 없어 기준선만 ON, 운영은 026이 같게 만듦, 그리고 선택 2b 표 1개) |
| P1만 적용한 중간 상태에서 옛 분석 서비스 삭제 경로 · 옛 청소 함수 | 오류 없이 동작 |
| 새 제약 동작 | NOT NULL · 공백 든 품번 · 알 수 없는 판정 · 필수 키 없는 결과 · 업로드인데 `demo_id` · 없는 대화 UUID의 분석 대화 모두 **거부**, 새 데모 회로 이름은 **허용** |
| 삭제 연쇄 | 프로젝트 삭제 → 분석 대화 · 메시지 · 이벤트 · 체크포인트 3종 · 승인까지 사라짐. 청소 함수도 같음. 분석 데이터가 있는 사용자 삭제가 RESTRICT에 막히지 않음 |
| **되돌리기**(B2 → B1 → A) | 처음(`db/000~025`) 구조와 **차이 0**(`app_migrations` · RLS · 새 단순 검사 1개 제외), 스냅샷 · 회로 사본 데이터 무손실 재생성 |
| 기준선 + `026`(anon · authenticated 역할 있는 DB, 두 번 실행) | 오류 없음, **공개 권한이 남은 표 0, RLS OFF 표 0** |

## 6. 가정과 확인 못 한 것

- 풀러가 **session 모드(5432)**라는 가정: 분석 서비스가 세션 단위 advisory lock을 쓴다. transaction 모드(6543)면 안전하지 않다. 이 설계는 이 부분을 바꾸지 않았다.
- 운영 DB에서 직접 **이전 SQL을 실행해 보지는 않았다**(승인 전 · 일회용 DB에서만 확인). 운영 적용은 백업 후 정운이 한다.
- `detail()`이 돌려주는 사전의 `approvals` · `related_memories` · `consulted_memories` 키를 API 계층이 어디까지 읽는지는 P2 구현 때 코드로 확인해야 한다(IMPACT §3). 응답 모양이 바뀌면 안 되므로 필요하면 빈 값으로 유지한다.
- 성능(쿼리 계획)은 표가 작아 조사하지 않았다.
