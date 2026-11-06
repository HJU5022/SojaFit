# api

## 역할
- 이 폴더: 서버 API(`/health`, 로그인·세션)를 확인하는 회귀 테스트를 둡니다.
- 넣는 것: `backend/api/`·`backend/auth/`를 대상으로 한 `test_*.py`. DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색·적재 시험(`tests/rag/`), LLM 호출 시험(`tests/services/`), 일회성 인증 실측(`scripts/auth/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/api`(저장소 루트).

## 파일
- `API.md` — 이 문서
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(세션 HMAC과 키 누락·교체, 데모 시드, 두 사용자 세션 격리, 관리자와 일반 사용자 권한, 비활성 사용자와 세션 폐기, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류, 로그인 화면, 질문 API 미노출, 비밀번호 해시 전용 CLI). 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_health.py` — `/health` 응답과 미구현 루트 경로의 404 확인
