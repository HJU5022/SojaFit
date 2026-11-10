# verify_chain

## 역할
- 이 폴더: 새 DB 초기화 체인(`db/000~029`)이 운영 이전 SQL과 같은 구조를 만드는지 일회용 도커 컨테이너로 확인하는 스크립트를 둡니다. 운영 DB에는 접속하지 않습니다.
- 넣는 것: 구조 비교 스크립트. 비교 도구(`db/redesign/verify/lib/rd_struct.py`)와 표본 데이터는 `db/redesign/verify/`의 것을 씁니다.
- 넣지 않는 것: 초기화 SQL(`db/`), 운영 이전 SQL(`db/redesign/to-be/sql/`), 시험(`tests/`).
- 담당: 서비스·운영

## 파일
- `VERIFY_CHAIN.md` — 이 문서
- `verify_chain.sh` — 현재 구조(`db/000~026`)에 운영 이전 SQL(expand → contract P1 → P2 → 2b)을 적용한 결과와 `db/*.sql` 새 체인의 구조 차이가 0줄인지, 되돌리기(B2 → B1 → A) 뒤 처음 구조와 차이가 0줄인지 확인합니다. 저장소 루트에서 `bash scripts/db/verify_chain/verify_chain.sh pgvector/pgvector:pg16 rd-schema-db16 55450`(Postgres 17은 `pg17`, 포트 55454). 출력 폴더는 `OUT`, 파이썬은 `PY`로 바꿉니다. 컨테이너는 끝나면 지웁니다
