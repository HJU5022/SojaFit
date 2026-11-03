# MCP 도구별 계약 및 사용처 1차 점검


> 기준: STH의 MCP 도구 구현 `f54c4fc` 및 2026-11-03 점검. 호출 조건은 해당 시점의 코드 사실, 사용처·노출 구분은 팀 제안이다. 최신 main 통합 후 실제 앱·그래프의 MCP 클라이언트 연결은 여전히 미구현이다.

| 도구 | 현재 입력 | 현재 출력 및 실패 | 호출 조건·데이터 경계 | 노출 제안 |
|---|---|---|---|---|
| `search_corpus` | `query` 1~500자, `k` 1~10(기본 5), `parts` 문자열 목록 또는 null | 기존 `retrieve`의 카드 목록을 그대로 반환. 결과가 없으면 `[]`; 검색기 예외는 도구로 전파 | 기존 DB 검색. `method=hybrid`, 데모에서는 기존 검색기의 BM25 동작을 따른다 | **우선 연결 후보:** 그래프 검색 단계. DB 장애와 빈 결과 구분 필요 |
| `get_corpus_document` | `doc_id` 1~200자 | `found`·`not_found`·`unavailable`, 문서 메타데이터, `pdf_verified=false` | 로컬 manifest 읽기. `verify_tsc_pdf`, `search_tsc_web`에서도 내부 사용 | **협의:** 검색 카드 출처로 충분하면 내부 기능으로 둘 수 있다 |
| `search_tsc_web` | `doc_id` 1~200자 | `disabled`, `missing_key`, `unavailable`, `unverified` 또는 `ok`와 미검증 후보 목록 | 데모 비활성, 명시적 활성화·키 필요. manifest 출처·문서명·개정 확인 후 최대 1회 요청, TSC HTTPS URL만 후보 반환 | **조건부 후보:** 공개 품번 목록·코퍼스 밖 처리와 PDF 검증 계약 확정 후 사용 |
| `verify_tsc_pdf` | `doc_id` 1~200자 | `integrity_verified`·`integrity_mismatch`·`not_found`·`unavailable`·`not_available_locally`; `content_verified=false` | 고정된 로컬 TSC PDF 세 표본의 서명·크기·해시만 확인 | **우선 점검용 제안:** 실제 서비스 근거 검증과 분리 |
| `get_circuit_info` | `circuit_id` 소문자·숫자·밑줄 1~50자, `target` 허용 문자 1~100자 | `found`·`not_found`·`unavailable` 및 회로 정보 | 고정 공개 예제 회로만 허용. 임의 경로·사용자 업로드 회로 미지원 | **협의:** 그래프의 기존 `read_input`·`circuit_around`와 역할 중복 확인 |

### 검색기 연결 계약 초안 — 팀 합의 전

- 입력 예: `search_corpus(query="1N4148 reverse voltage", k=5, parts=["1N4148"])`. 그래프는 `retriever(query, parts=...)`를 동기 호출하며 `docs`에 카드 목록을 저장한다. MCP `search_corpus`는 같은 검색 함수에 위 인자를 전달한다.
- 반환 예(형태 설명용): `[{"chunk_id": 7, "document_key": "문서 ID", "page": 1, "table": "표 이름", "content": "근거 내용", "doc_parts": ["1N4148"]}]`. 실제 응답에는 파일명·점수·순위 등 기존 검색기 필드도 있다. 예시는 실측값이나 정답이 아니다.
- 현재 `parts=None`은 품번 필터 없음, `parts=[]`는 검색기에서 빈 허용 집합으로 처리된다. `parts`의 개수·항목 길이 상한은 명시되지 않았고 도구 함수는 별도로 검증하지 않는다. 구체적인 상한과 빈 목록 처리 방식은 그래프·검색 담당자와 합의 후 작업서·테스트에 반영한다.
- **제안:** `[]`는 정상 검색의 결과 없음으로 유지하고 MCP 프로토콜 오류·DB 연결 오류·시간 초과는 별도 실패로 전달한다. 현재 `search_corpus`에는 이를 상태 객체로 분류하는 코드가 없으므로, 오류 형태와 민감정보 비노출은 연결 계약과 함께 결정한다. 실패를 `[]`로 바꾸면 없는 품번으로 오인할 수 있다.
- 도구별 MCP 호출 결과의 직렬화, 동기 그래프와 비동기 클라이언트의 세션 수명, 취소·종료, 장애 처리 위치는 통합 담당과 확인한다. 외부 검색은 공개 확인 정책과 $0 예산 확인 전 실호출하지 않는다.

### 나머지 네 도구의 연결 계약 점검 (2026-11-03)

현재 앱·그래프 호출이 아니라, 검색 흐름에서 가능한 사용 위치와 기존 함수 중복 여부를 확인했다.

| 도구 | 현재 코드에서의 호출 | 프로젝트 상황에 맞춘 호출 후보 | 연결 판단 |
|---|---|---|---|
| `get_corpus_document` | `verify_tsc_pdf`와 `search_tsc_web`가 내부에서 호출. 테스트에서 직접 호출 | 검색 카드의 `document_key`에 해당하는 출처·개정 확인 | 검색 카드에 출처가 이미 있으므로 기본 검색 경로의 필수 후속 호출로 보이지 않는다. 카드에 없는 manifest 정보가 필요할 때만 선택 호출을 검토한다. ID의 `document_key` ↔ manifest `doc_id` 정합을 먼저 확인한다. |
| `search_tsc_web` | 테스트에서 직접 호출. 다른 앱·그래프 호출은 없음 | 허용된 공개 TSC 문서의 보완 후보 검색 | 현재 입력은 정확한 manifest `doc_id`이며 목록 밖 부품은 `unverified`로 막힌다. 코퍼스 검색 실패만으로 이 도구를 자동 호출하면 SPEC의 코퍼스 밖 조회를 충족하지 못할 수 있다. 공개 품번 승인 절차, 비용 상한, 후보를 검증하는 후속 절차를 먼저 합의해야 한다. |
| `verify_tsc_pdf` | `get_corpus_document` 내부 호출 후 로컬 파일 3건 검증. 독립 호출은 테스트 | 저장소에 고정된 PDF 표본의 개발·릴리스 무결성 점검 | 사용자 질문을 처리하는 그래프 노드의 근거 검색에는 연결하지 않는 안을 제안한다. 반환도 `content_verified=false`이므로 실제 증거의 내용 판정으로 쓰면 안 된다. 점검용 CLI·테스트 중 어느 위치가 맞는지는 팀 결정 대상이다. |
| `get_circuit_info` | 도구 자체가 `circuit_around`를 호출. 현재 그래프 입력 노드도 로컬 넷리스트에서 같은 함수를 직접 호출 | 공개 예제 회로를 별도 ID로 조회할 때 | 현재 서비스 입력과 직접 이어지는 보편 도구로 보이지 않으며, `read_input`과 기능이 겹친다. 사용자 회로 접근·인증 범위가 정해지기 전에는 그래프에 연결하지 않고 공개 예제 전용 확인 기능으로 남기는 안을 제안한다. |

#### 단계 권고

1. 사용자 질문 응답의 1차 연결 범위는 `search_corpus`로 한정한다.
2. 그래프 노드가 출처 확인을 실제로 요구하는 근거를 찾으면 `get_corpus_document`를 별도 단계로 검토한다. 그 전에는 내부 보조 기능으로 둔다.
3. `search_tsc_web`은 공개 품번 조회·후보 검증 정책이 결정된 뒤 별도 흐름으로 다룬다. 검색 0건의 자동 fallback으로 두지 않는다.
4. `verify_tsc_pdf`는 우선 저장소 표본 점검에 한정한다.
5. `get_circuit_info`는 `read_input`과 중복 여부 및 사용자 회로 계약을 정한 다음 노출 필요를 결정한다.

이 분류는 코드 호출과 SPEC을 바탕으로 한 제안이다. `search_tsc_web`의 코퍼스 밖 허용 범위, 회로 도구 노출, PDF 검증 도구를 MCP에 둘지 여부는 팀에서 결정하지 않았다.

### MCP stdio 응답 확인 (2026-11-03)

조건: STH 작업 트리의 MCP 서버에 가짜 `retrieve`를 주입한 별도 stdio 프로세스, `DEMO_MODE=1`. 합성 질문·카드·오류를 사용했으며 DB, 외부 API, 실제 키는 사용하지 않았다. 각 상황을 한 번씩 호출한 관찰이며 실제 DB 또는 그래프 통합 성능 검증이 아니다.

| 사례 | 가짜 검색기 결과 | 실제 MCP `CallToolResult` 관찰 | 연결 시 의미 |
|---|---|---|---|
| 정상·카드 1개 | 합성 카드 목록 | `isError=false`, `structuredContent={"result": [카드]}`, `content`에 카드 텍스트 블록 1개 | 구조화된 `result`를 기존 카드 목록으로 전달하는 방안 검토 |
| 정상·결과 없음 | `[]` | `isError=false`, `structuredContent={"result": []}`, `content=[]` | 텍스트 블록 첫 항목만 읽으면 빈 결과를 처리할 수 없음 |
| 검색기 예외 | `RuntimeError`에 합성 오류 문구 | `isError=true`, `structuredContent=null`; `content` 텍스트에 예외 문구가 포함됨 | 예외 메시지에 접속 정보 등이 있으면 노출될 수 있으므로 오류 원문을 그대로 사용자에게 전달하지 않도록 계약·처리 필요 |

- 위 포장 형식은 현재 설치된 MCP SDK에서 확인한 결과다. 여러 카드의 `content` 표현, 다른 SDK 버전 및 실제 DB 오류는 이번에 확인하지 않았다.
- 그래프 입력은 `retriever(query, *, parts=...) -> list[dict]`이며 `search_corpus(query, k=5, parts=None)`는 기존 검색기에 `method=hybrid`로 위임한다. 따라서 연결부가 `isError`를 먼저 확인한 다음 성공 시 구조화된 `result`가 카드 목록인지 검증해 반환하는 방안을 제안한다. 이는 구현이나 팀 합의가 아니다.
- 실제 검색 카드 계약 필드: `chunk_id`, `document_key`, `file`, `page`, `table`, `content`, `score`, `dense_rank`, `bm25_rank`, `doc_parts`. 그래프의 채점·생성은 특히 `chunk_id`, `file`, `page`, `content` 등을 사용한다. 상세 계약은 [RAG 작업서](../specs/rag-pipeline.md)를 따른다.
- 정상 빈 결과는 기존 그래프에서 재작성 없이 거절 분기로 이어진다. 도구 오류를 `[]`로 바꾸면 장애를 문서 부재로 오인하므로 구분해야 한다. 오류 응답 형식·로그 비노출·재시도 여부와 상한, 세션 수명은 그래프 담당자와 확정한다.

### 점검 결과와 남은 작업

- `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py -p no:cacheprovider` — **36 passed**. 이 검사는 모의 응답·로컬 표본·stdio 호출을 포함하며 실제 DB 검색이나 Exa 실호출을 증명하지 않는다.
- 현재 구현의 검색기 예외 처리, 빈 `parts` 의미, 목록 길이 제한과 사용자별 호출 권한은 별도 경계 검토가 필요하다. 사용자 입력·공개 품번 정책에 대한 임의의 새 제한을 아직 적용하지 않았다.
- 팀의 디렉터리 정리 PR이 main에 반영되면 새 경로와 그래프 계약을 재확인한다. 도구 노출 여부는 팀 결정 전 확정하지 않는다.

관련 자료: [MCP 구현 계획](mcp-tool-implementation-plan.md) · [두 사람 작업 분담안](mcp-two-person-work-plan.md) · [공동작업 인수인계](mcp-collaboration-handoff.md).
