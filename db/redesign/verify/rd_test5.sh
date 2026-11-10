#!/bin/bash
# expand만 적용(contract 전)한 상태에서 새 코드가 쓴 행이 있을 때 expand 되돌리기(A)가 옛 구조를 복원하는가. 사용: rd_test5.sh <컨테이너> <포트>
NAME=$1; PORT=$2
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; S="${OUT:-/tmp/rd_verify_out}"; mkdir -p "$S"
R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/redesign/to-be/sql"; PY="${PY:-python3}"   # PY: psycopg가 설치된 파이썬(예: PY=$(pwd)/.venv/bin/python)
docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS mid2" -c "CREATE DATABASE mid2" >/dev/null
Q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d mid2 "$@"; }
for f in $(ls $R/db/0*.sql | sort); do Q < $f >/dev/null 2>&1; done; Q < $V/sql/rd_stub.sql; Q < $V/sql/rd_sample.sql
Q < $TB/migrate_prod_1_expand.sql >/dev/null && echo "expand 적용"
Q -c "INSERT INTO threads(id,project_id) VALUES ('00000000-0000-0000-0000-0000000000bb',2); INSERT INTO runs(id,thread_id,status) VALUES ('10000000-0000-0000-0000-0000000000bb','00000000-0000-0000-0000-0000000000bb','completed'); INSERT INTO messages(thread_id,run_id,role,content) VALUES ('00000000-0000-0000-0000-0000000000bb','10000000-0000-0000-0000-0000000000bb','assistant','nb'); INSERT INTO approvals(user_id,message_id,snapshot,candidate_part,verdict,part_number) VALUES (1,(SELECT max(id) FROM messages),'{\"answer\":\"n\",\"candidate\":{\"part\":\"X\",\"verdict\":\"ROLE_SUFFICIENT\"}}','X','ROLE_SUFFICIENT','X'); INSERT INTO quotes(user_id,approval_id,part_number,quantity) VALUES (1,(SELECT max(id) FROM approvals),'X',2); INSERT INTO approved_cases(user_id,approval_id) VALUES (1,(SELECT max(id) FROM approvals)); INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES ('00000000-0000-0000-0000-0000000000bb',1,'D3');" && echo "새 코드가 snapshot · circuit_id 없이 INSERT"
python3 - <<PYEOF
s=open("$TB/migrate_prod_4_rollback.sql",encoding="utf-8").read()
a=s.index("-- ===================================================== A.")
open("$S/rd_rb5_A.sql","w",encoding="utf-8").write(s[a:])
PYEOF
Q < $S/rd_rb5_A.sql 2>&1 | grep -v NOTICE | tail -3 && echo "expand 되돌리기(A) 적용"
Q -c "SELECT '  quotes.snapshot NULL 행='||(SELECT count(*) FROM quotes WHERE snapshot IS NULL)||' / approved_cases='||(SELECT count(*) FROM approved_cases WHERE snapshot IS NULL)||' / agent.threads.circuit_id NULL='||(SELECT count(*) FROM sojafit_agent.threads WHERE circuit_id IS NULL)||' / agent.circuits 행='||(SELECT count(*) FROM sojafit_agent.circuits)||' / agent.threads 행='||(SELECT count(*) FROM sojafit_agent.threads)"
$PY $V/lib/rd_struct.py $PORT mid2 > $S/rd_${NAME}_mid2.txt
diff <(grep -v "app_migrations\|RLS" $S/rd_${NAME}_asis.txt) <(grep -v "app_migrations\|RLS" $S/rd_${NAME}_mid2.txt) > $S/rd_${NAME}_mid2diff.txt; echo "  as-is와 구조 차이 줄 수: $(wc -l < $S/rd_${NAME}_mid2diff.txt)"; head -8 $S/rd_${NAME}_mid2diff.txt
