"""Gmail SMTP 메일 전송만 담당한다. 토큰·수신자·SMTP 오류를 로그하지 않는다.

호출자: backend/auth_email.py. 설정: SMTP_USERNAME, SMTP_PASSWORD, SMTP_PORT,
AUTH_ORIGIN. 비밀값 미설정이면 발송하지 않는다. 표준 라이브러리만 사용한다.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit


def configured() -> bool:
    return bool(os.getenv('SMTP_USERNAME') and os.getenv('SMTP_PASSWORD'))


def send_link(email: str, purpose: str, token: str) -> None:
    if not configured():
        raise ValueError('mail configuration unavailable')
    origin = os.environ.get('AUTH_ORIGIN', '').rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('invalid mail origin')
    if parsed.scheme != 'https' and os.getenv('DEMO_MODE', '1') != '1':
        raise ValueError('HTTPS required')
    route, title, minutes = ('verify-email', '회원가입 이메일 인증', 60) if purpose == 'signup' else ('reset-password', '비밀번호 재설정', 15)
    message = EmailMessage()
    message['From'] = os.environ['SMTP_USERNAME']
    message['To'] = email
    message['Subject'] = 'SojaFit ' + title
    message.set_content(f'{title}을 요청하셨다면 아래 링크를 열어 진행해 주세요.\n{minutes}분 동안 한 번만 사용할 수 있습니다.\n\n{origin}/{route}#token={token}\n\n요청하지 않으셨다면 이 메일을 무시하세요. 메일에 답장할 필요는 없습니다.')
    port = int(os.getenv('SMTP_PORT', '465'))
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL('smtp.gmail.com', port, timeout=10, context=context) as smtp:
            smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    elif port == 587:
        with smtplib.SMTP('smtp.gmail.com', port, timeout=10) as smtp:
            smtp.starttls(context=context)
            smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    else:
        raise ValueError('only TLS mail submission ports are allowed')
