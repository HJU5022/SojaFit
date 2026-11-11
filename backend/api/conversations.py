"""인증된 React 대화의 HTTP 경계. run·재개는 사용자 분석 서비스(`memory_service.Conversations`)를 거친다.

- 첫 run에 같은 UUID의 분석 회로·thread를 만들고 대상 부품을 고정한다(바꾸면 409).
- 결과는 그래프 상태에서 공개 값만 골라 `public.runs`·`public.messages`에 저장한 뒤 SSE로 보낸다.
- 완료 · 거절 결과에는 그 질문으로 찾은 사용자 사실(`profile_hints`, 참고(내 설정))을 붙여 보낸다. run 기록에는 저장하지 않는다.
- 분석 서비스가 없으면(THREADS_ENABLED≠1) 스트림을 열기 전에 503, 하루 토큰 상한이 찼으면 스트림을 열기 전에 429 `LIMIT_EXCEEDED`다(`admission`).
- 스트림을 연 뒤의 실패는 `failed` frame의 `error.code`로 보낸다. 코드는 공통 오류와 같은 표(`backend/errors.py`, ADR 0019)다.
하지 않는 일: 그래프 조립·예산·Store 기억·Langfuse(분석 서비스가 맡는다), 저장 SQL(`backend/conversations/repository.py`).
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

import psycopg
from psycopg_pool import PoolTimeout
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend import auth
from backend.errors import code_for, log_error
from backend.conversations.dto import BrowserResult, public_state, result_dto, stored_evidence
from backend.conversations.dto import BrowserResult, public_state, result_dto, safe_judgement
from backend.conversations.repository import ConversationNotFound, ConversationRepository, InvalidRunState
from backend.conversations.models import RunStatus
from backend.judge import conditions as judge_conditions
from backend.services import demo

router = APIRouter(prefix='/api', tags=['conversations'])
_tasks = set()
LOGGER = logging.getLogger('backend.api.conversations')


class RoleLabel(BaseModel):
    code: str
    name: str


class StartRun(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [
        {'question': 'D1을 1N5819로 바꿔도 되나요?', 'target_ref': 'D1', 'conditions': '입력 최대 12 V, 부하 전류 0.5 A'}]})
    question: str = Field(min_length=1, max_length=4000)
    target_ref: str = Field(max_length=100)
    conditions: str = Field(default='', max_length=2000)


class ResumeRun(BaseModel):
    # [왜] role은 interrupt가 역할을 물었을 때(role_choices)만 보낸다. 예시는 회로 값만 답하는 흔한 경우다
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'answers': {'v_in_max': '12', 'i_max': '0.5'}}]})
    answers: dict[str, str] = Field(max_length=30)
    role: str | None = Field(default=None, pattern=r'R(?:0[1-9]|1[0-9]|2[0-3])')

    @field_validator('answers')
    @classmethod
    def safe_answers(cls, value):
        forbidden = {'price', 'stock', 'product_url', 'fetched_at'}
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key) or key.lower() in forbidden
               or len(answer) > 200 or '://' in answer for key, answer in value.items()):
            raise ValueError('invalid answer')
        return value


class DemoResume(BaseModel):
    answers: dict[str, str]  # 비면 '모름'으로 재개한 것이다
    role: str  # 역할을 묻지 않았으면 빈 글자


class DemoQuestion(BaseModel):
    """키 없는 데모가 재생하는 기록 질문 하나(data/demo/recordings/outcomes.json). 기록한 답 · 판정 · 경로는 싣지 않는다."""
    id: str
    kind: str
    circuit: str
    demo_id: str | None  # React 데모 회로 id(GET /api/demo-circuits). 카탈로그에 없는 회로면 null
    target: str
    question: str  # 이 글자 그대로 새 대화의 첫 질문으로 보내야 재생된다(사용 조건도 같음)
    conditions: str
    resume: DemoResume | None  # 조건 질문에 보낼 기록한 답 · 역할. 조건 질문이 없던 질문은 null


class Thread(BaseModel):
    id: str  # UUID 문자열(분석 thread와 같은 UUID)
    project_id: int


class ThreadSummary(Thread):
    title: str
    created_at: datetime
    last_activity_at: datetime
    latest_run_id: str | None
    status: RunStatus | None


class SavedMessage(BaseModel):
    id: int
    run_id: str
    role: Literal['user', 'assistant']
    content: str
    created_at: datetime


class SavedRun(BaseModel):
    id: str
    status: RunStatus
    message_id: int | None


class ThreadDetail(Thread):
    title: str
    target_ref: str | None
    target_locked: bool
    latest_run: SavedRun | None
    messages: list[SavedMessage]
    next_before_message_id: int | None


class Run(BaseModel):
    id: str
    thread_id: str
    message_id: int | None  # 완료 · 거절 결과의 assistant 메시지. 승인(POST /api/messages/{id}/approvals)에 쓴다
    result: BrowserResult  # SSE 마지막 이벤트와 같은 공개 결과(profile_hints는 저장하지 않아 빈 목록)


# [왜] run · 재개는 SSE라 response_model로 적을 수 없다. /docs에는 이벤트 이름과 data 모양을 설명으로 적는다(SPEC 4절과 같은 내용)
SSE_RESPONSE = {200: {'description': (
    'text/event-stream. 각 frame은 `event: 이름`과 `data: JSON` 한 줄이다. 순서: '
    '`run_started` `{run_id, request_id}` → `status` (공개 결과, status=running, stage=입력 확인) → 마지막 하나: '
    '`requires_input` (stage=판정, interrupt `{missing, role_choices, question}`, 수정 가능한 재개 오류면 선택 error `{code, message}`) · '
    '`completed` · `refused` (stage=완료, answer · evidence · judgement · refusal · profile_hints) · '
    '`failed` (stage=오류, 공개 결과에 `error: {code, message}`, code는 공통 오류 표). '
    '공개 결과 칸은 GET /api/runs/{run_id}의 result와 같다(BrowserResult). '
    '실패 상태를 저장하지 못하면 마지막 frame 없이 끝난다.'),
    'content': {'text/event-stream': {'schema': {'type': 'string'}}}}}


def repository():
    try:
        yield ConversationRepository()
    except ConversationNotFound:
        raise HTTPException(404, '대화를 찾을 수 없습니다.') from None
    except (InvalidRunState, psycopg.errors.UniqueViolation):
        raise HTTPException(409, 'run_in_progress') from None
    except (psycopg.Error, KeyError, OSError):
        raise HTTPException(503, '대화 서비스를 사용할 수 없습니다.') from None


def analysis_service(request: Request):
    """THREADS_ENABLED=1로 띄운 사용자 분석 서비스. 없으면 스트림을 열기 전에 공통 503."""
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service


@router.get('/judge/roles', response_model=list[RoleLabel])
def list_judge_roles(user_id: int = Depends(auth.current_user_id)):
    del user_id
    return [RoleLabel(code=code, name=rule['name']) for code, rule in sorted(judge_conditions.load().items())]


@router.get('/demo-questions', response_model=list[DemoQuestion])
def list_demo_questions(user_id: int = Depends(auth.current_user_id), analysis=Depends(analysis_service)):
    """키 없는 데모(DEMO_REPLAY=1)의 기록 질문 목록. 재생 모드가 아니면 404(화면은 버튼을 숨긴다), 기록 파일이 없으면 503."""
    del user_id
    if analysis.mode != 'demo':
        raise HTTPException(404, '키 없는 데모 재생 모드가 아닙니다.')
    return demo.questions()  # [주의] 응답 모델이 칸을 고른다. outcomes.json의 답 · 판정 · 넷리스트 경로는 나가지 않는다


@router.get('/projects/{project_id}/threads', response_model=list[ThreadSummary])
def list_threads(project_id: int, response: Response, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    response.headers['Cache-Control'] = 'no-store'
    return repo.list_threads(user_id, project_id)


@router.get('/threads/{thread_id}', response_model=ThreadDetail)
def thread_detail(thread_id: UUID, response: Response, limit: int = Query(50, ge=1, le=100),
                  before_message_id: int | None = Query(None, gt=0, le=9223372036854775807), user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    response.headers['Cache-Control'] = 'no-store'
    return repo.thread_detail(user_id, str(thread_id), limit=limit, before_message_id=before_message_id)


@router.post('/projects/{project_id}/threads', status_code=201, response_model=Thread, dependencies=[Depends(auth.check_origin)])
def create_thread(project_id: int, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return {'id': repo.create_thread(user_id, project_id), 'project_id': project_id}


@router.delete('/threads/{thread_id}', status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_thread(thread_id: UUID, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    repo.delete_thread(user_id, str(thread_id))


@router.get('/runs/{run_id}', response_model=Run)
def get_run(run_id: UUID, request: Request, response: Response, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    response.headers['Cache-Control'] = 'no-store'
    run = repo.get_run(user_id, str(run_id))
    return {'id': run['id'], 'thread_id': run['thread_id'], 'message_id': run.get('message_id'),
            'result': result_dto(run['safe_result'], request_id=request.state.request_id, status=run['status']).model_dump()}


@router.post('/runs/{run_id}/recover', response_model=Run, dependencies=[Depends(auth.check_origin)])
def recover_run(run_id: UUID, request: Request, response: Response, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    """소유 실행의 오래된 상태만 정리한다. 분석·모델 호출이나 질문 재전송은 하지 않는다."""
    repo.recover_stale_run(user_id, str(run_id))
    return get_run(run_id, request, response, user_id, repo)


# [왜] failed는 시스템 오류다. 거절(refused, 답할 수 없는 질문)은 답이라 finished(완료)로 끝난다. 둘을 같은 말로 쓰지 않는다
STAGES = {'running': '입력 확인', 'judge': '판정', 'finished': '완료', 'failed': '오류'}


def frame(kind, payload):
    return f'event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


FINISH_RETRY_DELAYS = (0, 0.05, 0.2)


async def finish_with_retry(repo, user_id, thread_id, run_id, status, result):
    """짧은 DB 장애에는 제한된 횟수만 재시도하고, 상태 저장 전 terminal 이벤트를 보내지 않는다."""
    last_error = None
    for delay in FINISH_RETRY_DELAYS:
        if delay:
            await asyncio.sleep(delay)
        try:
            await run_in_threadpool(repo.finish, user_id, thread_id, run_id, status, result)
            return
        except (psycopg.Error, OSError) as exc:
            last_error = exc
    raise last_error


def outcome(analysis, thread_id, detail, request_id):
    """분석 서비스가 끝낸 thread를 React 결과 하나(종류, 공개 DTO)로 바꾼다."""
    if detail.get('interrupt'):
        return 'requires_input', result_dto({}, request_id=request_id, status='requires_input', stage=STAGES['judge'], interrupt=detail['interrupt'])
    state = analysis.graph.get_state(analysis.config(thread_id)).values or {}
    kind = 'refused' if state.get('refusal') else 'completed'
    return kind, result_dto(public_state(state), request_id=request_id, status=kind, stage=STAGES['finished'],
                            profile_hints=detail.get('profile_hints') or [],
                            input_conditions=(state.get('judgement') or {}).get('input_conditions', []))


def public_error(exc, request_id, run_id):
    """실패 frame에 넣을 공통 오류 코드·문구를 고르고 로그 한 줄을 남긴다(4xx는 INFO, 5xx · 예상 못 한 예외는 traceback까지)."""
    if isinstance(exc, HTTPException):
        # 예산 429(LIMIT_EXCEEDED) · 간격 429(RATE_LIMITED), 시간 초과 504, 바깥 장애 502, 데모 질문 422, 조건 대기 409(CONDITION_PENDING)처럼
        # 분석 서비스가 정한 상태 · 코드 · 공개 문구를 그대로 쓴다
        status, error = exc.status_code, {'code': code_for(exc.status_code, exc), 'message': str(exc.detail)}
    elif isinstance(exc, (psycopg.Error, PoolTimeout)):
        # [왜] 분석 전 잠금 · 예산 확인의 DB 장애는 보통 요청이면 공통 503(main.py의 database_unavailable)이다. 스트림에서도 같은 코드로 보낸다
        status, error = 503, {'code': 'UNAVAILABLE', 'message': '저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.'}
    else:
        status, error = 500, {'code': 'INTERNAL_ERROR', 'message': '분석을 완료하지 못했습니다.'}
    log_error(status, error['code'], exc, request_id=request_id, run_id=run_id)
    return error


def stream(repo, user_id, thread_id, run_id, request_id, analysis, call, *, resuming=False):
    """분석 서비스 호출(call)을 스레드에서 돌리고, 결과를 저장한 뒤 마지막 상태 하나를 보낸다."""
    queue = asyncio.Queue()
    async def execute():
        error = None
        await queue.put(frame('status', result_dto({}, request_id=request_id, status='running', stage=STAGES['running']).model_dump()))
        try:
            kind, safe = await run_in_threadpool(lambda: outcome(analysis, thread_id, call(), request_id))
            # [왜] profile_hints는 저장하지 않는다. 사용자가 사실을 지우면 지난 run 조회에도 남지 않게 한다
            # 공개 응답에만 붙이는 출처 URL과 표시 조건은 DB의 고정 저장 형식에서 제외한다.
            saved = {'answer': safe.answer, 'evidence': stored_evidence(safe.evidence), 'question_type': safe.question_type, 'price_parts': safe.price_parts, 'interrupt': safe.interrupt, 'judgement': safe_judgement(safe.judgement)}
            await finish_with_retry(repo, user_id, thread_id, run_id, kind, saved)
            await queue.put(frame(kind, safe.model_dump()))
        except Exception as exc:
            error = public_error(exc, request_id, run_id)
            if resuming and isinstance(exc, HTTPException) and exc.status_code in (400, 409, 422, 429):
                try:
                    detail = await run_in_threadpool(analysis.detail, user_id, thread_id)
                    if detail.get('interrupt'):
                        safe = result_dto({}, request_id=request_id, status='requires_input', stage=STAGES['judge'], interrupt=detail['interrupt'])
                        await finish_with_retry(repo, user_id, thread_id, run_id, 'requires_input', {'interrupt': safe.interrupt})
                        await queue.put(frame('requires_input', {**safe.model_dump(), 'error': error}))
                        await queue.put(None)
                        return
                except Exception:
                    LOGGER.exception('react_resume_restore_failed', extra={'request_id': request_id, 'run_id': run_id})
        if error:
            try:
                await finish_with_retry(repo, user_id, thread_id, run_id, 'failed', None)
                payload = result_dto({}, request_id=request_id, status='failed', stage=STAGES['failed']).model_dump()
                await queue.put(frame('failed', {**payload, 'error': error}))
            except Exception:
                # [주의] 실패 상태도 저장하지 못하면 terminal frame 없이 끝난다. GET /api/runs는 running으로 남는다
                LOGGER.exception('react_run_failure_unsaved', extra={'request_id': request_id, 'run_id': run_id})
        await queue.put(None)
    task = asyncio.create_task(execute())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    async def output():
        yield frame('run_started', {'run_id': run_id, 'request_id': request_id})
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    return StreamingResponse(output(), media_type='text/event-stream', headers={'Cache-Control': 'no-store'})


@router.post('/threads/{thread_id}/runs', response_class=StreamingResponse, responses=SSE_RESPONSE, dependencies=[Depends(auth.check_origin)])
async def start_run(thread_id: UUID, body: StartRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), analysis=Depends(analysis_service)):
    thread, request_id = str(thread_id), request.state.request_id
    # [왜] 하루 토큰 상한(429) · 대상 부품 확인(422·409) · 데모 질문 확인(422 · 기록 없음 503)을 run 행보다 먼저 끝내야
    #      거절된 요청이 '실행 중' run을 남기지 않고 공통 오류로 끝난다
    await run_in_threadpool(analysis.admission, user_id)
    _, _, connections, name = await run_in_threadpool(repo.get_thread, user_id, thread)
    await run_in_threadpool(analysis.ensure_thread, user_id, thread, name, connections, body.target_ref,
                            question=body.question, conditions=body.conditions)
    run_id, _ = await run_in_threadpool(repo.start, user_id, thread, body.model_dump())
    call = lambda: analysis.message(user_id, thread, body.question, body.conditions, request_id=request_id)
    return stream(repo, user_id, thread, run_id, request_id, analysis, call)


@router.post('/runs/{run_id}/resume', response_class=StreamingResponse, responses=SSE_RESPONSE, dependencies=[Depends(auth.check_origin)])
async def resume_run(run_id: UUID, body: ResumeRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), analysis=Depends(analysis_service)):
    run = await run_in_threadpool(repo.get_run, user_id, str(run_id))
    interrupt = (run.get('safe_result') or {}).get('interrupt', {})
    if 'missing' in interrupt and set(body.answers) - set(interrupt['missing']):
        raise HTTPException(422, '요청한 조건의 답만 입력하세요.')
    choices = interrupt.get('role_choices', [])
    if choices and body.role not in choices:
        raise HTTPException(422, '요청된 역할 중 하나를 선택해 주세요.')
    if not choices and body.role is not None:
        raise HTTPException(422, '이 run에는 역할 선택이 필요하지 않습니다.')
    thread, request_id = run['thread_id'], request.state.request_id
    await run_in_threadpool(analysis.admission, user_id)  # 스트림 전에 공통 오류 429로 거절한다(run 상태를 바꾸지 않음)
    await run_in_threadpool(repo.resume, user_id, thread, str(run_id))
    # [왜] 분석 서비스는 현재 결과 버전의 조건 질문만 재개한다. React run은 버전을 모르므로 지금 버전을 읽어 넘긴다
    call = lambda: analysis.resume(user_id, thread, body.answers, body.role or '', analysis.detail(user_id, thread)['version'], request_id=request_id)
    return stream(repo, user_id, thread, str(run_id), request_id, analysis, call, resuming=True)
