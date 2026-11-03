# scripts

## 역할
- 이 폴더: 서비스 코드 밖에서 손으로 돌리는 측정·점검 스크립트를 둡니다. 저장소 루트에서 `uv run python scripts/<파일>.py`로 실행합니다.
- 넣는 것: 실측·점검 스크립트. 원시 결과는 `evals/results/`에 날짜를 붙여 씁니다.
- 넣지 않는 것: 서비스 코드(`backend/`), 평가셋 실행·동결 스크립트(`evals/`), 원시 결과(`evals/results/`), 측정 해석(`docs/`).
- 담당: 각 모듈 담당

## 파일
- `auth_boundary_after_merge.py` — 로그인 잠금·세션 만료 경계 실측. 격리된 테스트 DB 전용. 해석은 [auth-login-verification.md](../docs/auth-login-verification.md)
- `measure_scrypt_concurrent.py` — 동시 scrypt·프로세스 메모리 실측. Windows 전용, 격리된 테스트 DB 전용

- check_mcp_offline_pdfs.py — 로컬 TSC PDF 표본 3건을 manifest 해시·쪽 수·텍스트 추출과 대조한다. pypdf 임시 오프라인 환경 사용.
