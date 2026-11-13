# 로그인 이메일 암호화 정책 선택지

- 상태: 계획
- 기준일: 2026-11-12 (현재 구조 대조일). 선택지 작성일 2026-11-04
- 기준 커밋: 선택지 작성 시점 fdbe30a. 현재 구조는 `backend/auth.py`, `db/schema/table-definition.md`로 대조
- 정본 여부: 비정본(제안). 결정이 나면 ADR로 기록한다. 현재 ADR 없음
- 관련 문서: [login-auth 스펙](../specs/login-auth.md), [SPEC.md](../../SPEC.md), [db/schema/table-definition.md](../../db/schema/table-definition.md)

범위: 로그인 식별 이메일의 저장과 조회. 비밀번호, 세션 토큰, 평가 계정 전달 방식은 별도 항목이다. pgvector 확장, 코퍼스, 임베딩 표와 데이터는 이 정책의 변경 대상이 아니다.

## 1. 질문과 결론

질문: DB에 평문으로 저장된 로그인 이메일을 어떻게 보호할 것인가.

| 항목 | 값 | 근거 |
|---|---|---|
| 결정 | 없음. 팀 합의와 DB 제공자 설정 확인이 남아 있다 | ADR 없음 |
| 논의 중인 방향 | A안(DB 저장 암호화와 접근 통제). 앱 계층 암호화와 인증 스키마 변경은 하지 않는 방향 | |
| A안의 한계 | DB 조회 권한을 가진 앱·운영 역할은 `users.login_id` 평문을 볼 수 있다. 이를 허용하지 못하면 B안을 다시 본다 | |
| 권장하지 않는 안 | D(단순 결정적 암호화) | 3절 |

## 2. 현재 구조

| 항목 | 값 | 근거 |
|---|---|---|
| 이메일 저장 | `users.login_id` varchar(100), UNIQUE, 소문자 이메일 원문. Google 가입도 같은 칸에 저장 | `db/schema/table-definition.md:42,53` |
| 로그인 조회 | `WHERE login_id = <trim·lowercase한 이메일>` | `backend/auth.py:334,355` |
| 이메일을 담은 다른 칸 | `auth_email_challenges.email`(가입·비밀번호 재설정 확인, PK의 일부) | `db/schema/table-definition.md:208,217` |
| 관리자 목록 | 이메일 로컬 파트를 서버에서 가려 반환 | `SPEC.md:188`, `tests/api/test_auth.py::test_admin_users_masks_email_local_part` |
| 비밀번호 | salt가 있는 scrypt 해시. 복호화하지 않는다 | `backend/auth.py:80-84` |
| 세션 토큰 | 원문은 쿠키에만 있고 DB에는 `AUTH_SECRET` 기반 HMAC만 저장 | `backend/auth.py:62-66` |
| 기능 범위 | 이메일 가입, 비밀번호 재설정, Google 로그인이 있다. 이메일 필드 암호화는 이들을 모두 바꿔야 한다 | `docs/specs/login-auth.md`, `SPEC.md` 인증 절 |

DB 제공자(Supabase 여부)와 저장·백업 암호화, 연결 TLS 설정은 이 저장소에서 확인되지 않는다.

## 3. 선택지

| 선택지 | DB의 이메일 원문 | 로그인 검색 | 코드·스키마 영향 | 운영 부담 | 적합한 경우 |
|---|---|---|---|---|---|
| A. DB 저장 암호화와 접근 통제 | DB 엔진을 통해서는 읽힘 | 현재 방식 그대로 | 거의 없음 | 낮음 | 매체·백업 탈취 위험을 줄이는 것이 목표이고 DB 권한자에게 이메일이 보여도 될 때 |
| B. 앱 계층 필드 암호화 + HMAC 검색값 | 암호문만 저장 | 정규화 이메일의 HMAC 검색값으로 일치 조회 | 중간. users 스키마, 로그인, CLI, 관리자 목록, 마이그레이션 | 중간 이상. 암호화 키, 검색 키, 회전·복구 | DB 덤프나 DB 읽기 권한만으로 평문 이메일을 못 보게 해야 할 때 |
| C. 별칭 또는 외부 인증 식별자 | 원문 이메일 미저장 또는 외부 ID만 저장 | 별칭 또는 IdP 주체 ID | 큼. 로그인 계약, 계정 생성, 관리 절차 변경 | 외부 IdP 연동, 가용성, 계정 복구 | 계정 DB에 이메일을 두지 않는 것이 우선이고 로그인 방식 변경을 감수할 때 |
| D. 단순 결정적 이메일 암호화 | 암호문 | 매번 같은 암호문으로 비교 | 작음~중간 | 낮아 보이나 누출·키 관리 위험 큼 | 권장하지 않음. 반복 이메일의 동일성·빈도가 드러나고 위변조 감지·키 보호가 약해지기 쉽다. B의 무작위 nonce 인증 암호화 + 별도 HMAC 검색값이 같은 요구를 더 분명히 처리한다 |

### 3.1 A. DB 저장 암호화와 접근 통제

- `login_id`, 로그인 API, 유일성 제약은 그대로 둔다.
- DB 제공자의 저장 매체·백업 암호화, DB 역할 권한, 연결 TLS, Secret 접근 권한을 확인해야 한다.
- 구현과 이관이 가장 쉽다. 저장 매체나 백업 파일만 분리 유출되는 위험을 줄이지만 앱 계층 암호화와 같은 보호 수준이 아니다. 이름만으로 제공자 설정을 추정하지 않는다.

### 3.2 B. 앱 계층 필드 암호화와 HMAC 검색값

- `users.login_id` 평문 저장을 중단하고 암호문(예: `login_id_ciphertext`)과 검색용 HMAC(예: `login_lookup_hmac`)을 저장한다. 필요하면 키 식별자를 함께 둔다.
- 로그인 입력 이메일은 현재 규칙대로 trim·lowercase 정규화한 뒤 HMAC해 조회한다. HMAC 키는 암호화 키와 분리한다. HMAC 색인은 원문을 숨기지만 같은 이메일의 반복과 계정 수는 드러낸다.
- 관리자 목록의 마스킹을 유지하려면 권한 확인 뒤 복호화해 마스킹한다. 평문 이메일을 API 응답에 추가하지 않는다.
- 바꿔야 하는 곳: 계정 생성 CLI, 데모 시드, 로그인, 관리자 목록, 이메일 UNIQUE·정규화 규칙, 이메일 가입·비밀번호 재설정(`auth_email_challenges`), Google 연결, DB 이관.
- 무작위 nonce를 쓰는 인증된 암호화(AEAD)를 쓰고 같은 키에서 nonce를 재사용하지 않는다. 암호화 키와 HMAC 키의 보관·접근·백업·회전·복구 담당을 정해야 한다.
- 키를 잃으면 이메일을 되살릴 수 없다. 조회 키를 바꾸면 전체 HMAC 재계산과 중복 확인이 필요하다.
- Cloud KMS envelope encryption은 키 통제·감사 경계를 강화하지만 IAM, API 호출, 배포 설정, 비용·지연 검토가 추가된다. Secret Manager에 앱 키를 두는 단순안도 런타임 권한과 회전·복구 절차가 필요하다.
- 기존 평문 값을 옮기는 일회성 변환은 기존 DB 접근권한, 백업, 로그에 남은 과거 값을 지우지 않는다. 전환 전후 정합성 대조와 복구 계획이 필요하다.
- 선택하면 `SPEC.md`에 기능 기준을 먼저 반영하고 승인된 작업서와 시험을 만든 뒤 구현한다.

### 3.3 C. 별칭 또는 외부 인증 식별자

- `user-<무작위 식별자>` 같은 별칭으로 로그인하거나 외부 인증 제공자의 안정된 주체 ID만 내부 `users` 키에 연결한다.
- 현재 기능 명세가 이메일·비밀번호 직접 로그인과 이메일 가입을 정하므로 계약과 평가 절차가 바뀐다. 별도 SPEC·ADR과 평가 시나리오 수정이 필요하다.
- 별칭을 안전하게 발급·회수·전달하는 절차가, IdP를 택하면 로그인 연동·사용자 매핑·장애 시 접근 회복이 추가된다.

## 4. 미결 질문

| 질문 | 값 |
|---|---|
| 보호하려는 주된 위험(저장 매체·백업 탈취 / DB 조회 권한 오남용 / 이메일 수집 자체) | 미결 |
| A, B, C 중 채택안 | 미결(D는 제외 권고) |
| 로그인 이메일 평문이 앱 메모리와 승인된 관리자 화면에 있어도 되는가 | 미결 |
| 암호화 키와 검색 HMAC 키의 보유·접근·회전·복구 담당. Cloud KMS 사용 시 비용·권한 담당 | 미결 |
| 기존 계정 이관·검증·복구, 남은 백업·로그의 처리 범위 | 미결 |

미결이면 필드 암호화 구현과 운영 계정 이관은 진행하지 않는다.

## 5. 논의안

- 목표가 DB 덤프·읽기 권한자에게 평문 이메일을 보이지 않는 것이면 B. 임의의 암호화 방식을 만들지 않고 검토된 AEAD·키 관리 라이브러리와 키 관리 경계를 쓴다.
- 목표가 저장 매체 암호화와 최소 권한이면 A. 실제 제공자 설정, 백업, TLS, 접근 권한을 읽기 전용으로 확인한다. 연결 문자열은 출력하거나 기록하지 않는다. 저장 계층 암호화가 앱 계층 필드 암호화를 대신한다고 표현하지 않는다.
- 이메일 수집 자체를 피해야 하면 C. 로그인 계약 변경과 IdP 운영 범위를 별도로 정한다.
- 세 선택 모두 실제 서비스 DB가 식별되고 백업·복구 경로가 확인되기 전에는 운영 데이터에 쓰지 않는다.

## 6. 한계

- 실제 Cloud Run `DATABASE_URL` 대상, DB 제공자 설정(저장·백업 암호화, 연결 TLS, 역할 권한)은 확인하지 않았다.
- 외부 자료는 일반 암호화 설계 근거이며 SojaFit DB 제공자의 설정, 청구액, 팀의 개인정보 정책을 확인한 결과가 아니다.

## 7. 참고 자료

- Google Cloud, [Envelope encryption](https://docs.cloud.google.com/kms/docs/envelope-encryption)
- Supabase, [Data Residency and Transfers FAQ](https://supabase.com/legal/privacy-resources/data-residency-and-transfers-faq): 일반 저장·백업 암호화 설명. 특정 프로젝트 확인 결과가 아니다.
- Supabase, [Postgres SSL Enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement)
- Google Cloud, [Client-side encryption with Tink and Cloud KMS](https://docs.cloud.google.com/kms/docs/client-side-encryption)
- NIST, [Key Management Guidelines](https://csrc.nist.gov/projects/key-management/key-management-guidelines)
- Python Cryptographic Authority, [Authenticated encryption primitives](https://cryptography.io/en/stable/hazmat/primitives/aead/): AEAD, AES-GCM nonce 재사용 주의
