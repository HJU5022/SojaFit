#!/bin/bash
# 이전 SQL의 데이터 손실 가드 시험: 가짜 운영 구조(옛 체인 000~026 + 표본 데이터)에서 정상 데이터는 통과하고 위반 데이터는 막히는지, 막힌 뒤 아무것도 지워지지 않았는지 확인한다.
# 사용(레포 루트): bash db/redesign/verify/rd_test6.sh <이미지> <컨테이너 이름> <포트>   (일회용 도커 컨테이너만 쓴다. 운영 DB 접속 없음)
IMG=$1; NAME=$2; PORT=$3
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/migrations"
docker rm -f $NAME >/dev/null 2>&1
docker run -d --name $NAME -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app -p $PORT:5432 $IMG >/dev/null || exit 1
for i in $(seq 1 40); do docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && sleep 1 && docker exec $NAME pg_isready -U app -d app >/dev/null 2>&1 && break; sleep 1; done
echo "== 서버: $(docker exec $NAME psql -U app -d app -Atc 'show server_version')"
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d "$1"; }
pf() { local db=$1 file=$2; shift 2; local args=(); for a in "$@"; do args+=(-c "SET $a='yes'"); done
       docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d "$db" "${args[@]}" -f - < "$file" 2>&1; }
mk() { docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS $1" -c "CREATE DATABASE $1 TEMPLATE base" >/dev/null; }
PASS=0; FAIL=0
ok() { echo "  통과: $1"; PASS=$((PASS+1)); }
bad() { echo "  실패: $1"; FAIL=$((FAIL+1)); }
# 가짜 운영 구조: 옛 체인 000~026 + 체크포인트 대역 + 표본 데이터
docker exec $NAME psql -U app -d app -qc "CREATE DATABASE base" >/dev/null
for f in $(bash $V/old_chain.sh $R); do q base < $f 2>&1 | grep -iE "error|fatal" | head -2; done
q base < $V/sql/rd_stub.sql; q base < $V/sql/rd_sample.sql
docker exec $NAME psql -U app -d app -qc "ALTER DATABASE base IS_TEMPLATE true" >/dev/null 2>&1
# 단계 적용 도우미: 앞 단계까지 정상 적용한 DB를 만든다
upto() { mk $1; pf $1 $TB/migrate_prod_1_expand.sql >/dev/null || echo "ERROR expand"; [ "$2" = e ] && return
         pf $1 $TB/migrate_prod_2_contract_p1.sql >/dev/null || echo "ERROR p1"; [ "$2" = p1 ] && return
         pf $1 $TB/migrate_prod_3_contract_p2.sql >/dev/null || echo "ERROR p2"; }
expect_block() { # <설명> <출력> <기대 문구>
  if echo "$2" | grep -q "$3"; then ok "$1 → 중단($3)"; else bad "$1 → 중단되지 않음: $(echo "$2" | tail -1 | cut -c1-120)"; fi; }
echo "== 정상 데이터: 네 단계 모두 통과(PG 가드가 정상 데이터를 막지 않음)"
upto n p2; out=$(pf n $TB/migrate_prod_2b_optional_drop_dead_auth.sql); echo "$out" | grep -q ERROR && bad "정상 2b: $out" || ok "정상 expand → P1 → P2 → 2b"
[ "$(q n <<< "SELECT to_regclass('sojafit_agent.approvals') IS NULL AND to_regclass('public.auth_google_pending') IS NULL")" = t ] && ok "정상 적용 뒤 삭제 대상이 사라짐" || bad "정상 적용 뒤 상태"
echo "== P1 가드"
upto v1 e; q v1 <<< "UPDATE users SET display_name='홍길동' WHERE id=1" >/dev/null
out=$(pf v1 $TB/migrate_prod_2_contract_p1.sql); expect_block "display_name 값 있음, 확인 없음" "$out" "app.ack_drop_display_name"
[ "$(q v1 <<< "SELECT count(*) FROM information_schema.columns WHERE table_name='users' AND column_name='display_name'")" = 1 ] && ok "중단 뒤 display_name 칸이 그대로" || bad "중단했는데 칸이 사라짐"
out=$(pf v1 $TB/migrate_prod_2_contract_p1.sql app.ack_drop_display_name); echo "$out" | grep -q "ERROR" && bad "확인 변수를 줬는데 막힘: $out" || ok "display_name 값 있음 + 확인 변수 'yes' → 통과"
upto v2 e; q v2 <<< "UPDATE quotes SET snapshot = snapshot || '{\"extra\":1}'::jsonb" >/dev/null
out=$(pf v2 $TB/migrate_prod_2_contract_p1.sql app.ack_drop_display_name); expect_block "quotes.snapshot이 approvals와 다름" "$out" "quotes.snapshot"
[ "$(q v2 <<< "SELECT count(*) FROM information_schema.columns WHERE table_name='quotes' AND column_name='snapshot'")" = 1 ] && ok "중단 뒤 quotes.snapshot 칸이 그대로" || bad "quotes.snapshot이 사라짐"
upto v3 e; q v3 <<< "UPDATE approved_cases SET snapshot = '{\"candidate\":{\"part\":\"X\",\"verdict\":\"IDENTICAL\"}}'" >/dev/null
out=$(pf v3 $TB/migrate_prod_2_contract_p1.sql); expect_block "approved_cases.snapshot이 approvals와 다름" "$out" "approved_cases.snapshot"
upto v3b e; q v3b <<< "UPDATE quotes SET snapshot = NULL; UPDATE approved_cases SET snapshot = NULL" >/dev/null
out=$(pf v3b $TB/migrate_prod_2_contract_p1.sql); echo "$out" | grep -q ERROR && bad "snapshot이 NULL(새 코드가 안 채움)인데 막힘: $out" || ok "snapshot NULL은 통과"
echo "== P2 가드"
upto v4 p1; q v4 <<< "INSERT INTO sojafit_agent.approvals(thread_id,version,snapshot) VALUES ('00000000-0000-0000-0000-000000000001',1,'{}')" >/dev/null
out=$(pf v4 $TB/migrate_prod_3_contract_p2.sql); expect_block "sojafit_agent.approvals에 행 있음" "$out" "app.ack_drop_agent_approvals"
[ "$(q v4 <<< "SELECT to_regclass('sojafit_agent.approvals') IS NOT NULL")" = t ] && ok "중단 뒤 sojafit_agent.approvals가 그대로" || bad "approvals가 사라짐"
out=$(pf v4 $TB/migrate_prod_3_contract_p2.sql app.ack_drop_agent_approvals); echo "$out" | grep -q ERROR && bad "확인 변수를 줬는데 막힘: $out" || ok "approvals 행 있음 + 확인 변수 → 통과"
upto v5 p1; q v5 <<< "INSERT INTO sojafit_agent.circuits(id,user_id,filename,netlist,connections) VALUES ('00000000-0000-0000-0000-0000000000ff',1,'orphan','','{\"parts\":[]}')" >/dev/null
out=$(pf v5 $TB/migrate_prod_3_contract_p2.sql); expect_block "thread 없는 분석 회로 사본" "$out" "app.ack_drop_agent_circuits"
echo "== 2b 가드"
upto v6 p2; q v6 <<< "INSERT INTO auth_google_pending(request_id,issuer,subject,email,expires_at) VALUES ('r','i','s','x@example.test',now())" >/dev/null
out=$(pf v6 $TB/migrate_prod_2b_optional_drop_dead_auth.sql); expect_block "auth_google_pending에 행 있음" "$out" "app.ack_drop_google_pending"
[ "$(q v6 <<< "SELECT to_regclass('public.auth_google_pending') IS NOT NULL")" = t ] && ok "중단 뒤 auth_google_pending이 그대로" || bad "표가 사라짐"
out=$(pf v6 $TB/migrate_prod_2b_optional_drop_dead_auth.sql app.ack_drop_google_pending); echo "$out" | grep -q ERROR && bad "확인 변수를 줬는데 막힘: $out" || ok "행 있음 + 확인 변수 → 통과"
echo "== 결과: 통과 $PASS, 실패 $FAIL"
docker rm -f $NAME >/dev/null 2>&1
[ $FAIL = 0 ]
