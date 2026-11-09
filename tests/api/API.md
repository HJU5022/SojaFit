# api

## 역할
- 이 폴더: 서버 API(`/health`, 로그인·세션, 가격·재고)를 확인하는 회귀 테스트를 둡니다.
- 넣는 것: `backend/main.py`·`backend/auth.py`를 대상으로 한 `test_*.py`. DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색·적재 시험(`tests/rag/`), LLM 호출 시험(`tests/services/`), 일회성 인증 실측(`scripts/auth/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/api`(저장소 루트).

## 파일
- `test_threads.py` — 격리 PostgreSQL의 업로드·소유권·체크포인트 복구·재개·승인 멱등성 시험. 승인 사례는 새 분석에 넘기지 않고 Store에 쓰지 않음(승인 기록), 질문·재개 결과의 사용자 사실 참고(`profile_hints`)의 A/B 격리·고침·지움, `vector` 확장이 있는 DB에서 의미 순위·다시 임베딩도 본다. React 대화의 같은 UUID thread 연결(대상 고정·소유권·원문 미저장)과 React run·재개 HTTP가 실제 분석 서비스로 이어지는지, 하루 토큰 상한(사용자 · 서비스)의 원자적 차감 · 입장과 호출 직전 429 · 외부 호출 없음도 본다
- 같은 파일에서 실제 로그인 쿠키의 키 없는 합성 HTTP 흐름, 기억 정정/철회/삭제/재승인 차단, 중단 checkpoint의 철회 기억 배제, 내용 없는 단계 기록/trace 실패 격리와 시간 초과 결과의 승인 차단을 확인한다.
- 같은 파일에서 DB 없이 실제 분석 그래프 조립이 카드 도구(`card_find` · `card_specs`)를 넘기고, `timed_tool`로 감싼 뒤에도 `prefetch` · `also_read`가 남는지 본다(ADR 0016).
- 같은 파일의 운영 준비 시험: 8개 병렬 thread의 일일 예약과 질문 격리, 명시적 TEST_THREAD_BACKUP_CONTAINER에서 pg_dump→일회용 DB 복원→Store/소유권/interrupt 재개. 공유 DB 복원은 실행하지 않는다.
- `API.md` — 이 문서
- `test_conversations.py` — 대화 인증·스트림·삭제 경계. 가짜 분석 서비스로 첫 run의 thread 연결, 대상 변경 409, 재개 버전, 완료 frame의 참고(내 설정)와 run 기록 미저장, 실패 frame의 `error.code`와 예외 로그, 서비스 없음 503, 토큰 상한 429가 스트림 · run 행 전에 끝남, 대화 있는 프로젝트 삭제 204
- `test_quotes.py` — 승인·견적·사례 API의 Origin·입력 allow-list·안전 오류
- `test_full_service_flow.py` — 격리 PostgreSQL의 업로드·interrupt 재개·승인·가격 없는 견적·타 사용자 차단·cascade 전체 흐름
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(세션 HMAC과 키 누락·교체, 데모 시드, 두 사용자 세션 격리, 관리자와 일반 사용자 권한, 비활성 사용자와 세션 폐기, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류, 로그인 화면, 질문 API 미노출, 비밀번호 해시 전용 CLI, 자기 가입의 중복·입력·출처·IP 하루 3회 한도와 Cloud Run 클라이언트 IP 판단, IP당 15분 로그인 실패 30회 잠금·구간 만료). 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_frontend.py` — SPA 직접 진입·assets·미빌드 로그인 fallback·API JSON 404와 기존 라우트 우선 경계
- `test_health.py` — `/health`, 서버 생성 요청 ID, 401·403·404·422·500 공통 오류 구조, 민감한 입력·내부 예외 비노출, OpenAPI 오류 스키마 확인
- `test_projects.py` — 세션·Origin·데모 5종·입력 검증·안전한 DB 오류·실제 DB CRUD와 관리자 포함 타 사용자 비공개 404. 업로드의 제한 수신·disk rollover 없음·저장소 payload·원본 즉시 close·오류 request ID. DB 시험은 `TEST_AUTH_DATABASE_URL`이 있을 때만 실행
- `test_prices.py` — `GET /api/prices`를 가짜 Mouser transport(손으로 쓴 응답)로 확인: 로그인 필요(401), `Cache-Control: no-store`, 화면 칸과 조회 시각만 돌려주기, 데모 모드·키 없음·호출 상한·Mouser 실패의 값 없음 모양, 품번 11개 이상·형식 오류의 공통 422 응답, 로그에 키·요청 주소·Mouser 값 없음
