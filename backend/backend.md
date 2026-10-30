# backend

## 역할
- 이 폴더: FastAPI 서비스 코드 전부를 둡니다. Dockerfile이 이 폴더를 이미지에 복사합니다.
- 넣는 것: API 진입점, 로그인, 사용자별 기억, 환경변수를 읽는 곳(`settings.py`), 모듈 사이 공유 데이터 형식(`schemas.py`), 하위 모듈.
- 넣지 않는 것: 평가 스크립트(`evals/`), 테스트(`tests/`), 원본 데이터(`data/`).
- 담당: 서비스·운영 (하위 폴더는 각 폴더의 `.md`에 적힌 담당)

## 파일
- `main.py` — FastAPI 진입점(`/health`)
- `auth.py` — 로그인과 사용자 식별. 로그인한 사용자 id로 대화(thread)와 장기 기억(Store namespace)을 나눕니다(G4). 평가자는 평가용 계정 2개로 두 사용자의 대화와 기억이 섞이지 않는지 봅니다
- `memory.py` — 사용자별 장기 기억. 승인된 판정·견적 사례를 쌓고, 틀린 기억은 승인 절차를 거쳐 고칩니다
- `judge/` — 회로 역할·대체 조건·판정. [judge.md](judge/judge.md)
- `graph/` — LangGraph 그래프. [graph.md](graph/graph.md)
- `prompts/` — LLM 프롬프트와 버전 기록. [prompts.md](prompts/prompts.md)
- `rag/` — 수집·파싱·검색. [rag.md](rag/rag.md)
- `services/` — LLM·임베딩 호출, 견적서, 가격·재고. [services.md](services/services.md)
- `web/` — 화면. [web.md](web/web.md)
- `mcp_skill/` — 가산: MCP 서버와 Skill. [mcp_skill.md](mcp_skill/mcp_skill.md)
