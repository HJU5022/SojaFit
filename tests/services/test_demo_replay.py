"""데모 응답 기록(recorder) · 재생(replayer, backend/services/demo.py)과 기록 스크립트(scripts/demo/record_demo.py)의 오프라인 시험.

- 역할: 가짜 LLM으로 멀티 그래프를 기록한 뒤 재생하면 같은 답 · 경로가 나오는지, 기록에 없는 호출은 거절 답이 아니라
  노드 이름을 담은 오류로 멈추는지, 기록 줄에 호출 칸 밖의 값(키 등)이 없는지, 스크립트가 DEMO_MODE=1 · 키 없이는 돌지 않는지,
  데모 질문의 v3 문항이 동결 평가셋 입력 그대로인지와 회로 · 대상이 저장소에 있는지 본다.
- 하지 않는 일: 실제 LLM · DB · MCP 호출. 실제 기록 실행과 재생 확인은 스크립트를 키 없는 compose에서 손으로 돌린다.
- 출처: backend/services/demo.py, scripts/demo/record_demo.py, data/demo/DEMO.md
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
    assert any('LAB_' in p for p in S.env_problems('replay', {'DEMO_MODE': '1', 'LAB_READ_VOTES': '3'}))
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
