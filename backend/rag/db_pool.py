"""DB 연결 풀: 검색(`retrieve.py`)과 카드 도구(`card_find.py`, `card_specs.py`)가 호출마다 새 연결을 맺지 않도록 프로세스당 풀 하나를 DSN별로 늦게 만들어 돌려준다.

- 역할: `connection()` 컨텍스트 매니저. `with connection() as conn:` 블록이 정상으로 끝나면 commit, 예외면 rollback하고 연결을 풀에 돌려준다
  (`psycopg.connect()`를 `with`로 쓰던 때와 같은 트랜잭션 의미, 닫는 대신 반납한다).
- 하지 않는 일: 쓰기 전용 풀, 대화 저장소 풀(`backend/conversations/memory_service.py`가 따로 가진다).
"""
import os
from threading import Lock

_pools = {}  # [왜] DSN별로 하나. 평가 러너가 작업마다 DATABASE_URL을 바꿔 같은 프로세스에서 다른 코퍼스를 읽는다
_lock = Lock()


def _configure(conn):
    from pgvector.psycopg import register_vector
    register_vector(conn)
    conn.commit()  # [주의] register_vector가 연 트랜잭션을 닫아야 풀이 이 연결을 버리지 않는다(INTRANS)


def _pool():
    dsn = os.environ['DATABASE_URL']
    with _lock:
        if dsn not in _pools:
            from psycopg_pool import ConnectionPool
            # [왜] prepare_threshold=0: 풀 연결은 오래 살아 같은 SQL이 5번 넘으면 서버 측 prepared statement가 되는데, Supabase 풀러(트랜잭션 모드)에서 깨진다(memory_service와 같은 설정)
            # [왜] check: 풀러가 놀던 연결을 끊었을 수 있어 꺼낼 때 살아 있는지 본다
            _pools[dsn] = ConnectionPool(dsn, min_size=1, max_size=8, timeout=20, configure=_configure, check=ConnectionPool.check_connection,
                                         kwargs={'prepare_threshold': 0}, open=True)
        return _pools[dsn]


def connection():
    """풀에서 연결 하나를 빌리는 컨텍스트 매니저. pgvector 형식이 이미 등록돼 있다."""
    return _pool().connection()
