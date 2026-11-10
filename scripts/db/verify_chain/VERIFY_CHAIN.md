# verify_chain

## 역할
- 이 폴더: 새 DB 기준선(`db/*.sql`: 코퍼스 + `020_service_baseline.sql` + `026`)이 옛 체인(`db/legacy/` 포함)에 운영 이전 SQL을 적용한 결과와 같은 구조를 만드는지 일회용 도커 컨테이너로 확인하는 스크립트를 둡니다. 운영 DB에는 접속하지 않습니다.
- 넣는 것: 구조 비교 스크립트. 비교 도구(`db/redesign/verify/lib/rd_struct.py`)와 표본 데이터는 `db/redesign/verify/`의 것을 씁니다.
- 넣지 않는 것: 초기화 SQL(`db/`), 운영 이전 SQL(`db/migrations/`), 시험(`tests/`).
- 담당: 서비스·운영

## 파일
- `VERIFY_CHAIN.md` — 이 문서
- `verify_chain.sh` — 옛 체인 000~026(`db/legacy/` + `db/`)에 운영 이전 SQL(`db/migrations/`: expand → contract P1 → P2 → 2b)을 적용한 결과와 `db/*.sql` 새 기준선의 구조 차이가 0줄인지, 옛 증분 체인 000~029 전체와도 0줄인지, 되돌리기(B2b → B2 → B1 → A) 뒤 처음 구조(RLS · 함수 권한 줄 포함)와 차이가 0줄인지, 되돌린 DB와 새 기준선 DB 둘 다의 RLS · PUBLIC 표 권한 · 함수 PUBLIC 실행을 확인하고(하나라도 있으면 exit 1), 코퍼스 4표를 배포된 코드(716c6d6)의 `db/*.sql`이 만든 표와 `pg_dump -s` 표별로 대조합니다(`CORPUS_REF`로 바꿈, git 저장소 안에서만). 저장소 루트에서 `bash scripts/db/verify_chain/verify_chain.sh pgvector/pgvector:pg16 rd-schema-db16 55450`(Postgres 17은 `pg17`, 포트 55454). 출력 폴더는 `OUT`, 파이썬은 `PY`로 바꿉니다. 컨테이너는 끝나면 지웁니다
