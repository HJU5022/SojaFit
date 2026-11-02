"""PostgreSQL-backed authentication for provisioned accounts."""
import getpass
import hashlib
import hmac
import os
import secrets
import sys

import psycopg
from fastapi import HTTPException, Request

COOKIE = "sojafit_session"
# scrypt uses 128 MiB per verification; cap request concurrency in deployment.
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
        cur.execute("SELECT failed_count, locked_until > CURRENT_TIMESTAMP FROM auth_login_attempts WHERE login_hash = %s FOR UPDATE", (key,))
        count, locked = cur.fetchone()
        cur.execute("SELECT id, password_hash, is_active FROM users WHERE login_id = %s", (email,))
        user = cur.fetchone()
        if locked:
            return None
        # Unknown accounts perform the same expensive password verification.
        encoded = user[1] if user else "scrypt$" + "00" * 16 + "$" + "00" * 32
        valid = verify_password(password, encoded)
        if not user or not user[2] or not valid:
            cur.execute("UPDATE auth_login_attempts SET failed_count = CASE WHEN locked_until <= CURRENT_TIMESTAMP THEN 1 ELSE failed_count + 1 END, locked_until = CASE WHEN (CASE WHEN locked_until <= CURRENT_TIMESTAMP THEN 1 ELSE failed_count + 1 END) >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE NULL END WHERE login_hash = %s", (key,))
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


def provision() -> None:
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if "@" not in email or len(email) > 100 or len(password) < 12 or len(password.encode()) > 1024 or password != confirmation:
        sys.exit("Invalid email or password; use at least 12 characters and matching confirmation.")
    with connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (login_id, password_hash) VALUES (%s, %s)", (email, hash_password(password)))
    print("Account created.")


if __name__ == "__main__":
    provision()
