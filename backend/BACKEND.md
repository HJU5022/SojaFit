# backend

## 역할
- 이 폴더: FastAPI 서비스 코드 전부를 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다.
- 넣는 것: API 진입점, 로그인, 사용자별 기억, 환경변수를 읽는 곳(`settings.py`, 아직 없음), 모듈 사이 공유 데이터 형식(`schemas.py`, 아직 없음), 하위 모듈.
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터(`data/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더의 `.md`에 적힌 담당)

## 파일
- `main.py` — FastAPI 진입점. `/health`, 로그인 화면(`/`), 인증 API(`/api/auth/login`·`me`·`logout`), 관리자 API(`/api/admin/users`)
- `auth.py` — 이메일·비밀번호 로그인, DB 세션, 관리자 계정 관리, 계정 생성 명령(`python -m backend.auth`). 로그인한 사용자 id로 대화(thread)와 장기 기억(Store namespace)을 나누는 연결은 그래프 구현 뒤에 붙입니다(SPEC 4절, G4)
- `memory.py` — 사용자별 장기 기억. 지금은 Store namespace `("memories", user_id)`만 정의합니다. 승인 사례 저장과 틀린 기억 정정은 아직 없습니다
- `judge/` — 회로 역할·대체 조건·판정. [JUDGE.md](judge/JUDGE.md)
- `graph/` — LangGraph 그래프. [GRAPH.md](graph/GRAPH.md)
- `prompts/` — LLM 프롬프트와 버전 기록. [PROMPTS.md](prompts/PROMPTS.md)
- `rag/` — 수집·파싱·검색. [RAG.md](rag/RAG.md)
- `services/` — LLM·임베딩 호출, 견적서, 가격·재고. [SERVICES.md](services/SERVICES.md)
- `web/` — 화면. [WEB.md](web/WEB.md)
- `mcp_skill/` — 가산: MCP 서버와 Skill. [MCP_SKILL.md](mcp_skill/MCP_SKILL.md)
