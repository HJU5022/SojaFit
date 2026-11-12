# 로그인과 사용자 식별

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 "인증 · 가입"과 8.6절). 이 문서는 구현 방식과 화면 동작의 상세
- 관련 문서: [google-admin-login.md](google-admin-login.md), [google-user-login.md](google-user-login.md), [api-error-contract.md](api-error-contract.md), [frontend-screen-redesign.md](frontend-screen-redesign.md), [user-thread-memory.md](user-thread-memory.md)

## Why

- 대상: 평가자와 일반 사용자. 이메일과 비밀번호 또는 Google로 로그인하고 자기 프로젝트·대화·기억·견적에만 접근해야 한다.
- 문제: 이메일 소유를 확인하지 않는 가입은 가짜 이메일 계정을 만든다. 공개 가입은 계정 대량 생성, 여러 계정에 나눠 보내는 비밀번호 대입, LLM 비용 소진에 노출된다.
- 지표: 인증 전 계정·세션 발급 0건, 토큰 재사용 성공 0건, 재설정 성공 뒤 본인 기존 세션 0건. 한도 값은 SPEC 8.6절이 정한다.

## Goal

- 로그인·로그아웃·이메일 인증 가입·비밀번호 재설정과 서버 측 사용자 식별을 제공한다.
- 기존 계정의 로그인·Google 연결·권한·업무 데이터를 바꾸지 않는다.
- 범위 밖: 관리자 가입 승인 화면, 비밀번호 변경(로그인 상태에서), 실제 메일 수신 보장.

## What

### 계정 종류

| 종류 | 만드는 방법 | 로그인 방법 |
|---|---|---|
| 사전 생성 계정(평가용, 관리자) | 운영자 CLI `python -m backend.auth` (`--role user\|admin`) | 이메일·비밀번호 |
| 이메일 가입 계정 | 메일 링크로 이메일 확인 후 비밀번호 설정. `role=user`, `email_verified_at` 기록 | 이메일·비밀번호 |
| Google 계정 | [google-user-login.md](google-user-login.md). `password_hash` NULL, `role=user` | Google |
| 데모 계정 A·B | `DEMO_MODE=1`에서 데모 버튼을 처음 누를 때 앱이 만든다(`auth.demo_session`). SQL 시드 없음 | 데모 버튼(비밀번호 로그인은 항상 실패) |

### 이메일 가입과 재설정

| 단계 | 동작 |
|---|---|
| 가입 요청 | `/signup`에서 이메일만 보낸다. 가입 가능한 이메일에만 메일을 보내지만 응답은 항상 같아 계정 존재를 드러내지 않는다. 계정·세션은 만들지 않는다 |
| 가입 확정 | 메일 링크의 `/verify-email#token=…`에서 비밀번호와 확인값을 입력해 `signup/confirm`을 호출한다. user 계정을 만들고 자동 로그인하지 않는다. 완료 화면은 로그인을 안내한다 |
| 재설정 요청 | `/reset-password`에서 이메일을 보낸다. 활성이고 scrypt 비밀번호를 가진 계정에만 메일을 보내며 응답은 항상 같다. Google 전용·비활성·없는 계정에는 비밀번호를 추가하거나 활성화하지 않는다 |
| 재설정 확정 | 새 비밀번호로 해시를 갱신하고 본인 `auth_sessions`와 로그인 실패 기록을 지운다. 다른 사용자의 세션·role·is_active·Google 연결은 바꾸지 않는다. 화면은 세션 만료 이벤트를 발생시킨다 |

경로·요청 모델·오류 코드는 SPEC 4절 표가 정본이다. 모든 요청은 Origin을 확인하고 모르는 필드를 422로 거절한다. 구버전 호환 필드 `consent`(선택 bool)는 저장하지 않고 동의 증거로 쓰지 않는다. 초기 요청에 비밀번호를 보내면 422다.

### 비밀번호 규칙

신규·재설정 비밀번호는 `backend/auth.py`의 `validate_new_password`가 검사한다(12~1024자, 공백뿐·숫자만·1~4자 단위 반복 거절). 길이 기준은 12자 하나다. 화면(`frontend/src/api/auth.ts`의 `newPasswordIssue`)은 같은 조건을 길이 하한→상한→공백뿐→숫자뿐→단순 반복 순으로 검사해 첫 이유 한 줄만 보인다. 기존 비밀번호 로그인에는 이 규칙을 적용하지 않는다. 운영자 CLI는 12자 이상, 1024바이트 이하만 확인한다.

### 로그인 실패 안내

서버는 계정 없음·비밀번호 오류·비활성·계정 잠금·IP 잠금에 같은 401 메시지를 낸다(존재 여부 보호). 화면은 `ApiError.code`와 요청 ID만 사용해 유형별 문구를 보인다.

| 오류 | 화면 안내 |
|---|---|
| 401 `UNAUTHORIZED` | 로그인 정보 확인, 탈퇴했거나 미가입이면 회원가입, Google 가입이면 Google 로그인(Google 활성 시), 반복 실패면 15분 뒤 재시도 |
| 422, 403, 429, 503·502·500, 시간 초과, 비JSON 응답, 연결 실패 | 인증 정보 오류로 오인하지 않는 유형별 문구 |
| 로그인 POST 성공 뒤 `me` 조회 실패 | 세션 확인 실패 문구. 로그인 POST를 자동 재전송하지 않는다 |

비밀번호는 실패 때 비우고 이메일은 유지한다. 본인 계정 삭제 직후의 로그인 화면은 삭제 완료·재가입 안내를 보인다. 이 상태는 `AuthProvider` 메모리에만 두고 다음 로그인·가입 성공, 로그아웃, 새 페이지에서 지운다.

### 세션과 접근 제한

| 항목 | 값 | 근거 |
|---|---|---|
| 세션 수명 | 절대 8시간, 유휴 2시간 | `backend/auth.py` (`INTERVAL '8 hours'`, `last_seen_at > … - INTERVAL '2 hours'`) |
| 세션 토큰 저장 | 난수 토큰의 HMAC-SHA256(`AUTH_SECRET`)만 저장. 키 없는 데모 모드는 SHA-256 | `session_token_hash` |
| 쿠키 | `sojafit_session`, HttpOnly, SameSite=Lax, `AUTH_ORIGIN`이 https면 Secure | `backend/api/auth.py` `set_session_cookie` |
| 비밀번호 저장 | scrypt(N=2^17, r=8, p=1), 임의 salt 16바이트 | `backend/auth.py` |
| 동시 scrypt 검증 | DB advisory lock 2칸. 칸이 모두 차면 503 | `authenticate`, `auth_email.complete` |
| 클라이언트 IP | Cloud Run(`K_SERVICE` 있음)은 `X-Forwarded-For`의 마지막 값, 그 밖은 소켓 주소. IP 원문은 저장하지 않고 키 해시만 저장 | `client_ip` |
| 로그인 실패 잠금 | 계정당·IP당 15분 집계 구간. 횟수는 SPEC 8.6절. 잠금 응답은 일반 실패와 같은 401. 로그인 성공은 IP 횟수를 지우지 않는다 | `auth_login_attempts`, `auth_login_ip_attempts` |
| 가입 확정 IP 한도 | UTC 하루. 횟수는 SPEC 8.6절. 이메일 가입과 Google 가입이 공유 | `auth_signup_attempts`, `_signup_slot` |
| LLM 토큰 한도 | 사용자·서비스 전체 하루 예약 합. 값은 SPEC 8.6절, 구현은 `backend/conversations/memory_service.py` | `db/legacy/022_token_limits.sql` |

로그인 이메일은 공백 없는 `local@domain.tld` 형태, 100자 이하다. 관리자 계정 목록은 로컬 부분을 첫 글자만 보이고 `***`로 가린다(예: `a***@example.test`). 형식이 깨진 기존 이메일은 목록 요청을 실패시키지 않고 `***`로 표시한다.

### 메일 인증 구현

| 항목 | 구현 | 근거 |
|---|---|---|
| 토큰 | 256bit 무작위(43자), DB에는 HMAC 해시만 저장. 이메일·목적별 활성 토큰 1개이며 재발급하면 이전 토큰 무효. 재발급은 직전 발급 60초 뒤부터 | `backend/auth_email.py` |
| 유효 시간 | 가입 60분, 재설정 15분 | `auth_email.request_email`, `backend/services/mail.py` |
| 링크 | `AUTH_ORIGIN`으로만 만들고 URL fragment로 전달. 화면은 토큰을 즉시 주소에서 제거하고 메모리에만 둔다. GET은 계정을 바꾸지 않고 최종 POST에서 행 잠금·트랜잭션으로 한 번만 소비 | `backend/services/mail.py`, `frontend/src/pages/EmailActionPage.tsx` |
| 발송 | 표준 `smtplib`로 Gmail SMTP. 포트 465(SSL) 또는 587(STARTTLS)만 허용, 인증서 검증, 소켓 timeout 10초, 자동 재시도 없음. `SMTP_USERNAME`이 발신 주소, `SMTP_PASSWORD`는 앱 비밀번호 | `backend/services/mail.py`, `.env.example` |
| 발송 실패 | 응답과 로그에 원문 예외·토큰을 남기지 않고 같은 조건부 안내를 반환. 메일 설정이 없으면 503 | `auth_email.request_email` |
| 한도 표 | `auth_email_send_limits`(이메일·IP·서비스 단위 요청 수). 값은 SPEC 4절 | `auth_email._reserve` |
| DB | `db/029_email_account_security.sql`: `users.email_verified_at`(nullable), `auth_email_challenges`, `auth_email_send_limits`. RLS 적용, PUBLIC·anon·authenticated 권한 회수 | `db/029_email_account_security.sql` |
| 전환 제약 | `db/manual/email_signup_cutover.sql`: 실행 시각 이전 계정은 유지하고 이후 신규 행은 `email_verified_at`을 요구하는 CHECK 제약 `users_email_signup_cutover`. 구버전 코드의 무인증 INSERT를 DB에서 차단. 제약을 제거해 인증 우회를 허용하는 롤백은 하지 않는다 | `db/manual/email_signup_cutover.sql` |
| 기존 계정 | NULL 인증 시각을 로그인 차단 근거로 쓰지 않는다 | `authenticate` |

### 데모 로그인

`GET /api/auth/demo`와 `POST /api/auth/demo-login`은 `DEMO_MODE=1`에서만 있고 아니면 본문을 읽기 전에 404다(코드 기본값은 `DEMO_MODE=1`, `backend/api/auth.py` `demo_mode`). 계정 이메일은 `demo-a@example.test`, `demo-b@example.test`이고 비밀번호 해시 칸에는 scrypt 형식이 아닌 표식(`auth.DEMO_PASSWORD_HASH`)을 넣는다. 표식이 없는 같은 이메일 계정·관리자·비활성 계정에는 세션을 주지 않는다(404). 로그인 화면의 데모 버튼은 Vite 개발 빌드(`import.meta.env.DEV`)에서만 보이고 production 빌드는 서버가 데모를 켜 놓았어도 보이지 않는다(`frontend/src/pages/LoginPage.tsx`). 로컬 UI 확인용 `VITE_DUMMY_AUTH=1`은 개발 서버에서만 더미 일반 사용자로 인증 경계를 통과시키며 production 빌드는 이 값을 무시한다.

### 관리자와 소유권

- `users.role`은 `admin`·`user`이고 기본값은 `user`다. 권한은 요청마다 DB에서 확인한다.
- 관리자 API는 계정 목록 조회와 일반 사용자의 활성 상태 변경만 한다. 관리자 계정의 상태 변경은 이 API 범위 밖이고 운영자 CLI가 한다. 비활성화와 세션 삭제는 한 트랜잭션이며 로그인과 경합하면 사용자 행을 잠근다.
- 세션에서 검증한 `users.id`만 프로젝트·대화·실행·승인·견적·사실 기억의 소유 식별에 쓴다. 클라이언트가 보낸 사용자 ID는 권한 근거가 아니다. 다른 사용자의 자료는 404다(SPEC 4절).

## AC

| # | Given - When - Then | 테스트 |
|---|---|---|
| 1 | 신규 이메일, 메일 요청 - 계정·세션 0건, 응답에 토큰 없음, DB에 평문 토큰 없음. 확정 뒤 user 계정 1개 | `tests/api/test_email_auth.py::test_signup_requires_email_proof_and_only_stores_token_hash` |
| 2 | 만료·위조·재발급 전·소비된 토큰, 완료 요청 - 400, 계정·암호·세션 변경 없음. 동시 소비 두 요청 중 성공 하나 | `tests/api/test_email_auth.py::test_expired_replaced_and_tampered_tokens_do_not_create_accounts`, `::test_token_consumption_is_atomic_for_concurrent_requests` |
| 3 | 기존 비밀번호 계정, 재설정 - 옛 비밀번호·본인 기존 세션 사용 불가, 새 비밀번호 로그인 가능. 타 사용자 세션 보존 | `tests/api/test_email_auth.py::test_reset_revokes_only_owners_sessions_and_old_password` |
| 4 | 없는·비활성·Google 전용 계정, 재설정 요청 - 동일 응답 | `tests/api/test_email_auth.py::test_nonexistent_inactive_and_google_only_accounts_have_same_response` |
| 5 | 약한 비밀번호·Origin 불일치·추가 필드·수신자 여러 명으로 해석되는 이메일 - DB 처리 전 거절 | `tests/api/test_email_auth.py::test_completion_rejects_weak_password_and_cross_origin_before_consumption`, `::test_email_requests_reject_ambiguous_recipient_headers` |
| 6 | 11자 비밀번호 - 가입·재설정 양쪽에서 거절, 12자는 길이 검사 통과 | `tests/api/test_email_auth.py::test_password_length_boundary_is_twelve_on_both_completion_routes` |
| 7 | 메일 설정 없음 - 두 요청 경로 503, 무인증 가입으로 돌아가지 않음 | `tests/api/test_email_auth.py::test_email_requests_fail_closed_without_smtp` |
| 8 | SMTP 오류 - 응답·로그에 원문 없음 | `tests/api/test_email_auth.py::test_smtp_errors_never_escape_in_response_or_logs` |
| 9 | 전환 제약 적용 DB - 기존 계정 유지, 구버전 무인증 신규 INSERT 거절 | `tests/api/test_email_auth.py::test_cutover_preserves_legacy_and_blocks_old_revision_signup` |
| 10 | 화면의 새 링크·늦은 응답 - 현재 링크 유지, 비밀번호·토큰을 브라우저 저장소에 남기지 않음 | `frontend/src/pages/EmailActionPage.test.tsx` |
| 11 | 로그인 화면 - 체크박스 없이 `Google 로그인`(활성 시), `/signup` 링크, 처리방침 링크. production 빌드에 데모 버튼 없음 | `frontend/src/pages/LoginPage.test.tsx` |
| 12 | 같은 401 - 동일 안내·요청 ID, 비밀번호 비움·이메일 유지. 로그인 성공 뒤 `me` 실패 - 세션 확인 실패 문구, 재전송 없음 | `frontend/src/pages/LoginPage.test.tsx` |
| 13 | 가입 화면 - 이메일만 전송, consent·비밀번호 미전송, 세션 없음 | `frontend/src/pages/SignupPage.test.tsx` |
| 14 | 잘못된 비밀번호·없는 계정 - 같은 오류. 필드 검증 실패 오류에 입력값 없음. 형식이 틀린 이메일 거절 | `tests/api/test_auth.py::test_login_validation_errors_do_not_echo_credentials`, `::test_login_rejects_malformed_email_without_echoing` |
| 15 | 계정·IP 로그인 실패 잠금, 집계 구간 만료 | `tests/api/test_auth.py::test_database_login_throttling`, `::test_database_login_ip_limit_blocks_after_thirty_failures_and_window_expires`, `::test_failed_attempt_window_expires` |
| 16 | 세션 절대·유휴 만료, 로그아웃·비활성 사용자의 세션 거절 | `tests/api/test_auth.py::test_idle_and_absolute_session_expiry_boundaries`, `::test_inactive_user_and_existing_session_are_rejected` |
| 17 | Cloud Run에서 `X-Forwarded-For`에 임의 값 - 마지막 값만 IP로 사용 | `tests/api/test_auth.py::test_client_ip_trusts_only_the_last_forwarded_entry_on_cloud_run` |
| 18 | `DEMO_MODE=0` - 데모 두 경로 404. 데모 모드 - A·B 별도 일반 사용자 세션, 비밀번호 로그인 401 | `tests/api/test_auth.py::test_demo_login_routes_do_not_exist_outside_demo_mode`, `::test_database_demo_buttons_create_and_log_into_separate_users_only` |
| 19 | 관리자 목록 - 이메일 마스킹, 형식 깨진 이메일은 `***`로 목록 성공 | `tests/api/test_auth.py::test_admin_users_masks_email_local_part`, `::test_admin_users_masks_malformed_email_without_failing` |
| 20 | 관리자·일반 사용자의 계정 관리 - 관리자만 허용, 비활성화 시 모든 세션 삭제 | `tests/api/test_auth.py::test_admin_account_management_and_session_revocation` |
| 21 | 데모 외 환경에서 `AUTH_SECRET` 없음 또는 32바이트 미만 - 시작 거부 | `tests/api/test_auth.py::test_production_requires_valid_auth_secret`, `::test_app_startup_requires_key_outside_demo` |

## 구현 상태

| AC | 상태 |
|---|---|
| 1~9, 14~21 | 위 테스트 파일이 있다. 실행 결과는 이 문서에 적지 않는다. DB 통합 사례는 전용 시험 DB가 없으면 skip된다 |
| 10~13 | 프론트 단위 시험 파일이 있다 |

## 한계

- 위 테스트 이름과 AC 문장의 1:1 대응은 파일·함수 이름으로만 맞췄고 본문을 줄 단위로 대조하지 않았다.
- 실제 메일 링크로 가입을 끝내고 재설정 메일·새 암호 로그인·기존 세션 해제까지 한 번에 확인한 기록은 레포에 없다.
- 직접 SMTP 호출의 응답 시간 차이는 숨기지 못한다(`backend/auth_email.py` 주석). 공개 규모 운영 시 내구성 있는 발송 큐가 필요하다. 개인 Gmail 계정의 발송 한도를 공유한다.
- 계정별 잠금 악용(남이 일부러 실패를 쌓아 계정을 잠그는 일)은 방어하지 않는다.
- IP 한도: 같은 NAT·통신사 뒤 사용자는 한 IP 한도를 나눠 쓰고, 여러 IP에서 나눠 보내는 요청은 IP 한도로 막지 못한다. Cloud Run 앞에 외부 부하분산기를 두면 IP 판단 규칙을 다시 정해야 한다.
- 기존 DB에 로그인 실패 제한을 적용하려면 `db/legacy/005_auth_attempt_window.sql`, `db/legacy/006_user_roles.sql`, `db/legacy/021_auth_ip_limits.sql`을 앱 배포 전에 적용해야 한다(표가 없으면 로그인이 503).
- `auth.signup`(직접 가입 헬퍼), `GOOGLE_PASSWORD_HASH`, `google_admin_session`은 HTTP 경로가 쓰지 않는 코드다(`backend/auth.py`). 시험은 `signup` 헬퍼를 호출한다.
