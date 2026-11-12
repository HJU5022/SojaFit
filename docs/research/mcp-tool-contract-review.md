# MCP 검색 도구와 LangGraph 검색기의 연결 계약

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002 (코드: `backend/graph/mcp_retriever.py`, `backend/mcp_skill/mcp_server/server.py`)
- 정본 여부: 정본(검색기 연결 계약과 stdio 응답 형식). 도구 표의 정본은 [mcp-tool-implementation-plan.md](mcp-tool-implementation-plan.md)
- 관련 문서: [MCP 서버 안내](../../backend/mcp_skill/MCP_SKILL.md), [RAG 작업서](../specs/rag-pipeline.md), [MCP 검색 도구 작업서](../specs/mcp-search-tools.md)

## 1. 질문과 결론

질문: `search_corpus` 결과를 LangGraph 검색기 계약으로 옮길 때 성공, 빈 결과, 장애를 어떻게 구분하는가.

| 항목 | 값 | 근거 |
|---|---|---|
| 그래프 검색기 시그니처 | `retriever(query, *, parts=...) -> list[dict]`. `StdioMcpRetriever.__call__`이 같은 시그니처 | `backend/graph/mcp_retriever.py:__call__` |
| MCP 호출 인자 | `search_corpus(query, k=5, parts)`. 서버는 `retrieve(method='hybrid')`에 위임 | `backend/graph/mcp_retriever.py:_call`, `server.py:search_corpus` |
| 성공·빈 결과·장애 구분 | 정상 빈 결과는 `[]`. `isError=true`는 `tool_error`, 응답 형식 오류는 `invalid_response`, 서버 미기동은 `mcp_unavailable`, 시간 초과는 `timeout`으로 `RetrievalUnavailableError(kind)`를 던진다. 장애를 `[]`로 바꾸지 않는다 | `mcp_retriever.py:decode_search_result`, `RetrievalUnavailableError` |
| 응답 검증 | 목록의 모든 카드가 필수 필드 `chunk_id`(정수)·`file`·`page`(정수)·`content`·`table`(문자열 또는 null)·`doc_parts`(문자열 목록)를 가져야 한다. 아니면 `invalid_response` | `mcp_retriever.py:_valid_card` |
| 세션 | 동기 그래프용으로 별도 스레드의 이벤트 루프에 stdio 세션 1개를 열어 재사용. 기본 시간 제한 30초. 평가 예산이 있으면 남은 예산으로 줄인다 | `mcp_retriever.py:StdioMcpRetriever` |
| 그래프의 장애 처리 | 검색·MCP 도구 장애는 거절 `search_error`로 간다 | `SPEC.md` "그래프" 절(거절 `search_error`), `backend/graph/nodes.py:235` |
| 검색 카드 필드(서버 반환) | `chunk_id`, `document_key`, `file`, `page`, `table`, `content`, `score`, `doc_parts`, `dense_rank`, `bm25_rank`. `score`는 RRF 점수 | `backend/rag/retrieve.py:167` |
| 시험 | 디코더·stdio 세션 재사용·시간 초과·그래프 연결·`check_corpus` 계약을 다루는 시험 함수 10개, 18 passed | [실측] 2026-11-12 `tests/graph/test_graph_mcp_retriever.py` |

## 2. stdio 응답 형식

가짜 `retrieve`를 주입한 별도 stdio 서버 프로세스(`DEMO_MODE=1`, 합성 질문·청크·오류, DB·외부 API 없음)를 2026-11-03에 각 상황 1회 호출한 관찰이다. 원시 기록은 저장소에 없다.

| 사례 | 가짜 검색기 결과 | MCP `CallToolResult` | 연결부 처리 |
|---|---|---|---|
| 정상, 청크 1개 | 합성 청크 목록 | `isError=false`, `structuredContent={"result": [청크]}`, `content`에 청크 텍스트 블록 1개 | `structuredContent["result"]`를 검증해 반환 |
| 정상, 결과 없음 | `[]` | `isError=false`, `structuredContent={"result": []}`, `content=[]` | 빈 목록 반환(`content`의 첫 항목만 읽으면 빈 결과를 처리할 수 없음) |
| 검색기 예외 | `RuntimeError` | `isError=true`, `structuredContent=null`, `content` 텍스트에 예외 문구 | `tool_error`로 변환. 예외 원문은 사용자에게 전달하지 않는다 |

`decode_search_result`는 `structuredContent["result"]`가 없으면 `content`가 텍스트 블록 1개인 경우 JSON으로 읽는다.

## 3. 한계

- 2절 관찰은 당시 설치된 MCP SDK 기준이다. 여러 청크의 `content` 표현, 다른 SDK 버전, 실제 DB 오류는 확인하지 않았다. 현재 의존성은 `mcp>=1.28,<2`(`pyproject.toml`).
- `parts`의 개수·항목 길이 상한과 빈 목록 `[]`의 의미는 서버에 검증이 없다. `parts=[]`는 검색기에서 빈 허용 집합으로 처리된다는 서술은 코드로 다시 확인하지 않았다.
- 연결부(`StdioMcpRetriever`)에 재시도는 없다. 오류 원문의 로그 비노출은 확인하지 않았다.
- 실제 DB를 거친 stdio 경유 검색(`tests/graph/test_graph_mcp_stdio.py`)은 `TEST_DATABASE_URL`에 격리 코퍼스가 없어 이 실행에서 건너뛰었다.
