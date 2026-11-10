# backend

## 역할
- 이 폴더: 서비스 코드 전부를 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다. FastAPI 진입점(앱 조립)과 로그인 · 세션 처리가 직접 들어 있고, HTTP 경로와 나머지는 하위 폴더에 나뉩니다.
- 넣는 것: API 진입점(`main.py`)과 진입점에서 나눈 공통 오류 코드(`errors.py`) · JSON 로그(`logs.py`), 로그인·세션·계정 관리(`auth.py`), 하위 모듈 폴더. 공통 오류 · 로그는 라우터 · 서비스도 import해 `main.py`에 두면 순환 import가 된다. 사용자별 장기 기억 규칙(`memory.py`)은 `graph/`에 있습니다.
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터·코퍼스(`data/`), DB 표 정의(`db/`), 일회성 스크립트(`scripts/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더 설명 파일의 담당)

## 파일
- 사용자 일일/실행 예약 한도는 DB에서 공유하며 `ANALYSIS_*`로 설정한다.
- `__init__.py` — 패키지 표시
- 분석 실행의 HTTP 입구는 React 대화 API(`api/conversations.py`의 `POST /api/threads/{id}/runs` · `POST /api/runs/{id}/resume`)뿐이고 `conversations/memory_service.py`에 위임한다. React 이전 화면 `/workspace`와 그 경로(`/api/circuits` · `/api/threads` 목록·상세·메시지·재개·승인·재시도 · `/api/memories` · `/api/analysis/*`)는 11-10에 지웠다. 오류는 공통 error.code/message/request_id이고 `/api/threads` · `/api/me/memory`는 Cache-Control: no-store다.
- `main.py` — FastAPI 진입점. 앱 조립만 한다: 수명(JSON 로그 · 인증 설정 검사 · 분석 저장소), 공통 JSON 오류 처리기(HTTP · 검증 · 500 · DB 503), 서버 생성 `X-Request-ID` 미들웨어(가장 바깥), 보안 응답 헤더 4개(같은 미들웨어), `/api/` 본문 128 KiB 한도(넷리스트 업로드 제외) · `/api/threads` · `/api/me/memory` no-store 미들웨어, `api/` 라우터 등록, React 화면 연결(라우터 뒤). 경로 함수는 두지 않는다(11-10 조장 결정, `tests/api/test_openapi.py`가 확인). 인증 처리는 `auth.py`, 경로는 `api/`에 맡깁니다
- `errors.py` — 오류 응답 `error.code` 15개(ADR 0019): 상태별 기본 코드, 상황 코드 4개(`ORIGIN_MISMATCH` · `CONDITION_PENDING` · `ALREADY_APPROVED` · `LIMIT_EXCEEDED`)를 붙이는 `ApiError`, 코드 고르기(`code_for`, 표에 없는 4xx · 5xx도 15개 안에서), 오류 한 줄 로그(`log_error`: 4xx INFO, 5xx ERROR + traceback)
- `logs.py` — stdout JSON 한 줄 로그: severity · time · logger · message · request_id(요청 문맥 변수) · extra 칸, 예외 메시지를 뺀 traceback, 서버 시작 때 루트 · uvicorn 로거에 한 번 붙이는 `setup`(루트에 처리기가 있으면 그대로), 접속 줄 경로의 쿼리 글을 `?<redacted>`로 가리는 `hide_query`
- `auth.py` — scrypt 비밀번호, DB 세션, 로그인 잠금(계정당 15분 5회, 클라이언트 IP당 15분 30회), 이메일 가입(`DEMO_MODE=1` 전용, 클라이언트 IP당 UTC 하루 3회, IP 판단 `client_ip`), 데모 버튼 로그인(`demo_session`: 비밀번호 표식을 가진 시드 일반 계정 A · B에만 세션), Google 가입 · 로그인(`google_session` · `google_signup`: 이메일이 같은 활성 계정에는 승인 없이 연결, 동의한 새 이메일은 비밀번호 없는 일반 계정)과 관리자 연결 철회 · 옛 승인 CLI, 탈퇴의 마지막 단계인 계정 행 삭제(`delete_account`, 일반 계정만), 관리자 계정 관리 명령(`python -m backend.auth`). 대화·장기 기억 저장은 연결하지 않습니다
- `api/` — HTTP 경로 전부: `/health`, 로그인 · 이메일 가입과 데모 버튼 로그인(`DEMO_MODE=1`에서만) · Google 가입 · 로그인(`auth.py`), 관리자 계정(`admin.py`), 가격 · 재고(`prices.py`, ADR 0009), 내 설정 · 탈퇴(`profile.py`), 프로젝트 · 대화와 실행(SSE) · 승인 · 견적 · 승인 사례. `<이름>.py`가 `frontend/src/api/<이름>.ts`와 짝입니다. 세션 · Origin 확인 · 공통 오류를 씁니다. [API.md](api/API.md)
- `conversations/` — 프로젝트 소유 대화 저장소와 React run·재개가 거치는 사용자 분석 서비스(체크포인트 · 예산 · 사용자 사실 기억). [CONVERSATIONS.md](conversations/CONVERSATIONS.md)
- `projects/` — 사용자 소유 데모 프로젝트·정규화 회로 저장소와 DTO. [PROJECTS.md](projects/PROJECTS.md)
- `multi_agent/` — D5 멀티 에이전트(Supervisor + 서브에이전트). D4 단일 그래프(`graph/`)와 분리. [MULTI_AGENT.md](multi_agent/MULTI_AGENT.md)
- `graph/` — LangGraph 그래프: 상태, 노드, 조립, 사용자별 장기 기억 규칙(`memory.py`). [GRAPH.md](graph/GRAPH.md)
- `prompts/` — 노드가 LLM에 보내는 프롬프트 원문과 버전 기록. [PROMPTS.md](prompts/PROMPTS.md)
- `rag/` — 하이브리드 검색(`retrieve.py`), 벡터 열 형식·DB 용량 점검(`storage.py`), 오프라인 데이터시트 도구(`pipeline/`). [RAG.md](rag/RAG.md)
- `services/` — LLM·임베딩 호출, Langfuse 프롬프트 관리, Mouser 가격·재고 조회. [SERVICES.md](services/SERVICES.md)
- `judge/` — 회로 역할·대체 조건·판정의 결정적 코드: 역할 규칙 파일(`rules/roles.yaml`), 기준식 계산, 시험 조건 비교, 판정 5종 · 찾기 조건 · 후보 정렬. [JUDGE.md](judge/JUDGE.md)
- `web/` — API 등록 뒤 빌드한 React 화면을 같은 출처로 연결(미빌드면 화면 주소도 공통 404). [WEB.md](web/WEB.md)
- `mcp_skill/` — 가산: MCP 서버와 도메인 Skill. [MCP_SKILL.md](mcp_skill/MCP_SKILL.md)
