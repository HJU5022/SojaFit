#!/bin/bash
# 백업 복원 왕복 시험: 합성 데이터가 든 DB를 pg_dump -Fc → 빈 새 DB에 pg_restore 했을 때 오류 0, 행 수 동일인지 본다(새 Supabase 프로젝트로 옮기는 경로).
# 대상 4가지: ① 새 기준선 ② 옛 구조 + 이전 SQL 전부 ③ 그 뒤 되돌린 결과 ④ 이전 전의 옛 구조(백업 복원 절차의 구조→데이터 순서가 필요함을 같이 보인다)
# 사용(레포 루트): bash db/redesign/verify/rd_test7.sh <이미지> <컨테이너 이름> <포트>   (일회용 도커 컨테이너만. 운영 접속 없음)
IMG=$1; NAME=$2; PORT=$3
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/migrations"
docker rm -f $NAME >/dev/null 2>&1
docker run -d --name $NAME -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app -p $PORT:5432 $IMG >/dev/null || exit 1
for i in $(seq 1 40); do docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && sleep 1 && docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && break; sleep 1; done
echo "== 서버: $(docker exec $NAME psql -U app -d app -Atc 'show server_version')"
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d "$1"; }
mkdb() { docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS $1" -c "CREATE DATABASE $1" >/dev/null; }
counts() { q $1 <<'SQL'
SELECT table_schema||'.'||table_name||'='||(xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text
FROM information_schema.tables WHERE table_schema IN ('public','sojafit_agent') AND table_type='BASE TABLE' ORDER BY 1;
SQL
}
FAIL=0
roundtrip() { # <원본 db> <설명> [steps: direct|sections]
  local src=$1 desc=$2 mode=${3:-direct} dst=r_$1 errs
  docker exec $NAME sh -c "pg_dump -U app -d $src -Fc --no-owner --no-privileges -f /tmp/$src.dump"
  mkdb $dst
  if [ $mode = direct ]; then
    errs=$(docker exec $NAME pg_restore -U app -d $dst --no-owner --no-privileges /tmp/$src.dump 2>&1 | grep -ciE "error")
  else
    # 구조 → (재귀 함수 설정) → 데이터 → 제약 · 인덱스 순서(DB.md의 복원 절차)
    errs=$(docker exec $NAME sh -c "pg_restore -U app -d $dst --no-owner --no-privileges --section=pre-data /tmp/$src.dump" 2>&1 | grep -ciE "error")
    q $dst <<'SQL'
ALTER FUNCTION public.quote_snapshot_has_forbidden_key(jsonb) SET search_path = "$user", public;
ALTER FUNCTION public.conversation_json_matches(jsonb, jsonb) SET search_path = "$user", public;
SQL
    errs=$((errs + $(docker exec $NAME sh -c "pg_restore -U app -d $dst --no-owner --no-privileges --section=data /tmp/$src.dump && pg_restore -U app -d $dst --no-owner --no-privileges --section=post-data /tmp/$src.dump" 2>&1 | grep -ciE "error")))
  fi
  if [ "$(counts $src)" = "$(counts $dst)" ] && [ "$errs" = 0 ]; then echo "  통과: $desc → 오류 0, 표 $(counts $src | wc -l)개 행 수 동일 (총 $(counts $src | awk -F= '{s+=$2} END {print s}')행)"
  else echo "  실패: $desc → 오류 줄 $errs, 행 수 차이: $(diff <(counts $src) <(counts $dst) | head -3 | tr '\n' ' ')"; FAIL=$((FAIL+1)); fi
}
# ① 새 기준선(compose initdb와 같은 순서) + 합성 데이터
mkdb b1; for f in $(ls $R/db/*.sql | sort); do q b1 < $f 2>&1 | grep -iE "error" | head -2; done; q b1 < $V/sql/rd_stub.sql; q b1 < $V/sql/rd_sample_new.sql
roundtrip b1 "① 새 기준선 DB (pg_dump -Fc → 빈 DB pg_restore 한 번)"
# ② 옛 구조 + 표본 → 이전 SQL 전부
mkdb o1; for f in $(bash $V/old_chain.sh $R); do q o1 < $f 2>&1 | grep -iE "error" | head -2; done; q o1 < $V/sql/rd_stub.sql; q o1 < $V/sql/rd_sample.sql
docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS o0" -c "CREATE DATABASE o0 TEMPLATE o1" >/dev/null
# ④ 이전 전의 옛 구조(o0)는 이전 SQL을 적용하기 전에 복사해 둔 것이다: 바로 복원하면 실패해야 하고, 구조→데이터 절차면 통과해야 한다
docker exec $NAME sh -c "pg_dump -U app -d o0 -Fc --no-owner --no-privileges -f /tmp/o0.dump"; mkdb r_o0_direct
n=$(docker exec $NAME pg_restore -U app -d r_o0_direct --no-owner --no-privileges /tmp/o0.dump 2>&1 | grep -c "does not exist")
[ "$n" -gt 0 ] && echo "  확인: 이전 전의 옛 구조는 한 번에 복원하면 실패한다('does not exist' $n줄, 재귀 함수에 search_path가 없어서) → 구조→데이터 절차 필요" || { echo "  실패: 옛 구조 직접 복원이 실패하지 않음(전제 확인)"; FAIL=$((FAIL+1)); }
roundtrip o0 "④ 이전 전의 옛 구조 (구조 → 함수 설정 → 데이터 → 제약 · 인덱스)" sections
for f in migrate_prod_1_expand migrate_prod_2_contract_p1 migrate_prod_3_contract_p2 migrate_prod_2b_optional_drop_dead_auth; do q o1 < $TB/$f.sql >/dev/null 2>&1 || echo "ERROR $f"; done
roundtrip o1 "② 옛 구조 + 이전 SQL 전부 (expand → P1 → P2 → 2b)"
# ③ 되돌린 결과
python3 - "$TB/migrate_prod_4_rollback.sql" /tmp <<'PY'
import sys
s=open(sys.argv[1],encoding="utf-8").read(); out=sys.argv[2]
m={k:s.index("-- ===================================================== "+k+".") for k in ("B2b","B2","B1","A")}
b=sorted(m.values())+[len(s)]
for k,v in m.items(): open(f"{out}/rd7_rb_{k}.sql","w",encoding="utf-8").write(s[v:b[b.index(v)+1]])
PY
for k in B2b B2 B1; do q o1 < /tmp/rd7_rb_$k.sql >/dev/null 2>&1 || echo "ERROR $k"
  if [ $k = B1 ]; then
    sed -n '/^CREATE FUNCTION conversation_json_matches/,/^END \$\$;/p' $R/db/legacy/019_conversations.sql | q o1 >/dev/null
    echo 'ALTER FUNCTION public.conversation_json_matches(jsonb, jsonb) SET search_path = "$user", public' | q o1
    for f in 025_runs_safe_result_preferred_mount 024_projects_demo_c01 023_retention; do q o1 < $R/db/legacy/$f.sql >/dev/null 2>&1; done
  fi
done
q o1 < /tmp/rd7_rb_A.sql >/dev/null 2>&1 || echo "ERROR A"
roundtrip o1 "③ 이전 SQL을 되돌린 결과 (B2b → B2 → B1 + 셸 단계 → A)"
docker rm -f $NAME >/dev/null 2>&1
echo "== 결과: 실패 $FAIL"; [ $FAIL = 0 ]
