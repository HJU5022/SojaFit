"""PostgreSQL 기반 인증(비밀번호 scrypt, DB 세션, 로그인 잠금, 관리자 계정 관리).

역할: 비밀번호는 scrypt로 해시해 users에 두고, 로그인하면 무작위 토큰을 만들어 그 해시(HMAC 또는 SHA-256)만
auth_sessions에 저장한다. 실패 5회는 15분 잠금(auth_login_attempts), 세션은 절대 8시간·유휴 30분이다.
호출자: backend/main.py(API 라우트), tests/api/test_auth.py, 계정 생성 CLI(`python -m backend.auth`, `--hash-only`는 해시만 출력).
하지 않는 일: HTTP 라우트·쿠키 설정(backend/main.py), 회원가입(관리자가 만든 계정만 로그인), 테이블 생성(db/*.sql),
회로·대화·기억·견적의 사용자별 권한 검증(해당 기능 구현 후 추가).
출처: SPEC.md 4절(인증·관리자 계약)·8.6절(로그인 AC), docs/specs/login-auth.md, backend/BACKEND.md.
읽는 환경변수: DATABASE_URL(필수), AUTH_SECRET(세션 토큰 HMAC 키, 32바이트 이상, DEMO_MODE!=1이면 필수),
DEMO_MODE(기본 1), AUTH_ORIGIN(허용 Origin, 기본 http://localhost:8000).
테이블 정의는 db/003_auth.sql·005·006.
"""
import getpass
import argparse
import hashlib
import hmac
import os
import re
import secrets
import sys

import psycopg
from fastapi import HTTPException, Request

COOKIE = "sojafit_session"
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# [왜] scrypt 검증 한 번에 128MiB를 쓴다. authenticate()가 DB advisory lock 2칸으로 동시 검증을 2개까지만 허용한다.
# N=2**17(CPU·메모리 비용), R=블록 크기, P=병렬도. [주의] 바꾸면 기존 해시가 검증되지 않는다
N, R, P = 2**17, 8, 1


def validate_auth_configuration() -> None:
    """AUTH_SECRET이 있으면 32바이트 이상, 데모 모드가 아니면 필수인지 검사한다(어기면 RuntimeError)."""
    secret = os.getenv("AUTH_SECRET", "")
    if secret and (not secret.strip() or len(secret.encode("utf-8")) < 32):
        raise RuntimeError("AUTH_SECRET must contain at least 32 bytes")
    if os.getenv("DEMO_MODE", "1") != "1" and not secret:
        raise RuntimeError("AUTH_SECRET is required outside demo mode")


def session_token_hash(token: str) -> str:
    """세션 토큰을 DB에 저장할 해시(hex)로 바꾼다."""
    # [왜] DB가 유출돼도 토큰 원문을 알 수 없게 해시만 저장한다. AUTH_SECRET이 있으면 HMAC-SHA256, 없으면(데모) SHA-256
    validate_auth_configuration()
    secret = os.getenv("AUTH_SECRET", "")
    if secret:
        return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """비밀번호를 salt와 scrypt로 해시해 `scrypt$<salt hex>$<digest hex>` 문자열로 돌려준다."""
    # [왜] 사용자마다 무작위 salt 16바이트를 써서 같은 비밀번호도 다른 해시가 되게 한다
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """비밀번호가 저장 해시와 같은지 확인한다(형식이 깨진 해시는 예외 없이 False)."""
    try:
        kind, salt, expected = encoded.split("$")
        if kind != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
        # [주의] 일반 ==는 틀린 위치에서 일찍 끝나 시간 차이가 생기므로 상수 시간 비교를 쓴다
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def connection():
    """DATABASE_URL로 새 PostgreSQL 연결을 연다(`with`로 쓰면 종료 때 커밋하고 닫는다)."""
    # [주의] DATABASE_URL이 없으면 KeyError, 연결 실패는 psycopg.Error. 연결 대기는 5초로 제한한다
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)


def valid_email(email: str) -> bool:
    """프로젝트 계정 규칙: 공백 없는 이메일, 도메인에 점 포함, DB 길이 100자 이하."""
    return len(email) <= 100 and EMAIL.fullmatch(email) is not None


def mask_email(email: str) -> str:
    """유효한 주소는 로컬 첫 글자와 도메인만 표시하고, 형식이 깨진 주소는 숨긴다."""
    if not valid_email(email):
        return "***"
    local, domain = email.split("@")
    return f"{local[0]}***@{domain}"


def check_origin(request: Request) -> None:
    """상태를 바꾸는 요청의 Origin 헤더가 AUTH_ORIGIN과 같은지 확인한다(다르면 403)."""
    # [왜] 쿠키 세션은 다른 사이트의 요청에도 따라붙으므로 Origin을 대조해 CSRF를 막는다
    origin = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/")
    if request.headers.get("origin") != origin:
        raise HTTPException(status_code=403, detail="요청 출처를 확인할 수 없습니다.")


def authenticate(email: str, password: str) -> tuple[str, int] | None:
    """이메일·비밀번호를 검증하고 성공하면 새 세션을 만든다.

    scrypt 동시 검증은 DB advisory lock 2칸으로 제한한다(메모리 보호). 실패 5회(15분 창)면 15분 잠금이다.
    없는 계정도 같은 비용으로 검증해 응답 시간 차이(timing attack)로 계정 존재를 알 수 없게 한다.

    Args:
        email: 로그인 이메일(공백 제거·소문자로 맞춘다).
        password: 평문 비밀번호.
    Returns:
        (세션 토큰, user_id). 실패·잠금·비활성 계정이면 None.
    Raises:
        HTTPException: 503, 동시 검증 슬롯이 모두 찼을 때.
    """
    email = email.strip().lower()
    key = hashlib.sha256(email.encode()).hexdigest()
    with connection() as conn, conn.cursor() as cur:
        # [왜] 트랜잭션 단위 advisory lock 2칸(736125,1·2) 중 하나를 못 잡으면 scrypt를 돌리지 않고 503으로 돌려보낸다
        cur.execute("SELECT pg_try_advisory_xact_lock(736125, 1) OR pg_try_advisory_xact_lock(736125, 2)")
        if not cur.fetchone()[0]:
            raise HTTPException(status_code=503, detail="잠시 후 다시 시도해 주세요.")
        # [왜] 무작위 이메일로 시도 행이 끝없이 쌓이지 않게, 창·잠금이 끝난 행(지워도 같은 결과)과 만료 세션을 함께 지운다
        cur.execute("DELETE FROM auth_login_attempts WHERE (locked_until IS NULL OR locked_until <= CURRENT_TIMESTAMP) AND (window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes')")
        cur.execute("DELETE FROM auth_sessions WHERE expires_at <= CURRENT_TIMESTAMP")
        # [왜] 이메일 원문 대신 sha256(key)로 시도 기록을 남기고, 행이 없으면 만들어 아래 FOR UPDATE로 잠글 대상을 확보한다
        cur.execute("INSERT INTO auth_login_attempts (login_hash) VALUES (%s) ON CONFLICT DO NOTHING", (key,))
        cur.execute("SELECT failed_count, locked_until > CURRENT_TIMESTAMP, window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes' FROM auth_login_attempts WHERE login_hash = %s FOR UPDATE", (key,))
        count, locked, window_expired = cur.fetchone()  # 실패 횟수, 잠금 중 여부, 15분 집계 창이 끝났는지
        # [왜] 계정 행을 FOR UPDATE로 잠가 로그인과 계정 비활성화·세션 폐기가 동시에 끼어들지 않게 직렬화한다
        cur.execute("SELECT id, password_hash, is_active FROM users WHERE login_id = %s FOR UPDATE", (email,))
        user = cur.fetchone()
        if locked:
            return None
        # [주의] 없는 계정도 더미 해시로 같은 scrypt 비용을 치러 응답 시간으로 계정 존재를 알 수 없게 한다
        encoded = user[1] if user else "scrypt$" + "00" * 16 + "$" + "00" * 32
        valid = verify_password(password, encoded)
        if not user or not user[2] or not valid:
            # 창이 끝났으면 1부터 다시 세고, 아니면 누적한다. 5회째에 locked_until을 15분 뒤로 건다
            count = 1 if window_expired else count + 1
            cur.execute("UPDATE auth_login_attempts SET failed_count = %s, window_started_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE window_started_at END, locked_until = CASE WHEN %s >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE NULL END WHERE login_hash = %s", (count, window_expired, count, key))
            return None
        cur.execute("DELETE FROM auth_login_attempts WHERE login_hash = %s", (key,))  # 성공하면 실패 기록을 지운다
        token = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (session_token_hash(token), user[0]))
        return token, user[0]


def current_user(request: Request) -> tuple[int, str]:
    """세션 쿠키로 로그인한 사용자를 찾고 마지막 접속 시각을 갱신한다(FastAPI 의존성).

    Returns:
        (user_id, role). 비활성 계정·만료(절대 8시간)·유휴 30분 초과 세션은 인정하지 않는다.
    Raises:
        HTTPException: 401, 쿠키가 없거나 세션이 유효하지 않을 때.
    """
    token = request.cookies.get(COOKIE)
    # [주의] 비정상적으로 긴 토큰은 해시 계산 전에 거른다(정상 토큰은 43자)
    if not token or len(token) > 128:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    digest = session_token_hash(token)
    with connection() as conn, conn.cursor() as cur:
        # [왜] 유효성 검사(활성·절대 만료·유휴 30분)와 last_seen_at 갱신을 UPDATE 한 문장으로 해 검사와 갱신 사이 틈을 없앤다
        cur.execute("UPDATE auth_sessions s SET last_seen_at = CURRENT_TIMESTAMP FROM users u WHERE s.token_hash = %s AND s.user_id = u.id AND u.is_active AND s.expires_at > CURRENT_TIMESTAMP AND s.last_seen_at > CURRENT_TIMESTAMP - INTERVAL '30 minutes' RETURNING s.user_id, u.role", (digest,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return row[0], row[1]


def current_user_id(request: Request) -> int:
    """current_user에서 user_id만 돌려주는 FastAPI 의존성."""
    return current_user(request)[0]


def logout(request: Request) -> None:
    """요청 쿠키의 세션을 DB에서 지운다(쿠키가 없거나 너무 길면 무시)."""
    token = request.cookies.get(COOKIE)
    if token and len(token) <= 128:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (session_token_hash(token),))


def admin_users(actor_id: int) -> list[dict]:
    """전체 계정 목록을 id 순으로 돌려준다(요청자가 활성 관리자가 아니면 403)."""
    with connection() as conn:
        # [왜] 요청자 행을 FOR UPDATE로 잠가 권한 확인 중 관리자가 비활성화되는 경합을 막는다
        actor = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (actor_id,)).fetchone()
        if not actor or actor != ("admin", True):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        # [주의] password_hash는 SELECT하지 않아 응답에 해시가 나갈 수 없다
        rows = conn.execute("SELECT id, login_id, role, is_active FROM users ORDER BY id").fetchall()
        return [{"id": row[0], "email": row[1], "role": row[2], "is_active": row[3]} for row in rows]


def admin_set_active(actor_id: int, target_id: int, active: bool) -> None:
    """일반 계정의 활성 상태를 바꾸고, 비활성화하면 그 계정의 세션을 모두 지운다.

    요청자는 활성 관리자, 대상은 role=user여야 한다(관리자 계정은 변경 불가).
    Raises:
        HTTPException: 403 요청자가 관리자 아님·대상이 관리자, 404 대상 없음.
    """
    with connection() as conn:
        # [왜] 요청자·대상 행을 FOR UPDATE로 잠가 로그인(authenticate)과 동시에 일어나도 세션이 남지 않게 직렬화한다
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
            # [왜] 세션을 지워야 재활성화 후에도 예전 세션을 쓸 수 없다(SPEC 8.6절)
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (target_id,))


def delete_provisioned_user(user_id: int) -> bool:
    """비활성 일반 계정과 해당 세션·로그인 실패 행을 함께 삭제한다(운영자 CLI 전용)."""
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("A positive user ID is required")
    with connection() as conn:
        account = conn.execute("SELECT login_id FROM users WHERE id=%s", (user_id,)).fetchone()
        if not account:
            return False
        login_id = account[0]
        if not login_id.strip().lower().endswith("@example.test"):
            raise ValueError("Only synthetic @example.test accounts can be deleted by this command")
        login_hash = hashlib.sha256(login_id.strip().lower().encode()).hexdigest()
        # [왜] authenticate()와 같은 순서(실패 행 → 사용자 행)로 잠가 로그인과 삭제의 교착을 피한다
        conn.execute("INSERT INTO auth_login_attempts(login_hash) VALUES (%s) ON CONFLICT DO NOTHING", (login_hash,))
        conn.execute("SELECT login_hash FROM auth_login_attempts WHERE login_hash=%s FOR UPDATE", (login_hash,))
        current = conn.execute("SELECT login_id, role, is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if not current:
            conn.execute("DELETE FROM auth_login_attempts WHERE login_hash=%s", (login_hash,))
            return False
        if current[0].strip().lower() != login_id.strip().lower():
            raise ValueError("Account changed during deletion; retry after review")
        if current[1] != "user":
            raise ValueError("Administrator accounts cannot be deleted by this command")
        if current[2]:
            raise ValueError("Deactivate the account before deletion")
        conn.execute("DELETE FROM users WHERE id=%s", (user_id,))  # auth_sessions uses ON DELETE CASCADE
        conn.execute("DELETE FROM auth_login_attempts WHERE login_hash=%s", (login_hash,))
    return True


def provision() -> None:
    """계정 생성 CLI. users에 계정을 넣거나 `--hash-only`로 해시만 출력한다."""
    parser = argparse.ArgumentParser(description="Create a provisioned account or print a password hash")
    parser.add_argument("--role", choices=("user", "admin"), default="user")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--hash-only", action="store_true", help="print a scrypt hash without creating an account")
    action.add_argument("--delete-user-id", type=int, help="delete a disabled user account by ID")
    args = parser.parse_args()
    if args.delete_user_id is not None:
        if args.role != "user":
            sys.exit("Account deletion only supports the user role.")
        expected = str(args.delete_user_id)
        if input(f"Delete disabled user ID {expected}? Type the ID to confirm: ").strip() != expected:
            print("Deletion cancelled.")
            return
        try:
            deleted = delete_provisioned_user(args.delete_user_id)
        except ValueError as error:
            sys.exit(str(error))
        print("Account deleted." if deleted else "Account not found.")
        return
    email = None if args.hash_only else input("Email: ").strip().lower()
    # [주의] 비밀번호는 getpass로만 받아 화면·셸 기록·인자에 남기지 않는다
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    # 이메일 100자 이하(DB 길이), 비밀번호 12자 이상·1024바이트 이하(scrypt 비용 제한)·확인 입력 일치. 틀리면 sys.exit
    if (email is not None and not valid_email(email)) or len(password) < 12 or len(password.encode()) > 1024 or password != confirmation:
        sys.exit("Invalid email or password; use at least 12 characters and matching confirmation.")
    password_hash = hash_password(password)
    if args.hash_only:
        print(password_hash)
        return
    with connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, %s)", (email, password_hash, args.role))
    print("Account created.")


if __name__ == "__main__":
    provision()
