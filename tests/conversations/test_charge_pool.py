"""charge()가 새 접속 대신 풀 연결을 빌리고, 트랜잭션 경계 · 429 오류는 그대로인지 확인한다(DB 없이 가짜 풀)."""
from contextlib import contextmanager
from decimal import Decimal

import pytest

from backend.conversations.memory_service import Conversations
from psycopg_pool import PoolTimeout

from backend.errors import ApiError


class FakeConn:
    def __init__(self, usage, service_ok=True):
        self.usage, self.service_ok, self.sql, self.log = usage, service_ok, [], []

    def execute(self, text, params=()):
        self.sql.append(text)
        row = None
        if text.startswith('SELECT reserved_usd,reserved_tokens'):
            row = self.usage
        elif text.startswith('UPDATE analysis_service_usage'):
            row = {'day': 1} if self.service_ok else None
        return type('R', (), {'fetchone': lambda self_: row})()

    @contextmanager
    def transaction(self):
        try:
            yield
        except BaseException:
            self.log.append('rollback')
            raise
        self.log.append('commit')


class FakePool:
    def __init__(self, conn):
        self.conn, self.borrowed = conn, 0

    @contextmanager
    def connection(self, timeout=None):
        if self.conn is None:
            raise PoolTimeout()
        self.borrowed += 1
        yield self.conn


def charge_of(conn, fresh=None):
    svc = object.__new__(Conversations)
    svc.pool = FakePool(conn)
    # 첫 예약(_budget의 usage 삽입)은 새 접속을 쓰므로 그 부분만 가짜로 대체한다
    @contextmanager
    def first():
        yield type('C', (), {'execute': lambda s, t, p=(): type('R', (), {'fetchone': lambda s2: {'day': 1, 'spent': False, 'mine': 0, 'service': 0}})()})()
    svc.connection = first
    budget = svc._budget('u1')
    if fresh:  # 첫 예약이 끝난 뒤의 새 접속은 풀 실패 때만 쓰인다
        svc.connection = lambda: fresh
    budget.reserving_tokens = 100  # reserve()가 호출 직전에 채우는 값
    return budget.on_reserve, svc.pool


def test_charge_uses_pool_and_commits():
    conn = FakeConn({'reserved_usd': Decimal('0'), 'reserved_tokens': 0})
    charge, pool = charge_of(conn)
    charge(0.01)
    assert pool.borrowed == 1 and conn.log == ['commit']
    assert conn.sql[0].endswith('FOR UPDATE') and conn.sql[-1].startswith('UPDATE analysis_usage')


def test_charge_rolls_back_on_user_limit():
    conn = FakeConn({'reserved_usd': Decimal('99'), 'reserved_tokens': 0})
    charge, _ = charge_of(conn)
    with pytest.raises(ApiError) as e:
        charge(0.01)
    assert e.value.status_code == 429 and conn.log == ['rollback'] and len(conn.sql) == 1


def test_charge_rolls_back_on_service_limit():
    conn = FakeConn({'reserved_usd': Decimal('0'), 'reserved_tokens': 0}, service_ok=False)
    charge, _ = charge_of(conn)
    with pytest.raises(ApiError) as e:
        charge(0.01)
    assert e.value.status_code == 429 and conn.log == ['rollback'] and not conn.sql[-1].startswith('UPDATE analysis_usage')


@pytest.mark.parametrize('usage,ok,log,status', [
    ({'reserved_usd': Decimal('0'), 'reserved_tokens': 0}, True, ['commit'], None),
    ({'reserved_usd': Decimal('99'), 'reserved_tokens': 0}, True, ['rollback'], 429),
    ({'reserved_usd': Decimal('0'), 'reserved_tokens': 0}, False, ['rollback'], 429),
])
def test_charge_falls_back_to_fresh_connection_on_pool_timeout(usage, ok, log, status):
    fresh = FakeConn(usage, service_ok=ok)
    charge, pool = charge_of(None, type('F', (), {'__enter__': lambda s: fresh, '__exit__': lambda s, *a: None})())
    if status:
        with pytest.raises(ApiError) as e:
            charge(0.01)
        assert e.value.status_code == status
    else:
        charge(0.01)
    assert pool.borrowed == 0 and fresh.log == log
