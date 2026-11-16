# Google 관리자 연결과 OIDC 검증

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 "Google 가입 · 로그인"과 8.6절). 이 문서는 OIDC 검증, 관리자 최초 연결 승인, 연결 철회의 상세
- 관련 문서: [google-user-login.md](google-user-login.md)(일반 사용자 가입·연결), [login-auth.md](login-auth.md), [db/DB.md](../../db/DB.md)
- 화면 열 주의: 2026-11-16 새 화면 교체로 이 문서가 가리키던 옛 화면 파일(`pages/` · `components/` · `hooks/` · `api/`)과 그 시험은 없다. 새 화면의 대응 파일은 [frontend/src/SRC.md](../../frontend/src/SRC.md), 새 화면 시험은 [frontend/tests/TESTS.md](../../frontend/tests/TESTS.md). 서버 쪽 계약의 정본은 [SPEC.md](../../SPEC.md)다

## Why

- 대상: 개인 Google 계정으로 로그인하려는 관리자와 일반 사용자. 평가자는 운영 DB에 미리 만든 이메일·비밀번호 계정을 쓴다.
- 문제: Google이 확인한 신원과 SojaFit 계정의 연결을 이메일 일치만으로 만들면 다른 사람의 계정을 가로챌 수 있다. 관리자 권한은 특히 운영자 확인 없이 얻으면 안 된다.
- 지표: 미연결·미승인 Google 신원이 얻는 관리자 세션 0건, 회수된 계정에 남는 세션 0건.

## Goal

- 연결된 활성 계정(관리자·일반 사용자)은 Google 로그인으로 기존 서버 세션을 받는다.
- 관리자 최초 연결은 운영자 CLI 승인만 허용한다. 일반 사용자의 가입·연결은 [google-user-login.md](google-user-login.md)가 정한다.
- Google 로그인이 설정되지 않은 환경에서도 비밀번호 로그인이 동작한다.
- 범위 밖: 업무 데이터 소유권 연결, Supabase Auth 전환, 운영 배포 자동화.

## What

### 로그인 결과

| 상황 | 결과 |
|---|---|
| `(issuer, sub)`가 연결된 활성 계정 | 기존 서버 세션(8시간, [login-auth.md](login-auth.md))을 발급하고 `/login`으로 보낸다. 계정 행을 늘리지 않는다 |
| 연결이 없는 신원 | 세션 없이 15분 유효한 연결 요청(`auth_google_pending`)을 만들고 `/login?google=finish`로 보낸다 |
| 연결된 계정이 비활성 | 세션 없음 |
| state·PKCE·nonce·서명·발급자·대상·만료 중 하나라도 틀림, Google·DB 오류, 설정 누락 | 세션 없이 `/login?google=error` |

이메일 일치만으로 연결하지 않는다. 연결된 신원은 이메일과 상관없이 `sub`로 찾는다.

### 관리자 최초 연결

1. 관리자가 Google 로그인을 하면 연결 요청이 만들어지고 `/login?google=finish`로 간다. 이 경로의 일반 가입은 409, 비밀번호 연결은 관리자라서 거절된다(`backend/auth.py` `complete_google_user`).
2. 같은 브라우저의 `GET /api/auth/google/pending`이 확인된 이메일과 요청 번호를 HTML로 보여 준다. 사용자는 이를 신뢰된 경로로 운영자에게 전달한다.
3. 운영자가 `uv run python -m backend.auth --approve-google`로 요청 번호, 기존 관리자 ID, 확인한 이메일을 입력한다. 승인은 요청·대상 행을 잠그고 활성 관리자·만료·중복·이미 연결 여부를 다시 확인한 뒤 연결과 요청 소비를 한 트랜잭션으로 처리한다. 이메일이 요청과 다르면 거절한다.
4. 승인 뒤 같은 `sub`의 Google 로그인이 관리자 세션을 발급한다. 비밀번호 로그인도 계속 쓸 수 있다.

### 연결 철회와 비활성화

| 명령 | 효과 |
|---|---|
| `--revoke-google-user-id <ID>` | Google 연결과 그 계정의 모든 세션을 삭제한다. 비밀번호 로그인 정책은 그대로다. ID를 다시 입력해 확인한다 |
| `--disable-admin-id <ID>` | 관리자를 비활성화하고 모든 세션을 폐기한다. 마지막 활성 관리자는 비활성화할 수 없다. 계정 행을 잠가 동시 로그인과 경합해도 폐기 뒤 세션이 남지 않는다 |

비활성화 뒤 재활성화만으로 이전 세션이 복구되지 않는다.

## How

| 항목 | 구현 | 근거 |
|---|---|---|
| 시작 | `GET /api/auth/google/start`: state·브라우저 값·PKCE verifier·nonce를 만들어 `auth_google_states`에 해시와 함께 10분 저장. 브라우저에는 HttpOnly·SameSite=Lax 임시 쿠키(`sojafit_google_browser`, 경로 `/api/auth/google/callback`)를 둔다. 범위는 `openid email`, 응답은 303 | `backend/api/auth.py` `google_start` |
| 콜백 | state와 브라우저 쿠키를 함께 검증해 DB 행을 원자적으로 1회 소비(만료·재사용·불일치 거절). 인가 코드를 Google 토큰 엔드포인트에서 교환하고 JWKS로 ID 토큰을 검증 | `auth.consume_google_state`, `auth.fetch_google_identity` |
| ID 토큰 검증 | RS256 서명, issuer(`accounts.google.com`), audience(client ID), 만료·발급 시각(시계 오차 30초), nonce, `email_verified is True`, 유효한 이메일, `sub` 255자 이하. Google 액세스·ID·리프레시 토큰은 저장하지 않는다 | `auth.verify_google_id_token` |
| 연결 표 | `auth_google_identities`(`(issuer, subject)`와 `user_id`에 각각 유일 제약), `auth_google_pending`(request_id, issuer, subject, email, expires_at), `auth_google_states`. 모두 RLS를 켜고 PUBLIC·anon·authenticated 권한을 회수 | `db/020_service_baseline.sql`, `db/030_google_onboarding.sql` |
| 설정 | `GOOGLE_AUTH_ENABLED=1`과 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`이 모두 있어야 켜진다. 콜백 주소는 `AUTH_ORIGIN` + `/api/auth/google/callback`. 비밀은 실행 환경으로 주입하며 저장소에는 이름만 둔다 | `backend/api/auth.py` `google_enabled`, `.env.example` |
| 쿠키 | 연결 요청 쿠키 `sojafit_google_pending`은 경로 `/api/auth/google`, 15분. `AUTH_ORIGIN`이 https면 Secure. 응답에 `Cache-Control: no-store`, `Referrer-Policy: no-referrer` | `backend/api/auth.py` |
| 접속 로그 | uvicorn 접속 로그에서 모든 경로의 쿼리를 `?<redacted>`로 바꿔 콜백의 `code`·`state`가 남지 않는다. 요청 경로와 상태 코드는 남는다. Cloud Run 요청 로그는 이 필터 밖이다 | `backend/logs.py` `hide_query` |
| 로그인 화면 | 설정이 켜져 있을 때만 `Google 로그인` 버튼(GET `/api/auth/google/start`)을 보인다. 설정 조회 실패 시 안내 문구를 보이고 이메일 로그인은 유지한다 | `frontend/src/Auth.tsx` |
| 운영 주의 | `db/migrations/migrate_prod_2b_optional_drop_dead_auth.sql`은 `auth_google_pending`을 삭제하므로 실행하지 않는다 | `db/migrations/MIGRATIONS.md` |

실제 Gmail 주소와 `sub`는 문서·로그·테스트 데이터에 넣지 않고 테스트는 합성 값을 쓴다.

## AC

| # | Given - When - Then | 테스트 |
|---|---|---|
| 1 | 승인된 활성 관리자 둘, 각자 Google 로그인 - 각자 관리자 세션 | `tests/api/test_auth.py::test_two_approved_google_admins_get_isolated_sessions` |
| 2 | 연결 전 관리자와 같은 이메일의 Google 신원 - 세션 없음, 명시 승인 필요 | `tests/api/test_auth.py::test_unlinked_google_admin_with_same_email_requires_explicit_approval` |
| 3 | 승인 CLI - 요청 번호·관리자 ID·이메일을 명시해야 한다 | `tests/api/test_auth.py::test_google_approval_cli_requires_explicit_email_and_user_id` |
| 4 | 연결 철회 - 연결과 세션 삭제 | `tests/api/test_auth.py::test_google_revocation_clears_the_link_and_sessions` |
| 5 | 관리자 비활성화 - 모든 세션 폐기 | `tests/api/test_auth.py::test_admin_deactivation_revokes_sessions` |
| 6 | state·브라우저 값 - 같은 브라우저에서 한 번만 소비 | `tests/api/test_auth.py::test_google_state_is_bound_to_browser_and_consumed_once` |
| 7 | ID 토큰의 서명·issuer·audience·만료·nonce·`email_verified` 중 하나 오류 - 거절 | `tests/api/test_auth.py::test_google_id_token_verifies_signature_and_identity_claims` |
| 8 | 토큰 교환 - 고정된 Google 엔드포인트로 PKCE 전송 | `tests/api/test_auth.py::test_google_token_exchange_sends_pkce_to_fixed_google_endpoint` |
| 9 | Google 미설정 - 비활성 | `tests/api/test_auth.py::test_google_oauth_is_disabled_without_configuration` |
| 10 | 콜백 쿼리 - uvicorn 접속 로그에 남지 않음 | `tests/api/test_auth.py::test_google_callback_query_is_not_written_to_uvicorn_access_logs` |
| 11 | Google 표 - 공개 접근 제한, 중복 연결 거부 | `tests/api/test_auth.py::test_google_auth_schema_restricts_public_access_and_duplicate_bindings` |
| 12 | 비활성 Google 사용자 - 세션 없음 | `tests/api/test_google_users.py::test_disabled_google_user_cannot_get_session` |

## 구현 상태

| AC | 상태 |
|---|---|
| 1~12 | 테스트 파일이 있다. DB를 쓰는 사례는 전용 시험 DB가 없으면 skip된다 |

## 한계

- 로그인 화면은 `GET /api/auth/google/pending` 링크를 제공하지 않는다(`frontend/src`에서 해당 경로 문자열 검색 결과 없음). 관리자는 이 주소를 직접 열어 요청 번호를 확인해야 한다.
- 관리자 복구 담당자와 마지막 관리자 잠금 방지 절차는 레포에 정해진 기록이 없다. CLI는 마지막 활성 관리자의 비활성화만 막는다.
- 만료된 연결 요청·상태 행은 관련 요청 때 지운다. 유휴 중에 지우는 정리 작업은 없다.
- 현재 Google Cloud 앱 게시 상태, 승인된 리디렉션 URI, 비밀 접근 권한, Cloud Run 요청 로그의 콜백 쿼리 보호는 레포로 확인할 수 없다(미확인).
- 실제 Google 계정으로 로컬·배포 주소의 콜백 왕복에 성공한 기록은 레포에서 확인하지 못했다(미확인). 시험은 합성 응답이다.
- 개인정보 처리 항목·보관·위탁·국외 이전은 [개인정보처리방침](../../frontend/src/Account.tsx)(`PrivacyText`, 2026-11-16 시행)에 적었다. Google 가입은 Google이 확인한 이메일과 계정 식별값을 받는 수집 항목으로 적었다.
