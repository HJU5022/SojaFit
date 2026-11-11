#!/bin/bash
# 이전 SQL 전체 검증을 Postgres 16(compose · CI)과 17(운영)에서 차례로 돌린다. 일회용 도커 컨테이너만 쓰고 운영 DB에는 접속하지 않는다.
# 사용(레포 루트): PY=$(pwd)/.venv/bin/python bash db/redesign/verify/run_all.sh
HERE="$(cd "$(dirname "$0")" && pwd)"
for pair in "pgvector/pgvector:pg16 rd-pg16 55443" "pgvector/pgvector:pg17 rd-pg17 55444"; do
  set -- $pair
  echo "################ $1"
  bash "$HERE/rd_test.sh" $1 $2 $3 | grep -E "서버|새 코드|구조 차이|ERROR|Error"
  bash "$HERE/rd_test2.sh" $2 $3 | grep -E "\\[|before|after|반환"
  docker rm -f $2 >/dev/null 2>&1; bash "$HERE/rd_test.sh" $1 $2 $3 >/dev/null 2>&1
  bash "$HERE/rd_test3.sh" $2 $3 | grep -E "snapshot|행=|차이 줄|ERROR"
  bash "$HERE/rd_test4.sh" $2 $3 | grep -E "통과|반환|ERROR"
  bash "$HERE/rd_test5.sh" $2 $3 | grep -E "NULL 행|차이 줄|ERROR"
  docker rm -f $2 >/dev/null 2>&1
done
echo "RLS · app_migrations 줄과 선택 2b 표(auth_google_pending)만 구조 차이로 나오는 것이 정상이다($OUT 또는 /tmp/rd_verify_out/rd_*_diff.txt)."
