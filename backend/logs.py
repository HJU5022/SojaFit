"""서버 로그를 Cloud Logging이 읽는 JSON 한 줄로 쓴다(표준 라이브러리만).

역할: 요청 ID 문맥 변수(`REQUEST_ID`), 줄마다 severity · time · logger · message · request_id와 `extra=` 칸을 담는 `JsonFormatter`,
메시지를 뺀 traceback(`safe_traceback`), 서버가 뜰 때 루트 · uvicorn 로거에 그 처리기를 한 번 붙이고
접속 줄의 쿼리 글을 가리는(`hide_query`) `setup`.
호출자: backend/main.py(lifespan의 `setup`, 요청 ID 미들웨어). 줄을 남기는 쪽은 `logging.getLogger('backend.…')`를 그대로 쓴다.
하지 않는 일: 무엇을 남길지 정하기(각 모듈, 오류 한 줄은 backend/errors.py의 `log_error`), 외부 로그 서비스로 보내기
(stdout에만 쓰고 Cloud Run이 모은다), 로그 보관.
출처: ADR 0019 결과(구조화 JSON 로그), SPEC.md 4절 공통 오류 · 7절(접속 로그 쿼리 가리기).
"""
import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone

# 요청 하나 동안의 서버 요청 ID. 요청 ID 미들웨어가 넣고, 그 요청에서 만든 task · 스레드 풀 호출이 복사해 받는다
REQUEST_ID: ContextVar[str | None] = ContextVar('request_id', default=None)
# [왜] LogRecord가 원래 가진 속성 이름. 이것 밖의 속성은 `extra=`로 넘긴 칸이라 JSON 칸으로 옮긴다
_RECORD_FIELDS = set(vars(logging.makeLogRecord({}))) | {'message', 'asctime'}


def safe_traceback(error: BaseException) -> str:
    """프레임(파일 · 줄 · 함수 · 코드 줄)과 예외 이름만 담은 traceback. 원인 사슬도 같은 모양으로 앞에 붙인다."""
    # [왜] 예외 메시지에는 질문 글(pydantic의 input_value) · 이메일(DB 오류의 DETAIL)이 섞일 수 있다. 메시지는 쓰지 않는다
    blocks, seen = [], set()
    while error is not None and id(error) not in seen:  # [주의] 원인 사슬이 고리를 이루면 거기서 멈춘다
        seen.add(id(error))
        kind = type(error)
        name = kind.__qualname__ if kind.__module__ == 'builtins' else f'{kind.__module__}.{kind.__qualname__}'
        blocks.append('Traceback (most recent call last):\n' + ''.join(traceback.format_tb(error.__traceback__)) + name)
        # 파이썬 기본 traceback과 같은 순서: `raise ... from`의 원인, 없으면(from None이 아닐 때) 처리 중 난 예외
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return '\n\nThe above exception led to the following exception:\n\n'.join(reversed(blocks))


def hide_query(record: logging.LogRecord) -> bool:
    """uvicorn 접속 줄의 경로에서 쿼리 글만 `?<redacted>`로 바꾼다. 줄은 버리지 않는다."""
    # [왜] 쿼리에는 사용자 글이 섞인다(`/api/me/memory?q=` 기억 검색어, Google 콜백의 code · state). 모든 경로에서 뺀다
    # uvicorn 접속 줄은 '%s - "%s %s HTTP/%s" %d' % (주소, 메서드, 쿼리 붙은 경로, HTTP 버전, 상태)다
    args = record.args
    if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str) and '?' in args[2]:
        record.args = (*args[:2], args[2].partition('?')[0] + '?<redacted>', *args[3:])
    return True


class JsonFormatter(logging.Formatter):
    """로그 기록 하나를 JSON 한 줄로 만든다. 기본 칸(severity · time · logger · message)은 같은 이름의 extra보다 앞선다."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = REQUEST_ID.get()
        entry = {'request_id': request_id} if request_id else {}
        # extra로 넘긴 칸(code · status · run_id 등). request_id를 직접 넘기면 문맥 변수 값보다 앞선다
        entry.update({key: value for key, value in vars(record).items() if key not in _RECORD_FIELDS})
        message = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            message += '\n' + safe_traceback(record.exc_info[1])  # [왜] Error Reporting은 message 안의 traceback을 읽는다
        entry.update(severity=record.levelname,  # [왜] Cloud Logging이 이 칸을 심각도로 읽는다(INFO · WARNING · ERROR)
                     time=datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec='milliseconds'),
                     logger=record.name, message=message)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup(stream=None) -> bool:
    """서버가 뜰 때 한 번: 루트 로거에 JSON 처리기(기본 stdout)를 붙이고 uvicorn 로거도 그리로 보낸다. 붙였으면 True."""
    root = logging.getLogger()
    # [주의] 루트에 처리기가 이미 있으면(pytest의 로그 수집, 다른 로그 설정) 아무것도 바꾸지 않는다.
    #        uvicorn 기본 설정은 루트를 건드리지 않아 서버에서는 늘 붙는다. 두 번째 부르면 이미 붙어 있어 그대로다
    if root.handlers:
        return False
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # [왜] 우리 코드(backend.*)만 INFO부터 남긴다. 루트는 WARNING 그대로라 라이브러리의 INFO 줄(httpx의 호출마다 URL 등)은 예전처럼 버린다.
    #      uvicorn 로거는 uvicorn 설정이 이미 INFO로 둔다
    logging.getLogger('backend').setLevel(logging.INFO)
    for name in ('uvicorn', 'uvicorn.access'):
        # [왜] uvicorn은 자기 처리기로 글 줄을 쓰고 루트로 올리지 않는다. 처리기를 비우고 올려 같은 JSON 줄로 쓴다.
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # [주의] 필터는 로거에 붙는다(처리기가 아니라). 처리기를 비워도 걸리고, main.py의 Google 콜백 필터보다 먼저 돈다
    logging.getLogger('uvicorn.access').addFilter(hide_query)
    # [왜] Starlette는 500 처리기(main.py의 internal_error)가 code · traceback을 남긴 뒤에도 같은 예외를 다시 올려
    #      uvicorn이 한 번 더 남긴다. 그 겹친 줄만 뺀다(lifespan 오류 등 다른 uvicorn 오류 줄은 그대로)
    logging.getLogger('uvicorn.error').addFilter(lambda record: not record.getMessage().startswith('Exception in ASGI application'))
    return True
