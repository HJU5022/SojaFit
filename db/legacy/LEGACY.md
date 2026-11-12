# db/legacy

## 역할
- 이 폴더: 서비스 표 기준선(`db/020_service_baseline.sql`)으로 교체하기 전의 옛 증분 SQL을 이력으로만 둔다. Postgres 이미지는 `db/` 바로 아래 파일만 실행하므로 여기 있는 SQL은 자동 실행되지 않는다([DB.md](../DB.md) "SQL이 실행되는 방식").
- 넣는 것: 기준선이 대체한 옛 증분 SQL(번호 `003`~`025` · `027`~`029`). 옛 이름 그대로 두어 작업 기록 · ADR · 운영 적용 이력의 번호와 맞춘다.
- 넣지 않는 것: 새 DB에서 실행할 SQL(`db/`), 운영 이전 SQL(`db/migrations/`). 이 폴더 파일은 고치지 않는다(고치면 "옛 체인 + 이전 SQL = 기준선" 증명이 흔들린다).
- 번호 겹침: `020`, `027`, `029`는 `db/` 바로 아래에 다른 파일이 있다([DB.md](../DB.md)의 번호 표).
- 담당: 서비스·운영
- 쓰는 곳: `scripts/db/verify_chain/verify_chain.sh`(옛 체인 000~026을 만들어 운영 이전 SQL을 적용한 결과와 기준선을 비교), 운영 이전 되돌리기(`db/migrations/migrate_prod_4_rollback.sql`이 `019` · `023` · `024` · `025`의 옛 정의를 다시 읽음), `scripts/db/verify_redesign/`.

## 파일

| 파일 | 묶음 | 설명 |
|---|---|---|
| `LEGACY.md` | 폴더 설명 | 이 문서 |
| `003_auth.sql` | 인증 | `users`(계정), `auth_sessions`(세션 토큰 해시), `auth_login_attempts`(로그인 실패 횟수·잠금) |
| `005_auth_attempt_window.sql` | 인증 | `auth_login_attempts`에 실패 집계 창 시작 시각 `window_started_at` 추가(15분 후 횟수 재집계) |
| `006_user_roles.sql` | 인증 | `users`에 역할 열 `role`(admin \| user) 추가 |
| `007_demo_accounts.sql` | 인증 | 로컬 Compose 데모 계정 시드 원본. 현재는 앱의 지연 데모 생성을 사용해 초기화에서 실행하지 않음 |
| `010_google_auth.sql` | 인증 | Google 로그인 상태 · 승인 대기(`029`가 삭제) · 계정 연결 표 |
| `013_agent_memory.sql` | 분석 서비스 | 비공개 `sojafit_agent` 스키마의 업로드 · thread · 대화 이력 · 승인 원본 |
| `014_thread_inputs.sql` | 분석 서비스 | `threads.input_record`(nullable JSONB) 추가 |
| `015_analysis_limits.sql` | 분석 서비스 | 사용자별 UTC 일일 예약액 · 빈도 제한 표 |
| `016_memory_controls.sql` | 분석 서비스 | 승인 원본과 분리된 기억 참조 상태 · 사용자 정정 메모 |
| `017_analysis_events.sql` | 분석 서비스 | 요청 · thread · trace 연결, 처리 결과와 단계 지연(내용 제외) |
| `021_auth_ip_limits.sql` | 인증 | 클라이언트 IP 한도 표 2개 `auth_signup_attempts` · `auth_login_ip_attempts`(IP 원문 없이 키 해시만) |
| `022_token_limits.sql` | 분석 서비스 | 하루 LLM 토큰 상한의 예약 토큰 카운터: `analysis_usage.reserved_tokens` 열, `analysis_service_usage` 표 |
| `023_retention.sql` | 분석 서비스 | 보관 기간 청소 함수 2개 `purge_inactive_projects` · `purge_log_records`(SPEC 8.5) |
| `018_projects.sql` | 업무 표 | 사용자 소유 프로젝트와 정규화 회로 |
| `019_conversations.sql` | 업무 표 | 대화 · 실행 · 메시지 |
| `020_approvals_quotes.sql` | 업무 표 | 승인 · 견적 · 승인 사례 |
| `024_projects_demo_c01.sql` | 긴급 수정 | 데모 프로젝트 허용 목록에 c01(`attiny85_time_switch`) 추가. 기준선은 단순 CHECK로 대체 |
| `025_runs_safe_result_preferred_mount.sql` | 긴급 수정 | `runs_safe_result_check`의 판정 형식에 `preferred_mount` 추가. 기준선은 단순 CHECK로 대체 |
| `027_service_redesign_p1.sql` | 재설계 1/3 | 승인 칸 3개 · 스냅샷 복사본 제거 · 단순 CHECK · 세션 인덱스 · 적용 이력 표(`public` 표만) |
| `028_service_redesign_agent.sql` | 재설계 2/3 | 화면 대화 FK · 체크포인트 삭제 트리거 · 회로 사본/죽은 승인 표 제거 |
| `029_drop_google_pending.sql` | 재설계 3/3 | `auth_google_pending` 삭제. 기준선이 최종 결과를 한 파일로 만들며, 이 표는 `db/030_google_onboarding.sql`이 다시 만든다 |
