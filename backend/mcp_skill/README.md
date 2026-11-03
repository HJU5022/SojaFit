# mcp_skill

## 역할
- 이 폴더: 가산점용 MCP 서버와 Skill 문서를 둡니다. 에이전트가 서비스 안에서 호출해야 하므로 Dockerfile이 복사하는 `backend/` 아래에 둡니다.
- 넣는 것: RAG 검색을 FastMCP 서버로 노출하는 코드(`mcp_server/`), 도메인 판단 지침 Skill(`skills/SKILL.md`).
- 넣지 않는 것: 판정 임계값과 규칙(`backend/judge/rules/`). SKILL.md에는 LLM 판단 지침만 적고 임계값은 다시 적지 않습니다.
- 담당: 가산을 시작할 때 정합니다.

## 파일
- `mcp_server/server.py` — FastMCP 서버
- `skills/SKILL.md` — Skill 문서

## 안내
둘 다 해야 인정되고, 3차에서 새로 한 통합만 인정됩니다. 2차에서 만든 MCP 서버나 Skill을 그대로 가져온 것은 인정되지 않습니다.

1. 3차 RAG 검색 등을 MCP 서버(FastMCP)로 노출하고, LangGraph 에이전트가 MCP 클라이언트로 호출합니다. (`mcp_server/`)
2. 도메인 판단 규칙을 Skill 문서(`skills/SKILL.md`)로 분리해 에이전트가 쓰고, **같은 평가셋으로 Skill이 있을 때와 없을 때의 점수 차이**를 보입니다.

현재 서버는 코퍼스 검색, 문서 정보 조회, 미검증 TSC 웹 후보 검색, 로컬 PDF 무결성 확인, 공개 회로 연결 정보 조회를 제공합니다.

- 실행: uv run --env-file .env python -m backend.mcp_skill.mcp_server.server (stdio MCP 클라이언트가 실행)
- search_corpus는 기존 retrieve를 호출하므로 적재된 DB와 기존 검색 설정이 필요합니다.
- get_corpus_document는 doc_id로 data/manifest.jsonl 기록을 읽습니다. PDF를 열거나 해시를 재검증하지 않습니다.
- search_tsc_web은 기본 꺼짐입니다. DEMO_MODE=0, EXA_WEB_SEARCH_ENABLED=1, EXA_API_KEY가 모두 필요합니다. 요청당 최대 1회 호출하므로 사용 전 무료 한도·요금 설정을 확인합니다.
- search_tsc_web은 자유 문장 대신 공개 TSC manifest의 doc_id를 받습니다. 공식 출처 경로와 문서명·개정이 일치하는 항목만 검색하며, 목록 밖이나 확인되지 않은 항목은 unverified로 차단합니다. Exa에는 고정 문구와 해당 문서명·개정이 전송됩니다.
- 목록의 과거 공개 출처 기록은 현재 공개 여부·최신성을 보장하지 않으며, 공개 품번을 검색한다는 사실 자체가 외부에 노출됩니다.
- 반환 URL은 아직 검증되지 않은 후보입니다. PDF를 받거나 내용·개정판을 확인하지 않습니다.
- `verify_tsc_pdf`는 저장소 PDF 표본 3건의 서명·크기·SHA-256만 manifest와 대조합니다. 전체 파싱·품번 및 개정 의미 검증은 하지 않으며 `content_verified=false`를 반환합니다.
- `get_circuit_info`는 고정 공개 회로 ID의 `connections.json`만 읽습니다. 사용자 업로드 회로와 사용자별 권한은 지원하지 않습니다.
- 그래프 클라이언트 연결, PDF 검증·적재, Skill 유무 비교와 평가 가산점 증명은 아직 구현하지 않았습니다.
- 상세 계약과 테스트 조건: [MCP 검색 도구 1차 작업서](../../docs/specs/mcp-search-tools.md).
