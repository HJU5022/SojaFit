# db/legacy

## 역할
- 이 폴더: 서비스 표 기준선(`db/020_service_baseline.sql`)으로 교체하기 전의 옛 증분 SQL을 **이력으로만** 둡니다(11-11 재설계 M 단계). Postgres 이미지는 `db/` 바로 아래 파일만 실행하므로 여기 있는 SQL은 자동 실행되지 않습니다.
- 넣는 것: 기준선이 대체한 옛 증분 SQL(번호 `003`~`025` · `027`~`029`). 파일은 옛 이름 그대로 두어 기록(작업 기록 · ADR · 운영 적용 이력)의 번호와 맞춥니다.
- 넣지 않는 것: 새 DB에서 실행할 SQL(`db/`), 운영 이전 SQL(`db/migrations/`). 이 폴더 파일은 고치지 않습니다(고치면 "옛 체인 + 이전 SQL = 기준선" 증명이 흔들립니다).
- 담당: 서비스·운영
- 쓰는 곳: `scripts/db/verify_chain/verify_chain.sh`(옛 체인 000~026을 만들어 운영 이전 SQL을 적용한 결과와 기준선을 비교), 운영 이전 되돌리기(`db/migrations/migrate_prod_4_rollback.sql`이 `019` · `023` · `024` · `025`의 옛 정의를 다시 읽음), `scripts/db/verify_redesign/`.

## 파일
- `007_demo_accounts.sql` — 옛 데모 계정 시드 원본. 현재 앱의 지연 데모 생성을 사용하므로 초기화에서 실행하지 않는다.
- `003_auth.sql` · `005_auth_attempt_window.sql` · `006_user_roles.sql` · `021_auth_ip_limits.sql` — 사용자 · 세션 · 로그인 시도 · 역할 · IP 한도 표
- `010_google_auth.sql` — Google 로그인 상태 · 승인 대기(`029`가 삭제) · 계정 연결 표
- `013_agent_memory.sql` · `014_thread_inputs.sql` · `015_analysis_limits.sql` · `016_memory_controls.sql` · `017_analysis_events.sql` · `022_token_limits.sql` · `023_retention.sql` — `sojafit_agent` 분석 서비스 표 · 사용량 · 청소 함수
- `018_projects.sql` · `019_conversations.sql` · `020_approvals_quotes.sql` — 프로젝트 · 회로 · 대화 · 실행 · 메시지 · 승인 · 견적 · 승인 사례
- `024_projects_demo_c01.sql` · `025_runs_safe_result_preferred_mount.sql` — 11-10 긴급 수정(데모 목록 · 결과 형식 CHECK, 기준선은 단순 CHECK로 대체)
- `027_service_redesign_p1.sql` · `028_service_redesign_agent.sql` · `029_drop_google_pending.sql` — 재설계 1/3 · 2/3 · 3/3(기준선이 최종 결과를 한 파일로 만든다)
- `LEGACY.md` — 이 문서
