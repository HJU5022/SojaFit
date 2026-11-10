#!/bin/bash
# 사용: rd_test.sh <이미지> <컨테이너 이름> <포트>   예: rd_test.sh pgvector/pgvector:pg16 rd-pg16 55443
IMG=$1; NAME=$2; PORT=$3
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; S="${OUT:-/tmp/rd_verify_out}"; mkdir -p "$S"
R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/redesign/to-be/sql"; PY="${PY:-python3}"   # PY: psycopg가 설치된 파이썬(예: PY=$(pwd)/.venv/bin/python)
psql_() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -U app -d "${DB:-app}" "$@"; }
docker rm -f $NAME >/dev/null 2>&1
docker run -d --name $NAME -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app -p $PORT:5432 $IMG >/dev/null || exit 1
for i in $(seq 1 40); do docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && sleep 1 && docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && break; sleep 1; done
echo "== 서버: $(docker exec $NAME psql -U app -d app -Atc 'show server_version')"
echo "== 1. as-is 구성: db/*.sql 23개 파일을 initdb 순서로 적용"
for f in $(ls $R/db/0*.sql | sort); do psql_ < $f 2>&1 | grep -v "^$" | grep -iv "notice" | head -3; done
psql_ < $V/sql/rd_stub.sql
psql_ -c "SELECT 'as-is 표 개수(서비스)', count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname IN ('public','sojafit_agent')"
echo "== 2. 표본 데이터"; psql_ < $V/sql/rd_sample.sql && psql_ -Atc "SELECT 'users',count(*) FROM users UNION ALL SELECT 'approvals',count(*) FROM approvals UNION ALL SELECT 'agent.threads',count(*) FROM sojafit_agent.threads"
$PY $V/lib/rd_struct.py $PORT app > $S/rd_${NAME}_asis.txt
echo "== 3. expand 적용"; psql_ < $TB/migrate_prod_1_expand.sql 2>&1 | tail -3
echo "== 3-1. 옛 코드가 expand 뒤 승인을 넣어도 되는지(새 칸 없이 INSERT)"
psql_ -c "INSERT INTO runs(id,thread_id,status) VALUES ('10000000-0000-0000-0000-000000000003','00000000-0000-0000-0000-000000000001','failed'); INSERT INTO messages(thread_id,run_id,role,content) VALUES ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000003','assistant','a3'); INSERT INTO approvals(user_id,message_id,snapshot) VALUES (1,(SELECT max(id) FROM messages),'{\"answer\":\"c\",\"candidate\":{\"part\":\"Taiwan Semiconductor 1N4148 A0G\",\"verdict\":\"SPEC_EQUIVALENT\"}}');" && echo "옛 코드 INSERT 통과"
psql_ -Atc "SELECT 'NULL 칸 있는 승인(옛 코드가 넣은 것)', count(*) FROM approvals WHERE candidate_part IS NULL"
echo "== 3-2. 새 코드(P1 + P2)가 expand 뒤 contract 전에 INSERT해도 되는가(snapshot · circuit_id 없이)"
psql_ -c "INSERT INTO threads(id,project_id) VALUES ('00000000-0000-0000-0000-0000000000bb',2); INSERT INTO runs(id,thread_id,status) VALUES ('10000000-0000-0000-0000-0000000000bb','00000000-0000-0000-0000-0000000000bb','completed'); INSERT INTO messages(thread_id,run_id,role,content) VALUES ('00000000-0000-0000-0000-0000000000bb','10000000-0000-0000-0000-0000000000bb','assistant','nb'); INSERT INTO approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) VALUES (1,(SELECT max(id) FROM messages),'{\"answer\":\"n\",\"candidate\":{\"part\":\"TSC 1N5819\",\"verdict\":\"ROLE_SUFFICIENT\"}}','TSC 1N5819','ROLE_SUFFICIENT','1N5819'); INSERT INTO quotes(user_id,approval_id,part_number,quantity) VALUES (1,(SELECT max(id) FROM approvals),'1N5819',2); INSERT INTO approved_cases(user_id,approval_id) VALUES (1,(SELECT max(id) FROM approvals)); INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES ('00000000-0000-0000-0000-0000000000bb',1,'D3');" && echo "새 코드 INSERT 통과"
echo "== 4. contract P1 적용(C0이 위 행을 채워야 함)"; psql_ < $TB/migrate_prod_2_contract_p1.sql 2>&1 | tail -3
echo "== 4-1. contract P2 적용"; psql_ < $TB/migrate_prod_3_contract_p2.sql 2>&1 | tail -3
psql_ -Atc "SELECT part_number||' | '||candidate_part||' | '||verdict FROM approvals ORDER BY id"
$PY $V/lib/rd_struct.py $PORT app > $S/rd_${NAME}_migrated.txt
echo "== 5. 기준선만 적용한 새 DB와 구조 비교"
docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS base" -c "CREATE DATABASE base" >/dev/null
DB=base psql_ < $TB/baseline_service.sql 2>&1 | tail -2; DB=base psql_ < $V/sql/rd_stub.sql
$PY $V/lib/rd_struct.py $PORT base > $S/rd_${NAME}_baseline.txt
diff <(grep -v "app_migrations" $S/rd_${NAME}_migrated.txt) <(grep -v "app_migrations" $S/rd_${NAME}_baseline.txt) > $S/rd_${NAME}_diff.txt; echo "구조 차이 줄 수: $(wc -l < $S/rd_${NAME}_diff.txt)"; head -40 $S/rd_${NAME}_diff.txt
