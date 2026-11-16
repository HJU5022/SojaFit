"""공통 오류 응답의 `error.code`(ADR 0019의 16개)와 오류 한 줄 로그.

역할: HTTP 상태마다 기본 코드(`DEFAULT_CODES`), 화면이 다르게 반응해야 하는 상황 코드 5개(`SPECIAL_CODES`)를 붙이는 `ApiError`,
예외 · 상태에서 코드를 고르는 `code_for`, 오류 응답 · 분석 실패 하나를 로그 한 줄로 남기는 `log_error`.
호출자: backend/main.py(공통 오류 처리기), backend/api/conversations.py(SSE `failed`), 상황 코드를 내는 곳
(backend/auth.py의 `check_origin`, backend/api/quotes.py, backend/api/external_circuits.py, backend/conversations/memory_service.py).
코드 표를 읽는 곳: backend/conversations/models.py(저장한 실행 오류의 code 검사).
하지 않는 일: 응답 JSON 만들기(backend/main.py의 `error_response`), 로그 줄 모양 · 요청 ID 연결(backend/logs.py),
바깥 서비스 장애 판별(backend/services/llm.py의 `is_upstream_error`).
출처: SPEC.md 4절 공통 오류, ADR 0019, docs/specs/api-error-contract.md.
[왜] backend/main.py가 라우터를 import하므로 라우터 · 서비스가 main에서 코드를 읽으면 순환 import가 된다. 그래서 따로 둔다.
"""
import logging

from fastapi import HTTPException

# 상황을 따로 고르지 않은 오류의 코드. 400 · 422는 둘 다 요청 · 파일 형식 오류라 같은 코드다
DEFAULT_CODES = {400: 'VALIDATION_ERROR', 401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'CONFLICT',
                 413: 'PAYLOAD_TOO_LARGE', 422: 'VALIDATION_ERROR', 429: 'RATE_LIMITED', 500: 'INTERNAL_ERROR',
                 502: 'UPSTREAM_ERROR', 503: 'UNAVAILABLE', 504: 'TIMEOUT'}
# [왜] 같은 HTTP 상태라도 화면이 다르게 행동해야 하는 상황만 나눈다(ADR 0019). 값은 그 코드가 쓰는 HTTP 상태다
SPECIAL_CODES = {'ORIGIN_MISMATCH': 403, 'CONDITION_PENDING': 409, 'ALREADY_APPROVED': 409, 'LIMIT_EXCEEDED': 429,
                 'SCHEMATIC_NOT_FOUND': 404}
LOGGER = logging.getLogger('backend.errors')


class ApiError(HTTPException):
    """기본 코드 대신 상황 코드(`SPECIAL_CODES`)를 붙이는 HTTPException. 코드와 상태가 표와 다르면 만들 때 ValueError."""

    def __init__(self, status_code: int, detail: str, *, code: str, headers: dict[str, str] | None = None):
        # [주의] 코드 이름 오타나 상태 착오를 시험에서 바로 드러낸다(표에 없는 코드가 화면으로 나가지 않게)
        if SPECIAL_CODES.get(code) != status_code:
            raise ValueError(f'{code}는 HTTP {status_code}에 쓰는 코드가 아닙니다')
        super().__init__(status_code, detail, headers)
        self.code = code


def code_for(status_code: int, error: BaseException | None = None) -> str:
    """응답 · SSE에 넣을 code. ApiError면 그 상황 코드, 아니면 상태의 기본 코드."""
    if isinstance(error, ApiError):
        return error.code
    # [왜] 표에 없는 상태(메서드가 틀린 405 등)도 16개 안에서 고른다. 4xx는 요청 오류, 5xx는 예상 못 한 오류다(ADR 0019 결과)
    return DEFAULT_CODES.get(status_code) or ('INTERNAL_ERROR' if status_code >= 500 else 'VALIDATION_ERROR')


def log_error(status_code: int, code: str, error: BaseException | None = None, **fields) -> None:
    """오류 응답 · 분석 실패 하나를 로그 한 줄로 남긴다. 4xx는 INFO(문구 · 본문 없이), 5xx는 ERROR에 traceback까지."""
    # [주의] fields에는 request_id · run_id 같은 식별자만 넘긴다. 질문 글 · 조건 · 넷리스트 · 이메일 · 키는 넣지 않는다
    # [왜] 4xx 문구는 사용자 입력(품번 등)을 담을 수 있어 남기지 않는다. code와 status면 무슨 오류였는지 안다
    extra = {'code': code, 'status': status_code, **fields}
    if status_code >= 500:
        # traceback은 backend/logs.py가 예외 메시지를 뺀 모양(프레임과 예외 이름)으로 적는다
        LOGGER.error('request_failed', exc_info=error, extra=extra)
    else:
        LOGGER.info('request_failed', extra=extra)
