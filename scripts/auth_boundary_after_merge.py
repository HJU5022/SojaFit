"""Exact PostgreSQL transaction-time boundary check; use only an isolated test DB."""
import json
import os
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoneinfo import ZoneInfo

import psycopg
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app

database_url = os.environ["TEST_AUTH_DATABASE_URL"]
if "127.0.0.1:55434/ci_auth" not in database_url:
    raise RuntimeError("This check is restricted to the isolated CI test database")
os.environ["AUTH_ORIGIN"] = "http://testserver"
email = f"boundary-{secrets.token_hex(8)}@example.test"
password = secrets.token_urlsafe(24)
records = []


def request(client, label, method, path, expected, **kwargs):
    started = time.perf_counter()
    response = client.request(method, path, **kwargs)
    records.append({"case": label, "expected": expected, "actual": response.status_code,
                    "ms": round((time.perf_counter() - started) * 1000, 2)})
    assert response.status_code == expected, label
    return response


class BorrowedConnection:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


conn = psycopg.connect(database_url)
original_connection = auth.connection
try:
    version, reference = conn.execute("SELECT current_setting('server_version'), CURRENT_TIMESTAMP").fetchone()
    user_id = conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id", (email, auth.hash_password(password))).fetchone()[0]
    auth.connection = lambda: BorrowedConnection(conn)
    headers = {"origin": "http://testserver"}
    key = __import__("hashlib").sha256(email.encode()).hexdigest()
    with TestClient(app) as client:
        for count in range(1, 6):
            request(client, f"wrong password {count}", "POST", "/api/auth/login", 401, headers=headers, json={"email": email, "password": "incorrect"})
            failures, lock_seconds = conn.execute("SELECT failed_count, EXTRACT(EPOCH FROM (locked_until-CURRENT_TIMESTAMP)) FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
            assert failures == count
            assert (lock_seconds is None) if count < 5 else (lock_seconds == 900)
        for label, expression, expected in (
            ("lock expires 1us later", "CURRENT_TIMESTAMP + INTERVAL '1 microsecond'", 401),
            ("lock expires exactly now", "CURRENT_TIMESTAMP", 200),
            ("lock expired 1us ago", "CURRENT_TIMESTAMP - INTERVAL '1 microsecond'", 200),
        ):
            conn.execute(f"INSERT INTO auth_login_attempts(login_hash,failed_count,locked_until,window_started_at) VALUES (%s,5,{expression},CURRENT_TIMESTAMP) ON CONFLICT (login_hash) DO UPDATE SET failed_count=5,locked_until=EXCLUDED.locked_until,window_started_at=CURRENT_TIMESTAMP", (key,))
            request(client, label, "POST", "/api/auth/login", expected, headers=headers, json={"email": email, "password": password})
        token = client.cookies.get(auth.COOKIE)
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        initial_seconds = conn.execute("SELECT EXTRACT(EPOCH FROM (expires_at-CURRENT_TIMESTAMP)) FROM auth_sessions WHERE token_hash=%s", (token_hash,)).fetchone()[0]
        assert initial_seconds == 28800
        for label, interval, expected in (
            ("idle 1us under 30m", "29 minutes 59.999999 seconds", 200),
            ("idle exactly 30m", "30 minutes", 401),
            ("idle 1us over 30m", "30 minutes 0.000001 seconds", 401),
        ):
            conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - %s::interval WHERE token_hash=%s", (interval, token_hash))
            request(client, label, "GET", "/api/auth/me", expected)
        for label, expression, expected in (
            ("absolute expires 1us later", "CURRENT_TIMESTAMP + INTERVAL '1 microsecond'", 200),
            ("absolute expires exactly now", "CURRENT_TIMESTAMP", 401),
            ("absolute expired 1us ago", "CURRENT_TIMESTAMP - INTERVAL '1 microsecond'", 401),
        ):
            conn.execute(f"UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP, expires_at={expression} WHERE token_hash=%s", (token_hash,))
            request(client, label, "GET", "/api/auth/me", expected)
    assert conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0] == reference
    result = {"measured_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
              "postgres_version": version, "lock_duration_seconds": int(lock_seconds),
              "session_absolute_duration_seconds": int(initial_seconds), "steps": records,
              "method": "one test-only PostgreSQL transaction; CURRENT_TIMESTAMP fixed; rollback"}
    out = Path(__file__).resolve().parents[1] / "evals" / "results" / f"auth_boundary_{result['measured_at_kst'][:10]}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
finally:
    auth.connection = original_connection
    conn.rollback()
    conn.close()
