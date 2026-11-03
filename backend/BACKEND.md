# backend

## 역할
- 이 폴더: 서비스 코드 전부를 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다. FastAPI 진입점과 로그인, 사용자별 기억(자리만)이 직접 들어 있고, 나머지는 하위 폴더에 나뉩니다.
- 넣는 것: API 진입점(`main.py`), 로그인·세션·계정 관리(`auth.py`), 사용자별 장기 기억 규칙(`memory.py`), 하위 모듈 폴더. 환경변수를 한곳에서 읽는 `settings.py`와 공유 데이터 형식 `schemas.py`는 아직 없습니다.
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터·코퍼스(`data/`), DB 표 정의(`db/`), 일회성 스크립트(`scripts/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더 설명 파일의 담당)

## 파일
- `__init__.py` — 패키지 표시
- `main.py` — FastAPI 진입점. `/health`, 인증 API(`/api/auth/login`·`me`·`logout`), 관리자 API(`/api/admin/users`). HTTP 입출력만 다루고 인증 처리는 `auth.py`에 맡깁니다
- `auth.py` — scrypt 비밀번호, DB 세션, 로그인 잠금, 관리자 계정 관리, 계정 생성 명령(`python -m backend.auth`). 로그인한 사용자 id로 대화(thread)와 장기 기억을 나누는 연결은 그래프 구현 뒤에 붙입니다(SPEC 4절, G4)
- `memory.py` — 사용자별 장기 기억(Store) namespace `("memories", user_id)`만 정의합니다. 부르는 곳이 아직 없고, 승인 사례 저장과 틀린 기억 정정은 없습니다
- `graph/` — LangGraph 그래프: 상태, 노드, 조립. [GRAPH.md](graph/GRAPH.md)
- `prompts/` — 노드가 LLM에 보내는 프롬프트 원문과 버전 기록. [PROMPTS.md](prompts/PROMPTS.md)
- `rag/` — 데이터시트 수집·파싱·청킹·적재(오프라인 CLI)와 하이브리드 검색. [RAG.md](rag/RAG.md)
- `services/` — LLM·임베딩 호출과 Langfuse 프롬프트 관리. [SERVICES.md](services/SERVICES.md)
- `judge/` — 회로 역할·대체 조건·판정의 결정적 코드. 아직 비어 있습니다. [JUDGE.md](judge/JUDGE.md)
- `web/` — 로그인·입력·승인·견적 화면. 아직 화면 코드가 없습니다. [WEB.md](web/WEB.md)
- `mcp_skill/` — 가산: MCP 서버와 도메인 Skill. [MCP_SKILL.md](mcp_skill/MCP_SKILL.md)
