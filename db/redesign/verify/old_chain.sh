#!/bin/bash
# 기준선 이전의 옛 체인(db/*.sql 중 코퍼스 + db/legacy/*.sql + 026)을 번호순으로 한 줄에 하나씩 찍는다. 사용: bash old_chain.sh <저장소 루트> [상한 접두사(기본 027: 026까지)]
# [왜] 기준선(db/020_service_baseline.sql)으로 바꾼 뒤에도 운영 이전 SQL은 "옛 구조"에서 시작해야 해서 옛 파일이 db/legacy/에 이력으로 남아 있다.
R=$1; MAX=${2:-027}
for f in "$R"/db/0*.sql "$R"/db/legacy/*.sql; do
  case $(basename "$f") in 020_service_baseline.sql) ;; *) echo "$(basename "$f") $f";; esac
done | sort | awk -v max="$MAX" '$1 < max {print $2}'
