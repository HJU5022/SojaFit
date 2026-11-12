# Supabase 인증 테스트 프로젝트 점검 결과

- 상태: 이력 (2026-11-04 시험용 프로젝트 점검. 운영 DB는 이 프로젝트가 아니다)
- 기준일: 2026-11-04
- 정본 여부: 비정본(정본: 운영 DB의 공개 역할 권한·RLS는 [db/026_revoke_public_grants_and_rls.sql](../../db/026_revoke_public_grants_and_rls.sql), DB 시험 환경은 [DB 안내](../../db/DB.md))
- 관련 문서: [인증 로그인 검증](auth-login-verification.md)

## 1. 질문과 결론

질문: Cloud Run 운영 DB와 분리된 Supabase PostgreSQL(Free)에서 저장소의 인증 SQL이 적용되고 FastAPI 인증 시험을 돌릴 수 있는가.

| 항목 | 값 | 근거 |
|---|---|---|
| 프로젝트 | 시험 전용 Supabase Free 프로젝트 1개, 리전 `ap-northeast-2`(서울), 생성 직후 `ACTIVE_HEALTHY`, 생성 비용 견적 월 $0 | 생성 시점 도구 출력(저장소에 없음) |
| 적용한 SQL | `db/legacy/003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql` 순서, 마이그레이션 1건 | 파일 존재 [실측] |
| 스키마 대조 | 세 인증 표(`users`, `auth_sessions`, `auth_login_attempts`)의 컬럼·기본값이 저장소 SQL과 일치, 행 0건 | 점검 당시 기록 |
| 설치된 확장 | `vector`는 사용 가능 목록에만 있고 설치되지 않음. pgvector는 설치·조회·수정하지 않음 | 점검 당시 기록 |
| 범위 | 인증 표 3개만. 개인정보, 업무 데이터, 코퍼스, 임베딩 데이터는 적재하지 않음 | |
| 보안 점검 결과(2026-11-04 최초) | 세 표 모두 RLS 꺼짐. `anon`·`authenticated`에 `SELECT`·`INSERT`·`UPDATE`·`DELETE` 권한. security advisor가 `rls_disabled_in_public`을 `ERROR`로 보고 | 점검 당시 기록 |
| 같은 날 후속 | `restrict_auth_tables_public_access` 마이그레이션 뒤 세 표에 RLS 켜짐, `anon`·`authenticated`의 SELECT 실효 권한 없음, 세 표 행 0건 | 점검 당시 기록 |
| 시험 실행 | 합성 계정 적재와 `tests/api/test_auth.py` 실행은 하지 않았다 | |
| 운영 연결 | 시험 프로젝트의 URL·자격 증명을 Cloud Run에 연결하지 않았고 운영 `DATABASE_URL`을 바꾸지 않았다 | |

## 2. 현재 서비스와의 관계

- 서버는 DB 소유자 연결(`DATABASE_URL`)로만 접속하고 Supabase Data API·공개 역할을 쓰지 않는다. 운영 DB의 공개 역할 권한 회수와 앱 표 RLS는 `db/026_revoke_public_grants_and_rls.sql`이 맞춘다(해당 파일 머리 주석).
- 앱은 Supabase Auth가 아닌 자체 세션 쿠키를 쓰므로 `auth.uid()` 기반 정책은 만들지 않았다.
- 인증 시험은 `TEST_AUTH_DATABASE_URL`(비밀값, 저장소에 쓰지 않음)을 쓰는 DB 시험으로 이어진다: `tests/api/test_auth.py` 등([API 시험 안내](../../tests/api/API.md)).

## 3. 한계

1. 프로젝트 점검 결과(스키마 대조, RLS·권한 상태, 확장 목록)는 점검 당시 기록이며 이 변환에서 재확인하지 않았다. 시험 프로젝트에 접근하지 않는다.
2. HTTP Data API 차단과 실제 로그인 시험은 확인하지 않았다.
3. 프로젝트 조직·식별자와 연결 정보는 문서에서 제거했다. 시험 프로젝트가 아직 존재하는지, Free 한도·비활성 일시 중지 조건에 걸렸는지 알 수 없다.
4. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` 권고안과 PowerShell 시험 절차는 위 후속 마이그레이션과 `db/026`로 대체되어 싣지 않았다.
