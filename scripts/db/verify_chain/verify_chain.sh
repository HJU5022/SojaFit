#!/bin/bash
# 새 DB 초기화 체인(db/000~029)이 운영 이전 SQL(expand → contract)을 현재 구조에 적용한 결과와 같은 구조인지, 되돌리기 뒤 처음 구조로 돌아오는지 확인한다.
# 일회용 도커 컨테이너만 쓴다(운영 DB 접속 없음). 사용(레포 루트): bash scripts/db/verify_chain/verify_chain.sh <이미지> <컨테이너 이름> <포트>
#   예: bash scripts/db/verify_chain/verify_chain.sh pgvector/pgvector:pg16 rd-schema-db16 55450
# [왜] 새 체인과 운영 이전 SQL이 따로 자라면 새 DB와 운영 DB의 구조가 갈라진다. 이 비교가 0줄이어야 한다.
set -u
IMG=$1; NAME=$2; PORT=$3
R="$(cd "$(dirname "$0")/../../.." && pwd)"; V="$R/db/redesign/verify"; TB="$R/db/redesign/to-be/sql"
S="${OUT:-/tmp/rd_chain_out}"; mkdir -p "$S"; PY="${PY:-uv run --no-sync python}"
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d "$1"; }
mk() { docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS $1" -c "CREATE DATABASE $1" >/dev/null; }
docker rm -f $NAME >/dev/null 2>&1
docker run -d --name $NAME -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app -p $PORT:5432 $IMG >/dev/null || exit 1
for i in $(seq 1 40); do docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && sleep 1 && docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && break; sleep 1; done
echo "== 서버: $(docker exec $NAME psql -U app -d app -Atc 'show server_version')"
apply() { for f in "$@"; do q $DB < $f 2>&1 | grep -iE "error|fatal" | head -3; done; }
# 1. 현재 구조: 000~026 + 체크포인트 표 모형(thread-setup 몫) + 표본 데이터
mk old; DB=old; apply $(ls $R/db/0*.sql | sort | awk -F/ '$NF < "027"'); q old < $V/sql/rd_stub.sql; q old < $V/sql/rd_sample.sql
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_asis.txt
# 2. 운영 이전 SQL: expand → contract P1 → contract P2 → 2b
for f in migrate_prod_1_expand migrate_prod_2_contract_p1 migrate_prod_3_contract_p2 migrate_prod_2b_optional_drop_dead_auth; do q old < $TB/$f.sql >/dev/null || echo "ERROR $f"; done
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_migrated.txt
# 3. 새 체인: 빈 DB에 db/*.sql을 이름순으로(compose initdb와 같다) + 체크포인트 표 모형
mk chain; DB=chain; apply $(ls $R/db/0*.sql | sort); q chain < $V/sql/rd_stub.sql
$PY $V/lib/rd_struct.py $PORT chain > $S/${NAME}_chain.txt
diff <(grep -v app_migrations $S/${NAME}_migrated.txt) <(grep -v app_migrations $S/${NAME}_chain.txt) > $S/${NAME}_chain_diff.txt
echo "== 새 체인 vs 운영 이전 결과: 구조 차이 줄 수 $(wc -l < $S/${NAME}_chain_diff.txt) (app_migrations 줄 제외)"; head -20 $S/${NAME}_chain_diff.txt
echo "== 이력 표: 체인 $(q chain <<< 'SELECT string_agg(version, $$,$$ ORDER BY applied_at, version) FROM app_migrations')"
echo "== 이력 표: 이전 $(q old <<< 'SELECT string_agg(version, $$,$$ ORDER BY applied_at, version) FROM app_migrations')"
# 4. 되돌리기 B2 → B1 → A 뒤 처음 구조(000~026)와 비교(app_migrations · RLS · 단순 검사 이름 제외)
python3 - "$TB/migrate_prod_4_rollback.sql" "$S" <<'PYEOF'
import sys
s=open(sys.argv[1],encoding="utf-8").read(); out=sys.argv[2]
m={k:s.index("-- ===================================================== "+k+".") for k in ("B2","B1","A")}
b=sorted(m.values())+[len(s)]
for k,v in m.items(): open(f"{out}/rb_{k}.sql","w",encoding="utf-8").write(s[v:b[b.index(v)+1]])
PYEOF
q old < $S/rb_B2.sql >/dev/null 2>&1 || echo "ERROR B2"; q old < $S/rb_B1.sql >/dev/null 2>&1 || echo "ERROR B1"
sed -n '/^CREATE FUNCTION conversation_json_matches/,/^END \$\$;/p' $R/db/019_conversations.sql | q old >/dev/null 2>&1
for f in 025_runs_safe_result_preferred_mount 024_projects_demo_c01 023_retention; do q old < $R/db/$f.sql >/dev/null 2>&1; done
q old < $S/rb_A.sql >/dev/null 2>&1 || echo "ERROR A"
# 2b(승인 대기 표 삭제)의 되돌리기는 010에서 빈 표만 다시 만드는 것이다(2b 파일 머리)
sed -n '/^CREATE TABLE auth_google_pending/,/^);/p' $R/db/010_google_auth.sql | q old >/dev/null 2>&1 || echo "ERROR 2b"
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_rolledback.txt
diff <(grep -v "app_migrations\|RLS\|ck_runs_safe_result" $S/${NAME}_asis.txt) <(grep -v "app_migrations\|RLS\|ck_runs_safe_result" $S/${NAME}_rolledback.txt) > $S/${NAME}_rb_diff.txt
echo "== 되돌리기 뒤 처음 구조와 차이 줄 수 $(wc -l < $S/${NAME}_rb_diff.txt)"; head -20 $S/${NAME}_rb_diff.txt
docker rm -f $NAME >/dev/null 2>&1
