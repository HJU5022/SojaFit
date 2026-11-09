# tests

## 역할
- 이 폴더: PR마다 CI가 돌리는 회귀 테스트를 종류별 하위 폴더로 나눠 둡니다. `pytest.ini`의 `testpaths = tests`가 하위 폴더까지 모두 찾습니다.
- 넣는 것: 모듈별 테스트(`test_<모듈>.py`)를 맞는 하위 폴더에. 외부 호출은 가짜로 바꾸고, DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌립니다. 이 폴더 바로 아래에는 파일을 두지 않습니다.
- 넣지 않는 것: 평가셋 전체 실행과 평가 실행기(`evals/`), 일회성 측정(`scripts/`).
- 담당: 각 모듈의 담당 (`tests/evals/`·`tests/repo/`는 평가·문서)

실행: 전체 `uv run pytest -q`, 하위 폴더만 `uv run pytest -q tests/graph`(저장소 루트).

## 파일
- `TESTS.md` — 이 문서
- `api/` — 서버 API·인증 시험. [API.md](api/API.md)
- `conversations/` — 격리 DB 대화·체크포인트 시험. [CONVERSATIONS.md](conversations/CONVERSATIONS.md)
- `projects/` — 실제 격리 DB에서 소유권·cascade·원자성·권한 시험. [PROJECTS.md](projects/PROJECTS.md)
- `evals/` — 동결 감시·평가 실행기·Skill 쌍 시험. [EVALS.md](evals/EVALS.md)
- `multi_agent/` — 멀티 에이전트 시험. [MULTI_AGENT.md](multi_agent/MULTI_AGENT.md)
- `graph/` — 질문 처리 그래프 노드 시험. [GRAPH.md](graph/GRAPH.md)
- `mcp_skill/` — MCP 서버 도구 6종 시험(외부 호출 없음). [MCP_SKILL.md](mcp_skill/MCP_SKILL.md)
- `judge/` — 판정 코드(시험 조건 · 기준식 · 판정 5종 · 규칙 파일) 시험. [JUDGE.md](judge/JUDGE.md)
- `fixtures/` — 단위 테스트용 가공 회로(설명 파일 없음). `netlists/minimal.net`, `netlists/invalid.net`은 공개 합성 KiCad export 정상/미완성 표본이며 외부 회로 원본·실사용 파일/경로·비밀값을 포함하지 않는다
- `rag/` — 수집·파싱·청킹·적재·검색 시험. [RAG.md](rag/RAG.md)
- `repo/` — 저장소 구조 검사. [REPO.md](repo/REPO.md)
- `services/` — LLM·Langfuse 서비스 계층 시험. [SERVICES.md](services/SERVICES.md)
