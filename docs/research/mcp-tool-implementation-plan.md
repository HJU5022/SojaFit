# MCP 서버 도구 6종: 계약, 사용처, 구현 상태

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 67e08b1 (코드는 `backend/mcp_skill/mcp_server/server.py`, `backend/graph/mcp_retriever.py` 기준)
- 정본 여부: 정본(MCP 도구 표). 도구 계약의 시험 정본은 [SPEC 8.7](../../SPEC.md)과 [mcp-search-tools.md](../specs/mcp-search-tools.md)
- 관련 문서: [MCP 서버 안내](../../backend/mcp_skill/MCP_SKILL.md), [검색기 연결 계약](mcp-tool-contract-review.md), [오프라인 점검](mcp-offline-verification-2026-11-03.md), [Docling 표본 대조](mcp-docling-verification-2026-11-03.md), [공개 품번 확인 방안](tsc-public-part-verification-options.md), [웹 검색 공급자 비교](mcp-tool-candidates-draft.md)

이 문서의 도구 표가 MCP 도구 목록의 유일한 표다. 다른 문서는 이 표를 링크한다.

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 서버 | FastMCP stdio 서버 `sojafit-search`, 도구 6종 | `backend/mcp_skill/mcp_server/server.py:16-150`의 `@mcp.tool()` 6개 |
| 서비스가 부르는 도구 | `check_corpus`만(사실 확인). 서비스·평가 실행기·데모 녹화가 `StdioMcpRetriever`로 호출 | `backend/conversations/memory_service.py:286-297`, `evals/runners/run_graph.py:156-160`, `scripts/demo/record_demo.py:105-112`, `backend/multi_agent/facts.py:72` |
| MCP 클라이언트 | `StdioMcpRetriever`(동기 그래프용 stdio 클라이언트, 기본 시간 제한 30초) | `backend/graph/mcp_retriever.py:91-97` |
| `search_corpus`를 MCP로 부르는 경로 | 시험에서만. 서비스 검색은 `retrieve()`를 직접 호출 | `backend/mcp_skill/MCP_SKILL.md` 안내 1항 |
| 시험 | `tests/mcp_skill/test_mcp_server.py` 56 passed, `tests/graph/test_graph_mcp_retriever.py` 18 passed, `tests/graph/test_graph_mcp_stdio.py` 1 skipped (합계 74 passed, 1 skipped) | [실측] 2026-11-12 `pytest` 실행 |
| 지운 도구 | 사양 도구 2종 `get_part_specs`·`find_parts_by_specs`(ADR 0016, 11-10) | `backend/mcp_skill/MCP_SKILL.md`, `SPEC.md` 8.7 |

## 2. 도구 표

입력 검증과 출력은 `server.py`의 코드 값이다. "현재 호출처"는 저장소에서 찾은 호출 위치이고 "제안 사용처"는 호출처가 아직 없는 도구의 후보다.

| 도구 | 입력 | 출력·실패 | 호출 조건·데이터 경계 | 현재 호출처 | 제안 사용처 |
|---|---|---|---|---|---|
| `search_corpus` | `query` 1~500자, `k` 1~10(기본 5), `parts` 문자열 목록 또는 null. `parts` 길이·항목은 검증하지 않음 | `retrieve(method='hybrid')`의 카드 목록. 결과 없음은 `[]`, 검색기 예외는 MCP `isError`로 전파 | 적재된 DB 필요 | `StdioMcpRetriever.__call__`(시험 `tests/graph/test_graph_mcp_retriever.py`) | 그래프의 근거 검색 단계 |
| `check_corpus` | `parts`·`revisions` 각각 문자열 20개 이하, 항목 1~100자 | `{"parts": {이름: bool}, "revisions": {이름: bool}}`. 있음/없음만 반환하고 판단하지 않음. 품번은 대소문자 무시, 개정 코드는 대문자로 비교 | `corpus_known()`이 읽는 코퍼스 목록 | 사실 확인 노드(`StdioMcpRetriever.check`, `backend/multi_agent/facts.py`), 서비스·평가·데모 녹화 | - |
| `get_corpus_document` | `doc_id` 1~200자 | `found`·`not_found`·`unavailable`. `found`면 `doc_id`·`title`·`revision`·`source_url`·`sha256`·`bytes`·`pages`와 `pdf_verified=false` | `data/manifest.jsonl`(1,360행)을 읽기만 함. 반환 해시·출처는 기록값이며 PDF를 다시 검증하지 않음 | `verify_tsc_pdf`·`search_tsc_web` 내부 호출, 시험 | 검색 청크에 없는 출처 정보가 필요할 때 |
| `search_tsc_web` | `doc_id` 1~200자 | `disabled`·`missing_key`·`unavailable`·`unverified`, 또는 `ok`와 후보 `[{url, verified:false}]`(HTTPS `taiwansemi.com` 계열 URL만, 최대 5개) | `DEMO_MODE=0`, `EXA_WEB_SEARCH_ENABLED=1`, `EXA_API_KEY`가 모두 있어야 호출. manifest의 출처·문서명·개정이 `services.taiwansemi.com` 형식과 일치할 때만 검색어를 만들고 사용자 문장은 보내지 않음. 호출당 HTTP 1회, timeout 15초, 리디렉션 따라가지 않음 | 시험 | 공개 확인된 TSC 문서의 미검증 후보 조회 |
| `verify_tsc_pdf` | `doc_id` 1~200자 | `integrity_verified`·`integrity_mismatch`·`not_found`·`unavailable`·`not_available_locally`, `content_verified=false` | `data/corpus/tsc/`의 PDF 3건(`1N4148-SERIES_K2301`, `1N5817-SERIES_H2104`, `BZT52C2V4-SERIES_G1804`)의 서명·바이트 크기·SHA-256만 manifest와 대조 | 시험 | 저장소 표본 무결성 점검(서비스 근거 검증과 분리) |
| `get_circuit_info` | `circuit_id` 소문자·숫자·밑줄 1~50자, `target` 1~100자 | `found`·`not_found`·`unavailable`과 `circuit_around` 결과 | 고정 공개 회로 5개 ID(`CIRCUITS`)만. 임의 경로·사용자 업로드 회로는 받지 않음 | 시험. 그래프 `read_input`은 같은 `circuit_around`를 직접 호출 | 공개 예제 회로 조회 전용 |

## 3. 구현 범위 밖

| 기능 | 상태 | 근거 |
|---|---|---|
| 수치·요구 조건 비교 | MCP 도구 없음. 판정은 `backend/judge/` | `SPEC.md` 8.7 |
| 견적 생성·승인·저장 | MCP 도구 없음 | 도구 표에 없음 |
| 가격·재고(Mouser) | MCP 도구 없음. Mouser는 그래프·MCP 밖 `/api/prices`만 호출한다. 응답 저장 금지 정책 | `backend/multi_agent/build.py:94`, [ADR 0009](../adr/0009-mouser-응답은-저장하지-않는다.md) |
| 공식 PDF 다운로드·파싱·적재 | MCP 도구에 없음. Exa 검색과 공식 PDF 행 읽기는 `backend/services/exa.py`·`backend/services/datasheet_rows.py`가 맡음 | `backend/services/exa.py:1-25` |
| 코퍼스 밖 신규 TSC 품번 조회 | 지원하지 않음. 목록 밖 문서는 `unverified`로 차단 | `server.py`의 `search_tsc_web`, [공개 품번 확인 방안](tsc-public-part-verification-options.md) |

## 4. 측정 기록

| 측정 | 결과 | 환경 | 원시 |
|---|---|---|---|
| 격리 PostgreSQL 합성 문서 검색(2026-11-03): 알려진 1N4148 질의 | 2건, 120.68ms, `document_key`와 manifest 일치, 문서 조회 found·`pdf_verified=false` 1.86ms | 임시 PostgreSQL 16.15, 합성 문서 4건·청크 8건, 데모 BM25 | 저장소에 없음 |
| 같은 환경: 없는 품번 `NOPE123` | 0건, 3.13ms | 위와 같음 | 저장소에 없음 |
| 같은 환경: `SS34` 필터 + 1N4148 질의 | 0건, 15.47ms (다른 부품 결과가 섞이지 않음. SS34 정상 검색 성공은 확인하지 않음) | 위와 같음 | 저장소에 없음 |
| 같은 환경: 데모 웹 검색 | `disabled` 1.38ms | 위와 같음 | 저장소에 없음 |

각 1회 관찰이며 성능 벤치마크가 아니다. 합성 데이터는 정격 근거가 아니다. 이 측정에서 일반 서버 진입점은 첫 검색 응답이 지연됐고, NumPy를 서버 시작 전에 import한 진단 조건에서만 완료됐다(원인 미확정).

DB 없는 저장소 표본 점검은 [오프라인 점검](mcp-offline-verification-2026-11-03.md), 표 숫자 대조는 [Docling 표본 대조](mcp-docling-verification-2026-11-03.md)에 있다.

## 5. 외부 검색 데이터 경계

- 사용자 자유 문장을 Exa에 보내지 않는다. 공개 TSC manifest의 문서 ID로 조회하고, 출처·문서명·개정 형식이 일치할 때만 검색어를 만든다(`server.py`의 `search_tsc_web`).
- 목록 밖 또는 확인되지 않은 항목은 `unverified`다. manifest는 과거 수집 기록이라 현재 공개 상태를 보장하지 않는다. 검색한 공개 품번과 호출 사실은 검색 공급자에 노출된다.
- 반환된 URL은 후보다. PDF 본문·품번·개정을 검증하기 전에는 판정 근거로 쓰지 않는다.
- 실제 외부 호출은 사전 등록, 무료 한도·자동 과금 차단 확인, 실제 지출 $0 조건 확인 뒤에만 한다(`evals/guides/preregister.md`).

## 6. 남은 일

| 항목 | 내용 |
|---|---|
| 실제 코퍼스 DB 검색 | MCP `search_corpus`로 실제 코퍼스의 관련·무관 품번 결과와 문서 연결을 확인하지 않았다 |
| MCP를 통한 Exa 실호출 | 서버 도구 경유 실호출을 확인하지 않았다(모의 응답 시험만) |
| 서버 첫 검색 지연 | 일반 진입점의 NumPy 로딩 지연을 독립 재현·진단하지 않았다 |
| 공개 품번 정책 | 공개 확인 목록의 출처·갱신 책임·목록 밖 처리 방식 미결([선택지](tsc-public-part-verification-options.md)) |
| 외부 검색 상한 | 도구 호출당 HTTP 1회, timeout 15초만 있고 반복 호출·전체 시간 상한은 도구에 없다 |
| 사용자별 회로 접근 | 인증된 사용자 회로 카탈로그·업로드 제한은 없다. `get_circuit_info`는 고정 공개 회로만 읽는다 |
| 도구 노출 범위 | `get_corpus_document`·`verify_tsc_pdf`·`get_circuit_info`를 에이전트에 노출할지, 서버 내부·점검용으로 둘지 미결 |

## 7. 한계

- 4절의 측정은 원시 파일이 저장소에 없다. 값은 기록 당시 문서의 것이다.
- 도구 표의 "현재 호출처"는 `backend/`·`evals/`·`scripts/`·`tests/` 전체 검색(`grep`) 결과이며, 외부 클라이언트의 호출은 알 수 없다.
- `tests/graph/test_graph_mcp_stdio.py`는 이 실행에서 skipped였다(실제 검색 환경 필요). 실제 stdio 경유 검색 경로는 이 실행에서 확인하지 않았다(`TEST_DATABASE_URL`에 격리 코퍼스가 없어 건너뜀).
