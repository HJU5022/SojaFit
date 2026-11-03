# MCP 우선순위 1~2: DB 없는 저장소 표본 점검

> 실행일 2026-11-03 · 로컬 표본 기초 검사 · 최종 검색 품질 평가 아님

## 범위와 환경

- 실행 브랜치: STH, 기준 커밋 1cf18a9 및 미커밋 MCP 작업.
- 입력: 저장소의 TSC PDF 3건, data/manifest.jsonl, 공개 회로 연결 정보 및 기존 테스트.
- DB 연결 0회, 외부 웹/API 요청 0회, 지출 $0.
- PDF 열기·문자 추출: pypdf 6.21.4, uv 임시 오프라인 환경. 프로젝트 uv.lock·기존 가상환경 의존성 변경 없음.
- Docling·pdfplumber는 프로젝트 가상환경에서 설치 여부를 확인한 결과 없었다. 이 점검에서 두 도구의 표 파싱·교차 대조는 실행하지 않았다.

## 실행 결과

| 확인 항목 | 결과 | 의미 |
|---|---:|---|
| MCP·회로 읽기·수집·파싱 기초 회귀 테스트 | 31 passed | 테스트 환경의 모의 응답, 저장소 manifest, 공개 회로 데이터를 대상으로 실행했다. 실제 DB 검색·외부 Exa 실호출은 포함되지 않는다. |
| get_corpus_document 실제 manifest 조회 | 3/3 found | 아래 PDF의 doc_id 3개를 조회했다. 도구는 모두 pdf_verified=false를 반환했으며 실제 PDF 검증 여부와 구분했다. |
| PDF 서명·manifest SHA-256 일치 | 3/3 | 저장된 파일이 PDF 서명을 가지고 당시 manifest에 기록한 바이트 해시와 같다. 해시 일치가 문서 내용의 정답성·최신성까지 보장하지는 않는다. |
| 페이지 수 | 3/3 일치 | PDF에서 읽은 페이지 수와 manifest 기록이 같다. |
| 품번 토큰과 개정 코드 문자열 | 각각 3/3 발견 | pypdf가 추출한 텍스트에 manifest 문서명의 첫 토큰과 개정 코드가 있다. 표지 위치·맥락이나 전기적 사양의 정확성까지 검증한 결과는 아니다. |
| manifest 문서명 전체 문자열 | 0/3 발견 | 세 PDF에서 SERIES 단어도 추출되지 않아 manifest의 전체 문서명과 단순 문자열 비교가 일치하지 않았다. 이 결과만으로 잘못된 PDF라고 볼 수 없다. |

### PDF 표본별 결과

| 저장소 PDF | 해시 일치 | 실제 쪽 수 / manifest | 품번 토큰 | 개정 코드 | manifest 전체 문서명 |
|---|---|---:|---|---|---|
| 1N4148-SERIES_K2301.pdf | O | 5 / 5 | O | O | 미발견 |
| 1N5817-SERIES_H2104.pdf | O | 6 / 6 | O | O | 미발견 |
| BZT52C2V4-SERIES_G1804.pdf | O | 7 / 7 | O | O | 미발견 |

전체 문서명은 품번과 SERIES를 붙인 manifest의 값이다. PDF에서 SERIES가 추출되지 않았다는 관찰은 문자열 비교 한계를 보여 주며, 품번 전체·개정판·표 내용의 실제 대조는 별도로 수행해야 한다.

## 재현 방법

프로젝트 루트의 PowerShell에서 실행한다.

    .\.venv\Scripts\uv.exe run --no-sync pytest -q -rs tests/test_mcp_manifest.py tests/test_mcp_search.py tests/test_graph_read_input.py tests/test_rag_collect.py tests/test_rag_parse.py

    .\.venv\Scripts\uv.exe run --no-project --offline --with pypdf==6.21.4 python scripts/check_mcp_offline_pdfs.py

두 번째 명령은 로컬 uv 캐시에 pypdf 6.21.4가 있을 때 네트워크 없이 실행된다. 다른 컴퓨터에서 캐시가 없으면 오프라인 명령이 실패할 수 있다. 별도 설치·다운로드 또는 ingest 환경 사용은 팀의 의존성 정책에 따라 확인한다.

## 다음에 확인할 것

1. PDF 확인: 실제 Docling·pdfplumber로 표와 숫자를 대조하고, 요청 품번·개정판의 위치와 의미를 검증한다. 이번 pypdf 문자열 점검을 프로젝트의 PDF 검증 관문 통과로 쓰지 않는다.
2. 회로 도구: 현재 테스트는 그래프 내부 입력 읽기 기능이다. 별도 MCP 도구, 경로 제한 및 사용자별 권한은 아직 검증하지 않았다.
3. 코퍼스 검색: 저장소 PDF 3건을 파싱·청킹해 격리 DB에 적재한 뒤 MCP 검색 결과를 확인해야 한다. Docker 엔진과 코퍼스 적재 테스트 DB는 이번 점검에 사용하지 않았다.
4. 외부 검색: 모의 응답 기반으로 기본 비활성과 실패 처리를 시험했다. MCP 도구를 통한 실제 Exa API 호출·잔액과 과금 결과는 이 점검에 포함되지 않는다.

## 참고

- [MCP 도구 실행 준비 계획](mcp-tool-implementation-plan.md)
- [MCP 서버](../../backend/mcp_skill/mcp_server/server.py)
- [오프라인 PDF 점검 스크립트](../../scripts/check_mcp_offline_pdfs.py)
- [실험 사전등록](../../evals/preregister.md)
