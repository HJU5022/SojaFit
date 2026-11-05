"""SojaFit FastAPI 진입점.

역할: `/health`, `/login`, 로그인 API(`/api/auth/*`), 관리자 계정 API(`/api/admin/users`)와 Google 콜백 접속 로그 보호를 등록한다.
호출자: uvicorn(`backend.main:app`), Docker Compose의 api 서비스, tests/api/test_health.py·tests/api/test_auth.py.
하지 않는 일: 인증·세션·계정 처리(backend/auth.py), 질문·답변 API, 회로·대화·기억·견적 API.
출처: SPEC.md 4절(인증·관리자 계약)·8.6절(로그인 AC), docs/specs/login-auth.md, backend/BACKEND.md.
읽는 환경변수: AUTH_ORIGIN(허용 Origin이자 https일 때 쿠키 Secure 여부 결정, 기본 http://localhost:8000).
시작할 때 auth.validate_auth_configuration()이 AUTH_SECRET·DEMO_MODE 조합을 검사하고 Uvicorn 접속 로그 필터를 등록한다.
"""
import os
import base64
import hashlib
import logging
from html import escape
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote, urlencode

import httpx
import psycopg
from authlib.common.errors import AuthlibBaseError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, StrictBool, field_validator

from backend import auth


class GoogleCallbackLogFilter(logging.Filter):
    """Uvicorn 접속 로그에서 Google 콜백의 쿼리만 제거한다."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            target = record.args[2]
            if isinstance(target, str):
                path, separator, _ = target.partition("?")
                if separator and unquote(path).rstrip("/") == "/api/auth/google/callback":
                    record.args = (*record.args[:2], path, *record.args[3:])
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 인증 설정을 검사한다."""
    # [왜] 잘못된 AUTH_SECRET으로 뜬 서버가 약한 세션 해시를 쓰지 않도록 RuntimeError로 기동 자체를 막는다
    auth.validate_auth_configuration()
    logger = logging.getLogger("uvicorn.access")
    log_filter = GoogleCallbackLogFilter()
    logger.addFilter(log_filter)
    try:
        yield
    finally:
        logger.removeFilter(log_filter)


app = FastAPI(title="SojaFit API", lifespan=lifespan)
LOGIN_PAGE = Path(__file__).parent / "web" / "templates" / "login.html"
GOOGLE_COOKIE = "sojafit_google_browser"
GOOGLE_PENDING_COOKIE = "sojafit_google_pending"


def google_enabled() -> bool:
    return os.getenv("GOOGLE_AUTH_ENABLED") == "1" and bool(os.getenv("GOOGLE_CLIENT_ID")) and bool(os.getenv("GOOGLE_CLIENT_SECRET"))


@app.get("/api/auth/google/status", include_in_schema=False)
def google_status():
    return {"enabled": google_enabled()}


@app.get("/api/auth/google/start", include_in_schema=False)
def google_start():
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google 로그인을 사용할 수 없습니다.")
    try:
        state, browser, verifier, nonce = auth.create_google_state()
    except (psycopg.Error, KeyError):
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    origin = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").rstrip("/")
    query = urlencode({"client_id": os.environ["GOOGLE_CLIENT_ID"], "redirect_uri": origin + "/api/auth/google/callback", "response_type": "code", "scope": "openid email", "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + query, status_code=303)
    response.set_cookie(GOOGLE_COOKIE, browser, max_age=600, httponly=True, secure=origin.startswith("https://"), samesite="lax", path="/api/auth/google/callback")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/auth/google/callback", include_in_schema=False)
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
        session = auth.google_admin_session(identity[0], identity[1])
        if session:
            response = RedirectResponse("/login", status_code=303)
            secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
            response.set_cookie(auth.COOKIE, session[0], httponly=True, secure=secure, samesite="lax", max_age=8 * 3600, path="/")
        else:
            request_id = auth.request_google_link(*identity)
            response = RedirectResponse("/api/auth/google/pending", status_code=303)
            secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
            response.set_cookie(GOOGLE_PENDING_COOKIE, request_id, max_age=900, httponly=True, secure=secure, samesite="lax", path="/api/auth/google/pending")
    except (psycopg.Error, KeyError, httpx.HTTPError, AuthlibBaseError, ValueError, TypeError):
        return google_failure()
    response.delete_cookie(GOOGLE_COOKIE, path="/api/auth/google/callback")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def google_failure():
    response = RedirectResponse("/login?google=error", status_code=303)
    response.delete_cookie(GOOGLE_COOKIE, path="/api/auth/google/callback")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/auth/google/pending", include_in_schema=False)
def google_pending(request: Request):
    if not google_enabled():
        raise HTTPException(status_code=404, detail="Google 로그인을 사용할 수 없습니다.")
    request_id = request.cookies.get(GOOGLE_PENDING_COOKIE, "")
    try:
        email = auth.google_pending_email(request_id)
    except (psycopg.Error, KeyError):
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if not email:
        raise HTTPException(status_code=400, detail="연결 요청이 만료되었거나 처리되었습니다.")
    response = HTMLResponse(f"<h1>관리자 연결 승인 대기</h1><p>확인된 이메일: {escape(email)}</p><p>요청 번호: {escape(request_id)}</p><p>이 정보를 신뢰할 수 있는 경로로 운영자에게 전달하세요.</p>")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": [{key: value for key, value in error.items() if key not in {"input", "ctx"}} for error in exc.errors()]})


@app.get("/health")
def health() -> dict:
    """서비스 생존 확인용. 배포 환경과 평가자가 부르며 항상 {"status": "ok"}를 돌려준다."""
    return {"status": "ok"}


@app.get("/login", include_in_schema=False)
def login_page():
    """같은 출처의 로그인 화면을 제공한다."""
    return FileResponse(LOGIN_PAGE, media_type="text/html; charset=utf-8")


class Login(BaseModel):
    """로그인 요청 본문."""

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


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    """이메일·비밀번호를 검증하고 세션 쿠키를 심은 뒤 {"user_id": 정수}를 돌려준다."""
    # [주의] 403 Origin 불일치, 401 인증 실패·잠금, 503 DB 사용 불가 또는 동시 검증 슬롯 부족(authenticate가 냄)
    auth.check_origin(request)
    try:
        result = auth.authenticate(body.email, body.password)
    except (psycopg.Error, KeyError):  # KeyError는 DATABASE_URL 누락
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if result is None:
        # [왜] 계정 없음·비밀번호 틀림·잠금·비활성을 같은 메시지로 돌려 계정 존재를 알 수 없게 한다
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호를 확인해 주세요.")
    token, user_id = result
    # [왜] AUTH_ORIGIN이 https일 때만 Secure를 켠다(로컬 http 개발에서는 쿠키가 안 붙는 것을 피함)
    secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
    # [주의] httponly=JS가 못 읽게 해 토큰 탈취를 막고, samesite=lax는 CSRF를 줄인다. 8시간은 세션 절대 만료와 같다
    response.set_cookie(auth.COOKIE, token, httponly=True, secure=secure, samesite="lax", max_age=8 * 3600, path="/")
    return {"user_id": user_id}


@app.get("/api/auth/me")
def me(user: tuple[int, str] = Depends(auth.current_user)):
    """현재 세션의 사용자 id와 역할(admin | user)을 돌려준다(세션이 없으면 401)."""
    return {"user_id": user[0], "role": user[1]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    """DB 세션을 지우고 쿠키를 삭제한다(Origin이 다르면 403)."""
    auth.check_origin(request)
    auth.logout(request)
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


class AccountState(BaseModel):
    """계정 활성 상태 변경 요청 본문."""

    # [왜] StrictBool이라 "false" 같은 문자열이 True로 해석되는 일을 막는다

    is_active: StrictBool


@app.get("/api/admin/users")
def admin_users(user_id: int = Depends(auth.current_user_id)):
    """관리자 전용 계정 목록을 반환하고 이메일 사용자명을 마스킹한다."""
    users = auth.admin_users(user_id)
    return {"users": [{**user, "email": auth.mask_email(user["email"])} for user in users]}

@app.patch("/api/admin/users/{target_id}")
def admin_set_active(target_id: int, body: AccountState, request: Request, user_id: int = Depends(auth.current_user_id)):
    """일반 계정(user)을 활성화·비활성화한다(관리자 전용)."""
    # [주의] 403 Origin 불일치·관리자 아님·대상이 관리자, 404 대상 없음. 비활성화하면 auth가 그 계정의 세션도 지운다
    auth.check_origin(request)
    auth.admin_set_active(user_id, target_id, body.is_active)
    return {"ok": True}
