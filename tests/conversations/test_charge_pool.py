"""charge()가 새 접속 대신 풀 연결을 빌리고, 트랜잭션 경계 · 429 오류는 그대로인지 확인한다(DB 없이 가짜 풀)."""
from contextlib import contextmanager
from decimal import Decimal

import pytest

from backend.conversations.memory_service import Conversations
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
    def connection(self):
        self.borrowed += 1
        yield self.conn


def charge_of(conn):
    svc = object.__new__(Conversations)
    svc.pool = FakePool(conn)
    svc.connection = lambda: pytest.fail('charge는 새 접속을 열면 안 된다')
    # 첫 예약(_budget의 usage 삽입)은 새 접속을 쓰므로 그 부분만 가짜로 대체한다
    @contextmanager
    def first():
        yield type('C', (), {'execute': lambda s, t, p=(): type('R', (), {'fetchone': lambda s2: {'day': 1, 'spent': False, 'mine': 0, 'service': 0}})()})()
    svc.connection = first
    budget = svc._budget('u1')
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
