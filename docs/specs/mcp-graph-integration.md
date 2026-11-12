# MCP `search_corpus` LangGraph 통합

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 8.7 MCP 검색 도구, 도구 계약은 [mcp-search-tools.md](mcp-search-tools.md))
- 관련 문서: [mcp-search-tools.md](mcp-search-tools.md), `backend/graph/GRAPH.md`, `backend/mcp_skill/MCP_SKILL.md`

## Why

- 페르소나: SojaFit의 LangGraph와 통합 검증을 담당하는 개발자.
- 상황: 그래프는 동기 검색기 `retriever(query, *, parts=...)`를 주입받는다. FastMCP stdio 서버의 `search_corpus`를 실제 MCP 클라이언트로 호출하는 어댑터가 필요하다.
- 문제:
  1. MCP 서버 단위 테스트가 통과해도 그래프에서 실제로 사용할 수 있는지 증명되지 않는다.
  2. 현재 그래프 계약은 빈 검색 결과와 검색기 장애를 구분하지 않아, MCP·DB 장애를 코퍼스에 문서가 없는 것으로 잘못 안내할 수 있다.
  3. 동기 LangGraph 호출과 비동기 MCP 세션의 시작·재사용·종료 기준이 없다.
- 측정 지표: 가짜 MCP 정상·빈 결과·장애 경로 통과, 검색 호출 최대 2회, 격리 합성 DB의 그래프→stdio MCP→검색→출처 경로 1회 이상 재현.

## Goal

- MCP stdio `search_corpus(query, k=5, parts=...)`를 기존 그래프 검색기 계약에 맞춘 동기 어댑터로 제공한다.
- 기존 `build_graph(retriever=...)` 주입 방식과 직접 RAG 기본 경로를 유지한다.
- 정상 빈 결과와 MCP 세션·프로토콜·응답 형식 장애를 서로 다른 그래프 상태와 사용자 응답으로 처리한다.
- 첫 검색과 재작성 뒤 검색을 합쳐 MCP 검색 호출을 최대 2회로 유지한다.
- 가짜 클라이언트 단위 테스트와 실제 stdio 서버 통합 테스트를 분리한다. 실제 DB 검사는 격리 합성 DB와 `TEST_DATABASE_URL`이 있을 때만 실행한다.
- Out of Scope:
  - `backend/mcp_skill/` 서버 구현, 도구 이름·인자·반환 형식 변경.
  - `get_corpus_document`, `search_tsc_web`, `verify_tsc_pdf`, `get_circuit_info`의 사용자 그래프 연결. 어댑터가 연결한 도구는 `search_corpus`와 `check_corpus`(`StdioMcpRetriever.check`, 품번·판 확인)뿐이다.
  - Exa·LLM 실호출, 웹 후보 PDF 다운로드·검증·적재.
  - 운영·공유 DB 사용, 기존 DB나 Docker 볼륨 초기화.
  - Supervisor·서브에이전트·체크포인트(이 문서의 어댑터와 별개로 `backend/multi_agent/`가 가진다).
  - 동결 평가셋 점수.

## What

### Happy Path

1. 호출자는 `StdioMcpRetriever` 컨텍스트를 열고 이를 `build_graph(retriever=...)`에 주입한다.
2. 어댑터는 FastMCP 서버 프로세스와 `ClientSession`을 한 번 초기화하고 그래프 실행 동안 재사용한다.
3. 기존 검색 노드는 질문·품번 필터를 어댑터에 전달한다.
4. 어댑터는 `search_corpus`를 `query`, `k=5`, `parts`로 호출하고 MCP 텍스트 응답의 JSON 청크 목록을 검증한다.
5. 정상 청크는 기존 `docs`로 들어가 채점·생성으로 진행한다.
6. 첫 청크가 채점을 통과하지 못하면 기존 재작성 노드를 거쳐 같은 세션에서 한 번 더 검색한다.
7. 컨텍스트 종료 시 MCP 세션·stdio 스트림·서버 프로세스를 종료한다.

### Edge Cases

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | MCP가 정상적으로 `[]`를 반환 | `retrieval_error` 없이 기존 문서 없음 경로로 진행 |
| EC-02 | 서버 시작·세션 초기화·도구 호출 timeout | `RetrievalUnavailableError`로 경계를 넘기고 오류 종류만 상태에 기록, 재호출 없이 장애 응답 |
| EC-03 | MCP `CallToolResult.isError=true` | 공급자 본문을 노출하지 않고 `tool_error` 종류로 처리 |
| EC-04 | 응답이 JSON이 아니거나 목록이 아님 | `invalid_response`로 처리하고 빈 결과로 바꾸지 않음 |
| EC-05 | 청크에 필수 필드가 없거나 타입이 잘못됨 | 전체 응답을 `invalid_response`로 거부하고 일부 청크만 사용하지 않음 |
| EC-06 | 첫 검색 청크가 채점을 통과하지 못함 | 기존 재작성 뒤 같은 MCP 세션에서 한 번만 재검색 |
| EC-07 | 두 번째 검색도 통과하지 못함 | 세 번째 호출 없이 기존 근거 없음 응답 |
| EC-08 | 컨텍스트 안에서 여러 문항 실행 | 한 세션을 재사용하되 문항별 그래프 State와 검색 횟수는 공유하지 않음 |
| EC-09 | `TEST_DATABASE_URL`이 없음 | 실제 DB 통합 검사는 명시적 사유로 skip, 가짜 클라이언트 검사는 계속 실행 |
| EC-10 | 컨텍스트 종료 중 오류 | 원래 검색 결과나 예외를 덮어쓰지 않고 자원을 최선으로 정리하며 비밀값을 출력하지 않음 |

## How

### 파일

- 어댑터·분기: `backend/graph/mcp_retriever.py`, `backend/graph/state.py`, `backend/graph/nodes.py`, `backend/graph/build.py`.
- 시험: `tests/graph/test_graph_mcp_retriever.py`, `tests/graph/test_graph_mcp_stdio.py`, `tests/graph/test_graph_build.py`.
- MCP 서버와 도구 계약(`backend/mcp_skill/mcp_server/server.py`)은 이 문서의 범위 밖이다([mcp-search-tools.md](mcp-search-tools.md)).
- 서비스 분석 경로는 어댑터의 `check`(`check_corpus`)만 쓴다. `search_corpus` 어댑터 호출은 단일 그래프 기준선(`backend/graph/`)과 평가 실행기(`evals/runners/run_graph.py`)가 쓴다.

### 어댑터 계약

```text
StdioMcpRetriever(command, args, env, timeout_seconds)
  __enter__() -> self
  __call__(query: str, *, parts: list[str] | None = None) -> list[dict]
  __exit__(...) -> None
```

- 외부 동작은 기존 검색기와 같은 동기 호출이다. 내부 비동기 stdio·`ClientSession`은 전용 실행 루프에서 관리한다.
- 컨텍스트 진입 때 서버와 세션을 초기화하고, 호출마다 새 서버를 띄우지 않는다.
- 도구 호출 인자는 `{"query": query, "k": 5, "parts": parts}`이며 `parts=None`도 기존 계약대로 전달한다.
- `CallToolResult`가 오류가 아니고, `structuredContent.result`가 목록일 때 성공으로 본다. 이전 단일 JSON 텍스트 응답은 호환 경로로만 허용한다.
- 각 청크는 최소한 `chunk_id`, `file`, `page`, `content`, `table`, `doc_parts`를 가진다. `chunk_id`는 정수, `file`·`content`는 문자열, `page`는 정수, `table`은 문자열 또는 null, `doc_parts`는 문자열 목록이어야 한다.
- 오류 본문·환경변수·명령 전체를 예외 메시지나 State에 복사하지 않는다.

### 그래프 상태와 분기

```text
retrieval_error = null
  또는 {"kind": "mcp_unavailable" | "timeout" | "tool_error" | "invalid_response"}
```

- MCP 어댑터는 위 종류를 가진 `RetrievalUnavailableError`만 그래프 경계로 보낸다.
- 검색 노드는 이 예외만 잡아 `docs=[]`, `retrieval_error={kind}`, `tries=1`, `path=["검색"]`을 반환한다.
- 검색 직후 분기는 `retrieval_error`가 있으면 채점·재작성 없이 거절 노드로 보낸다. 오류가 없으면 기존 채점으로 간다.
- 거절 노드는 검색 장애와 문서 없음 문구를 구분한다. 검색 장애 응답에는 내부 오류 원문, 키, DB 주소를 넣지 않는다.
- 직접 RAG 검색기와 기존 가짜 검색기의 성공 계약은 바꾸지 않는다. `build_graph()` 기본 동작도 직접 검색을 유지한다.

### 검증

1. 가짜 MCP transport로 정확한 도구·인자, `structuredContent.result` 청크·빈 목록, timeout, `isError`, 비정상 응답, 필드 누락, 세션 재사용·종료를 검사한다.
2. 가짜 retriever 그래프로 정상·빈 결과·장애·재작성·두 번 상한 경로를 검사한다.
3. 실제 stdio 서버 테스트는 외부 검색을 비활성화하고 서버 초기화·호출·종료를 검사한다.
4. 격리 합성 PostgreSQL 검사는 `TEST_DATABASE_URL`이 명시된 경우에만 실행한다. 기존 DB·볼륨 삭제 명령은 사용하지 않는다.

## AC (Given-When-Then)

### AC-01 · 정상 MCP 검색
- GIVEN: 가짜 MCP가 필수 필드를 갖춘 청크 목록을 반환한다.
- WHEN: MCP retriever를 주입한 그래프가 정격 질문을 처리한다.
- THEN: 정확한 `query`, `k=5`, `parts`로 `search_corpus`를 호출하고 기존 채점·생성 경로로 진행한다.

### AC-02 · 정상 빈 결과
- GIVEN: MCP가 오류 없이 빈 목록을 반환한다.
- WHEN: 검색 노드가 실행된다.
- THEN: `retrieval_error` 없이 기존 문서 없음 응답으로 끝나며 재작성하지 않는다.

### AC-03 · MCP 장애
- GIVEN: MCP 초기화·호출·응답 검증 중 오류가 발생한다.
- WHEN: 검색 노드가 실행된다.
- THEN: 오류 종류만 `retrieval_error`에 기록하고, 문서 없음과 다른 안전한 장애 응답으로 끝나며 같은 요청에서 다시 호출하지 않는다.

### AC-04 · 재작성과 호출 상한
- GIVEN: 첫 MCP 검색 청크는 채점을 통과하지 못하고 두 번째 검색 청크도 통과하지 못한다.
- WHEN: 그래프를 끝까지 실행한다.
- THEN: 원래 질문과 재작성 질문으로 각각 한 번씩만 MCP를 호출하고 세 번째 호출 없이 거절한다.

### AC-05 · 세션 수명
- GIVEN: 하나의 `StdioMcpRetriever` 컨텍스트에서 그래프가 두 번 검색한다.
- WHEN: 재작성 경로를 실행하고 컨텍스트를 종료한다.
- THEN: 서버·세션 초기화는 한 번이며 두 호출이 같은 세션을 쓰고 종료 시 자원이 정리된다.

### AC-06 · 실제 stdio와 격리 DB
- GIVEN: 외부 검색이 비활성화된 실제 MCP 서버와 합성 문서가 있는 격리 `TEST_DATABASE_URL`.
- WHEN: 그래프가 MCP `search_corpus`를 경유한다.
- THEN: 알려진 품번의 청크와 출처 필드를 받고, 없는 품번은 빈 결과이며, 환경·단발 지연·미검증 범위를 작업 기록에 남긴다.

### AC-07 · 기존 그래프 회귀 방지
- GIVEN: MCP retriever를 주입하지 않은 기존 그래프 테스트와 평가 실행.
- WHEN: 전체 테스트를 실행한다.
- THEN: 직접 검색 기본 경로와 기존 라우팅·최대 2회 검색 동작이 유지된다.

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| `StdioMcpRetriever`(`search_corpus`, `check`) | 구현 | `backend/graph/mcp_retriever.py` |
| 검색 장애 분기(`retrieval_error`) | 구현 | `backend/graph/nodes.py`, `tests/graph/test_graph_mcp_retriever.py` |
| AC-01·AC-02·AC-03·AC-04·AC-05 | 시험 있음 | `tests/graph/test_graph_mcp_retriever.py`(`test_stdio_retriever_reuses_one_session_and_sends_contract`, `test_graph_uses_mcp_retriever_for_one_search`, `test_graph_reuses_mcp_session_for_rewritten_search`, `test_stdio_retriever_turns_timeout_into_safe_kind`) |
| AC-06 | 시험 있음 | `tests/graph/test_graph_mcp_stdio.py` |
| AC-07 | 시험 있음 | `tests/graph/test_graph_build.py` |

## 한계

- 변이 확인(검색 상한 2→3 등)을 `docs/GATES.md`에 기록했는지는 대조하지 않았다.
