#!/bin/bash
# P1만 적용한 중간 상태(P2 코드 전)에서 옛 분석 서비스 삭제 경로 · 옛 청소 함수가 그대로 되는지 본다. 사용: rd_test4.sh <컨테이너> <포트>
NAME=$1; PORT=$2
HERE="$(cd "$(dirname "$0")" && pwd)"; V="$HERE"; S="${OUT:-/tmp/rd_verify_out}"; mkdir -p "$S"
R="$(cd "$HERE/../../.." && pwd)"; TB="$R/db/redesign/to-be/sql"; PY="${PY:-python3}"   # PY: psycopg가 설치된 파이썬(예: PY=$(pwd)/.venv/bin/python)
q() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d app "$@"; }
docker exec $NAME psql -U app -d app -qc "DROP DATABASE IF EXISTS mid" -c "CREATE DATABASE mid" >/dev/null
Q2() { docker exec -i $NAME psql -v ON_ERROR_STOP=1 -q -At -U app -d mid "$@"; }
for f in $(ls $R/db/0*.sql | sort); do Q2 < $f >/dev/null 2>&1; done; Q2 < $V/sql/rd_stub.sql; Q2 < $V/sql/rd_sample.sql
Q2 < $TB/migrate_prod_1_expand.sql >/dev/null && Q2 < $TB/migrate_prod_2_contract_p1.sql >/dev/null && echo "expand + contract P1 적용(P2 전)"
echo "-- 옛 코드의 프로젝트 삭제 경로(delete_analysis_threads 같은 순서)가 오류 없이 되는가"
Q2 -c "DELETE FROM sojafit_agent.checkpoint_writes WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE user_id=1); DELETE FROM sojafit_agent.checkpoint_blobs WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE user_id=1); DELETE FROM sojafit_agent.checkpoints WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE user_id=1); DELETE FROM sojafit_agent.threads WHERE user_id=1; DELETE FROM sojafit_agent.circuits WHERE user_id=1; DELETE FROM public.projects WHERE id=1;" && echo "  통과"
Q2 -c "SELECT '  남은 agent.circuits='||(SELECT count(*) FROM sojafit_agent.circuits)||' agent.threads='||(SELECT count(*) FROM sojafit_agent.threads)"
echo "-- 옛 청소 함수(P2 전이라 아직 옛 본문)가 그대로 도는가"
Q2 -c "UPDATE projects SET updated_at=now()-interval '100 days'; UPDATE threads SET created_at=now()-interval '100 days'; UPDATE runs SET updated_at=now()-interval '100 days'; UPDATE approvals SET created_at=now()-interval '100 days'; UPDATE quotes SET created_at=now()-interval '100 days'"
Q2 -c "SELECT '  purge_inactive_projects 반환='||sojafit_agent.purge_inactive_projects(60,20)||' / 남은 agent.circuits='||(SELECT count(*) FROM sojafit_agent.circuits)"
