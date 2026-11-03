# scripts

## 역할
- 이 폴더: 서비스 코드 밖에서 손으로 돌리는 측정·점검 스크립트를 둡니다. 저장소 루트에서 `uv run python scripts/<파일>.py`로 실행합니다.
- 넣는 것: 실측·점검 스크립트. 원시 결과는 `evals/results/`에 날짜를 붙여 씁니다.
- 넣지 않는 것: 서비스 코드(`backend/`), 평가셋 실행·동결 스크립트(`evals/`), 원시 결과(`evals/results/`), 측정 해석(`docs/`).
- 담당: 각 모듈 담당

## 파일
- `langfuse_skill_check.py` — `DEMO_MODE=0 uv run python -m scripts.langfuse_skill_check <새 결과 JSON>`. 기본은 기존 development 버전을 조회·대조한 뒤 합성 대표 요청의 노드·generation·버전·모델을 확인. 로컬/원격 불일치 시 모델 호출 전에 중단. 원격 등록은 `--publish`를 명시해야 하며 `--resume-from`과 함께 사용할 수 없음. 실제 코퍼스 검색·전체 평가·서비스 그래프 통합 검증은 아님
- `auth_boundary_after_merge.py` — 로그인 잠금·세션 만료 경계 실측. 격리된 테스트 DB 전용. 해석은 [auth-login-verification.md](../docs/auth-login-verification.md)
- `measure_scrypt_concurrent.py` — 동시 scrypt·프로세스 메모리 실측. Windows 전용, 격리된 테스트 DB 전용
