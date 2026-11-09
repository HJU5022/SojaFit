"""SojaFit FastAPI 진입점.

역할: 인증·관리자·가격 API, #73의 회로·thread·기억 API, OSC의 프로젝트·D5 run·승인·견적 API와 React SPA를 같은 출처로 등록한다.
호출자: uvicorn(`backend.main:app`), Docker Compose의 api 서비스와 API·프론트 통합 테스트.
하지 않는 일: 인증·세션·계정 처리(`backend/auth.py`), Mouser 호출 자체, 저장소 SQL과 그래프 실행 자체.
출처: SPEC.md 4절(인증·관리자·가격·재고 계약)·6절(Mouser)·8.4절(가격·재고 AC)·8.6절(로그인 AC), docs/specs/login-auth.md, docs/specs/api-error-contract.md, ADR 0009, backend/BACKEND.md.
읽는 환경변수: AUTH_ORIGIN(허용 Origin이자 https일 때 쿠키 Secure 여부 결정, 기본 http://localhost:8000), DEMO_MODE(기본 1, 1이면 `/api/prices`가 Mouser를 부르지 않음).
시작할 때 auth.validate_auth_configuration()이 AUTH_SECRET·DEMO_MODE 조합을 검사하고 Uvicorn 접속 로그 필터를 등록한다.
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
from uuid import UUID
from urllib.parse import unquote, urlencode
from uuid import uuid4

import httpx
import psycopg
from authlib.common.errors import AuthlibBaseError
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import auth
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
    """서버 시작 시 인증 설정을 검사한다."""
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


ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


class ErrorPayload(BaseModel):
    """클라이언트가 분기하고 사용자에게 표시할 공개 오류 정보."""

    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    """모든 JSON 오류 응답의 최상위 구조."""

    error: ErrorPayload


COMMON_ERROR_RESPONSES = {
    status_code: {"model": ErrorEnvelope, "description": code}
    for status_code, code in ERROR_CODES.items()
}
COMMON_ERROR_RESPONSES[500] = {"model": ErrorEnvelope, "description": "INTERNAL_ERROR"}

app = FastAPI(
    title="SojaFit API",
    lifespan=lifespan,
    responses=COMMON_ERROR_RESPONSES,
)
LOGIN_PAGE = Path(__file__).parent / "web" / "templates" / "login.html"
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
) -> JSONResponse:
    """공개 가능한 오류 정보만 공통 계약으로 반환한다."""
    request_id = request_id_for(request)
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


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """클라이언트 값 대신 서버 UUID를 모든 응답에 넣는다."""
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


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
        code=ERROR_CODES.get(exc.status_code, "HTTP_ERROR"),
        message=message,
        headers=exc.headers,
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
    )


@app.get("/health")
def health() -> dict:
    """서비스 생존 확인용. 배포 환경과 평가자가 부르며 항상 {"status": "ok"}를 돌려준다."""
    return {"status": "ok"}


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


def price_unavailable(reason: str) -> dict:
    """Mouser 값 없이 돌려주는 모양(SPEC 4절). reason: demo_mode 또는 `mouser.MouserError.kind`."""
    message = "데모 모드라 Mouser 가격·재고를 조회하지 않아요." if reason == "demo_mode" else "지금은 Mouser 가격·재고를 불러올 수 없어요."
    return {"available": False, "source": mouser.SOURCE, "reason": reason, "message": message, "parts": []}


@app.get("/api/prices", dependencies=[Depends(auth.current_user_id)])
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
    private = request.url.path.startswith(('/api/circuits', '/api/threads', '/api/memories', '/api/analysis/'))
    if private and request.method == 'POST':
        limit = 7 * 1024 * 1024 if request.url.path == '/api/circuits' else 128 * 1024
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > limit:
                return error_response(request, status_code=413, code=ERROR_CODES[413],
                                      message='요청이 너무 큽니다.', headers={'Cache-Control': 'no-store'})
            data.extend(chunk)
        request._body = bytes(data)  # downstream JSON 검증에도 한도 내에서 읽은 같은 본문을 전달한다
    response = await call_next(request)
    if private or request.url.path == '/workspace':
        response.headers['Cache-Control'] = 'no-store'
    return response


async def database_unavailable(request: Request, error):
    return error_response(request, status_code=503, code=ERROR_CODES[503],
                          message='저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.',
                          headers={'Cache-Control': 'no-store'})


app.add_exception_handler(psycopg.Error, database_unavailable)
app.add_exception_handler(PoolTimeout, database_unavailable)


def conversation_service(request: Request):
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service


@app.get('/api/analysis/readiness')
def analysis_readiness(request: Request, user: int = Depends(auth.current_user_id)):
    """분석 저장소 준비 확인. 외부 모델·검색의 품질/가용성은 보증하지 않는다."""
    conversation_service(request).readiness()
    return {'status': 'ready', 'storage': 'ready'}


@app.get('/api/analysis/demo')
def demo_configuration(request: Request, user: int = Depends(auth.current_user_id)):
    """명시적으로 켠 합성 데모의 회로와 지원 질문만 제공한다."""
    from backend.services import demo
    return {'enabled': True, **demo.configuration()} if conversation_service(request).mode == 'demo' else {'enabled': False}


class CircuitUpload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    filename: str = Field(min_length=1, max_length=200)
    netlist: str = Field(min_length=1, max_length=1024 * 1024)


class ThreadCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    circuit_id: UUID
    target: str = Field(min_length=1, max_length=100)


class ThreadMessage(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str = Field(min_length=1, max_length=10000)
    conditions: str = Field(default='', max_length=4000)

    @field_validator('text')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('질문을 입력하세요.')
        return value


class ThreadResume(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: int = Field(ge=1)
    answers: dict[str, str] = Field(default_factory=dict, max_length=50)
    role: str = Field(default='', max_length=100)

    @field_validator('answers')
    @classmethod
    def answer_lengths(cls, value):
        if any(len(k) > 100 or len(v) > 200 for k, v in value.items()):
            raise ValueError('조건 답변이 너무 깁니다.')
        return value


class ThreadApproval(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: int = Field(ge=1)


class MemoryControl(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Literal['correct','revoke','restore','delete']
    correction: str = Field(default='', max_length=1000)


@app.get('/workspace', include_in_schema=False)
def workspace_page():
    return FileResponse(LOGIN_PAGE.with_name('workspace.html'), media_type='text/html; charset=utf-8')


@app.post('/api/circuits')
def upload_circuit(body: CircuitUpload, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).upload(user, body.filename, body.netlist)


@app.get('/api/circuits')
def list_circuits(request: Request, user: int = Depends(auth.current_user_id)):
    return conversation_service(request).circuits(user)


@app.post('/api/threads')
def create_thread(body: ThreadCreate, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).create(user, str(body.circuit_id), body.target)


@app.get('/api/threads')
def list_threads(request: Request, user: int = Depends(auth.current_user_id)):
    return conversation_service(request).threads(user)


@app.get('/api/threads/{thread_id}')
def thread_detail(thread_id: UUID, request: Request, user: int = Depends(auth.current_user_id)):
    return conversation_service(request).detail(user, str(thread_id))


@app.post('/api/threads/{thread_id}/messages')
def thread_message(thread_id: UUID, body: ThreadMessage, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).message(user, str(thread_id), body.text, body.conditions, request_id=request_id_for(request))


@app.post('/api/threads/{thread_id}/resume')
def thread_resume(thread_id: UUID, body: ThreadResume, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).resume(user, str(thread_id), body.answers, body.role, body.version, request_id=request_id_for(request))


@app.post('/api/threads/{thread_id}/approve')
def thread_approve(thread_id: UUID, body: ThreadApproval, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).approve(user, str(thread_id), body.version, request_id=request_id_for(request))


@app.post('/api/threads/{thread_id}/retry')
def thread_retry(thread_id: UUID, body: ThreadApproval, request: Request, user: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    return conversation_service(request).retry(user, str(thread_id), body.version, request_id=request_id_for(request))


@app.get('/api/memories')
def list_memories(request: Request, user: int = Depends(auth.current_user_id)):
    return conversation_service(request).memories(user)


@app.post('/api/memories/{thread_id}/{version}/control')
def control_memory(thread_id: UUID, version: int, body: MemoryControl, request: Request, user: int = Depends(auth.current_user_id)):
    """사례 기억의 정정 메모·철회·복구·삭제. 대화·판정 승인 원본과 견적서는 변경하지 않는다."""
    auth.check_origin(request)
    return conversation_service(request).control_memory(user, str(thread_id), version, body.action, body.correction)


# 직접 등록한 #73 API와 health·Google 콜백이 SPA보다 먼저 처리되도록 마지막에 연결한다.
from backend.api.conversations import router as conversations_router
app.include_router(projects_router)
app.include_router(quotes_router)
app.include_router(conversations_router)
mount_frontend(app, FRONTEND_DIST, LOGIN_PAGE)
