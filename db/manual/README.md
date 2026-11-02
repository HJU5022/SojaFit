# db/manual

## 역할
- 이 폴더: Compose 초기화가 자동 실행하지 않는 SQL을 둡니다. Postgres 이미지는 `db/` 바로 아래 파일만 실행하고 하위 폴더는 건너뜁니다.
- 넣는 것: 검토 중인 마이그레이션 초안, 복제 DB에서 손으로 실행하는 전환 SQL.
- 넣지 않는 것: 새 볼륨에서 자동 실행할 초기화 SQL(`db/`에 세 자리 번호로).
- 담당: 서비스·운영 (RAG 저장 형식 SQL은 검색·데이터)

## 파일
- `004_create_business_tables.sql.draft` — 나머지 업무 테이블 11개의 초안(Migration 1 초안). 코퍼스·인증 테이블을 참조함. 적용할 때는 `db/`의 다음 번호로 옮깁니다
- `halfvec.sql.manual` — 백업을 확보한 복제 DB에서 명시적으로 실행하는 halfvec(1536) 전환·HNSW 제거(재생성 없음). 기본 vector 유지. 역변환으로 정밀도 복구 불가
