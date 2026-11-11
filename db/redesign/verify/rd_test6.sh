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
echo "== 실행 전 점검 질의(읽기 전용, 개수만): 각 단계 직전 구조에서 오류 없이 돌고 개수만 찍는다"
chk() { # <db> <파일> <설명>
  out=$(pf $1 $TB/$2); if echo "$out" | grep -q "ERROR"; then bad "$3: $(echo "$out" | head -2 | cut -c1-140)"; else ok "$3 ($(echo "$out" | grep -c '^\[')줄)"; fi
  echo "$out" | grep -qE "a@example|b@example|1N4007G|TSC" && bad "$3 → 출력에 내용이 새어 나옴"; }
mk c1; chk c1 precheck_1_before_expand.sql "점검1(expand 전)"
upto c2 e; chk c2 precheck_2_before_p1.sql "점검2(P1 전)"
upto c3 p1; chk c3 precheck_3_before_p2.sql "점검3(P2 전)"
upto c4 p2; chk c4 precheck_4_before_2b.sql "점검4(2b 전)"
echo "== expand 사전점검(값 형식): 새 CHECK를 어길 행이 있으면 ADD CONSTRAINT 전에 중단하고 id만 알린다"
bad_expand() { # <db> <설명> <UPDATE 문> <기대 문구>
  mk $1; q $1 <<< "$3" >/dev/null; out=$(pf $1 $TB/migrate_prod_1_expand.sql)
  if echo "$out" | grep -q "$4"; then ok "$2 → 중단"; else bad "$2 → 막히지 않음: $(echo "$out" | tail -1 | cut -c1-120)"; fi
  echo "$out" | grep -q "1N4007G\|@example" && bad "$2 → 오류 문구에 행 내용이 새어 나옴"
  [ "$(q $1 <<< "SELECT count(*) FROM information_schema.columns WHERE table_name='approvals' AND column_name='candidate_part'")" = 0 ] && ok "$2 → 중단 뒤 새 칸이 없음(롤백)" || bad "$2 → 새 칸이 남음"; }
bad_expand x1 "품번에 괄호" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,part_number}','\"1N4007G(A)\"') WHERE id=1" "품번이 형식"
bad_expand x2 "품번에 쉼표" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,part_number}','\"1N4007G,A\"') WHERE id=1" "품번이 형식"
bad_expand x3 "품번에 전각 문자" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,part_number}','\"１N4007G\"') WHERE id=1" "품번이 형식"
bad_expand x4 "품번이 빈 문자열" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,part_number}','\"\"') WHERE id=1" "품번이 형식"
bad_expand x5 "이름이 빈 문자열(파생 품번 없음)" "UPDATE approvals SET snapshot=jsonb_set(jsonb_set(snapshot,'{candidate,part}','\"\"'),'{candidate,part_number}','null') WHERE id=2" "1~100자"
bad_expand x6 "이름이 101자" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,part}',to_jsonb(repeat('A',101))) WHERE id=2" "1~100자"
bad_expand x7 "알 수 없는 판정" "UPDATE approvals SET snapshot=jsonb_set(snapshot,'{candidate,verdict}','\"MAYBE\"') WHERE id=1" "허용 3값"
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
upto v5b p1; q v5b <<< "UPDATE sojafit_agent.circuits SET netlist='.title x'" >/dev/null
out=$(pf v5b $TB/migrate_prod_3_contract_p2.sql); expect_block "분석 회로 사본의 netlist가 빈 값이 아님" "$out" "app.ack_drop_agent_circuits"
upto v5c p1; q v5c <<< "UPDATE sojafit_agent.circuits SET filename='내가 바꾼 이름' WHERE id='00000000-0000-0000-0000-000000000001'" >/dev/null
out=$(pf v5c $TB/migrate_prod_3_contract_p2.sql); expect_block "분석 회로 사본의 filename이 프로젝트 이름과 다름" "$out" "app.ack_drop_agent_circuits"
out=$(pf v5c $TB/migrate_prod_3_contract_p2.sql app.ack_drop_agent_circuits); echo "$out" | grep -q ERROR && bad "확인 변수를 줬는데 막힘: $out" || ok "filename 다름 + 확인 변수 → 통과"
echo "== SET LOCAL(풀러 transaction 모드 대안): 한 트랜잭션 안에서 확인 변수를 주면 같은 세션 SET 없이 통과"
upto v7 e; q v7 <<< "UPDATE users SET display_name='홍길동' WHERE id=1" >/dev/null
out=$( (echo "BEGIN; SET LOCAL app.ack_drop_display_name='yes';"; cat $TB/migrate_prod_2_contract_p1.sql) | docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d v7 2>&1 )
echo "$out" | grep -q "ERROR" && bad "SET LOCAL 경로가 막힘: $out" || ok "BEGIN; SET LOCAL ...; 파일 → 통과"
[ "$(q v7 <<< "SELECT count(*) FROM information_schema.columns WHERE table_name='users' AND column_name='display_name'")" = 0 ] && ok "SET LOCAL 경로로 실제로 적용됨" || bad "적용되지 않음"
echo "== 2b 가드"
upto v6 p2; q v6 <<< "INSERT INTO auth_google_pending(request_id,issuer,subject,email,expires_at) VALUES ('r','i','s','x@example.test',now())" >/dev/null
out=$(pf v6 $TB/migrate_prod_2b_optional_drop_dead_auth.sql); expect_block "auth_google_pending에 행 있음" "$out" "app.ack_drop_google_pending"
[ "$(q v6 <<< "SELECT to_regclass('public.auth_google_pending') IS NOT NULL")" = t ] && ok "중단 뒤 auth_google_pending이 그대로" || bad "표가 사라짐"
out=$(pf v6 $TB/migrate_prod_2b_optional_drop_dead_auth.sql app.ack_drop_google_pending); echo "$out" | grep -q ERROR && bad "확인 변수를 줬는데 막힘: $out" || ok "행 있음 + 확인 변수 → 통과"
echo "== 결과: 통과 $PASS, 실패 $FAIL"
docker rm -f $NAME >/dev/null 2>&1
[ $FAIL = 0 ]
