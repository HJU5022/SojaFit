# 로그인 역할·AUTH_SECRET 키 사용 실측

- 상태: 이력
- 기준일: 2026-11-02
- 기준 커밋: 없음(측정 대상은 STH 작업 트리의 미커밋 인증 변경)
- 정본 여부: 비정본(측정 기록). 인증 동작의 정본은 `backend/auth.py`와 [SPEC.md](../../SPEC.md)
- 관련 문서: [auth-login-verification.md](auth-login-verification.md), [scripts/auth/AUTH.md](../../scripts/auth/AUTH.md)

## 1. 질문과 결론

질문: 역할(`admin`/`user`) 반환과 관리자 API 권한, 실제 `AUTH_SECRET`으로 계산한 세션 해시, 키 없는 시작 조건이 설계대로인가. 아래 표의 9개 항목이 모두 통과했다. 레포에는 이 측정의 원시 파일이 없다(6절).

| 확인 항목 | 결과 | 근거 |
|---|---|---|
| `/api/auth/me` 역할 반환 | 관리자 3/3 `admin`, 일반 사용자 3/3 `user`, 모두 HTTP 200 | 측정 로그(레포에 없음) |
| 관리자 API 권한 | 관리자 계정 목록 3/3 HTTP 200, 일반 사용자 3/3 HTTP 403 | 측정 로그(레포에 없음). 상태 변경·세션 폐기는 `tests/api/test_auth.py::test_admin_account_management_and_session_revocation` |
| 키 없는 새 데모 DB | `DEMO_MODE=1` 초기화에서 관리자 1개·일반 1개 생성 | 측정 로그(레포에 없음). 현재 코드는 첫 데모 로그인 때 계정을 만든다(5절) |
| 비데모 기본 계정 차단 | `DEMO_MODE=0`에서 계정 환경변수가 비어 있으면 기본 계정 0개 | 측정 로그(레포에 없음) |
| 사용자 지정·불완전 시드 | 격리 DB의 시드 5조건에서 설정 재정의와 일부 값 오류 확인 | 측정 로그(레포에 없음). 해당 이름의 시험(`test_demo_seed_configuration`)은 현재 레포에 없다 |
| 실제 로컬 `AUTH_SECRET` | 6/6 세션에서 DB 저장값이 HMAC-SHA256과 일치하고 SHA-256 단독값과 다름 | 측정 로그(레포에 없음). 구현 `backend/auth.py:62-66`, 시험 `test_session_token_hash_uses_key_when_provided` |
| 키 변경과 세션 | 일반 사용자 세션 중 임시 키로 바꾸자 `/api/auth/me` 401. 키를 복원한 뒤 로그아웃 성공 | 측정 로그(레포에 없음) |
| 키 없는 시작 조건 | 키 없는 데모 시작 허용, 데모 외 키 누락·짧은 키 거부, 유효한 테스트 키 시작 | `backend/auth.py:52-57`, `tests/api/test_auth.py::test_production_requires_valid_auth_secret`, `test_app_startup_requires_key_outside_demo` |
| 로그아웃 | 6/6 HTTP 200, 로그아웃 후 `/api/auth/me` 6/6 401 | 측정 로그(레포에 없음) |

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 측정 시각 | 2026-11-02 19:59 KST |
| 환경 | Windows, Python 3.12.10, FastAPI `TestClient`, Docker PostgreSQL 16.15. 임시 Compose DB 두 개 |
| 호출 방식 | 같은 컴퓨터의 `TestClient`에서 PostgreSQL에 접속. 계정별 3회 순차 호출한 단일 측정 |
| 시드 확인 | `DEMO_MODE=1`과 `0`인 새 볼륨 각각. 키 사용 측정은 데모 계정이 준비된 격리 DB에서 `DEMO_MODE=0`과 로컬 키로 실행 |
| 키 | 6회 실측만 로컬 `.env`의 실제 `AUTH_SECRET` 사용. 시드·키 자동 검사의 키는 테스트 전용. 키·세션 토큰·DB 접속 정보는 기록하지 않음 |

## 3. 결과: 응답 시간

단위 ms. 로그인에는 비밀번호 검증이 포함된다. 레포에 원시 파일이 없어 중앙값만 남긴다.

| 역할 | 로그인 중앙값(3회) |
|---|---:|
| admin | 425.76 |
| user | 398.81 |

3회뿐이므로 분포나 성능 차이의 근거로 쓰지 않는다.

## 4. 자동 회귀 검사

테스트 전용 PostgreSQL을 `TEST_AUTH_DATABASE_URL`로 지정하고 `PYTHONUTF8=1`로 실행한 `pytest -q -rs`: 75 passed, 10 skipped, 18.39초. skipped 10건은 별도 RAG 테스트 DB나 코퍼스가 필요한 검사다. 원시 파일 없음.

## 5. 현재 코드와 다른 점

| 항목 | 이 측정 | 현재 코드 |
|---|---|---|
| 데모 계정 | `DEMO_MODE=1` 초기화에서 관리자 1·일반 1 | 첫 데모 버튼 로그인 때 일반 사용자 `demo-a`/`demo-b`를 만든다(`backend/auth.py:43`, `:440`) |

## 6. 한계

- 이 표의 측정 로그(역할 응답, 응답 시간, 6/6 세션)는 레포에 없다. 재현 스크립트도 없다.
- 실제 브라우저의 운영자 메뉴는 구현 전이어서 표시를 확인하지 못했다. 서버의 역할 응답과 관리자 API만 확인했다.
- 로컬 API 컨테이너의 `.env` 전달, 클라우드 비밀값 설정, 배포 서비스의 HTTPS·다중 인스턴스·동시 부하, 기존 볼륨 적용은 범위 밖이다.
