"""멀티 에이전트 조립(backend/multi_agent/build.py) 시험: 가짜 LLM · 검색기로 Supervisor → 에이전트 하나 → 답 검사 길을 끝까지 돌려 본다.

- 역할: 그래프 모양(노드 이름 · 간선, RAG 고리가 간선으로 보이는지), Supervisor가 고른 길(일상 대화 · 가격 안내 · 범위 밖 거절 · 형식 실패 ·
  RAG · 대체 부품), RAG 고리(근거 없음 → 다른 검색어로 한 번 더, 상한), 거절한 부분 붙이기, 대체 부품 에이전트의 인터럽트 재개(읽기 LLM을
  다시 부르지 않음)와 코드 답 틀, 새 턴에서 칸 비우기를 본다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/build.py, 강의 IV-3 15강 · IV-2 18 · 20강, 회의록 D4-D5 B-지시서 4-4 시험 목록
"""
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from backend.multi_agent import build as B
from backend.multi_agent.agents import judge as J
from backend.multi_agent.agents.docs import DocsAnswer
from backend.multi_agent.contracts import Plan, Reason, Task

PART = {'ref': 'D1', 'value': '1N4148', 'footprint': 'DO-35', 'nets': []}
START_PATH = ['입력 읽기', '사실 확인', 'Supervisor']


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


def docs_plan(query='1N4148 VRRM', **kw):
    return Plan(question_type='rating', next='docs', task=Task(goal='VRRM of 1N4148', query=query), **kw)


ROWS = [{'part': '1N5817', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 20.0, 'text': None, 'unit': 'V',
         'source_value_text': '20', 'test_condition': None,
         'citation': {'document': 'a.pdf', 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', 'row': 'VRRM', 'chunk_index': 1}}]


def judge_app(chat, searched=None):
    return app(chat, docs=[doc(7)], searched=searched, judge_enabled=True, specs=lambda part, codes=None: ROWS,
               find=lambda *a, **k: [], checkpointer=InMemorySaver())


def edges(graph) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in graph.get_graph().edges}


def test_graph_shape_is_supervisor_picks_one_agent_then_check():
    """[왜] 11-09 강사 피드백: Supervisor는 에이전트 앞에 한 번만 있고(강의 15강), 갈림길 · 고리는 간선으로 보여야 한다(강의 03 · 18 · 20강)."""
    graph = judge_app(scripted())
    assert set(graph.get_graph().nodes) == {'__start__', '입력 읽기', '품번·판 확인', 'Supervisor', 'RAG 에이전트', '대체 부품 에이전트',
                                            '답 검사', '끝내기', '거절', '가격 안내', '__end__'}
    assert edges(graph) == {
        ('__start__', '입력 읽기'), ('입력 읽기', '품번·판 확인'), ('품번·판 확인', 'Supervisor'),
        ('Supervisor', 'RAG 에이전트'), ('Supervisor', '대체 부품 에이전트'), ('Supervisor', '가격 안내'), ('Supervisor', '거절'), ('Supervisor', '끝내기'),
        ('RAG 에이전트', '답 검사'), ('대체 부품 에이전트', '답 검사'), ('답 검사', '끝내기'), ('답 검사', '거절'),
        ('끝내기', '__end__'), ('거절', '__end__'), ('가격 안내', '__end__')}
    rag = B.rag_subgraph(chat=None, retriever=None, find=None)
    assert edges(rag) == {('__start__', '검색'), ('검색', '근거 채점·답 쓰기'), ('근거 채점·답 쓰기', '검색'), ('근거 채점·답 쓰기', '__end__')}
    judge = B.judge_subgraph(chat=None, specs=None, find=None, retriever=None)
    assert edges(judge) == {('__start__', '회로 역할 읽기'), ('회로 역할 읽기', '대체 부품 판정'), ('대체 부품 판정', '__end__')}
    # 대체 부품 에이전트를 켜지 않으면 그 노드 · 간선이 없다
    assert '대체 부품 에이전트' not in app(scripted()).get_graph().nodes


def test_chat_finishes_with_the_supervisor_reply_without_agents():
    chat = scripted(supervisor=[Plan(question_type='chat', next='finish', reply='안녕하세요! 회로 속 다이오드를 도와 드려요.')])
    out = app(chat).invoke({'input': '안녕'})
    assert out['path'] == [*START_PATH, '끝내기'] and out['answer'].startswith('안녕하세요') and chat.calls == ['supervisor']


def test_out_of_scope_and_format_failure_are_refused():
    out = app(scripted(supervisor=[Plan(question_type='out_of_scope', next='refuse', reason=Reason.OUT_OF_SCOPE)])).invoke({'input': '날씨?'})
    assert out['path'] == [*START_PATH, '거절'] and out['refusal']['code'] == 'out_of_scope' and '회로나 부품' in out['answer']

    def broken(node, system, user, schema):
        raise ValueError('형식 실패')
    out = app(broken).invoke({'input': 'SS14 정격?'})
    assert out['path'] == [*START_PATH, '거절'] and out['refusal']['code'] == 'limit_reached'


def test_missing_part_fact_reaches_the_supervisor_and_refusal_names_the_part():
    from backend.multi_agent.supervisor import Facts
    seen = []

    def chat(node, system, user, schema):
        seen.append(user)
        return Plan(question_type='rating', next='refuse', reason=Reason.PART_MISSING)
    out = app(chat, lookup=lambda state: Facts(parts={'BAT85': False})).invoke({'input': 'BAT85 정격?'})
    assert 'part BAT85: NOT in corpus' in seen[0] and 'BAT85' in out['answer'] and out['refusal']['code'] == 'part_missing'


def test_price_question_ends_with_the_same_notice_as_the_single_graph_and_no_mouser_call(monkeypatch):
    """가격 질문: Supervisor가 price면 단일 그래프와 같은 가격 안내 노드로 끝난다. 검색 · HTTP(Mouser) 호출이 없고 값이 상태에 없다(ADR 0009)."""
    import httpx
    from backend.multi_agent.messages import price_message

    def no_http(*args, **kwargs):
        raise AssertionError('그래프가 HTTP를 부르면 안 된다(Mouser는 그래프 밖 /api/prices만)')
    monkeypatch.setattr(httpx.Client, 'send', no_http)
    searched = []
    out = app(scripted(supervisor=[Plan(question_type='price', next='price')]), searched=searched).invoke({'input': '1N5817 지금 가격이랑 재고 알려 줘'})
    assert searched == [] and out['path'] == [*START_PATH, '가격 안내']
    assert out['price_parts'] == ['1N5817'] and out['answer'] == price_message(['1N5817']) and out['question_type'] == 'price'


def test_rag_agent_answers_with_one_supervisor_call_and_one_llm_call():
    chat = scripted(supervisor=[docs_plan()], docs_answer=[DocsAnswer(grade='enough', answer='1N4148의 VRRM은 75 V이다 [7].')])
    out = app(chat, docs=[doc(7)]).invoke({'input': '1N4148 VRRM?'})
    assert out['path'] == [*START_PATH, '검색', '근거 채점·답 쓰기', '답 검사', '끝내기']
    assert chat.calls == ['supervisor', 'docs_answer']  # Supervisor 1번 + 근거 채점 · 답 쓰기 1번, 뒤에 Supervisor가 다시 오지 않는다
    assert out['answer'].endswith('[7].') and out['passed'] == [7] and out['check']['used'] == ['7']
    assert out['counters'] == {'hops': 1, 'searches': 1} and out['searches'][0]['query'] == '1N4148 VRRM'


def test_rag_loop_searches_again_with_the_graded_query_then_answers():
    """[왜] 근거가 없다고 채점하면 고리 간선이 검색으로 되돌린다(강의 18강 채점 → 재작성 → 검색). 바퀴마다 경로에 보인다."""
    searched = []
    chat = scripted(supervisor=[docs_plan()], docs_answer=[DocsAnswer(grade='none', next_query='1N4148 Peak reverse voltage'),
                                                          DocsAnswer(grade='enough', answer='VRRM은 75 V이다 [7].')])
    out = app(chat, docs=[doc(7)], searched=searched).invoke({'input': '1N4148 VRRM?'})
    assert out['path'] == [*START_PATH, '검색', '근거 채점·답 쓰기', '검색', '근거 채점·답 쓰기', '답 검사', '끝내기']
    assert searched == ['1N4148 VRRM', '1N4148 Peak reverse voltage'] and out['counters']['searches'] == 2 and out['answer'] == 'VRRM은 75 V이다 [7].'


def test_rag_loop_stops_at_the_search_limit_and_refuses_as_not_found():
    chat = scripted(supervisor=[docs_plan()], docs_answer=[DocsAnswer(grade='none', next_query='b'), DocsAnswer(grade='none', next_query='c')])
    out = app(chat, docs=[doc(7)]).invoke({'input': '1N4148 FIT?'})
    # [왜] 검색은 2바퀴까지(AGENTS 6). 둘째 바퀴도 다른 검색어를 주지만 간선이 고리를 나가 '못 찾음'으로 거절한다
    assert out['path'][-6:] == ['검색', '근거 채점·답 쓰기', '검색', '근거 채점·답 쓰기', '답 검사', '거절']
    assert chat.calls == ['supervisor', 'docs_answer', 'docs_answer'] and out['refusal']['code'] == 'not_found' and out['docs'] == []


def test_declined_parts_are_appended_to_the_agent_answer():
    plan = docs_plan(declined=[{'ask': 'TSC ES1DQ의 VRRM', 'reason': 'part_missing'}])
    chat = scripted(supervisor=[plan], docs_answer=[DocsAnswer(grade='enough', answer='VRRM은 75 V이다 [7].')])
    from backend.multi_agent.supervisor import Facts
    out = app(chat, docs=[doc(7)], lookup=lambda state: Facts(parts={'1N4148': True, 'ES1DQ': False})).invoke({'input': '1N4148과 ES1DQ VRRM?'})
    # [왜] 여러 개를 묻는 질문의 코퍼스 밖 부분을 말없이 빼지 않는다(B-지시서 4-5.3, c20-15)
    assert out['path'][-1] == '끝내기' and out['answer'].startswith('VRRM은 75 V이다 [7].')
    assert "답하지 않은 부분 'TSC ES1DQ의 VRRM'" in out['answer'] and 'ES1DQ' in out['answer']


def test_unbuilt_features_are_rejected_instead_of_silently_ignored():
    with pytest.raises(ValueError):
        app(scripted(), web_enabled=True)
    with pytest.raises(ValueError):
        app(scripted(), judge_enabled=True)  # 판정은 사양 표 도구와 체크포인터가 있어야 켠다


def judge_plan():
    return Plan(question_type='candidate_judge', next='judge', task=Task(goal='judge 1N5817 for D1'))


def test_judge_interrupt_resumes_without_rerunning_the_read_and_answers_with_the_code_template():
    from backend.multi_agent.messages import render_judgement
    read = J.JudgeRead(role='R01', candidates=['1N5817'], values=[J.Value(name='v_in_max', number=20, unit='V', quote='20V')])
    chat = scripted(supervisor=[judge_plan()], judge_read=[read])
    searched, config = [], {'configurable': {'thread_id': 't1'}}
    graph = judge_app(chat, searched)
    state = graph.invoke({'input': 'D1(입력 20V)을 TSC 1N5817로 바꿔도 돼?'}, config)
    assert '__interrupt__' in state  # i_max가 빠져 한 번 묻는다(강의 09강)
    state = graph.invoke(Command(resume={'answers': {}}), config)
    assert chat.calls == ['supervisor', 'judge_read'] and searched == []  # 재개해도 읽기 LLM을 다시 부르지 않고, RAG 검색은 없다
    assert state['path'] == [*START_PATH, '판정 읽기', '판정', '답 검사', '끝내기']
    assert state['answer'] == render_judgement(state['judgement']) and '불충족' in state['answer'] and 'a.pdf' in state['answer']
    assert state['check']['judgement'] is True and state['judgement']['kind'] == 'judge'


def test_judge_gate_refusal_ends_as_refusal_without_an_answer():
    """[왜] 대체 부품 에이전트가 코퍼스 밖 요구(TSC 아닌 제조사)로 실패하면 답 없이 그 사유로 거절한다(SPEC 8.3)."""
    read = J.JudgeRead(role='R01', candidates=['1N5817'], maker_wanted='Vishay')
    state = judge_app(scripted(supervisor=[judge_plan()], judge_read=[read])).invoke({'input': 'D1을 Vishay 1N5817로?'},
                                                                                       {'configurable': {'thread_id': 't2'}})
    assert '__interrupt__' not in state and state['path'][-4:] == ['판정 읽기', '판정', '답 검사', '거절']
    assert state['refusal']['code'] == 'part_missing' and state['judgement'] == {}


def test_judge_falls_back_to_the_rag_agent_when_judge_is_off():
    chat = scripted(supervisor=[judge_plan()], docs_answer=[DocsAnswer(grade='enough', answer='1N5817 VRRM은 20 V이다 [7].')])
    out = app(chat, docs=[doc(7)]).invoke({'input': 'D1을 1N5817로?'})
    assert out['path'][3:5] == ['검색', '근거 채점·답 쓰기'] and out['searches'][0]['query'] == 'judge 1N5817 for D1'  # 검색어가 없으면 목표로 찾는다


def test_new_turn_clears_previous_answer_and_judgement():
    """[왜] 같은 thread의 다음 질문에서 앞 질문의 지시서 · 판정 결과로 답을 쓰지 않게 입력 읽기가 칸을 비운다."""
    out = B.parse_node({'input': 'q'}, parse=lambda s: {'question': 'q'})
    assert out['judgement'] == {} and out['plan'] == {} and out['task'] == {} and out['refusal_reason'] == '' and out['searches'] == []
