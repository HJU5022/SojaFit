#!/bin/bash
# 이미 rd_test.sh로 as-is → expand → contract까지 간 컨테이너에서 되돌리기를 시험한다
NAME=$1; PORT=$2
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; S="${OUT:-/tmp/rd_verify_out}"; mkdir -p "$S"
R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/migrations"; PY="${PY:-python3}"   # PY: psycopg가 설치된 파이썬(예: PY=$(pwd)/.venv/bin/python)
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d app "$@"; }
python3 - <<PYEOF
s=open("$TB/migrate_prod_4_rollback.sql",encoding="utf-8").read()
m={k:s.index("-- ===================================================== "+k+".") for k in ("B2","B1","A")}
i=sorted(m.values())+[len(s)]
for k,v in m.items():
    end=i[i.index(v)+1]
    open("$S/rd_rb_%s.sql"%k,"w",encoding="utf-8").write(s[v:end])
PYEOF
echo "== 되돌리기 B2 → B1"; q < $S/rd_rb_B2.sql 2>&1 | tail -3; q < $S/rd_rb_B1.sql 2>&1 | tail -3
echo "== 옛 검사 · 옛 함수를 레포 파일로 복원"
sed -n '/^CREATE FUNCTION conversation_json_matches/,/^END \$\$;/p' $R/db/legacy/019_conversations.sql | q 2>&1 | tail -2
q < $R/db/legacy/025_runs_safe_result_preferred_mount.sql 2>&1 | tail -2; q < $R/db/legacy/024_projects_demo_c01.sql 2>&1 | tail -2; q < $R/db/legacy/023_retention.sql 2>&1 | tail -2
echo "== 복원 데이터 확인"
q -c "SELECT 'quotes.snapshot = approvals.snapshot: '||(SELECT bool_and(q.snapshot = a.snapshot) FROM quotes q JOIN approvals a ON a.id=q.approval_id)"
q -c "SELECT 'agent.circuits 행='||(SELECT count(*) FROM sojafit_agent.circuits)||' agent.threads 행='||(SELECT count(*) FROM sojafit_agent.threads)||' (같아야 함)'"
echo "== 되돌리기 A(expand 되돌림)"; q < $S/rd_rb_A.sql 2>&1 | tail -3
$PY $V/lib/rd_struct.py $PORT app > $S/rd_${NAME}_rolledback.txt
echo "== as-is 구조와 비교(app_migrations · RLS · ck_runs_safe_result 제외)"
diff <(grep -v "app_migrations\|RLS\|ck_runs_safe_result" $S/rd_${NAME}_asis.txt) <(grep -v "app_migrations\|RLS\|ck_runs_safe_result" $S/rd_${NAME}_rolledback.txt) > $S/rd_${NAME}_rbdiff.txt; echo "차이 줄 수: $(wc -l < $S/rd_${NAME}_rbdiff.txt)"; head -20 $S/rd_${NAME}_rbdiff.txt
