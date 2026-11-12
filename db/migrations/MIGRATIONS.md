# db/migrations

- 2026-11-12 인증 통합: 030_google_onboarding.sql 사용 버전에서는 `migrate_prod_2b_optional_drop_dead_auth.sql`을 실행하지 않는다. pending은 명시적 가입·비밀번호 재확인 연결·관리자 승인에 쓰이는 활성 표다. 운영 적용은 이 로컬 통합에서 수행하지 않았다.

## 역할
- 이 폴더: **이미 서비스 표가 있는 DB(운영)** 를 재설계 구조로 옮기는 SQL을 둡니다. 새 DB는 이 폴더를 쓰지 않고 `db/020_service_baseline.sql`로 한 번에 만듭니다. Postgres 이미지는 `db/` 바로 아래만 실행하므로 여기 SQL은 자동 실행되지 않습니다.
- 넣는 것: 운영 이전 단계별 SQL(expand → 새 코드 배포 → contract), 선택 단계, 되돌리기. 단계마다 파일 끝에서 이력 표 `public.app_migrations`에 한 줄을 남깁니다([결정] D6: Supabase의 `supabase_migrations`를 이어 쓰지 않음).
- 넣지 않는 것: 새 DB 초기화 SQL(`db/`), 설계 설명(`db/redesign/`).
- 담당: 서비스·운영

## 순서 (운영, 정운이 백업 뒤 직접 실행)
1. `migrate_prod_1_expand.sql` — 옛 코드가 돌고 있어도 안전한 "더하기"만(새 칸 · 검사 · 인덱스 · FK · 이력 표). 머리에 `pg_dump` 백업 명령(세 파일: sojafit_agent 전체 · public 서비스 표 · public 구조 + 함수).
2. P1 새 코드 배포(0% → 점검 → 100%) → 스모크.
3. `migrate_prod_2_contract_p1.sql` — 되돌릴 수 없는 삭제(스냅샷 복사본 · `display_name`).
4. P2 새 코드 배포 → `migrate_prod_3_contract_p2.sql`. 선택: `migrate_prod_2b_optional_drop_dead_auth.sql`(구글 승인 대기 표 삭제, 코드 제거 배포 뒤에만) **[주의] 2026-11-12(#109)부터 `auth_google_pending`이 다시 쓰이므로 실행하지 않는다.**
5. 되돌리기: `migrate_prod_4_rollback.sql`을 **적용의 반대 순서**(B2b → B2 → B1 → A)로 한 절씩. contract 뒤에는 **코드보다 DB를 먼저** 되돌린다(옛 코드가 지운 칸을 읽는다). 되돌린 회로 사본은 옛 코드가 읽는 `{components, nets}` 모양으로 복사된다. B1 끝의 셸 단계(`db/legacy/`의 옛 검사 · 청소 함수 재생성 + `REVOKE`)도 실행한다. 다시 만든 표는 RLS ON, 함수는 PUBLIC 실행 권한 없음으로 돌아온다.
- 검증: `scripts/db/verify_chain/verify_chain.sh`가 일회용 Postgres 16 · 17에서 "옛 구조 + 이 SQL들 = 새 기준선", "되돌리기 뒤 = 처음 구조(RLS · 함수 권한 포함)"를 확인한다. 운영 DB에는 실행한 적이 없다.

## 실행 전 점검 (읽기 전용, 개수만 출력)
단계마다 직전에 점검 파일을 돌려 "기대"와 다른 값이 없는지 본다. 모두 `BEGIN READ ONLY`이고 질문 · 답 · 이메일 같은 내용은 찍지 않고 개수(와 id)만 찍는다. 사용: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At -f db/migrations/<파일>`

| 직전 | 파일 | 보는 것 |
|---|---|---|
| expand | `precheck_1_before_expand.sql` | `display_name` 값 수, `agent.threads` 고아 수, 승인 snapshot의 part · verdict · 품번 형식 위반 수, 프로젝트 · 결과 JSON 검사 위반 수, 체크포인트 고아 수(참고), 이력 표 없음 |
| P1 contract | `precheck_2_before_p1.sql` | 이력 표 기대(`expand`), `display_name` 값 수, `quotes` · `approved_cases` snapshot 불일치 수, 승인 새 칸이 빈 행 수, expand가 만든 객체 3개 |
| P2 contract | `precheck_3_before_p2.sql` | 이력 표 기대, `sojafit_agent.approvals` 행 수, `sojafit_agent.circuits` 행 수 · netlist 값 있음 · filename 다름 · 연결 안 됨 · 가드 판정 행 수, 체크포인트 고아(참고) |
| 2b | `precheck_4_before_2b.sql` | 이력 표 기대(`contract-p2`), `auth_google_pending` 행 수(표가 이미 없어도 오류 없이 돎) |

expand의 `DO` 사전점검(값 형식)과 contract의 데이터 손실 가드가 같은 기준으로 한 번 더 막는다. 점검 파일은 "미리 보는 것"이고 막는 것은 SQL 안의 `EXCEPTION`이다.

## 풀러 · 연결 방식
- 가드의 확인 변수 `SET app.ack_...`는 **연결(세션) 단위**다. Supabase 풀러의 transaction 모드(6543)는 문장마다 연결이 바뀔 수 있어 확인 변수가 다른 연결로 가서 막힐 수 있다. 이전 SQL은 **직접 연결 또는 session 모드(5432)**로 실행한다.
- 풀러(6543)밖에 못 쓰면 한 트랜잭션에 넣는다: `(echo "BEGIN; SET LOCAL app.ack_drop_display_name='yes';"; cat db/migrations/migrate_prod_2_contract_p1.sql) | psql "$DATABASE_URL" -v ON_ERROR_STOP=1` (파일 안의 `BEGIN`은 경고만 내고 파일 끝 `COMMIT`이 끝낸다). 이 경로는 `rd_test6.sh`가 확인한다.

## 백업 복원
백업에서 새 DB(예: 새 Supabase 프로젝트)로 옮기는 절차는 [`db/DB.md`](../DB.md) "백업 복원"을 따른다. `pg_dump`/`pg_restore`는 복원 중 `search_path`를 비우는데, 재귀 함수(`quote_snapshot_has_forbidden_key`, 옛 `conversation_json_matches`)가 자기 자신을 스키마 없이 불러 설정이 없으면 `approvals` 등의 COPY가 `function ... does not exist`로 실패한다. 기준선은 함수에 `SET search_path`를 붙여 만들고, `expand`(E0)가 운영 함수 둘에 같은 설정을 붙이며, 되돌리기 셸 단계가 다시 만든 `conversation_json_matches`에도 붙인다. 복원 뒤에는 `db/026`을 다시 실행하고 `post_restore_privileges.sql`로 함수 PUBLIC 실행 권한을 회수한 뒤 점검한다(`--no-privileges` 복원은 함수 권한을 되살리지 않는다). `rd_test7.sh`가 네 경우(새 기준선 · 이전 SQL 뒤 · 되돌린 뒤 · 이전 전 옛 구조)의 왕복을 확인한다.

## 데이터 손실 가드 (11-11)
- 되돌릴 수 없는 삭제 앞에 사전 점검(`DO` 블록)이 있어 **버려지는 데이터가 있으면 명시 확인 없이는 `EXCEPTION`으로 중단**한다(트랜잭션 전체 롤백). 점검 수치는 `NOTICE`로 찍힌다. 확인하려면 같은 `psql` 세션에서 먼저 `SET`한다: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SET app.ack_drop_display_name='yes'" -f db/migrations/migrate_prod_2_contract_p1.sql`
- `2_contract_p1`: `users.display_name`에 값이 있으면 `app.ack_drop_display_name`, `quotes` · `approved_cases`의 snapshot이 `approvals.snapshot`과 다르면(NULL은 통과) 확인 변수로도 못 넘기고 중단.
- `3_contract_p2`: `sojafit_agent.approvals`에 행이 있으면 `app.ack_drop_agent_approvals`, 되살릴 수 없는 `sojafit_agent.circuits` 사본(thread · public 회로로 이어지지 않음, `netlist`가 빈 글자가 아님, `filename`이 프로젝트 이름과 다름)이 있으면 `app.ack_drop_agent_circuits`.
- `2b`: `auth_google_pending`에 행이 있으면 `app.ack_drop_google_pending`.
- 시험: `db/redesign/verify/rd_test6.sh`가 가짜 운영 구조에서 정상 데이터는 통과하고 위반 데이터(품번 괄호 · 쉼표 · 전각 · 빈 문자열 포함)는 막히는 것을 확인한다.

## 파일
- `migrate_prod_1_expand.sql` — 1단계 expand
- `migrate_prod_2_contract_p1.sql` — 2단계 contract P1(승인 칸 NOT NULL, 스냅샷 복사본 · 미사용 칸 제거, 단순 검사)
- `migrate_prod_2b_optional_drop_dead_auth.sql` — 선택 2b(`auth_google_pending` 삭제) **[경고] 2026-11-12(#109)부터 이 표는 사용 중이다. 실행하면 운영 표가 삭제되므로 실행하지 않는다.**
- `migrate_prod_3_contract_p2.sql` — 3단계 contract P2(분석 회로 사본 · 죽은 승인 표 제거, 삭제 CASCADE, 체크포인트 삭제 트리거, 청소 함수 교체)
- `migrate_prod_4_rollback.sql` — 되돌리기(B2b · B2 · B1 · A 절)
- `precheck_1_before_expand.sql` · `precheck_2_before_p1.sql` · `precheck_3_before_p2.sql` · `precheck_4_before_2b.sql` — 단계 직전 읽기 전용 점검(개수만 출력)
- `post_restore_privileges.sql` — 백업 복원 직후(`db/026` 재실행 뒤) 함수 PUBLIC 실행 권한 회수 + 권한 점검(어긋나면 EXCEPTION)
- `MIGRATIONS.md` — 이 문서
