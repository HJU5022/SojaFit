# backend

## 역할
- 이 폴더: 서비스 코드 전부. `Dockerfile`이 `backend/`를 이미지에 복사하고 `uvicorn backend.main:app`으로 띄운다. FastAPI 진입점, 공통 오류·로그, 로그인·세션 처리가 이 폴더 바로 아래에 있고, HTTP 경로와 나머지는 하위 폴더에 나뉜다.
- 넣는 것: 앱 조립(`main.py`), 공통 오류 코드(`errors.py`), JSON 로그(`logs.py`), 로그인·세션·계정 관리(`auth.py`, `auth_email.py`), 하위 모듈 폴더. 공통 오류·로그는 라우터와 서비스도 import하므로 `main.py`에 두지 않는다(순환 import).
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터·코퍼스(`data/`), DB 표 정의(`db/`), 일회성 스크립트(`scripts/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더 설명 파일의 담당)

## 요청이 지나가는 길
| 단계 | 코드 |
|---|---|
| 앱 조립: 수명, 공통 오류 처리기, 미들웨어, 라우터 등록, React 화면 연결 | `main.py` |
| HTTP 경로 | `api/` (경로 목록은 [API.md](api/API.md), 경로 수는 [SPEC.md](../SPEC.md) 4절) |
| 대화 저장과 분석 서비스 | `conversations/` |
| 질문 처리 그래프 | `multi_agent/` (그래프가 import하는 도구는 `graph/`, 분담은 [GRAPH.md](graph/GRAPH.md)) |
| 검색·판정·외부 호출 | `rag/`, `judge/`, `services/` |

분석 실행의 HTTP 입구는 `api/conversations.py`의 run·재개 경로이고 `conversations/memory_service.py`에 위임한다. `main.py`는 경로 함수를 두지 않는다(`tests/api/test_openapi.py`가 확인).

## 파일
| 파일 | 하는 일 |
|---|---|
| `BACKEND.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `main.py` | FastAPI 진입점. 수명(JSON 로그 켜기, 인증 설정 검사, `THREADS_ENABLED=1`이면 분석 서비스 생성), 공통 JSON 오류 처리기, 요청 ID·보안 헤더·본문 한도·`no-store` 미들웨어, `api/` 라우터 등록, React 화면 연결. 모든 `psycopg.Error` · 풀 대기 초과는 503(코드 버그도 저장소 장애로 보임), `DuplicateProject`는 409 `details.duplicates` |
| `errors.py` | 오류 응답 `error.code` 표(`DEFAULT_CODES`, `SPECIAL_CODES`), `ApiError`, `code_for`, 오류 한 줄 로그 `log_error`. 코드 목록은 SPEC.md·ADR 0019 |
| `logs.py` | stdout JSON 한 줄 로그: 요청 ID 문맥 변수, `JsonFormatter`, 예외 메시지를 뺀 traceback, 서버 시작 때 로거에 붙이는 `setup`, 접속 줄의 쿼리 글 가리기 `hide_query` |
| `auth.py` | scrypt 비밀번호, DB 세션, 로그인 잠금·가입 한도, 데모 로그인, Google 가입·로그인, 탈퇴의 계정 행 삭제, 관리자 계정 관리와 그 작업 이력(`admin_audit`, db/034), 관리자 CLI(`python -m backend.auth`). 직접 `signup`은 내부·시험용 |
| `auth_email.py` | 이메일 인증 가입·비밀번호 재설정의 일회용 토큰, 발송 한도, 계정 행 잠금. 재설정하면 그 계정의 세션 · 로그인 실패 기록을 지운다. 메일 발송은 `services/mail.py` |
| `api/` | HTTP 경로 전부. [API.md](api/API.md) |
| `conversations/` | 프로젝트 소유 대화 저장소와 React run·재개가 거치는 사용자 분석 서비스. [CONVERSATIONS.md](conversations/CONVERSATIONS.md) |
| `projects/` | 사용자 소유 프로젝트·정규화 회로 저장소, 데모 회로도, 외부 회로도 변환. [PROJECTS.md](projects/PROJECTS.md) |
| `multi_agent/` | 서비스가 쓰는 질문 처리 그래프(Supervisor + 서브에이전트). [MULTI_AGENT.md](multi_agent/MULTI_AGENT.md) |
| `graph/` | 단일 에이전트 기준선 그래프와 서비스가 import하는 공용 도구. [GRAPH.md](graph/GRAPH.md) |
| `prompts/` | 노드가 LLM에 보내는 프롬프트 원문과 버전 기록. [PROMPTS.md](prompts/PROMPTS.md) |
| `rag/` | 하이브리드 검색, 카드 읽기·찾기, 단위 환산, 오프라인 데이터시트 도구. [RAG.md](rag/RAG.md) |
| `services/` | LLM·임베딩 호출, Langfuse, Mouser, 메일, 데모 재생, 견적 저장. [SERVICES.md](services/SERVICES.md) |
| `judge/` | 회로 역할 규칙, 기준식 계산, 시험 조건 비교, 판정 5종. [JUDGE.md](judge/JUDGE.md) |
| `web/` | 빌드한 React 화면을 같은 출처로 연결. [WEB.md](web/WEB.md) |
| `mcp_skill/` | MCP 서버와 도메인 Skill(가산). [MCP_SKILL.md](mcp_skill/MCP_SKILL.md) |
