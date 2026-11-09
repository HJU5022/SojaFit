# api

## 역할
- 이 폴더: 서버 API(`/health`, 로그인·세션, 가격·재고)를 확인하는 회귀 테스트를 둡니다.
- 넣는 것: `backend/main.py`·`backend/api/*.py`·`backend/auth.py`·`backend/errors.py`·`backend/logs.py`를 대상으로 한 `test_*.py`. DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색·적재 시험(`tests/rag/`), LLM 호출 시험(`tests/services/`), 일회성 인증 실측(`scripts/auth/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/api`(저장소 루트).

## 파일
- `test_threads.py` — 격리 PostgreSQL에서 사용자 분석 서비스(`Conversations`)의 소유권·체크포인트 복구·재개·(HTTP 경로 없는) 승인 기록 멱등성 시험. 승인 사례는 새 분석에 넘기지 않고 Store에 쓰지 않음(승인 기록), 질문·재개 결과의 사용자 사실 참고(`profile_hints`)의 A/B 격리·고침·지움, `vector` 확장이 있는 DB에서 의미 순위·다시 임베딩도 본다. React 대화의 같은 UUID thread 연결(대상 고정·소유권·원문 미저장)과 React run·재개 HTTP가 실제 분석 서비스로 이어지는지, 하루 토큰 상한(사용자 · 서비스)의 원자적 차감 · 입장과 호출 직전 429 · 외부 호출 없음도 본다
- 같은 파일에서 키 없는 데모 재생(`DEMO_REPLAY=1`, 가짜 그래프 · 가짜 기록)의 확인 자리: 기록한 회로 · 대상 · 질문만 새 대화의 첫 질문으로 받고(스트림 전 `ensure_thread`와 `message`), 재개는 기록한 답만 받고, 기록이 없으면 503인지, 내용 없는 단계 기록/trace 실패 격리, 시간 초과 결과의 승인 차단, 다른 DB 역할의 전용 스키마 접근 차단을 확인한다. React 이전 화면(`/workspace`) HTTP 경로 · 기억 정정/철회 · 재시도 시험은 11-10에 경로와 함께 지웠다.
- 같은 파일에서 DB 없이 실제 분석 그래프 조립이 카드 도구(`card_find` · `card_specs`)를 넘기고, `timed_tool`로 감싼 뒤에도 `prefetch` · `also_read`가 남는지 본다(ADR 0016). 데모 재생 조립은 같은 재생 chat을 그래프 · 카드 도구에 넣고 Store를 넘기지 않으며, `DEMO_MODE=1`만으로는 재생하지 않는지도 본다.
- 같은 파일의 운영 준비 시험: 8개 병렬 thread의 일일 예약과 질문 격리, 명시적 TEST_THREAD_BACKUP_CONTAINER에서 pg_dump→일회용 DB 복원→Store/소유권/interrupt 재개. 공유 DB 복원은 실행하지 않는다.
- `API.md` — 이 문서
- `test_conversations.py` — 대화 인증·스트림·삭제 경계. 가짜 분석 서비스로 첫 run의 thread 연결, 대상 변경 409, 재개 버전, 완료 frame의 참고(내 설정)와 run 기록 미저장, 실패 frame의 `error.code` · 단계 이름(`오류`, 거절과 구분)과 예외 로그, 서비스 없음 503, 토큰 상한 429가 스트림 · run 행 전에 끝남, 본문 128 KiB 초과 413 · 끼워 넣은 칸 422 · 다른 Origin 403 · 재개 답 200자 초과 422 · DB 오류 503(내부 문구 비노출)이 분석 전에 끝남, 대화 있는 프로젝트 삭제가 분석 checkpoint · thread · 회로를 사용자 조건으로 먼저 지우고 프로젝트를 마지막에 지움. 데모 질문 목록(`GET /api/demo-questions`)은 재생 모드에서만 200이고 기록한 답 · 판정을 싣지 않으며 기록이 없으면 503, run이 질문 · 조건을 스트림 전 `ensure_thread`에 넘김
- `test_quotes.py` — 승인·견적·사례 API의 Origin·입력 allow-list·안전 오류(같은 메시지 두 번 승인 · 승인할 수 없는 판정은 409 `ALREADY_APPROVED`)
- `test_full_service_flow.py` — 격리 PostgreSQL의 업로드·interrupt 재개·승인(같은 메시지 두 번 승인은 막혀 한 건)·가격 없는 견적·타 사용자 차단·cascade 전체 흐름
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(세션 HMAC과 키 누락·교체, 데모 시드(데모 모드에서만 비밀번호 없는 A · B), 데모 버튼 로그인(데모 모드 밖 404 · A · B가 서로 다른 일반 사용자 · 비밀번호 로그인 실패 · 같은 이메일 가입 계정 · 관리자 · 비활성 계정에는 닿지 않음), 두 사용자 세션 격리, 관리자와 일반 사용자 권한, 비활성 사용자와 세션 폐기, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류, 질문 API 미노출, 비밀번호 해시 전용 CLI, 로그인 · 가입 · 계정 상태 본문의 모르는 칸 422(DB 호출 없음), 자기 가입의 중복·입력·동의(consent) 필수·출처·IP 하루 3회 한도와 Cloud Run 클라이언트 IP 판단, IP당 15분 로그인 실패 30회 잠금·구간 만료). 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_frontend.py` — SPA 직접 진입·assets·미빌드 때 화면 주소도 공통 404·API JSON 404와 기존 라우트 우선 경계
- `test_health.py` — `/health`, 서버 생성 요청 ID, 401·403(`ORIGIN_MISMATCH`)·404·422·500 공통 오류 구조, 민감한 입력·내부 예외 비노출, OpenAPI 오류 스키마 확인
- `test_deletion.py` — 격리 DB(public에 React 표가 있을 때만)의 삭제 범위: 프로젝트 삭제가 그 프로젝트의 React 행과 같은 UUID 분석 기록 · checkpoint만 지움, 탈퇴가 그 사용자의 모든 기록 · Store namespace · 계정을 지우고 다른 사용자(접두사가 같은 namespace 포함)는 남김, 일부 실패 뒤 다시 요청하면 마저 지움, 진행 중 분석과 탈퇴가 서로 409, 관리자 409. 보관 기간 청소: 60일 지난 프로젝트 · 분석 대화 · 빈 회로만(어제 run이 있는 프로젝트 · 59일 · 사용자 사실은 남김), 30일 지난 기록만(아직 걸린 로그인 잠금 · 15분 창 안의 행은 남김), 단계 · 표마다 묶음 상한, 새 분석이 청소를 부르고 청소 실패는 분석을 막지 않음
- `test_projects.py` — 세션·Origin·데모 5종·입력 검증·안전한 DB 오류·실제 DB CRUD와 관리자 포함 타 사용자 비공개 404. 업로드의 제한 수신·disk rollover 없음·저장소 payload·원본 즉시 close·오류 request ID. DB 시험은 `TEST_AUTH_DATABASE_URL`이 있을 때만 실행
- `test_errors.py` — 오류 코드 15개(ADR 0019): 표 · 기본 코드 · 표에 없는 405, `DATABASE_URL` 없음 503 `UNAVAILABLE`(500 아님) · Google 콜백은 그래도 로그인 화면 오류로 이동, 남의 run 404, 가입 IP 한도 `RATE_LIMITED`, 하루 토큰 · USD `LIMIT_EXCEEDED`와 호출 간격 `RATE_LIMITED`, 조건 대기 `CONDITION_PENDING`, 분석 실패의 502(공급자) · 503(DB · 설정) · 504(시간) · 실행 상한 429, SSE `failed`의 같은 코드, 오류 로그 줄의 severity · request_id(스레드 풀 · 응답 보낼 때까지) · 5xx traceback · 질문 글 · 이메일 비노출(DB · 바깥 호출 없음)
- `test_openapi.py` — HTTP API 계약(`/openapi.json` · `/docs`): JSON 본문 모델 11개마다 예시가 있고 그대로 통과하며 모르는 칸을 막음, 업로드의 multipart `file` · `name` 칸, SSE 두 경로의 `text/event-stream`과 이벤트 6개 설명, 204 · SSE 밖 성공 응답의 빈 스키마 없음, 경로 37개(메서드, 경로) 고정과 모두 `backend/api/` 라우터에 태그와 함께 있음(`main.py`에 경로 함수 없음), 응답 모델이 화면이 읽는 칸(`frontend/src/api/*.ts`)을 지우지 않음(승인 · 견적 · 사례 · 대화 · run은 가짜 연결로 실제 저장소 코드를, 내 설정은 실제 `ProfileMemory`를 거침)
- `test_logs.py` — JSON 한 줄 로그(`backend/logs.py`): 칸(severity · time · logger · message · extra), 문맥 변수와 직접 넘긴 request_id, 예외 메시지 없는 traceback(원인 사슬 · 고리), setup이 처리기 있는 루트는 그대로 두고 없으면 한 번 붙여 uvicorn 줄도 JSON으로 · 500과 겹친 uvicorn 줄 빼기
- `test_prices.py` — `GET /api/prices`를 가짜 Mouser transport(손으로 쓴 응답)로 확인: 로그인 필요(401), `Cache-Control: no-store`, 화면 칸과 조회 시각만 돌려주기, 데모 모드·키 없음·호출 상한·Mouser 실패의 값 없음 모양, 품번 11개 이상·형식 오류의 공통 422 응답, 로그에 키·요청 주소·Mouser 값 없음
- `test_http_smoke.py` — HTTP 점검 스크립트(`scripts/smoke/http_smoke.py`)를 쿠키 · Origin · 소유권을 지키는 가짜 서버(`httpx.MockTransport`)로: 1~9단계 전체 통과(두 번째 승인 409 `ALREADY_APPROVED`를 통과로 셈), `requires_input`이 없거나 스트림 전 503이면 그 단계 실패 · 5~7단계 건너뜀 · 8단계 격리는 계속 · 종료 코드 1, 결과 파일 · 화면에 비밀번호 · 쿠키 값 · 이메일 · 답 글 없음, `--confirm-live` 없으면 요청 없이 멈춤, 재개 값 규칙, 데모 질문 회로가 데모 카탈로그에 있음
