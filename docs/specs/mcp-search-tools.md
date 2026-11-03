# MCP 검색 도구 1차 작업서

## Why

SojaFit 에이전트는 기존 코퍼스 검색과 코퍼스에 없는 TSC 문서 후보 탐색이 필요하다. 검색 후보가 곧 판정 근거가 되지 않도록 경계를 유지하며, API 키 없는 데모와 오프라인 평가를 지원해야 한다.

## Goal

- MCP stdio 서버에서 코퍼스 검색과 Exa 기반 공식 TSC 문서 후보 검색 도구 2개를 노출한다.
- 외부 호출은 기본 0회, 명시적인 허용과 키가 있는 경우 도구 요청당 최대 1회이며 재시도하지 않는다.
- Out of Scope: LangGraph 실제 연결, 외부 문서 다운로드·파싱·검증·적재, 자동 재검색, 사용자용 HTTP 배포, 가산점 충족 주장, 실제 서비스 부하 평가.

## What

- 코퍼스 검색은 기존 retrieve(question, k, parts, method) 계약을 사용한다.
- 공식 문서 후보 검색은 Exa 검색 API 결과에서 HTTPS TSC 공식 도메인 URL만 후보로 반환하며 미검증 상태를 표시한다.
- verify_tsc_pdf(doc_id)는 저장소의 TSC 표본 3건에 대해서만 PDF 서명·바이트 크기·SHA-256을 manifest와 대조한다. 내용 파싱 검증은 아니다.
- get_circuit_info(circuit_id, target)는 고정된 공개 회로 ID 카탈로그에서 connections.json을 읽고 기존 circuit_around를 호출한다. 임의 경로 입력은 허용하지 않는다.
- 외부 검색이 꺼져 있거나 데모일 때 disabled, 키가 없으면 missing_key, 공급자 실패면 unavailable을 반환한다.
- 빈 질의·너무 긴 질의 및 허용 밖 k를 거부한다. 외부 오류 본문이나 인증키는 응답에 포함하지 않는다.

## How

- MCP Python SDK 1.x FastMCP와 stdio를 사용한다.
- 도구 search_corpus(query, k=5, parts=None)는 backend.rag.retrieve.retrieve를 호출한다.
- 도구 search_tsc_web(doc_id)는 DEMO_MODE=0 및 EXA_WEB_SEARCH_ENABLED=1, EXA_API_KEY가 모두 갖춰진 경우에만 Exa Search API 호출 1회, 결과 최대 5개, 타임아웃 15초, 리디렉션 금지를 적용한다.
- Exa에는 공개 목록에서 확인한 문서명·개정으로 구성한 질의와 TSC 도메인 필터만 보낸다. 답변 본문이나 공급자 오류는 저장하지 않는다.
- 반환된 링크는 URL 후보일 뿐이다. 실제 PDF·품번·개정판·본문의 검증과 적재는 후속 작업이다.
- G5 평가 호출 경로에는 연결하지 않는다. 평가 실행에서 외부 검색은 비활성 상태여야 한다.

## AC

- GIVEN 기존 검색기 대역 WHEN 코퍼스 도구 호출 THEN query, k, parts가 기존 검색 계약에 전달되고 결과가 그대로 반환된다.
- GIVEN 데모 또는 외부 검색 미허용 WHEN 문서 후보 도구 호출 THEN 외부 요청 없이 disabled를 반환한다.
- GIVEN 외부 검색 허용과 키 누락 WHEN 호출 THEN 외부 요청 없이 missing_key를 반환한다.
- GIVEN 정상 Exa 응답 WHEN 호출 THEN 안전한 HTTPS TSC URL만 최대 5개 미검증 후보로 반환한다.
- GIVEN Exa HTTP 오류 또는 비정상 응답 WHEN 호출 THEN 비밀값과 오류 본문 없이 unavailable을 반환하고 재시도하지 않는다.
- GIVEN 빈 질의 또는 범위 밖 결과 수 WHEN 호출 THEN 잘못된 입력을 거부한다.
- GIVEN stdio MCP 클라이언트 WHEN 도구 목록을 조회 THEN 두 도구가 보인다.

## 문서 메타데이터 조회 1차

- Why: 코퍼스 검색에서 반환된 문서 식별자를 이용해 출처와 개정판 등 기존 manifest 기록을 확인한다.
- Goal: 외부 호출·DB 변경 없이 manifest 기준 정확히 일치하는 문서 1건을 조회한다.
- What: get_corpus_document(doc_id)는 found, not_found, unavailable을 구분한다. 문서 식별자는 1~200자이고 빈 값은 거절한다. manifest 손상이나 읽기 실패는 unavailable을 반환한다.
- How: 저장소의 data/manifest.jsonl을 읽고 doc_id가 정확히 일치하는 항목에서 doc_id, title, revision, source_url, sha256, bytes, pages를 반환한다. PDF·해시를 재검증하지 않았음을 pdf_verified=false로 표시한다. 사용자 입력을 파일 경로로 사용하거나 네트워크 호출을 하지 않는다.
- AC: GIVEN manifest의 문서 ID WHEN 조회 THEN 해당 문서 정보와 pdf_verified=false를 반환한다. GIVEN 존재하지 않는 ID WHEN 조회 THEN not_found. GIVEN 읽기 실패·손상 WHEN 조회 THEN unavailable. GIVEN 빈 ID 또는 200자 초과 WHEN 조회 THEN 입력 오류. GIVEN MCP 클라이언트 WHEN 도구 목록 조회 THEN 이 도구가 포함된다.

## 외부 검색 개인정보 경계

- Why: 회로 설명이나 비공개 품번이 외부 검색 공급자에 전달되지 않도록 한다.
- Goal: 외부 호출 시 신뢰한 공개 TSC manifest의 문서명과 개정만 전송한다. 목록에 없거나 출처·형식이 일치하지 않으면 호출 0회.
- What: search_tsc_web(doc_id)는 정확히 일치하는 문서 ID만 받는다. 미확인 항목은 unverified, 목록 읽기 실패는 unavailable. 기존 자유 문장 검색 계약은 중단한다.
- How: TSC 공식 데이터시트 경로의 파일명이 목록의 문서명·개정과 일치하고 안전한 형식일 때만 고정 문구와 해당 문서명·개정으로 질의를 구성한다. 사용자 원문은 전송하지 않는다. 목록은 공개 출처의 과거 기록이며 실시간 공개 여부나 최신성을 보장하지 않는다.
- AC: GIVEN 내부 정보가 포함된 ID, 없는 ID, 출처나 파일명이 불일치하는 기록 WHEN 검색 THEN 외부 요청 없이 unverified. GIVEN 목록 읽기 실패 WHEN 검색 THEN 외부 요청 없이 unavailable. GIVEN 허용된 문서 WHEN 검색 THEN 고정 문구와 목록의 문서명·개정만 전송한다.

## 우선순위 2 도구 1차 기능

- Goal: 저장소에 포함된 표본과 공개 회로 카탈로그에서 안전한 로컬 확인을 제공한다.
- What: PDF 도구는 세 표본만 서명·크기·해시를 대조하며 `content_verified=false`를 유지한다. 회로 도구는 허용 ID와 부품 기호로 연결 정보를 조회한다.
- How: 외부 다운로드·DB 쓰기·임의 경로 접근은 하지 않는다. 전체 PDF 파싱 관문과 사용자별 회로 권한은 후속 계약이다.
- AC: GIVEN 표본 PDF WHEN 검증 THEN manifest 해시·크기 일치와 내용 미검증을 표시한다. GIVEN 허용 회로 ID와 존재하는 ref WHEN 조회 THEN 연결 정보를 반환한다. 알 수 없는 ID/ref는 not_found이며 경로 형식 주입은 거부한다.
