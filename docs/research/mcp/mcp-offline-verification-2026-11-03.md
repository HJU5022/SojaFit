# DB 없는 저장소 표본 점검

- 상태: 이력 (2026-11-03 측정 기록. 재실행하지 않았다)
- 기준일: 2026-11-03
- 기준 커밋: 1cf18a9 및 당시 미커밋 MCP 작업
- 정본 여부: 정본(저장소 TSC PDF 3건의 서명·해시·쪽 수·문자열 점검). 최종 검색 품질 평가가 아니다
- 관련 문서: [MCP 서버 도구 6종](mcp-tool-implementation-plan.md), [Docling 표본 대조](mcp-docling-verification-2026-11-03.md), [사전 등록](../../../evals/guides/preregister.md)

## 1. 질문과 결론

질문: DB와 외부 API 없이 저장소의 MCP 도구와 TSC 표본 PDF 3건이 manifest와 일치하는가.

| 확인 항목 | 결과 | 의미 | 근거 |
|---|---:|---|---|
| MCP·회로 읽기·수집·파싱 기초 회귀 시험 | 31 passed | 모의 응답, 저장소 manifest, 공개 회로 데이터 대상. 실제 DB 검색·Exa 실호출은 포함하지 않음 | 당시 기록. 시험 파일은 이후 `tests/mcp_skill/` 등으로 옮겨 재현 불가(한계 2) |
| `get_corpus_document` manifest 조회 | 3/3 found | 모두 `pdf_verified=false` 반환. PDF 검증 여부와 구분 | 당시 기록 |
| PDF 서명 + manifest SHA-256 | 3/3 일치 | 해시 일치는 내용의 정답성·최신성을 보장하지 않음 | [실측] 2026-11-12 `hashlib`로 재계산, 3건 모두 일치 |
| 쪽 수 | 3/3 일치 (5·6·7) | | `data/manifest.jsonl`의 `pages` 5·6·7 [실측], PDF 쪽 수는 당시 pypdf 6.21.4 기록 |
| 품번 토큰·개정 코드 문자열 | 각각 3/3 발견 | 표지 위치·맥락, 전기적 사양의 정확성은 아님 | 당시 pypdf 추출 기록 |
| manifest 문서명 전체 문자열 | 0/3 발견 | `SERIES` 단어도 추출되지 않음. 이 결과만으로 잘못된 PDF라고 볼 수 없음 | 당시 pypdf 추출 기록 |

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 입력 | `data/corpus/tsc/`의 PDF 3건, `data/manifest.jsonl`, 공개 회로 연결 정보, 기존 시험 |
| 연결 | DB 0회, 외부 웹/API 0회, 지출 $0 |
| PDF 열기·문자 추출 | pypdf 6.21.4, uv 임시 오프라인 환경(프로젝트 `uv.lock`·가상환경 변경 없음). 현재 `.venv`에는 pypdf가 없다 [실측] |
| Docling·pdfplumber | 이 점검에서 실행하지 않음 → [Docling 표본 대조](mcp-docling-verification-2026-11-03.md) |

### 표본별 결과

| 저장소 PDF | 해시 일치 | 쪽 수 (PDF / manifest) | 품번 토큰 | 개정 코드 | manifest 전체 문서명 |
|---|---|---:|---|---|---|
| 1N4148-SERIES_K2301.pdf | O | 5 / 5 | O | O | 미발견 |
| 1N5817-SERIES_H2104.pdf | O | 6 / 6 | O | O | 미발견 |
| BZT52C2V4-SERIES_G1804.pdf | O | 7 / 7 | O | O | 미발견 |

전체 문서명은 manifest의 품번 + `SERIES` 값이다. 문자열 비교의 한계를 보여 주며, 품번·개정판·표 내용의 실제 대조는 Docling 점검과 별도다.

## 3. 현재 재현 방법

| 대상 | 명령 |
|---|---|
| MCP 서버·클라이언트 시험 | `uv run --no-sync pytest -q tests/mcp_skill tests/graph/test_graph_mcp_retriever.py` (2026-11-12 기준 74 passed, 1 skipped는 이 명령에 `tests/graph/test_graph_mcp_stdio.py`를 더한 값) |
| 해시·바이트·쪽 수 대조 | `data/manifest.jsonl`의 `sha256`·`bytes`·`pages`와 `data/corpus/tsc/*.pdf`를 `hashlib`으로 대조 |
| pypdf 문자열 점검 | 당시 스크립트(check_mcp_offline_pdfs.py)는 저장소에 없다 |

## 4. 결정에 미치는 영향

정해진 것: 저장소 표본 3건은 manifest의 해시·쪽 수와 일치한다(`verify_tsc_pdf` 도구의 검사 범위, [MCP 서버 도구 6종](mcp-tool-implementation-plan.md) 2절). 이 점검은 프로젝트의 PDF 검증 관문 통과가 아니다.

## 5. 한계

1. pypdf 문자열 결과(품번 토큰, 개정 코드, 문서명 전체)와 31 passed는 당시 기록이며 재현하지 않았다.
2. 당시 시험 파일(test_mcp_manifest, test_mcp_search, test_graph_read_input, test_rag_collect, test_rag_parse)과 스크립트 check_mcp_offline_pdfs.py는 당시 경로에 없다. MCP 시험은 `tests/mcp_skill/`, 그래프 입력 시험은 `tests/graph/test_graph_read_input.py`로 옮겨졌다.
3. 회로 도구의 경로 제한·사용자별 권한, 격리 DB 검색, 모의 응답을 넘은 Exa 실호출은 이 점검에 포함되지 않는다.
