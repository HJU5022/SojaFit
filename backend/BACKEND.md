# backend

## 역할
- 이 폴더: 서비스 코드 전부를 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다. FastAPI 진입점과 로그인이 직접 들어 있고, 나머지는 하위 폴더에 나뉩니다.
- 넣는 것: API 진입점(`main.py`), 로그인·세션·계정 관리(`auth.py`), 하위 모듈 폴더. 사용자별 장기 기억 규칙(`memory.py`)은 `graph/`에 있습니다.
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터·코퍼스(`data/`), DB 표 정의(`db/`), 일회성 스크립트(`scripts/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더 설명 파일의 담당)

## 파일
- 사용자 일일/실행 예약 한도는 DB에서 공유하며 `ANALYSIS_*`로 설정한다.
- `__init__.py` — 패키지 표시
- 분석 실행의 HTTP 입구는 React 대화 API(`api/conversations.py`의 `POST /api/threads/{id}/runs` · `POST /api/runs/{id}/resume`)뿐이고 `conversations/memory_service.py`에 위임한다. React 이전 화면 `/workspace`와 그 경로(`/api/circuits` · `/api/threads` 목록·상세·메시지·재개·승인·재시도 · `/api/memories` · `/api/analysis/*`)는 11-10에 지웠다. 오류는 공통 error.code/message/request_id이고 `/api/threads` · `/api/me/memory`는 Cache-Control: no-store다.
- `main.py` — FastAPI 진입점. `/health`, 로그인·가입 API(`/api/auth/*`), 데모 버튼 로그인(`GET /api/auth/demo` · `POST /api/auth/demo-login`, `DEMO_MODE=1`에서만, 아니면 404), 탈퇴(`DELETE /api/me`: Origin 확인, 관리자 409, 분석 기록 → Store → 계정 순서, 지운 건수), 관리자 API(`/api/admin/users`), 가격·재고 API(`/api/prices`: 로그인 필요, 요청 때 `services/mouser.py`로 한 번 조회, `Cache-Control: no-store`, 데모 모드·키 없음이면 Mouser를 부르지 않음, ADR 0009), 서버 생성 `X-Request-ID`와 공통 JSON 오류 응답, Uvicorn 접속 로그의 Google 콜백 쿼리 제거. 인증 처리는 `auth.py`에 맡깁니다
- `auth.py` — scrypt 비밀번호, DB 세션, 로그인 잠금(계정당 15분 5회, 클라이언트 IP당 15분 30회), 자기 가입(클라이언트 IP당 UTC 하루 3회, IP 판단 `client_ip`), 데모 버튼 로그인(`demo_session`: 비밀번호 표식을 가진 시드 일반 계정 A · B에만 세션), Google 관리자 인증·연결 승인과 철회, 탈퇴의 마지막 단계인 계정 행 삭제(`delete_account`, 일반 계정만), 관리자 계정 관리 명령(`python -m backend.auth`). 대화·장기 기억 저장은 연결하지 않습니다
- `api/` — React 작업대가 쓰는 HTTP 라우터: 프로젝트 · 대화와 실행(SSE) · 승인 · 견적 · 승인 사례 · 내 설정. 세션 · Origin 확인 · 공통 오류를 씁니다. [API.md](api/API.md)
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
