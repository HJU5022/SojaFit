"""인증된 React 대화의 HTTP 경계. run·재개는 사용자 분석 서비스(`memory_service.Conversations`)를 거친다.

- 첫 run에 같은 UUID의 분석 회로·thread를 만들고 대상 부품을 고정한다(바꾸면 409). 대상을 안 보내면 서버가 정하고,
  못 정하면 대상 없이 그래프를 돌려 계획이 대상을 써야 할 때만 `requires_input`(target_choices)으로 묻는다. 고른 부품은 재개(`ResumeRun.target`)로 받는다(SPEC 8.9).
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
from backend.conversations.dto import BrowserResult, public_state, result_dto, safe_judgement, stored_evidence
from backend.conversations.repository import ConversationNotFound, ConversationRepository, InvalidRunState
from backend.conversations.memory_service import other_targets_note
from backend.conversations.models import RunStatus
from backend.judge import conditions as judge_conditions
from backend.multi_agent.messages import CIRCUIT_MISSING, NEED_NETLIST
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
    # [왜] 없으면 서버가 정한다: 질문에 적힌 지원 다이오드 → 회로의 유일한 지원 다이오드 → 둘 이상이면 계획이 대상을 써야 할 때만 requires_input으로 묻는다(SPEC 8.9)
    target_ref: str | None = Field(default=None, max_length=100)
    conditions: str = Field(default='', max_length=2000)


class ResumeRun(BaseModel):
    # [왜] role은 interrupt가 역할을 물었을 때(role_choices)만, target은 대상 부품을 물었을 때(target_choices)만 보낸다. 예시는 회로 값만 답하는 흔한 경우다
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'answers': {'v_in_max': '12', 'i_max': '0.5'}}]})
    answers: dict[str, str] = Field(max_length=30)
    role: str | None = Field(default=None, pattern=r'R(?:0[1-9]|1[0-9]|2[0-3])')
    target: str | None = Field(default=None, max_length=100)
    # 폼 대신 글로 적은 답("전원은 5V, 전류는 잘 몰라"). 읽기 LLM이 사용 조건처럼 읽는다(SPEC 4절 재개, 11-17)
    text: str = Field(default='', max_length=1000)

    @field_validator('text')
    @classmethod
    def safe_text(cls, value):
        value = value.strip()
        if '://' in value or any(ord(ch) < 32 and ch not in '\n\t' for ch in value):
            raise ValueError('주소나 제어 문자는 넣을 수 없습니다.')
        return value

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
    circuit_version: int
    title: str
    created_at: datetime
    last_activity_at: datetime
    latest_run_id: str | None
    status: RunStatus | None


class ThreadListItem(Thread):
    """모든 프로젝트를 모은 대화 목록의 한 줄(사이드바 "대화"). title은 고친 이름, 없으면 첫 질문으로 만든 이름."""
    project_name: str
    title: str
    created_at: datetime
    last_activity_at: datetime


class RenameThread(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'title': 'D1 쇼트키 교체 검토'}]})
    title: str

    @field_validator('title')
    @classmethod
    def valid_title(cls, value: str) -> str:
        # [왜] 줄바꿈 · 겹친 공백을 한 칸으로 줄인 뒤 잰다. DB CHECK(ck_threads_title)는 앞뒤 공백을 막아 여기서 못 거르면 422가 아니라 503이 된다
        value = ' '.join(value.split())
        if not 1 <= len(value) <= 200:
            raise ValueError('대화 이름은 1~200자여야 합니다.')
        return value


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
    circuit_version: int
    previous_thread_id: UUID | None = None
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
    result: BrowserResult  # 저장·재조회 가능한 공개 결과는 SSE와 동일하다. profile_hints와 judgement.input_conditions는 요청/표시용 SSE 전용 칸이라 저장하지 않아 GET에서 비어 있거나 생략될 수 있다


# [왜] run · 재개는 SSE라 response_model로 적을 수 없다. /docs에는 이벤트 이름과 data 모양을 설명으로 적는다(SPEC 4절과 같은 내용)
SSE_RESPONSE = {200: {'description': (
    'text/event-stream. 각 frame은 `event: 이름`과 `data: JSON` 한 줄이다. 순서: '
    '`run_started` `{run_id, request_id}` → `status` (공개 결과, status=running, stage=입력 확인) → '
    '진행 단계가 바뀔 때마다 `status` 0개 이상 (같은 모양, stage=품번 확인 · 질문 분석 · 문서 검색 · 회로 역할 읽기 · 후보 판정 · 답 작성 중 하나. '
    '그래프 노드가 시작할 때 보내며, 동시 실행 · 재계획이면 순서가 섞이거나 같은 이름이 다시 올 수 있다) → 마지막 하나: '
    '`requires_input` (stage=판정, interrupt `{missing, role_choices, question}`, 대상 부품을 물으면 interrupt `{target_choices: [{ref, value}], question}` '
    '(질문 분석 뒤 대상이 필요한 질문에만 온다. 고른 ref를 ResumeRun.target으로 보낸다), 수정 가능한 재개 오류면 선택 error `{code, message}`) · '
    '`completed` · `refused` (stage=완료, answer · evidence · judgement · refusal · profile_hints) · '
    '`failed` (stage=오류, 공개 결과에 `error: {code, message}`, code는 공통 오류 표). '
    '저장 가능한 공개 결과 칸은 GET /api/runs/{run_id}의 result와 같다(BrowserResult). '
    '`profile_hints`와 `judgement.input_conditions`는 각각 사용자 설정 참고와 판정 입력 표시를 위한 SSE 전용 칸이라 저장·재조회에 포함되지 않을 수 있다. '
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


@router.get('/threads', response_model=list[ThreadListItem])
def list_all_threads(response: Response, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    """내 모든 프로젝트의 대화, 마지막 활동이 최근인 순. 다른 사용자의 대화는 나오지 않는다."""
    response.headers['Cache-Control'] = 'no-store'
    return repo.list_all_threads(user_id)


@router.patch('/threads/{thread_id}', response_model=ThreadListItem, dependencies=[Depends(auth.check_origin)])
def rename_thread(thread_id: UUID, body: RenameThread, user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return repo.rename_thread(user_id, str(thread_id), body.title)


@router.get('/threads/{thread_id}', response_model=ThreadDetail)
def thread_detail(thread_id: UUID, response: Response, limit: int = Query(50, ge=1, le=100),
                  before_message_id: int | None = Query(None, gt=0, le=9223372036854775807), user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    response.headers['Cache-Control'] = 'no-store'
    return repo.thread_detail(user_id, str(thread_id), limit=limit, before_message_id=before_message_id)


@router.post('/projects/{project_id}/threads', status_code=201, response_model=Thread, dependencies=[Depends(auth.check_origin)])
def create_thread(project_id: int, circuit_version: int | None = Query(None, ge=0, le=9223372036854775807),
                  user_id: int = Depends(auth.current_user_id), repo=Depends(repository)):
    return {'id': repo.create_thread(user_id, project_id, circuit_version), 'project_id': project_id}


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
# 실행 중 진행 단계: 그래프 노드 이름(backend/multi_agent/build.py) → 화면에 보일 단계 이름(SPEC 4절 SSE 표).
# [왜] 표에 없는 노드(기억 읽기 · Spec 에이전트 묶음 · 가격 안내 · 부품 목록 · 견적 안내 · 끝내기 · 거절)는 따로 보이지 않는다. 마지막 frame이 곧 온다
NODE_STAGES = {'입력 읽기': STAGES['running'], '품번·판 확인': '품번 확인', 'Supervisor': '질문 분석', 'RAG 에이전트': '문서 검색',
               '회로 읽기': '회로 역할 읽기', '대체 부품 판정': '후보 판정',
               '답 모으기': '답 작성', '답 정리': '답 작성', '종합': '답 작성', '답 검사': '답 작성'}


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
    # [왜] state가 있으면 그래프를 돌리지 않은 결과다(키 없는 데모의 회로 없는 질문, start_run)
    state = detail.get('state') or analysis.graph.get_state(analysis.config(thread_id)).values or {}
    kind = 'refused' if state.get('refusal') else 'completed'
    # [왜] 웹 검색 장애 표시(#28)는 그래프 상태가 아니라 분석 서비스가 이번 실행에서 본 값이다(memory_service._invoke)
    public = {**public_state(state), 'web_search_unavailable': detail.get('web_search_unavailable') is True}
    if kind == 'completed' and state.get('connections'):
        # [왜] 대상은 대화마다 하나다. 질문에 적은 다른 지원 다이오드('D1 D2 둘 다'의 D2)는 보지 않았다고 답 끝에 알린다(#62)
        public['answer'] += other_targets_note(state['connections'], state.get('question'), state.get('target'))
    return kind, result_dto(public, request_id=request_id, status=kind, stage=STAGES['finished'],
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
    """분석 서비스 호출 call(progress)을 스레드에서 돌리며 진행 단계를 보내고, 결과를 저장한 뒤 마지막 상태 하나를 보낸다."""
    queue = asyncio.Queue()
    loop, stage = asyncio.get_running_loop(), STAGES['running']

    def show(node):
        """(이벤트 루프에서) 노드 하나가 시작했다. 화면 단계 이름이 바뀌었을 때만 status frame을 보낸다."""
        nonlocal stage
        if NODE_STAGES.get(node, stage) != stage:
            stage = NODE_STAGES[node]
            queue.put_nowait(frame('status', result_dto({}, request_id=request_id, status='running', stage=stage).model_dump()))

    # [왜] 분석은 스레드 풀에서 돈다(동시 Send면 여러 스레드). asyncio.Queue는 스레드에 안전하지 않아 루프 쪽으로 넘겨 넣는다.
    #      넘긴 순서대로 돌고, 분석 호출이 끝나기 전에 넘겨지므로 마지막 frame보다 늘 앞이다
    progress = lambda node: loop.call_soon_threadsafe(show, node)

    async def execute():
        error = None
        await queue.put(frame('status', result_dto({}, request_id=request_id, status='running', stage=STAGES['running']).model_dump()))
        try:
            kind, safe = await run_in_threadpool(lambda: outcome(analysis, thread_id, call(progress), request_id))
            # [왜] profile_hints는 저장하지 않는다. 사용자가 사실을 지우면 지난 run 조회에도 남지 않게 한다
            saved = {'answer': safe.answer, 'evidence': stored_evidence(safe.evidence), 'question_type': safe.question_type, 'price_parts': safe.price_parts, 'interrupt': safe.interrupt, 'judgement': safe_judgement(safe.judgement),
                     'web_search_unavailable': safe.web_search_unavailable}
            await finish_with_retry(repo, user_id, thread_id, run_id, kind, saved)
            await queue.put(frame(kind, safe.model_dump()))
        except Exception as exc:
            error = public_error(exc, request_id, run_id)
            if resuming and isinstance(exc, HTTPException) and exc.status_code in (400, 409, 422, 429):
                try:
                    detail = await run_in_threadpool(analysis.detail, user_id, thread_id)
                    if detail.get('interrupt'):
                        safe = result_dto({}, request_id=request_id, status='requires_input', stage=STAGES['judge'], interrupt=detail['interrupt'])
                        await finish_with_retry(repo, user_id, thread_id, run_id, 'requires_input', {'interrupt': safe.interrupt, 'error': error})
                        await queue.put(frame('requires_input', {**safe.model_dump(), 'error': error}))
                        await queue.put(None)
                        return
                except Exception:
                    LOGGER.exception('react_resume_restore_failed', extra={'request_id': request_id, 'run_id': run_id})
        if error:
            try:
                await finish_with_retry(repo, user_id, thread_id, run_id, 'failed', {'error': error})
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
    if not connections.get('components', connections.get('parts')) and analysis.mode == 'demo':
        # [왜] 키 없는 데모에는 회로 없는 질문의 기록이 없다. 그래프 · 분석 thread 없이 넷리스트를 달라는 거절로 끝내 화면이 회로를 고르게 한다(SPEC 7절 · 8.9)
        run_id, _ = await run_in_threadpool(repo.start, user_id, thread, body.model_dump())
        needs = {'answer': NEED_NETLIST, 'refusal': {'code': CIRCUIT_MISSING, 'message': NEED_NETLIST}}
        return stream(repo, user_id, thread, run_id, request_id, analysis, lambda progress: {'state': needs})
    reply = await run_in_threadpool(analysis.ensure_thread, user_id, thread, name, connections, body.target_ref,
                                    question=body.question, conditions=body.conditions)
    if not reply and connections.get('components', connections.get('parts')):
        # [왜] 위 확인은 대화를 처음 만들 때만 돈다. 이어지는 질문의 없는 기호("D3 대체할 부품", 회로에는 D1 · D2뿐)는 품번으로 읽혀
        #      "D3의 데이터시트를 찾을 수 없어요"로 거절됐다(11-17 운영 대화 실측). 같은 코드 글로 답한다
        from backend.conversations.memory_service import absent_diode_reply, unsupported_diode_reply
        # 회로에 있지만 지원 대상이 아닌 다이오드 모양 기호(LED인 D3)도 같은 길로 답한다
        reply = absent_diode_reply(connections, body.question) or unsupported_diode_reply(connections, body.question)
    run_id, _ = await run_in_threadpool(repo.start, user_id, thread, body.model_dump())
    if reply:
        # [왜] 질문이 회로에 없는 다이오드 기호(D9)만 적었다. 코드가 그 사실과 회로의 다이오드를 답하고 그래프는 돌리지 않는다(LLM이 지어내지 않게, SPEC 8.9 · #62)
        return stream(repo, user_id, thread, run_id, request_id, analysis, lambda progress: {'state': {'answer': reply}})
    call = lambda progress: analysis.message(user_id, thread, body.question, body.conditions, request_id=request_id, progress=progress)
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
    targets = [c['ref'] for c in interrupt.get('target_choices') or []]
    if targets and (body.target not in targets or body.answers or body.text):  # 부품을 물은 run은 부품 하나만 받는다
        raise HTTPException(422, '제시된 부품 중 하나를 골라 주세요.')
    if not targets and body.target is not None:
        raise HTTPException(422, '이 run에는 부품 선택이 필요하지 않습니다.')
    thread, request_id = run['thread_id'], request.state.request_id
    try:
        await run_in_threadpool(analysis.admission, user_id)
    except HTTPException as exc:
        if exc.status_code == 429:
            await run_in_threadpool(repo.record_resume_error, user_id, str(run_id),
                                    {'code': code_for(exc.status_code, exc), 'message': str(exc.detail)})
        raise
    if targets:
        # [왜] 고른 부품을 분석 thread의 대상으로 고정한다(대상 확인 · 데모 질문 확인 422는 run을 그대로 두고 스트림 전에 끝난다).
        #      그 뒤 그래프의 '대상 확인'에서 멈춘 질문을 아래에서 재개한다(Supervisor를 다시 부르지 않는다, #62)
        pending = run['safe_result'].get('pending_start')
        _, _, connections, name = await run_in_threadpool(repo.get_thread, user_id, thread)
        await run_in_threadpool(analysis.ensure_thread, user_id, thread, name, connections, body.target,
                                question=(pending or {}).get('question'), conditions=(pending or {}).get('conditions', ''))
        if pending:
            # [왜] #62 전에 그래프 없이 물은 run이다. 그래프가 돈 적이 없으니 재개가 아니라 처음 질문으로 돌린다
            await run_in_threadpool(repo.resume, user_id, thread, str(run_id))
            call = lambda progress: analysis.message(user_id, thread, pending['question'], pending['conditions'], request_id=request_id, progress=progress)
            return stream(repo, user_id, thread, str(run_id), request_id, analysis, call)
    await run_in_threadpool(repo.resume, user_id, thread, str(run_id))
    # [왜] 분석 서비스는 현재 결과 버전의 조건 질문만 재개한다. React run은 버전을 모르므로 지금 버전을 읽어 넘긴다
    call = lambda progress: analysis.resume(user_id, thread, body.answers, body.role or '', analysis.detail(user_id, thread)['version'],
                                            request_id=request_id, progress=progress, **({'text': body.text} if body.text else {}))
    return stream(repo, user_id, thread, str(run_id), request_id, analysis, call, resuming=True)
