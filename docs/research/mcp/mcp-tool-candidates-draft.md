# MCP 도구 후보와 웹 검색 공급자 후보 조사

- 상태: 이력 (2026-11-03 후보 조사와 7질의 탐색. 공급자 선정 결정은 ADR에 없다. 현재 코드는 Exa를 쓴다: `backend/services/exa.py`, `backend/mcp_skill/mcp_server/server.py`의 `search_tsc_web`)
- 기준일: 2026-11-03 (후보·가격 조사, 7질의 탐색). 현재 코드 확인 2026-11-12
- 정본 여부: 정본(후보 목록, 가격 비교, 7질의 탐색 수치). 30문항 탐색은 [web-search-results-interpretation.md](web-search-results-interpretation.md), 필터 유무는 [web-search-filter-comparison.md](web-search-filter-comparison.md), MCP 도구 표는 [mcp-tool-implementation-plan.md](mcp-tool-implementation-plan.md)
- 관련 문서: [MCP 서버 안내](../../../backend/mcp_skill/MCP_SKILL.md), [RAG 안내](../../../backend/rag/RAG.md), [SPEC](../../../SPEC.md), [사전 등록](../../../evals/guides/preregister.md)

## 1. 미결 항목

| 항목 | 내용 |
|---|---|
| 웹 검색 요건 | "필수 웹 검색"이 실시간 외부 검색 실행을 뜻하는지, 키 없는 데모에서 어떤 실행이 허용되는지. 평가 가이드 원문에서 웹 검색 필수 조항을 찾지 못했다(조사 당시 `docs/`) |
| 웹 검색 공급자 | Tavily·Exa·Brave 중 선택. 코드는 Exa를 쓰지만 선정 ADR은 없다 |
| 도구 경계 | 자체 RAG MCP, 외부 웹 검색, PDF 검증, 결정적 판정의 책임과 입출력 |
| 외부 조회 | 공식 도메인, PDF 검증 절차, 실패와 데모 모드 동작([공개 품번 확인 방안](tsc-public-part-verification-options.md)) |

## 2. 프로젝트 제약

| 제약 | 근거 |
|---|---|
| 검색 `retrieve(question, k, parts)`는 기존 코퍼스의 BM25·벡터 검색과 품번 필터를 쓴다. 데모 모드는 임베딩 API 없이 BM25 | [RAG 안내](../../../backend/rag/RAG.md) |
| 공식 자료 출처·페이지·표·행을 보존한다. 수치·단위 비교와 판정은 `backend/judge/` | [SPEC](../../../SPEC.md) |
| 평가자는 키 없이 Compose를 시작한다. 키 없는 데모의 대체 응답이 웹 검색 필수 조건을 충족하는지는 미확인 | 조사 당시 확인 |
| Mouser는 확장 단계. 응답을 DB·데모 응답·대화·체크포인트·트레이스에 저장하지 않는다 | [ADR 0009](../../adr/0009-mouser-응답은-저장하지-않는다.md) |
| 웹 검색 도구 호출에 기존 그래프 검색 2회 제한을 어떻게 적용할지 | 미결 |

## 3. 외부 MCP 후보 (2026-11-03 조사)

순위는 기능 설명에 따른 예비 순서다. 운영 안전성·프로젝트 호환성은 검증하지 않았다. 외부 MCP 사용 여부와 관계없이 프로젝트의 공식 출처 검증, PDF 확인, 해시, 파싱, 교차 대조는 유지한다.

### 3.1 기존 코퍼스 검색 `search_corpus`

외부 범용 서버보다 자체 `retrieve()`를 FastMCP로 노출하는 쪽을 택했다(현재 `search_corpus`). 외부 후보는 개발 점검·대체안이었다.

| 순위 | 후보 | 장점 | 제한 |
|---:|---|---|---|
| 1 | [Microsoft PostgreSQL MCP](https://github.com/microsoft/postgres-mcp/blob/main/USAGE.md) | PostgreSQL 조회·운영 점검, 읽기 전용 질의 | 범용 SQL. RRF·품번 필터·출처 반환을 재현하지 않음. DB 권한 제한 필요 |
| 2 | [Supabase MCP](https://supabase.com/features/mcp-server) | Supabase 관리·조회, 읽기 전용 옵션 | 로컬 Compose 검색을 대체하기 어려움 |
| 3 | [mcp-server-pgvector](https://github.com/mittalpk/mcp-server-pgvector) | pgvector 유사도·하이브리드 검색 | 커뮤니티 구현. 스키마·RRF·인용 필드 호환성 미확인 |

### 3.2 웹 검색 `web_search`

| 순위 | 후보 | 장점 | 제한 |
|---:|---|---|---|
| 1 | [Tavily MCP](https://github.com/tavily-ai/tavily-mcp) | 검색·추출, 도메인 포함 필터 | API 키·크레딧 필요 |
| 2 | [Exa MCP](https://github.com/exa-labs/exa-mcp-server) | 검색·본문 읽기, 호스팅 MCP의 제한된 익명 접근 | 익명 호출 한도·가용성 |
| 3 | [Brave Search MCP](https://github.com/brave/brave-search-mcp-server) | 독립 검색 인덱스, 언어·지역 설정 | API 키. 정확한 부품 번호 검색 성능 미측정 |

### 3.3 공식 문서 가져오기·파싱 `fetch_official_document`

| 순위 | 후보 | 장점 | 제한 |
|---:|---|---|---|
| 1 | [Docling MCP](https://github.com/docling-project/docling-mcp) | PDF 구조화, 기존 Docling 파이프라인과 같은 계열 | 버전·SDK 호환성, 서버 자원. pdfplumber 대조·해시 검증을 대체하지 않음 |
| 2 | [Jina AI MCP](https://github.com/jina-ai/MCP) | 페이지·PDF 읽기·추출 | 외부 전송·한도·비용, 쪽·표·행 정확성 확인 필요 |
| 3 | [MCP Fetch](https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md) | 웹페이지 가져오기·Markdown 변환 | PDF 표 파싱 대체 불가. 내부 주소 접근 제한과 버전별 보안 검토 필요 |

### 3.4 사양·요구 조건 비교 `compare_requirements`

| 순위 | 후보 | 장점 | 제한 |
|---:|---|---|---|
| 1 | [SheetsData MCP](https://github.com/octoco-ltd/sheetsdata-mcp) | 데이터시트 읽기·부품 비교·동작 조건 적합성 | 호스팅·인증, 일부 과금. 프로젝트 판정 5종·단위·시험 조건 규칙과의 일치 미확인 |

2·3순위는 적합한 외부 MCP를 확인하지 못했다. 수치·단위 비교와 판정은 `backend/judge/`가 한다.

### 3.5 가격·재고 `get_price_availability` (확장 단계)

| 순위 | 후보 | 장점 | 제한 |
|---:|---|---|---|
| 1 | [Mouser Search MCP](https://github.com/cmaurer/mouser-search-mcp) | Mouser Search API 연결 | 커뮤니티 MCP. 키·약관·응답 저장 제한 확인 필요 |
| 2 | [PCB Parts MCP](https://github.com/Averyy/pcbparts-mcp) | JLCPCB·Mouser·DigiKey 조회 | 공급처별 키·한도·출처가 다름 |
| 3 | [Electronic Parts Finder MCP](https://github.com/controlguy-ys/electronic-parts-finder-mcp) | 복수 공급처 검색·통합 | 커뮤니티 구현. 응답·저장·로그·약관 검토 필요 |

## 4. 웹 검색 비용·적합성 (2026-11-03 공식 가격 기준)

무료 크레딧 적용 전 검색만 계산했다. 본문 추출, 추가 결과, 재시도, LLM 비용은 제외한다. 가격은 도입 직전 다시 확인해야 한다.

| 항목 | Tavily | Exa | Brave Search |
|---|---|---|---|
| 공식 MCP | 있음 | 있음 | 있음 |
| 검색 키 | 필요 | API는 필요. 호스팅 MCP 익명 접근은 제한 | 필요 |
| 무료 안내 | 월 1,000크레딧 | API 플랜 월 $10 크레딧. 익명 MCP 한도 별도 | Search 플랜 월 $5 크레딧 |
| 검색 1,000회 예시 | Basic·종량제 $8 | Lite $4부터 / Auto $7부터 | Search $5 |
| 추가 비용 | Basic 1크레딧/회, Advanced 2크레딧/회. 추출 별도 | 검색 모드·결과 수·본문 추출에 따라 | 별도 본문 확보 확인 |

공식 근거: [Tavily 요금·크레딧](https://docs.tavily.com/documentation/api-credits), [Tavily 가격](https://www.tavily.com/pricing), [Exa 가격](https://exa.ai/pricing), [Exa MCP 익명 제한](https://github.com/exa-labs/exa-mcp-server), [Brave Search 가격](https://brave.com/search/api/).

## 5. 탐색 입력: W01~W08

`data/manifest.jsonl`의 기존 문서 제목·개정 코드로 만든 8개 질의다. 정답이나 최신 판본으로 확정한 것이 아니며 동결 평가셋과 별개다. `1N4148`과 `1N4148W`처럼 유사 품번이 섞이는지 별도로 확인해야 한다.

| ID | 질의 | 비교 대상 문서 ID |
|---|---|---|
| W01 | `Taiwan Semiconductor 1N4148 SERIES K2301 datasheet` | `tsc-1n4148-series_k2301` |
| W02 | `Taiwan Semiconductor 1N4148W SERIES K1804 datasheet` | `tsc-1n4148w-series_k1804` |
| W03 | `Taiwan Semiconductor 1N4148W-G D1601 datasheet` | `tsc-1n4148w-g_d1601` |
| W04 | `Taiwan Semiconductor 1N4148WH A2501 datasheet` | `tsc-1n4148wh_a2501` |
| W05 | `Taiwan Semiconductor 1N5817 SERIES H2104 datasheet` | `tsc-1n5817-series_h2104` |
| W06 | `Taiwan Semiconductor BZT52B2V4-G SERIES H2002 datasheet` | `tsc-bzt52b2v4-g-series_h2002` |
| W07 | `Taiwan Semiconductor SS34L SERIES C2103 datasheet` | `tsc-ss34l-series_c2103` |
| W08 | `Taiwan Semiconductor SS34ALH SERIES B2103 datasheet` | `tsc-ss34alh-series_b2103` |

## 6. 무료 탐색 (2026-11-03, Exa 익명 공개 MCP)

| 탐색 | 조건 | 결과 |
|---|---|---|
| 연결 | 공개 엔드포인트에 초기화·도구 목록만 요청. 개인 정보·회로·API 키 없음. 예산 $0, 재시도 상한 1회 | 초기화 HTTP 200, 준비 알림 202, 도구 목록 200. 도구 `web_search_exa`, `web_fetch_exa`. 세 요청 합계 약 1,052ms(1회, 성능 지표 아님) |
| 검색 기능 | W01 질의 1회, 상위 5개, 키 없음. 목적은 처리 여부 확인뿐 | `tools/call` HTTP 200, 도구 오류 없음, 1,172.74ms. 반환 텍스트에서 URL 6개 추출, 그중 `taiwansemi.com` 계열 3개. manifest K2301 문서 경로와 일치하는 공식 도메인 PDF 링크 포함. `http` 주소도 포함됨 |

PDF를 내려받지 않았으므로 개정판·내용·해시는 확인하지 않았다. 공식 판본 검증 완료가 아니다. 수집 시에는 HTTPS·허용 도메인·리디렉션 검증을 별도로 적용해야 한다. 공개 MCP 주소는 `https://mcp.exa.ai/mcp`, 입력은 `{"query": "<W01 질의>", "objective": "Find the official manufacturer datasheet for the exact 1N4148 SERIES revision K2301 and provide source URLs.", "numResults": 5}`다. 재실행도 외부 요청이다.

## 7. W02~W08 비교 탐색

### 7.1 조건

| 항목 | 값 |
|---|---|
| 후보 | Tavily(Python SDK 0.8.5, 익명 Basic), Exa(익명 호스팅 MCP), Brave(Search API, 무료 크레딧) |
| 질의 | W02~W08 7개. W01은 Exa 탐색 결과를 이미 보아 제외 |
| 호출 | 후보·질의당 1회, 상위 5개, 15초, 재시도 0. 후보당 최대 7회, 전체 21회. 본문 추출·PDF 내려받기·LLM 답변 없음 |
| 예산 | 실제 지출 상한 $0. 무료 한도·자동 과금 방지 여부를 확인할 수 없으면 미실행. 무료분 전 단순 대입값: Tavily Basic $0.056, Exa Lite $0.028, Brave $0.035 |
| 사전 기대(합격 기준 아님) | 후보당 7질의 중 4~7질의에서 상위 5개에 TSC 공식 도메인 링크, 성공 호출 응답 시간 중앙값 0.5~5초 |
| 공식 도메인 판정 | URL의 hostname이 `taiwansemi.com` 또는 점으로 구분된 하위 도메인 |

### 7.2 1차 (2026-11-03)

| 후보 | 호출 | 정상 | 실패·판정 불가 | 공식 도메인 상위 5개 출현 | 정상 응답 중앙값 |
|---|---:|---:|---|---|---:|
| Tavily SDK 0.8.5, 익명 Basic | 7 | 7 | 없음 | 4/7 | 2,443.30ms |
| Exa 익명 호스팅 MCP | 7 | 4 | 무료 한도 오류 2(W03·W07), 응답 기록 오류 1(W02) | 확인된 4/7 | 1,430.37ms (정상 4건) |
| Brave Search API | 7 | 7 | 없음 | 7/7 | 669.14ms (최솟값 594.51, 최댓값 946.56) |

W02의 Exa 응답은 HTTP 200·2,211.70ms까지 확인했지만 Windows 출력 인코딩 오류로 응답을 덮어써 성공 여부와 URL을 판정할 수 없다. 사전 등록대로 재호출하지 않았다. Tavily는 W04·W06·W07·W08, Exa는 성공한 W04·W05·W06·W08에서 공식 도메인이 나타났다. 실패와 기록 불가를 0점으로 세지 않는다.

### 7.3 2차 재측정 (같은 질의, 독립 평가셋 아님)

| 후보 | 정상 | TSC 도메인 출현 | 정상 응답 중앙값 |
|---|---:|---:|---:|
| Tavily | 7/7 | 4/7 | 790.22ms |
| Exa | 7/7 | 6/7 | 1,193.75ms |
| Brave | 7/7 | 7/7 | 240.48ms |

| 질의 | Tavily 시간·출현 | Exa 시간·출현 | Brave 시간·출현 |
|---|---|---|---|
| W02 | 754.58ms · X | 1,086.42ms · O | 498.12ms · O |
| W03 | 747.61ms · X | 1,160.85ms · O | 247.55ms · O |
| W04 | 805.60ms · O | 1,194.95ms · O | 729.47ms · O |
| W05 | 810.93ms · X | 1,456.02ms · O | 231.15ms · O |
| W06 | 806.85ms · O | 1,184.64ms · O | 232.53ms · O |
| W07 | 790.22ms · O | 1,443.14ms · X | 240.48ms · O |
| W08 | 760.95ms · O | 1,193.75ms · O | 238.29ms · O |

O는 상위 5개 URL에 `taiwansemi.com` 또는 하위 도메인이 있다는 뜻이며 PDF 내용·품번·개정 일치 검증이 아니다. Exa는 응답의 URL 필드 순서로 5개를 센다. 응답 시간은 요청 전송부터 응답 수신까지이며 Exa MCP 초기화와 Tavily 프로세스 시작은 제외한다. Brave는 키 인증, 나머지 둘은 익명 방식이다.

### 7.4 판독 범위

- 7질의 표본은 작다. 도메인 적중은 품번·개정판·PDF 본문 일치 검증이 아니다.
- 세 방법의 시점·프로토콜·캐시가 달라 속도 차이를 공급자 고유 성능으로 읽을 수 없다.
- 원시 결과는 저장소 밖 질의별 URL·시간·오류 JSON이고 Tavily 실험 코드는 `benchmark_tavily_keyless.py`(저장소 밖)다. Brave 원문·URL은 보관하지 않았다.

## 8. 한계

1. 7절의 모든 수치와 6절의 탐색 결과는 원시 파일이 저장소에 없고 재계산하지 않았다.
2. 3절 후보 링크와 4절 가격은 2026-11-03 조사값이며 현재 상태를 다시 확인하지 않았다.
3. Brave 사용량은 무료 크레딧 $5·자동 충전 꺼짐을 확인하고 실행했다. 대시보드의 실제 차감액은 확인하지 않았다. 파생 통계의 보관·공유 가능 범위는 공급자 확인이 필요하다.
4. 사전 기대(7.1절)는 합격 기준이 아니다.
5. 후보별 우열, 비용 대비 효과, 실서비스 안정성은 이 자료로 정하지 않는다.
