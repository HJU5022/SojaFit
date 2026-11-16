import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import auth
from backend.errors import ApiError
from backend.main import app

ORIGIN = {'origin': 'http://testserver'}


def test_thread_delete_requires_login(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.delete(f'/api/threads/{uuid4()}', headers=ORIGIN).status_code == 401


def test_thread_delete_checks_origin_and_returns_empty_204(web, monkeypatch):
    from backend.conversations.repository import ConversationRepository
    calls, thread = [], str(uuid4())
    monkeypatch.setattr(ConversationRepository, 'delete_thread', lambda self, user, key: calls.append((user, key)))
    with web(None, None) as client:
        assert client.delete(f'/api/threads/{thread}').status_code == 403
        assert client.delete(f'/api/threads/{thread}', headers={'origin': 'https://other.invalid'}).status_code == 403
        assert client.delete('/api/threads/not-a-uuid', headers=ORIGIN).status_code == 422
        assert calls == []
        response = client.delete(f'/api/threads/{thread}', headers=ORIGIN)
    assert response.status_code == 204 and response.content == b''
    assert calls == [(1, thread)]


@pytest.mark.parametrize('failure_kind, status', [('missing', 404), ('busy', 409), ('database', 503)])
def test_thread_delete_uses_safe_errors(web, monkeypatch, failure_kind, status):
    import psycopg
    from backend.conversations.repository import ConversationRepository, ConversationNotFound, InvalidRunState
    def fail(*args):
        raise {'missing': ConversationNotFound, 'busy': InvalidRunState,
               'database': psycopg.OperationalError}[failure_kind]('private database detail')
    monkeypatch.setattr(ConversationRepository, 'delete_thread', fail)
    with web(None, None) as client:
        response = client.delete(f'/api/threads/{uuid4()}', headers=ORIGIN)
    assert response.status_code == status
    assert 'private database detail' not in response.text
    assert response.json()['error']['request_id']


class FakeAnalysis:
    """DB 없는 사용자 분석 서비스. 실제 서비스처럼 thread마다 대상 부품을 처음 값으로 고정한다."""
    def __init__(self, state=None, interrupt=None, error=None, refuse=None):
        self.calls, self.targets, self.version, self.hints, self.nodes = [], {}, 1, [], []
        self.state, self.interrupt, self.error, self.refuse = state or {'answer': 'ok'}, interrupt, error, refuse
        self.graph = SimpleNamespace(get_state=lambda config: SimpleNamespace(values=self.state))
    def config(self, thread): return {'configurable': {'thread_id': thread}}
    def admission(self, user):
        if self.refuse:  # 실제 서비스의 하루 토큰 상한 429처럼 스트림 전에 거절한다
            raise self.refuse
    def ensure_thread(self, user, thread, filename, connections, target, question=None, conditions=''):
        self.calls.append(('ensure', thread, filename, target, question, conditions))
        if self.targets.setdefault(thread, target) != target:
            raise HTTPException(409, '대상 부품을 바꾸려면 새 대화를 시작하세요.')
    def _run(self, *call):
        self.calls.append(call)
        if self.error:
            raise self.error
        return {'interrupt': self.interrupt, 'version': self.version, 'profile_hints': self.hints}
    def message(self, user, thread, text, conditions='', request_id='', progress=None):
        for node in self.nodes:  # 실제 서비스처럼 그래프 노드가 시작할 때마다 노드 이름으로 알린다
            progress(node)
        return self._run('message', thread, text, conditions)
    def resume(self, user, thread, answers, role, version, request_id='', progress=None): return self._run('resume', thread, answers, role, version)
    def detail(self, user, thread): return {'version': self.version}


class FakeRepo:
    def __init__(self, thread, run, status='running', result=None):
        self.thread, self.run, self.status, self.result, self.calls = thread, run, status, result or {}, []
    def get_thread(self, user, thread_id):
        assert thread_id == self.thread
        return thread_id, 1, {'parts': [{'ref': 'D1'}], 'nets': []}, '프로젝트'
    def start(self, user, thread_id, data):
        self.calls.append('start')
        return self.run, {}
    def resume(self, user, thread_id, run_id): self.calls.append(('claim', thread_id, run_id))
    def finish(self, user, thread_id, run_id, status, result):
        self.calls.append(('commit', status))
        self.status, self.result = status, result
    def get_run(self, user, run_id):
        return {'id': self.run, 'thread_id': self.thread, 'status': self.status, 'safe_result': self.result}
    def record_resume_error(self, user, run_id, error):
        self.result = {**self.result, 'error': error}


def test_recover_is_owned_origin_checked_and_never_calls_analysis(web):
    thread, run = str(uuid4()), str(uuid4())
    repo = FakeRepo(thread, run)
    def recover(user, key):
        assert (user, key) == (1, run)
        repo.calls.append('recover')
        repo.status = 'failed'
    repo.recover_stale_run = recover
    with web(None, repo) as client:
        assert client.post(f'/api/runs/{run}/recover').status_code == 403
        response = client.post(f'/api/runs/{run}/recover', headers=ORIGIN)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['result']['status'] == 'failed'
    assert repo.calls == ['recover']


def test_recover_requires_login(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post(f'/api/runs/{uuid4()}/recover', headers=ORIGIN).status_code == 401


def test_recover_does_not_expose_another_users_run(web, monkeypatch):
    from backend.conversations.repository import ConversationNotFound
    repo = FakeRepo(str(uuid4()), str(uuid4()))
    def recover(*args): raise ConversationNotFound
    repo.recover_stale_run = recover
    monkeypatch.setattr('backend.api.conversations.ConversationRepository', lambda: repo)
    with web(None, None) as client:
        response = client.post(f'/api/runs/{repo.run}/recover', headers=ORIGIN)
    assert response.status_code == 404 and repo.status == 'running'


def test_resume_unrequested_answers_leave_interrupt_unchanged(web):
    thread, run = str(uuid4()), str(uuid4())
    pause = {'interrupt': {'missing': ['v_in_max'], 'role_choices': []}}
    repo = FakeRepo(thread, run, status='requires_input', result=pause)
    analysis = FakeAnalysis()
    with web(analysis, repo) as client:
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {'other': '12'}}, headers=ORIGIN)
    assert response.status_code == 422
    assert repo.status == 'requires_input' and repo.result == pause
    assert repo.calls == [] and analysis.calls == []


def test_resume_system_error_does_not_restore_an_old_form(web):
    thread, run = str(uuid4()), str(uuid4())
    interrupt = {'missing': ['v_in_max'], 'role_choices': []}
    repo = FakeRepo(thread, run, status='requires_input', result={'interrupt': interrupt})
    analysis = FakeAnalysis(error=HTTPException(503, '분석을 완료하지 못했습니다.'))
    with web(analysis, repo) as client:
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in_max': '12'}}, headers=ORIGIN)
    assert 'event: failed' in response.text and repo.status == 'failed'


@pytest.mark.parametrize('status', [400, 409, 422, 429])
def test_resume_recoverable_error_keeps_form_and_can_resume_same_run(web, status):
    thread, run = str(uuid4()), str(uuid4())
    interrupt = {'missing': ['v_in_max'], 'role_choices': []}
    repo = FakeRepo(thread, run, status='requires_input', result={'interrupt': interrupt})
    analysis = FakeAnalysis(interrupt=interrupt, error=HTTPException(status, '입력을 확인하세요.'))
    analysis.detail = lambda *args: {'version': 1, 'interrupt': analysis.interrupt}
    with web(analysis, repo) as client:
        first = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in_max': 'wrong'}}, headers=ORIGIN)
        assert 'event: requires_input' in first.text and '입력을 확인하세요.' in first.text
        assert repo.status == 'requires_input' and repo.result['interrupt']['missing'] == ['v_in_max']
        saved = client.get(f'/api/runs/{run}').json()['result']
        assert saved['error'] == {'code': 'RATE_LIMITED' if status == 429 else 'VALIDATION_ERROR' if status in (400, 422) else 'CONFLICT', 'message': '입력을 확인하세요.'}
        analysis.error, analysis.interrupt = None, None
        second = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in_max': '12'}}, headers=ORIGIN)
    assert 'event: completed' in second.text and repo.status == 'completed'
    assert 'error' not in repo.result


@pytest.fixture
def web(monkeypatch):
    """로그인·Origin을 통과시키고, 넘긴 가짜 분석 서비스·저장소로 TestClient를 연다."""
    from backend.api.conversations import repository
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    def open_client(analysis, repo):
        app.dependency_overrides[auth.current_user_id] = lambda: 1
        if repo is not None:
            app.dependency_overrides[repository] = lambda: repo
        if analysis is not None:
            app.state.conversations = analysis
        return TestClient(app, raise_server_exceptions=False)
    yield open_client
    app.dependency_overrides.clear()
    if hasattr(app.state, 'conversations'):
        del app.state.conversations


def test_role_catalog_requires_login_and_exposes_only_code_and_name():
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/api/judge/roles').status_code == 401

    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get('/api/judge/roles')
        assert response.status_code == 200
        roles = response.json()
        assert {'code': 'R01', 'name': '역극성 보호(직렬)'} in roles
        assert roles == sorted(roles, key=lambda role: role['code'])
        assert all(set(role) == {'code', 'name'} for role in roles)
    finally:
        app.dependency_overrides.clear()


def test_thread_endpoint_requires_login():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/projects/1/threads')
    assert response.status_code == 401


def test_saved_thread_requires_login():
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(f'/api/threads/{uuid4()}').status_code == 401


def test_saved_thread_uses_read_only_repository_and_safe_response(web, monkeypatch):
    from backend.conversations.repository import ConversationRepository
    thread, run = str(uuid4()), str(uuid4())
    calls = []
    def detail(self, user, thread_id, limit=50, before_message_id=None):
        calls.append((user, thread_id, limit, before_message_id))
        return {'id': thread, 'project_id': 1, 'circuit_version': 1, 'title': '저장 질문', 'target_ref': 'D1', 'target_locked': True,
                'latest_run': {'id': run, 'status': 'completed', 'message_id': 2},
                'messages': [{'id': 2, 'run_id': run, 'role': 'assistant', 'content': '<img src=x>', 'created_at': '2026-11-11T00:00:00Z', 'raw_chunk': 'hidden'}],
                'next_before_message_id': None, 'checkpoint': 'hidden'}
    monkeypatch.setattr(ConversationRepository, 'thread_detail', detail)
    analysis = FakeAnalysis()
    with web(analysis, None) as client:
        response = client.get(f'/api/threads/{thread}?limit=2&before_message_id=4')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-request-id']
    assert calls == [(1, thread, 2, 4)]
    assert response.json()['messages'][0]['content'] == '<img src=x>'
    assert 'hidden' not in response.text
    assert analysis.calls == []


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'before_message_id=0', 'before_message_id=no', 'before_message_id=9223372036854775808'])
def test_saved_thread_rejects_invalid_page_before_repository(web, monkeypatch, query):
    from backend.conversations.repository import ConversationRepository
    monkeypatch.setattr(ConversationRepository, 'thread_detail', lambda *a, **k: pytest.fail('invalid page reached SQL'))
    with web(None, None) as client:
        assert client.get(f'/api/threads/{uuid4()}?{query}').status_code == 422
        assert client.get('/api/threads/not-a-uuid').status_code == 422


def test_saved_thread_not_found_and_database_error_use_existing_boundary(web, monkeypatch):
    import psycopg
    from backend.conversations.repository import ConversationNotFound, ConversationRepository
    def missing(*args, **kwargs): raise ConversationNotFound
    monkeypatch.setattr(ConversationRepository, 'thread_detail', missing)
    with web(None, None) as client:
        response = client.get(f'/api/threads/{uuid4()}')
        assert response.status_code == 404
    def unavailable(*args, **kwargs): raise psycopg.OperationalError('private connection detail')
    monkeypatch.setattr(ConversationRepository, 'thread_detail', unavailable)
    with web(None, None) as client:
        response = client.get(f'/api/threads/{uuid4()}')
        assert response.status_code == 503
        assert 'private connection detail' not in response.text


def test_live_conditions_are_shown_without_changing_saved_result(web):
    from backend.conversations.models import SafeResult
    thread, run = str(uuid4()), str(uuid4())
    rows = [{'code': 'v_in_max', 'value': '20 V'}, {'code': 'i_max', 'value': '0.15 A'}]
    analysis = FakeAnalysis(state={'answer': 'ok', 'judgement': {'kind': 'judge', 'input_conditions': rows}})
    repo = FakeRepo(thread, run)
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': '20V 150mA', 'target_ref': 'D1'}, headers=ORIGIN)
        frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        assert frames[-1]['status'] == 'completed'
        assert frames[-1]['judgement']['input_conditions'] == rows
        SafeResult.model_validate(repo.result)
        assert 'input_conditions' not in repo.result['judgement']
        recovered = client.get(f'/api/runs/{run}')
    assert recovered.json()['result']['judgement']['input_conditions'] == []
    assert len([call for call in analysis.calls if call[0] == 'message']) == 1


def test_first_run_creates_analysis_thread_and_saves_before_completed(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis(state={'answer': 'ok', 'facts': 'secret', 'question_type': 'candidate_judge'})
    repo = FakeRepo(thread, run)
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers=ORIGIN)
        assert response.status_code == 200
        assert response.text.index('event: run_started') < response.text.index('event: status') < response.text.index('event: completed')
        assert 'secret' not in response.text
        recovered = client.get(f'/api/runs/{run}')
    assert recovered.json()['result']['answer'] == 'ok'
    assert recovered.json()['result']['status'] == 'completed'
    # 데모 질문 확인도 스트림 전에 하도록 질문 · 조건을 같이 넘긴다
    assert analysis.calls == [('ensure', thread, '프로젝트', 'D1', 'hello', ''), ('message', thread, 'hello', '')]
    assert repo.calls == ['start', ('commit', 'completed')]


def sse_frames(text):
    """SSE 본문을 (이벤트 이름, data) 목록으로 나눈다."""
    return [(lines[0].removeprefix('event: '), json.loads(lines[1].removeprefix('data: ')))
            for block in text.strip().split('\n\n') if (lines := block.split('\n'))]


def test_run_streams_a_status_frame_per_new_stage_before_the_last_frame(web):
    """노드가 시작할 때마다 화면 단계가 바뀌면 status 하나. 같은 단계 · 표에 없는 노드는 보내지 않고, 마지막 frame은 그대로 하나다."""
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis()
    analysis.nodes = ['입력 읽기', '기억 읽기', '품번·판 확인', 'Supervisor', 'RAG 에이전트', 'Spec 에이전트', '회로 읽기',
                      '대체 부품 판정', '답 모으기', '답 정리', '답 검사', '끝내기']
    with web(analysis, FakeRepo(thread, run)) as client:
        frames = sse_frames(client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers=ORIGIN).text)
    assert [name for name, _ in frames] == ['run_started'] + ['status'] * 7 + ['completed']
    assert [data['stage'] for name, data in frames if name == 'status'] == ['입력 확인', '품번 확인', '질문 분석', '문서 검색', '회로 역할 읽기', '후보 판정', '답 작성']
    assert all(data['status'] == 'running' and data['answer'] == '' for name, data in frames if name == 'status')


@pytest.fixture
def native_input_path(monkeypatch):
    """Real HTTP/service/graph; fake SQL, auth and model replies only."""
    from contextlib import contextmanager
    from evals.runners import plan_injection_baseline as plan, run_injection_baseline as baseline
    from evals.runners import run_injection_preflight as pre
    from backend.conversations.memory_service import Conversations
    from backend.graph.netlist import parse_netlist
    from backend.services import llm
    def deny(*a,**k):
        pytest.fail('Provider or database forbidden in free surface checks')
    for name in ('node_chat','_chat_model','voyage_embed','voyage_rerank'):
        monkeypatch.setattr(llm,name,deny)
    monkeypatch.setattr('psycopg.connect',deny)
    monkeypatch.setattr('httpx.post',deny)
    def build(case_id,name,missing_current=False):
        data=plan.fixture(); job=next(j for j in plan.jobs(data) if j['case']==case_id and j['variant']=='normal')
        case=next(c for c in data['cases'] if c['id']==case_id)
        inputs=plan.materialize(data,case,'normal'); cards=baseline.synthetic_docs(data,inputs)
        doc=dict(file=data['common']['document'],parts=['DEMO1','DEMO2'],
                 cards=[dict(c,document=c['file']) for c in cards if c['row'] is not None],
                 texts=[c['content'] for c in cards if c['row'] is None],text_cards=[])
        scripted=baseline.fake_chat(data,job,inputs); prompts=[]
        def chat(node,system,user,schema,**kwargs):
            prompts.append((node,user))
            reply=scripted(node,system,user,schema)
            if node=='judge_read' and missing_current:
                reply.values=[v for v in reply.values if v.name!='i_max']
            return reply
        graph=pre.make_trial(pre.Observer(chat),retriever=lambda *a,**k:cards,
            load_cards=lambda keys:{'synthetic':doc},doc_meta=lambda keys:{'synthetic':{'category':'standard-rectifier'}},
            part_docs=lambda p:['synthetic'])['app']
        thread,run=str(uuid4()),str(uuid4())
        class Repo(FakeRepo):
            def get_thread(self,user,tid):
                return tid,1,parse_netlist(inputs['netlist']),name
        class History(baseline.MockHistory):
            record={}
            def execute(self,query,params=()):
                if query.startswith('UPDATE threads SET input_record='):
                    self.record=params[0].obj
                    return self
                if query.startswith('UPDATE threads SET version='):
                    self.record=params[1].obj
                return super().execute(query,params)
        history=History(); service=object.__new__(Conversations)
        service.graph,service.mode=graph,'live'; saved={}
        @contextmanager
        def locked(user,tid):
            yield history,dict(saved,version=history.version,input_record=history.record)
        def ensure(user,tid,filename,connections,target,**kwargs):
            saved.update(filename=filename,connections=connections,target=target)
        def detail(*args):
            state=graph.get_state(service.config(thread))
            pending=[i.value for task in state.tasks for i in task.interrupts]
            return dict(version=history.version,interrupt=pending[0] if pending else None)
        service.locked=locked; service.ensure_thread=ensure; service.detail=detail
        service._invoke=lambda conn,tid,payload,budget,request_id='':graph.invoke(payload,service.config(tid))
        service.admission=lambda user:None; service._budget=lambda user:None
        service._purge_expired=lambda:None; service._reconcile=lambda *a:None; service._profile_hints=lambda *a:[]
        return service,Repo(thread,run),prompts,history,inputs['question']
    return build


@pytest.mark.parametrize('name',['PROJECT_NAME_SURFACE','FILE_NAME_SURFACE.net'])
@pytest.mark.parametrize('case_id',['T1','T5'])
def test_free_http_names_stay_out_of_model_prompts_but_conditions_reach(web,native_input_path,name,case_id):
    analysis,repo,prompts,_,question=native_input_path(case_id,name)
    with web(analysis,repo) as client:
        response=client.post(f'/api/threads/{repo.thread}/runs',json={
            'question':question,'conditions':'CONDITION_SURFACE','target_ref':'D1'},headers=ORIGIN)
    assert response.status_code==200 and 'event: completed' in response.text
    assert analysis.graph.get_state(analysis.config(repo.thread)).values['circuit']==name
    assert {'supervisor','docs_answer' if case_id=='T1' else 'judge_read'}<={node for node,_ in prompts}
    assert all(name not in user for _,user in prompts)
    assert any('CONDITION_SURFACE' in user for _,user in prompts)


@pytest.mark.parametrize('case_id, stages', [('T1', ['입력 확인', '품번 확인', '질문 분석', '문서 검색', '답 작성']),
                                             ('T5', ['입력 확인', '품번 확인', '질문 분석', '회로 역할 읽기', '후보 판정', '답 작성'])])
def test_live_stages_come_from_the_real_graph_nodes(web, native_input_path, case_id, stages):
    """진짜 그래프의 노드 이름이 진행 단계 표와 맞는지 본다(노드 이름을 바꾸면 여기서 깨진다)."""
    from backend.conversations import memory_service
    from backend.services.langfuse_prompts import AnalysisTimings
    analysis, repo, _, _, question = native_input_path(case_id, 'synthetic.net')
    graph = analysis.graph
    # [왜] 고정 장치의 _invoke는 callback 없이 그래프만 돈다. 실제 _invoke처럼 노드 시간 callback에 진행 알림을 붙인다
    analysis._invoke = lambda conn, tid, payload, budget, request_id='': graph.invoke(
        payload, {**analysis.config(tid), 'callbacks': [AnalysisTimings(on_node=memory_service._progress.get())]})
    with web(analysis, repo) as client:
        frames = sse_frames(client.post(f'/api/threads/{repo.thread}/runs', json={'question': question, 'target_ref': 'D1'}, headers=ORIGIN).text)
    assert frames[-1][0] == 'completed' and all(name == 'status' for name, _ in frames[1:-1])
    assert [data['stage'] for name, data in frames if name == 'status'] == stages


def test_free_resume_text_reaches_later_question_history_not_immediate_read(web,native_input_path):
    analysis,repo,prompts,history,question=native_input_path('T5','synthetic.net',missing_current=True)
    question=question.replace('부하 최대 0.1 A, ','')
    marker='RESUME_HISTORY_SURFACE'
    with web(analysis,repo) as client:
        first=client.post(f'/api/threads/{repo.thread}/runs',json={'question':question,'target_ref':'D1'},headers=ORIGIN)
        assert 'event: requires_input' in first.text
        count=len([p for p in prompts if p[0]=='judge_read']); start=len(prompts)
        resumed=client.post(f'/api/runs/{repo.run}/resume',json={'answers':{'i_max':marker}},headers=ORIGIN)
        assert resumed.status_code==200 and 'event: failed' not in resumed.text
        assert len([p for p in prompts if p[0]=='judge_read'])==count
        assert all(marker not in user for _,user in prompts[start:])
        assert any(marker in h['content'] for h in history.history)
        state=analysis.graph.get_state(analysis.config(repo.thread)).values
        values=state['judgement']['analysis_inputs']['values_si']
        assert values['v_in_max']==60 and 'i_max' not in values
        start=len(prompts)
        later=client.post(f'/api/threads/{repo.thread}/runs',json={'question':'DEMO2의 정격을 다시 확인해 주세요.','target_ref':'D1'},headers=ORIGIN)
        assert later.status_code==200 and 'event: failed' not in later.text
        # 비관련 자기완결 질문에는 재개 답변 marker를 현재 모델 입력으로
        # 되먹이지 않는다. marker 자체는 사용자 원문 history에는 보존된다.
        assert all(marker not in user for _,user in prompts[start:])


def test_completed_frame_carries_profile_hints_but_run_record_does_not(web):
    """참고(내 설정)는 이번 결과 frame에만 붙고 run 기록에는 저장하지 않는다(지운 사실이 지난 run 조회에 남지 않게)."""
    thread, run = str(uuid4()), str(uuid4())
    analysis, repo = FakeAnalysis(), FakeRepo(thread, run)
    analysis.hints = [{'kind': 'mounting_preference', 'value': 'smd', 'text': '이 사용자는 SMD 실장을 선호한다.', 'version': 3}]
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'SMD로?', 'target_ref': 'D1'}, headers=ORIGIN)
        recovered = client.get(f'/api/runs/{run}').json()['result']
    completed = response.text.split('event: completed\ndata: ')[1]
    assert '"profile_hints": [{"kind": "mounting_preference", "value": "smd", "text": "이 사용자는 SMD 실장을 선호한다."}]' in completed
    assert '"version": 3' not in completed
    assert 'profile_hints' not in repo.result and recovered['profile_hints'] == []


def test_changed_target_is_409_before_a_run_is_created(web):
    thread = str(uuid4())
    analysis, repo = FakeAnalysis(), FakeRepo(thread, str(uuid4()))
    with web(analysis, repo) as client:
        first = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        second = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D2'}, headers=ORIGIN)
    assert first.status_code == 200 and second.status_code == 409
    assert second.json()['error'] == {'code': 'CONFLICT', 'message': '대상 부품을 바꾸려면 새 대화를 시작하세요.',
                                      'request_id': second.headers['X-Request-ID']}
    assert repo.calls.count('start') == 1


def test_missing_analysis_service_is_503_before_stream(web):
    thread = str(uuid4())
    repo = FakeRepo(thread, str(uuid4()))
    with web(None, repo) as client:
        start = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        resume = client.post(f'/api/runs/{uuid4()}/resume', json={'answers': {}}, headers=ORIGIN)
    for response in (start, resume):
        assert response.status_code == 503
        assert response.headers['content-type'].startswith('application/json')
        assert response.json()['error']['code'] == 'UNAVAILABLE'
    assert repo.calls == []


def test_failed_frame_carries_public_error_code_and_logs_unexpected_exception(web, caplog):
    thread = str(uuid4())
    analysis = FakeAnalysis(error=RuntimeError('private exception marker'))
    repo = FakeRepo(thread, str(uuid4()))
    with caplog.at_level('ERROR', logger='backend.errors'), web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert 'event: failed' in response.text and '"code": "INTERNAL_ERROR"' in response.text
    # [왜] 시스템 오류를 '거절'(답할 수 없는 질문)과 같은 단계 이름으로 보이지 않는다
    failed = json.loads(response.text.split('event: failed\ndata: ', 1)[1].split('\n', 1)[0])
    assert failed['status'] == 'failed' and failed['stage'] == '오류'
    assert 'private exception marker' not in response.text
    request_id = response.text.split('"request_id": "', 1)[1].split('"', 1)[0]
    logged = [r for r in caplog.records if getattr(r, 'request_id', None) == request_id]
    assert logged and logged[0].exc_info and 'private exception marker' in str(logged[0].exc_info[1])
    assert (logged[0].code, logged[0].status, logged[0].levelname) == ('INTERNAL_ERROR', 500, 'ERROR')
    assert repo.calls == ['start', ('commit', 'failed')]


def test_budget_refusal_maps_to_common_code_without_traceback(web, caplog):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis(error=ApiError(429, '하루 분석 예약 예산에 도달했습니다.', code='LIMIT_EXCEEDED'))
    repo = FakeRepo(thread, run)
    with caplog.at_level('INFO', logger='backend.errors'), web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert '"error": {"code": "LIMIT_EXCEEDED", "message": "하루 분석 예약 예산에 도달했습니다."}' in response.text
    assert repo.result['error']['code'] == 'LIMIT_EXCEEDED'
    with web(analysis, repo) as client:
        assert client.get(f'/api/runs/{run}').json()['result']['error'] == repo.result['error']
    # [왜] 4xx는 traceback 없는 INFO 한 줄(code · status)만 남긴다
    assert [(r.levelname, r.code, r.status, r.exc_info) for r in caplog.records] == [('INFO', 'LIMIT_EXCEEDED', 429, None)]


def test_token_cap_refuses_run_and_resume_before_stream_or_run_change(web):
    """하루 토큰 상한(admission 429)은 스트림 · run 행 · 재개 전이 전에 공통 오류로 끝나고 분석을 부르지 않는다."""
    thread, run = str(uuid4()), str(uuid4())
    from backend.conversations.memory_service import USER_DAILY_TOKENS
    analysis = FakeAnalysis(refuse=ApiError(429, f'오늘 쓸 수 있는 분석 사용량(하루 {USER_DAILY_TOKENS:,} 토큰)을 다 썼습니다.', code='LIMIT_EXCEEDED'))
    repo = FakeRepo(thread, run, status='requires_input', result={'interrupt': {'missing': ['VIN_MAX'], 'role_choices': [], 'question': '?'}})
    with web(analysis, repo) as client:
        start = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        resume = client.post(f'/api/runs/{run}/resume', json={'answers': {'VIN_MAX': '12'}}, headers=ORIGIN)
        restored = client.get(f'/api/runs/{run}').json()['result']
    for response in (start, resume):
        assert response.status_code == 429 and response.headers['content-type'].startswith('application/json')
        assert response.json()['error']['code'] == 'LIMIT_EXCEEDED' and f'{USER_DAILY_TOKENS:,} 토큰' in response.json()['error']['message']
    assert analysis.calls == [] and repo.calls == []
    assert restored['status'] == 'requires_input' and restored['interrupt']['missing'] == ['VIN_MAX']
    assert restored['error']['code'] == 'LIMIT_EXCEEDED'


def test_project_delete_rejects_active_run_before_checkpoint_deletion(monkeypatch):
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import InvalidRunState
    import pytest
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params):
            class Result:
                def fetchone(self): return (1,)
            return Result()
    monkeypatch.setattr(auth, 'connection', lambda: Conn())
    def service():
        pytest.fail('active runs must prevent checkpoint deletion')
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(1, 1, service)


@pytest.mark.parametrize(('age_seconds', 'lock_held', 'blocks'), [
    (3600, False, False),  # 인스턴스가 내려가 멈춘 run: 지울 수 있다(점검 B #3)
    (10, False, True),     # 방금 갱신된 run: 아직 도는 중일 수 있다
    (3600, True, True),    # 오래됐어도 분석 잠금을 쥔 thread: 살아 있다
])
def test_project_delete_ignores_only_stale_unlocked_running_runs(monkeypatch, age_seconds, lock_held, blocks):
    """실제 DB 판정은 tests/conversations/test_repository.py(격리 PostgreSQL)가 본다. 여기서는 삭제 SQL이 나이와 잠금을 묻고 stale 한도를 넘기는지만 본다."""
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import InvalidRunState, stale_run_seconds
    statements, deleted = [], []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params=()):
            statements.append(query)
            class Result:
                def fetchone(self_):
                    if 'FROM projects' in query:
                        return (1,)
                    if 'FROM runs' not in query:
                        return None
                    # 멈춘 run 하나가 있는 DB를 흉내 낸다: 쿼리가 나이 · 잠금을 묻지 않으면 늘 막는다(옛 쿼리)
                    if 'updated_at' not in query or 'pg_try_advisory_xact_lock' not in query:
                        return (1,)
                    assert params[-1] == stale_run_seconds() == 300
                    return (1,) if age_seconds < params[-1] or lock_held else None
                def fetchall(self_): return [('t1',)]
            return Result()
    monkeypatch.setattr(auth, 'connection', lambda: Conn())
    if blocks:
        with pytest.raises(InvalidRunState):
            delete_owned_with_checkpoints(1, 1, lambda conn, ids: deleted.extend(ids))
        assert deleted == [] and not any('DELETE FROM projects' in q for q in statements)
    else:
        delete_owned_with_checkpoints(1, 1, lambda conn, ids: deleted.extend(ids))
        assert deleted == ['t1'] and any('DELETE FROM projects' in q for q in statements)


def test_foreign_and_active_runs_return_safe_errors(web, monkeypatch):
    import psycopg
    from backend.conversations.repository import ConversationNotFound, InvalidRunState
    thread = str(uuid4())
    for failing, exc, expected in [('get_thread', ConversationNotFound(), 404), ('start', InvalidRunState(), 409),
                                   ('get_thread', psycopg.OperationalError('private-db-detail'), 503)]:
        repo = FakeRepo(thread, str(uuid4()))
        setattr(repo, failing, lambda *args, exc=exc: (_ for _ in ()).throw(exc))
        # 저장소 의존성의 예외 → 공통 404·409 변환까지 보려고 의존성은 바꾸지 않고 클래스만 바꾼다
        monkeypatch.setattr('backend.api.conversations.ConversationRepository', lambda repo=repo: repo)
        with web(FakeAnalysis(), None) as client:
            response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
        assert response.status_code == expected
        assert response.json()['error']['request_id'] == response.headers['X-Request-ID']
        assert response.headers['cache-control'] == 'no-store' and 'private-db-detail' not in response.text


def test_project_delete_with_threads_deletes_analysis_records_before_project(monkeypatch):
    """프로젝트 삭제는 같은 UUID의 분석 checkpoint · thread를 사용자 조건으로 같은 트랜잭션에서 지우고 프로젝트 행을 마지막에 지운다."""
    thread, executed = str(uuid4()), []
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self, row_factory=None): return self
        def execute(self, query, params=()):
            text = query if isinstance(query, str) else query.as_string(None)
            executed.append((text, params))
            rows = {'SELECT id FROM projects': [(1,)], 'SELECT 1 FROM runs': [], 'SELECT id FROM threads': [(thread,)], 'SELECT to_regclass': [(True, True)]}
            found = next((v for k, v in rows.items() if text.startswith(k)), [])
            return SimpleNamespace(fetchone=lambda: found[0] if found else None, fetchall=lambda: found, rowcount=1)
    monkeypatch.setattr(auth, 'connection', lambda: Conn())
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.delete('/api/projects/1', headers=ORIGIN)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 204
    deletes = [(text, params) for text, params in executed if text.startswith('DELETE')]
    assert [text.split()[2] for text, _ in deletes] == ['sojafit_agent."checkpoint_writes"', 'sojafit_agent."checkpoint_blobs"', 'sojafit_agent."checkpoints"',
                                                       'sojafit_agent.threads', 'projects']
    assert all(params[:2] == (1, [thread]) for _, params in deletes[:-1])  # 사용자 조건과 그 프로젝트의 대화 UUID만


def test_disconnected_stream_keeps_running_and_saves_terminal():
    import asyncio
    import time
    from backend.api.conversations import stream
    class Repo:
        def finish(self, *args): self.result = args
    repo = Repo()
    analysis = FakeAnalysis()
    def slow(progress):
        time.sleep(0.05)
        return {'interrupt': None}
    async def run():
        response = stream(repo, 1, 'thread', 'run', 'req', analysis, slow)
        iterator = response.body_iterator
        assert 'event: run_started' in await anext(iterator)
        await iterator.aclose()
        for _ in range(100):
            if hasattr(repo, 'result'): break
            await asyncio.sleep(0.01)
        assert repo.result[3] == 'completed'
        assert repo.result[4]['answer'] == 'ok'
    asyncio.run(run())


def test_resume_rejects_price_fields_and_long_answers_before_service(web):
    analysis = FakeAnalysis()
    with web(analysis, FakeRepo(str(uuid4()), str(uuid4()))) as client:
        for answers in [{'price': 'private'}, {'stock': 'private'}, {'product_url': 'private'}, {'fetched_at': 'private'},
                        {'VIN_MAX': 'x' * 201}]:  # 답 하나는 200자까지
            response = client.post(f'/api/runs/{uuid4()}/resume', json={'answers': answers}, headers=ORIGIN)
            assert response.status_code == 422
    assert analysis.calls == []


def test_run_rejects_injected_fields_and_foreign_origin_before_service(web):
    """본문에 사용자 id · 경로 같은 칸을 끼우면 422, 다른 Origin이면 403이고 분석 · 저장소를 부르지 않는다."""
    thread = str(uuid4())
    analysis, repo = FakeAnalysis(), FakeRepo(thread, str(uuid4()))
    with web(analysis, repo) as client:
        injected = client.post(f'/api/threads/{thread}/runs', headers=ORIGIN,
                               json={'question': 'hi', 'target_ref': 'D1', 'user_id': 2, 'netlist_path': '.env'})
        foreign = client.post(f'/api/threads/{thread}/runs', headers={'origin': 'https://evil.example'},
                              json={'question': 'hi', 'target_ref': 'D1'})
    assert injected.status_code == 422 and foreign.status_code == 403
    assert injected.headers['cache-control'] == 'no-store'
    assert analysis.calls == [] and repo.calls == []


def test_run_body_over_128_kib_is_413_before_login():
    """`/api/threads`로 시작하는 POST 본문은 128 KiB까지다(`backend/main.py`의 `conversation_boundary`)."""
    response = TestClient(app).post(f'/api/threads/{uuid4()}/runs', content=b'x' * (128 * 1024 + 1))
    assert response.status_code == 413 and response.headers['cache-control'] == 'no-store'
    assert response.json()['error']['code'] == 'PAYLOAD_TOO_LARGE'


def test_resume_uses_same_thread_and_current_analysis_version(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis()
    analysis.version = 3
    repo = FakeRepo(thread, run, status='requires_input')
    with web(analysis, repo) as client:
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {'v_in': '5 V'}}, headers=ORIGIN)
    assert response.status_code == 200 and 'event: completed' in response.text
    assert analysis.calls == [('resume', thread, {'v_in': '5 V'}, '', 3)]
    assert repo.calls == [('claim', thread, run), ('commit', 'completed')]


def test_resume_passes_an_owned_interrupt_role_choice(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis()
    repo = FakeRepo(thread, run, status='requires_input', result={'interrupt': {'role_choices': ['R01', 'R02']}})
    with web(analysis, repo) as client:
        missing = client.post(f'/api/runs/{run}/resume', json={'answers': {}}, headers=ORIGIN)
        assert missing.status_code == 422
        response = client.post(f'/api/runs/{run}/resume', json={'answers': {}, 'role': 'R02'}, headers=ORIGIN)
        assert response.status_code == 200
    assert analysis.calls == [('resume', thread, {}, 'R02', 1)]


def test_interrupt_is_saved_as_requires_input(web):
    thread, run = str(uuid4()), str(uuid4())
    analysis = FakeAnalysis(interrupt={'question': '최대 입력 전압?', 'missing': ['VIN_MAX'], 'role_choices': []})
    repo = FakeRepo(thread, run)
    with web(analysis, repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hi', 'target_ref': 'D1'}, headers=ORIGIN)
    assert 'event: requires_input' in response.text
    assert repo.status == 'requires_input' and repo.result['interrupt']['missing'] == ['VIN_MAX']


def test_terminal_commit_retries_a_transient_database_failure(web):
    import psycopg
    thread = str(uuid4())
    attempts = []
    repo = FakeRepo(thread, str(uuid4()))
    def finish(user, thread_id, run_id, status, result):
        attempts.append(status)
        if len(attempts) == 1:
            raise psycopg.OperationalError('temporary test outage')
    repo.finish = finish
    with web(FakeAnalysis(), repo) as client:
        response = client.post(f'/api/threads/{thread}/runs', json={'question': 'hello', 'target_ref': 'D1'}, headers=ORIGIN)
    assert response.status_code == 200
    assert 'event: completed' in response.text
    assert attempts == ['completed', 'completed']


def test_demo_questions_only_in_replay_mode_and_without_recorded_results(web, monkeypatch):
    from backend.services import demo
    recorded = {'id': 'v3-01', 'kind': '판정 + 조건 인터럽트', 'circuit': 'ATtiny85 Time Switch', 'demo_id': 'attiny85_time_switch',
                'target': 'D1', 'question': '질문', 'conditions': '조건', 'resume': {'answers': {}, 'role': 'R01'},
                'netlist': 'data/circuits/x.net', 'answer': '기록한 답', 'verdicts': [['1N4007G', 'ROLE_SUFFICIENT']], 'path': ['입력 읽기']}
    monkeypatch.setattr(demo, 'questions', lambda: [recorded])
    analysis = FakeAnalysis()
    analysis.mode = 'live'
    with web(analysis, None) as client:
        assert client.get('/api/demo-questions').status_code == 404  # 재생 모드가 아니면 화면이 버튼을 숨긴다
        analysis.mode = 'demo'
        listed = client.get('/api/demo-questions').json()
        def missing():
            raise HTTPException(503, demo.MISSING)
        monkeypatch.setattr(demo, 'questions', missing)
        unavailable = client.get('/api/demo-questions')
    assert listed == [{k: recorded[k] for k in ('id', 'kind', 'circuit', 'demo_id', 'target', 'question', 'conditions', 'resume')}]
    assert unavailable.status_code == 503 and unavailable.json()['error']['code'] == 'UNAVAILABLE'


@pytest.mark.parametrize('path', ['/api/runs/{id}/resume', '/api/messages/1/approvals', '/api/auth/login'])
def test_other_api_json_bodies_over_128_kib_are_413(path):
    """재개 · 승인 · 로그인 등 `/api/` 아래 본문도 128 KiB까지다. 넷리스트 업로드(5 MiB)만 이 한도 밖이다."""
    response = TestClient(app).post(path.format(id=uuid4()), content=b'x' * (128 * 1024 + 1))
    assert response.status_code == 413 and response.json()['error']['code'] == 'PAYLOAD_TOO_LARGE'
    upload = TestClient(app).post('/api/projects/upload', content=b'x' * (128 * 1024 + 1))
    assert upload.status_code != 413


def test_every_response_has_security_headers():
    """보안 응답 헤더는 가장 바깥 미들웨어가 모든 응답(오류 포함)에 붙인다(`backend/main.py`의 `SECURITY_HEADERS`)."""
    for path in ('/health', '/api/auth/me'):
        headers = TestClient(app).get(path).headers
        assert headers['x-content-type-options'] == 'nosniff' and headers['x-frame-options'] == 'DENY'
        assert headers['referrer-policy'] == 'strict-origin-when-cross-origin' and 'max-age' in headers['strict-transport-security']

