"""JSON 한 줄 로그(backend/logs.py)의 모양 · 요청 ID · 메시지 없는 traceback · 설정 시험.

- 역할: 줄마다 severity · time · logger · message, 문맥 변수와 extra의 request_id, traceback에 예외 메시지가 없는지,
  setup이 루트에 처리기가 있으면 손대지 않고 없으면 한 번만 붙이는지 본다.
- 하지 않는 일: 앱에 연결한 뒤의 오류 한 줄(tests/api/test_errors.py), 실제 uvicorn 서버 실행.
- 출처: ADR 0019 결과, SPEC.md 4절 공통 오류.
"""
import io
import json
import logging
from contextlib import contextmanager

from backend import logs


def record(message='event_name', *, level=logging.INFO, exc_info=None, **extra):
    """이름 `backend.test`의 로그 기록 하나를 만든다(처리기 없이 형식만 볼 때)."""
    item = logging.getLogger('backend.test').makeRecord('backend.test', level, __file__, 1, message, (), exc_info, extra=extra)
    return json.loads(logs.JsonFormatter().format(item))


def test_line_has_cloud_logging_fields_and_extra():
    line = record(code='CONFLICT', status=409, run_id='run-1')
    assert line['severity'] == 'INFO' and line['logger'] == 'backend.test' and line['message'] == 'event_name'
    assert line['time'].endswith('+00:00') and 'T' in line['time']
    assert (line['code'], line['status'], line['run_id']) == ('CONFLICT', 409, 'run-1')
    assert 'request_id' not in line  # 요청 밖(서버 시작 등)의 줄에는 없다


def test_request_id_comes_from_context_and_explicit_value_wins():
    token = logs.REQUEST_ID.set('ctx-id')
    try:
        assert record()['request_id'] == 'ctx-id'
        assert record(request_id='explicit-id')['request_id'] == 'explicit-id'
        # [왜] 기본 칸 이름을 extra로 넘겨도 심각도 · 시각은 바뀌지 않는다
        assert record(severity='DEBUG', time='x')['severity'] == 'INFO'
    finally:
        logs.REQUEST_ID.reset(token)


def test_traceback_keeps_frames_and_names_but_not_messages():
    # [주의] 비밀 글은 변수로 넘긴다. traceback의 코드 줄에는 소스가 그대로 나오므로 글자를 raise 줄에 쓰면 시험이 틀린다
    question, detail = '질문 원문 PRIVATE_QUESTION user@example.com', 'outer PRIVATE_DETAIL'
    def inner():
        raise ValueError(question)
    try:
        try:
            inner()
        except ValueError as error:
            raise RuntimeError(detail) from error
    except RuntimeError as error:
        line = record('request_failed', level=logging.ERROR, exc_info=(type(error), error, error.__traceback__))
    message = line['message']
    assert line['severity'] == 'ERROR' and message.startswith('request_failed\nTraceback (most recent call last):')
    assert 'in inner' in message and message.index('ValueError') < message.index('RuntimeError')  # 원인이 먼저
    assert 'PRIVATE_QUESTION' not in message and 'user@example.com' not in message and 'PRIVATE_DETAIL' not in message


def test_suppressed_context_and_cycles_stop():
    try:
        try:
            raise KeyError('hidden')
        except KeyError:
            raise LookupError('x') from None
    except LookupError as error:
        text = logs.safe_traceback(error)
    assert 'KeyError' not in text and text.endswith('LookupError')
    first, second = ValueError('a'), ValueError('b')
    first.__cause__, second.__cause__ = second, first
    assert logs.safe_traceback(first).count('ValueError') == 2


@contextmanager
def bare_root():
    """루트 처리기와 backend · uvicorn 로거 상태를 비워 서버 시작 상태를 흉내 내고 끝나면 되돌린다."""
    # [주의] pytest는 단계(준비 · 실행)마다 루트에 수집 처리기를 붙였다 뗀다. 픽스처가 아니라 시험 안에서 비우고 되돌린다
    root = logging.getLogger()
    loggers = [logging.getLogger(n) for n in ('backend', 'uvicorn', 'uvicorn.access', 'uvicorn.error')]
    saved = (root.handlers[:], [(l.level, l.handlers[:], l.propagate, l.filters[:]) for l in loggers])
    root.handlers.clear()
    try:
        yield root
    finally:
        root.handlers[:] = saved[0]
        for logger, (level, handlers, propagate, filters) in zip(loggers, saved[1]):
            logger.setLevel(level)
            logger.handlers[:], logger.propagate, logger.filters[:] = handlers, propagate, filters


def test_setup_attaches_once_and_routes_uvicorn():
    stream, access = io.StringIO(), logging.getLogger('uvicorn.access')
    token = logs.REQUEST_ID.set('req-access')
    with bare_root() as root:
        for name in ('uvicorn', 'uvicorn.access'):  # uvicorn 기본 설정처럼: INFO, 자기 처리기, 루트로 안 올림
            logging.getLogger(name).setLevel(logging.INFO)
        access.addHandler(logging.NullHandler())
        access.propagate = False
        assert logs.setup(stream) is True and logs.setup(stream) is False  # 두 번째는 그대로
        assert len(root.handlers) == 1 and access.propagate and not access.handlers
        access.info('%s - "%s %s HTTP/%s" %d', '127.0.0.1:1', 'GET', '/health', '1.1', 200)
        logging.getLogger('uvicorn.error').error('Exception in ASGI application\n')  # 500 처리기와 겹치는 줄은 뺀다
        logging.getLogger('uvicorn.error').info('Application startup complete.')
        logging.getLogger('backend.errors').info('request_failed')  # 우리 코드는 INFO부터
        logging.getLogger('httpx').info('HTTP Request: POST https://api.example/v1')  # 라이브러리 INFO는 예전처럼 버린다
    logs.REQUEST_ID.reset(token)
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [line['message'] for line in lines] == ['127.0.0.1:1 - "GET /health HTTP/1.1" 200', 'Application startup complete.', 'request_failed']
    assert lines[0]['logger'] == 'uvicorn.access' and lines[0]['request_id'] == 'req-access'


def test_setup_leaves_existing_logging_alone():
    # [왜] pytest가 루트에 로그 수집 처리기를 붙여 둔다. setup이 그걸 바꾸면 '로그에 키가 없다' 시험이 빈 로그로 통과한다
    before = logging.getLogger().handlers[:]
    assert before and logs.setup(io.StringIO()) is False and logging.getLogger().handlers == before
