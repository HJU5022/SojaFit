"""SojaFit FastAPI 진입점.

역할: 인증·가입·데모 버튼 로그인(`DEMO_MODE=1`만)·탈퇴(`DELETE /api/me`)·관리자·가격 API, OSC의 프로젝트·D5 run·승인·견적 API, 내 설정(사용자 사실 기억) API와 React SPA를 같은 출처로 등록한다.
호출자: uvicorn(`backend.main:app`), Docker Compose의 api 서비스와 API·프론트 통합 테스트.
하지 않는 일: 인증·세션·계정 처리(`backend/auth.py`), Mouser 호출 자체, 저장소 SQL과 그래프 실행 자체.
출처: SPEC.md 4절(인증·관리자·가격·재고 계약, 공통 오류)·6절(Mouser)·8.4절(가격·재고 AC)·8.6절(로그인 AC), docs/specs/login-auth.md, docs/specs/api-error-contract.md, ADR 0009 · 0019, backend/BACKEND.md.
읽는 환경변수: AUTH_ORIGIN(허용 Origin이자 https일 때 쿠키 Secure 여부 결정, 기본 http://localhost:8000), DEMO_MODE(기본 1, 1이면 `/api/prices`가 Mouser를 부르지 않음).
시작할 때 JSON 로그를 켜고(`backend/logs.py`), auth.validate_auth_configuration()이 AUTH_SECRET·DEMO_MODE 조합을 검사하고 Uvicorn 접속 로그 필터를 등록한다.
오류 응답의 `error.code`는 `backend/errors.py`의 표(ADR 0019, 15개)에서 고르고, 오류 응답마다 code · status · request_id 로그 한 줄을 남긴다.
THREADS_ENABLED=1이면 명시적으로 준비한 DATABASE_URL의 분석 저장소·MCP 세션을 앱 수명 동안 관리한다.
"""
import os
import base64
import hashlib
import logging
from http import HTTPStatus
from html import escape
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlencode
from uuid import uuid4

import httpx
import psycopg
from authlib.common.errors import AuthlibBaseError
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import auth, logs
from backend.errors import DEFAULT_CODES, SPECIAL_CODES, code_for, log_error
from backend.api.projects import router as projects_router
from backend.api.quotes import router as quotes_router
from backend.services import mouser
from backend.web.app import mount_frontend


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
    """서버 시작 시 JSON 로그를 켜고 인증 설정을 검사한다."""
    logs.setup()  # [주의] 루트 로거에 처리기가 이미 있으면(pytest 등) 손대지 않는다
    # [왜] 잘못된 AUTH_SECRET으로 뜬 서버가 약한 세션 해시를 쓰지 않도록 RuntimeError로 기동 자체를 막는다
    auth.validate_auth_configuration()
    logger = logging.getLogger("uvicorn.access")
    log_filter = GoogleCallbackLogFilter()
    logger.addFilter(log_filter)
    conversations = None
    try:
        if os.getenv('THREADS_ENABLED') == '1':
            from backend.conversations.memory_service import Conversations
            conversations = Conversations(os.environ['DATABASE_URL'])
            app.state.conversations = conversations
        yield
    finally:
        if conversations:
            conversations.close()
            del app.state.conversations
        logger.removeFilter(log_filter)


class ErrorPayload(BaseModel):
    """클라이언트가 분기하고 사용자에게 표시할 공개 오류 정보."""

    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    """모든 JSON 오류 응답의 최상위 구조."""

    error: ErrorPayload


# 성공 응답 본문(`response_model`). [주의] response_model은 선언하지 않은 칸을 응답에서 지우고, 선언한 칸이 없으면 500이다.
# 칸은 각 경로가 지금 돌려주는 dict와 frontend/src/api/*.ts의 타입에서 옮겼다(tests/api/test_health.py가 대조한다)
class Health(BaseModel):
    status: Literal["ok"]


class UserId(BaseModel):
    """로그인 · 가입 · 데모 버튼 로그인 성공. 세션은 쿠키로 간다."""

    user_id: int


class Enabled(BaseModel):
    """데모 버튼 로그인 · Google 관리자 로그인이 켜져 있는지."""

    enabled: bool


class Me(BaseModel):
    user_id: int
    role: Literal["admin", "user"]


class Ok(BaseModel):
    ok: bool


class Deleted(BaseModel):
    """탈퇴로 지운 건수. 키: analysis_threads · analysis_circuits · checkpoints · memory_items · projects · quotes · account."""

    deleted: dict[str, int]


class Account(BaseModel):
    id: int
    email: str  # 사용자명을 가린 이메일(auth.mask_email)
    role: Literal["admin", "user"]
    is_active: bool


class Accounts(BaseModel):
    users: list[Account]


# [왜] 가격 칸은 Mouser 응답에서 그대로 옮긴 값이라 모두 null을 허용한다(형식이 다르면 mouser.py가 bad_response로 거른다)
class PriceBreak(BaseModel):
    quantity: int | None
    price: str | None
    currency: str | None


class PricePart(BaseModel):
    part_number: str | None
    manufacturer: str | None
    price_breaks: list[PriceBreak]
    availability: str | None
    product_url: str | None


class PricesAvailable(BaseModel):
    available: Literal[True]
    source: str
    fetched_at: str  # 조회 시각(UTC ISO 8601)
    parts: list[PricePart]


class PricesUnavailable(BaseModel):
    """키 없음 · 데모 모드 · 호출 상한 · Mouser 실패. parts는 늘 빈 목록이다."""

    available: Literal[False]
    source: str
    reason: str
    message: str
    parts: list[PricePart]


# OpenAPI 설명에는 상태마다 나올 수 있는 code를 적는다(예: 409 → CONFLICT · CONDITION_PENDING · ALREADY_APPROVED)
COMMON_ERROR_RESPONSES = {
    status_code: {"model": ErrorEnvelope, "description": " · ".join([code, *(c for c, s in SPECIAL_CODES.items() if s == status_code)])}
    for status_code, code in DEFAULT_CODES.items()
}

app = FastAPI(
    title="SojaFit API",
    lifespan=lifespan,
    responses=COMMON_ERROR_RESPONSES,
)
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
GOOGLE_COOKIE = "sojafit_google_browser"
GOOGLE_PENDING_COOKIE = "sojafit_google_pending"


def request_id_for(request: Request) -> str:
    """현재 요청 ID를 반환하되 예외가 미들웨어보다 먼저 나도 안전하게 만든다."""
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = str(uuid4())
        request.state.request_id = request_id
    return request_id


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    error: BaseException | None = None,
) -> JSONResponse:
    """공개 가능한 오류 정보만 공통 계약으로 반환하고, 같은 code · status · request_id로 로그 한 줄을 남긴다(5xx는 error의 traceback까지)."""
    request_id = request_id_for(request)
    # [왜] 모든 JSON 오류(HTTP · 검증 · 500 · DB 503 · 본문 413)가 여기를 지나 로그도 한 곳에서 남긴다. request_id는 직접 넘겨
    #      요청 ID 미들웨어보다 먼저 난 오류(request_id_for가 새로 만든 ID)에서도 응답과 로그의 ID가 같다
    log_error(status_code, code, error, request_id=request_id)
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers=response_headers,
    )


async def add_request_id(request: Request, call_next):
    """클라이언트 값 대신 서버 UUID를 모든 응답에 넣고, 이 요청에서 남기는 로그 줄에도 같은 값을 붙인다(등록은 파일 끝)."""
    request.state.request_id = str(uuid4())
    # [왜] 문맥 변수는 이 요청의 task와 거기서 만든 task · 스레드 풀 호출에 복사된다.
    #      가장 바깥 미들웨어는 응답을 보내는 task(uvicorn 접속 로그를 남기는 곳)와 같아 거기까지 같은 ID가 붙는다
    logs.REQUEST_ID.set(request.state.request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def google_enabled() -> bool:
    return os.getenv("GOOGLE_AUTH_ENABLED") == "1" and bool(os.getenv("GOOGLE_CLIENT_ID")) and bool(os.getenv("GOOGLE_CLIENT_SECRET"))


@app.get("/api/auth/google/status", include_in_schema=False, response_model=Enabled)
def google_status():
    return {"enabled": google_enabled()}


@app.get("/api/auth/google/start", include_in_schema=False)
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
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if not email:
        raise HTTPException(status_code=400, detail="연결 요청이 만료되었거나 처리되었습니다.")
    response = HTMLResponse(f"<h1>관리자 연결 승인 대기</h1><p>확인된 이메일: {escape(email)}</p><p>요청 번호: {escape(request_id)}</p><p>이 정보를 신뢰할 수 있는 경로로 운영자에게 전달하세요.</p>")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    try:
        default_message = HTTPStatus(exc.status_code).phrase
    except ValueError:
        default_message = "HTTP error"
    message = exc.detail if isinstance(exc.detail, str) else default_message
    return error_response(
        request,
        status_code=exc.status_code,
        code=code_for(exc.status_code, exc),  # 상황 코드(ApiError)가 없으면 상태의 기본 코드
        message=message,
        headers=exc.headers,
        error=exc,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="요청 형식이 올바르지 않습니다.",
    )


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="요청을 처리하지 못했습니다.",
        error=exc,  # [왜] 응답에는 숨기고 로그에만 traceback(예외 메시지는 뺀 모양)을 남긴다
    )


@app.get("/health", response_model=Health)
def health():
    """서비스 생존 확인용. 배포 환경과 평가자가 부르며 항상 {"status": "ok"}를 돌려준다."""
    return {"status": "ok"}


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


@app.post("/api/auth/login", response_model=UserId)
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


class Signup(Login):
    """가입 요청 본문. 이메일 검증은 로그인과 같고 비밀번호는 8자 이상, 처리방침 고지 동의(consent)는 true여야 한다(11-09 결정)."""

    # [주의] 로그인의 예시를 물려받으면 consent가 빠져 422가 된다. 모르는 칸 금지(extra)는 Login에서 물려받는다
    model_config = ConfigDict(json_schema_extra={"examples": [{"email": "new-user@example.com", "password": "example-password-123", "consent": True}]})
    password: str = Field(min_length=8, max_length=1024)
    # [왜] 가입 화면의 처리방침 고지(개인정보 보호법 15조 2항)를 읽고 동의했다는 표시. 없거나 true가 아니면 공통 422다
    consent: StrictBool

    @field_validator("consent")
    @classmethod
    def agreed(cls, consent: bool) -> bool:
        if consent is not True:
            raise ValueError("개인정보 수집 · 이용 동의가 필요합니다.")
        return consent


@app.post("/api/auth/signup", response_model=UserId)
def signup(body: Signup, request: Request, response: Response):
    """승인 없이 user 계정을 만들고 로그인과 같은 세션 쿠키를 심은 뒤 {"user_id": 정수}를 돌려준다."""
    # [주의] 403 Origin 없음·불일치, 409 이미 있는 이메일, 422 입력 검증 실패·동의(consent) 없음(입력값 미노출, validation_error가 냄),
    # 429 IP 하루 한도, 503 DB 사용 불가 또는 동시 scrypt 슬롯 부족(auth.signup이 냄)
    auth.check_origin(request)
    try:
        result = auth.signup(body.email, body.password, auth.client_ip(request))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="가입 서비스를 사용할 수 없습니다.") from None
    if result is None:
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
    token, user_id = result
    set_session_cookie(response, token)
    return {"user_id": user_id}


def demo_mode() -> None:
    """데모 버튼 로그인 경로는 DEMO_MODE=1일 때만 있다. 아니면 본문을 읽기 전에 공통 404."""
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(status_code=404, detail="Not Found")


@app.get("/api/auth/demo", dependencies=[Depends(demo_mode)], response_model=Enabled)
def demo_status():
    """데모 모드면 로그인 화면이 데모 사용자 A · B 버튼을 보인다(로그인 필요 없음)."""
    return {"enabled": True}


class DemoLogin(BaseModel):
    """데모 버튼 로그인 본문. 계정은 a · b 둘 중 하나만(이메일 · 사용자 id는 받지 않음)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"account": "a"}]})
    account: Literal["a", "b"]


@app.post("/api/auth/demo-login", dependencies=[Depends(demo_mode)], response_model=UserId)
def demo_login(body: DemoLogin, request: Request, response: Response):
    """데모 모드에서 시드한 데모 사용자 A · B로 비밀번호 없이 로그인과 같은 세션 쿠키를 심고 {"user_id"}를 돌려준다."""
    # [주의] 404 데모 모드 아님 · 데모 계정 없음(새 볼륨에서만 시드), 403 Origin, 422 a · b 밖의 값, 503 DB 사용 불가
    auth.check_origin(request)
    try:
        result = auth.demo_session(body.account)
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if result is None:
        raise HTTPException(status_code=404, detail="데모 계정이 없습니다. 데모 모드로 새 DB 볼륨을 만들어 다시 시작하세요.")
    token, user_id = result
    set_session_cookie(response, token)
    return {"user_id": user_id}


@app.get("/api/auth/me", response_model=Me)
def me(user: tuple[int, str] = Depends(auth.current_user)):
    """현재 세션의 사용자 id와 역할(admin | user)을 돌려준다(세션이 없으면 401)."""
    return {"user_id": user[0], "role": user[1]}


@app.post("/api/auth/logout", response_model=Ok)
def logout(request: Request, response: Response):
    """DB 세션을 지우고 쿠키를 삭제한다(Origin이 다르면 403)."""
    auth.check_origin(request)
    auth.logout(request)
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.delete("/api/me", response_model=Deleted)
def delete_me(request: Request, response: Response, user: tuple[int, str] = Depends(auth.current_user)):
    """탈퇴: 로그인 사용자의 기록을 먼저, 계정을 마지막에 지우고 지운 건수를 돌려준다(SPEC 8.5, 개인정보 보호법 37조 동의 철회)."""
    # [주의] 403 Origin 불일치, 409 관리자 · 진행 중 분석, 503 분석 저장소 없음 · 일부만 지움(다시 요청하면 남은 것부터 이어서 지움)
    auth.check_origin(request)
    if user[1] != "user":
        raise HTTPException(status_code=409, detail="관리자 계정은 이 기능으로 삭제할 수 없습니다.")
    try:
        with conversation_service(request).account_deletion(user[0]) as deleted:
            deleted.update(auth.delete_account(user[0]))  # 계정은 마지막: 앞에서 실패하면 계정이 남아 다시 요청할 수 있다
    except (psycopg.Error, PoolTimeout, OSError):
        raise HTTPException(status_code=503, detail="계정 삭제를 끝내지 못했습니다. 다시 요청하면 남은 기록부터 이어서 지웁니다.") from None
    response.delete_cookie(auth.COOKIE, path="/")
    return {"deleted": deleted}


class AccountState(BaseModel):
    """계정 활성 상태 변경 요청 본문. 모르는 칸은 공통 422다."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"is_active": False}]})
    # [왜] StrictBool이라 "false" 같은 문자열이 True로 해석되는 일을 막는다
    is_active: StrictBool


@app.get("/api/admin/users", response_model=Accounts)
def admin_users(user_id: int = Depends(auth.current_user_id)):
    """관리자 전용 계정 목록을 반환하고 이메일 사용자명을 마스킹한다."""
    users = auth.admin_users(user_id)
    return {"users": [{**user, "email": auth.mask_email(user["email"])} for user in users]}

@app.patch("/api/admin/users/{target_id}", response_model=Ok)
def admin_set_active(target_id: int, body: AccountState, request: Request, user_id: int = Depends(auth.current_user_id)):
    """일반 계정(user)을 활성화·비활성화한다(관리자 전용)."""
    # [주의] 403 Origin 불일치·관리자 아님·대상이 관리자, 404 대상 없음. 비활성화하면 auth가 그 계정의 세션도 지운다
    auth.check_origin(request)
    auth.admin_set_active(user_id, target_id, body.is_active)
    return {"ok": True}


def price_unavailable(reason: str) -> dict:
    """Mouser 값 없이 돌려주는 모양(SPEC 4절). reason: demo_mode 또는 `mouser.MouserError.kind`."""
    message = "데모 모드라 Mouser 가격·재고를 조회하지 않아요." if reason == "demo_mode" else "지금은 Mouser 가격·재고를 불러올 수 없어요."
    return {"available": False, "source": mouser.SOURCE, "reason": reason, "message": message, "parts": []}


@app.get("/api/prices", dependencies=[Depends(auth.current_user_id)], response_model=PricesAvailable | PricesUnavailable)
def prices(response: Response, parts: str = Query(min_length=1, max_length=450, description="쉼표로 나눈 품번 1~10개")):
    """로그인한 사용자에게 후보 품번의 Mouser 가격·재고를 요청 때 한 번 조회해 돌려준다(SPEC 4절).

    [주의] ADR 0009: 결과는 이 응답으로만 내보내고 저장 · 캐시 · 로그하지 않는다. 그래서 이 함수는 아무것도 로그에 쓰지 않고,
    브라우저 · 중간 캐시도 남기지 않게 `Cache-Control: no-store`를 붙인다. 그래프는 이 API를 부르지 않는다.
    """
    response.headers["Cache-Control"] = "no-store"
    names = list(dict.fromkeys(p.strip() for p in parts.split(",") if p.strip()))  # 같은 품번은 한 번만
    try:
        mouser.check_parts(names)  # [왜] 데모 모드에서도 같은 입력 규칙(422)을 쓴다. Mouser를 부르기 전에 거른다
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error), headers={"Cache-Control": "no-store"}) from None
    if os.getenv("DEMO_MODE", "1") == "1":
        return price_unavailable("demo_mode")  # SPEC 7절: 데모 모드는 Mouser 칸을 비운다
    try:
        return {"available": True, **mouser.search_parts(names)}
    except mouser.MouserError as error:
        return price_unavailable(error.kind)  # [주의] 오류를 로그에 쓰지 않는다. 종류만 화면에 알린다


@app.middleware('http')
async def conversation_boundary(request: Request, call_next):
    """대화 run(`/api/threads/...`)과 내 설정(`/api/me/memory`) 응답에 no-store를 붙이고, 그 경로의 POST 본문을 128 KiB로 막는다."""
    private = request.url.path.startswith(('/api/threads', '/api/me/memory'))
    if private and request.method == 'POST':
        limit = 128 * 1024
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > limit:
                return error_response(request, status_code=413, code=DEFAULT_CODES[413],
                                      message='요청이 너무 큽니다.', headers={'Cache-Control': 'no-store'})
            data.extend(chunk)
        request._body = bytes(data)  # downstream JSON 검증에도 한도 내에서 읽은 같은 본문을 전달한다
    response = await call_next(request)
    if private:
        response.headers['Cache-Control'] = 'no-store'
    return response


async def database_unavailable(request: Request, error):
    return error_response(request, status_code=503, code=DEFAULT_CODES[503],
                          message='저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.',
                          headers={'Cache-Control': 'no-store'}, error=error)


app.add_exception_handler(psycopg.Error, database_unavailable)
app.add_exception_handler(PoolTimeout, database_unavailable)


def conversation_service(request: Request):
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service


# health·인증·Google 콜백과 아래 라우터가 SPA보다 먼저 처리되도록 화면 연결은 마지막에 둔다.
from backend.api.conversations import router as conversations_router
from backend.api.profile import router as profile_router
app.include_router(projects_router)
app.include_router(quotes_router)
app.include_router(conversations_router)
app.include_router(profile_router)
mount_frontend(app, FRONTEND_DIST)
# [주의] 마지막에 등록한 미들웨어가 가장 바깥에서 돈다. 요청 ID를 화면 연결 · 본문 한도 미들웨어보다 먼저 정해야
#        본문 413 · 500 · 접속 로그까지 같은 ID를 쓴다(안쪽 미들웨어 task에서 넣은 문맥 변수는 바깥 task로 올라오지 않는다)
app.middleware("http")(add_request_id)
