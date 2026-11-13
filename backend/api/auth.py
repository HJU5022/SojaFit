"""로그인 · 가입 · 데모 버튼 로그인 · 로그아웃 · 내 계정 HTTP 경계(`/api/auth/*`)와 숨긴 Google 가입 · 로그인 경로.

- 경로: `POST /api/auth/login` · `POST /api/auth/signup`(가입 메일 요청) · `POST /api/auth/signup/confirm` · `POST /api/auth/password-reset` · `POST /api/auth/password-reset/confirm` · `GET /api/auth/demo` · `POST /api/auth/demo-login`(데모 두 경로만 `DEMO_MODE=1`에서 제공) ·
  `GET /api/auth/me` · `POST /api/auth/logout`, `/docs`에 싣지 않는 `GET /api/auth/google/status|start|callback|pending|onboarding` · `POST /api/auth/google/signup|link`(Google 가입 · 로그인, 명시적 가입·비밀번호 재확인 연결).
- 화면 쪽 짝: `frontend/src/api/auth.ts`.
하지 않는 일: 비밀번호 · 세션 · 잠금 · 가입 한도 · Google 신원 확인(`backend/auth.py`), 탈퇴(`backend/api/profile.py`),
  관리자 계정 관리(`backend/api/admin.py`), Uvicorn 접속 로그의 쿼리 지우기(`backend/logs.py`의 `hide_query`).
출처: SPEC.md 4절 · 8.6절, docs/specs/login-auth.md, docs/specs/google-admin-login.md.
읽는 환경변수: AUTH_ORIGIN(쿠키 Secure 여부 · Google 콜백 주소, 기본 http://localhost:8000), DEMO_MODE(기본 1),
  GOOGLE_AUTH_ENABLED · GOOGLE_CLIENT_ID · GOOGLE_CLIENT_SECRET(셋 다 있어야 Google 경로가 열림).
"""
import os
import base64
import hashlib
from html import escape
from email.utils import parseaddr
from typing import Literal
from urllib.parse import urlencode

import httpx
import psycopg
from authlib.common.errors import AuthlibBaseError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from backend import auth

router = APIRouter(prefix='/api/auth', tags=['auth'])
GOOGLE_COOKIE = "sojafit_google_browser"
GOOGLE_PENDING_COOKIE = "sojafit_google_pending"


# 성공 응답 본문(`response_model`). [주의] response_model은 선언하지 않은 칸을 응답에서 지우고, 선언한 칸이 없으면 500이다.
# 칸은 각 경로가 지금 돌려주는 dict와 frontend/src/api/*.ts의 타입에서 옮겼다(tests/api/test_openapi.py가 대조한다)
class UserId(BaseModel):
    """로그인 · 가입 · 데모 버튼 로그인 성공. 세션은 쿠키로 간다."""

    user_id: int


class Enabled(BaseModel):
    """데모 버튼 로그인 · Google 관리자 로그인이 켜져 있는지."""

    enabled: bool


class Me(BaseModel):
    user_id: int
    role: Literal["admin", "user"]
    email: str


class Ok(BaseModel):
    # [주의] 관리자 계정 상태 변경(backend/api/admin.py)도 이 클래스를 쓴다. 같은 이름을 따로 만들면 /docs 스키마 이름이 바뀐다
    ok: bool


def google_enabled() -> bool:
    return os.getenv("GOOGLE_AUTH_ENABLED") == "1" and bool(os.getenv("GOOGLE_CLIENT_ID")) and bool(os.getenv("GOOGLE_CLIENT_SECRET"))


@router.get("/google/status", include_in_schema=False, response_model=Enabled)
def google_status():
    return {"enabled": google_enabled()}


@router.get("/google/start", include_in_schema=False)
def google_start():
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google 로그인을 사용할 수 없습니다.")
    try:
        state, browser, verifier, nonce = auth.create_google_state()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    origin = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/")
    query = urlencode({"client_id": os.environ["GOOGLE_CLIENT_ID"], "redirect_uri": origin + "/api/auth/google/callback", "response_type": "code", "scope": "openid email", "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + query, status_code=303)
    response.set_cookie(GOOGLE_COOKIE, browser, max_age=600, httponly=True, secure=origin.startswith("https://"), samesite="lax", path="/api/auth/google/callback")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/google/callback", include_in_schema=False)
def google_callback(request: Request):
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google 로그인을 사용할 수 없습니다.")
    state, code = request.query_params.get("state", ""), request.query_params.get("code", "")
    if not code or len(code) > 2048:
        return google_failure()
    try:
        stored = auth.consume_google_state(state, request.cookies.get(GOOGLE_COOKIE, ""))
        if not stored:
            return google_failure()
        identity = auth.fetch_google_identity(code, *stored)
        if not identity:
            return google_failure()
        session = auth.google_session(identity[0], identity[1])
        if session:
            response = RedirectResponse("/login", status_code=303)
            response.delete_cookie(GOOGLE_PENDING_COOKIE, path="/api/auth/google")
            secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
            response.set_cookie(auth.COOKIE, session[0], httponly=True, secure=secure, samesite="lax", max_age=8 * 3600, path="/")
        else:
            request_id = auth.request_google_link(*identity)
            response = RedirectResponse("/login?google=finish", status_code=303)
            secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
            response.set_cookie(GOOGLE_PENDING_COOKIE, request_id, max_age=900, httponly=True, secure=secure, samesite="lax", path="/api/auth/google")
    # [왜] 콜백은 브라우저 이동이라 DB 설정 누락(auth.connection의 503)도 JSON 대신 로그인 화면 오류로 돌려보낸다
    except (psycopg.Error, HTTPException, KeyError, httpx.HTTPError, AuthlibBaseError, ValueError, TypeError):
        return google_failure()
    response.delete_cookie(GOOGLE_COOKIE, path="/api/auth/google/callback")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def google_failure():
    response = RedirectResponse("/login?google=error", status_code=303)
    response.delete_cookie(GOOGLE_COOKIE, path="/api/auth/google/callback")
    response.delete_cookie(GOOGLE_PENDING_COOKIE, path="/api/auth/google")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/google/pending", include_in_schema=False)
def google_pending(request: Request):
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google 로그인을 사용할 수 없습니다.")
    request_id = request.cookies.get(GOOGLE_PENDING_COOKIE, "")
    try:
        email = auth.google_pending_email(request_id)
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if not email:
        raise HTTPException(status_code=400, detail="연결 요청이 만료되었거나 처리되었습니다.")
    response = HTMLResponse(f"<h1>관리자 연결 승인 대기</h1><p>확인된 이메일: {escape(email)}</p><p>요청 번호: {escape(request_id)}</p><p>이 정보를 신뢰할 수 있는 경로로 운영자에게 전달하세요.</p>")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


class Login(BaseModel):
    """로그인 요청 본문. 모르는 칸은 공통 422다."""

    # [왜] 화면은 email · password만 보낸다(frontend/src/api/auth.ts). 예시는 /docs에 보이는 가짜 값이다
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"email": "user@example.com", "password": "example-password"}]})
    # [왜] 길이 상한은 입력 크기를 제한해 scrypt 비용 증폭과 DB 값 길이 초과를 막는다
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def check_email(cls, email: str) -> str:
        email = email.strip().lower()
        if not auth.valid_email(email):
            raise ValueError("유효한 이메일 주소를 입력해 주세요.")
        return email


def set_session_cookie(response: Response, token: str) -> None:
    """로그인·가입이 같은 세션 쿠키를 심는다."""
    # [왜] AUTH_ORIGIN이 https일 때만 Secure를 켠다(로컬 http 개발에서는 쿠키가 안 붙는 것을 피함)
    secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
    # [주의] httponly=JS가 못 읽게 해 토큰 탈취를 막고, samesite=lax는 CSRF를 줄인다. 8시간은 세션 절대 만료와 같다
    response.set_cookie(auth.COOKIE, token, httponly=True, secure=secure, samesite="lax", max_age=8 * 3600, path="/")


@router.post("/login", response_model=UserId)
def login(body: Login, request: Request, response: Response):
    """이메일·비밀번호를 검증하고 세션 쿠키를 심은 뒤 {"user_id": 정수}를 돌려준다."""
    # [주의] 403 Origin 불일치, 401 인증 실패·계정 잠금·IP 잠금, 503 DB 사용 불가 또는 동시 검증 슬롯 부족(authenticate가 냄)
    auth.check_origin(request)
    try:
        result = auth.authenticate(body.email, body.password, auth.client_ip(request))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if result is None:
        # [왜] 계정 없음·비밀번호 틀림·계정 잠금·IP 잠금·비활성을 같은 메시지로 돌려 계정 존재와 잠금을 알 수 없게 한다
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호를 확인해 주세요.")
    token, user_id = result
    set_session_cookie(response, token)
    return {"user_id": user_id}


class Signup(BaseModel):
    """메일 발송 요청만 받으며 인증 전에 계정·세션을 만들지 않는다."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"email": "new-user@example.com"}]})
    email: str = Field(min_length=3, max_length=100)
    consent: StrictBool | None = None  # 구버전 표시 호환; 동의 증거로 저장하지 않는다.

    @field_validator("email")
    @classmethod
    def check_email(cls, email: str) -> str:
        email = Login.check_email(email)
        if parseaddr(email)[1] != email:
            raise ValueError("유효한 이메일 주소를 입력해 주세요.")
        return email


class PasswordAction(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"token": "x" * 43, "password": "example-password-123"}]})
    token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("password")
    @classmethod
    def check_new_password(cls, password: str) -> str:
        auth.validate_new_password(password)
        return password


def email_request(body: Signup, request: Request, response: Response, purpose: str):
    from backend import auth_email
    auth.check_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        auth_email.request_email(body.email, auth.client_ip(request), purpose)
    except psycopg.Error:
        raise HTTPException(503, "메일 인증 서비스를 사용할 수 없습니다.") from None
    return {"ok": True}


def email_complete(body: PasswordAction, request: Request, response: Response, purpose: str):
    from backend import auth_email
    auth.check_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        auth_email.complete(body.token, body.password, purpose, auth.client_ip(request))
    except psycopg.Error:
        raise HTTPException(503, "메일 인증 서비스를 사용할 수 없습니다.") from None
    return {"ok": True}


@router.post("/signup", response_model=Ok)
def signup(body: Signup, request: Request, response: Response):
    return email_request(body, request, response, 'signup')


@router.post("/signup/confirm", response_model=Ok)
def signup_confirm(body: PasswordAction, request: Request, response: Response):
    return email_complete(body, request, response, 'signup')


@router.post("/password-reset", response_model=Ok)
def password_reset(body: Signup, request: Request, response: Response):
    return email_request(body, request, response, 'reset')


@router.post("/password-reset/confirm", response_model=Ok)
def password_reset_confirm(body: PasswordAction, request: Request, response: Response):
    return email_complete(body, request, response, 'reset')


class GoogleSignup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    consent: StrictBool | None = None  # 구버전 요청 호환, 동의 증거로 사용하지 않음


class GoogleOnboarding(BaseModel):
    email: str


def require_google():
    if not google_enabled():
        raise HTTPException(404, 'Google 로그인을 사용할 수 없습니다.')


@router.get('/google/onboarding', include_in_schema=False, response_model=GoogleOnboarding, dependencies=[Depends(require_google)])
def google_onboarding(request: Request, response: Response):
    email = auth.google_pending_email(request.cookies.get(GOOGLE_PENDING_COOKIE, ''))
    if not email:
        raise HTTPException(400, 'Google 인증이 만료되었습니다. 다시 시작해 주세요.')
    response.headers['Cache-Control'] = 'no-store'
    return {'email': auth.mask_email(email)}


def complete_google_response(request: Request, response: Response, *, user_id=None):
    token, user_id = auth.complete_google_user(request.cookies.get(GOOGLE_PENDING_COOKIE, ''), auth.client_ip(request), user_id=user_id)
    set_session_cookie(response, token)
    response.delete_cookie(GOOGLE_PENDING_COOKIE, path='/api/auth/google')
    response.headers['Cache-Control'] = 'no-store'
    return {'user_id': user_id}


@router.post('/google/signup', include_in_schema=False, response_model=UserId, dependencies=[Depends(require_google), Depends(auth.check_origin)])
def google_signup(body: GoogleSignup, request: Request, response: Response):
    return complete_google_response(request, response)


@router.post('/google/link', include_in_schema=False, response_model=UserId, dependencies=[Depends(require_google), Depends(auth.check_origin)])
def google_link(body: Login, request: Request, response: Response):
    # 비밀번호를 다시 확인하며, 연결이 완료되기 전에는 세션을 발급하지 않는다.
    proof = auth.authenticate(body.email, body.password, auth.client_ip(request), issue_session=False)
    if proof is None:
        raise HTTPException(401, '이메일 또는 비밀번호를 확인해 주세요.')
    return complete_google_response(request, response, user_id=proof[1])


def demo_mode() -> None:
    """데모 로그인 경로만 DEMO_MODE=1에서 제공한다."""
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(status_code=404, detail="Not Found")


@router.get("/demo", dependencies=[Depends(demo_mode)], response_model=Enabled)
def demo_status():
    """데모 모드면 로그인 화면이 데모 사용자 A · B 버튼을 보인다(로그인 필요 없음)."""
    return {"enabled": True}


class DemoLogin(BaseModel):
    """데모 버튼 로그인 본문. 계정은 a · b 둘 중 하나만(이메일 · 사용자 id는 받지 않음)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"account": "a"}]})
    account: Literal["a", "b"]


@router.post("/demo-login", dependencies=[Depends(demo_mode)], response_model=UserId)
def demo_login(body: DemoLogin, request: Request, response: Response):
    """데모 모드의 데모 사용자 A · B(없으면 만든다)로 비밀번호 없이 로그인과 같은 세션 쿠키를 심고 {"user_id"}를 돌려준다."""
    # [주의] 404 데모 모드 아님(데모 계정은 첫 로그인 때 만든다), 403 Origin, 422 a · b 밖의 값, 503 DB 사용 불가
    auth.check_origin(request)
    try:
        result = auth.demo_session(body.account)
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if result is None:
        raise HTTPException(status_code=404, detail="데모 계정을 사용할 수 없습니다.")
    token, user_id = result
    set_session_cookie(response, token)
    return {"user_id": user_id}


@router.get("/me", response_model=Me)
def me(response: Response, user: tuple[int, str] = Depends(auth.current_user)):
    """현재 세션 본인의 id·역할·로그인 이메일을 돌려준다(세션이 없으면 401)."""
    response.headers['Cache-Control'] = 'no-store'
    return {"user_id": user[0], "role": user[1], "email": auth.account_email(user[0])}


@router.post("/logout", response_model=Ok)
def logout(request: Request, response: Response):
    """DB 세션을 지우고 쿠키를 삭제한다(Origin이 다르면 403)."""
    auth.check_origin(request)
    auth.logout(request)
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}
