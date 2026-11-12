"""승인 대기 보고(scripts/eval/approval_wait_report.py): 합성 이벤트로 재개 · 승인 대기와 자동 호출 분리를 확인하고, 일회용 DB에서 읽기 전용 접속을 확인한다.

- 역할: 사람 대기(조건 질문 → 재개, 완료 → 승인)가 서버 처리 시간과 분리되고, 즉시 자동 호출(스모크)은 사람 대기에서 빠지며, 출력에 id가 없는지 본다.
  DB 시험은 TEST_THREAD_DATABASE_URL(일회용 postgres에 서비스 기준선 적용)이 있을 때만 돈다. 합성 행은 2099년으로 넣어 다른 시험과 섞이지 않게 `--since`로 거른다.
- 하지 않는 일: 운영 DB 접속.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from scripts.eval import approval_wait_report as W

T0 = datetime(2099, 1, 1, tzinfo=timezone.utc)


def at(seconds):
    return T0 + timedelta(seconds=seconds)


def synthetic():
    human, auto = uuid.uuid4(), uuid.uuid4()
    events = [  # 사람: 질문 처리 4초(10에 끝) → 25초 기다려 재개(처리 3초, 38에 끝) → 승인은 38 + 20 = 58
        (human, 'WAITING', 4000, at(10)), (human, 'DONE', 3000, at(38)),
        # 자동: 처리 후 0.2초 만에 재개, 0.1초 만에 승인
        (auto, 'WAITING', 5000, at(100)), (auto, 'DONE', 1000, at(101.2))]
    return human, auto, events, [(human, at(58)), (auto, at(101.3))]


def test_compute_separates_human_wait_server_time_and_auto_calls():
    _, _, events, approvals = synthetic()
    r = W.compute(events, approvals)
    assert r['resume_wait_s']['n'] == 1 and r['resume_wait_s']['p50'] == 25.0  # (38 - 3) - 10
    assert r['approval_wait_s']['p50'] == 20.0 and r['approval_wait_s']['n'] == 1
    assert r['auto_suspect'] == {'resume': 1, 'approve': 1}
    assert r['server_s_per_thread'] == {'n': 2, 'p50': 6.5, 'p95': 7.0}  # 7초 · 6초
    assert r['threads_with_events'] == 2


def test_output_has_counts_and_seconds_only():
    human, _, events, approvals = synthetic()
    assert str(human) not in json.dumps(W.compute(events, approvals))


@pytest.mark.skipif(not os.getenv('TEST_THREAD_DATABASE_URL'), reason='일회용 DB 없음')
def test_fetch_reads_synthetic_rows_and_connection_is_read_only():
    import psycopg
    dsn = os.environ['TEST_THREAD_DATABASE_URL']
    human, user = uuid.uuid4(), 900_000_000 + uuid.uuid4().int % 99_000_000
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute('SET session_replication_role = replica')  # 합성 행이라 사용자 · 프로젝트 · run 같은 외래키 줄을 건너뛴다(일회용 DB, 슈퍼유저)
            conn.execute("INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES (%s,%s,'x')", (human, user))
            message = conn.execute("INSERT INTO public.messages(thread_id,run_id,role,content) VALUES (%s,%s,'assistant','x') RETURNING id", (human, uuid.uuid4())).fetchone()[0]
            for status, ms, sec in (('WAITING', 4000, 10), ('DONE', 3000, 38)):
                conn.execute("INSERT INTO sojafit_agent.analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery,created_at) "
                             "VALUES (%s,%s,1,'r','live',%s,%s,'[]','t','disabled',%s)", (uuid.uuid4(), human, status, ms, at(sec)))
            conn.execute("INSERT INTO public.approvals(user_id,message_id,candidate_part,verdict,part_number,snapshot,created_at) "
                         "VALUES (%s,%s,'P','IDENTICAL','P','{}',%s)", (user, message, at(58)))
            conn.commit()
        with psycopg.connect(dsn) as conn:
            events, approvals = W.fetch(conn, datetime(2098, 1, 1, tzinfo=timezone.utc))
            r = W.compute(events, approvals)
            assert (r['resume_wait_s']['p50'], r['approval_wait_s']['p50']) == (25.0, 20.0)
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                conn.execute('DELETE FROM sojafit_agent.analysis_events')
            conn.rollback()
            events, _ = W.fetch(conn, datetime(2098, 1, 1, tzinfo=timezone.utc), [user])
            assert events == []  # 제외한 사용자 대화는 읽지 않는다

    finally:  # [왜] 외래키 없이 넣은 합성 행이 남으면 다른 시험의 고아 행 검사가 깨진다
        with psycopg.connect(dsn) as conn:
            conn.execute('SET session_replication_role = replica')
            conn.execute('DELETE FROM public.approvals WHERE user_id=%s', (user,))
            conn.execute('DELETE FROM public.messages WHERE thread_id=%s', (human,))
            conn.execute('DELETE FROM sojafit_agent.analysis_events WHERE thread_id=%s', (human,))
            conn.execute('DELETE FROM sojafit_agent.threads WHERE id=%s', (human,))
            conn.commit()
