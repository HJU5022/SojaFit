"""오류 코드 15개(ADR 0019)와 오류 로그 한 줄 시험. DB · 바깥 호출 없음.

- 역할: 코드 표와 `ApiError` · `code_for`, 상황 코드가 나는 실제 자리(조건 대기 · 하루 상한 · 호출 간격 · 분석 실패의 502 · 504 · 실행 상한),
  (승인 409 `ALREADY_APPROVED`는 test_quotes.py, Origin 403 `ORIGIN_MISMATCH`는 test_health.py)
  API 응답과 SSE `failed`의 code, 오류 응답 로그의 severity · request_id · traceback과 질문 글 비노출을 본다.
- 하지 않는 일: 실제 DB의 소유권 필터 · 가입 횟수(tests/api/test_auth.py · test_threads.py의 DB 시험), JSON 줄 모양 자체(test_logs.py).
- 출처: ADR 0019, SPEC.md 4절 공통 오류, backend/errors.py.
"""
import io
import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openai import APIConnectionError  # 예외 모양만 만든다(호출 없음)

from backend import auth, logs
from backend.conversations.memory_service import Conversations
from backend.conversations.repository import ConversationNotFound
from backend.errors import DEFAULT_CODES, SPECIAL_CODES, ApiError, code_for
from backend.main import app
from backend.services import llm

ORIGIN = {'origin': 'http://testserver'}
QUESTION = 'PRIVATE_QUESTION_TEXT 회로의 D1을 바꿔도 되나요'


def test_table_has_fifteen_codes_and_defaults():
    assert len(set(DEFAULT_CODES.values()) | set(SPECIAL_CODES)) == 15
    assert [code_for(s) for s in (400, 422, 429, 502, 503, 504)] == ['VALIDATION_ERROR', 'VALIDATION_ERROR', 'RATE_LIMITED',
                                                                   'UPSTREAM_ERROR', 'UNAVAILABLE', 'TIMEOUT']
    assert code_for(405) == 'VALIDATION_ERROR' and code_for(501) == 'INTERNAL_ERROR'  # 표에 없는 상태도 15개 안에서
    assert code_for(409, ApiError(409, 'x', code='CONDITION_PENDING')) == 'CONDITION_PENDING'
    with pytest.raises(ValueError):
        ApiError(409, 'x', code='LIMIT_EXCEEDED')  # 표와 다른 상태


def test_method_not_allowed_uses_a_table_code():
    response = TestClient(app).post('/health')
    assert response.status_code == 405 and response.json()['error']['code'] == 'VALIDATION_ERROR'


@pytest.fixture
def web(monkeypatch):
    """로그인 · Origin을 통과시킨 TestClient. 끝나면 의존성 바꿔치기와 분석 서비스를 지운다."""
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    yield lambda: TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    if hasattr(app.state, 'conversations'):
        del app.state.conversations


def test_other_users_run_is_not_found(web, monkeypatch):
    class OwnerFiltered:  # 저장소가 남의 run을 못 찾은 것으로 다룬다(실제 SQL 소유자 필터는 DB 시험)
        def get_run(self, user, run_id):
            raise ConversationNotFound
    monkeypatch.setattr('backend.api.conversations.ConversationRepository', OwnerFiltered)
    response = web().get(f'/api/runs/{uuid4()}')
    assert response.status_code == 404 and response.json()['error']['code'] == 'NOT_FOUND'


def test_missing_database_url_is_unavailable_not_internal_error(monkeypatch):
    """DATABASE_URL이 없으면 로그인 확인(auth.connection)이 공통 503 `UNAVAILABLE`이다(예전에는 KeyError로 500)."""
    monkeypatch.delenv('DATABASE_URL', raising=False)  # [주의] .env를 읽은 값이 있어도 지운다
    monkeypatch.setenv('DEMO_MODE', '1')
    response = TestClient(app, cookies={auth.COOKIE: 'x' * 43}).get('/api/auth/me')  # 쿠키가 있어야 DB까지 간다
    error = response.json()['error']
    assert response.status_code == 503 and error['code'] == 'UNAVAILABLE'
    assert error['message'] == '저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.'
    assert error['request_id'] == response.headers['X-Request-ID']


def test_google_callback_without_database_url_still_redirects_to_login(monkeypatch):
    """Google 콜백은 브라우저 이동이라 DB 설정 누락(503)도 JSON이 아니라 로그인 화면 오류로 돌려보낸다."""
    monkeypatch.delenv('DATABASE_URL', raising=False)
    for name, value in {'DEMO_MODE': '1', 'GOOGLE_AUTH_ENABLED': '1', 'GOOGLE_CLIENT_ID': 'test-client', 'GOOGLE_CLIENT_SECRET': 'test-secret'}.items():
        monkeypatch.setenv(name, value)
    client = TestClient(app, follow_redirects=False, cookies={'sojafit_google_browser': 'browser'})
    response = client.get('/api/auth/google/callback', params={'state': 'state', 'code': 'code'})
    assert response.status_code == 303 and response.headers['location'] == '/login?google=error'


def test_signup_daily_ip_limit_is_rate_limited(web, monkeypatch):
    def limited(*args):  # auth.signup이 IP 하루 3회를 넘기면 내는 오류와 같다
        raise HTTPException(status_code=429, detail='오늘 이 네트워크에서 가입할 수 있는 횟수를 넘었습니다.')
    monkeypatch.setattr('backend.main.auth.signup', limited)
    response = web().post('/api/auth/signup', json={'email': 'a@example.test', 'password': 'synthetic-pass-123', 'consent': True}, headers=ORIGIN)
    assert response.status_code == 429 and response.json()['error']['code'] == 'RATE_LIMITED'


class Conn:
    """execute(...).fetchone()이 차례로 rows를 돌려주는 가짜 연결."""
    def __init__(self, *rows): self.rows, self.sql = list(rows), []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.sql.append(sql)
        return SimpleNamespace(fetchone=lambda: self.rows.pop(0) if self.rows else {'user_id': 1})


def service(**attrs):
    """DB 없이 메서드 하나만 부를 분석 서비스."""
    svc = Conversations.__new__(Conversations)
    svc.mode = 'live'
    for key, value in attrs.items():
        setattr(svc, key, value)
    return svc


def test_token_cap_is_limit_exceeded():
    with pytest.raises(ApiError) as error:
        Conversations._token_room(Conn({'mine': 200_000, 'service': 0}), 1)
    assert error.value.code == 'LIMIT_EXCEEDED' and '200,000 토큰' in error.value.detail


@pytest.mark.parametrize('spent, code', [(False, 'RATE_LIMITED'), (True, 'LIMIT_EXCEEDED')])
def test_interval_and_daily_usd_get_different_codes(spent, code, monkeypatch):
    monkeypatch.setenv('ANALYSIS_MIN_INTERVAL_SECONDS', '2')
    conn = Conn({'mine': 0, 'service': 0}, None, {'spent': spent})  # 토큰 자리 있음 → 간격 · USD 갱신 실패 → USD 다 씀?
    with pytest.raises(HTTPException) as error:
        service(connection=lambda: conn)._budget(1)
    assert code_for(429, error.value) == code
    assert ('Retry-After' in (error.value.headers or {})) == (code == 'RATE_LIMITED')  # 다음 날까지는 다시 시도 안내를 붙이지 않는다


def test_pending_condition_is_condition_pending():
    @contextmanager
    def locked(user, thread):
        yield None, {'version': 1}
    svc = service(_purge_expired=lambda: None, locked=locked, _reconcile=lambda conn, row: None,
                  graph=SimpleNamespace(get_state=lambda config: SimpleNamespace(next=('판정',))))
    with pytest.raises(ApiError) as error:
        svc.message(1, 'thread', QUESTION)
    assert (error.value.status_code, error.value.code) == (409, 'CONDITION_PENDING')


def invoke_failure(error, *, late=False):
    """분석 실행(_invoke)에서 그래프가 error를 내면 바깥으로 나가는 HTTPException."""
    def fail(inputs, config):
        if late:
            budget.started -= budget.max_seconds + 1  # 시간 예산을 다 쓴 뒤에 난 오류
        raise error
    budget = llm.EvaluationBudget(max_calls=4, max_usd=1.0, max_seconds=60, prompt_rate=1e-6, completion_rate=1e-6)
    svc = service(graph=SimpleNamespace(invoke=fail), _current_memories=lambda user, items: items)
    with pytest.raises(HTTPException) as raised:
        svc._invoke(Conn(), 'thread', {}, budget, 'req-1')
    return raised.value.status_code, code_for(raised.value.status_code, raised.value)


@pytest.mark.parametrize('error, expected', [
    (llm.UpstreamError('Voyage error 503'), (502, 'UPSTREAM_ERROR')),
    (httpx.ConnectTimeout('voyage'), (502, 'UPSTREAM_ERROR')),
    (APIConnectionError(request=httpx.Request('POST', 'https://openrouter.ai/api/v1/chat')), (502, 'UPSTREAM_ERROR')),  # LLM 연결 끊김
    (psycopg.OperationalError('db down'), (503, 'UNAVAILABLE')),
    (RuntimeError('VOYAGE_API_KEY is required'), (503, 'UNAVAILABLE')),  # 키 없음은 우리 설정 문제
    (llm.EvaluationLimitError('호출 상한'), (429, 'LIMIT_EXCEEDED')),
])
def test_analysis_failure_codes(error, expected):
    assert invoke_failure(error) == expected


@pytest.mark.parametrize('error', [llm.EvaluationLimitError('분석 시간 상한'), httpx.ReadTimeout('voyage')])
def test_time_budget_is_timeout(error):
    assert invoke_failure(error, late=True) == (504, 'TIMEOUT')


class FailingAnalysis:
    """스트림 안에서 error를 내는 가짜 분석 서비스. 실행 중 로그 한 줄도 남긴다(스레드 풀에서 request_id가 이어지는지 볼 때)."""
    def __init__(self, error): self.error = error
    def admission(self, user): pass
    def ensure_thread(self, *args): pass
    def message(self, user, thread, text, conditions='', request_id=''):
        logging.getLogger('backend.conversations').warning('fake_step')
        raise self.error


class Repo:
    def __init__(self): self.thread = str(uuid4())
    def get_thread(self, user, thread_id): return thread_id, 1, {'parts': [{'ref': 'D1'}], 'nets': []}, '프로젝트'
    def start(self, user, thread_id, data): return str(uuid4()), {}
    def finish(self, *args): pass


def run_failure(web, error):
    from backend.api.conversations import repository
    repo = Repo()
    app.dependency_overrides[repository] = lambda: repo
    app.state.conversations = FailingAnalysis(error)
    response = web().post(f'/api/threads/{repo.thread}/runs', json={'question': QUESTION, 'target_ref': 'D1'}, headers=ORIGIN)
    return response, json.loads(response.text.split('event: failed\ndata: ', 1)[1].split('\n', 1)[0])


@pytest.mark.parametrize('error, code', [
    (ApiError(409, '먼저 요청한 조건에 답해주세요.', code='CONDITION_PENDING'), 'CONDITION_PENDING'),
    (ApiError(429, '하루 분석 예약 예산에 도달했습니다.', code='LIMIT_EXCEEDED'), 'LIMIT_EXCEEDED'),
    (HTTPException(502, 'LLM · 검색 서비스가 응답하지 않습니다.'), 'UPSTREAM_ERROR'),
    (HTTPException(504, '분석 실행의 시간·호출·예약 예산 상한에 도달했습니다.'), 'TIMEOUT'),
    (psycopg.OperationalError('db down'), 'UNAVAILABLE'),  # 분석 전 잠금 · 예산 확인의 DB 장애도 보통 요청과 같은 코드
])
def test_sse_failed_frame_uses_the_same_table(web, error, code):
    _, failed = run_failure(web, error)
    assert failed['status'] == 'failed' and failed['error']['code'] == code


@contextmanager
def json_lines():
    """backend.* 로그를 서버와 같은 JSON 한 줄로 모은다(INFO 이상)."""
    stream, handler, logger = io.StringIO(), logging.StreamHandler(), logging.getLogger('backend')
    handler.stream = stream
    handler.setFormatter(logs.JsonFormatter())
    level, logger.level = logger.level, logging.INFO
    logger.addHandler(handler)
    lines = []
    try:
        yield lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
        lines.extend(json.loads(line) for line in stream.getvalue().splitlines())


def test_every_run_log_line_has_request_id_and_no_question(web):
    secret = RuntimeError(f'model echoed {QUESTION}')  # 예외 메시지에 질문 글이 섞여도
    with json_lines() as lines:
        response, failed = run_failure(web, secret)
    request_id = failed['request_id']
    assert lines and all(line['request_id'] == request_id for line in lines)  # 스레드 풀 안의 줄까지
    assert {line['message'].split('\n')[0] for line in lines} == {'fake_step', 'request_failed'}
    error = next(line for line in lines if line['message'].startswith('request_failed'))
    assert (error['severity'], error['code'], error['status']) == ('ERROR', 'INTERNAL_ERROR', 500)
    assert 'Traceback (most recent call last)' in error['message'] and 'RuntimeError' in error['message']
    assert 'PRIVATE_QUESTION_TEXT' not in json.dumps(lines, ensure_ascii=False) and 'PRIVATE_QUESTION_TEXT' not in response.text


def test_unhandled_500_and_4xx_log_lines(web, monkeypatch):
    def broken(*args):
        raise RuntimeError(f'login failed for {QUESTION}')
    monkeypatch.setattr('backend.main.auth.authenticate', broken)
    with json_lines() as lines:
        failed = web().post('/api/auth/login', json={'email': 'user@example.test', 'password': 'synthetic-pass-123'}, headers=ORIGIN)
        refused = web().post('/api/auth/logout', headers={'origin': 'https://evil.example'})
    first, second = lines
    assert (first['severity'], first['code'], first['status'], first['request_id']) == ('ERROR', 'INTERNAL_ERROR', 500, failed.headers['X-Request-ID'])
    assert 'Traceback (most recent call last)' in first['message'] and 'PRIVATE_QUESTION_TEXT' not in first['message']
    assert (second['severity'], second['code'], second['status'], second['request_id']) == ('INFO', 'ORIGIN_MISMATCH', 403, refused.headers['X-Request-ID'])
    assert second['message'] == 'request_failed'  # 4xx는 traceback · 문구 없이
    assert 'user@example.test' not in json.dumps(lines)


def test_response_send_sees_request_id():
    """uvicorn은 응답 시작을 보낼 때 접속 로그를 남긴다. 그 순간 문맥 변수에 이 요청의 ID가 있어야 접속 줄에도 붙는다."""
    seen = []

    async def server(scope, receive, send):
        async def logged_send(message):
            if message['type'] == 'http.response.start':
                seen.append(logs.REQUEST_ID.get())
            await send(message)
        await app(scope, receive, logged_send)
    response = TestClient(server).get('/health')
    assert seen == [response.headers['X-Request-ID']]
