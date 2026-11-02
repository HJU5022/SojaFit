# db

## 역할
- 이 폴더: Compose가 DB 컨테이너를 처음 띄울 때 이름순으로 실행하는 초기화 SQL을 둡니다. 확장과 코퍼스 SQL을 업무 스키마보다 먼저 실행해야 합니다. 실행 파일의 번호는 코퍼스 SQL 반영 후 확정합니다.
- 넣는 것: 확장과 스키마, 스냅샷 데이터 적재, 인덱스 생성, 데모 계정 2개(비밀번호는 해시). 순서는 스키마 → 데이터 → 인덱스 → 데모 계정입니다.
- 넣지 않는 것: 평가용 계정 비밀번호(강사에게 따로 제출), 원본 문서(`data/corpus/`).
- 담당: 서비스·운영 (RAG 스키마·스냅샷·인덱스 SQL은 검색·데이터)

## 주의
SQL은 db 볼륨이 비어 있을 때만 실행됩니다. SQL을 바꾼 뒤에는 `docker compose down -v`로 볼륨을 지우고 다시 띄웁니다.

## 파일
- `000_init.sql` — pgvector 확장 생성
- `001_create_business_tables.sql.draft` — Migration 1 업무 표 초안. PR #17의 `02_rag_corpus.sql`을 먼저 반영·실행해야 하며, 자동 실행 전 파일 순서와 이력 방식을 확정해야 함
- `02_rag_corpus.sql` — RAG 코퍼스 표 3개(`source_documents`, `document_chunks`, `chunk_embeddings` `vector(1536)`)와 HNSW 인덱스. 이미 뜬 DB와 Supabase에는 `psql -f`로 따로 적용
- `halfvec.sql.manual` — 백업을 확보한 복제 DB에서 명시적으로 실행하는 halfvec(1536) 전환·코사인 HNSW 재생성. 자동 초기화 제외, 기본 vector 유지. 역변환으로 정밀도 복구 불가
- `ERD.md` — 표 관계도와 표마다 하는 일. SQL로 표를 바꾸면 같은 PR에서 고칩니다
- `table-definition.md` — 업무 테이블의 컬럼, 관계, 제약조건과 미정 항목을 정리한 정의서 초안
