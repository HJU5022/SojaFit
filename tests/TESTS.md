# tests

## 역할
- 이 폴더: PR마다 CI가 돌리는 회귀 테스트를 종류별 하위 폴더로 나눠 둔다. `pytest.ini`의 `testpaths = tests`가 하위 폴더까지 모두 찾는다.
- 넣는 것: 모듈별 테스트(`test_<모듈>.py`)를 맞는 하위 폴더에. 외부 호출은 가짜로 바꾸고, DB 시험은 전용 DB 주소 환경변수가 있을 때만 돌린다. 시험 헬퍼는 이 폴더 바로 아래 `db_schema.py` 하나뿐이다.
- 넣지 않는 것: 평가셋 전체 실행과 평가 실행기(`evals/`), 일회성 측정(`scripts/`).
- 담당: 각 모듈의 담당 (`tests/evals/`·`tests/repo/`는 평가·문서)

실행: 전체 `uv run pytest -q`, 하위 폴더만 `uv run pytest -q tests/graph`(저장소 루트).

## DB 시험 환경변수
환경변수가 없으면 해당 DB 시험은 건너뛴다. 운영·공유 DB 주소를 넣지 않는다.

| 환경변수 | 쓰는 시험 |
|---|---|
| `TEST_AUTH_DATABASE_URL` | `tests/api`(`test_auth.py`, `test_admin.py`, `test_projects.py`, `test_quotes.py`, `test_email_auth.py`, `test_google_users.py`, `test_full_service_flow.py`, `test_datasheets.py`), `tests/conversations/test_repository.py`, `tests/projects/test_project_repository.py`, `tests/projects/test_service_schema.py`, `tests/db/test_schema_docs.py`, `tests/db/test_public_grants.py` |
| `TEST_THREAD_DATABASE_URL` | `tests/api/test_threads.py`, `tests/api/test_deletion.py`, `tests/conversations/test_profile.py`, `tests/evals/test_approval_wait_report.py` |
| `TEST_DATABASE_URL` | `tests/rag/test_rag_retrieve.py`, `tests/rag/test_rag_storage.py`, `tests/rag/test_rag_ingest.py` |
| `TEST_GOOGLE_DATABASE_URL` | `tests/api/test_google_users.py`(없으면 `TEST_AUTH_DATABASE_URL`을 씀) |
| `TEST_INJECTION_DATABASE_URL` | `tests/evals/test_judgement_bundle.py` |

## 파일
| 파일 | 하는 일 |
|---|---|
| `TESTS.md` | 이 문서 |
| `db_schema.py` | 시험 헬퍼 `apply_service_schema(conn, agent=False)`: 서비스 표 기준선 `db/020_service_baseline.sql`을 시험 DB에 적용. 기준선 파일 이름을 부르는 유일한 곳 |
| `api/` | 서버 API·인증·삭제·OpenAPI 계약 시험. [API.md](api/API.md) |
| `conversations/` | 대화 저장소·공개 DTO·사용자 사실 기억 시험. [CONVERSATIONS.md](conversations/CONVERSATIONS.md) |
| `db/` | 서비스 DB 문서 생성 도구와 커밋된 문서-DB 일치, 026 공개 권한 · RLS SQL 시험. [DB.md](db/DB.md) |
| `evals/` | 동결 감시·평가 실행기·채점기·인젝션 기준선 시험. [EVALS.md](evals/EVALS.md) |
| `fixtures/` | 단위 테스트용 가공 회로(설명 파일 없음). `netlists/minimal.net`과 `netlists/invalid.net`은 합성 KiCad export 정상/미완성 표본, `netlists/minimal.kicad_sch`는 합성 KiCad 회로도 한 장(#52) |
| `graph/` | 단일 그래프 노드·MCP 검색기 시험. [GRAPH.md](graph/GRAPH.md) |
| `judge/` | 판정 코드 시험. [JUDGE.md](judge/JUDGE.md) |
| `mcp_skill/` | MCP 서버 도구 시험. [MCP_SKILL.md](mcp_skill/MCP_SKILL.md) |
| `multi_agent/` | 멀티 에이전트 시험. [MULTI_AGENT.md](multi_agent/MULTI_AGENT.md) |
| `projects/` | 프로젝트 저장소·정규화·회로도 시험. [PROJECTS.md](projects/PROJECTS.md) |
| `rag/` | 수집·파싱·청킹·적재·검색·카드 시험. [RAG.md](rag/RAG.md) |
| `repo/` | 저장소 구조 검사. [REPO.md](repo/REPO.md) |
| `services/` | LLM·Langfuse·Mouser·데모 재생 서비스 계층 시험. [SERVICES.md](services/SERVICES.md) |
