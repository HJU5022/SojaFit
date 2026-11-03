# auth

## 역할
- 이 폴더: 로그인 잠금·세션 만료·scrypt 동시성을 재는 일회성 인증 실측 스크립트를 둡니다. 저장소 루트에서 실행합니다.
- 넣는 것: 격리된 테스트 DB(`TEST_AUTH_DATABASE_URL`, `127.0.0.1:55434/ci_auth`) 전용 인증 실측 스크립트.
- 넣지 않는 것: 실측 원시 결과(`scripts/results/auth/`), 인증 서비스 코드(`backend/auth/`), 인증 회귀 테스트(`tests/api/`), 측정 해석([auth-login-verification.md](../../docs/research/auth-login-verification.md)).
- 담당: 인증

## 파일
- `AUTH.md` — 이 문서
- `auth_boundary_after_merge.py` — 잠금 해제(15분)·유휴 만료(30분)·절대 만료(8시간) 경계 시각 실측. `TEST_AUTH_DATABASE_URL=... uv run python scripts/auth/auth_boundary_after_merge.py` → `scripts/results/auth/auth_boundary_<KST 날짜>.json`
- `measure_scrypt_concurrent.py` — 동시 scrypt 상한(2건)과 프로세스 메모리 실측. **Windows 전용**(`ctypes.windll`). `uv run python scripts/auth/measure_scrypt_concurrent.py` → `scripts/results/auth/scrypt_concurrent_<KST 날짜>.json`
