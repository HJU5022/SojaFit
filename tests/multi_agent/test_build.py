"""멀티 에이전트 조립(backend/multi_agent/build.py) 시험: 가짜 LLM · 검색기로 Supervisor가 노드를 오가는 길을 끝까지 돌려 본다.

- 역할: 다섯 길(역할 → 바로 작성, 검색 → 작성 → 검증 → 끝, 검색 두 번 실패 → 못 찾음 거절, 범위 밖 거절, 꺼진 기능 거부)과
  매 서브에이전트 뒤에 Supervisor로 돌아오는지, 거절 문구와 이유 코드가 남는지 확인한다.
- 하지 않는 일: 실제 LLM · 검색 · DB 호출.
- 출처: backend/multi_agent/build.py, MULTI_AGENT.md 구조 결정(11-05)
"""
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from backend.multi_agent import build as B
from backend.multi_agent import supervisor as S
from backend.multi_agent.agents import judge as J
from backend.multi_agent.contracts import Decision, Reason

PART = {'ref': 'D1', 'value': '1N4148', 'footprint': 'DO-35', 'nets': []}


def scripted(*decisions):
    queue = list(decisions)
    calls = []

    def chat(node, system, user, schema):
        calls.append(user)
        return queue.pop(0)
    chat.calls = calls
    return chat


def app(chat, docs=(), passed=(), answer='정격은 20 V이다 [1].', lookup=None, **kw):
    return B.build_graph(
        chat=chat, retriever=lambda q, parts=None: list(docs),
        parse=lambda s: {'question': s['input'], 'target': 'D1', 'conditions': '', 'target_part': PART},
        rewrite=lambda s: {'query': 'q'}, grade=lambda s: {'passed': list(passed)},
        generate=lambda s: {'answer': answer, 'check': {'used': []}}, lookup=lookup, **kw)


def doc(cid):
    return {'chunk_id': cid, 'file': 'a.pdf', 'page': 1, 'content': 'x', 'table': None, 'doc_parts': []}


def test_role_question_goes_straight_to_writer_and_returns_to_supervisor_each_time():
    chat = scripted(Decision(next='writer', question_type='role'), Decision(next='verifier'), Decision(next='finish'))
    out = app(chat, answer='D1은 보호 다이오드이다 [넷리스트].').invoke({'input': 'D1은 왜 필요해?'})
    assert out['path'] == ['입력 읽기', '사실 확인', '판단', '작성', '판단', '검증', '판단', '끝']  # 서브에이전트가 끝날 때마다 판단으로 돌아온다
    assert out['answer'].startswith('D1은') and out['question_type'] == 'role'
    assert 'Question type: role' in chat.calls[1]  # 처음 판단에서 정한 질문 종류가 다음 판단 입력에도 보인다
    assert out['counters']['hops'] == 3 and out['counters']['writes'] == 1


def test_search_then_write_then_verify_then_finish():
    chat = scripted(Decision(next='search', question_type='rating'), Decision(next='writer'), Decision(next='verifier'), Decision(next='finish'))
    out = app(chat, docs=[doc(1)], passed=[1]).invoke({'input': '1N5817 역전압?'})
    assert out['path'] == ['입력 읽기', '사실 확인', '판단', '검색', '판단', '작성', '판단', '검증', '판단', '끝']
    assert 'search → ok' in chat.calls[1]  # 두 번째 판단은 검색 보고를 읽었다
    assert out['passed'] == [1] and out['counters']['searches'] == 1


def test_two_failed_searches_end_as_not_found_refusal_with_code_and_plain_message():
    chat = scripted(Decision(next='search'), Decision(next='search', reason=Reason.NO_RESULT, brief='필터를 풀어서'), Decision(next='search'))
    out = app(chat, docs=[], passed=[]).invoke({'input': '1N5817 역전압?'})
    assert out['path'][-1] == '거절'  # 평가 채점기가 끝이 거절인지 본다
    assert out['refusal']['code'] == Reason.NOT_FOUND.value and out['answer'] == out['refusal']['message']
    assert '코퍼스' not in out['answer']


def test_out_of_scope_is_refused_without_searching():
    chat = scripted(Decision(next='refuse', reason=Reason.OUT_OF_SCOPE, question_type='out_of_scope'))
    out = app(chat).invoke({'input': 'MOSFET 추천해줘'})
    assert out['path'] == ['입력 읽기', '사실 확인', '판단', '거절'] and out['refusal']['code'] == 'out_of_scope'
    assert out['counters']['searches'] == 0


def test_missing_part_fact_reaches_supervisor_and_refusal_names_the_part():
    chat = scripted(Decision(next='refuse', reason=Reason.PART_MISSING))
    lookup = lambda state: S.Facts(parts={'1N4001': False}, revisions={})
    out = app(chat, lookup=lookup).invoke({'input': '1N4001로 바꿔도 돼?'})
    assert 'part 1N4001: NOT in corpus' in chat.calls[0]  # 사실 확인 결과가 Supervisor 입력에 들어간다
    assert '1N4001' in out['answer'] and out['refusal']['code'] == 'part_missing'


def test_verification_failure_allows_one_rewrite_then_refuses():
    bad = '근거 없는 문장이다.'
    chat = scripted(Decision(next='writer'), Decision(next='verifier'), Decision(next='writer', brief='인용 붙여'),
                    Decision(next='verifier'), Decision(next='writer'))  # 세 번째 쓰기는 한도에 걸려 거절
    out = app(chat, answer=bad).invoke({'input': '질문'})
    assert out['path'][-1] == '거절' and out['refusal']['code'] == Reason.VERIFY_FAILED.value
    assert out['counters']['writes'] == 2


def test_unbuilt_features_are_rejected_instead_of_silently_ignored():
    with pytest.raises(ValueError):
        app(scripted(), web_enabled=True)
    with pytest.raises(ValueError):
        app(scripted(), judge_enabled=True)


def test_chat_is_answered_by_the_supervisor_without_searching():
    chat = scripted(Decision(next='finish', question_type='chat', reply='안녕하세요! 회로 속 다이오드의 역할과 대체 후보를 도와 드려요.'))
    out = app(chat, docs=[doc(1)], passed=[1]).invoke({'input': '안녕'})
    assert out['path'] == ['입력 읽기', '사실 확인', '판단', '끝']  # 검색 · 작성 없이 끝난다
    assert out['answer'].startswith('안녕하세요') and out['question_type'] == 'chat'
    assert out['counters']['searches'] == 0 and out['counters']['writes'] == 0


def test_other_part_asks_for_web_but_web_is_off_so_it_is_refused_as_not_found():
    chat = scripted(Decision(next='web', question_type='other_part'))
    out = app(chat).invoke({'input': 'MOSFET 정격이 뭐야?'})
    assert out['path'][-1] == '거절' and out['refusal']['code'] == 'not_found'


def test_unrelated_question_gets_a_gentle_refusal():
    chat = scripted(Decision(next='refuse', reason=Reason.OUT_OF_SCOPE, question_type='out_of_scope'))
    out = app(chat).invoke({'input': '오늘 날씨 어때?'})
    assert '회로나 부품' in out['answer'] and out['refusal']['code'] == 'out_of_scope'



def judge_app(chat, specs, **kw):
    return B.build_graph(
        chat=chat, retriever=lambda q, parts=None: [],
        parse=lambda s: {'question': s['input'], 'target': 'D1', 'conditions': '입력 전압의 최댓값은 20V', 'target_part': PART},
        rewrite=lambda s: {'query': 'q'}, grade=lambda s: {'passed': []},
        generate=lambda s: {'answer': 'x', 'check': {'used': []}}, judge_enabled=True,
        specs=specs, find=lambda *a: [], checkpointer=InMemorySaver(), **kw)


def test_judge_path_goes_read_judge_writer_verifier_finish_with_one_interrupt():
    rows = [{'part': '1N5817', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 20.0, 'text': None, 'unit': 'V',
             'source_value_text': '20', 'test_condition': None,
             'citation': {'document': 'a.pdf', 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', 'row': 'VRRM', 'chunk_index': 1}}]
    read = J.JudgeRead(role='R01', candidates=['1N5817'],
                       values=[J.Value(name='v_in_max', number=20, unit='V', quote='입력 전압의 최댓값은 20V')])
    chat = scripted(Decision(next='judge', question_type='candidate_judge', brief='judge'), read,
                    Decision(next='writer', brief='write'), Decision(next='verifier', brief='verify'), Decision(next='finish', brief='done'))
    app = judge_app(chat, specs=lambda part, codes=None: rows)
    config = {'configurable': {'thread_id': 't1'}}
    state = app.invoke({'input': 'D1을 TSC 1N5817로 바꿔도 돼?'}, config)
    assert '__interrupt__' in state  # i_max가 빠져 한 번 묻는다
    state = app.invoke(Command(resume={'answers': {}}), config)
    assert state['path'].count('판정 읽기') == 1 and '판정' in state['path'] and state['path'][-1] == '끝'
    assert '불충족' in state['answer'] and 'a.pdf' in state['answer'] and '같은 동작은 보장하지 않' in state['answer']


def test_judge_needs_tools_and_checkpointer():
    with pytest.raises(ValueError):
        B.build_graph(chat=scripted(), retriever=lambda q, parts=None: [], judge_enabled=True)


def test_new_turn_clears_previous_judgement():
    """[왜] 같은 thread의 다음 질문에서 앞 질문의 판정 결과로 답을 쓰지 않게 입력 읽기가 판정 칸도 비운다."""
    out = B.parse_node({'input': 'q'}, parse=lambda s: {'question': 'q'})
    assert out['judgement'] == {} and out['judge_read'] == {}
