"""이메일 인증 가입·암호 재설정의 토큰/DB 경계. 기존 계정 로그인은 auth.py에 둔다.

호출자: api/auth.py. 읽는 설정은 auth.connection의 DATABASE_URL 및 services.mail 설정.
토큰 원문은 SMTP로만 보내고 DB/로그/응답에 남기지 않는다. 029 SQL 준비가 필요하다.
"""
import hashlib
import logging
import secrets

from fastapi import HTTPException

from backend import auth
from backend.services import mail

LOGGER = logging.getLogger(__name__)


def _reserve(conn, key: str, limit: int, period: str = 'hour') -> None:
    row = conn.execute("""
        INSERT INTO auth_email_send_limits(key_hash,window_start,request_count)
        VALUES (%s,date_trunc(%s,CURRENT_TIMESTAMP),1)
        ON CONFLICT (key_hash) DO UPDATE SET
          request_count=CASE WHEN auth_email_send_limits.window_start < date_trunc(%s,CURRENT_TIMESTAMP)
                             THEN 1 ELSE auth_email_send_limits.request_count+1 END,
          window_start=date_trunc(%s,CURRENT_TIMESTAMP)
        WHERE auth_email_send_limits.window_start < date_trunc(%s,CURRENT_TIMESTAMP)
           OR auth_email_send_limits.request_count < %s
        RETURNING request_count
    """, (auth.session_token_hash(key), period, period, period, period, limit)).fetchone()
    if not row:
        raise HTTPException(429, '메일 요청이 많습니다. 잠시 후 다시 시도해 주세요.')


def request_email(email: str, ip: str, purpose: str) -> None:
    if not mail.configured():
        raise HTTPException(503, '메일 인증 서비스를 준비 중입니다. 잠시 후 다시 시도해 주세요.')
    token = None
    with auth.connection() as conn:
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        conn.execute("DELETE FROM auth_email_send_limits WHERE window_start < date_trunc('day',CURRENT_TIMESTAMP)")
        conn.execute('DELETE FROM auth_email_challenges WHERE expires_at <= CURRENT_TIMESTAMP')
        _reserve(conn, 'mail-service', 200, 'day')
        _reserve(conn, 'mail-ip:' + ip, 10)
        _reserve(conn, 'mail-email:' + purpose + ':' + email, 5)
        user = conn.execute("SELECT id,is_active,left(password_hash,7)='scrypt$' FROM users WHERE login_id=%s", (email,)).fetchone()
        # shortcut: 직접 SMTP 시간 차이는 숨기지 못한다. 공개 대규모 운영 시 내구성 있는 발송 큐로 전환한다.
        eligible = not user if purpose == 'signup' else bool(user and user[1] and user[2])
        if not eligible:
            return
        token = secrets.token_urlsafe(32)
        row = conn.execute("""
            INSERT INTO auth_email_challenges(email,purpose,token_hash,user_id,expires_at)
            VALUES(%s,%s,%s,%s,CURRENT_TIMESTAMP + (%s * INTERVAL '1 minute'))
            ON CONFLICT(email,purpose) DO UPDATE SET token_hash=EXCLUDED.token_hash,
              user_id=EXCLUDED.user_id,created_at=CURRENT_TIMESTAMP,expires_at=EXCLUDED.expires_at
            WHERE auth_email_challenges.created_at <= CURRENT_TIMESTAMP-INTERVAL '60 seconds'
            RETURNING email
        """, (email, purpose, auth.session_token_hash(token), user[0] if user else None, 60 if purpose == 'signup' else 15)).fetchone()
        if not row:
            token = None
    # SMTP 장애가 DB 트랜잭션/행 잠금을 붙들거나 계정 존재 여부를 응답으로 드러내지 않게 한다.
    if token:
        try:
            mail.send_link(email, purpose, token)
        except Exception:
            LOGGER.warning('auth_mail_delivery_failed')


def complete(token: str, password: str, purpose: str, ip: str) -> None:
    auth.validate_new_password(password)
    with auth.connection() as conn:
        challenge = conn.execute('SELECT email,user_id FROM auth_email_challenges WHERE token_hash=%s AND purpose=%s '
                                 'AND expires_at>CURRENT_TIMESTAMP FOR UPDATE', (auth.session_token_hash(token), purpose)).fetchone()
        if not challenge:
            raise HTTPException(400, '링크가 만료되었거나 사용할 수 없습니다. 메일을 다시 요청해 주세요.')
        email, user_id = challenge
        # 로그인과 동일한 scrypt 메모리 슬롯을 공유한다.
        if not conn.execute('SELECT pg_try_advisory_xact_lock(736125,1) OR pg_try_advisory_xact_lock(736125,2)').fetchone()[0]:
            raise HTTPException(503, '잠시 후 다시 시도해 주세요.')
        if purpose == 'signup':
            auth._signup_slot(conn, ip)
            row = conn.execute("INSERT INTO users(login_id,password_hash,role,email_verified_at) VALUES(%s,%s,'user',CURRENT_TIMESTAMP) "
                               'ON CONFLICT(login_id) DO NOTHING RETURNING id', (email, auth.hash_password(password))).fetchone()
            if not row:
                raise HTTPException(400, '링크를 사용할 수 없습니다. 로그인하거나 메일을 다시 요청해 주세요.')
        else:
            row = conn.execute("SELECT id FROM users WHERE id=%s AND login_id=%s AND is_active AND left(password_hash,7)='scrypt$' FOR UPDATE",
                               (user_id, email)).fetchone()
            if not row:
                raise HTTPException(400, '링크를 사용할 수 없습니다. 메일을 다시 요청해 주세요.')
            conn.execute('UPDATE users SET password_hash=%s,email_verified_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=%s',
                         (auth.hash_password(password), user_id))
            conn.execute('DELETE FROM auth_sessions WHERE user_id=%s', (user_id,))
            conn.execute('DELETE FROM auth_login_attempts WHERE login_hash=%s', (hashlib.sha256(email.encode()).hexdigest(),))
        conn.execute('DELETE FROM auth_email_challenges WHERE email=%s AND purpose=%s', (email, purpose))
