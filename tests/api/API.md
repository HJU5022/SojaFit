# api

## 역할
- 이 폴더: 서버 API(`/health`, 로그인·세션, 가격·재고, 프로젝트, 대화·실행, 견적, 내 설정)와 그 아래 저장소·분석 서비스 연결을 확인하는 회귀 테스트.
- 넣는 것: `backend/main.py`, `backend/api/*.py`, `backend/auth.py`, `backend/errors.py`, `backend/logs.py`를 대상으로 한 `test_*.py`와, HTTP 경로를 거쳐야 의미가 있는 흐름 시험(`test_threads.py`, `test_deletion.py`, `test_public_grants.py`, 배포 점검 스크립트 `scripts/smoke/`의 오프라인 시험). DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌린다([TESTS.md](../TESTS.md)).
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색·적재 시험(`tests/rag/`), LLM 호출 시험(`tests/services/`), 일회성 인증 실측(`scripts/auth/`).
- 담당: 서비스·운영

실행: `uv run pytest -q tests/api`(저장소 루트).

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `API.md` | 이 문서 |
| `test_auth.py` | 인증 단위·DB 통합: 비밀번호 해시·강도, 세션 만료, 로그인 잠금, 데모 로그인, 자기 가입·IP 한도, 관리자 권한, 비활성 계정, 쿠키·출처. DB 시험은 `TEST_AUTH_DATABASE_URL`일 때만 |
| `test_local_live_config.py` | 로컬 실제 API Compose가 운영 DB·Origin을 상속하지 않고 별도 볼륨·loopback 포트·live 설정을 유지하는지 검사. 가짜 비밀값과 Compose 해석만 사용 |
| `test_email_auth.py` | 메일 인증 가입·비밀번호 재설정: 가짜 SMTP와 격리 DB로 인증 전 계정 없음, 토큰 만료·재발급·재사용·경합, 발송 한도, 재설정 뒤 세션 폐기, TLS 검증 |
| `test_google_users.py` | Google 일반 가입·기존 계정 연결: 합성 신원, 비밀번호 재확인, 관리자 최초 승인 유지, 만료·중복·동시 연결, 공유 IP 한도. 새 로컬 시험 DB만 허용 |
| `test_health.py` | `/health`, 서버 생성 요청 ID, 공통 오류 구조(401·403·404·422·500), 민감한 입력·내부 예외 비노출, OpenAPI 오류 스키마 |
| `test_errors.py` | `backend/errors.py` 오류 코드 표(기본 코드·상황 코드), DB 설정 없음 503, 남의 run 404, 한도 오류 코드, SSE `failed` frame의 코드, 오류 로그 줄(severity·request_id·5xx traceback, 질문 글·이메일 비노출) |
| `test_logs.py` | `backend/logs.py`: JSON 한 줄 칸, 요청 ID, 메시지 없는 traceback, `setup`의 처리기 부착, 접속 줄의 쿼리 글 가리기 |
| `test_openapi.py` | `/openapi.json`·`/docs` 계약: 본문 모델 예시와 모르는 칸 거부, 업로드 multipart 칸, SSE 설명, 경로 목록 고정(모두 `backend/api/` 라우터), 응답 모델이 화면 칸을 지우지 않음 |
| `test_frontend.py` | SPA 직접 진입, assets, 미빌드 때 화면 주소도 공통 404, API JSON 404와 기존 라우트 우선 |
| `test_prices.py` | `GET /api/prices`를 가짜 Mouser transport로: 로그인 필요, `no-store`, 화면 칸만 반환, 데모 모드·키 없음·호출 상한·Mouser 실패의 값 없음 모양, 품번 형식 오류 422, 로그에 키·요청 주소 없음 |
| `test_projects.py` | 프로젝트 HTTP 계약: 세션·Origin·입력 검증·안전한 DB 오류·실제 DB CRUD와 관리자 포함 타 사용자 비공개 404, 업로드의 제한 수신·원본 즉시 close·오류 request ID. DB 시험은 `TEST_AUTH_DATABASE_URL`이 있을 때만 |
| `test_external_circuits.py` | 완성 회로도 manifest·PNG 응답, 인증·`no-store`·`SCHEMATIC_NOT_FOUND` 경계 |
| `test_conversations.py` | 대화 인증·스트림·삭제 경계(가짜 분석 서비스): thread 연결, 대상 변경 409, 재개, `failed` frame의 `error.code`, 서비스 없음 503, 토큰 상한 429, recover, 저장 기록 GET, 데모 질문 목록 |
| `test_threads.py` | `Conversations`의 LED/표시기·다이오드 외 부품 분석 전 차단과 일반 다이오드 허용은 가짜 연결/그래프로 DB·모델 없이 검사. 소유권·체크포인트·재개·기억·토큰 상한·데모 조립의 PostgreSQL 통합 부분은 `TEST_THREAD_DATABASE_URL`일 때만 |
| `test_deletion.py` | 격리 DB의 삭제 범위: 프로젝트 삭제와 단일 대화 삭제가 해당 React 행과 같은 UUID 분석 기록만 지움, 탈퇴가 그 사용자의 기록·Store namespace·계정을 지우고 다른 사용자는 남김, 진행 중 분석과 탈퇴의 409, 보관 기간 청소 |
| `test_quotes.py` | 승인·견적·사례 API의 Origin·입력 allow-list·안전 오류(같은 메시지 두 번 승인은 409 `ALREADY_APPROVED`) |
| `test_full_service_flow.py` | 격리 PostgreSQL의 업로드 → interrupt 재개 → 승인 → 가격 없는 견적 → 소유권 → cascade 전체 흐름, 저장 대화 GET이 소유자에게만 보임 |
| `test_public_grants.py` | `db/026_revoke_public_grants_and_rls.sql`을 격리 PostgreSQL에서: 공개 역할 권한 회수, 재실행 동일, 소유자는 RLS 뒤에도 읽기·쓰기, anon은 코퍼스 표를 못 읽음, LangGraph 체크포인트·Store 표 동작 |
| `test_http_restart.py` | 명시적으로 실행할 때만 Docker로 실제 HTTP 서버를 종료·재기동해 소유자 재개와 다른 계정의 404를 확인. 기본 pytest에서는 건너뜀 |
| `test_http_smoke.py` | `scripts/smoke/http_smoke.py`를 가짜 서버(`httpx.MockTransport`)로 오프라인 시험: 단계 통과·실패 처리, `--confirm-live` 없으면 요청 없이 멈춤, 결과 파일·화면에 비밀값 없음 |
| `test_injection_http.py` | `scripts/smoke/injection_http.py`를 가짜 서버로 오프라인 시험: 정상 run 통과, 공격문이 정해진 위치에만 실림, 하루 한도에서 재시도 없이 멈춤, `--confirm-live` 없으면 요청 없이 멈춤, 결과 파일·화면에 비밀값·질문·공격문 없음 |
