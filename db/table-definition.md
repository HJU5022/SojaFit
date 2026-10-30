# SojaFit DB 테이블 정의서 초안

## 1. 문서 목적

이 문서는 SojaFit의 업무 데이터를 PostgreSQL에 저장하기 위한 테이블 정의 초안입니다. 다음 단계에서 이 문서를 기준으로 ERD를 작성하고, ERD 검토가 끝난 뒤 Migration SQL을 작성합니다.

현재 프로젝트의 핵심 흐름은 다음과 같습니다.

```text
사용자 로그인
→ KiCad 넷리스트 등록
→ 교체 대상 부품 분석
→ 회로 역할과 대체 조건 도출
→ 후보 부품별 판정과 근거 제시
→ 사람 승인
→ 승인된 견적서 저장
```

## 2. 현재 범위

### 포함

- 로그인 사용자 식별
- KiCad 넷리스트와 회로 정보
- 부품과 데이터시트 기반 구조화 사양
- 분석 실행과 교체 대상 부품
- 역할 기반 대체 조건
- 후보 부품별 5종 판정
- 판정에 사용한 문서 인용
- 승인 후 저장되는 견적서
- RAG 원문 문서와 일반 텍스트 청크 메타데이터

### 제외

- `pgvector` 임베딩 컬럼과 벡터 인덱스
- HNSW, IVFFlat 등 벡터 검색 구조
- 실시간 가격·재고 조회
- 실제 주문·결제
- ERD
- Migration SQL
- LangGraph 라이브러리가 자동 생성하는 체크포인트와 Store 테이블

## 3. 작성 기준

### 3.1 확정 상태

| 상태 | 의미 |
|---|---|
| 확정 | 현재 `SPEC.md`와 프로젝트 문서에서 필요성이 확인됨 |
| 가정 | 초안을 작성하기 위해 합리적인 기본값을 두었으나 팀 합의가 필요함 |
| 미정 | 요구사항이나 기술 선택이 정해지지 않아 추가 결정이 필요함 |

`가정`과 `미정` 항목은 바로 Migration에 반영하지 않습니다. 이 문서의 추가 검토 영역에서 결정한 뒤 반영합니다.

### 3.2 공통 규칙 초안

- 테이블명과 컬럼명은 영문 `snake_case`를 사용합니다.
- 애플리케이션이 생성하는 주요 테이블의 PK는 `BIGINT`를 사용합니다. 자동 증가 방식은 Migration 단계에서 결정합니다.
- 날짜와 시각은 `TIMESTAMPTZ`를 사용하고 UTC로 저장하는 것을 가정합니다.
- 금액은 부동소수점 오차를 피하기 위해 `NUMERIC`을 사용합니다.
- 측정값은 원본 단위와 정규화된 단위를 구분할 수 있어야 합니다.
- 원본 문서, 회로 파일 및 판정 결과는 재현을 위해 버전 또는 해시를 남깁니다.
- `created_at`, `updated_at`의 자동 갱신 방식은 Migration 단계에서 결정합니다.

## 4. 테이블 목록

| 구분 | 논리명 | 물리명 | 역할 | 상태 |
|---|---|---|---|---|
| 사용자 | 사용자 | `users` | 로그인 사용자와 승인자를 식별 | 가정 포함 |
| 회로 | 회로 | `circuits` | 업로드한 KiCad 넷리스트와 파일 메타데이터 저장 | 가정 포함 |
| 분석 | 분석 실행 | `analysis_runs` | 특정 회로 부품에 대한 한 번의 대체 분석 저장 | 확정 |
| 부품 | 부품 | `parts` | 원본 부품과 후보 부품의 기본정보 저장 | 확정 |
| 부품 | 부품 사양 | `part_specifications` | 데이터시트에서 추출한 구조화된 사양 저장 | 가정 포함 |
| 분석 | 대체 조건 | `replacement_requirements` | 회로 역할에서 도출한 필수·선택 조건 저장 | 확정 |
| 분석 | 후보 판정 | `candidate_evaluations` | 분석별 후보 부품의 5종 판정 저장 | 확정 |
| 근거 | 출처 문서 | `source_documents` | 데이터시트와 공개 문서의 출처·버전 저장 | 확정 |
| 근거 | 문서 청크 | `document_chunks` | 검색 가능한 일반 텍스트 청크와 위치 저장 | 확정 |
| 근거 | 부품 문서 연결 | `part_documents` | 부품과 해당 데이터시트 연결 | 가정 |
| 근거 | 판정 인용 | `evidence_citations` | 후보 판정에 사용한 페이지·표·행 근거 저장 | 확정 |
| 견적 | 견적서 | `quotes` | 사람 승인 후 확정된 견적서 저장 | 확정 |
| 견적 | 견적 항목 | `quote_items` | 견적서에 포함된 부품·수량·가격 저장 | 확정 |

## 5. 테이블 상세 정의

### 5.1 `users` — 사용자

로그인 사용자를 식별하고 사용자별 회로, 분석, 기억 및 승인을 분리합니다. 로그인 구현 방식은 아직 정해지지 않았으므로 인증 관련 컬럼은 가정입니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 사용자 ID | `BIGINT` | N | PK | 내부 사용자 식별자 | 확정 |
| `login_id` | 로그인 ID | `VARCHAR(100)` | N | UNIQUE | 사용자가 로그인할 때 사용하는 식별자 | 가정 |
| `password_hash` | 비밀번호 해시 | `VARCHAR(255)` | Y |  | 로컬 인증을 선택할 때만 사용하며 평문 비밀번호는 저장하지 않음 | 미정 |
| `display_name` | 표시 이름 | `VARCHAR(100)` | Y |  | 화면에 표시할 이름 | 가정 |
| `is_active` | 활성 여부 | `BOOLEAN` | N | 기본값 `true` 가정 | 비활성 계정의 접근을 막기 위한 값 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 계정 생성 시각 | 확정 |
| `updated_at` | 수정 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 계정 마지막 수정 시각 | 가정 |

### 5.2 `circuits` — 회로

사용자가 업로드한 KiCad 넷리스트를 분석 가능한 단위로 저장합니다. MVP에서는 입력 원문을 보존해 같은 분석을 재현할 수 있어야 합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 회로 ID | `BIGINT` | N | PK | 회로 식별자 | 확정 |
| `user_id` | 소유 사용자 ID | `BIGINT` | N | FK → `users.id` | 회로를 등록한 사용자 | 확정 |
| `name` | 회로 이름 | `VARCHAR(200)` | N |  | 사용자가 구분하는 회로 이름 | 가정 |
| `original_filename` | 원본 파일명 | `VARCHAR(255)` | N |  | 업로드 당시 파일명 | 확정 |
| `netlist_format` | 넷리스트 형식 | `VARCHAR(50)` | N |  | KiCad XML, S-expression 등 입력 형식 | 가정 |
| `netlist_content` | 넷리스트 원문 | `TEXT` | N |  | 분석 재현에 사용하는 원본 내용 | 가정 |
| `content_sha256` | 콘텐츠 해시 | `CHAR(64)` | N | 사용자 범위 중복 정책 미정 | 동일 입력 확인과 재현에 사용하는 SHA-256 | 확정 |
| `created_at` | 등록 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 회로 등록 시각 | 확정 |
| `updated_at` | 수정 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 회로 정보 수정 시각 | 가정 |

### 5.3 `parts` — 부품

원본 부품과 대체 후보 부품을 같은 부품 목록에서 관리합니다. 원본인지 후보인지는 분석 안에서의 역할이므로 이 테이블에 고정하지 않습니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 부품 ID | `BIGINT` | N | PK | 부품 식별자 | 확정 |
| `manufacturer` | 제조사 | `VARCHAR(150)` | N | 복합 UNIQUE 후보 | 제조사명 | 확정 |
| `part_number` | 품번 | `VARCHAR(150)` | N | 복합 UNIQUE 후보 | 제조사가 부여한 품번 | 확정 |
| `category_code` | 부품 분류 코드 | `VARCHAR(50)` | N | MVP는 다이오드만 허용 | 제너, 쇼트키, 정류 다이오드 등의 분류 | 가정 |
| `package_code` | 패키지 코드 | `VARCHAR(100)` | Y |  | SOD-123, DO-41 등 패키지 정보 | 확정 |
| `description` | 부품 설명 | `TEXT` | Y |  | 부품의 짧은 설명 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 부품 등록 시각 | 확정 |
| `updated_at` | 수정 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 부품 정보 수정 시각 | 가정 |

제약조건 초안: 동일 제조사의 동일 품번이 중복되지 않도록 `UNIQUE (manufacturer, part_number)`를 검토합니다. 패키지별 품번 표기 방식이 확인된 뒤 확정합니다.

### 5.4 `source_documents` — 출처 문서

RAG 코퍼스에 포함된 데이터시트와 공개 문서의 출처, 버전 및 이용 조건을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 문서 ID | `BIGINT` | N | PK | 출처 문서 식별자 | 확정 |
| `document_key` | 문서 키 | `VARCHAR(200)` | N | UNIQUE | manifest와 DB에서 공통으로 사용하는 문서 식별키 | 가정 |
| `document_type` | 문서 종류 | `VARCHAR(50)` | N | 허용 코드 미정 | 데이터시트, 설계 문서, 분류 문서 등의 종류 | 확정 |
| `title` | 문서 제목 | `VARCHAR(500)` | N |  | 문서 제목 | 확정 |
| `publisher` | 발행처 | `VARCHAR(200)` | N |  | 제조사 또는 공개 문서 발행처 | 확정 |
| `source_url` | 원본 URL | `TEXT` | N |  | 문서 원본 위치 | 확정 |
| `revision` | 문서 개정 정보 | `VARCHAR(100)` | Y |  | 발행일, 버전 또는 revision | 확정 |
| `license_text` | 이용 조건 | `TEXT` | Y |  | 라이선스와 재배포 조건 요약 | 확정 |
| `file_sha256` | 파일 해시 | `CHAR(64)` | N | UNIQUE 후보 | 실제 수집 파일의 SHA-256 | 확정 |
| `corpus_version` | 코퍼스 버전 | `VARCHAR(100)` | N |  | 해당 문서가 포함된 코퍼스 버전 | 확정 |
| `collected_at` | 수집 시각 | `TIMESTAMPTZ` | N |  | 원본을 수집한 시각 | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | DB 레코드 생성 시각 | 가정 |

### 5.5 `part_documents` — 부품 문서 연결

하나의 부품에 여러 문서가 연결되거나 한 문서가 여러 부품을 다루는 경우를 표현합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `part_id` | 부품 ID | `BIGINT` | N | PK 일부, FK → `parts.id` | 문서에 설명된 부품 | 확정 |
| `document_id` | 문서 ID | `BIGINT` | N | PK 일부, FK → `source_documents.id` | 부품을 설명하는 문서 | 확정 |
| `relationship_type` | 관계 종류 | `VARCHAR(30)` | N | 허용 코드 미정 | 기본 데이터시트, 보충 문서 등의 구분 | 가정 |
| `is_primary` | 대표 문서 여부 | `BOOLEAN` | N | 기본값 `false` 가정 | 부품의 대표 데이터시트인지 표시 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 연결 생성 시각 | 가정 |

PK 초안: `PRIMARY KEY (part_id, document_id)`.

### 5.6 `document_chunks` — 문서 청크

출처 문서에서 추출한 일반 텍스트와 문서 내 위치를 저장합니다. 임베딩과 벡터 컬럼은 현재 범위에서 제외합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 청크 ID | `BIGINT` | N | PK | 청크 식별자 | 확정 |
| `document_id` | 문서 ID | `BIGINT` | N | FK → `source_documents.id` | 원본 문서 | 확정 |
| `chunk_index` | 청크 순서 | `INTEGER` | N | 문서 안에서 UNIQUE | 원문 내 청크 순서, 0 또는 1 시작 여부 미정 | 확정 |
| `content` | 청크 본문 | `TEXT` | N |  | 검색과 인용에 사용하는 텍스트 | 확정 |
| `page_number` | 페이지 번호 | `INTEGER` | Y | 양수 CHECK 후보 | PDF 기준 페이지 번호 | 확정 |
| `section_name` | 절 이름 | `VARCHAR(500)` | Y |  | 원문 내 절 또는 제목 | 확정 |
| `table_name` | 표 이름 | `VARCHAR(500)` | Y |  | 표에서 추출한 경우 표 이름 | 확정 |
| `row_label` | 행 식별자 | `VARCHAR(500)` | Y |  | 표의 행 이름 또는 항목명 | 확정 |
| `token_count` | 토큰 수 | `INTEGER` | Y | 0 이상 CHECK 후보 | 사용한 토크나이저 기준 토큰 수 | 가정 |
| `chunker_version` | 청커 버전 | `VARCHAR(100)` | N |  | 청크 생성 규칙 또는 코드 버전 | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 청크 생성 시각 | 가정 |

제약조건 초안: `UNIQUE (document_id, chunk_index)`.

### 5.7 `part_specifications` — 부품 사양

데이터시트에서 추출한 숫자 사양과 시험 조건을 구조화해 저장합니다. `backend/judge/`가 LLM 대신 숫자와 단위를 비교할 때 사용하는 데이터입니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 부품 사양 ID | `BIGINT` | N | PK | 사양 식별자 | 확정 |
| `part_id` | 부품 ID | `BIGINT` | N | FK → `parts.id` | 사양 대상 부품 | 확정 |
| `document_id` | 출처 문서 ID | `BIGINT` | N | FK → `source_documents.id` | 값을 추출한 데이터시트 | 확정 |
| `parameter_code` | 파라미터 코드 | `VARCHAR(100)` | N | 코드 목록 미정 | 역전압, 순방향 전류 등의 표준화된 항목 | 미정 |
| `symbol` | 데이터시트 기호 | `VARCHAR(50)` | Y |  | 데이터시트에 표시된 `VRRM`, `IF` 등의 기호 | 확정 |
| `minimum_value` | 최소값 | `NUMERIC` | Y |  | 데이터시트 최소값 | 확정 |
| `typical_value` | 대표값 | `NUMERIC` | Y |  | 데이터시트 대표값 | 확정 |
| `maximum_value` | 최대값 | `NUMERIC` | Y |  | 데이터시트 최대값 | 확정 |
| `text_value` | 비수치 값 | `TEXT` | Y |  | 숫자로 표현할 수 없는 사양값 | 가정 |
| `source_unit` | 원본 단위 | `VARCHAR(30)` | Y |  | 데이터시트에 표기된 단위 | 확정 |
| `normalized_unit` | 정규화 단위 | `VARCHAR(30)` | Y | 단위 표준 미정 | 비교 코드에서 사용하는 표준 단위 | 미정 |
| `test_condition` | 시험 조건 | `TEXT` | Y |  | 온도, 전류 등 값이 성립하는 조건 | 확정 |
| `page_number` | 페이지 번호 | `INTEGER` | Y |  | 데이터시트 페이지 | 확정 |
| `table_name` | 표 이름 | `VARCHAR(500)` | Y |  | 값이 나온 표 이름 | 확정 |
| `row_label` | 행 식별자 | `VARCHAR(500)` | Y |  | 값이 나온 행 또는 항목명 | 확정 |
| `footnote_text` | 각주 | `TEXT` | Y |  | 값에 적용되는 데이터시트 각주 | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 사양 적재 시각 | 가정 |

최소값, 대표값, 최대값, 비수치 값이 모두 비어 있는 행을 허용할지는 파서 결과를 확인한 뒤 결정합니다.

### 5.8 `analysis_runs` — 분석 실행

사용자가 특정 회로의 특정 부품을 대상으로 수행한 한 번의 대체 분석을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 분석 실행 ID | `BIGINT` | N | PK | 분석 실행 식별자 | 확정 |
| `user_id` | 사용자 ID | `BIGINT` | N | FK → `users.id` | 분석을 요청한 사용자 | 확정 |
| `circuit_id` | 회로 ID | `BIGINT` | N | FK → `circuits.id` | 분석 대상 회로 | 확정 |
| `original_part_id` | 원본 부품 ID | `BIGINT` | Y | FK → `parts.id` | 넷리스트의 원본 품번이 식별된 경우 연결 | 확정 |
| `target_reference` | 교체 대상 참조명 | `VARCHAR(100)` | N |  | `D1`, `D2` 등 회로 내 참조명 | 확정 |
| `role_code` | 회로 역할 코드 | `VARCHAR(100)` | Y | 코드 목록 미정 | 역극성 보호, 제너 클램프 등의 표준 역할 | 미정 |
| `role_description` | 회로 역할 설명 | `TEXT` | Y |  | 사용자에게 보여 주는 역할 설명 | 확정 |
| `status_code` | 분석 상태 | `VARCHAR(30)` | N | 허용 코드 미정 | 접수, 분석 중, 승인 대기, 완료, 실패 등의 상태 | 미정 |
| `corpus_version` | 코퍼스 버전 | `VARCHAR(100)` | N |  | 검색에 사용한 코퍼스 버전 | 확정 |
| `rule_version` | 판정 규칙 버전 | `VARCHAR(100)` | N |  | 대체 조건과 판정에 사용한 규칙 버전 | 가정 |
| `started_at` | 시작 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 분석 시작 시각 | 확정 |
| `completed_at` | 완료 시각 | `TIMESTAMPTZ` | Y |  | 분석 완료 또는 종료 시각 | 확정 |
| `failure_reason` | 실패 사유 | `TEXT` | Y |  | 분석 실패 시 사용자에게 설명할 사유 | 가정 |

동일한 회로와 부품을 여러 번 분석할 수 있으므로 `(circuit_id, target_reference)`에는 UNIQUE를 두지 않습니다.

### 5.9 `replacement_requirements` — 대체 조건

회로 역할에서 도출한 후보 부품의 필수 또는 선택 조건을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 대체 조건 ID | `BIGINT` | N | PK | 대체 조건 식별자 | 확정 |
| `analysis_run_id` | 분석 실행 ID | `BIGINT` | N | FK → `analysis_runs.id` | 조건이 도출된 분석 | 확정 |
| `parameter_code` | 파라미터 코드 | `VARCHAR(100)` | N | 코드 목록 미정 | `part_specifications.parameter_code`와 비교할 항목 | 미정 |
| `comparison_operator` | 비교 연산자 | `VARCHAR(20)` | N | 허용 값 미정 | `>=`, `<=`, `=`, `BETWEEN` 등의 비교 방식 | 미정 |
| `required_value` | 요구값 | `NUMERIC` | Y |  | 조건의 첫 번째 수치 | 확정 |
| `secondary_value` | 두 번째 요구값 | `NUMERIC` | Y |  | 범위 조건의 두 번째 수치 | 가정 |
| `required_text` | 비수치 요구값 | `TEXT` | Y |  | 패키지나 재질처럼 문자열로 비교하는 값 | 가정 |
| `unit` | 비교 단위 | `VARCHAR(30)` | Y | 단위 표준 미정 | 정규화된 비교 단위 | 미정 |
| `test_condition` | 적용 조건 | `TEXT` | Y |  | 온도, 전류 등 요구값이 적용되는 조건 | 확정 |
| `is_mandatory` | 필수 여부 | `BOOLEAN` | N | 기본값 `true` 가정 | 불충족 시 후보를 탈락시킬 조건인지 표시 | 확정 |
| `rationale` | 도출 이유 | `TEXT` | N |  | 회로 역할에서 이 조건을 도출한 이유 | 확정 |
| `sort_order` | 표시 순서 | `INTEGER` | N | 0 이상 CHECK 후보 | 화면에서 조건을 보여 줄 순서 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 조건 생성 시각 | 가정 |

수치 조건과 비수치 조건의 값 조합을 제한하는 CHECK는 연산자 규칙이 확정된 뒤 작성합니다.

### 5.10 `candidate_evaluations` — 후보 판정

분석 실행에서 후보 부품마다 내린 대체 판정과 판정 이유를 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 후보 판정 ID | `BIGINT` | N | PK | 판정 식별자 | 확정 |
| `analysis_run_id` | 분석 실행 ID | `BIGINT` | N | FK → `analysis_runs.id` | 판정이 속한 분석 | 확정 |
| `candidate_part_id` | 후보 부품 ID | `BIGINT` | N | FK → `parts.id` | 판정 대상 후보 부품 | 확정 |
| `verdict_code` | 대체 판정 코드 | `VARCHAR(30)` | N | 5종 코드 미정 | 동일품, 사양 동등, 역할상 충분, 불충족, 문서로 확인 안 됨 | 미정 |
| `reason` | 판정 이유 | `TEXT` | N |  | 조건 비교와 문서 근거를 요약한 설명 | 확정 |
| `board_change_required` | 기판 수정 필요 | `BOOLEAN` | N | 기본값 `false` 가정 | 패키지 차이로 PCB 수정이 필요한지 표시 | 확정 |
| `uncertainty_reason` | 확인 불가 사유 | `TEXT` | Y |  | 문서 누락 또는 시험 조건 차이로 확인하지 못한 이유 | 확정 |
| `created_at` | 판정 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 판정 생성 시각 | 확정 |

제약조건 초안: 한 번의 분석에서 같은 후보를 중복 판정하지 않도록 `UNIQUE (analysis_run_id, candidate_part_id)`를 둡니다.

### 5.11 `evidence_citations` — 판정 인용

후보 판정에 사용한 데이터시트의 페이지·표·행 또는 공개 문서의 절을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 인용 ID | `BIGINT` | N | PK | 인용 식별자 | 확정 |
| `candidate_evaluation_id` | 후보 판정 ID | `BIGINT` | N | FK → `candidate_evaluations.id` | 인용이 뒷받침하는 판정 | 확정 |
| `document_id` | 문서 ID | `BIGINT` | N | FK → `source_documents.id` | 인용 원문 | 확정 |
| `chunk_id` | 청크 ID | `BIGINT` | Y | FK → `document_chunks.id` | 검색에서 사용한 청크 | 확정 |
| `citation_type` | 인용 종류 | `VARCHAR(30)` | N | 허용 코드 미정 | 페이지, 표, 행, 절 등의 구분 | 가정 |
| `page_number` | 페이지 번호 | `INTEGER` | Y |  | PDF 페이지 번호 | 확정 |
| `section_name` | 절 이름 | `VARCHAR(500)` | Y |  | 공개 문서 또는 데이터시트 절 | 확정 |
| `table_name` | 표 이름 | `VARCHAR(500)` | Y |  | 데이터시트 표 이름 | 확정 |
| `row_label` | 행 식별자 | `VARCHAR(500)` | Y |  | 표의 행 또는 항목명 | 확정 |
| `quoted_text` | 인용 문구 | `TEXT` | N |  | 판정에 실제로 사용한 짧은 원문 | 확정 |
| `sort_order` | 표시 순서 | `INTEGER` | N | 0 이상 CHECK 후보 | 판정 화면의 근거 표시 순서 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 인용 생성 시각 | 가정 |

`chunk_id`가 있을 때 해당 청크의 `document_id`와 인용의 `document_id`가 같아야 합니다. DB 제약 또는 애플리케이션 검증 중 어느 쪽에서 보장할지 Migration 단계에서 결정합니다.

### 5.12 `quotes` — 견적서

사람이 승인한 뒤에만 견적서를 저장합니다. 승인 전 초안은 LangGraph 체크포인트 상태에 두는 것을 기본안으로 합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 견적서 ID | `BIGINT` | N | PK | 견적서 식별자 | 확정 |
| `analysis_run_id` | 분석 실행 ID | `BIGINT` | N | FK → `analysis_runs.id` | 견적의 근거가 된 분석 | 확정 |
| `quote_number` | 견적서 번호 | `VARCHAR(100)` | N | UNIQUE | 화면과 문서에 표시할 견적 번호 | 가정 |
| `approved_by_user_id` | 승인 사용자 ID | `BIGINT` | N | FK → `users.id` | 저장을 승인한 사용자 | 확정 |
| `currency_code` | 통화 코드 | `CHAR(3)` | N | ISO 4217 사용 가정 | 가격 표시 통화 | 가정 |
| `total_amount` | 총 금액 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 견적 총액 스냅샷 | 가정 |
| `approved_at` | 승인 시각 | `TIMESTAMPTZ` | N |  | 사람이 승인한 시각 | 확정 |
| `created_at` | 저장 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 승인된 견적을 DB에 저장한 시각 | 확정 |

한 분석에서 여러 견적 버전을 허용할지는 미정이므로 `analysis_run_id`에 UNIQUE를 두지 않습니다.

### 5.13 `quote_items` — 견적 항목

승인된 견적서에 포함된 후보 부품, 수량 및 승인 당시의 가격을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 견적 항목 ID | `BIGINT` | N | PK | 견적 항목 식별자 | 확정 |
| `quote_id` | 견적서 ID | `BIGINT` | N | FK → `quotes.id` | 항목이 속한 견적서 | 확정 |
| `candidate_evaluation_id` | 후보 판정 ID | `BIGINT` | N | FK → `candidate_evaluations.id` | 견적 선택의 근거가 된 후보 판정 | 확정 |
| `part_id` | 부품 ID | `BIGINT` | N | FK → `parts.id` | 견적 대상 부품 | 확정 |
| `quantity` | 수량 | `INTEGER` | N | 1 이상 CHECK 후보 | 견적 수량 | 확정 |
| `unit_price` | 단가 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 승인 당시 단가 | 가정 |
| `line_amount` | 항목 금액 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 수량과 단가를 반영한 금액 스냅샷 | 가정 |
| `price_source` | 가격 출처 | `VARCHAR(200)` | Y |  | 데모 데이터 또는 가격 제공처 | 가정 |
| `price_as_of` | 가격 기준 시각 | `TIMESTAMPTZ` | Y |  | 가격이 유효했던 기준 시각 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 견적 항목 생성 시각 | 가정 |

`part_id`는 `candidate_evaluation_id`가 가리키는 후보 부품과 같아야 합니다. 중복 컬럼을 제거할지 견적 스냅샷으로 유지할지는 추가 검토가 필요합니다.

## 6. 관계 정의 초안

| 부모 | 관계 | 자식 | 설명 |
|---|---:|---|---|
| `users` | 1:N | `circuits` | 한 사용자가 여러 회로를 등록할 수 있음 |
| `users` | 1:N | `analysis_runs` | 한 사용자가 여러 분석을 실행할 수 있음 |
| `circuits` | 1:N | `analysis_runs` | 같은 회로의 여러 부품 또는 같은 부품을 반복 분석할 수 있음 |
| `parts` | 1:N | `analysis_runs` | 하나의 부품이 여러 분석에서 원본 부품으로 사용될 수 있음 |
| `parts` | N:M | `source_documents` | `part_documents`가 연결함 |
| `source_documents` | 1:N | `document_chunks` | 한 문서를 여러 청크로 나눔 |
| `parts` | 1:N | `part_specifications` | 한 부품에 여러 사양과 시험 조건이 존재함 |
| `source_documents` | 1:N | `part_specifications` | 한 문서에서 여러 구조화 사양을 추출함 |
| `analysis_runs` | 1:N | `replacement_requirements` | 한 분석에서 여러 대체 조건을 도출함 |
| `analysis_runs` | 1:N | `candidate_evaluations` | 한 분석에서 여러 후보를 판정함 |
| `parts` | 1:N | `candidate_evaluations` | 같은 부품이 여러 분석에서 후보가 될 수 있음 |
| `candidate_evaluations` | 1:N | `evidence_citations` | 한 판정에 여러 문서 근거를 붙일 수 있음 |
| `source_documents` | 1:N | `evidence_citations` | 같은 문서가 여러 판정의 근거가 될 수 있음 |
| `analysis_runs` | 1:N | `quotes` | 견적 버전 정책이 정해지기 전까지 여러 견적을 허용하는 구조 |
| `quotes` | 1:N | `quote_items` | 한 견적서에 여러 부품 항목을 넣을 수 있음 |
| `candidate_evaluations` | 1:N | `quote_items` | 같은 판정을 여러 견적 버전에서 사용할 수 있음 |

## 7. 주요 제약조건 초안

| 대상 | 제약조건 | 상태 |
|---|---|---|
| `parts` | 제조사와 품번의 조합 중복 금지 | 가정 |
| `source_documents` | 문서 키 중복 금지 | 가정 |
| `source_documents` | 동일 파일 해시 중복 정책 검토 | 미정 |
| `part_documents` | 같은 부품과 문서 연결 중복 금지 | 확정 |
| `document_chunks` | 같은 문서에서 청크 순번 중복 금지 | 확정 |
| `candidate_evaluations` | 같은 분석에서 후보 부품 중복 판정 금지 | 확정 |
| `quote_items` | 수량은 1 이상 | 확정 |
| `quotes`, `quote_items` | 금액은 0 이상 | 가정 |
| `replacement_requirements` | 연산자에 맞는 요구값 조합만 허용 | 미정 |
| `part_specifications` | 최소·대표·최대·텍스트 값의 유효 조합 | 미정 |
| `candidate_evaluations` | 합의된 5종 판정 코드만 허용 | 코드 미정 |
| 전체 FK | 삭제 시 CASCADE, RESTRICT 또는 보존 정책 | 미정 |

## 8. 라이브러리 관리 테이블

다음 테이블은 `langgraph-checkpoint-postgres`의 `PostgresSaver` 또는 `PostgresStore`가 생성하고 관리합니다. 애플리케이션 Migration에서 직접 생성하거나 컬럼을 수정하지 않습니다.

| 테이블 | 관리 주체 | 용도 |
|---|---|---|
| `checkpoints` | `PostgresSaver` | thread별 그래프 체크포인트 |
| `checkpoint_blobs` | `PostgresSaver` | 체크포인트 채널 값 |
| `checkpoint_writes` | `PostgresSaver` | 재개에 사용하는 중간 쓰기 |
| `checkpoint_migrations` | `PostgresSaver` | 체크포인트 스키마 버전 |
| `store` | `PostgresStore` | 사용자별 장기 기억 |
| `store_vectors` | `PostgresStore` | 장기 기억 임베딩. 현재 pgvector 범위에서는 제외 |
| `store_migrations` | `PostgresStore` | Store 스키마 버전 |
| `vector_migrations` | `PostgresStore` | Store 벡터 스키마 버전 |

## 9. 추가 검토 영역

재료가 부족한 항목은 임의로 확정하지 않고 아래 결정 목록에서 관리합니다.

| ID | 미정 항목 | 현재 확인된 내용 | 필요한 결정 | 영향 범위 |
|---|---|---|---|---|
| A-01 | 로그인 방식 | 사용자별 대화와 기억 분리가 필요함 | 로컬 비밀번호, 외부 인증 또는 데모 전용 인증 중 선택 | `users`, `backend/auth.py` |
| A-02 | 사용자 ID 형식 | `backend/memory.py`는 문자열 형태의 사용자 ID를 받을 수 있음 | DB PK를 `BIGINT`, UUID 또는 외부 인증 ID로 사용할지 결정 | 전체 사용자 FK |
| A-03 | 회로 원문 저장 위치 | KiCad 넷리스트 입력과 재현이 필요함 | DB `TEXT` 저장 또는 파일·오브젝트 저장소 사용 | `circuits` |
| A-04 | 파일 크기·보존 정책 | 제한이 문서에 없음 | 최대 업로드 크기, 삭제 및 보존 기간 결정 | `circuits`, API |
| A-05 | 부품 분류 코드 | MVP가 다이오드라는 범위만 확정 | 제너·쇼트키·정류 등 코드 목록 결정 | `parts` |
| A-06 | 역할 코드 | 회로 역할 설명은 필요하지만 코드 목록은 없음 | 역극성 보호, 클램프 등 역할 코드와 규칙 파일 연결 결정 | `analysis_runs` |
| A-07 | 사양 파라미터 코드 | 숫자와 단위 비교는 `backend/judge/`에서 수행 | `reverse_voltage` 등 표준 코드 목록 결정 | `part_specifications`, `replacement_requirements` |
| A-08 | 단위 표준 | `μ`가 `m`으로 깨지는 사례가 확인됨 | 원본 단위, 정규화 단위 및 변환 규칙 결정 | 부품 사양, 대체 조건 |
| A-09 | 대체 조건 연산자 | 조건 비교가 필요함 | 허용 연산자와 값 조합 결정 | `replacement_requirements` |
| A-10 | 대체 판정 코드 | 화면 표기 5종만 확정 | DB 영문 코드와 CHECK 또는 코드 테이블 사용 여부 결정 | `candidate_evaluations`, `SPEC.md` 3절 |
| A-11 | 분석 상태 코드 | 승인 대기와 완료 흐름은 있음 | 상태 목록과 상태 전이 규칙 결정 | `analysis_runs` |
| A-12 | 견적 저장 정책 | 사람 승인 후에만 저장함 | 한 분석당 견적 1건 또는 여러 버전 허용 여부 결정 | `quotes` |
| A-13 | 승인 감사 이력 | 저장 전 사람 승인이 필요함 | `approved_by`, `approved_at`만 둘지 별도 `quote_approvals`를 둘지 결정 | `quotes`, 추가 테이블 가능 |
| A-14 | 가격과 통화 | 실시간 가격·재고는 현재 범위 밖이며 데모 응답 사용 | 통화, 소수 자릿수, 가격 기준 시각과 출처 결정 | `quotes`, `quote_items` |
| A-15 | 견적 항목 중복 컬럼 | `quote_items.part_id`는 판정에서 유도 가능 | 승인 시점 스냅샷으로 중복 저장할지 결정 | `quote_items` |
| A-16 | 판정·규칙 버전 | 개선 전후 평가 재현이 필요함 | 규칙 파일과 코드의 버전 식별 방법 결정 | `analysis_runs` |
| A-17 | 인용 대상 범위 | 판정마다 인용하는 것은 확정 | 회로 역할과 대체 조건에도 별도 인용 연결이 필요한지 결정 | `evidence_citations` 또는 연결 테이블 |
| A-18 | 삭제 정책 | 사용자별 데이터와 평가 재현 자료가 존재함 | FK별 `CASCADE`, `RESTRICT`, 논리 삭제 정책 결정 | 전체 테이블 |
| A-19 | pgvector 구조 | 이번 정의서에서 제외 | 임베딩 모델 확정 후 차원, 거리 함수, 인덱스 결정 | 향후 RAG Migration |
| A-20 | 승인 사례 장기 기억 | 승인된 판정·견적 사례를 다음 판정에서 보여 줌 | 업무 테이블 조회와 `PostgresStore` 기억의 역할 경계 결정 | `quotes`, 판정, Store |

## 10. 향후 추가 가능 영역

다음 항목은 현재 MVP 범위에 바로 넣지 않습니다. 요구사항이 확정되면 별도 테이블 또는 컬럼으로 추가합니다.

- 견적 승인·반려 이력 `quote_approvals`
- 판정 수정 및 기억 정정 이력
- 실시간 가격과 재고 스냅샷
- Mouser API 요청·응답 이력
- 제조사 마스터 테이블
- 부품 패키지 마스터 테이블
- 주문과 결제
- 임베딩과 `pgvector` 인덱스

## 11. 다음 단계 진입 조건

다음 항목을 팀에서 검토한 뒤 ERD를 작성합니다.

1. 핵심 테이블 13개의 포함 여부가 합의됨
2. A-01부터 A-20 중 ERD 관계에 영향을 주는 항목이 결정됨
3. 테이블별 PK와 FK 관계가 승인됨
4. 중복 저장을 허용할 스냅샷 컬럼이 결정됨
5. 판정 코드, 역할 코드, 사양 코드의 관리 방법이 결정됨

ERD 승인 후에 자료형, 기본값, CHECK, FK 삭제 정책을 확정하고 Migration SQL을 작성합니다.
