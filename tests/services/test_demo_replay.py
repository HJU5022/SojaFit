"""데모 응답 기록(recorder) · 재생(replayer, backend/services/demo.py)과 기록 스크립트(scripts/demo/record_demo.py)의 오프라인 시험.

- 역할: 가짜 LLM으로 멀티 그래프를 기록한 뒤 재생하면 같은 답 · 경로가 나오는지, 기록에 없는 호출은 거절 답이 아니라
  노드 이름을 담은 오류로 멈추는지, 기록 줄에 호출 칸 밖의 값(키 등)이 없는지, 스크립트가 DEMO_MODE=1 · 키 없이는 돌지 않는지,
  데모 질문의 v3 문항이 동결 평가셋 입력 그대로인지와 회로 · 대상이 저장소에 있는지 본다.
  서비스 쪽(DEMO_REPLAY=1): 서비스 조립(`Conversations._graph`)으로 판정 · 조건 인터럽트 · 기록한 답 재개를 기록한 뒤 재생하면
  같은 경로 · 판정이 나오는지, 기록이 없으면 503인지, 같은 회로 · 대상 · 질문 · 조건만 기록 질문으로 받는지,
  데모 질문마다 같은 회로의 React 데모 프로젝트(c01 포함)가 있는지 본다.
- 하지 않는 일: 실제 LLM · DB · MCP 호출. 실제 기록 실행과 재생 확인은 스크립트를 키 없는 compose에서 손으로 돌린다.
  서비스의 DB 쪽 확인 자리(ensure_thread · message · resume)는 tests/api/test_threads.py(격리 DB가 있을 때만)가 본다.
- 출처: backend/services/demo.py, backend/conversations/memory_service.py, scripts/demo/record_demo.py, data/demo/DEMO.md
"""
import importlib.util
import json
from pathlib import Path

import pytest

from backend.multi_agent import build as B
from backend.multi_agent.agents.docs import DocsAnswer
from backend.multi_agent.contracts import Plan, Task
from backend.services import demo

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('record_demo', ROOT / 'scripts/demo/record_demo.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

PART = {'ref': 'D1', 'value': '1N4148', 'footprint': 'DO-35', 'nets': []}


def scripted():
    """Supervisor 계획 1번 + 문서 답 1번을 내는 가짜 LLM. 부른 노드를 남긴다."""
    answers = {'supervisor': Plan(question_type='rating', next='tasks',
                                  tasks=[Task(id=1, agent='docs', kind='rating', goal='rating', query='1N4148 VRRM')]),
               'docs_answer': DocsAnswer(grade='enough', answer='1N4148의 VRRM은 75 V이다 [7].')}
    calls = []

    def chat(node, system, user, schema):
        calls.append(node)
        return answers[node]
    chat.calls = calls
    return chat


def app(chat):
    doc = {'chunk_id': 7, 'file': 'a.pdf', 'page': 1, 'content': 'VRRM 75 V', 'table': None, 'doc_parts': []}
    return B.build_graph(chat=chat, retriever=lambda q, parts=None: [doc],
                         parse=lambda s: {'question': s['input'], 'target': 'D1', 'conditions': '', 'target_part': PART})


def test_record_then_replay_gives_the_same_graph_result(tmp_path):
    path = tmp_path / 'calls.jsonl'
    llm = scripted()
    recorded = app(demo.recorder(llm, path)).invoke({'input': '1N4148 VRRM?'})
    replayed = app(demo.replayer(path)).invoke({'input': '1N4148 VRRM?'})
    assert llm.calls == ['supervisor', 'docs_answer']  # 실제(가짜) LLM은 기록할 때만 불렸다
    assert [json.loads(line)['node'] for line in path.read_text(encoding='utf-8').splitlines()] == ['supervisor', 'docs_answer']
    for key in ('answer', 'path', 'question_type', 'passed', 'check'):
        assert replayed[key] == recorded[key]
    assert replayed['answer'].endswith('[7].')


def test_miss_fails_closed_with_the_node_name_instead_of_a_refusal(tmp_path):
    path = tmp_path / 'calls.jsonl'
    path.write_text('', encoding='utf-8')
    # [왜] Supervisor는 형식 실패(ValueError)를 거절 답으로 바꾼다. 기록에 없는 질문이 그 길로 새면 지어낸 거절이 나간다
    with pytest.raises(demo.ReplayMiss, match='supervisor'):
        app(demo.replayer(path)).invoke({'input': '기록에 없는 질문'})
    assert not issubclass(demo.ReplayMiss, ValueError)


def test_same_prompt_with_a_different_word_is_a_miss(tmp_path):
    path = tmp_path / 'calls.jsonl'
    app(demo.recorder(scripted(), path)).invoke({'input': '1N4148 VRRM?'})
    with pytest.raises(demo.ReplayMiss):
        app(demo.replayer(path)).invoke({'input': '1N4148 VRRM은?'})


def test_recorder_writes_only_the_call_fields_and_calls_once_per_key(tmp_path, monkeypatch):
    secret = 'sk-or-v1-' + 'f' * 48
    monkeypatch.setenv('OPENROUTER_API_KEY', secret)
    path, calls = tmp_path / 'calls.jsonl', []

    def chat(node, system, user, schema):
        calls.append(node)
        return DocsAnswer(grade='enough', answer='답 [1].')
    record = demo.recorder(chat, path)
    first = record('docs_answer', 'system', 'user', DocsAnswer)
    again = record('docs_answer', 'system', 'user', DocsAnswer)
    text = path.read_text(encoding='utf-8')
    assert calls == ['docs_answer'] and first == again  # 같은 키는 LLM을 다시 부르지 않고 같은 응답
    lines = [json.loads(line) for line in text.splitlines()]
    assert len(lines) == 1 and set(lines[0]) == {'sha256', 'node', 'schema', 'response'}
    assert lines[0]['sha256'] == demo.call_key('docs_answer', 'system', 'user', DocsAnswer)
    assert secret not in text and 'OPENROUTER' not in text and 'api_key' not in text.lower()


def test_recorder_stops_on_a_format_failure_instead_of_recording_a_refusal(tmp_path):
    def broken(node, system, user, schema):
        raise ValueError('형식 실패')
    with pytest.raises(RuntimeError, match='supervisor') as raised:
        demo.recorder(broken, tmp_path / 'calls.jsonl')('supervisor', 's', 'u', Plan)
    assert not isinstance(raised.value, ValueError)


def test_key_separates_fields():
    assert demo.call_key('a', 'bc', 'd', Plan) != demo.call_key('a', 'b', 'cd', Plan)
    assert demo.call_key('a', 'b', 'c', Plan) != demo.call_key('a', 'b', 'c', DocsAnswer)


def test_script_refuses_without_demo_mode_or_key():
    assert any('DEMO_MODE' in p for p in S.env_problems('record', {'OPENROUTER_API_KEY': 'x'}))
    assert any('DEMO_MODE' in p for p in S.env_problems('replay', {'DEMO_MODE': '0'}))
    assert any('OPENROUTER_API_KEY' in p for p in S.env_problems('record', {'DEMO_MODE': '1'}))
    assert any('LAB_' in p for p in S.env_problems('replay', {'DEMO_MODE': '1', 'LAB_THINKING': '1'}))
    assert any('LLM_MODEL' in p for p in S.env_problems('record', {'DEMO_MODE': '1', 'OPENROUTER_API_KEY': 'x', 'LLM_MODEL': 'm'}))
    assert S.env_problems('record', {'DEMO_MODE': '1', 'OPENROUTER_API_KEY': 'x'}) == []
    assert S.env_problems('replay', {'DEMO_MODE': '1'}) == []  # 재생은 키가 없어도 돈다


def test_main_stops_before_db_and_llm(tmp_path, monkeypatch, capsys):
    import psycopg

    def no_db(*a, **k):
        raise AssertionError('DB에 붙으면 안 된다')
    monkeypatch.setattr(psycopg, 'connect', no_db)
    monkeypatch.setattr(S, 'CALLS', tmp_path / 'calls.jsonl')
    for key in [k for k in __import__('os').environ if k.startswith('LAB_')]:
        monkeypatch.delenv(key)
    monkeypatch.setenv('DEMO_MODE', '0')
    assert S.main('record', True) == 1  # DEMO_MODE=1이 아니면 확인 플래그가 있어도 멈춘다
    monkeypatch.setenv('DEMO_MODE', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    monkeypatch.delenv('LLM_MODEL', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'openrouter')
    assert S.main('record', False) == 0  # --confirm-live 없으면 예상 호출 수만 찍고 멈춘다
    assert '예상 LLM 호출' in capsys.readouterr().out and not (tmp_path / 'calls.jsonl').exists()


def test_v3_questions_are_the_frozen_inputs_and_demo_variants_are_not_in_the_dataset():
    from backend.graph.nodes import parse_input
    items = {json.loads(line)['id']: json.loads(line) for line in open(ROOT / 'evals/dataset_v3.jsonl', encoding='utf-8')}
    for q in S.QUESTIONS:
        if q['id'].startswith('v3-'):
            f = parse_input(items[q['id']]['input'])
            assert (q['circuit'], q['netlist'], q['target'], q['conditions'], q['question']) == \
                   (f['circuit'], f['netlist_path'], f['target'], f.get('conditions', ''), f['question'])
        else:
            assert q['id'].startswith('demo-') and q['id'] not in items


def test_question_circuits_and_targets_exist_offline():
    from backend.graph.nodes import circuit_around
    assert len(S.QUESTIONS) == len({q['id'] for q in S.QUESTIONS}) and any(q['interrupt'] for q in S.QUESTIONS)
    for q in S.QUESTIONS:
        inputs = S.service_inputs(q)
        assert circuit_around(inputs['connections'], q['target'])['ref'] == q['target']
        assert inputs['input'].endswith(q['question']) and inputs['approved_memories'] == []


def test_run_question_resumes_once_like_the_service_api():
    from types import SimpleNamespace
    sent = []

    class FakeApp:
        def invoke(self, value, config):
            sent.append(value)
            if len(sent) == 1:
                return {'__interrupt__': [SimpleNamespace(value={'missing': ['v_drop_allowed'], 'role_choices': ['R01', 'R02'], 'question': '?'})]}
            return {'path': ['입력 읽기', '판정', '끝'], 'answer': '답', 'judgement': {'kind': 'judge', 'results': [{'part': '1N4007G', 'verdict': 'ROLE_SUFFICIENT'}]}}
    q = {**S.QUESTIONS[0], 'answers': {'v_drop_allowed': '1V', 'not_asked': '5V'}}
    out = S.run_question(FakeApp(), q)
    # 물은 이름만 보내고, 역할 후보가 있으면 API처럼 하나를 꼭 고른다
    assert sent[1].resume == {'answers': {'v_drop_allowed': '1V'}, 'role': 'R01'} and out['resume'] == sent[1].resume
    assert out['verdicts'] == [['1N4007G', 'ROLE_SUFFICIENT']] and sent[0]['input'].startswith('사용 조건: ')
    with pytest.raises(SystemExit, match='멈추지 않았습니다'):
        S.run_question(SimpleNamespace(invoke=lambda v, c: {'path': []}), S.QUESTIONS[0])  # 인터럽트를 보일 질문이 안 멈추면 기록하지 않는다


def test_differences_names_question_and_field():
    rec = [{'id': 'a', **{k: 1 for k in S.COMPARED}}, {'id': 'b', **{k: 1 for k in S.COMPARED}}]
    assert S.differences(rec, [{'id': 'a', **{k: 1 for k in S.COMPARED}, 'answer': 2}]) == ['a: answer', 'b: 재생 안 됨']


def fake_recording(monkeypatch, tmp_path, questions, calls=''):
    """가짜 기록 파일 두 개(calls.jsonl · outcomes.json)를 만들고 demo가 읽게 한다."""
    (tmp_path / 'calls.jsonl').write_text(calls, encoding='utf-8')
    (tmp_path / 'outcomes.json').write_text(json.dumps({'questions': questions}, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(demo, 'RECORDING', tmp_path / 'calls.jsonl')
    monkeypatch.setattr(demo, 'OUTCOMES', tmp_path / 'outcomes.json')


def test_missing_recording_is_503_and_the_server_still_builds_its_chat(tmp_path, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(demo, 'RECORDING', tmp_path / 'calls.jsonl')
    monkeypatch.setattr(demo, 'OUTCOMES', tmp_path / 'outcomes.json')
    chat = demo.service_chat()  # [왜] 기록이 없어도 서버(내 설정 · 탈퇴 등)는 떠야 한다. 분석만 503
    for call in (lambda: chat('supervisor', 's', 'u', Plan), demo.questions, lambda: demo.match({}, 'D1')):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 503 and 'recordings' in error.value.detail


def test_recorded_questions_match_only_the_same_circuit_target_question_and_conditions(tmp_path, monkeypatch):
    q = {k: S.QUESTIONS[0][k] for k in ('id', 'kind', 'circuit', 'netlist', 'target', 'conditions', 'question')}
    fake_recording(monkeypatch, tmp_path, [{**q, 'resume': {'answers': {}, 'role': 'R01'}}])
    circuit = demo.connections(q['netlist'])
    assert [x['id'] for x in demo.match(circuit, 'D1')] == ['v3-01']
    assert demo.match(circuit, 'D1', q['question'], q['conditions'])[0]['resume'] == {'answers': {}, 'role': 'R01'}
    assert demo.match(circuit, 'D1', q['question'] + ' ', q['conditions']) == []  # 글자 하나라도 다르면 받지 않는다
    assert demo.match(circuit, 'D1', q['question'], '') == [] and demo.match(circuit, 'D2') == []
    assert demo.match(demo.connections(S.FRANZ), 'D1') == []
    error = demo.refusal('다른 질문입니다.')
    assert error.status_code == 422 and f"[v3-01] ATtiny85 Time Switch · D1: {q['question']}" in error.detail


def test_ensure_thread_refuses_other_targets_and_questions_before_the_stream_opens(tmp_path, monkeypatch):
    """[왜] pinned 회로를 읽은 뒤 run 스트림 전에 거르면 공통 오류를 바로 보이고 상태를 쓰지 않는다."""
    from fastapi import HTTPException
    from backend.conversations.memory_service import Conversations
    q = {k: S.QUESTIONS[0][k] for k in ('id', 'kind', 'circuit', 'netlist', 'target', 'conditions', 'question')}
    fake_recording(monkeypatch, tmp_path, [{**q, 'resume': None}])
    pinned = demo.connections(q['netlist'])

    class Conn:
        def __init__(self):
            self.queries = []
            self._result = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params=()):
            self.queries.append(query)
            if 'pg_try_advisory_lock_shared' in query:
                self._result = {'ok': True}
            elif 'project_circuit_versions' in query:
                self._result = {'connections': pinned}
            else:
                self._result = None
            return self

        def fetchone(self):
            return self._result

    conn = Conn()
    app = Conversations.__new__(Conversations)
    app.mode, caller_circuit = 'demo', {'components': [{'ref': 'D2'}], 'nets': []}
    monkeypatch.setattr(app, 'connection', lambda: conn)
    for target, question in (('D2', None), ('D1', '다른 질문'), ('D1', q['question'] + ' ')):
        with pytest.raises(HTTPException) as error:
            app.ensure_thread(1, 'thread', '이름', caller_circuit, target, question=question, conditions=q['conditions'])
        assert error.value.status_code == 422 and '[v3-01]' in error.value.detail
    assert not any(any(word in query.upper() for word in ('INSERT', 'UPDATE', 'DELETE')) for query in conn.queries)


def test_ensure_thread_refuses_missing_or_foreign_pinned_thread(tmp_path, monkeypatch):
    """[왜] pinned 버전이 없거나 다른 사용자의 대화면 입력 회로와 무관하게 404다."""
    from fastapi import HTTPException
    from backend.conversations.memory_service import Conversations
    q = {k: S.QUESTIONS[0][k] for k in ('netlist', 'target', 'conditions')}
    fake_recording(monkeypatch, tmp_path, [])

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params=()):
            self.query = query
            return self

        def fetchone(self):
            return {'ok': True} if 'pg_try_advisory_lock_shared' in self.query else None

    app = Conversations.__new__(Conversations)
    app.mode = 'demo'
    monkeypatch.setattr(app, 'connection', lambda: Conn())
    with pytest.raises(HTTPException) as error:
        app.ensure_thread(999, 'foreign-or-missing', '이름', demo.connections(q['netlist']), q['target'], conditions=q['conditions'])
    assert error.value.status_code == 404


def test_every_demo_question_has_a_react_demo_project_with_the_same_circuit(tmp_path, monkeypatch):
    """[왜] 화면은 데모 프로젝트(create_demo가 읽은 파일)로 run한다. 기록 질문의 회로와 같아야 서비스 확인을 통과하고 재생된다(c01은 11-10 추가)."""
    from backend.projects.repository import demo_path
    fake_recording(monkeypatch, tmp_path, [{**q, 'resume': None} for q in S.QUESTIONS])
    found = {q['id']: q['demo_id'] for q in demo.questions()}
    assert found == {'v3-01': 'attiny85_time_switch', 'demo-find': 'franzininho_diy', 'demo-rating': 'franzininho_diy',
                     'v3-36': 'franzininho_diy', 'v3-30': 'franzininho_diy',
                     'v3-03': 'attiny2313a_thermostat', 'demo-leak': 'mosfet_driver', 'demo-notsuff': 'breadboard_supply',
                     'demo-ask': 'attiny85_time_switch', 'demo-edition': 'pro_micro'}
    for q in S.QUESTIONS:
        data = json.loads(demo_path(found[q['id']]).read_text(encoding='utf-8'))
        project = {'components': data.get('components', data.get('parts', [])), 'nets': data.get('nets', [])}  # ensure_thread와 같은 모양
        assert demo.match(project, q['target'], q['question'], q['conditions'])


ROWS = [{'part': '1N5817', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 20.0, 'text': None, 'unit': 'V',
         'source_value_text': '20', 'test_condition': None,
         'citation': {'document': 'a.pdf', 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', 'row': 'VRRM', 'chunk_index': 1}}]


def service_graph(monkeypatch, chat):
    """서비스 조립(`Conversations._graph`, 데모 모드)으로 만든 그래프. MCP · 카드 도구 · 검색은 가짜, 체크포인터는 메모리 안."""
    from contextlib import ExitStack
    from langgraph.checkpoint.memory import InMemorySaver
    from backend.conversations.memory_service import Conversations
    from backend.graph import mcp_retriever
    from backend.rag import card_find, card_specs, retrieve

    class Mcp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def check(self, parts, revisions): return {'parts': {p: True for p in parts}, 'revisions': {r: True for r in revisions}}
    def specs(part, codes=None): return ROWS
    specs.prefetch, specs.doc_rows = (lambda parts, codes=None: None), (lambda part, codes=None: [])
    def find(*a, **k): return []
    find.also_read = lambda codes: None
    monkeypatch.setattr(mcp_retriever, 'StdioMcpRetriever', Mcp)
    monkeypatch.setattr(card_specs, 'default_specs', lambda chat=None: specs)
    monkeypatch.setattr(card_find, 'default_find', lambda chat=None: find)
    monkeypatch.setattr(retrieve, 'retrieve', lambda *a, **k: [])
    monkeypatch.setattr(demo, 'service_chat', lambda: chat)
    app = Conversations.__new__(Conversations)  # [왜] DB 없이 서비스의 그래프 조립만 쓴다
    app.mode, app.stack, app.saver, app.store = 'demo', ExitStack(), InMemorySaver(), None
    return app._graph()


def test_service_replays_a_recorded_judgement_with_interrupt_and_recorded_resume(tmp_path, monkeypatch):
    from backend.multi_agent.agents import judge as J
    real_service_chat = demo.service_chat
    read = J.JudgeRead(role='R01', candidates=['1N5817'], values=[J.Value(name='v_in_max', number=20, unit='V', quote='20V')])
    plan = Plan(question_type='candidate_judge', next='tasks', tasks=[Task(id=1, agent='judge', kind='candidate_judge', goal='judge 1N5817')])
    calls = []

    def llm(node, system, user, schema):
        calls.append(node)
        return {'supervisor': plan, 'judge_read': read}[node]
    q = {'id': 'demo-x', 'kind': '시험', 'circuit': '시험 회로', 'netlist': S.BREAD, 'target': 'D1', 'conditions': '입력 최대 20V',
         'question': 'D1을 TSC 1N5817로 바꿔도 돼?', 'answers': {}, 'interrupt': True}
    fake_recording(monkeypatch, tmp_path, [])
    recorded = S.run_question(service_graph(monkeypatch, demo.recorder(llm, demo.RECORDING)), q)
    assert recorded['interrupt']['missing'] and recorded['verdicts'] and calls == ['supervisor', 'judge_read']
    fake_recording(monkeypatch, tmp_path, [recorded], demo.RECORDING.read_text(encoding='utf-8'))
    replayed = S.run_question(service_graph(monkeypatch, real_service_chat()), q)  # 키 · LLM 없이 기록만 재생
    assert S.differences([recorded], [replayed]) == [] and len(calls) == 2
    # 서비스 재개 확인(resume)이 요구하는 값 = 기록한 재개 값
    assert demo.match(demo.connections(S.BREAD), 'D1', q['question'], q['conditions'])[0]['resume'] == recorded['resume']
    with pytest.raises(demo.ReplayMiss):
        service_graph(monkeypatch, real_service_chat()).invoke(S.service_inputs({**q, 'question': '다른 질문'}),
                                                              {'configurable': {'thread_id': 'other'}})
    # [왜] 서비스 message()는 기록과 세 칸이 다르다: 사용자가 붙인 프로젝트 이름 · 숫자 사용자 id · DB(jsonb)를 거친 연결 정보.
    #      셋 다 프롬프트 글자를 바꾸지 않아야 화면에서도 재생된다
    from langgraph.types import Command
    graph, config = service_graph(monkeypatch, real_service_chat()), {'configurable': {'thread_id': 'service'}}
    graph.invoke({**S.service_inputs(q), 'circuit': '내가 붙인 프로젝트 이름', 'user_id': '42',
                  'connections': jsonb_like(demo.connections(q['netlist']))}, config)
    state = graph.invoke(Command(resume=recorded['resume']), config)
    assert (state['path'], state['answer']) == (recorded['path'], recorded['answer'])


def jsonb_like(value):
    """Postgres jsonb가 돌려주는 모양: 객체 키를 (바이트 길이, 바이트) 순으로 다시 놓는다. 배열 순서는 그대로다."""
    if isinstance(value, dict):
        return {k: jsonb_like(value[k]) for k in sorted(value, key=lambda k: (len(k.encode()), k.encode()))}
    return [jsonb_like(v) for v in value] if isinstance(value, list) else value


def test_replay_miss_during_a_run_is_a_503_naming_the_node_not_a_hidden_fallback(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend.conversations.memory_service import Conversations
    from backend.services import langfuse_prompts
    monkeypatch.setattr(langfuse_prompts, 'publish_analysis_trace', lambda *a, **k: 'skipped')  # [왜] 시험에서 Langfuse로 보내지 않는다
    sent = []

    class Conn:  # [왜] DB 없이 _invoke의 실패 처리만 본다. 상태 줄 · 분석 사건 쓰기는 받아 두기만 한다
        def execute(self, query, params=()):
            sent.append(query)
            return self
        def fetchone(self): return {'user_id': 1, 'version': 1, 'status': 'FAILED'}

    def invoke(*a, **k):
        raise demo.ReplayMiss('기록에 없는 LLM 호출입니다(노드 supervisor, Plan).')
    app = Conversations.__new__(Conversations)
    app.mode, app.graph = 'demo', SimpleNamespace(invoke=invoke)
    with pytest.raises(HTTPException) as error:
        app._invoke(Conn(), 'thread-1', {'input': '질문'}, Conversations._budget_settings()[0])
    assert error.value.status_code == 503 and '노드 supervisor' in error.value.detail
    assert isinstance(error.value.__cause__, demo.ReplayMiss) and any("status='FAILED'" in q for q in sent)
