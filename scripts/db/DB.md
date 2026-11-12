# db

## 역할
- 이 폴더: 운영 DB에 손으로 하는 작업 스크립트를 둡니다. 저장소 루트에서 `DATABASE_URL`을 준 채 실행합니다. 출력은 숫자와 상태뿐이고 접속 문자열은 찍지 않습니다.
- 넣는 것: voyage-4-large 검색 설정을 운영 DB에 올리는 점검 · 마이그레이션 · 검증 스크립트.
- 넣지 않는 것: 초기화 SQL(`db/`), 코퍼스 적재(`backend/rag/pipeline/ingest.py`), 검색 품질 측정(`evals/runners/`), 테스트(`tests/rag/`).
- 담당: 서비스·운영

## 파일
- `DB.md` — 이 문서
- `gen_schema_docs.py` — 실제 DB(`DATABASE_URL`, 읽기 전용)의 서비스 표 24개를 `pg_catalog`에서 읽어 `db/schema/erd.md`(mermaid)와 `db/schema/table-definition.md`를 만든다. 표 목적 · 칸 의미는 스크립트의 `TABLES`에 있고 DB와 목록이 다르면 멈춘다. `--out-dir DIR`로 다른 곳에 쓰고 `--check`는 쓰지 않고 문서가 DB와 같은지만 본다(다르면 종료 코드 1). 코퍼스 · LangGraph 표는 이름만 적는다. 시험은 `tests/db/`. `uv run python scripts/db/gen_schema_docs.py`
- `verify_chain/` — 새 DB 기준선(`db/020_service_baseline.sql`)이 옛 체인 + 운영 이전 SQL 결과와 같은 구조인지, 되돌리기 뒤 처음 구조로 돌아오는지 일회용 컨테이너로 확인. [VERIFY_CHAIN.md](verify_chain/VERIFY_CHAIN.md)
- `verify_redesign/` — 운영 이전 SQL(`db/migrations/`)과 기준선을 일회용 Postgres 16 · 17에서 검증하는 셸 스크립트(`run_all.sh`), 보조 코드(`lib/`), 표본 데이터(`sql/`). 운영 DB에는 접속하지 않는다. 설계 문서는 `docs/research/db-redesign/`
- `voyage_rollout.py` — `check`(읽기 전용: 열 형식 · DB 크기 · 모델별 행 수 · HNSW · filenode, 적재 뒤 예상 크기와 STOP), `migrate`(check → `db/008` 한 트랜잭션 → filenode 전후 · 형식 · 색인 · 행 수 · 옛 질의 모양 확인, 실패하면 롤백), `verify`(적재 뒤 행 수 대조와 무작위 5건 코사인 ≥ 0.999). `uv run python scripts/db/voyage_rollout.py check|migrate|verify [벡터 폴더]`
