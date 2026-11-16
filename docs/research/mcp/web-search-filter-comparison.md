# 웹 검색 TSC 도메인 필터 유무 비교

- 상태: 이력 (2026-11-03 측정. 현재 `search_tsc_web`은 Exa에 `includeDomains`로 `taiwansemi.com`을 지정한다: `backend/mcp_skill/mcp_server/server.py`)
- 기준일: 2026-11-03
- 정본 여부: 정본(도메인 필터 유무 비교 수치). 필터 없는 3공급자 30문항 탐색은 [web-search-results-interpretation.md](web-search-results-interpretation.md)
- 관련 문서: [웹 검색 공급자 3종 30문항 탐색](web-search-results-interpretation.md), [MCP 서버 도구 6종](mcp-tool-implementation-plan.md), [사전 등록](../../../evals/guides/preregister.md)

## 1. 질문과 결론

질문: TSC 도메인 제한이 원하는 데이터시트를 찾는 데 어떤 영향을 주는가.

| 도구 | 조건 | 정상 응답 | TSC 공식 도메인 출현 | 과거 manifest 주소 일치 | 응답 시간 중앙값 |
|---|---|---:|---:|---:|---:|
| Exa | 필터 없음 | 30/30 | 26/30 | 23/30 | 1,328.39ms |
| Exa | TSC 필터 | 30/30 | 30/30 | 24/30 | 1,477.78ms |
| Tavily | 필터 없음 | 30/30 | 26/30 | 5/30 | 1,863.58ms |
| Tavily | TSC 필터 | 30/30 | 30/30 | 5/30 | 1,901.81ms |
| Brave | 필터 없음 | 30/30 | 30/30 | 9/30 | 585.53ms |
| Brave | TSC 필터 | 30/30 | 30/30 | 9/30 | 505.18ms |

근거: 저장소 밖 `web-search-filter-comparison-2026-11-03.json`(질문별 집계). 전체 180회에 실패·미실행은 없다. 저장소에 없어 재계산하지 않았다(한계 1).

| 도구 | 필터 적용 뒤 주소 일치가 새로 생긴 문항 | 기존 일치가 사라진 문항 | 변화 |
|---|---:|---:|---|
| Exa | 1건 (S23) | 0건 | 23건 → 24건 |
| Tavily | 1건 (S13) | 1건 (S29) | 총합 5건으로 같으나 맞은 문항이 달라짐 |
| Brave | 0건 | 0건 | 변화 없음 |

필터 적용 응답의 상위 5개에서 세 도구 모두 TSC 외 도메인 주소가 관찰되지 않았다. 도메인 필터의 동작 확인이며 PDF의 정확성을 보장하지 않는다.

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 질문 | 프로젝트 manifest에서 고정한 30문항(3공급자 30문항 탐색과 같은 질문). 질문에 문서명과 과거 개정판 포함. 앞선 30문항 결과를 이미 본 뒤의 반복이라 독립 평가가 아님 |
| 호출 | 도구마다 무필터 1회, TSC 필터 1회씩. 상위 5개, 최대 15초, 재시도 없음. 홀수 문항은 무필터 먼저, 짝수 문항은 필터 먼저 |
| Exa | 인증 Search API, type auto, 필터는 `includeDomains` |
| Tavily | 인증 Search API, Basic, 필터는 `include_domains`와 `restrict` |
| Brave | 인증 Search API, 필터는 질문 뒤 `site:taiwansemi.com` 연산자(질문 자체를 바꾸는 실험 기능이라 세 도구의 필터가 같은 구현이 아님) |
| 지표 | 공식 도메인 출현 = 상위 5개에 `taiwansemi.com`·하위 도메인 포함 문항 수(필터 조건에서는 높게 나오는 것이 예상됨). 과거 주소 일치 = 상위 5개에 manifest URL과 호스트·디코딩 경로가 일치한 문항 수(대소문자 무시, 스킴·쿼리 비교 안 함, 같은 PDF의 다른 주소는 놓침) |
| 비용 | 계획상 최대: Exa Auto 60회 무료분 전 $0.42, Tavily Basic 60크레딧, Brave 60회 무료분 전 $0.30. 세 계정 모두 무료 크레딧 잔여와 자동 과금·충전 꺼짐 확인 |
| 저장 | API 키, 응답 원문, 결과 URL은 저장하지 않음 |

## 3. 바뀐 3문항의 공개 PDF 확인

검색 API 재호출 없이 manifest의 공개 TSC 원본 URL을 문항마다 1회 조회했다. PDF 원문은 메모리에서만 처리했고, 서명·파싱과 manifest SHA-256을 확인했다. 이 확인은 검색 비교의 180회에 포함하지 않는다.

| 문항 | 선택한 이유 | PDF 응답·파싱 | manifest 해시 일치 | 문서명 문자열 | 개정판 문자열 |
|---|---|---|---|---|---|
| S23 | Exa 필터 뒤 주소 일치 증가 | 성공 | O | O | O |
| S13 | Tavily 필터 뒤 주소 일치 증가 | 성공 | O | O | O |
| S29 | Tavily 필터 뒤 기존 일치 사라짐 | 성공 | O | 확인되지 않음 | O |

S29는 원본 해시가 manifest와 일치하지만 단순 문자열 방식으로는 manifest 문서명 전체가 추출 텍스트에서 확인되지 않았다. 문서가 틀렸다는 뜻이 아니며 표지·품번 범위를 수동으로 대조해야 한다. 개정판 문자 발견은 위치·맥락이나 전기적 조건의 검증이 아니다. 근거: 저장소 밖 `web-search-pdf-smoke-2026-11-03.json`.

## 4. 결정에 미치는 영향

- 이번 표본에서 Exa의 TSC 필터는 과거 주소 일치를 1건 늘렸고 줄인 건은 없었다. 필터를 제거할 근거는 관찰되지 않았다.
- 현재 MCP 서버는 Exa 결과 중 HTTPS TSC 공식 도메인 URL만 미검증 후보로 반환한다([MCP 서버 도구 6종](mcp-tool-implementation-plan.md) 2절).
- 모든 실제 사용자 질문에서 필터가 낫다는 결론은 내리지 않는다.

## 5. 한계

1. 질문 30개, 질문별 집계, 실행기 5개(`benchmark_tavily_keyless.py`, `benchmark_web_search_30.py`, `benchmark_tavily_authenticated_30.py`, `benchmark_web_search_filter.py`, `benchmark_web_search_pdf_smoke.py`), 결과 파일(`web-search-exploration-2026-11-03.json`, `web-search-30-2026-11-03.json`, `tavily-authenticated-30-2026-11-03.json`, `web-search-filter-comparison-2026-11-03.json`, `web-search-pdf-smoke-2026-11-03.json`, `mcp-docling-pdf-2026-11-03.json`)은 저장소 밖에 있다. 수치를 재계산하지 않았다. 다시 돌리기 전 사전 등록과 무료 한도 확인이 필요하다.
2. 30건 단일 반복이고 과거 주소와 문서명을 알고 만든 질문이다.
3. 응답 시간 중앙값은 공급자별 통신 방식·캐시·처리 시간이 달라 엔진 성능 차이로 볼 수 없다.
4. 계정별 실제 차감·청구 내역은 확인하지 않았다.
5. Brave API 결과의 파생 통계 보관·공유 가능 범위는 공급자 확인이 필요하다.
