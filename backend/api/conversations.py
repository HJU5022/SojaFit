"""인증된 React 대화의 HTTP 경계. run·재개는 사용자 분석 서비스(`memory_service.Conversations`)를 거친다.

- 첫 run에 같은 UUID의 분석 회로·thread를 만들고 대상 부품을 고정한다(바꾸면 409).
- 결과는 그래프 상태에서 공개 값만 골라 `public.runs`·`public.messages`에 저장한 뒤 SSE로 보낸다.
- 완료 · 거절 결과에는 그 질문으로 찾은 사용자 사실(`profile_hints`, 참고(내 설정))을 붙여 보낸다. run 기록에는 저장하지 않는다.
- 분석 서비스가 없으면(THREADS_ENABLED≠1) 스트림을 열기 전에 503이다.
하지 않는 일: 그래프 조립·예산·Store 기억·Langfuse(분석 서비스가 맡는다), 저장 SQL(`backend/conversations/repository.py`).
"""
import asyncio
import json
import logging
import re
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend import auth
from backend.conversations.dto import public_state, result_dto
from backend.conversations.repository import ConversationNotFound, ConversationRepository, InvalidRunState
from backend.judge import conditions as judge_conditions

router = APIRouter(prefix='/api', tags=['conversations'])
_tasks = set()
LOGGER = logging.getLogger('backend.api.conversations')


class RoleLabel(BaseModel):
    code: str
    name: str


class StartRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=4000)
    target_ref: str = Field(max_length=100)
    conditions: str = Field(default='', max_length=2000)


class ResumeRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
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


@router.get('/projects/{project_id}/threads')
def list_threads(project_id: int, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return repo.list_threads(user_id, project_id)


@router.post('/projects/{project_id}/threads', status_code=201, dependencies=[Depends(auth.check_origin)])
def create_thread(project_id: int, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return {'id': repo.create_thread(user_id, project_id), 'project_id': project_id}


@router.get('/runs/{run_id}')
def get_run(run_id: UUID, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    run = repo.get_run(user_id, str(run_id))
    return {'id': run['id'], 'thread_id': run['thread_id'], 'message_id': run.get('message_id'),
            'result': result_dto(run['safe_result'], request_id=request.state.request_id, status=run['status']).model_dump()}


STAGES = {'running': '입력 확인', 'judge': '판정', 'finished': '완료', 'failed': '거절'}


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
                            profile_hints=detail.get('profile_hints') or [])


def public_error(exc, request_id, run_id):
    """실패 frame에 넣을 공통 오류 코드·문구. 4xx가 아닌 예외는 request_id와 함께 traceback을 남긴다."""
    # [왜] backend.main이 이 라우터를 import하므로 모듈 첫머리에서 읽으면 순환 import가 된다
    from backend.main import ERROR_CODES
    if not isinstance(exc, HTTPException) or exc.status_code >= 500:
        LOGGER.exception(json.dumps({'event': 'react_run_failed', 'request_id': request_id, 'run_id': run_id}))
    if isinstance(exc, HTTPException):
        # 예산·간격 429, 시간 초과 504, 데모 질문 422, 조건 대기 409처럼 분석 서비스가 정한 공개 문구를 그대로 쓴다
        return {'code': ERROR_CODES.get(exc.status_code, 'INTERNAL_ERROR'), 'message': str(exc.detail)}
    return {'code': 'INTERNAL_ERROR', 'message': '분석을 완료하지 못했습니다.'}


def stream(repo, user_id, thread_id, run_id, request_id, analysis, call):
    """분석 서비스 호출(call)을 스레드에서 돌리고, 결과를 저장한 뒤 마지막 상태 하나를 보낸다."""
    queue = asyncio.Queue()
    async def execute():
        error = None
        await queue.put(frame('status', result_dto({}, request_id=request_id, status='running', stage=STAGES['running']).model_dump()))
        try:
            kind, safe = await run_in_threadpool(lambda: outcome(analysis, thread_id, call(), request_id))
            # [왜] profile_hints는 저장하지 않는다. 사용자가 사실을 지우면 지난 run 조회에도 남지 않게 한다
            saved = {'answer': safe.answer, 'evidence': safe.evidence, 'question_type': safe.question_type, 'price_parts': safe.price_parts, 'interrupt': safe.interrupt, 'judgement': safe.judgement or None}
            await finish_with_retry(repo, user_id, thread_id, run_id, kind, saved)
            await queue.put(frame(kind, safe.model_dump()))
        except Exception as exc:
            error = public_error(exc, request_id, run_id)
        if error:
            try:
                await finish_with_retry(repo, user_id, thread_id, run_id, 'failed', None)
                payload = result_dto({}, request_id=request_id, status='failed', stage=STAGES['failed']).model_dump()
                await queue.put(frame('failed', {**payload, 'error': error}))
            except Exception:
                # [주의] 실패 상태도 저장하지 못하면 terminal frame 없이 끝난다. GET /api/runs는 running으로 남는다
                LOGGER.exception(json.dumps({'event': 'react_run_failure_unsaved', 'request_id': request_id, 'run_id': run_id}))
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


@router.post('/threads/{thread_id}/runs', dependencies=[Depends(auth.check_origin)])
async def start_run(thread_id: UUID, body: StartRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), analysis=Depends(analysis_service)):
    thread, request_id = str(thread_id), request.state.request_id
    # [왜] 대상 부품 확인(422·409)을 run 행보다 먼저 끝내야 거절된 요청이 '실행 중' run을 남기지 않는다
    _, _, connections, name = await run_in_threadpool(repo.get_thread, user_id, thread)
    await run_in_threadpool(analysis.ensure_thread, user_id, thread, name, connections, body.target_ref)
    run_id, _ = await run_in_threadpool(repo.start, user_id, thread, body.model_dump())
    call = lambda: analysis.message(user_id, thread, body.question, body.conditions, request_id=request_id)
    return stream(repo, user_id, thread, run_id, request_id, analysis, call)


@router.post('/runs/{run_id}/resume', dependencies=[Depends(auth.check_origin)])
async def resume_run(run_id: UUID, body: ResumeRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), analysis=Depends(analysis_service)):
    run = await run_in_threadpool(repo.get_run, user_id, str(run_id))
    choices = (run.get('safe_result') or {}).get('interrupt', {}).get('role_choices', [])
    if choices and body.role not in choices:
        raise HTTPException(422, '요청된 역할 중 하나를 선택해 주세요.')
    if not choices and body.role is not None:
        raise HTTPException(422, '이 run에는 역할 선택이 필요하지 않습니다.')
    thread, request_id = run['thread_id'], request.state.request_id
    await run_in_threadpool(repo.resume, user_id, thread, str(run_id))
    # [왜] 분석 서비스는 현재 결과 버전의 조건 질문만 재개한다. React run은 버전을 모르므로 지금 버전을 읽어 넘긴다
    call = lambda: analysis.resume(user_id, thread, body.answers, body.role or '', analysis.detail(user_id, thread)['version'], request_id=request_id)
    return stream(repo, user_id, thread, str(run_id), request_id, analysis, call)
