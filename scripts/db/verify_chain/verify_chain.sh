#!/bin/bash
# 새 DB 기준선(db/020_service_baseline.sql 등 db/*.sql)이 옛 체인(db/legacy 포함 000~026)에 운영 이전 SQL(db/migrations/)을 적용한 결과와 같은 구조인지, 옛 증분 체인 000~029와도 같은지,
# 되돌리기(B2b → B2 → B1 → A) 뒤 처음 구조(RLS · 함수 권한 포함)로 돌아오는지 확인한다.
# 일회용 도커 컨테이너만 쓴다(운영 DB 접속 없음). 사용(레포 루트): bash scripts/db/verify_chain/verify_chain.sh <이미지> <컨테이너 이름> <포트>
#   예: bash scripts/db/verify_chain/verify_chain.sh pgvector/pgvector:pg16 rd-schema-db16 55450
# [왜] 기준선과 운영 이전 SQL이 따로 자라면 새 DB와 운영 DB의 구조가 갈라진다. 이 비교가 0줄이어야 한다.
set -u
RC=0   # 비교에서 차이(허용 목록 밖)가 나오면 1로 끝낸다
IMG=$1; NAME=$2; PORT=$3
R="$(cd "$(dirname "$0")/../../.." && pwd)"; V="$R/db/redesign/verify"; TB="$R/db/migrations"
S="${OUT:-/tmp/rd_chain_out}"; mkdir -p "$S"; PY="${PY:-uv run --no-sync python}"
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d "$1"; }
mk() { docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS $1" -c "CREATE DATABASE $1" >/dev/null; }
docker rm -f $NAME >/dev/null 2>&1
docker run -d --name $NAME -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app -p $PORT:5432 $IMG >/dev/null || exit 1
for i in $(seq 1 40); do docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && sleep 1 && docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && break; sleep 1; done
echo "== 서버: $(docker exec $NAME psql -U app -d app -Atc 'show server_version')"
apply() { for f in "$@"; do q $DB < $f 2>&1 | grep -iE "error|fatal" | head -3; done; }
# 옛 체인 = db/*.sql + db/legacy/*.sql를 파일 이름(번호)순으로 섞은 것(기준선 이전 db/ 폴더와 같은 순서)
legacy_chain() { for f in $R/db/0*.sql $R/db/legacy/*.sql; do case $(basename $f) in 020_service_baseline.sql) ;; *) echo "$(basename $f) $f";; esac; done | sort | awk -v max="$1" '$1 < max {print $2}'; }
# 1. 현재 구조: 옛 체인 000~026 + 체크포인트 표 모형(thread-setup 몫) + 표본 데이터
mk old; DB=old; apply $(legacy_chain 027); q old < $V/sql/rd_stub.sql; q old < $V/sql/rd_sample.sql
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_asis.txt
# 2. 운영 이전 SQL: expand → contract P1 → contract P2 → 2b
for f in migrate_prod_1_expand migrate_prod_2_contract_p1 migrate_prod_3_contract_p2 migrate_prod_2b_optional_drop_dead_auth; do q old < $TB/$f.sql >/dev/null || echo "ERROR $f"; done
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_migrated.txt
# 3. 새 기준선: 빈 DB에 db/*.sql을 이름순으로(compose initdb와 같다, 하위 폴더 제외) + 체크포인트 표 모형
mk chain; DB=chain; apply $(ls $R/db/*.sql | sort); q chain < $V/sql/rd_stub.sql
$PY $V/lib/rd_struct.py $PORT chain > $S/${NAME}_chain.txt
diff <(grep -v app_migrations $S/${NAME}_migrated.txt) <(grep -v app_migrations $S/${NAME}_chain.txt) > $S/${NAME}_chain_diff.txt
echo "== 새 기준선 vs 옛 체인 + 운영 이전 결과: 구조 차이 줄 수 $(wc -l < $S/${NAME}_chain_diff.txt) (app_migrations 줄 제외)"; head -20 $S/${NAME}_chain_diff.txt; [ -s $S/${NAME}_chain_diff.txt ] && RC=1
# 3b. 옛 증분 체인 전체(000~029)와도 비교(legacy 폴더가 이력으로 남아도 기준선과 같은 결과를 내야 한다)
mk legfull; DB=legfull; apply $(legacy_chain 9999); q legfull < $V/sql/rd_stub.sql
$PY $V/lib/rd_struct.py $PORT legfull > $S/${NAME}_legacyfull.txt
# 허용: 옛 증분 파일(legacy 020)은 재귀 함수에 search_path를 붙이지 않았다(백업 복원 불가였던 원인). 기준선만 붙인다
diff <(grep -v app_migrations $S/${NAME}_legacyfull.txt) <(grep -v app_migrations $S/${NAME}_chain.txt) | grep '^[<>]' | grep -vE '^[<>] FCFG public\.quote_snapshot_has_forbidden_key\(' > $S/${NAME}_legacyfull_diff.txt
echo "== 새 기준선 vs 옛 증분 체인 000~029: 구조 차이 줄 수 $(wc -l < $S/${NAME}_legacyfull_diff.txt) (허용: 옛 파일에는 없는 search_path 설정)"; head -20 $S/${NAME}_legacyfull_diff.txt; [ -s $S/${NAME}_legacyfull_diff.txt ] && RC=1
echo "== 이력 표: 체인 $(q chain <<< 'SELECT string_agg(version, $$,$$ ORDER BY applied_at, version) FROM app_migrations')"
echo "== 이력 표: 이전 $(q old <<< 'SELECT string_agg(version, $$,$$ ORDER BY applied_at, version) FROM app_migrations')"
# 4. 되돌리기 B2 → B1 → A 뒤 처음 구조(000~026)와 비교(app_migrations · RLS · 단순 검사 이름 제외)
python3 - "$TB/migrate_prod_4_rollback.sql" "$S" <<'PYEOF'
import sys
s=open(sys.argv[1],encoding="utf-8").read(); out=sys.argv[2]
m={k:s.index("-- ===================================================== "+k+".") for k in ("B2b","B2","B1","A")}
b=sorted(m.values())+[len(s)]
for k,v in m.items(): open(f"{out}/rb_{k}.sql","w",encoding="utf-8").write(s[v:b[b.index(v)+1]])
PYEOF
for k in B2b B2 B1; do q old < $S/rb_$k.sql >/dev/null 2>&1 || echo "ERROR $k"
  # B1 뒤: 옛 JSON 모양 검사 · 옛 청소 함수를 레포 파일에서 다시 만든다(되돌리기 SQL 머리말의 셸 단계)
  if [ $k = B1 ]; then
    sed -n '/^CREATE FUNCTION conversation_json_matches/,/^END \$\$;/p' $R/db/legacy/019_conversations.sql | q old >/dev/null 2>&1 || echo "ERROR 019"
    echo 'REVOKE ALL ON FUNCTION public.conversation_json_matches(jsonb, jsonb) FROM PUBLIC' | q old >/dev/null 2>&1 || echo "ERROR revoke"
    for f in 025_runs_safe_result_preferred_mount 024_projects_demo_c01 023_retention; do q old < $R/db/legacy/$f.sql >/dev/null 2>&1; done
  fi
done
q old < $S/rb_A.sql >/dev/null 2>&1 || echo "ERROR A"
$PY $V/lib/rd_struct.py $PORT old > $S/${NAME}_rolledback.txt
diff $S/${NAME}_asis.txt $S/${NAME}_rolledback.txt | grep '^[<>]' > $S/${NAME}_rb_diff_raw.txt
# 되돌리기 뒤에도 남는 것으로 알려진 차이(명시 허용 목록. 여기 없는 줄은 모두 실패다):
#  ① app_migrations 표와 그 줄(이력 표는 남긴다) ② 새 단순 검사 ck_runs_safe_result(B1이 지우지 않고 옛 검사 runs_safe_result_check 옆에 둠, 무해)
#  ③ 재귀 함수 2개의 search_path 설정(FCFG, 백업 복원 가능하게 일부러 남김) ④ 그 함수의 본문 해시는 같아야 하므로 허용하지 않음
ALLOW='app_migrations|^[<>] CON  public\.runs ck_runs_safe_result |^[<>] FCFG public\.(quote_snapshot_has_forbidden_key|conversation_json_matches)\('
grep -vE "$ALLOW" $S/${NAME}_rb_diff_raw.txt > $S/${NAME}_rb_diff.txt
echo "== 되돌리기 뒤 처음 구조와 허용 목록 밖 차이 줄 수 $(wc -l < $S/${NAME}_rb_diff.txt) (허용: app_migrations · 단순 검사 ck_runs_safe_result · 재귀 함수 search_path 설정, 원본 차이 $(wc -l < $S/${NAME}_rb_diff_raw.txt)줄)"; head -20 $S/${NAME}_rb_diff.txt; [ -s $S/${NAME}_rb_diff.txt ] && RC=1
# 되돌리기가 다시 만든 표 · 함수의 보안 상태를 직접 확인한다: RLS OFF 표(내 소유) 0개, 공개 역할 · PUBLIC 권한이 남은 표 0개, 함수 PUBLIC 실행 권한 없음
q old <<'SQLEOF' | sed 's/^/   /'
SELECT 'RLS OFF 표: ' || count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('public','sojafit_agent') AND c.relkind IN ('r','p') AND NOT c.relrowsecurity AND pg_get_userbyid(c.relowner) = current_user
   AND c.relname NOT IN ('source_documents','document_chunks','chunk_embeddings','chunk_embedding_bits') AND c.relname NOT LIKE 'checkpoint%' AND c.relname !~ '^store';
SELECT 'PUBLIC 권한 남은 서비스 표: ' || count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
 WHERE n.nspname IN ('public','sojafit_agent') AND c.relkind IN ('r','p','S') AND a.grantee = 0;
SELECT 'conversation_json_matches PUBLIC 실행 권한: ' || COALESCE((SELECT bool_or(a.grantee = 0) FROM pg_proc p, LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a WHERE p.proname = 'conversation_json_matches'), false);
SQLEOF
docker rm -f $NAME >/dev/null 2>&1
exit $RC
