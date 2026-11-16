"""PostgreSQL 기반 인증(비밀번호 scrypt, DB 세션, 로그인 잠금, 자기 가입, 데모 버튼 로그인, 탈퇴의 계정 행 삭제, 관리자 계정 관리).

역할: 비밀번호는 scrypt로 해시해 users에 두고, 로그인하면 무작위 토큰을 만들어 그 해시(HMAC 또는 SHA-256)만
auth_sessions에 저장한다. 계정당 실패 5회는 15분 잠금(auth_login_attempts), 클라이언트 IP당 실패 30회도 15분 잠금
(auth_login_ip_attempts), 세션은 절대 8시간·유휴 2시간이다.
이메일 가입은 소유 확인 뒤 user 계정만 만들며, 인증 완료 시 IP당 UTC 하루 3회 한도를 적용한다(auth_email.py). 직접 signup 헬퍼는 내부/기존 회귀용이다.
Google 신원 확인 뒤 사용자가 명시적으로 일반 가입하거나 기존 계정의 비밀번호를 재확인한다. 관리자 최초 연결은 승인 CLI를 거친다.
호출자: backend/api/*.py(API 라우트, 로그인 경로는 backend/api/auth.py), tests/api/test_auth.py, 계정 생성 CLI(`python -m backend.auth`, `--hash-only`는 해시만 출력).
하지 않는 일: HTTP 라우트·쿠키 설정(backend/api/auth.py 등 backend/api/), 테이블 생성(db/*.sql), 메일 전송(services/mail.py)·이메일 토큰 처리(auth_email.py),
회로·대화·기억·견적의 사용자별 권한 검증(해당 기능 구현 후 추가).
출처: SPEC.md 4절(인증·가입·관리자 계약)·8.6절(로그인 AC), docs/specs/login-auth.md, backend/BACKEND.md.
읽는 환경변수: DATABASE_URL(필수), AUTH_SECRET(세션 토큰 HMAC 키, 32바이트 이상, DEMO_MODE!=1이면 필수),
DEMO_MODE(기본 1), AUTH_ORIGIN(허용 Origin, 기본 http://localhost:8000), K_SERVICE(Cloud Run이 넣음, 있으면 X-Forwarded-For로 IP 판단).
테이블 정의는 db/020_service_baseline.sql과 추가 인증 SQL 027·029·030, 관리자 작업 이력 034를 따른다. 옛 서비스 증분 SQL은 db/legacy/ 이력이다.
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
import httpx
from authlib.oidc.core import CodeIDToken
from fastapi import HTTPException, Request
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from backend.errors import ApiError

COOKIE = "sojafit_session"
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# [왜] scrypt 검증 한 번에 128MiB를 쓴다. authenticate()가 DB advisory lock 2칸으로 동시 검증을 2개까지만 허용한다.
# N=2**17(CPU·메모리 비용), R=블록 크기, P=병렬도. [주의] 바꾸면 기존 해시가 검증되지 않는다
N, R, P = 2**17, 8, 1
SIGNUP_IP_DAILY = 3  # 클라이언트 IP당 UTC 하루 가입 요청 상한(11-09 결정)
LOGIN_IP_FAILURES = 30  # 클라이언트 IP당 15분 로그인 실패 상한. 닿으면 그 IP를 15분 잠근다(11-09 결정)
# 데모 모드 버튼 로그인 계정(첫 데모 로그인 때 demo_session이 만든다). 로컬 데모 전용 일반 사용자이고 평가 계정이 아니다
DEMO_ACCOUNTS = {"a": "demo-a@example.test", "b": "demo-b@example.test"}
# [왜] scrypt 형식이 아닌 표식이라 verify_password가 늘 False다(비밀번호 로그인 불가). 버튼 로그인은 이 표식을 가진 계정만 받는다
DEMO_PASSWORD_HASH = "demo-button-login-only"


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


def validate_new_password(password: str) -> None:
    """새로 설정하는 암호만 검사한다. 기존 암호 검증·해시 형식은 바꾸지 않는다."""
    compact = re.sub(r'[\s\ufeff]', '', password)
    repeated = any(all(char == password[index % width] for index, char in enumerate(password))
                   for width in range(1, min(4, len(password)) + 1))
    if not 12 <= len(password) <= 1024 or not compact or compact.isdecimal() or repeated:
        raise ValueError('비밀번호는 12~1024자로, 공백뿐인 값·숫자만·단순 반복을 사용할 수 없습니다.')


def hash_password(password: str) -> str:
    """비밀번호를 salt와 scrypt로 해시해 `scrypt$<salt hex>$<digest hex>` 문자열로 돌려준다."""
    # [왜] 사용자마다 무작위 salt 16바이트를 써서 같은 비밀번호도 다른 해시가 되게 한다
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    """비밀번호가 저장 해시와 같은지 확인한다(형식이 깨진 해시는 예외 없이 False)."""
    if not isinstance(encoded, str):
        return False
    try:
        kind, salt, expected = encoded.split("$")
        if kind != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=N, r=R, p=P, dklen=32, maxmem=256 * 1024 * 1024)
        # [주의] 일반 ==는 틀린 위치에서 일찍 끝나 시간 차이가 생기므로 상수 시간 비교를 쓴다
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def purge_expired_sessions(conn) -> None:
    """만료된 auth_sessions 행을 지운다. [왜] 세션을 발급하는 모든 경로가 부르므로 만료 행이 쌓이지 않는다(인덱스 ix_auth_sessions_expires)."""
    conn.execute("DELETE FROM auth_sessions WHERE expires_at <= CURRENT_TIMESTAMP")


def connection():
    """DATABASE_URL로 새 PostgreSQL 연결을 연다(`with`로 쓰면 종료 때 커밋하고 닫는다)."""
    # [주의] 연결 실패는 psycopg.Error(공통 처리기가 503). 연결 대기는 5초로 제한한다
    url = os.getenv("DATABASE_URL")
    if not url:
        # [왜] 설정 누락도 DB를 쓸 수 없는 상태다. KeyError로 두면 공통 500이 되므로 DB 장애 처리기와 같은 문구의 503으로 낸다
        raise HTTPException(503, "저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.")
    return psycopg.connect(url, connect_timeout=5)


def create_google_state() -> tuple[str, str, str, str]:
    """브라우저에 묶인 10분짜리 일회용 Google 인증 상태를 만든다."""
    state, browser, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(4))
    with connection() as conn:
        conn.execute("DELETE FROM auth_google_states WHERE expires_at <= CURRENT_TIMESTAMP")
        conn.execute(
            "INSERT INTO auth_google_states (state_hash, browser_hash, verifier, nonce, expires_at) "
            "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes')",
            (session_token_hash(state), session_token_hash(browser), verifier, nonce),
        )
    return state, browser, verifier, nonce


def consume_google_state(state: str, browser: str) -> tuple[str, str] | None:
    """같은 브라우저에서 돌아온 유효한 상태를 원자적으로 한 번만 소비한다."""
    if not state or not browser or len(state) > 128 or len(browser) > 128:
        return None
    with connection() as conn:
        return conn.execute(
            "DELETE FROM auth_google_states WHERE state_hash = %s AND browser_hash = %s "
            "AND expires_at > CURRENT_TIMESTAMP RETURNING verifier, nonce",
            (session_token_hash(state), session_token_hash(browser)),
        ).fetchone()


def verify_google_id_token(token: str, jwks: dict, client_id: str, nonce: str) -> tuple[str, str, str] | None:
    """Google의 서명과 OIDC 필수 항목을 확인하고 안정적인 식별자만 돌려준다."""
    if not client_id or not nonce or not isinstance(token, str) or not token or len(token) > 16384:
        return None
    try:
        decoded = jwt.decode(token, KeySet.import_key_set(jwks), algorithms=["RS256"])
        claims = CodeIDToken(
            decoded.claims, decoded.header,
            options={"iss": {"essential": True, "values": ["accounts.google.com", "https://accounts.google.com"]}, "aud": {"essential": True, "value": client_id}},
            params={"nonce": nonce, "client_id": client_id},
        )
        claims.validate(leeway=30)  # Google과 서버의 작은 시계 오차만 허용한다.
        subject, email = claims.get("sub"), claims.get("email")
        if not isinstance(subject, str) or not subject or len(subject) > 255 or not isinstance(email, str) or not valid_email(email) or claims.get("email_verified") is not True:
            return None
        return "https://accounts.google.com", subject, email
    except (JoseError, ValueError, TypeError, KeyError):
        return None


def fetch_google_identity(code: str, verifier: str, nonce: str) -> tuple[str, str, str] | None:
    """Google에 인증 코드를 교환하고 ID 토큰을 검증한다. 토큰은 저장하지 않는다."""
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    redirect_uri = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/") + "/api/auth/google/callback"
    response = httpx.post("https://oauth2.googleapis.com/token", data={"grant_type": "authorization_code", "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "code": code, "code_verifier": verifier}, timeout=10, follow_redirects=False)
    response.raise_for_status()
    token = response.json()
    if not isinstance(token, dict):
        return None
    response = httpx.get("https://www.googleapis.com/oauth2/v3/certs", timeout=10, follow_redirects=False)
    response.raise_for_status()
    jwks = response.json()
    if not isinstance(jwks, dict):
        return None
    return verify_google_id_token(token.get("id_token", ""), jwks, client_id, nonce)


def request_google_link(issuer: str, subject: str, email: str) -> str:
    request_id = secrets.token_urlsafe(24)
    with connection() as conn:
        conn.execute("DELETE FROM auth_google_pending WHERE expires_at <= CURRENT_TIMESTAMP")
        conn.execute(
            "INSERT INTO auth_google_pending (request_id, issuer, subject, email, expires_at) "
            "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '15 minutes')",
            (request_id, issuer, subject, email),
        )
    return request_id


def google_pending_email(request_id: str) -> str | None:
    if not request_id or len(request_id) > 128:
        return None
    with connection() as conn:
        row = conn.execute("SELECT email FROM auth_google_pending WHERE request_id=%s AND expires_at > CURRENT_TIMESTAMP", (request_id,)).fetchone()
    return row[0] if row else None


def approve_google_link(request_id: str, user_id: int, email: str) -> bool:
    with connection() as conn:
        pending = conn.execute("SELECT issuer, subject, email FROM auth_google_pending WHERE request_id=%s AND expires_at > CURRENT_TIMESTAMP FOR UPDATE", (request_id,)).fetchone()
        if not pending or not hmac.compare_digest(pending[2].encode("utf-8"), email.encode("utf-8")):
            return False
        user = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if user != ("admin", True):
            return False
        result = conn.execute("INSERT INTO auth_google_identities (issuer, subject, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING user_id", (pending[0], pending[1], user_id)).fetchone()
        if not result:
            return False
        conn.execute("DELETE FROM auth_google_pending WHERE request_id=%s", (request_id,))
        return True


def google_session(issuer: str, subject: str, *, admin_only: bool = False) -> tuple[str, int] | None:
    with connection() as conn:
        identity = conn.execute("SELECT user_id FROM auth_google_identities WHERE issuer=%s AND subject=%s", (issuer, subject)).fetchone()
        if not identity:
            return None
        user_id = identity[0]
        user = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if not user or not user[1] or (admin_only and user[0] != "admin") or not conn.execute("SELECT 1 FROM auth_google_identities WHERE issuer=%s AND subject=%s AND user_id=%s", (issuer, subject, user_id)).fetchone():
            return None
        token = secrets.token_urlsafe(32)
        purge_expired_sessions(conn)
        conn.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (session_token_hash(token), user_id))
        return token, user_id


def google_admin_session(issuer: str, subject: str) -> tuple[str, int] | None:
    return google_session(issuer, subject, admin_only=True)


def complete_google_user(request_id: str, ip: str, *, user_id: int | None = None) -> tuple[str, int]:
    """검증된 pending을 일반 계정에만 연결하고 같은 트랜잭션에서 소비·세션 발급한다.

    user_id는 HTTP 호출자가 비밀번호를 재검증한 계정 ID만 넘긴다. 관리자 연결은 기존 운영자 CLI만 담당한다.
    """
    if not request_id or len(request_id) > 128:
        raise HTTPException(400, 'Google 인증이 만료되었습니다. 다시 시작해 주세요.')
    try:
        with connection() as conn:
            pending = conn.execute('SELECT issuer,subject,email FROM auth_google_pending WHERE request_id=%s '
                'AND expires_at>CURRENT_TIMESTAMP FOR UPDATE', (request_id,)).fetchone()
            if not pending:
                raise HTTPException(400, 'Google 인증이 만료되었습니다. 다시 시작해 주세요.')
            issuer, subject, email = pending
            if conn.execute('SELECT 1 FROM auth_google_identities WHERE issuer=%s AND subject=%s', (issuer, subject)).fetchone():
                raise HTTPException(409, '이미 연결된 Google 계정입니다. Google 로그인을 다시 시작해 주세요.')
            if user_id is None:
                if conn.execute('SELECT 1 FROM users WHERE login_id=%s', (email.strip().lower(),)).fetchone():
                    raise HTTPException(409, '기존 계정의 이메일과 비밀번호로 본인 확인 후 연결해 주세요.')
                _signup_slot(conn, ip)
                user_id = conn.execute("INSERT INTO users(login_id,password_hash,role,email_verified_at) VALUES (%s,NULL,'user',CURRENT_TIMESTAMP) RETURNING id",
                                       (email.strip().lower(),)).fetchone()[0]
            else:
                account = conn.execute('SELECT role,is_active FROM users WHERE id=%s FOR UPDATE', (user_id,)).fetchone()
                if account != ('user', True):
                    raise HTTPException(409, '활성 일반 계정만 직접 연결할 수 있습니다. 관리자는 운영자 연결 승인이 필요합니다.')
            conn.execute('INSERT INTO auth_google_identities(issuer,subject,user_id) VALUES (%s,%s,%s)', (issuer,subject,user_id))
            conn.execute('DELETE FROM auth_google_pending WHERE request_id=%s', (request_id,))
            token = secrets.token_urlsafe(32)
            purge_expired_sessions(conn)
            conn.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP+INTERVAL '8 hours')",
                         (session_token_hash(token),user_id))
            return token, user_id
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, '이미 가입되었거나 다른 Google 계정이 연결되어 있습니다. 기존 로그인으로 확인해 주세요.') from None


def revoke_google_link(user_id: int) -> bool:
    with connection() as conn:
        if not conn.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone():
            return False
        removed = conn.execute("DELETE FROM auth_google_identities WHERE user_id=%s RETURNING user_id", (user_id,)).fetchone()
        if removed:
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (user_id,))
        return bool(removed)


def deactivate_admin(user_id: int) -> bool:
    """운영자가 관리자를 비활성화하고 모든 세션을 같은 트랜잭션에서 폐기한다."""
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(736126)")
        user = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if user != ("admin", True):
            return False
        other = conn.execute("SELECT 1 FROM users WHERE role='admin' AND is_active AND id<>%s LIMIT 1", (user_id,)).fetchone()
        if not other:
            return False
        conn.execute("UPDATE users SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (user_id,))
        conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (user_id,))
        return True


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
    """상태를 바꾸는 요청의 Origin 헤더가 AUTH_ORIGIN과 같은지 확인한다(다르면 403 `ORIGIN_MISMATCH`)."""
    # [왜] 쿠키 세션은 다른 사이트의 요청에도 따라붙으므로 Origin을 대조해 CSRF를 막는다
    origin = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/")
    if request.headers.get("origin") != origin:
        # [왜] 권한 없음(FORBIDDEN)과 화면 안내가 다르다: 접속 주소 · 배포 설정(AUTH_ORIGIN)을 확인하게 한다(ADR 0019)
        raise ApiError(403, "요청 출처를 확인할 수 없습니다.", code="ORIGIN_MISMATCH")


def authenticate(email: str, password: str, ip: str, *, issue_session: bool = True) -> tuple[str, int] | None:
    """이메일·비밀번호를 검증하고 성공하면 새 세션을 만든다.

    scrypt 동시 검증은 DB advisory lock 2칸으로 제한한다(메모리 보호). 계정당 실패 5회(15분 창)면 15분 잠금,
    클라이언트 IP당 실패 LOGIN_IP_FAILURES회(15분 창)면 그 IP를 15분 잠근다(여러 계정에 나눠 보내는 대입 방어).
    없는 계정도 같은 비용으로 검증해 응답 시간 차이(timing attack)로 계정 존재를 알 수 없게 한다.

    Args:
        email: 로그인 이메일(공백 제거·소문자로 맞춘다).
        password: 평문 비밀번호.
        ip: client_ip()가 돌려준 값. 원문 대신 키 해시만 저장한다.
    Returns:
        (세션 토큰, user_id). issue_session=False는 본인 확인만 하고 빈 토큰을 돌려준다. 실패·계정 잠금·IP 잠금·비활성 계정이면 None(호출자가 같은 401로 돌려 잠금을 드러내지 않는다).
    Raises:
        HTTPException: 503, 동시 검증 슬롯이 모두 찼을 때.
    """
    email = email.strip().lower()
    key = hashlib.sha256(email.encode()).hexdigest()
    ip_key = session_token_hash(ip)  # [왜] 가입 한도와 같은 키 해시라 IP 원문이 DB에 남지 않는다
    with connection() as conn, conn.cursor() as cur:
        # [왜] 트랜잭션 단위 advisory lock 2칸(736125,1·2) 중 하나를 못 잡으면 scrypt를 돌리지 않고 503으로 돌려보낸다
        cur.execute("SELECT pg_try_advisory_xact_lock(736125, 1) OR pg_try_advisory_xact_lock(736125, 2)")
        if not cur.fetchone()[0]:
            raise HTTPException(status_code=503, detail="잠시 후 다시 시도해 주세요.")
        # [왜] 무작위 이메일로 시도 행이 끝없이 쌓이지 않게, 창·잠금이 끝난 행(지워도 같은 결과)과 만료 세션을 함께 지운다
        cur.execute("DELETE FROM auth_login_attempts WHERE (locked_until IS NULL OR locked_until <= CURRENT_TIMESTAMP) AND (window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes')")
        cur.execute("DELETE FROM auth_login_ip_attempts WHERE (locked_until IS NULL OR locked_until <= CURRENT_TIMESTAMP) AND (window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes')")
        purge_expired_sessions(cur)
        # [왜] 이메일 원문 대신 sha256(key)로 시도 기록을 남기고, 행이 없으면 만들어 아래 FOR UPDATE로 잠글 대상을 확보한다
        cur.execute("INSERT INTO auth_login_attempts (login_hash) VALUES (%s) ON CONFLICT DO NOTHING", (key,))
        cur.execute("SELECT failed_count, locked_until > CURRENT_TIMESTAMP, window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes' FROM auth_login_attempts WHERE login_hash = %s FOR UPDATE", (key,))
        count, locked, window_expired = cur.fetchone()  # 실패 횟수, 잠금 중 여부, 15분 집계 창이 끝났는지
        # [왜] IP 행도 같은 방식(없으면 만들고 FOR UPDATE)으로 잡는다. 잠그는 순서는 계정 시도 행 → IP 행 → 사용자 행으로 고정해 교착을 피한다
        cur.execute("INSERT INTO auth_login_ip_attempts (ip_hash) VALUES (%s) ON CONFLICT DO NOTHING", (ip_key,))
        cur.execute("SELECT failed_count, locked_until > CURRENT_TIMESTAMP, window_started_at IS NULL OR window_started_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes' FROM auth_login_ip_attempts WHERE ip_hash = %s FOR UPDATE", (ip_key,))
        ip_count, ip_locked, ip_window_expired = cur.fetchone()
        # [왜] 계정 행을 FOR UPDATE로 잠가 로그인과 계정 비활성화·세션 폐기가 동시에 끼어들지 않게 직렬화한다
        cur.execute("SELECT id, password_hash, is_active FROM users WHERE login_id = %s FOR UPDATE", (email,))
        user = cur.fetchone()
        # [주의] 잠긴 동안은 비밀번호가 맞아도 거절하고 횟수도 올리지 않는다(계정·IP 같은 규칙)
        if locked or ip_locked:
            return None
        # [주의] 없는 계정도 더미 해시로 같은 scrypt 비용을 치러 응답 시간으로 계정 존재를 알 수 없게 한다
        encoded = user[1] if user and user[1] else "scrypt$" + "00" * 16 + "$" + "00" * 32
        valid = verify_password(password, encoded)
        if not user or not user[1] or not user[2] or not valid:
            # 창이 끝났으면 1부터 다시 세고, 아니면 누적한다. 5회째에 locked_until을 15분 뒤로 건다
            count = 1 if window_expired else count + 1
            cur.execute("UPDATE auth_login_attempts SET failed_count = %s, window_started_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE window_started_at END, locked_until = CASE WHEN %s >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE NULL END WHERE login_hash = %s", (count, window_expired, count, key))
            # IP도 같은 규칙: 창이 끝났으면 1부터, LOGIN_IP_FAILURES회째에 15분 잠금
            ip_count = 1 if ip_window_expired else ip_count + 1
            cur.execute("UPDATE auth_login_ip_attempts SET failed_count = %s, window_started_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE window_started_at END, locked_until = CASE WHEN %s >= %s THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE NULL END WHERE ip_hash = %s", (ip_count, ip_window_expired, ip_count, LOGIN_IP_FAILURES, ip_key))
            return None
        cur.execute("DELETE FROM auth_login_attempts WHERE login_hash = %s", (key,))  # 성공하면 그 계정의 실패 기록을 지운다
        # [주의] IP 실패 기록은 성공해도 지우지 않는다. 지우면 공격자가 자기 계정 로그인을 끼워 넣어 IP 횟수를 계속 되돌릴 수 있다
        if not issue_session:
            return '', user[0]  # 연결 성공 전에는 로그인 세션을 만들지 않는다.
        token = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (session_token_hash(token), user[0]))
        return token, user[0]


def client_ip(request: Request) -> str:
    """요청한 클라이언트 IP. Cloud Run에서는 X-Forwarded-For의 마지막 값, 그 밖에서는 소켓 주소."""
    # [왜] Cloud Run(run.app 직접 호출)은 Google 프런트엔드가 접속한 클라이언트 IP를 X-Forwarded-For 끝에 덧붙이고,
    # 그 앞의 값은 클라이언트가 보낸 것이라 위조할 수 있다. 그래서 마지막 값만 쓴다. 소켓 주소는 Google 내부 주소라 쓸 수 없다.
    # 출처: https://docs.cloud.google.com/load-balancing/docs/https#x-forwarded-for_header (Google이 덧붙인 값만 신뢰, 앞 값은 클라이언트가 보낸 것),
    # https://github.com/GoogleCloudPlatform/nodejs-docs-samples/pull/3586 (Google의 Cloud Run 샘플이 프록시 1단 = 마지막 값만 신뢰),
    # https://docs.cloud.google.com/run/docs/container-contract (K_SERVICE는 Cloud Run이 모든 컨테이너에 넣는 변수)
    # [주의] Cloud Run 앞에 외부 부하분산기를 두면 마지막 값이 부하분산기 IP가 되어 모두 한 IP로 묶인다. 그때는 끝에서 두 번째 값으로 바꾼다
    forwarded = ",".join(request.headers.getlist("x-forwarded-for"))
    if os.getenv("K_SERVICE") and forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    # [주의] 로컬·Compose에서는 X-Forwarded-For를 믿지 않는다(앞에 Google 프런트엔드가 없어 누구나 넣을 수 있음)
    return request.client.host if request.client else ""


def _signup_slot(conn, ip):
    conn.execute("DELETE FROM auth_signup_attempts WHERE day < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date")  # 지난 날짜 행은 결과에 영향이 없어 지운다
    # [왜] 행을 만들거나 1 올리는 문장 하나로 같은 IP의 동시 요청을 직렬화하고, 상한에 닿았으면 행을 돌려주지 않는다
    result = conn.execute(
        "INSERT INTO auth_signup_attempts (ip_hash, day) VALUES (%s, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date) "
        "ON CONFLICT (ip_hash, day) DO UPDATE SET signup_count = auth_signup_attempts.signup_count + 1 "
        "WHERE auth_signup_attempts.signup_count < %s RETURNING signup_count",
        (session_token_hash(ip), SIGNUP_IP_DAILY),
    )
    if not result.fetchone():
        raise HTTPException(status_code=429, detail="오늘 이 네트워크에서 가입할 수 있는 횟수를 넘었습니다.")


def signup(email: str, password: str, ip: str) -> tuple[str, int] | None:
    """승인 없이 일반 사용자(role=user) 계정을 만들고 바로 새 세션을 발급한다.

    클라이언트 IP당 UTC 하루 SIGNUP_IP_DAILY회까지 받는다. 중복 이메일도 1회로 센다(409가 계정 존재를 알려 주므로
    존재 확인 남용도 같은 한도로 묶는다). 한도 초과·503은 트랜잭션이 되돌려져 세지 않는다.

    Args:
        email: 가입 이메일(공백 제거·소문자로 맞춘다).
        password: 평문 비밀번호(길이 검증은 호출자 backend/api/auth.py가 한다).
        ip: client_ip()가 돌려준 값. 원문 대신 키 해시만 저장한다.
    Returns:
        (세션 토큰, user_id). 이미 있는 이메일이면 None(호출자가 409).
    Raises:
        HTTPException: 429 IP 하루 한도 초과, 503 동시 scrypt 슬롯이 모두 찼을 때.
    """
    email = email.strip().lower()
    with connection() as conn, conn.cursor() as cur:
        _signup_slot(conn, ip)
        # [왜] scrypt 한 번에 128MiB를 쓰므로 로그인(authenticate)과 같은 advisory lock 2칸을 나눠 써 동시 계산을 2개로 묶는다
        cur.execute("SELECT pg_try_advisory_xact_lock(736125, 1) OR pg_try_advisory_xact_lock(736125, 2)")
        if not cur.fetchone()[0]:
            raise HTTPException(status_code=503, detail="잠시 후 다시 시도해 주세요.")
        cur.execute("INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, 'user') ON CONFLICT (login_id) DO NOTHING RETURNING id", (email, hash_password(password)))
        user = cur.fetchone()
        if not user:
            return None  # [주의] 예외 없이 끝내야 위 가입 횟수가 커밋된다
        purge_expired_sessions(cur)
        token = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (session_token_hash(token), user[0]))
        return token, user[0]


def demo_session(account: str) -> tuple[str, int] | None:
    """데모 버튼 로그인: 데모 계정(A · B)에 새 세션을 발급한다. 계정이 없으면 이 때 만든다(11-11 결정: 007 시드 대신).

    [주의] DEMO_MODE=1이 아니면 계정을 만들지 않고 None이다(호출자 backend/api/auth.py도 먼저 404로 막는다).
    정해진 이메일이고, 비밀번호 표식(DEMO_PASSWORD_HASH)을 가진 활성 일반 사용자일 때만 세션을 준다.
    같은 이메일로 가입한 계정(비밀번호 해시가 있음) · 관리자 · 비활성 계정에는 세션을 주지 않는다.
    Returns:
        (세션 토큰, user_id). 세션을 줄 수 없으면 None(호출자가 404).
    """
    if os.getenv("DEMO_MODE", "1") != "1":
        return None
    find = "SELECT id FROM users WHERE login_id=%s AND password_hash=%s AND role='user' AND is_active FOR UPDATE"
    args = (DEMO_ACCOUNTS[account], DEMO_PASSWORD_HASH)
    with connection() as conn:
        # [왜] 로그인 · 비활성화와 같이 사용자 행을 FOR UPDATE로 잠가 비활성화와 세션 발급이 엇갈리지 않게 한다
        user = conn.execute(find, args).fetchone()
        if not user:
            # [왜] 없을 때만 넣는다(DO NOTHING은 id 번호만 소모). 동시 첫 로그인이 겹쳐도 login_id UNIQUE로 한 행만 남고, 다시 찾는다
            conn.execute("INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, 'user') ON CONFLICT (login_id) DO NOTHING", args[:2])
            user = conn.execute(find, args).fetchone()
        if not user:
            return None
        purge_expired_sessions(conn)
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '8 hours')", (session_token_hash(token), user[0]))
        return token, user[0]


def current_user(request: Request) -> tuple[int, str]:
    """세션 쿠키로 로그인한 사용자를 찾고 마지막 접속 시각을 갱신한다(FastAPI 의존성).

    Returns:
        (user_id, role). 비활성 계정·만료(절대 8시간)·유휴 2시간 초과 세션은 인정하지 않는다.
    Raises:
        HTTPException: 401, 쿠키가 없거나 세션이 유효하지 않을 때.
    """
    token = request.cookies.get(COOKIE)
    # [주의] 비정상적으로 긴 토큰은 해시 계산 전에 거른다(정상 토큰은 43자)
    if not token or len(token) > 128:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    digest = session_token_hash(token)
    with connection() as conn, conn.cursor() as cur:
        # [왜] 유효성 검사(활성·절대 만료·유휴 2시간)와 last_seen_at 갱신을 UPDATE 한 문장으로 해 검사와 갱신 사이 틈을 없앤다
        cur.execute("UPDATE auth_sessions s SET last_seen_at = CURRENT_TIMESTAMP FROM users u WHERE s.token_hash = %s AND s.user_id = u.id AND u.is_active AND s.expires_at > CURRENT_TIMESTAMP AND s.last_seen_at > CURRENT_TIMESTAMP - INTERVAL '2 hours' RETURNING s.user_id, u.role", (digest,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return row[0], row[1]


def current_user_id(request: Request) -> int:
    """current_user에서 user_id만 돌려주는 FastAPI 의존성."""
    return current_user(request)[0]


def account_email(user_id: int) -> str:
    """이미 인증된 본인 계정의 로그인 이메일을 읽는다."""
    with connection() as conn:
        row = conn.execute('SELECT login_id FROM users WHERE id=%s AND is_active', (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return row[0]


def logout(request: Request) -> None:
    """요청 쿠키의 세션을 DB에서 지운다(쿠키가 없거나 너무 길면 무시)."""
    token = request.cookies.get(COOKIE)
    if token and len(token) <= 128:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (session_token_hash(token),))


def _require_admin(conn, actor_id: int) -> None:
    """요청자가 활성 관리자가 아니면 403. [왜] 요청자 행을 FOR UPDATE로 잠가 권한 확인 중 관리자가 비활성화되는 경합을 막는다."""
    actor = conn.execute("SELECT role, is_active FROM users WHERE id=%s FOR UPDATE", (actor_id,)).fetchone()
    if not actor or actor != ("admin", True):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def _audit(conn, actor_id: int, target_id: int, email: str, action: str, reason: str | None = None) -> None:
    """관리자 작업 이력(admin_audit, db/034) 한 줄. INSERT만 한다. 대상은 가린 이메일로만 남긴다(탈퇴 뒤에도 누구였는지 알아볼 정도)."""
    conn.execute("INSERT INTO admin_audit(actor_id,target_id,target_email_masked,action,fields,reason) VALUES (%s,%s,%s,%s,%s,%s)",
                 (actor_id, target_id, mask_email(email), action, ["email"] if action == "unmask" else [], reason))


def admin_users(actor_id: int) -> list[dict]:
    """전체 계정 목록을 id 순으로 돌려준다(요청자가 활성 관리자가 아니면 403)."""
    with connection() as conn:
        _require_admin(conn, actor_id)
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
        email = _lock_user_target(conn, actor_id, target_id)
        conn.execute("UPDATE users SET is_active=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (active, target_id))
        if not active:
            # [왜] 세션을 지워야 재활성화 후에도 예전 세션을 쓸 수 없다(SPEC 8.6절)
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (target_id,))
        _audit(conn, actor_id, target_id, email, "activate" if active else "deactivate")


def _lock_user_target(conn, actor_id: int, target_id: int) -> str:
    """요청자가 활성 관리자이고 대상이 일반 계정(user)인지 잠가서 확인하고 대상 이메일을 돌려준다.

    Raises:
        HTTPException: 403 요청자가 관리자 아님 · 대상이 관리자(자기 자신 포함), 404 대상 없음.
    """
    _require_admin(conn, actor_id)
    target = conn.execute("SELECT role, login_id FROM users WHERE id=%s FOR UPDATE", (target_id,)).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if target[0] != "user":
        raise HTTPException(status_code=403, detail="관리자 계정은 변경할 수 없습니다.")
    return target[1]


def admin_check_deletable(actor_id: int, target_id: int) -> None:
    """탈퇴 처리 전 확인: 요청자는 활성 관리자, 대상은 자기 자신이 아닌 일반 계정. 분석 기록을 지우기 전에 부른다(403 · 404)."""
    if actor_id == target_id:
        raise HTTPException(status_code=403, detail="자기 계정은 이 기능으로 지울 수 없습니다.")
    with connection() as conn:
        _lock_user_target(conn, actor_id, target_id)


def admin_unmask(actor_id: int, target_id: int, reason: str) -> str:
    """사유를 이력에 먼저 남기고 대상 한 명의 이메일 원문을 돌려준다(관리자 전용).

    [주의] 이력 INSERT와 원문 읽기는 한 트랜잭션이라 기록이 실패하면 원문이 나가지 않는다. 원문은 로그에 적지 않는다.
    Raises:
        HTTPException: 403 요청자가 관리자 아님, 404 대상 없음(이력도 남기지 않는다).
    """
    with connection() as conn:
        _require_admin(conn, actor_id)
        target = conn.execute("SELECT login_id FROM users WHERE id=%s", (target_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
        _audit(conn, actor_id, target_id, target[0], "unmask", reason)
        return target[0]


def admin_audit_log(actor_id: int, limit: int = 100) -> list[dict]:
    """관리자 작업 이력을 최근 순으로 돌려준다(요청자가 활성 관리자가 아니면 403). 처리한 관리자 이메일은 가린다."""
    with connection() as conn:
        _require_admin(conn, actor_id)
        rows = conn.execute("SELECT a.id,a.actor_id,u.login_id,a.target_id,a.target_email_masked,a.action,a.fields,a.reason,a.created_at "
                            "FROM admin_audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT %s", (limit,)).fetchall()
    return [{"id": r[0], "actor_id": r[1], "actor_email": mask_email(r[2] or ""), "target_id": r[3], "target_email": r[4],
             "action": r[5], "fields": r[6], "reason": r[7], "created_at": r[8]} for r in rows]


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


def delete_account(user_id: int, actor_id: int | None = None) -> dict:
    """탈퇴의 마지막 단계: 일반 계정 행을 지우고 지운 건수를 돌려준다(backend/api/profile.py `DELETE /api/me`가 분석 기록 · 기억을 지운 뒤 부른다).

    계정 행을 지우면 세션 · 프로젝트(회로 · 대화 · run · 메시지) · 승인 · 견적 · 승인 사례 · 분석 사용량이 FK cascade로 함께 지워진다.
    그 이메일의 로그인 실패 기록도 지운다. 계정이 이미 없으면 모두 0이다.
    actor_id(관리자의 탈퇴 처리 `DELETE /api/admin/users/{id}`)를 주면 계정 행을 지우는 같은 트랜잭션에서 관리자 작업 이력을 남긴다.
    Raises:
        HTTPException: 409 관리자 계정(운영자 CLI `--delete-user-id`도 관리자는 지우지 않는다).
    """
    with connection() as conn:
        account = conn.execute("SELECT login_id FROM users WHERE id=%s", (user_id,)).fetchone()
        if not account:
            return {"projects": 0, "quotes": 0, "account": 0}
        login_hash = hashlib.sha256(account[0].strip().lower().encode()).hexdigest()
        # [왜] authenticate()와 같은 순서(실패 행 → 사용자 행)로 잠가 같은 이메일의 로그인과 교착하지 않는다
        conn.execute("INSERT INTO auth_login_attempts(login_hash) VALUES (%s) ON CONFLICT DO NOTHING", (login_hash,))
        conn.execute("SELECT login_hash FROM auth_login_attempts WHERE login_hash=%s FOR UPDATE", (login_hash,))
        current = conn.execute("SELECT role FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if current and current[0] != "user":
            raise HTTPException(status_code=409, detail="관리자 계정은 이 기능으로 삭제할 수 없습니다.")
        if actor_id is not None and current:
            _audit(conn, actor_id, user_id, account[0], "delete")  # 계정 행 삭제와 함께 커밋되거나 함께 취소된다
        counts = {"projects": conn.execute("SELECT count(*) FROM projects WHERE user_id=%s", (user_id,)).fetchone()[0],
                  "quotes": conn.execute("SELECT count(*) FROM quotes WHERE user_id=%s", (user_id,)).fetchone()[0],
                  "account": conn.execute("DELETE FROM users WHERE id=%s", (user_id,)).rowcount}
        conn.execute("DELETE FROM auth_login_attempts WHERE login_hash=%s", (login_hash,))
    return counts


def provision() -> None:
    """계정 생성 CLI. users에 계정을 넣거나 `--hash-only`로 해시만 출력한다."""
    parser = argparse.ArgumentParser(description="Create a provisioned account or print a password hash")
    parser.add_argument("--role", choices=("user", "admin"), default="user")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--hash-only", action="store_true", help="print a scrypt hash without creating an account")
    action.add_argument("--delete-user-id", type=int, help="delete a disabled user account by ID")
    action.add_argument("--revoke-google-user-id", type=int, help="revoke a Google link and its existing sessions")
    action.add_argument("--disable-admin-id", type=int, help="disable an administrator and revoke all sessions")
    action.add_argument("--approve-google", action="store_true", help="approve a verified Google link request")
    args = parser.parse_args()
    if args.approve_google:
        request_id = input("Google request ID: ").strip()
        try:
            user_id = int(input("Existing administrator ID: ").strip())
        except ValueError:
            sys.exit("A positive administrator ID is required.")
        email = input("Verified Google email: ").strip()
        if not request_id or len(request_id) > 128 or user_id <= 0 or not valid_email(email):
            sys.exit("Invalid request ID, administrator ID or email.")
        print("Google link approved." if approve_google_link(request_id, user_id, email) else "Google link was not approved.")
        return
    if args.revoke_google_user_id is not None:
        user_id = args.revoke_google_user_id
        if user_id <= 0 or input(f"Revoke Google link and sessions for user ID {user_id}? Type the ID: ").strip() != str(user_id):
            print("Revocation cancelled.")
            return
        print("Google link revoked." if revoke_google_link(user_id) else "Google link not found.")
        return
    if args.disable_admin_id is not None:
        user_id = args.disable_admin_id
        if user_id <= 0 or input(f"Disable administrator ID {user_id} and revoke all sessions? Type the ID: ").strip() != str(user_id):
            print("Deactivation cancelled.")
            return
        print("Administrator disabled." if deactivate_admin(user_id) else "Administrator not disabled; another active administrator is required.")
        return
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
