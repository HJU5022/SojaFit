"""SojaFit FastAPI 진입점: 앱을 조립만 한다.

역할: 수명(lifespan) · 공통 오류 처리기 · 미들웨어(요청 ID · 대화 본문 한도) · 라우터 등록 · React SPA 연결. 경로 함수는 두지 않는다.
  경로는 `backend/api/<이름>.py` 라우터에 있고 화면의 `frontend/src/api/<이름>.ts`와 짝이다(health · auth · admin · prices · profile · projects · quotes · conversations).
호출자: uvicorn(`backend.main:app`), Docker Compose의 api 서비스와 API·프론트 통합 테스트.
하지 않는 일: 경로 처리(`backend/api/`), 인증·세션·계정 처리(`backend/auth.py`), Mouser 호출 자체, 저장소 SQL과 그래프 실행 자체.
출처: SPEC.md 4절(공통 오류, 대화 본문 한도)·8.6절(로그인 AC), docs/specs/api-error-contract.md, ADR 0019, backend/BACKEND.md.
읽는 환경변수: THREADS_ENABLED · DATABASE_URL(분석 저장소). 경로가 읽는 AUTH_ORIGIN · DEMO_MODE 등은 각 라우터 머리말에 적는다.
시작할 때 JSON 로그를 켜고(`backend/logs.py`), auth.validate_auth_configuration()이 AUTH_SECRET·DEMO_MODE 조합을 검사한다.
오류 응답의 `error.code`는 `backend/errors.py`의 표(ADR 0019, 16개)에서 고르고, 오류 응답마다 code · status · request_id 로그 한 줄을 남긴다.
THREADS_ENABLED=1이면 명시적으로 준비한 DATABASE_URL의 분석 저장소·MCP 세션을 앱 수명 동안 관리한다.
"""
import os
from http import HTTPStatus
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import auth, logs
from backend.errors import DEFAULT_CODES, SPECIAL_CODES, code_for, log_error
from backend.api.admin import router as admin_router
from backend.api.auth import router as auth_router
from backend.api.health import router as health_router
from backend.api.prices import router as prices_router
from backend.api.projects import router as projects_router
from backend.api.external_circuits import router as external_circuits_router
from backend.api.quotes import router as quotes_router
from backend.web.app import mount_frontend


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 JSON 로그를 켜고 인증 설정을 검사한다."""
    logs.setup()  # [주의] 루트 로거에 처리기가 이미 있으면(pytest 등) 손대지 않는다
    # [왜] 잘못된 AUTH_SECRET으로 뜬 서버가 약한 세션 해시를 쓰지 않도록 RuntimeError로 기동 자체를 막는다
    auth.validate_auth_configuration()
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


class ErrorPayload(BaseModel):
    """클라이언트가 분기하고 사용자에게 표시할 공개 오류 정보."""

    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    """모든 JSON 오류 응답의 최상위 구조."""

    error: ErrorPayload


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
    if request.url.path.startswith("/api/external-circuits/schematics"):
        response_headers["Cache-Control"] = "private, no-store"
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


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000",
}


async def add_request_id(request: Request, call_next):
    """클라이언트 값 대신 서버 UUID를 모든 응답에 넣고, 이 요청에서 남기는 로그 줄에도 같은 값을 붙인다(등록은 파일 끝)."""
    request.state.request_id = str(uuid4())
    # [왜] 문맥 변수는 이 요청의 task와 거기서 만든 task · 스레드 풀 호출에 복사된다.
    #      가장 바깥 미들웨어는 응답을 보내는 task(uvicorn 접속 로그를 남기는 곳)와 같아 거기까지 같은 ID가 붙는다
    logs.REQUEST_ID.set(request.state.request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    # [왜] 보안 응답 헤더(D7 2-3절): 형식 추측 금지, 다른 사이트의 iframe 금지, HTTPS 고정(http에서는 브라우저가 무시한다).
    #      setdefault라 Google 로그인 경로가 직접 넣은 Referrer-Policy: no-referrer는 그대로 남는다
    # shortcut: Content-Security-Policy는 없다(React 번들의 스타일 · 스크립트 출처를 확인해야 함), 화면이 굳으면 더한다
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
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


@app.middleware('http')
async def conversation_boundary(request: Request, call_next):
    """대화 run(`/api/threads/...`)과 내 설정(`/api/me/memory`) 응답에 no-store를 붙이고, `/api/` 아래 본문 있는 요청을 128 KiB로 막는다."""
    private = request.url.path.startswith(('/api/threads', '/api/me/memory'))
    schematic = request.url.path.startswith('/api/external-circuits/schematics')
    # [왜] 재개(`/api/runs/{id}/resume`) · 승인 · 로그인 등 JSON 경로도 같은 한도를 쓴다(D6 1-2절).
    #      넷리스트 업로드만 뺀다: 그 경로는 5 MiB 한도를 스스로 센다(backend/api/projects.py)
    netlist_upload = request.url.path == '/api/projects/upload' or (request.url.path.startswith('/api/projects/') and request.url.path.endswith('/netlist'))
    limited = (request.url.path.startswith('/api/') and not netlist_upload
               and request.method in ('POST', 'PATCH', 'PUT', 'DELETE'))
    if limited:
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
    if schematic:
        response.headers['Cache-Control'] = 'private, no-store'
    return response


async def database_unavailable(request: Request, error):
    return error_response(request, status_code=503, code=DEFAULT_CODES[503],
                          message='저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.',
                          headers={'Cache-Control': 'no-store'}, error=error)


app.add_exception_handler(psycopg.Error, database_unavailable)
app.add_exception_handler(PoolTimeout, database_unavailable)


# API 라우터가 SPA보다 먼저 처리되도록 화면 연결은 마지막에 둔다(등록 순서가 곧 경로 찾는 순서).
from backend.api.conversations import router as conversations_router
from backend.api.profile import router as profile_router
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(prices_router)
app.include_router(projects_router)
app.include_router(external_circuits_router)
app.include_router(quotes_router)
app.include_router(conversations_router)
app.include_router(profile_router)
mount_frontend(app, FRONTEND_DIST)
# [주의] 마지막에 등록한 미들웨어가 가장 바깥에서 돈다. 요청 ID를 화면 연결 · 본문 한도 미들웨어보다 먼저 정해야
#        본문 413 · 500 · 접속 로그까지 같은 ID를 쓴다(안쪽 미들웨어 task에서 넣은 문맥 변수는 바깥 task로 올라오지 않는다)
app.middleware("http")(add_request_id)
