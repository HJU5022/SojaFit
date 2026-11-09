"""인증된 대화와 D5 실행의 HTTP 경계."""
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend import auth
from backend.conversations.dto import result_dto
from backend.conversations.repository import ConversationNotFound, ConversationRepository, InvalidRunState
from backend.services.d5 import RunInput, production_service

router = APIRouter(prefix='/api', tags=['conversations'])
_tasks = set()


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


def service_factory():
    return lambda: production_service(os.environ['DATABASE_URL'])


@router.get('/projects/{project_id}/threads')
def list_threads(project_id: int, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return repo.list_threads(user_id, project_id)


@router.post('/projects/{project_id}/threads', status_code=201, dependencies=[Depends(auth.check_origin)])
def create_thread(project_id: int, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return {'id': repo.create_thread(user_id, project_id), 'project_id': project_id}


@router.get('/threads/{thread_id}')
def get_thread(thread_id: UUID, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return repo.thread_detail(user_id, str(thread_id))


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


def stream(repo, user_id, thread_id, run_id, request_id, service, data, resume=False):
    queue = asyncio.Queue()
    async def execute():
        terminal = False
        try:
            async with service() as d5:
                if resume:
                    source = d5.resume(thread_id, data['answers'], role=data.get('role')) if data.get('role') else d5.resume(thread_id, data['answers'])
                else:
                    source = d5.start(thread_id, data)
                async for event in source:
                    if event.type == 'status':
                        await queue.put(frame('status', result_dto({}, request_id=request_id, status='running', stage=STAGES.get(event.stage, '결과 정리')).model_dump()))
                    else:
                        safe = result_dto(event.state, request_id=request_id, status=event.type,
                                          stage=STAGES.get(event.stage, '추가 정보 필요' if event.type == 'requires_input' else '완료'), interrupt=event.interrupt)
                        saved = {'answer': safe.answer, 'evidence': safe.evidence, 'question_type': safe.question_type, 'price_parts': safe.price_parts, 'interrupt': safe.interrupt, 'judgement': safe.judgement or None}
                        await finish_with_retry(repo, user_id, thread_id, run_id, event.type, saved)
                        terminal = True
                        await queue.put(frame(event.type, safe.model_dump()))
                        break
        except Exception:
            pass
        if not terminal:
            try:
                await finish_with_retry(repo, user_id, thread_id, run_id, 'failed', None)
                await queue.put(frame('failed', result_dto({}, request_id=request_id, status='failed', stage='거절').model_dump()))
            except Exception:
                pass
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
async def start_run(thread_id: UUID, body: StartRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), service=Depends(service_factory)):
    thread = str(thread_id)
    run_id, circuit = await run_in_threadpool(repo.start, user_id, thread, body.model_dump())
    data = RunInput(question=body.question, target_ref=body.target_ref, conditions=body.conditions, connections=circuit)
    return stream(repo, user_id, thread, run_id, request.state.request_id, service, data)


@router.post('/runs/{run_id}/resume', dependencies=[Depends(auth.check_origin)])
async def resume_run(run_id: UUID, body: ResumeRun, request: Request, user_id: int = Depends(auth.current_user_id), repo=Depends(repository), service=Depends(service_factory)):
    run = await run_in_threadpool(repo.get_run, user_id, str(run_id))
    choices = (run.get('safe_result') or {}).get('interrupt', {}).get('role_choices', [])
    if choices and body.role not in choices:
        raise HTTPException(422, '요청된 역할 중 하나를 선택해 주세요.')
    if not choices and body.role is not None:
        raise HTTPException(422, '이 run에는 역할 선택이 필요하지 않습니다.')
    await run_in_threadpool(repo.resume, user_id, run['thread_id'], str(run_id))
    return stream(repo, user_id, run['thread_id'], str(run_id), request.state.request_id,
                  service, body.model_dump(exclude_none=True), resume=True)
