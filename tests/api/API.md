# api

## 역할
- 이 폴더: 서버 API(`/health`, 로그인·세션, 가격·재고)를 확인하는 회귀 테스트를 둡니다.
- 넣는 것: `backend/main.py`·`backend/auth.py`를 대상으로 한 `test_*.py`. DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색·적재 시험(`tests/rag/`), LLM 호출 시험(`tests/services/`), 일회성 인증 실측(`scripts/auth/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/api`(저장소 루트).

## 파일
- `API.md` — 이 문서
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(세션 HMAC과 키 누락·교체, 데모 시드, 두 사용자 세션 격리, 관리자와 일반 사용자 권한, 비활성 사용자와 세션 폐기, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류, 로그인 화면, 질문 API 미노출, 비밀번호 해시 전용 CLI). 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_frontend.py` — SPA 직접 진입·assets·미빌드 로그인 fallback·API JSON 404와 기존 라우트 우선 경계
- `test_health.py` — `/health`, 서버 생성 요청 ID, 401·403·404·422·500 공통 오류 구조, 민감한 입력·내부 예외 비노출, OpenAPI 오류 스키마 확인
- `test_projects.py` — 세션·Origin·데모 5종·입력 검증·안전한 DB 오류·실제 DB CRUD와 관리자 포함 타 사용자 비공개 404. 업로드의 제한 수신·disk rollover 없음·저장소 payload·원본 즉시 close·오류 request ID. DB 시험은 `TEST_AUTH_DATABASE_URL`이 있을 때만 실행
- `test_prices.py` — `GET /api/prices`를 가짜 Mouser transport(손으로 쓴 응답)로 확인: 로그인 필요(401), `Cache-Control: no-store`, 화면 칸과 조회 시각만 돌려주기, 데모 모드·키 없음·호출 상한·Mouser 실패의 값 없음 모양, 품번 11개 이상·형식 오류의 공통 422 응답, 로그에 키·요청 주소·Mouser 값 없음
