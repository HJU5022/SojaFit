"""로그인 잠금·세션 만료의 경계 시각을 PostgreSQL 트랜잭션 시각으로 정확히 재는 일회성 실측. 인증 담당이 로컬에서 손으로 돌린다.

- 역할: 잠금 해제(15분), 유휴 만료(30분), 절대 만료(8시간)가 경계 1마이크로초 전후에서 설계대로 갈리는가를 본다.
  CURRENT_TIMESTAMP를 한 트랜잭션 안에서 고정해 시계 오차 없이 비교한다.
- 하지 않는 일: 평가셋 평가(evals/)가 아니다. 부하·동시성·메모리는 재지 않는다(measure_scrypt_concurrent.py). 외부 API·키는 쓰지 않는다.
- 출처: SPEC 8.6(로그인 AC), docs/specs/login-auth.md "로그인 실패 제한", 해석은 docs/research/auth-login-verification.md.
- 입력: 환경변수 TEST_AUTH_DATABASE_URL. 값에 127.0.0.1:55434/ci_auth가 없으면 실행을 거부한다(격리된 테스트 DB 전용).
  CI의 5432 포트 DB는 이 검사를 통과하지 않으므로 이 스크립트는 로컬에서만 돌린다.
- 원시 결과: scripts/results/auth_boundary_<KST 날짜>.json(같은 날 다시 돌리면 덮어쓴다). 시험 데이터는 롤백한다.
- 필요한 것: 인증 SQL(db/003·005·006)을 적용한 격리 PostgreSQL.

실행(저장소 루트에서): TEST_AUTH_DATABASE_URL=postgresql://...@127.0.0.1:55434/ci_auth uv run python scripts/auth_boundary_after_merge.py
"""
import json
import os
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

# [왜] 저장소 루트를 import 경로에 넣어 `backend`를 어느 위치에서 실행해도 찾게 한다
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoneinfo import ZoneInfo

import psycopg
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app

database_url = os.environ["TEST_AUTH_DATABASE_URL"]
# [주의] DB 안전장치: 로컬 격리 테스트 DB 주소가 아니면 쓰기(사용자 INSERT)를 시작하기 전에 거부한다
if "127.0.0.1:55434/ci_auth" not in database_url:
    raise RuntimeError("This check is restricted to the isolated CI test database")
os.environ["AUTH_ORIGIN"] = "http://testserver"  # TestClient의 기본 출처. 로그인의 출처 검사를 통과시키려고 맞춘다
# 시험 계정은 실행마다 새로 만든 무작위 값이다(고정 비밀번호를 코드에 두지 않는다)
email = f"boundary-{secrets.token_hex(8)}@example.test"
password = secrets.token_urlsafe(24)
records = []  # 요청마다 (이름, 기대 코드, 실제 코드, 걸린 ms)를 쌓아 결과 json의 steps가 된다


def request(client, label, method, path, expected, **kwargs):
    """요청을 보내 (이름·기대·실제 코드·ms)를 records에 쌓고, 기대 코드와 다르면 AssertionError를 낸다."""
    started = time.perf_counter()
    response = client.request(method, path, **kwargs)
    records.append({"case": label, "expected": expected, "actual": response.status_code,
                    "ms": round((time.perf_counter() - started) * 1000, 2)})
    assert response.status_code == expected, label
    return response


class BorrowedConnection:
    """auth.connection()이 새 연결 대신 같은 트랜잭션의 연결을 쓰게 하는 껍데기. with를 나가도 닫지 않는다."""

    def __init__(self, conn):
        """빌려줄 psycopg 연결을 보관한다."""
        self.conn = conn

    def __enter__(self):
        """보관한 연결을 그대로 돌려준다."""
        return self.conn

    def __exit__(self, *args):
        """연결을 닫지 않고, 예외도 삼키지 않는다."""
        return False


conn = psycopg.connect(database_url)
# [왜] auth.connection을 같은 연결로 갈아 끼워, 서버 코드와 이 스크립트가 한 트랜잭션을 공유하게 한다(마지막에 되돌린다)
original_connection = auth.connection
try:
    # reference: 트랜잭션 시작 시각. Postgres에서 CURRENT_TIMESTAMP는 트랜잭션 안에서 변하지 않으므로 경계(±1마이크로초)를 시계 오차 없이 만든다
    version, reference = conn.execute("SELECT current_setting('server_version'), CURRENT_TIMESTAMP").fetchone()
    # 시험 사용자를 넣는다. [주의] 커밋하지 않으므로 끝의 rollback에서 사라진다
    user_id = conn.execute("INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id", (email, auth.hash_password(password))).fetchone()[0]
    auth.connection = lambda: BorrowedConnection(conn)
    headers = {"origin": "http://testserver"}
    # 로그인 시도 기록의 키: 이메일의 sha256(서버 코드와 같은 방식)
    key = __import__("hashlib").sha256(email.encode()).hexdigest()
    with TestClient(app) as client:
        # 1단계: 잘못된 비밀번호 5번. 5번째에 15분(900초) 잠금이 걸리는지 본다
        for count in range(1, 6):
            request(client, f"wrong password {count}", "POST", "/api/auth/login", 401, headers=headers, json={"email": email, "password": "incorrect"})
            failures, lock_seconds = conn.execute("SELECT failed_count, EXTRACT(EPOCH FROM (locked_until-CURRENT_TIMESTAMP)) FROM auth_login_attempts WHERE login_hash=%s", (key,)).fetchone()
            assert failures == count
            assert (lock_seconds is None) if count < 5 else (lock_seconds == 900)
        # 2단계: 잠금 해제 시각을 지금 +1us / 지금 / 지금 -1us로 바꿔 보며 경계에서 잠금이 풀리는지 본다(풀리는 시각 이후만 200)
        for label, expression, expected in (
            ("lock expires 1us later", "CURRENT_TIMESTAMP + INTERVAL '1 microsecond'", 401),
            ("lock expires exactly now", "CURRENT_TIMESTAMP", 200),
            ("lock expired 1us ago", "CURRENT_TIMESTAMP - INTERVAL '1 microsecond'", 200),
        ):
            conn.execute(f"INSERT INTO auth_login_attempts(login_hash,failed_count,locked_until,window_started_at) VALUES (%s,5,{expression},CURRENT_TIMESTAMP) ON CONFLICT (login_hash) DO UPDATE SET failed_count=5,locked_until=EXCLUDED.locked_until,window_started_at=CURRENT_TIMESTAMP", (key,))
            request(client, label, "POST", "/api/auth/login", expected, headers=headers, json={"email": email, "password": password})
        token = client.cookies.get(auth.COOKIE)  # 위 마지막 로그인(200)이 발급한 세션 쿠키
        token_hash = auth.session_token_hash(token)
        initial_seconds = conn.execute("SELECT EXTRACT(EPOCH FROM (expires_at-CURRENT_TIMESTAMP)) FROM auth_sessions WHERE token_hash=%s", (token_hash,)).fetchone()[0]
        assert initial_seconds == 28800  # 절대 만료 8시간 = 28,800초
        # 3단계: 마지막 사용 시각을 30분 -1us / 30분 / 30분 +1us 전으로 돌려 유휴 만료 경계를 본다(30분 이상이면 401)
        for label, interval, expected in (
            ("idle 1us under 30m", "29 minutes 59.999999 seconds", 200),
            ("idle exactly 30m", "30 minutes", 401),
            ("idle 1us over 30m", "30 minutes 0.000001 seconds", 401),
        ):
            conn.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP - %s::interval WHERE token_hash=%s", (interval, token_hash))
            request(client, label, "GET", "/api/auth/me", expected)
        # 4단계: 만료 시각(expires_at)을 지금 +1us / 지금 / 지금 -1us로 바꿔 절대 만료 경계를 본다. last_seen_at은 지금으로 둬 유휴 만료와 섞이지 않게 한다
        for label, expression, expected in (
            ("absolute expires 1us later", "CURRENT_TIMESTAMP + INTERVAL '1 microsecond'", 200),
            ("absolute expires exactly now", "CURRENT_TIMESTAMP", 401),
            ("absolute expired 1us ago", "CURRENT_TIMESTAMP - INTERVAL '1 microsecond'", 401),
        ):
            conn.execute(f"UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP, expires_at={expression} WHERE token_hash=%s", (token_hash,))
            request(client, label, "GET", "/api/auth/me", expected)
    assert conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0] == reference  # 트랜잭션 안에서 시각이 끝까지 고정이었는지 확인
    result = {"measured_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
              "postgres_version": version, "lock_duration_seconds": int(lock_seconds),
              "session_absolute_duration_seconds": int(initial_seconds), "steps": records,
              "method": "one test-only PostgreSQL transaction; CURRENT_TIMESTAMP fixed; rollback"}
    # [주의] 같은 날 다시 돌리면 같은 이름의 결과 파일을 덮어쓴다
    out = Path(__file__).resolve().parents[1] / "scripts" / "results" / f"auth_boundary_{result['measured_at_kst'][:10]}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
finally:
    auth.connection = original_connection
    conn.rollback()  # [주의] 시험 사용자·로그인 기록·세션을 모두 되돌려 DB에 남기지 않는다
    conn.close()
