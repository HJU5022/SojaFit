# SojaFit DB 테이블 정의서

## 1. 문서 목적

이 문서는 SojaFit의 업무 데이터를 PostgreSQL에 저장하기 위한 테이블 정의서입니다. 다음 단계에서 이 문서를 기준으로 ERD를 작성하고, ERD 검토가 끝난 뒤 Migration SQL을 작성합니다.

Migration SQL이 생기면 열의 정본은 SQL입니다(`db/ERD.md` 기본 규칙). 그때 이 문서의 표 설명은 `db/ERD.md`로 옮기고 이 문서는 지웁니다.

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
- 후보 판정의 대체 조건별 비교 결과
- 승인 후 저장되는 견적서
- RAG 원문 문서와 일반 텍스트 청크 메타데이터
- 청크 임베딩 표와 벡터 인덱스(`pgvector`). 벡터 차원은 임베딩 모델을 정한 뒤 채웁니다

### 제외

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

`가정` 항목은 Migration 작성자가 적힌 기본값으로 반영하고, 바꾸면 같은 PR에서 이 문서를 고칩니다. `미정` 항목은 결정한 뒤 반영합니다. 결정 내용은 9절에 있습니다.

### 3.2 공통 규칙 초안

- 테이블명과 컬럼명은 영문 `snake_case`를 사용합니다.
- 애플리케이션이 생성하는 주요 테이블의 PK는 `BIGINT`를 사용합니다. 자동 증가 방식은 Migration 단계에서 결정합니다.
- 날짜와 시각은 `TIMESTAMPTZ`를 사용하고 UTC로 저장하는 것을 가정합니다.
- 금액은 부동소수점 오차를 피하기 위해 `NUMERIC`을 사용합니다.
- 측정값은 원본 단위와 정규화된 단위를 구분할 수 있어야 합니다.
- 원본 문서, 회로 파일 및 판정 결과는 재현을 위해 버전 또는 해시를 남깁니다.
- `created_at`, `updated_at`의 자동 갱신 방식은 Migration 단계에서 결정합니다.
- 코드 값(부품 분류, 회로 역할, 사양, 비교 연산자, 판정, 상태)은 영문 대문자 `SNAKE_CASE`로 쓰고 CHECK 제약으로 허용 값을 제한합니다. 코드 표는 따로 두지 않습니다.
- 모든 FK의 삭제 동작은 `RESTRICT`입니다. MVP에는 사용자 데이터 삭제 기능이 없고, 코퍼스 문서는 `source_documents.retired_at`으로 논리 삭제합니다(A-18).
- 벡터 열 타입은 스키마 이름 없이 `vector(N)`으로 씁니다. 확장은 로컬 compose에서는 `public`, Supabase에서는 `extensions` 스키마에 설치됩니다.
- Migration은 번호를 붙여 계속 추가하고, 이미 적용한 파일은 고치지 않습니다. 로컬 compose와 Supabase에 같은 방법으로 적용하고 적용 이력을 남깁니다.

## 4. 테이블 목록

| 구분 | 논리명 | 물리명 | 역할 | 상태 |
|---|---|---|---|---|
| 사용자 | 사용자 | `users` | 로그인 사용자와 승인자를 식별 | 확정 |
| 회로 | 회로 | `circuits` | 업로드한 KiCad 넷리스트와 파일 메타데이터 저장 | 확정 |
| 분석 | 분석 실행 | `analysis_runs` | 특정 회로 부품에 대한 한 번의 대체 분석 저장 | 확정 |
| 부품 | 부품 | `parts` | 원본 부품과 후보 부품의 기본정보 저장 | 확정 |
| 부품 | 부품 사양 | `part_specifications` | 데이터시트에서 추출한 구조화된 사양 저장 | 확정 |
| 분석 | 대체 조건 | `replacement_requirements` | 회로 역할에서 도출한 필수·선택 조건 저장 | 확정 |
| 분석 | 후보 판정 | `candidate_evaluations` | 분석별 후보 부품의 5종 판정 저장 | 확정 |
| 분석 | 조건별 비교 | `requirement_checks` | 후보 판정마다 대체 조건 하나씩의 비교 결과 저장 | 확정 |
| 근거 | 출처 문서 | `source_documents` | 데이터시트와 공개 문서의 출처·버전 저장 | 확정 |
| 근거 | 문서 청크 | `document_chunks` | 검색 가능한 일반 텍스트 청크와 위치 저장 | 확정 |
| 근거 | 청크 임베딩 | `chunk_embeddings` | 청크의 임베딩 벡터 저장 | 차원 미정 |
| 근거 | 부품 문서 연결 | `part_documents` | 부품과 해당 데이터시트 연결 | 가정 |
| 근거 | 판정 인용 | `evidence_citations` | 후보 판정에 사용한 페이지·표·행 근거 저장 | 확정 |
| 견적 | 견적서 | `quotes` | 사람 승인 후 확정된 견적서 저장 | 확정 |
| 견적 | 견적 항목 | `quote_items` | 견적서에 포함된 부품·수량·가격 저장 | 확정 |

## 5. 테이블 상세 정의

### 5.1 `users` — 사용자

로그인 사용자를 식별하고 사용자별 회로, 분석, 기억 및 승인을 분리합니다. 로그인은 아이디·비밀번호를 직접 구현하고, 평가용 데모 계정 2개는 `db/` SQL로 비밀번호 해시와 함께 적재합니다(A-01). LangGraph `thread_id`와 Store namespace에는 `str(users.id)`를 씁니다(A-02).

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 사용자 ID | `BIGINT` | N | PK | 내부 사용자 식별자 | 확정 |
| `login_id` | 로그인 ID | `VARCHAR(100)` | N | UNIQUE | 사용자가 로그인할 때 사용하는 식별자 | 확정 |
| `password_hash` | 비밀번호 해시 | `VARCHAR(255)` | N |  | 비밀번호 해시. 평문 비밀번호는 저장하지 않음 | 확정 |
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
| `netlist_format` | 넷리스트 형식 | `VARCHAR(50)` | N | CHECK: `KICAD_NET` | KiCad `.net` 넷리스트(평가·시연 회로 `data/circuits/`와 같은 형식) | 가정 |
| `netlist_content` | 넷리스트 원문 | `TEXT` | N | 업로드 최대 1MB(API에서 검증) | 분석 재현에 사용하는 원본 내용. 파일 저장소는 쓰지 않음(A-03·A-04) | 확정 |
| `content_sha256` | 콘텐츠 해시 | `CHAR(64)` | N | 인덱스. UNIQUE 아님(같은 파일을 다시 올려도 됨) | 동일 입력 확인과 재현에 사용하는 SHA-256 | 확정 |
| `created_at` | 등록 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 회로 등록 시각 | 확정 |
| `updated_at` | 수정 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 회로 정보 수정 시각 | 가정 |

### 5.3 `parts` — 부품

원본 부품과 대체 후보 부품을 같은 부품 목록에서 관리합니다. 원본인지 후보인지는 분석 안에서의 역할이므로 이 테이블에 고정하지 않습니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 부품 ID | `BIGINT` | N | PK | 부품 식별자 | 확정 |
| `manufacturer` | 제조사 | `VARCHAR(150)` | N | 복합 UNIQUE 후보 | 제조사명 | 확정 |
| `part_number` | 품번 | `VARCHAR(150)` | N | 복합 UNIQUE 후보 | 제조사가 부여한 품번 | 확정 |
| `category_code` | 부품 분류 코드 | `VARCHAR(50)` | N | CHECK: `RECTIFIER`, `SCHOTTKY`, `ZENER`, `TVS`, `ESD`, `SWITCHING`, `SIC_SCHOTTKY` | MVP 다이오드 분류(A-05) | 확정 |
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
| `document_key` | 문서 키 | `VARCHAR(200)` | N | UNIQUE | manifest(`data/DATA.md`의 형식)의 `doc_id`와 같은 값 | 확정 |
| `document_type` | 문서 종류 | `VARCHAR(50)` | N | CHECK: `DATASHEET`, `PUBLIC_DOC` | 제조사 데이터시트 또는 공개 문서 | 확정 |
| `title` | 문서 제목 | `VARCHAR(500)` | N |  | 문서 제목 | 확정 |
| `publisher` | 발행처 | `VARCHAR(200)` | N |  | 제조사 또는 공개 문서 발행처 | 확정 |
| `source_url` | 원본 URL | `TEXT` | N |  | 문서 원본 위치 | 확정 |
| `revision` | 문서 개정 정보 | `VARCHAR(100)` | Y |  | 발행일, 버전 또는 revision | 확정 |
| `license_text` | 이용 조건 | `TEXT` | Y |  | 라이선스와 재배포 조건 요약 | 확정 |
| `file_sha256` | 파일 해시 | `CHAR(64)` | N | UNIQUE | 실제 수집 파일의 SHA-256 | 확정 |
| `corpus_version` | 코퍼스 버전 | `VARCHAR(100)` | N |  | 해당 문서가 포함된 코퍼스 버전 | 확정 |
| `collected_at` | 수집 시각 | `TIMESTAMPTZ` | N |  | 원본을 수집한 시각 | 확정 |
| `parser` | 파서 | `VARCHAR(50)` | N |  | manifest의 `parser`. 원문을 텍스트로 바꾼 방식 | 확정 |
| `chars_original` | 원문 글자 수 | `INTEGER` | N | 0 이상 CHECK | manifest의 `chars_original` | 확정 |
| `chars_kept` | 보존 글자 수 | `INTEGER` | N | 0 이상 CHECK | manifest의 `chars_kept` | 확정 |
| `truncated` | 잘림 여부 | `BOOLEAN` | N |  | manifest의 `truncated`. 원문을 잘라 넣었으면 true | 확정 |
| `retired_at` | 제외 시각 | `TIMESTAMPTZ` | Y |  | 증분 수집에서 사라진 문서를 검색에서 빼는 논리 삭제 시각. 인용 기록은 남김(A-18) | 확정 |
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
| `chunk_index` | 청크 순서 | `INTEGER` | N | 문서 안에서 UNIQUE | 원문 내 청크 순서. 0부터 시작 | 확정 |
| `content` | 청크 본문 | `TEXT` | N |  | 검색과 인용에 사용하는 텍스트 | 확정 |
| `chunk_sha256` | 본문 해시 | `CHAR(64)` | N | 인덱스. UNIQUE 아님 | 본문의 SHA-256. 서로 다른 청크 수(G3)는 이 값의 고유 개수로 셈 | 확정 |
| `page_number` | 페이지 번호 | `INTEGER` | Y | 양수 CHECK 후보 | PDF 기준 페이지 번호 | 확정 |
| `section_name` | 절 이름 | `VARCHAR(500)` | Y |  | 원문 내 절 또는 제목 | 확정 |
| `table_name` | 표 이름 | `VARCHAR(500)` | Y |  | 표에서 추출한 경우 표 이름 | 확정 |
| `row_label` | 행 식별자 | `VARCHAR(500)` | Y |  | 표의 행 이름 또는 항목명 | 확정 |
| `token_count` | 토큰 수 | `INTEGER` | Y | 0 이상 CHECK 후보 | 사용한 토크나이저 기준 토큰 수 | 가정 |
| `chunker_version` | 청커 버전 | `VARCHAR(100)` | N |  | 청크 생성 규칙 또는 코드 버전 | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 청크 생성 시각 | 가정 |

제약조건 초안: `UNIQUE (document_id, chunk_index)`.

### 5.7 `part_specifications` — 부품 사양

데이터시트에서 추출한 숫자 사양과 시험 조건을 구조화해 저장합니다. `backend/judge/`가 LLM 대신 숫자와 단위를 비교할 때 사용하는 데이터입니다. 최소·대표·최대값은 `backend/rag/`의 단위 환산 함수로 SI 기본 단위로 바꿔 저장하고, 원문 표기는 `source_value_text`에 그대로 남깁니다(A-08).

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 부품 사양 ID | `BIGINT` | N | PK | 사양 식별자 | 확정 |
| `part_id` | 부품 ID | `BIGINT` | N | FK → `parts.id` | 사양 대상 부품 | 확정 |
| `document_id` | 출처 문서 ID | `BIGINT` | N | FK → `source_documents.id` | 값을 추출한 데이터시트 | 확정 |
| `parameter_code` | 파라미터 코드 | `VARCHAR(100)` | N | CHECK: `VRRM`, `IF_AV`, `IFSM`, `VF`, `IR`, `TRR`, `VZ`, `PD`, `CJ`, `TJ_MAX` | 표준화된 사양 항목(A-07) | 확정 |
| `symbol` | 데이터시트 기호 | `VARCHAR(50)` | Y |  | 데이터시트에 표시된 `VRRM`, `IF` 등의 기호 | 확정 |
| `minimum_value` | 최소값 | `NUMERIC` | Y |  | 데이터시트 최소값. 정규화 단위로 환산한 값 | 확정 |
| `typical_value` | 대표값 | `NUMERIC` | Y |  | 데이터시트 대표값. 정규화 단위로 환산한 값 | 확정 |
| `maximum_value` | 최대값 | `NUMERIC` | Y |  | 데이터시트 최대값. 정규화 단위로 환산한 값 | 확정 |
| `text_value` | 비수치 값 | `TEXT` | Y |  | 숫자로 표현할 수 없는 사양값 | 가정 |
| `source_value_text` | 원문 표기 | `TEXT` | N |  | 데이터시트에 적힌 그대로의 값과 단위(예: `1.1 V`, `500 μA`). 인용 화면과 단위 깨짐 확인에 사용 | 확정 |
| `source_unit` | 원본 단위 | `VARCHAR(30)` | Y |  | 데이터시트에 표기된 단위 | 확정 |
| `normalized_unit` | 정규화 단위 | `VARCHAR(30)` | Y | CHECK: `V`, `A`, `s`, `W`, `F`, `degC` | SI 기본 단위(A-08) | 확정 |
| `test_condition` | 시험 조건 | `TEXT` | Y |  | 온도, 전류 등 값이 성립하는 조건 | 확정 |
| `page_number` | 페이지 번호 | `INTEGER` | Y |  | 데이터시트 페이지 | 확정 |
| `table_name` | 표 이름 | `VARCHAR(500)` | Y |  | 값이 나온 표 이름 | 확정 |
| `row_label` | 행 식별자 | `VARCHAR(500)` | Y |  | 값이 나온 행 또는 항목명 | 확정 |
| `footnote_text` | 각주 | `TEXT` | Y |  | 값에 적용되는 데이터시트 각주 | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 사양 적재 시각 | 가정 |

최소값, 대표값, 최대값, 비수치 값이 모두 비어 있는 행은 받지 않습니다(CHECK, 가정). 파서 결과에서 이런 행이 꼭 필요하면 이 규칙을 고칩니다.

### 5.8 `analysis_runs` — 분석 실행

사용자가 특정 회로의 특정 부품을 대상으로 수행한 한 번의 대체 분석을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 분석 실행 ID | `BIGINT` | N | PK | 분석 실행 식별자 | 확정 |
| `user_id` | 사용자 ID | `BIGINT` | N | FK → `users.id` | 분석을 요청한 사용자 | 확정 |
| `circuit_id` | 회로 ID | `BIGINT` | N | FK → `circuits.id` | 분석 대상 회로 | 확정 |
| `thread_id` | 그래프 thread ID | `VARCHAR(200)` | N | UNIQUE | 이 분석을 실행한 LangGraph thread. 승인 대기 중인 그래프를 재개할 때 체크포인트를 찾는 열 | 확정 |
| `original_part_id` | 원본 부품 ID | `BIGINT` | Y | FK → `parts.id` | 넷리스트의 원본 품번이 식별된 경우 연결 | 확정 |
| `target_reference` | 교체 대상 참조명 | `VARCHAR(100)` | N |  | `D1`, `D2` 등 회로 내 참조명 | 확정 |
| `role_code` | 회로 역할 코드 | `VARCHAR(100)` | Y | CHECK: `REVERSE_POLARITY`, `RECTIFICATION`, `FLYBACK`, `CLAMP_ESD`, `ZENER_REFERENCE`, `REVERSE_BLOCKING` | 역극성 보호, 정류, 플라이백, 신호 클램프·ESD 보호, 제너 기준 전압, 역류 방지(A-06). 역할을 정하기 전에는 NULL | 확정 |
| `role_description` | 회로 역할 설명 | `TEXT` | Y |  | 사용자에게 보여 주는 역할 설명 | 확정 |
| `status_code` | 분석 상태 | `VARCHAR(30)` | N | CHECK: `RUNNING`, `AWAITING_APPROVAL`, `APPROVED`, `REJECTED`, `FAILED` | `RUNNING` → `AWAITING_APPROVAL` → `APPROVED` 또는 `REJECTED`, 도중 실패는 `FAILED`(A-11) | 확정 |
| `corpus_version` | 코퍼스 버전 | `VARCHAR(100)` | N |  | 검색에 사용한 코퍼스 버전 | 확정 |
| `rule_version` | 판정 규칙 버전 | `VARCHAR(100)` | N |  | 대체 조건 규칙 파일의 SHA-256(A-16) | 확정 |
| `model_name` | 모델 이름 | `VARCHAR(200)` | N |  | 이 분석에 쓴 LLM 모델 이름(A-16) | 확정 |
| `prompt_version` | 프롬프트 버전 | `VARCHAR(100)` | N |  | `backend/prompts/`의 프롬프트 버전(A-16) | 확정 |
| `trace_id` | 트레이스 ID | `VARCHAR(200)` | Y |  | Langfuse 트레이스 ID. 데모 모드에서는 NULL(A-16) | 확정 |
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
| `parameter_code` | 파라미터 코드 | `VARCHAR(100)` | N | `part_specifications.parameter_code`와 같은 CHECK | 후보 사양과 비교할 항목(A-07) | 확정 |
| `comparison_operator` | 비교 연산자 | `VARCHAR(20)` | N | CHECK: `>=`, `<=`, `=`, `BETWEEN`, `IN` | 비교 방식(A-09) | 확정 |
| `required_value` | 요구값 | `NUMERIC` | Y |  | 조건의 첫 번째 수치 | 확정 |
| `secondary_value` | 두 번째 요구값 | `NUMERIC` | Y |  | 범위 조건의 두 번째 수치 | 가정 |
| `required_text` | 비수치 요구값 | `TEXT` | Y |  | 패키지나 재질처럼 문자열로 비교하는 값 | 가정 |
| `unit` | 비교 단위 | `VARCHAR(30)` | Y | `part_specifications.normalized_unit`과 같은 CHECK | 정규화된 비교 단위(A-08) | 확정 |
| `test_condition` | 적용 조건 | `TEXT` | Y |  | 온도, 전류 등 요구값이 적용되는 조건 | 확정 |
| `is_mandatory` | 필수 여부 | `BOOLEAN` | N | 기본값 `true` 가정 | 불충족 시 후보를 탈락시킬 조건인지 표시 | 확정 |
| `rationale` | 도출 이유 | `TEXT` | N |  | 회로 역할에서 이 조건을 도출한 이유 | 확정 |
| `sort_order` | 표시 순서 | `INTEGER` | N | 0 이상 CHECK 후보 | 화면에서 조건을 보여 줄 순서 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 조건 생성 시각 | 가정 |

연산자별 값 조합 CHECK: `BETWEEN`은 `required_value`와 `secondary_value`가 모두 있어야 하고, `IN`은 `required_text`(쉼표로 나눈 목록)가 있어야 하며, `>=`·`<=`는 `required_value`만 씁니다. `=`는 `required_value`와 `required_text` 중 하나만 씁니다(A-09).

### 5.10 `candidate_evaluations` — 후보 판정

분석 실행에서 후보 부품마다 내린 대체 판정과 판정 이유를 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 후보 판정 ID | `BIGINT` | N | PK | 판정 식별자 | 확정 |
| `analysis_run_id` | 분석 실행 ID | `BIGINT` | N | FK → `analysis_runs.id` | 판정이 속한 분석 | 확정 |
| `candidate_part_id` | 후보 부품 ID | `BIGINT` | N | FK → `parts.id` | 판정 대상 후보 부품 | 확정 |
| `verdict_code` | 대체 판정 코드 | `VARCHAR(30)` | N | CHECK: `IDENTICAL`, `SPEC_EQUIVALENT`, `ROLE_SUFFICIENT`, `NOT_SUFFICIENT`, `NOT_VERIFIED` | 동일품, 사양 동등, 역할상 충분, 불충족, 문서로 확인 안 됨. 뜻과 판정 순서는 `SPEC.md` 3절(A-10) | 확정 |
| `reason` | 판정 이유 | `TEXT` | N |  | 조건 비교와 문서 근거를 요약한 설명 | 확정 |
| `board_change_required` | 기판 수정 필요 | `BOOLEAN` | N | 기본값 `false` 가정 | 패키지 차이로 PCB 수정이 필요한지 표시 | 확정 |
| `uncertainty_reason` | 확인 불가 사유 | `TEXT` | Y |  | 화면에 보여 줄 요약. 조건별 이유는 `requirement_checks`에 둠 | 확정 |
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
| `requirement_check_id` | 조건별 비교 ID | `BIGINT` | Y | FK → `requirement_checks.id` | 특정 대체 조건의 근거일 때 연결. 판정 전체의 근거면 NULL(A-17) | 확정 |
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
| `currency_code` | 통화 코드 | `CHAR(3)` | N | ISO 4217. MVP는 `USD` | 가격 표시 통화(A-14) | 확정 |
| `total_amount` | 총 금액 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 견적 총액 스냅샷 | 가정 |
| `approved_at` | 승인 시각 | `TIMESTAMPTZ` | N |  | 사람이 승인한 시각 | 확정 |
| `created_at` | 저장 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 승인된 견적을 DB에 저장한 시각 | 확정 |

한 분석에는 승인된 견적 1건만 둡니다: `UNIQUE (analysis_run_id)`(A-12). 반려 후 다시 하려면 분석을 새로 실행합니다. 승인 이력은 `approved_by_user_id`와 `approved_at`만 두고, 반려 이력 표(`quote_approvals`)는 확장 단계로 미룹니다(A-13).

### 5.13 `quote_items` — 견적 항목

승인된 견적서에 포함된 후보 부품, 수량 및 승인 당시의 가격을 저장합니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 견적 항목 ID | `BIGINT` | N | PK | 견적 항목 식별자 | 확정 |
| `quote_id` | 견적서 ID | `BIGINT` | N | FK → `quotes.id` | 항목이 속한 견적서 | 확정 |
| `candidate_evaluation_id` | 후보 판정 ID | `BIGINT` | N | FK → `candidate_evaluations.id` | 견적 선택의 근거가 된 후보 판정. 견적 대상 부품은 이 판정의 `candidate_part_id`(A-15) | 확정 |
| `quantity` | 수량 | `INTEGER` | N | 1 이상 CHECK 후보 | 견적 수량 | 확정 |
| `unit_price` | 단가 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 승인 당시 단가 | 가정 |
| `line_amount` | 항목 금액 | `NUMERIC(18,4)` | N | 0 이상 CHECK 후보 | 수량과 단가를 반영한 금액 스냅샷 | 가정 |
| `price_source` | 가격 출처 | `VARCHAR(200)` | N |  | MVP는 `demo`(`data/demo/` 가공 가격표). Mouser 연동은 확장(A-14) | 확정 |
| `price_as_of` | 가격 기준 시각 | `TIMESTAMPTZ` | Y |  | 가격표의 기준 시각 | 가정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 견적 항목 생성 시각 | 가정 |

견적 항목은 판정이 `IDENTICAL`, `SPEC_EQUIVALENT`, `ROLE_SUFFICIENT`인 후보만 가리키고, 그 판정은 견적과 같은 분석에 속해야 합니다. 다른 표를 봐야 하는 규칙이라 애플리케이션에서 저장 전에 검증합니다. `NOT_SUFFICIENT`와 `NOT_VERIFIED` 후보는 견적에 넣지 않습니다.

### 5.14 `requirement_checks` — 조건별 비교

후보 판정 하나에서 대체 조건 하나씩을 비교한 결과를 저장합니다. 화면에 "어느 조건이 왜 통과·불충족·확인 안 됨인지"를 보여 주고, 검색 실패 분석에서 이유별로 셀 때 씁니다(A-17). 비교는 `backend/judge/`가 하고, LLM은 비교하지 않습니다.

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `id` | 조건별 비교 ID | `BIGINT` | N | PK | 비교 식별자 | 확정 |
| `candidate_evaluation_id` | 후보 판정 ID | `BIGINT` | N | FK → `candidate_evaluations.id` | 비교가 속한 후보 판정 | 확정 |
| `requirement_id` | 대체 조건 ID | `BIGINT` | N | FK → `replacement_requirements.id` | 비교한 대체 조건 | 확정 |
| `part_specification_id` | 부품 사양 ID | `BIGINT` | Y | FK → `part_specifications.id` | 비교에 쓴 후보 사양 행(쪽·표·행이 여기에 있음). 값을 못 찾았으면 NULL | 확정 |
| `result_code` | 비교 결과 | `VARCHAR(20)` | N | CHECK: `PASS`, `FAIL`, `UNKNOWN` | 조건 충족, 불충족, 확인 안 됨 | 확정 |
| `unknown_reason_code` | 확인 불가 이유 | `VARCHAR(30)` | Y | CHECK: `VALUE_MISSING`, `CONDITION_MISMATCH`, `DOC_NOT_FOUND` | 값이 문서에 없음, 시험 조건이 다름, 데이터시트가 코퍼스에 없음 | 확정 |
| `compared_value` | 비교한 값 | `NUMERIC` | Y |  | judge가 조건과 비교한 후보 값(정규화 단위) | 확정 |
| `compared_text` | 비교한 문자열 | `TEXT` | Y |  | 패키지처럼 문자열로 비교한 값 | 확정 |
| `note` | 설명 | `TEXT` | Y |  | 화면에 보여 줄 한 줄 설명(예: "데이터시트에는 100°C 값만 있음") | 확정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 비교 생성 시각 | 가정 |

제약조건: `UNIQUE (candidate_evaluation_id, requirement_id)`. `result_code = 'UNKNOWN'`일 때만 `unknown_reason_code`가 있어야 합니다(CHECK). 대체 조건이 판정과 같은 분석에 속하는지는 애플리케이션에서 검증합니다.

### 5.15 `chunk_embeddings` — 청크 임베딩

청크마다 임베딩 벡터를 저장합니다. 청크 표와 나눠 두어 임베딩 모델을 바꾸거나 다시 만들 때 `document_chunks`를 건드리지 않습니다(A-19).

| 컬럼 | 논리명 | 자료형 초안 | NULL | 키·제약 초안 | 설명 | 상태 |
|---|---|---|---|---|---|---|
| `chunk_id` | 청크 ID | `BIGINT` | N | PK 일부, FK → `document_chunks.id` | 임베딩한 청크 | 확정 |
| `embedding_model` | 임베딩 모델 | `VARCHAR(200)` | N | PK 일부 | 임베딩에 쓴 모델 이름 | 확정 |
| `embedding` | 임베딩 벡터 | `vector(N)` | N |  | N은 임베딩 모델의 출력 차원. 모델을 정한 뒤 채움 | 미정 |
| `created_at` | 생성 시각 | `TIMESTAMPTZ` | N | 현재 시각 기본값 가정 | 임베딩 생성 시각 | 가정 |

- 거리 함수는 코사인 거리, 인덱스는 HNSW(`vector_cosine_ops`)입니다. `vector` 타입의 HNSW 인덱스는 2,000차원까지 걸 수 있으므로 N은 2,000 이하여야 합니다.
- 현재 RAG 기본 열은 vector(1536)이며, 원본 코퍼스를 유지한 복제 DB에만 `halfvec.sql.manual`로 halfvec(1536) 저장·HNSW 제거 전환을 시험할 수 있습니다. 검색 거리는 float32로 계산합니다. 최종 채택은 동일 코퍼스 품질·전체 DB 용량 실측 후 결정하며 현재 기본값은 바꾸지 않았습니다.
- 메타데이터 필터(문서 종류, 제조사 등)를 같이 걸면 HNSW가 오류 없이 결과를 적게 돌려줄 수 있습니다. 검색 코드에서 `hnsw.ef_search`와 `hnsw.iterative_scan`을 설정합니다.
- 차원이 다른 모델로 바꾸면 `embedding` 열을 새 Migration으로 바꿉니다.
- 이 표와 인덱스는 N이 정해진 뒤 별도 Migration으로 만듭니다(11절).

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
| `candidate_evaluations` | 1:N | `requirement_checks` | 한 판정에서 대체 조건마다 비교 결과를 남김 |
| `replacement_requirements` | 1:N | `requirement_checks` | 한 조건을 여러 후보와 비교함 |
| `part_specifications` | 1:N | `requirement_checks` | 한 사양 행이 여러 비교의 근거가 될 수 있음 |
| `requirement_checks` | 1:N | `evidence_citations` | 한 조건 비교에 여러 인용을 붙일 수 있음 |
| `document_chunks` | 1:N | `chunk_embeddings` | 한 청크를 모델마다 임베딩할 수 있음 |
| `analysis_runs` | 1:1 | `quotes` | 한 분석에 승인된 견적은 1건 |
| `quotes` | 1:N | `quote_items` | 한 견적서에 여러 부품 항목을 넣을 수 있음 |
| `candidate_evaluations` | 1:N | `quote_items` | 견적 항목의 부품은 판정의 후보 부품 |

## 7. 주요 제약조건 초안

| 대상 | 제약조건 | 상태 |
|---|---|---|
| `parts` | 제조사와 품번의 조합 중복 금지 | 가정 |
| `source_documents` | 문서 키 중복 금지 | 확정 |
| `source_documents` | 같은 파일 해시 중복 금지(한 파일이 여러 부품을 다루면 `part_documents`로 연결) | 가정 |
| `part_documents` | 같은 부품과 문서 연결 중복 금지 | 확정 |
| `document_chunks` | 같은 문서에서 청크 순번 중복 금지 | 확정 |
| `analysis_runs` | `thread_id` 중복 금지 | 확정 |
| `candidate_evaluations` | 같은 분석에서 후보 부품 중복 판정 금지 | 확정 |
| `requirement_checks` | 같은 판정에서 같은 조건 중복 비교 금지, `UNKNOWN`일 때만 확인 불가 이유 | 확정 |
| `chunk_embeddings` | 같은 청크·모델 조합 중복 금지 | 확정 |
| `quotes` | 한 분석에 견적 1건 | 확정 |
| `quote_items` | 수량은 1 이상 | 확정 |
| `quotes`, `quote_items` | 금액은 0 이상 | 확정 |
| `quote_items` | 판정이 동일품·사양 동등·역할상 충분인 후보만(애플리케이션 검증) | 확정 |
| `replacement_requirements` | 연산자에 맞는 요구값 조합만 허용 | 확정 |
| `part_specifications` | 최소·대표·최대·텍스트 값 중 하나 이상 있어야 함 | 가정 |
| 코드 열 전체 | 3.2의 코드 목록만 허용(CHECK) | 확정 |
| 전체 FK | 삭제는 `RESTRICT`, 코퍼스 문서는 논리 삭제 | 확정 |

## 8. 라이브러리 관리 테이블

다음 테이블은 `langgraph-checkpoint-postgres`의 `PostgresSaver` 또는 `PostgresStore`가 생성하고 관리합니다. 애플리케이션 Migration에서 직접 생성하거나 컬럼을 수정하지 않습니다.

| 테이블 | 관리 주체 | 용도 |
|---|---|---|
| `checkpoints` | `PostgresSaver` | thread별 그래프 체크포인트 |
| `checkpoint_blobs` | `PostgresSaver` | 체크포인트 채널 값 |
| `checkpoint_writes` | `PostgresSaver` | 재개에 사용하는 중간 쓰기 |
| `checkpoint_migrations` | `PostgresSaver` | 체크포인트 스키마 버전 |
| `store` | `PostgresStore` | 사용자별 장기 기억 |
| `store_vectors` | `PostgresStore` | 장기 기억 임베딩. Store에 의미 검색 인덱스를 설정할 때만 생기며, MVP는 설정하지 않음(A-20) |
| `store_migrations` | `PostgresStore` | Store 스키마 버전 |
| `vector_migrations` | `PostgresStore` | Store 벡터 스키마 버전 |

## 9. 결정 기록

초안의 추가 검토 항목 A-01~A-20은 2026-10-30에 조장(하정운)이 아래와 같이 정했습니다. A-19의 벡터 차원만 임베딩 모델을 정한 뒤 채웁니다.

| ID | 항목 | 결정 | 반영한 곳 |
|---|---|---|---|
| A-01 | 로그인 방식 | 아이디·비밀번호 직접 구현. 비밀번호는 해시로 저장하고 데모 계정 2개는 `db/` SQL로 적재 | `users`, `backend/auth.py` |
| A-02 | 사용자 ID 형식 | `users.id`는 `BIGINT`. LangGraph `thread_id`와 Store namespace에는 `str(users.id)` | 사용자 FK, `backend/memory.py` |
| A-03 | 회로 원문 저장 위치 | DB `TEXT` | `circuits.netlist_content` |
| A-04 | 파일 크기·보존 | 업로드 최대 1MB(API에서 검증), MVP에는 삭제 기능 없음 | `circuits`, API |
| A-05 | 부품 분류 코드 | `RECTIFIER`, `SCHOTTKY`, `ZENER`, `TVS`, `ESD`, `SWITCHING`, `SIC_SCHOTTKY` | `parts.category_code` |
| A-06 | 역할 코드 | `REVERSE_POLARITY`, `RECTIFICATION`, `FLYBACK`, `CLAMP_ESD`, `ZENER_REFERENCE`, `REVERSE_BLOCKING`. 역할별 필수 조건은 규칙 파일(`SPEC.md` 5절) | `analysis_runs.role_code` |
| A-07 | 사양 파라미터 코드 | `VRRM`, `IF_AV`, `IFSM`, `VF`, `IR`, `TRR`, `VZ`, `PD`, `CJ`, `TJ_MAX` | `part_specifications`, `replacement_requirements` |
| A-08 | 단위 표준 | SI 기본 단위(`V`, `A`, `s`, `W`, `F`, `degC`)로 환산해 저장하고 원문 표기는 `source_value_text`에 보존. 환산은 `backend/rag/`, 비교는 `backend/judge/` | 부품 사양, 대체 조건 |
| A-09 | 대체 조건 연산자 | `>=`, `<=`, `=`, `BETWEEN`, `IN`과 5.9의 값 조합 | `replacement_requirements` |
| A-10 | 대체 판정 코드 | `IDENTICAL`, `SPEC_EQUIVALENT`, `ROLE_SUFFICIENT`, `NOT_SUFFICIENT`, `NOT_VERIFIED`. CHECK로 제한하고 코드 표는 두지 않음 | `candidate_evaluations`, `SPEC.md` 3절 |
| A-11 | 분석 상태 코드 | `RUNNING` → `AWAITING_APPROVAL` → `APPROVED` 또는 `REJECTED`, 실패는 `FAILED` | `analysis_runs` |
| A-12 | 견적 저장 정책 | 분석 1건당 승인된 견적 1건 | `quotes` |
| A-13 | 승인 감사 이력 | `approved_by_user_id`, `approved_at`만 둠. `quote_approvals`는 확장 | `quotes` |
| A-14 | 가격과 통화 | `data/demo/` 가공 가격표, `USD`, `price_source = 'demo'` | `quotes`, `quote_items` |
| A-15 | 견적 항목 중복 컬럼 | `quote_items.part_id`를 빼고 판정의 후보 부품을 씀 | `quote_items` |
| A-16 | 판정·규칙 버전 | `rule_version`은 규칙 파일 SHA-256. `model_name`, `prompt_version`, `trace_id` 열 추가 | `analysis_runs` |
| A-17 | 인용 대상 범위 | 조건별 비교 표 `requirement_checks`를 두고 인용을 조건에도 연결. 역할 설명의 인용은 MVP에서 제외 | `requirement_checks`, `evidence_citations` |
| A-18 | 삭제 정책 | 모든 FK `RESTRICT`. 코퍼스 문서는 `retired_at`으로 논리 삭제 | 전체 테이블 |
| A-19 | pgvector 구조 | `chunk_embeddings` 표, 코사인 거리, HNSW. 벡터 차원 N은 임베딩 모델을 정한 뒤 채움 | `chunk_embeddings` |
| A-20 | 승인 사례 장기 기억 | 원본은 업무 표(`quotes`, `candidate_evaluations`). Store에는 사례 요약과 `quote_id`·`analysis_run_id` 참조만 두고 의미 검색 인덱스는 쓰지 않음 | Store, `quotes` |

검토하며 더한 열: `analysis_runs.thread_id`(승인 재개), `document_chunks.chunk_sha256`(G3 서로 다른 청크 수), `source_documents`의 manifest 열(`parser`, `chars_original`, `chars_kept`, `truncated`).

## 10. 향후 추가 가능 영역

다음 항목은 현재 MVP 범위에 바로 넣지 않습니다. 요구사항이 확정되면 별도 테이블 또는 컬럼으로 추가합니다.

- 견적 승인·반려 이력 `quote_approvals`
- 판정 수정 및 기억 정정 이력
- 실시간 가격과 재고 스냅샷
- Mouser API 요청·응답 이력
- 제조사 마스터 테이블
- 부품 패키지 마스터 테이블
- 주문과 결제

## 11. 다음 단계

아래 분할은 기존 계획이다. PR #17 코퍼스 SQL이 문서·청크·임베딩 표를 먼저 생성하므로, Migration 1 초안은 문서·청크·사용자 표를 제외한 11개 업무 표를 대상으로 조정했다. 코퍼스 SQL 반영과 실행 순서·이력 방식은 확정 전이다.

1. 이 정의서로 `db/ERD.md`에 표 관계도(mermaid `erDiagram`)를 그립니다.
2. Migration은 두 번으로 나눕니다.

| 순서 | 내용 | 시작 조건 |
|---|---|---|
| Migration 1 | 5.1~5.14의 업무 표 14개와 CHECK·FK·UNIQUE | ERD 승인 |
| Migration 2 | 5.15 `chunk_embeddings`와 HNSW 인덱스 | 임베딩 모델과 벡터 차원 N 결정 |

3. 데모 계정 2개 적재는 `db/DB.md`의 순서(스키마 → 데이터 → 인덱스 → 데모 계정)를 따릅니다.
4. 개발 중 표나 열이 더 필요하면 Migration 3부터 번호를 이어 추가하고, 이미 적용한 Migration은 고치지 않습니다.
5. Migration 1을 넣는 PR에서 이 문서의 표 설명을 `db/ERD.md`로 옮기고 이 문서를 지웁니다.
