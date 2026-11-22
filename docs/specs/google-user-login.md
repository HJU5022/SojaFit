# Google 일반 사용자 로그인

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 "Google 가입 · 로그인"과 8.6절). 이 문서는 일반 사용자 가입·기존 계정 연결의 상세
- 관련 문서: [google-admin-login.md](google-admin-login.md)(OIDC 검증, 관리자 연결 승인), [login-auth.md](login-auth.md), [frontend-screen-redesign.md](../archive/frontend-screen-redesign.md)
- 화면 열 주의: 2026-11-16 새 화면 교체로 이 문서가 가리키던 옛 화면 파일(`pages/` · `components/` · `hooks/` · `api/`)과 그 시험은 없다. 새 화면의 대응 파일은 [frontend/src/SRC.md](../../frontend/src/SRC.md), 새 화면 시험은 [frontend/tests/TESTS.md](../../frontend/tests/TESTS.md). 서버 쪽 계약의 정본은 [SPEC.md](../../SPEC.md)다

## Why

연결된 Google 신원만 로그인할 수 있으면 처음 오는 일반 사용자는 이용할 수 없다. 목표는 일반 사용자의 최초 가입에 운영자 개입 0회, 기존 사용자 데이터의 자동 병합 0건이다.

## Goal

- 신규 Google 사용자는 본인 선택으로 `user` 계정과 서버 세션을 얻는다.
- 기존 계정 연결에는 기존 비밀번호 재확인이 필요하다. 관리자 연결은 운영자 CLI만 허용한다.
- 비밀번호 로그인, 관리자 승인·철회, state·PKCE·nonce 검증은 유지한다.
- 범위 밖: GCP 설정, 새 인증 공급자, 비밀번호 재설정([login-auth.md](login-auth.md)).

## What

| 상황 | 동작 |
|---|---|
| 연결된 활성 계정이 Google 로그인 | 콜백에서 바로 세션 발급 |
| 연결 없음 | 콜백이 15분 유효 연결 요청을 만들고 `/login?google=finish`로 보낸다. 계정은 만들지 않는다 |
| 새 이메일, 화면의 `Google 계정으로 가입` | 비밀번호 없는 `role=user` 계정을 만들고 Google 신원을 연결한 뒤 세션 발급 |
| Google 이메일이 기존 계정의 로그인 이메일과 같음, 가입 시도 | 409. 자동 연결·생성 없음 |
| 기존 활성 일반 계정의 이메일·비밀번호 입력, `기존 계정에 연결` | 비밀번호를 다시 확인한 뒤 연결하고 세션 발급. 이미 로그인한 브라우저도 비밀번호를 다시 받는다. 기존 id·프로젝트 유지 |
| 관리자 계정 | 연결 거절(409). 운영자 승인만 가능([google-admin-login.md](google-admin-login.md)) |
| 비활성 계정, 이미 다른 Google 신원에 연결된 계정, 이미 연결된 신원 | 연결 거절, 세션 없음 |
| 만료·소비된 연결 요청, 쿠키 없음, Origin 불일치, 알 수 없는 필드 | 계정·연결 생성 없음 |

Google 이메일과 기존 계정의 이메일이 달라도 연결할 수 있다. 이 경우 두 신원을 각각 확인한 일반 계정 연결만 허용한다. 이메일 일치만으로 연결하지 않는다. 별도 약관·수집 동의 체크는 없다. 구버전의 `consent` 값은 선택 호환 필드로만 받고 저장하거나 동의 증거로 쓰지 않는다. 개인정보 안내는 `/privacy`에서 읽는다.

### 로그인 화면

- 서버의 Google 상태가 enabled일 때만 `Google 로그인` 버튼을 이메일 폼 위에 보이고 `GET /api/auth/google/start`로 보낸다. 미설정이거나 조회에 실패하면 OAuth 진입을 만들지 않는다.
- `/login?google=finish`에서는 숨긴 `GET /api/auth/google/onboarding`으로 마스킹된 이메일을 조회한다. 조회가 끝나기 전, 실패, 만료 상태에서는 가입·연결 버튼을 막고 `Google 인증 다시 시작` 링크를 보인다. 늦은 응답은 폐기한다.
- 같은 화면의 이메일·비밀번호 제출은 `finish` 상태에서 `기존 계정에 연결`로 바뀐다.
- 데모 사용자 버튼과 데모 상태 조회는 Vite 개발 빌드에서만 있다. production 빌드는 서버가 데모를 켜 놓았어도 보이지 않는다.

## How

| 항목 | 구현 | 근거 |
|---|---|---|
| 연결 요청 | issuer·sub·이메일을 `auth_google_pending`에 15분 저장. 브라우저에는 `sojafit_google_pending` HttpOnly 쿠키(경로 `/api/auth/google`). URL·JS에 식별 토큰을 내보내지 않는다 | `backend/auth.py` `request_google_link`, `backend/api/auth.py` |
| 가입·연결 API | 숨긴 `GET /api/auth/google/onboarding`(마스킹 이메일), `POST /api/auth/google/signup`(빈 객체 또는 호환 `consent`만), `POST /api/auth/google/link`(`{email, password}`). 두 POST 모두 Origin을 확인하고 추가 필드를 거절하며 서버 세션 쿠키를 발급. 모델·오류 코드는 SPEC 4절 표가 정본 | `backend/api/auth.py` |
| 원자성 | 연결 요청 소비, 신원 연결, 세션 발급을 한 트랜잭션에서 처리. `(issuer, sub)`·`user_id` 유일 제약 위반은 409 | `auth.complete_google_user` |
| 비밀번호 칸 | 새 Google 계정은 `password_hash` NULL. `db/027_google_user_login.sql`이 NOT NULL을 풀고 CHECK 제약 `users_admin_password_required`(NULL이면 role은 user)를 둔다. 가짜 해시를 저장하지 않는다. NULL 계정의 비밀번호 인증은 항상 실패하며 동일한 scrypt 비용을 쓴다 | `db/027_google_user_login.sql`, `auth.authenticate` |
| pending 표 | 새 기준선(`db/020_service_baseline.sql`)에는 표가 없어 `db/030_google_onboarding.sql`이 만든다. 027·029·030은 기존 사용자·신원 연결·세션을 바꾸지 않는 추가 SQL이다. 기존 DB는 앱 배포 전에 백업과 적용 대상을 확인하고 SQL을 먼저 적용한다 | `db/030_google_onboarding.sql` |
| 가입 한도 | 새 계정 생성은 이메일 가입 확정과 같은 IP별 UTC 하루 한도를 공유한다(값은 SPEC 8.6절). 연결의 비밀번호 검사는 계정·IP 실패 잠금과 동시 scrypt 제한을 재사용하고 성공 세션은 연결 트랜잭션에서만 발급 | `auth._signup_slot`, `auth.authenticate(issue_session=False)` |
| 토큰 | Google 토큰은 저장하지 않는다 | `auth.fetch_google_identity` |

## AC

| # | Given - When - Then | 테스트 |
|---|---|---|
| 1 | 새 Google 신원, 가입 - user·NULL 비밀번호·세션 생성, 같은 신원 재로그인은 같은 계정 | `tests/api/test_google_users.py::test_new_google_user_has_no_password_and_reuses_same_identity` |
| 2 | 같은 이메일의 기존 계정 - 자동 연결 없음. 비밀번호를 확인한 일반 계정만 연결 | `tests/api/test_google_users.py::test_same_email_never_auto_links_but_password_verified_user_can_link` |
| 3 | 관리자·비활성 계정 - 자가 연결 거절 | `tests/api/test_google_users.py::test_admin_or_disabled_account_is_not_self_linked` |
| 4 | 만료·이미 연결된 신원 - 새 세션 없음 | `tests/api/test_google_users.py::test_expiry_and_existing_binding_never_create_new_session` |
| 5 | 이메일 가입과 Google 가입의 합계가 한도에 닿음 - 429 | `tests/api/test_google_users.py::test_google_and_password_signup_share_ip_limit` |
| 6 | 비밀번호 재확인 전 - 세션 미발급, 틀린 비밀번호 거절 | `tests/api/test_google_users.py::test_google_link_rechecks_password_and_does_not_issue_session_first`, `::test_http_link_requires_password_and_keeps_existing_account` |
| 7 | Origin 불일치·쿠키 없음·잘못된 필드 - DB 처리 전 거절 | `tests/api/test_google_users.py::test_google_completion_checks_origin_before_database`, `::test_google_signup_rejects_invalid_legacy_fields` |
| 8 | 같은 신원의 동시 가입 - 중복 연결 없음 | `tests/api/test_google_users.py::test_concurrent_signup_cannot_bind_same_google_identity_twice` |
| 9 | NULL 비밀번호 계정 - 비밀번호 인증 실패 | `tests/api/test_google_users.py::test_passwordless_google_account_cannot_authenticate_with_a_password` |
| 10 | 027 SQL - 기존 비밀번호 보존, 반복 적용 가능, 관리자는 비밀번호 필요 | `tests/api/test_google_users.py::test_migration_preserves_passwords_is_repeatable_and_requires_admin_password` |
| 11 | 연결 없는 콜백 - 브라우저에 묶인 완료 단계로 이동 | `tests/api/test_google_users.py::test_unlinked_callback_enters_browser_bound_completion` |
| 12 | 만료된 연결 요청 - 화면에서 가입·연결 버튼 차단 | (화면 시험은 11-16 교체로 지워짐) |
| 13 | Google 버튼은 있고, 데모 버튼은 서버가 데모 모드라고 답할 때만 보인다(11-16 새 화면 규칙) | (화면 시험은 11-16 교체로 지워짐) |

## 구현 상태

| AC | 상태 |
|---|---|
| 1~13 | 테스트 파일이 있다. DB를 쓰는 사례(`db` 픽스처)는 전용 시험 DB가 없으면 skip된다 |

## 한계

- 027 SQL은 기존 DB에서 자동 실행되지 않는다. 운영 DB의 적용 여부는 레포로 확인할 수 없다(미확인).
- NULL 비밀번호 계정이 생긴 뒤 NULL을 처리하지 못하는 구버전 `backend/auth.py`로 롤백하면 비밀번호 인증 오류가 날 수 있다. 계정 삭제나 임의 비밀번호 부여 없이 NULL 처리 호환성을 유지해야 한다.
- 실제 Google 왕복 성공 기록은 레포에서 확인하지 못했다(미확인). 화면·API 시험은 합성 응답이다.
- OIDC 공식 근거: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)(sub 기준 연결, issuer·aud·exp·서명·nonce 확인).
