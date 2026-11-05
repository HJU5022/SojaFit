# Supabase 인증 테스트 프로젝트 기록

> 2026-11-04 후속 확인: 아래 RLS 미적용·공개 역할 권한 관련 설명은 변경 전 기록이다. 현재 세 인증 표에 RLS가 켜져 있고 `anon`·`authenticated`의 SELECT 실효 권한은 없다. `restrict_auth_tables_public_access` 마이그레이션을 확인했다. 세 표의 행은 각각 0건이다. HTTP Data API 차단과 실제 로그인 테스트는 아직 확인하지 않았다.

## 상태

- 확인일: 2026-11-04
- 상태: 프로젝트 생성 및 인증 스키마 적용 완료. 합성 계정·애플리케이션 서버 테스트는 RLS/권한 점검 후속으로 보류.
- 목적: Cloud Run 운영 DB와 분리된 Supabase PostgreSQL에서 인증 스키마와 FastAPI 인증 흐름을 시험한다.
- 범위: 인증 표 3개만 사용한다. 실제 개인정보, 업무 데이터, 코퍼스, 임베딩 데이터는 적재하지 않는다.

## 프로젝트

| 항목 | 확인값 |
|---|---|
| 조직 | `SimonTH-0912's Org` (Free) |
| 프로젝트 | `sojafit-auth-test` |
| 프로젝트 ref | `tdtiabsgldkusyfyfysf` |
| 리전 | `ap-northeast-2` (서울) |
| 상태 | 생성 직후 `ACTIVE_HEALTHY` |
| 생성 비용 견적 | 월 `$0` |

Free 프로젝트는 사용 한도와 비활성 일시 중지 조건을 따른다. 비용은 생성 시점 도구 견적이며 장기 사용·초과 사용 비용을 보장하지 않는다. [요금 안내](https://supabase.com/pricing), [Free 프로젝트 비용 FAQ](https://supabase.com/kb/faqs/platform/database-only-cost).

## 확인한 과정과 결과

1. 조직을 확인하고 프로젝트별 생성 비용을 조회했다. 사용자 선택 후 월 `$0` 견적을 확인하고 서울 리전에 생성했다.
2. 생성 직후 `public` 테이블과 마이그레이션이 없는 것을 확인했다.
3. 설치된 확장(`pg_extension`)을 확인했다. `vector`는 사용할 수 있는 확장 목록에는 있었지만 설치되어 있지 않았다. 이번 작업에서 pgvector를 설치·조회·수정하지 않았다.
4. 저장소의 인증 SQL만 `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql` 순으로 migration `sojafit_auth_test_schema`에 적용했다.
5. 테이블 정의·마이그레이션·권한·보안 advisor를 점검했다. 세 인증 표의 컬럼/기본값은 저장소 SQL과 맞고, 테이블 행은 아직 0건이다.

## 보안 점검 및 현재 차단

`users`, `auth_sessions`, `auth_login_attempts` 세 표 모두 RLS가 꺼져 있다. `anon`과 `authenticated` 역할에 각 표의 `SELECT`, `INSERT`, `UPDATE`, `DELETE`를 포함한 권한이 부여되어 있고, Supabase security advisor는 `rls_disabled_in_public`을 `ERROR`로 보고했다. 따라서 합성 계정도 아직 적재하지 않았다.

Supabase advisor는 RLS를 켜는 제안 SQL을 제공했지만, Supabase 지침에 따라 자동 실행하지 않았다. 앱은 Supabase Auth가 아니라 자체 세션 쿠키를 사용하므로 `auth.uid()` 기반 정책을 임의로 만들지 않는다. 외부 API 역할의 권한 회수/RLS 적용 방식과 서버 DB 역할을 정한 뒤 테스트를 재개해야 한다. [RLS 보안 안내](https://supabase.com/docs/guides/database/postgres/row-level-security), [advisor 설명](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public).

```sql
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_login_attempts ENABLE ROW LEVEL SECURITY;
```

위 SQL은 advisor의 RLS 권고안이다. 적용만으로 anon/authenticated 접근 경계를 정했다고 단정하지 말고, 실제 권한 및 백엔드 DB 역할도 확인해야 한다. 현재 `anon`/`authenticated`에 직접 테이블 권한도 있으므로 접근 정책은 적용 전에 함께 검토한다.

## FastAPI 연결 테스트 절차 (보류)

프로젝트 생성 도구에서는 애플리케이션용 DB 비밀번호/연결 문자열을 문서화하지 않았다. 비밀값을 채팅·저장소에 옮기지 말고, 승인된 비밀 저장 위치에 `TEST_AUTH_DATABASE_URL`을 설정해야 한다. 테스트가 끝나면 프로세스 환경변수에서 지운다.

RLS/권한 결정을 마친 뒤 별도 PowerShell 세션에서 아래 기존 테스트를 실행한다. URL 값은 콘솔에 출력하지 않는다.

```powershell
$env:TEST_AUTH_DATABASE_URL = '<승인된 테스트 프로젝트 DB URL>'
uv run --no-sync pytest -q -rs tests/api/test_auth.py -p no:cacheprovider
Remove-Item Env:TEST_AUTH_DATABASE_URL
```

프로젝트 URL·DB 자격 증명을 Cloud Run에 연결하지 않았고, Cloud Run 서비스 설정이나 `DATABASE_URL`은 변경하지 않았다. 위 테스트 명령은 아직 Supabase 프로젝트를 대상으로 실행하지 않았다.

## 재개 기준

- Supabase `anon`/`authenticated`의 직접 표 권한 및 RLS 동작이 안전하게 제한됨.
- 신뢰된 백엔드 DB 역할이 인증 SQL을 읽고 쓸 수 있는지 확인됨.
- `TEST_AUTH_DATABASE_URL`을 비밀값 노출 없이 테스트 프로세스에 공급할 수 있음.
- 합성 A/B/admin 계정만 만든 뒤 기존 DB 인증 테스트가 skip 없이 통과함.
- 확장 목록 재확인에서 `vector`가 설치되지 않았고 코퍼스/업무 표를 변경하지 않았음.
