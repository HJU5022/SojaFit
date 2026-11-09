"""멀티 에이전트 조립(backend/multi_agent/build.py) 시험: 가짜 LLM · 검색기로 계획 → 서브에이전트 → 모으기 → 답 검사 길을 끝까지 돌려 본다.

- 역할: 바로 끝내는 길(일상 대화 · 가격 안내 · 범위 밖 거절 · 계획 형식 실패), 할 일 1개(역할 · 정격)와 2개(동시 실행 → 종합),
  판정 길의 인터럽트 재개(읽기 LLM을 다시 부르지 않고, 함께 돈 문서 할 일도 다시 돌지 않음), 판정 거절 보고, 새 턴에서 칸 비우기를 본다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/build.py, 참조/아티팩트 "SojaFit 멀티 에이전트 구조", 회의록 D4-D5 B-지시서 4-4 시험 목록
"""
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from backend.multi_agent import build as B
from backend.multi_agent.agents import judge as J
from backend.multi_agent.agents.docs import DocsAnswer
from backend.multi_agent.contracts import Plan, Reason, Task
from backend.multi_agent.supervisor import Synth

PART = {'ref': 'D1', 'value': '1N4148', 'footprint': 'DO-35', 'nets': []}


def scripted(**by_node):
    """노드 이름마다 답을 차례로 내는 가짜 LLM. 부른 노드 이름을 순서대로 남긴다."""
    queues, calls = {k: list(v) for k, v in by_node.items()}, []

    def chat(node, system, user, schema):
        calls.append(node)
        return queues[node].pop(0)
    chat.calls = calls
    return chat


def doc(cid, file='a.pdf', page=1):
    return {'chunk_id': cid, 'file': file, 'page': page, 'content': 'VRRM 75 V', 'table': None, 'doc_parts': []}


def app(chat, docs=(), lookup=None, searched=None, **kw):
    def retriever(q, parts=None):
        if searched is not None:
            searched.append(q)
        return list(docs)
    return B.build_graph(chat=chat, retriever=retriever, lookup=lookup,
                         parse=lambda s: {'question': s['input'], 'target': 'D1', 'conditions': '', 'target_part': PART}, **kw)


def docs_task(i=1, kind='rating', query='1N4148 VRRM'):
    return Task(id=i, agent='docs', kind=kind, goal=f'goal {i}', query=query)


def test_chat_finishes_with_the_plan_reply_without_agents():
    chat = scripted(supervisor=[Plan(question_type='chat', next='finish', reply='안녕하세요! 회로 속 다이오드를 도와 드려요.')])
    out = app(chat).invoke({'input': '안녕'})
    assert out['path'] == ['입력 읽기', '사실 확인', '계획', '끝'] and out['answer'].startswith('안녕하세요') and chat.calls == ['supervisor']


def test_out_of_scope_and_plan_format_failure_are_refused():
    out = app(scripted(supervisor=[Plan(question_type='out_of_scope', next='refuse', reason=Reason.OUT_OF_SCOPE)])).invoke({'input': '날씨?'})
    assert out['path'][-1] == '거절' and out['refusal']['code'] == 'out_of_scope' and '회로나 부품' in out['answer']

    def broken(node, system, user, schema):
        raise ValueError('형식 실패')
    out = app(broken).invoke({'input': 'SS14 정격?'})
    assert out['path'] == ['입력 읽기', '사실 확인', '계획', '거절'] and out['refusal']['code'] == 'limit_reached'


def test_missing_part_fact_reaches_the_plan_and_refusal_names_the_part():
    from backend.multi_agent.supervisor import Facts
    seen = []

    def chat(node, system, user, schema):
        seen.append(user)
        return Plan(question_type='rating', next='refuse', reason=Reason.PART_MISSING)
    out = app(chat, lookup=lambda state: Facts(parts={'BAT85': False})).invoke({'input': 'BAT85 정격?'})
    assert 'part BAT85: NOT in corpus' in seen[0] and 'BAT85' in out['answer'] and out['refusal']['code'] == 'part_missing'


def test_price_question_ends_with_the_same_notice_as_the_single_graph_and_no_mouser_call(monkeypatch):
    """가격 질문: 계획이 price면 단일 그래프와 같은 가격 안내 노드로 끝난다. 검색 · HTTP(Mouser) 호출이 없고 값이 상태에 없다(ADR 0009)."""
    import httpx
    from backend.multi_agent.messages import price_message

    def no_http(*args, **kwargs):
        raise AssertionError('그래프가 HTTP를 부르면 안 된다(Mouser는 그래프 밖 /api/prices만)')
    monkeypatch.setattr(httpx.Client, 'send', no_http)
    searched = []
    out = app(scripted(supervisor=[Plan(question_type='price', next='price')]), searched=searched).invoke({'input': '1N5817 지금 가격이랑 재고 알려 줘'})
    assert searched == [] and out['path'] == ['입력 읽기', '사실 확인', '계획', '가격 안내']
    assert out['price_parts'] == ['1N5817'] and out['answer'] == price_message(['1N5817']) and out['question_type'] == 'price'


def test_one_docs_task_answers_without_a_second_supervisor_call():
    chat = scripted(supervisor=[Plan(question_type='rating', next='tasks', tasks=[docs_task()])],
                    docs_answer=[DocsAnswer(grade='enough', answer='1N4148의 VRRM은 75 V이다 [7].')])
    out = app(chat, docs=[doc(7)]).invoke({'input': '1N4148 VRRM?'})
    assert out['path'] == ['입력 읽기', '사실 확인', '계획', '문서', '모으기', '답 정리', '답 검사', '끝']
    assert chat.calls == ['supervisor', 'docs_answer']  # Supervisor 1번 + 서브에이전트 1번
    assert out['answer'].endswith('[7].') and out['passed'] == [7] and out['check']['used'] == ['7'] and out['counters']['searches'] == 1


def test_two_tasks_run_in_one_step_and_are_joined_by_synth():
    p = Plan(question_type='role', next='tasks', tasks=[docs_task(1, kind='role', query=''), docs_task(2)])
    by_goal = {'goal 1': DocsAnswer(grade='enough', answer='D1은 신호를 보호한다 [넷리스트].'),
               'goal 2': DocsAnswer(grade='partial', answer='VRRM은 75 V이다 [7].', missing=['IFSM'])}  # 일부만 답해 종합(LLM)이 이유를 쓴다
    calls = []

    def chat(node, system, user, schema):
        # [왜] 두 할 일이 동시에 돌아 부르는 순서가 정해지지 않는다. 지시서의 목표로 답을 고른다
        calls.append(node)
        if node == 'supervisor':
            return p
        if node == 'synth':
            return Synth(answer='D1은 신호를 보호한다 [넷리스트]. 1N4148의 VRRM은 75 V이다 [7].')
        return by_goal[next(g for g in by_goal if f'goal: {g}' in user)]
    chat.calls = calls
    out = app(chat, docs=[doc(7)]).invoke({'input': 'D1 역할과 VRRM?'})
    assert out['path'].count('문서') == 2 and out['path'].count('모으기') == 1  # 두 할 일이 같은 단계에서 돌고 모으기는 한 번
    assert out['path'][-3:] == ['종합', '답 검사', '끝'] and chat.calls[-1] == 'synth' and out['counters']['hops'] == 2
    assert out['check']['used'] == ['7', '넷리스트']


def test_synth_that_invents_a_number_is_refused_by_the_check():
    p = Plan(question_type='rating', next='tasks', tasks=[docs_task(1), docs_task(2)])
    chat = scripted(supervisor=[p], docs_answer=[DocsAnswer(grade='partial', answer='VRRM은 75 V이다 [7].')] * 2,
                    synth=[Synth(answer='VRRM은 100 V이다 [7].')])
    out = app(chat, docs=[doc(7)]).invoke({'input': 'q'})
    assert out['path'][-2:] == ['답 검사', '거절'] and out['refusal']['code'] == 'verify_failed'


def test_two_ok_docs_answers_are_joined_by_code_without_the_synth_llm():
    p = Plan(question_type='rating', next='tasks', tasks=[docs_task(1), docs_task(2, query='1N4148 TJ')])
    chat = scripted(supervisor=[p], docs_answer=[DocsAnswer(grade='enough', answer='VRRM은 75 V이다 [7].')] * 2)
    out = app(chat, docs=[doc(7)]).invoke({'input': '1N4148 VRRM과 TJ?'})
    # [왜] 두 부분 답이 모두 근거 있는 완성 글이면 코드로 잇는다(종합 LLM 4초 절약, 11-07 R1 dev r1-075)
    assert 'synth' not in chat.calls and out['path'][-3:] == ['답 정리', '답 검사', '끝'] and out['answer'].count('[7]') == 2


def test_all_tasks_failing_ends_as_refusal_with_the_reason():
    # [왜] 설계 v2: 문서가 근거를 못 찾으면 Supervisor ①이 한 번 다시 계획한다. 재계획도 거절을 고르면 거절로 끝난다
    chat = scripted(supervisor=[Plan(question_type='rating', next='tasks', tasks=[docs_task()]),
                                Plan(question_type='rating', next='refuse', reason=Reason.NOT_FOUND)],
                    docs_answer=[DocsAnswer(grade='none'), DocsAnswer(grade='none')])
    out = app(chat, docs=[doc(7)]).invoke({'input': '1N4148 FIT?'})
    assert out['path'][-4:] == ['문서', '모으기', '계획', '거절'] and out['refusal']['code'] == 'not_found'
    assert chat.calls == ['supervisor', 'docs_answer', 'supervisor']  # 다른 검색어를 주지 않아 문서 LLM은 1번


def test_replan_runs_a_second_round_with_parts_and_answers_from_it():
    searched = []
    first = Plan(question_type='rating', next='tasks', tasks=[docs_task(query='bridge 1000 V 40 A junction temperature')])
    second = Plan(question_type='rating', next='tasks',
                  tasks=[Task(id=1, agent='docs', kind='rating', goal='TJ', query='TS40P05G TJ', parts=['TS40P05G'])])
    chat = scripted(supervisor=[first, second], docs_answer=[DocsAnswer(grade='none'), DocsAnswer(grade='enough', answer='TJ는 150°C이다 [7].')])
    out = app(chat, docs=[doc(7)], searched=searched).invoke({'input': '1000 V 40 A 브리지 접합부 온도?'})
    assert out['path'][-7:] == ['모으기', '계획', '문서', '모으기', '답 정리', '답 검사', '끝'] and out['answer'] == 'TJ는 150°C이다 [7].'
    assert out['counters']['replans'] == 1 and out['counters']['hops'] == 2


def test_unbuilt_features_are_rejected_instead_of_silently_ignored():
    with pytest.raises(ValueError):
        app(scripted(), web_enabled=True)
    with pytest.raises(ValueError):
        app(scripted(), judge_enabled=True)  # 판정은 사양 표 도구와 체크포인터가 있어야 켠다


ROWS = [{'part': '1N5817', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 20.0, 'text': None, 'unit': 'V',
         'source_value_text': '20', 'test_condition': None,
         'citation': {'document': 'a.pdf', 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', 'row': 'VRRM', 'chunk_index': 1}}]


def judge_app(chat, searched=None, specs=lambda part, codes=None: ROWS):
    return app(chat, docs=[doc(7)], searched=searched, judge_enabled=True, specs=specs, find=lambda *a, **k: [], checkpointer=InMemorySaver())


def test_judge_interrupt_resumes_without_rerunning_the_read_or_the_parallel_docs_task():
    read = J.JudgeRead(role='R01', candidates=['1N5817'], values=[J.Value(name='v_in_max', number=20, unit='V', quote='20V')])
    p = Plan(question_type='candidate_judge', next='tasks',
             tasks=[Task(id=1, agent='judge', kind='candidate_judge', goal='judge 1N5817'), docs_task(2)])
    chat = scripted(supervisor=[p], judge_read=[read], docs_answer=[DocsAnswer(grade='enough', answer='VRRM은 75 V이다 [7].')],
                    synth=[Synth(answer='1N5817은 불충족이다. 1N4148의 VRRM은 75 V이다 [7].')])
    searched, config = [], {'configurable': {'thread_id': 't1'}}
    graph = judge_app(chat, searched)
    state = graph.invoke({'input': 'D1(입력 20V)을 TSC 1N5817로 바꿔도 돼? 1N4148 VRRM도'}, config)
    assert '__interrupt__' in state  # i_max가 빠져 한 번 묻는다
    state = graph.invoke(Command(resume={'answers': {}}), config)
    assert chat.calls.count('judge_read') == 1 and chat.calls.count('docs_answer') == 1 and len(searched) == 1
    # [왜] 판정 · 문서 할 일이 모두 ok면 종합 LLM 없이 코드로 잇는다(11-07)
    assert state['path'][-3:] == ['답 정리', '답 검사', '끝'] and state['path'].count('모으기') == 1
    assert '불충족' in state['answer'] and 'a.pdf' in state['answer'] and state['judgement']['kind'] == 'judge'


def test_single_judge_task_answers_with_the_code_template():
    read = J.JudgeRead(role='R01', candidates=['1N5817'], values=[J.Value(name='v_in_max', number=20, unit='V', quote='20V'),
                                                                   J.Value(name='i_max', number=0.1, unit='A', quote='100mA')])
    from backend.multi_agent.messages import render_judgement
    p = Plan(question_type='candidate_judge', next='tasks', tasks=[Task(id=1, agent='judge', kind='candidate_judge', goal='judge')])
    graph = judge_app(scripted(supervisor=[p], judge_read=[read]))
    state = graph.invoke({'input': 'D1(입력 20V, 100mA)을 1N5817로?'}, {'configurable': {'thread_id': 't2'}})
    if '__interrupt__' in state:
        state = graph.invoke(Command(resume={'answers': {}}), {'configurable': {'thread_id': 't2'}})
    assert state['answer'] == render_judgement(state['judgement']) and state['check']['judgement'] is True
    assert state['path'][-4:] == ['모으기', '답 정리', '답 검사', '끝']


def test_new_turn_clears_previous_reports_and_judgement():
    """[왜] 같은 thread의 다음 질문에서 앞 질문의 보고 · 판정 결과로 답을 쓰지 않게 입력 읽기가 칸을 비운다."""
    out = B.parse_node({'input': 'q'}, parse=lambda s: {'question': 'q'})
    assert out['reports'] is None and out['judgement'] == {} and out['plan'] == {} and out['refusal_reason'] == ''
    from backend.multi_agent.state import add_or_reset
    assert add_or_reset([{'task': 1}], None) == [] and add_or_reset([{'task': 1}], [{'task': 2}]) == [{'task': 1}, {'task': 2}]
