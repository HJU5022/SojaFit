"""사람이 기다린 시간(조건 질문 → 재개, 완료 → 승인 클릭)을 서버 처리 시간과 떼어 DB 시각에서 읽는 읽기 전용 보고(D8 승인 대기).

- 역할: DATABASE_URL의 DB를 읽기 전용으로 열어 `sojafit_agent.analysis_events`(분석 호출 한 번마다 한 행)와 `public.approvals`의 시각으로 계산한다.
  - 재개 대기 = 다음 행의 `created_at − elapsed_ms` − 앞 행의 `created_at`(앞 행의 status가 WAITING일 때만). 행의 created_at은 호출이 끝나 기록한 시각이다.
  - 승인 대기 = `approvals.created_at` − 같은 대화의 승인 직전 DONE 행의 `created_at`.
  - 서버 처리 = 행의 `elapsed_ms`(대화 하나의 분석 호출 합).
- 사람 대기가 아닌 것: 스모크 계정의 자동 재개 · 승인(scripts/smoke/http_smoke.py)은 응답이 끝나자마자 다음 요청을 보내 대기가 `--auto-under`초(기본 3초) 안이다.
  그 값은 `auto_suspect`로 따로 세고 사람 대기 통계에서 뺀다. 계정으로 거르려면 `--exclude-users`(사용자 id), 기간은 `--since`로 좁힌다.
- 하지 않는 일: DB 쓰기(연결을 read-only로 연다), 사용자 id · 이메일 · 대화 id · 질문 · 답 출력(건수와 시간만 낸다).
- 한계: 사람이 화면을 보고 답하기까지 걸린 시간에 네트워크 · 화면 그리는 시간이 섞인다. 행의 시작 시각은 `created_at − elapsed_ms`로 근사한다(기록 INSERT 직전 몇십 ms 오차).
- 실행(저장소 루트, DATABASE_URL 필요): uv run --env-file .env python -m scripts.eval.approval_wait_report --since 2026-11-11 [--exclude-users 1,2] [--out <결과.json>]
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from scripts.eval.stage_report import dist

EVENTS = ("SELECT e.thread_id, e.status, e.elapsed_ms, e.created_at FROM sojafit_agent.analysis_events e "
          "JOIN sojafit_agent.threads t ON t.id = e.thread_id WHERE e.created_at >= %(since)s AND t.user_id <> ALL(%(skip)s::bigint[]) "
          "ORDER BY e.thread_id, e.created_at")
APPROVALS = ("SELECT m.thread_id, a.created_at FROM public.approvals a JOIN public.messages m ON m.id = a.message_id "
             "WHERE a.created_at >= %(since)s AND a.user_id <> ALL(%(skip)s::bigint[])")


def compute(events, approvals, auto_under=3.0):
    """events: (thread, status, elapsed_ms, created_at) 행, approvals: (thread, created_at) 행 → 건수 · 시간 요약. 대화 id는 결과에 넣지 않는다."""
    by_thread = defaultdict(list)
    for thread, status, elapsed_ms, at in sorted(events, key=lambda e: (str(e[0]), e[3])):
        by_thread[thread].append((status, elapsed_ms, at))
    resume, approve, server, auto = [], [], [], {'resume': 0, 'approve': 0}
    for rows in by_thread.values():
        server.append(sum(r[1] for r in rows) / 1000)
        for before, after in zip(rows, rows[1:]):
            if before[0] == 'WAITING':
                wait = (after[2] - timedelta(milliseconds=after[1]) - before[2]).total_seconds()
                if wait > auto_under:
                    resume.append(wait)
                else:
                    auto['resume'] += 1
    done = {t: [r[2] for r in rows if r[0] == 'DONE'] for t, rows in by_thread.items()}
    for thread, at in approvals:
        before = [d for d in done.get(thread, []) if d <= at]
        if not before:
            continue
        wait = (at - max(before)).total_seconds()
        if wait > auto_under:
            approve.append(wait)
        else:
            auto['approve'] += 1
    return {'threads_with_events': len(by_thread), 'auto_under_s': auto_under, 'auto_suspect': auto,
            'resume_wait_s': dist(resume, 1), 'approval_wait_s': dist(approve, 1), 'server_s_per_thread': dist(server, 1),
            'definition': {'resume': 'next.created_at - next.elapsed_ms - prev.created_at, prev.status=WAITING',
                           'approve': 'approval.created_at - latest DONE event.created_at', 'p50': 'true median', 'p95': 'nearest rank'}}


def fetch(conn, since, skip_users=()):
    conn.read_only = True  # [왜] 이 스크립트는 읽기만 한다. 서버가 쓰기 문장을 거부하게 연결부터 읽기 전용으로 둔다
    params = {'since': since, 'skip': list(skip_users)}
    return conn.execute(EVENTS, params).fetchall(), conn.execute(APPROVALS, params).fetchall()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='1970-01-01')
    ap.add_argument('--exclude-users', default='', help='쉼표로 나눈 사용자 id(예: 스모크 계정)')
    ap.add_argument('--auto-under', type=float, default=3.0)
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    import psycopg
    skip = [int(x) for x in args.exclude_users.split(',') if x]
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        events, approvals = fetch(conn, datetime.fromisoformat(args.since), skip)
    result = compute(events, approvals, args.auto_under)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if args.out:
        json.dump(result, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
