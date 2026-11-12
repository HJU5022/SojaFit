# Google 일반 사용자 로그인

## 2026-11-12 로컬 OAuth·신규 계정 완료 UI와 시계 오차 보완
- Why/Goal: 로컬에서 검증된 Google 신원은 google=finish로 돌아왔으나 화면에 가입/기존 계정 연결 완료 동작이 없었다. 빠른 반복 로그인은 ID 토큰 iat 시각차로 거절됐다. 기존 API/본인확인 경계를 재사용해 두 경로를 끝까지 제공한다.
- What/How: LoginPage는 finish일 때 onboarding의마스킹이메일을조회하고명시적Google가입/기존일반계정이메일·비밀번호연결을제공한다. 기존AuthProvider.googleSignup/googleLink와서버세션후me확인을사용한다. 만료/실패는완료버튼차단과재인증경로,지연조회는current플래그로폐기한다. 일반Google버튼/비밀번호로그인은유지. auth.verify_google_id_token의시간claim만leeway30초로처리하고서명/issuer/aud/nonce/email_verified검증은유지한다. 발급미래30초허용/31초거절·만료31초거절을고정시간서명토큰으로검증한다.
- AC: Given유효pending When명시가입/연결 Then각기존API만호출하고세션확인후작업대로이동. Given미클릭/만료pending Then자동가입·연결없음. Given30초이내시계오차 Then검증유지한채로그인가능,31초이상미래/허용범위밖만료/잘못된서명·nonce·issuer·aud Then거절.
- 로컬설정: localhost:8198은새로컬DB sojafit_auth_lab_1112와메모리메일함만사용. 사용자가승인한Google OAuth클라이언트콜백1줄 http://localhost:8198/api/auth/google/callback 추가를실제저장했고기존3주소/secret은유지했다. localhost:8000운영DB조회용서버와세션/Google쿠키이름을분리한다. 운영DB/배포·실제SMTP·분석은변경/실행하지않는다. SPEC정본반영은조장검토대상.


2026-11-11 / 사용자 선택: 일반 사용자 승인 없는 로그인, 관리자 최초 연결 승인 유지, 기존 계정 비밀번호 재확인 후 연결. 운영 반영 전 작업서.

## Why
Google 인증이 관리자 연결 요청으로만 끝나 일반 사용자가 이용할 수 없다. 최초 일반 사용자 가입에 운영자 개입 0회, 기존 사용자 데이터의 자동 병합 0건을 목표로 한다.

## Goal
- 신규 Google 사용자는 동의 후 user 계정과 기존 서버 세션을 얻는다.
- 기존 계정 연결에는 기존 비밀번호 재확인이 필요하며 관리자 연결은 운영자 CLI만 허용한다.
- 비밀번호 로그인·관리자 승인/회수·state/PKCE/nonce 검증은 유지한다.
- 제외: GCP 설정·운영 DB 적용·배포·비밀번호 재설정·새 인증 공급자·평가셋 변경.

## What
- 운영 로그인 화면: 서버 Google status가 enabled일 때 ‘Google로 계속하기’를 이메일 폼 위에 표시한다. 데모 A/B 접속 버튼과 status 조회는 Vite 개발 환경에서만 허용하며 production 빌드에서는 서버가 데모 enabled를 잘못 응답해도 표시/조회하지 않는다. 서버 데모 endpoint 비활성화는 기존 DEMO_MODE=0 설정으로 유지한다. Google 미설정/조회 실패 시 잘못된 OAuth 진입을 만들지 않는다. GCP·운영 DB·배포 설정은 이 화면 변경에서 수정하지 않는다.
- 연결된 활성 사용자는 Google callback에서 바로 로그인한다.
- 미연결 사용자는 `/login?google=finish`에서 동의 후 가입하거나 기존 계정의 이메일·비밀번호로 연결한다. 이미 로그인한 브라우저라도 비밀번호를 다시 받는다.
- 같은 이메일 계정이 있으면 자동 연결/생성을 하지 않는다. 관리자 최초 연결은 기존 승인 대기 화면과 CLI를 사용한다.
- 만료·재사용·다른 계정에 이미 연결·비활성 계정은 세션을 발급하지 않는다.

## How
- 기존 issuer/sub 연결·15분 pending·브라우저 HttpOnly 쿠키 재사용. pending 쿠키 경로는 `/api/auth/google`이며 URL·JS에 식별 토큰을 내보내지 않는다.
- 숨긴 GET `/api/auth/google/onboarding`: 마스킹 이메일. POST `/google/signup`: `{consent:true}`, POST `/google/link`: `{email,password}`. 두 POST 모두 Origin 확인·추가 필드 거부·서버 세션 쿠키 발급.
- 새 계정은 `role=user`, `password_hash=NULL`. 027 SQL로 NULL을 일반 계정에만 허용한다. 가짜 비밀번호를 저장하지 않는다. NULL 계정 비밀번호 인증은 실패하고 동일한 scrypt 비용을 사용한다.
- 기존 IP별 UTC 하루 가입 3회 한도를 Google 가입도 공유한다. 연결의 비밀번호 검사는 기존 계정/IP 실패 잠금과 동시 scrypt 제한을 재사용하되 성공 세션은 연결 트랜잭션에서만 발급한다.
- 이메일 일치만으로 연결하지 않는다. 기존 계정과 Google 이메일이 달라도 두 신원을 각각 확인한 일반 계정 연결만 허용한다. `(issuer,sub)`·user_id 유일 제약 유지, 연결·pending 소비·세션은 한 트랜잭션이다.
- 기존 관리자 최초 연결은 운영자 승인 유지, 연결된 관리자의 Google 로그인은 그대로다. Google 토큰은 영구 저장하지 않는다.
- 주 문서 SPEC 4/8.6은 조장 소유이므로 이 문서의 신규 일반 사용자 흐름과 nullable 비밀번호 정책을 조장 검토 대상으로 남긴다. 기존 관리자 정책을 삭제하지 않는다.
- 공식 근거: [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect): sub 기준 연결, issuer/aud/exp/signature/nonce 확인.

## AC
- Given production 빌드와 Google enabled/데모 enabled 응답, When 로그인 화면 표시, Then Google 버튼이 기존 /api/auth/google/start에 연결되고 데모 버튼·status 조회는 없다. Given 개발 환경의 DEMO_MODE=1, Then 기존 개발용 데모 접속은 유지된다.
- Given 새 Google 신원, When 명시적 동의 후 가입, Then 운영 승인 없이 user·NULL 비밀번호·세션이 원자적으로 생성된다.
- Given 기존 이메일 또는 기존 연결, When 가입/다른 사용자 연결, Then 자동 병합·권한 변경·중복 연결 없이 거절한다.
- Given 기존 일반 계정, When 올바른 비밀번호와 현재 pending으로 연결, Then 기존 id·프로젝트를 유지하고 다음 Google 로그인은 같은 계정이다.
- Given 틀린 비밀번호·비활성 계정·관리자, When 일반 연결 요청, Then 연결/새 세션 없음. 관리자는 기존 운영자 승인만 가능하다.
- Given 만료/소비된 pending·쿠키 없음·잘못된 Origin·동의 없음, When 완료 요청, Then 계정/연결 생성 없음.
- Given 동일 IP의 비밀번호 가입과 Google 가입 합계 3회, When 다음 가입, Then 429다.

## 구현 순서와 검증
1. 인증/HTTP 경계 회귀를 먼저 추가하고 미구현 실패를 확인한다.
2. 027 SQL·공통 가입 한도·일반 Google 세션·원자적 연결/가입을 구현한다.
3. 기존 로그인 화면에 가입 동의/비밀번호 재확인 연결을 넣고 PrivacyNotice를 재사용한다.
4. 격리 로컬 DB에서 신규/기존/관리자/만료/충돌/한도·기존 인증 회귀, 프런트 시험·빌드, 저장소 구조·diff를 확인한다. 운영 DB·GCP·실제 Google 인증은 변경하지 않는다. 커밋·푸시하지 않는다.

## 조장 정본 반영 요청
+- `SPEC.md:179`: Google start를 일반 사용자·관리자 공용 진입으로 설명한다.
+- `SPEC.md:180`: 미연결 callback 목적지를 `/login?google=finish`로 적고, 기존 pending은 관리자 최초 승인용으로 유지한다.
+- `SPEC.md:192`, `SPEC.md:421`: 연결된 활성 일반 사용자도 세션을 발급한다. 미연결 신규 사용자는 명시적 동의 후 일반 가입, 기존 사용자는 비밀번호 재확인 후 연결, 관리자 최초 연결은 운영자 승인이라는 계약·AC를 반영한다.
+- 4절 엔드포인트 표에 숨긴 GET onboarding(마스킹 이메일), POST google/signup(동의), POST google/link(기존 이메일·비밀번호)의 입력·응답·400/401/403/409/422/429/503 경계를 추가한다. `users.password_hash`는 Google 일반 계정만 NULL 가능하며 일반 비밀번호 가입/관리자는 기존 해시를 유지한다.

## 운영 적용 전 확인
- 2026-11-11 사용자 결정: 실제 Google 로그인은 로컬에서 더 진행하지 않고 운영 반영 과정의 팀장 확인으로 이관한다. 현재 gcloud의 비밀 읽기 권한 부족으로 로컬 인증은 완료되지 않았다. Cloud SDK 인증 대기/로컬 OAuth 시험 서버는 중단했으며 운영 OAuth·IAM·DB·배포는 변경하지 않았다. 화면/API mock 통과를 실제 OAuth 성공으로 표시하지 않는다.
+- 027 SQL은 기존 DB에서 자동 실행되지 않는다. 백업·적용 대상 확인 후 SQL 먼저, 해당 코드 배포 순서다. 이 작업에서는 운영 DB·GCP·배포를 실행하지 않는다.
+- Google callback URI와 openid/email 범위는 변경하지 않았다. OAuth 클라이언트 공개/테스트 사용자 상태와 실제 Google 왕복은 별도 확인한다.
+- NULL 비밀번호 계정 생성 후 NULL을 처리하지 못하는 구버전 auth.py로 단순 롤백하면 비밀번호 인증 오류가 생길 수 있다. 계정 삭제나 임의 비밀번호 부여 없이 NULL 처리 호환성을 유지해야 한다.
+- 핵심 변경은 인증 SQL·HTTP·화면·보안 회귀가 연결된 한 기능이다. 향후 PR에서 테스트/작업서 포함 400줄을 넘는 규모와 보안 경계별 검증 필요성을 설명하고 목적별 커밋을 구분한다. 이번에는 커밋·푸시하지 않는다.


## 로그인·가입 동의 UI 제거 후속 승인 (2026-11-12)
- 사용자는 별도 약관/수집 동의 체크 제거와 운영 회원가입 제공을 요청했다. Google 버튼은 `Google 로그인`, 이메일 가입에는 email/password만 전송하며 동의 true를 자동으로 만들지 않는다. 구버전 consent bool은 선택 호환 필드이며 저장·동의 증거로 해석하지 않는다.
- 운영 callback의 새 계정 생성에서는 동의 쿠키만 제거하고 기존 Google state/PKCE/nonce/email_verified·활성 계정/연결·세션 정책을 유지한다. 로컬의 별도 pending/비밀번호 연결 작업은 운영 배포에 섞지 않는다. 운영 DB 구조·OAuth 등록·Origin·Secret은 변경하지 않는다.
- 이메일 가입은 운영 DEMO_MODE=0에서도 제공하고 기존 Origin/8자 이상 비밀번호/가입 IP 한도·scrypt/세션을 유지한다. 개인정보처리방침 링크와 미정 처리 근거/운영 정보 표시는 유지한다. 상세 AC는 frontend-screen-redesign.md의 같은 날짜 계약을 따른다. 정본 SPEC의 동의 필수·운영 가입 조건은 조장 반영 요청이며 이 브랜치에서 수정하지 않는다.
