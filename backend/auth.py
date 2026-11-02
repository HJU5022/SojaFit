"""PostgreSQL-backed authentication for provisioned accounts."""
import getpass
import argparse
import hashlib
import hmac
import os
import secrets
import sys

import psycopg
from fastapi import HTTPException, Request

COOKIE = "sojafit_session"
# [왜] scrypt 검증 한 번에 128MiB를 쓴다. authenticate()가 DB advisory lock 2칸으로 동시 검증을 2개까지만 허용한다.
N, R, P = 2**17, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        kind, salt, expected = encoded.split("$")
        if kind != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def connection():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def check_origin(request: Request) -> None:
    origin = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/")
    if request.headers.get("origin") != origin:
        raise HTTPException(status_code=403, detail="요청 출처를 확인할 수 없습니다.")


def authenticate(email: str, password: str) -> tuple[str, int] | None:
    email = email.strip().lower()
    key = hashlib.sha256(email.encode()).hexdigest()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(736125, 1) OR pg_try_advisory_xact_lock(736125, 2)")
        if not cur.fetchone()[0]:
            raise HTTPException(status_code=503, detail="잠시 후 다시 시도해 주세요.")
        cur.execute("INSERT INTO auth_login_attempts (login_hash) VALUES (%s) ON CONFLICT DO NOTHING", (key,))
        cur.execute("SELECT failed_count, locked_until > CURRENT_TIMESTAMP, window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes' FROM auth_login_attempts WHERE login_hash = %s FOR UPDATE", (key,))
        count, locked, window_expired = cur.fetchone()
        # Serialize login against account deactivation and session revocation.
        cur.execute("SELECT id, password_hash, is_active FROM users WHERE login_id = %s FOR UPDATE", (email,))
        user = cur.fetchone()
        if locked:
            return None
        # Unknown accounts perform the same expensive password verification.
        encoded = user[1] if user else "scrypt$" + "00" * 16 + "$" + "00" * 32
        valid = verify_password(password, encoded)
        if not user or not user[2] or not valid:
            count = 1 if window_expired else count + 1
            cur.execute("UPDATE auth_login_attempts SET failed_count = %s, window_started_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE window_started_at END, locked_until = CASE WHEN %s >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE NULL END WHERE login_hash = %s", (count, window_expired, count, key))
            return None
        cur.execute("DELETE FROM auth_login_attempts WHERE login_hash = %s", (key,))
        token = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (hashlib.sha256(token.encode()).hexdigest(), user[0]))
        return token, user[0]


def current_user_id(request: Request) -> int:
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE auth_sessions s SET last_seen_at = CURRENT_TIMESTAMP FROM users u WHERE s.token_hash = %s AND s.user_id = u.id AND u.is_active AND s.expires_at > CURRENT_TIMESTAMP AND s.last_seen_at > CURRENT_TIMESTAMP - INTERVAL '30 minutes' RETURNING s.user_id", (digest,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return row[0]


def logout(request: Request) -> None:
    token = request.cookies.get(COOKIE)
    if token and len(token) <= 128:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (hashlib.sha256(token.encode()).hexdigest(),))


def admin_users(actor_id: int) -> list[dict]:
    with connection() as conn:
        actor = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (actor_id,)).fetchone()
        if not actor or actor != ("admin", True):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        rows = conn.execute("SELECT id, login_id, role, is_active FROM users ORDER BY id").fetchall()
        return [{"id": row[0], "email": row[1], "role": row[2], "is_active": row[3]} for row in rows]


def admin_set_active(actor_id: int, target_id: int, active: bool) -> None:
    with connection() as conn:
        actor = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (actor_id,)).fetchone()
        if not actor or actor != ("admin", True):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        target = conn.execute("SELECT role FROM users WHERE id=%s FOR UPDATE", (target_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
        if target[0] != "user":
            raise HTTPException(status_code=403, detail="관리자 계정은 변경할 수 없습니다.")
        conn.execute("UPDATE users SET is_active=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (active, target_id))
        if not active:
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (target_id,))


def provision() -> None:
    parser = argparse.ArgumentParser(description="Create a provisioned account")
    parser.add_argument("--role", choices=("user", "admin"), default="user")
    args = parser.parse_args()
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if "@" not in email or len(email) > 100 or len(password) < 12 or len(password.encode()) > 1024 or password != confirmation:
        sys.exit("Invalid email or password; use at least 12 characters and matching confirmation.")
    with connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, %s)", (email, hash_password(password), args.role))
    print("Account created.")


if __name__ == "__main__":
    provision()
