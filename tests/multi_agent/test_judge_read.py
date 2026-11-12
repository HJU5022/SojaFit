"""판정 읽기(backend/multi_agent/agents/judge.py · backend/prompts/judge_read.md) 시험: 값 이름이 규칙에 닿는지.

- 역할: 읽기 LLM이 받는 글에 역할마다 그 역할의 값 이름이 있는지, 프롬프트가 모든 값 이름의 뜻을 담았는지,
  고른 역할의 이름으로 읽은 값은 남고 다른 이름은 버려 `dropped`에 남는지.
- 하지 않는 일: 실제 LLM · MCP · DB 호출.
- 출처: SPEC 8.3 "회로 값 이름", docs/specs/judge-agent.md How
"""
import re
import copy

import pytest

from backend.judge import conditions as C
from backend.multi_agent.agents import judge as J

RULES = C.load()
STATE = {'question': 'D2를 TSC 1N5819로 바꿔도 돼?',
         'conditions': '반대편 5V 레일의 최대 전압은 5V이다. D2의 최대 부하 전류는 10mA이다.',
         'target': 'D2', 'target_part': {'ref': 'D2', 'value': '1N5819', 'footprint': 'SOD-123', 'nets': []},
         'question_type': 'candidate_judge'}


@pytest.mark.parametrize('context',['plan','read','docs'])
def test_t7_footprint_only_changes_never_reach_multi_model_context(context):
    from backend.multi_agent import supervisor as S
    from backend.multi_agent.agents import docs as D
    from backend.multi_agent.contracts import Task
    from evals.runners import plan_injection_baseline as P
    data=P.fixture();attack=next(c['payload'] for c in data['cases'] if c['id']=='T7')
    normal=copy.deepcopy(STATE)
    normal['target_part']['nets']=[{'name':'INPUT','nodes':['D2.A','J1.1'],'more':0}]
    poisoned=copy.deepcopy(normal)
    poisoned['target_part']['footprint']+='; '+attack
    before=copy.deepcopy(poisoned)
    def render(s):
        if context=='plan':return S.render_plan(s,True)
        if context=='read':return J.render_read(s,RULES)
        return D.render(s['question'],Task(id=1,agent='docs',kind='role',goal='role'),[],s['target_part'])
    assert render(normal)==render(poisoned)
    assert attack not in render(poisoned) and 'D2' in render(poisoned)
    assert normal['question'] in render(poisoned)
    assert poisoned==before and 'SOD-123' in poisoned['target_part']['footprint']

def test_historical_numbers_reach_reader_but_are_not_current_grounding(monkeypatch):
    memory = {'thread_id': 'old', 'version': 1, 'approved_at': '2026-11-09', 'part': '1N5819',
              'summary': '입력 전압은 987V', 'context': {'conditions': '입력 전압은 987V'}}
    state = {**STATE, 'approved_memories': [memory]}
    read = J.JudgeRead(role='R02', candidates=['1N5819'], values=[
        J.Value(name='v_reverse_max', number=987, unit='V', quote='입력 전압은 987V')])
    def chat(node, system, user, schema):
        assert '987V' in user and 'never copy historical' in system.lower()
        return read
    result = J.judge_read_agent(state, chat=chat)
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.extend(payload['missing']) or {'answers': {}})
    judged = J.judge_agent({**state, **result}, specs=lambda *args: [], find=None, retriever=None)['judgement']
    assert 'v_reverse_max' in judged['dropped'] and 'v_reverse_max' in asked
    assert '987V' not in J.render_read(state, {})


def test_read_input_lists_each_roles_own_value_names_and_kinds():
    text = J.render_read(STATE, RULES)
    for rid, rule in RULES.items():
        line = next(x for x in text.splitlines() if x.startswith(f'- {rid}:'))
        assert all(f'{name} ({kind})' in line for name, kind in C.inputs(rule).items()), rid
    r02 = next(x for x in text.splitlines() if x.startswith('- R02:'))
    assert 'v_reverse_max' in r02 and 'i_out' not in r02 and 'v_in_max' not in r02  # 다른 역할의 이름은 그 역할 줄에 없다


def test_prompt_explains_every_value_name():
    """[왜] roles.yaml에 값 이름이 늘면 프롬프트에도 뜻이 있어야 LLM이 사용자의 말을 그 이름으로 옮긴다."""
    names = {n for rule in RULES.values() for n in C.inputs(rule)}
    explained = set(re.findall(r'^- `([a-z0-9_]+)`:', J.PROMPT, re.M))
    assert names <= explained, sorted(names - explained)


def test_value_under_the_roles_own_name_is_kept_and_other_names_are_dropped():
    read = J.JudgeRead(role='R02', values=[
        J.Value(name='v_reverse_max', number=5, unit='V', quote='반대편 5V 레일의 최대 전압은 5V'),
        J.Value(name='i_max', number=10, unit='mA', quote='최대 부하 전류는 10mA'),
        J.Value(name='i_out', number=10, unit='mA', quote='최대 부하 전류는 10mA'),       # R11 · R12의 이름
        J.Value(name='v_in_max', number=5, unit='V', quote='반대편 5V 레일의 최대 전압은 5V')])  # R01의 이름
    values, _, dropped = J.to_inputs(read, STATE['conditions'], C.inputs(RULES['R02']))
    assert values == {'v_reverse_max': 5.0, 'i_max': pytest.approx(0.01)}
    assert dropped == ['i_out', 'v_in_max']


def test_roles_own_names_reach_the_thresholds(monkeypatch):
    rows = [{'part': '1N5819', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 40.0, 'text': None, 'unit': 'V', 'source_value_text': '40',
             'test_condition': None, 'citation': {'document': 'a.pdf', 'page': 1, 'table': 'MAXIMUM RATINGS (TA = 25°C)', 'row': 'VRRM',
                                                  'chunk_index': 1}}]
    read = J.JudgeRead(role='R02', candidates=['1N5819'], values=[
        J.Value(name='v_reverse_max', number=5, unit='V', quote='반대편 5V 레일의 최대 전압은 5V'),
        J.Value(name='i_out', number=10, unit='mA', quote='최대 부하 전류는 10mA')]).model_dump(mode='json')
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    j = J.judge_agent({**STATE, 'judge_read': read}, specs=lambda part, codes=None: rows, find=None, retriever=None)['judgement']
    vrrm = next(c for c in j['results'][0]['checks'] if c['code'] in ('VRRM', 'VR'))
    assert vrrm['threshold'] == pytest.approx(6.25) and vrrm['result'] == 'pass'  # 5V × 1.25
    assert j['analysis_inputs']['values_si']['v_reverse_max'] == 5.0
    assert j['analysis_inputs']['roles'] == ['R02']
    assert j['dropped'] == ['i_out'] and 'i_max' in j['asked']  # 다른 역할 이름은 버리고, 그 역할의 이름으로 묻는다


# ── 코퍼스 밖 요구 거절(SPEC 8.3): 규칙 · 조건을 만들기 전에 코드가 대조해 거절한다 ──
GATE = [  # (읽기 칸, 사실 확인, 거절 사유)
    ({'required_specs': [{'words': '55°C에서 고장률 10FIT 이하', 'code': 'none'}]}, {}, 'not_found'),
    ({'maker_wanted': 'ROHM'}, {}, 'part_missing'),
    ({'revision_wanted': '2027년판'}, {}, 'revision_missing'),
    ({'revision_wanted': 'G2710'}, {'revisions': {'G2710': False}}, 'revision_missing'),
]
INSIDE = [  # 사양 표 항목인 성질 · TSC · 코퍼스에 있다고 확인된 개정 코드는 통과
    ({'required_specs': [{'words': '역누설이 작은', 'code': 'IR'}, {'words': '표면실장', 'code': 'PACKAGE'}]}, {}),
    ({'maker_wanted': 'TSC'}, {}),
    ({'maker_wanted': 'Taiwan Semiconductor'}, {}),
    ({'revision_wanted': 'K2611판'}, {'revisions': {'K2611': True}}),
    ({'revision_wanted': 'L0'}, {}),  # 포장 코드는 판이 아니다(11-06 v3-03)
]


def test_prompt_and_schema_name_every_spec_table_item():
    from pydantic import ValidationError

    from backend.rag.spec_lookup import CODES
    assert set(CODES) <= set(re.findall(r"^- `([A-Z0-9_]+)`:", J.PROMPT, re.M))
    with pytest.raises(ValidationError):
        J.RequiredSpec(words='고장률', code='FIT')  # 사양 표 항목 · none 밖의 글자는 형식 검사에서 걸린다


@pytest.mark.parametrize('extra, facts, code', GATE)
def test_requirement_outside_the_corpus_refuses_before_rules(monkeypatch, extra, facts, code):
    monkeypatch.setattr(J, 'interrupt', lambda payload: pytest.fail('거절할 질문인데 빠진 값을 물었다'))
    read = J.JudgeRead(role='R02', candidates=['1N5819'], **extra).model_dump(mode='json')
    asked = {**STATE, 'question': STATE['question'] + ' ' + extra.get('revision_wanted', '')}  # 판 요구는 사용자 글에 있어야 한다
    out = J.judge_agent({**asked, 'facts': facts, 'judge_read': read}, specs=lambda *a, **k: pytest.fail('사양 표를 읽었다'),
                        find=None, retriever=None)
    report = out['reports'][-1]
    assert report['agent'] == 'judge' and report['status'] == 'fail' and report['reason'] == code
    assert out['path'] == ['판정'] and 'judgement' not in out


@pytest.mark.parametrize('extra, facts', INSIDE)
def test_requirement_inside_the_corpus_is_judged(monkeypatch, extra, facts):
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    read = J.JudgeRead(role='R02', candidates=['1N5819'], **extra).model_dump(mode='json')
    out = J.judge_agent({**STATE, 'facts': facts, 'judge_read': read}, specs=lambda part, codes=None: [], find=None, retriever=None)
    assert out['judgement']['kind'] == 'judge' and out['reports'][-1]['status'] == 'ok'


@pytest.mark.parametrize('extra, facts, code', GATE)
def test_multi_graph_ends_the_gate_report_as_a_refusal(extra, facts, code):
    """[왜] Spec 에이전트가 코퍼스 밖 요구로 실패하면 모으기(코드)가 그 사유로 거절한다. 답을 쓰지 않는다."""
    from langgraph.checkpoint.memory import InMemorySaver

    from backend.multi_agent import build as B
    from backend.multi_agent.contracts import Plan, Task
    from backend.multi_agent.supervisor import Facts
    plan = Plan(question_type='candidate_find', next='tasks', tasks=[Task(id=1, agent='judge', kind='candidate_find', goal='find')])
    queue = {'supervisor': [plan], 'judge_read': [J.JudgeRead(role='R02', **extra)]}

    def chat(node, system, user, schema):
        return queue[node].pop(0)  # docs_answer · synth를 부르면 KeyError로 실패한다
    app = B.build_graph(chat=chat, retriever=lambda q, parts=None: [], lookup=lambda state: Facts(**facts),
                        parse=lambda s: {'question': s['input'], 'target': 'D2', 'conditions': STATE['conditions'],
                                         'target_part': STATE['target_part']},
                        judge_enabled=True, specs=lambda *a, **k: [], find=lambda *a, **k: [], checkpointer=InMemorySaver())
    out = app.invoke({'input': 'D2 대체 후보를 찾아 줘 ' + extra.get('revision_wanted', '')}, {'configurable': {'thread_id': code + str(extra)}})
    assert out['path'][-4:] == ['판정 읽기', '판정', '모으기', '거절'] and out['refusal']['code'] == code


def test_refusal_names_only_parts_confirmed_missing():
    """[왜] 제조사 거절(part_missing)에서 코퍼스에 있는 품번을 '찾을 수 없어요'라고 말하지 않는다."""
    from backend.multi_agent.contracts import Reason
    from backend.multi_agent.messages import refusal_for
    assert '1N4148' not in refusal_for(Reason.PART_MISSING, {'parts': {'1N4148': True}, 'revisions': {}})
    assert '1N4001' in refusal_for(Reason.PART_MISSING, {'parts': {'1N4001': False, '1N4148': True}, 'revisions': {}})


def test_json_fragment_in_a_field_is_cut_off():
    """[왜] 읽기 LLM이 칸 값에 JSON · 마크다운 조각을 붙였다(v3-11 · v3-15 · v3-08). 다시 불러도 같은 실수라 조각 앞까지만 남긴다."""
    assert J.JudgeRead(role='R01', revision_wanted="','package_wanted':'SMA'}").revision_wanted == ''
    assert J.JudgeRead(role='R01', revision_wanted='K2611판', package_wanted='SOD-123F').revision_wanted == 'K2611판'
    assert J.Value(name='temp', quote="25°C','condition':'TA=25°C").quote == '25°C'
    assert J.Value(name='temp', quote='주변 온도는 25°C이다.](condition)').quote == '주변 온도는 25°C이다.'


def test_long_prose_in_revision_wanted_is_read_as_no_revision():
    """[왜] 읽기가 개정 코드 대신 40자 넘는 설명 글을 적어 형식 재시도로 노드가 2~3.6초 늦었다(세 회차 v3 재시도 4번 모두, 사전 등록 #45)."""
    assert J.JudgeRead(role='R01', revision_wanted='Order code difference (A0G vs R0G); no revision specified.').revision_wanted == ''
    assert J.JudgeRead(role='R01', revision_wanted='2027 edition').revision_wanted == '2027 edition'
    # 긴 글 안에 개정 코드가 있으면 그 코드만 남긴다(통째로 버리면 개정판 거절이 빠진다)
    assert J.JudgeRead(role='R01', revision_wanted='The user requires the datasheet revision K2611 specifically.').revision_wanted == 'K2611'
    # JSON 조각이 붙어 40자를 넘어도 조각 앞의 개정 코드는 남는다(조각 자르기와 같이 돈다)
    assert J.JudgeRead(role='R01', revision_wanted="K2611','package_wanted':'SMA (DO-214AC)','category_wanted':'x'").revision_wanted == 'K2611'


def test_revision_not_in_the_user_text_and_family_words_do_not_refuse():
    """[왜] 읽기가 질문에 없는 'K2611'을 지어내 개정판 거절(h3-15), '쇼트키 정류형'을 사양 표에 없는 성질로 봐 거절했다(h3-14)."""
    made_up = J.JudgeRead(role='R06', revision_wanted='K2611')
    assert J.outside_corpus(made_up, {}, '양방향 TVS로 바꿔 줘') is None
    assert J.outside_corpus(made_up, {}, 'K2611판 기준으로') is not None
    family = J.JudgeRead(role='R12', required_specs=[J.RequiredSpec(words='쇼트키 정류형', code='none')])
    assert J.outside_corpus(family, {}, '') is None


def test_find_without_original_documents_drops_conditions_against_original_values(monkeypatch):
    """[왜] 원래 부품 문서가 없으면(제조사 미상 1N5231) 'PD ≥ 원래 PD'가 모든 후보를 확인 안 됨으로 만들었다(11-06 h3-13). 구매 규격으로 찾는다."""
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    rows = [{'part': 'BZV55C5V1', 'code': 'VZ', 'min': mn, 'typ': ty, 'max': mx, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'text': None,
             'category': 'zener-diode', 'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)', 'row': 'x'}}
            for mn, ty, mx in ((4.8, None, None), (None, 5.1, None), (None, None, 5.4))]  # C 등급 표는 소수 첫째 자리로 적는다
    read = J.JudgeRead(role='R04', original_part='1N5231', required_specs=[J.RequiredSpec(words='nominal 5.1V, tolerance ±5%', code='VZ')])
    state = {**STATE, 'question_type': 'candidate_find', 'facts': {}, 'judge_read': read.model_dump(mode='json')}
    out = J.judge_agent(state, specs=lambda part, codes=None: rows if part == 'BZV55C5V1' else [],
                        find=lambda *a, **k: [{'part': 'BZV55C5V1', 'category': 'zener-diode', 'packages': ['MMELF']}], retriever=lambda q, parts=None: [])
    shown = out['judgement']['shown']
    assert [j['part'] for j in shown] == ['BZV55C5V1'] and not any(c['basis'].startswith('i_z') for c in shown[0]['checks'])


def test_vague_wish_is_not_a_refusal_but_a_measured_property_is():
    """[왜] '지금 SS14와 같은 수준'도 none으로 와 거절했다(v3-08). 숫자 · 단위나 코퍼스 밖 성질 낱말이 있을 때만 거절한다."""
    vague = J.JudgeRead(role='R05', required_specs=[J.RequiredSpec(words='same usable level as the current SS14', code='none')])
    fit = J.JudgeRead(role='R05', required_specs=[J.RequiredSpec(words='failure rate 10 FIT or less', code='none')])
    assert J.outside_corpus(vague, {}, '') is None and J.outside_corpus(fit, {}, '') is not None
    surge = J.JudgeRead(role='R05', required_specs=[J.RequiredSpec(words='same level as the currently fitted SS14 at a 3A surge', code='none')])
    assert J.outside_corpus(surge, {}, '') is None  # 지금 부품과 같기를 바라는 말은 숫자 · 단위가 있어도 거절하지 않는다(공식 10회차 v3-08)
    same_fit = J.JudgeRead(role='R05', required_specs=[J.RequiredSpec(words='same failure rate (FIT) as the current part', code='none')])
    assert J.outside_corpus(same_fit, {}, '') is not None  # 코퍼스 밖 성질 낱말이 있으면 거절


def test_dropped_limit_value_becomes_the_same_requirement(monkeypatch):
    """[왜] '전압강하 1.8V까지'를 읽기가 이 역할에 없는 v_drop_allowed로 적으면 버려져 VF 검사가 빠졌다(v3-04). 같은 뜻의 요구 조건으로 바꾼다."""
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    read = J.JudgeRead(role='R22', candidates=['UF4007'], values=[J.Value(name='v_drop_allowed', number=1.8, unit='V', quote='1.8V까지')])
    rows = [{'part': 'UF4007', 'code': 'VF', 'min': None, 'typ': None, 'max': 1.7, 'unit': 'V', 'test_condition': 'IF = 1A, TJ = 25°C',
             'text': None, 'category': '', 'citation': {'document': 'a.pdf', 'page': 2, 'table': 'T', 'row': 'VF'}}]
    state = {**STATE, 'conditions': '다이오드 전압강하는 1.8V까지 허용한다.', 'facts': {}, 'judge_read': read.model_dump(mode='json')}
    out = J.judge_agent(state, specs=lambda part, codes=None: rows, find=None, retriever=lambda q, parts=None: [])
    checks = out['judgement']['results'][0]['checks']
    assert any(c['code'] == 'VF' and c['result'] == 'unverified' for c in checks)  # 회로 전류(모름)의 VF가 표에 없다


def test_ac_rms_value_implies_ac_input():
    """[왜] 읽기가 ac_input 플래그를 회차마다 비워 브리지 VRRM 조건(실효값 × √2)이 빠졌다(v3-08). AC 실효값이 있으면 AC 입력이다."""
    read = J.JudgeRead(role='R05', values=[J.Value(name='v_ac_rms', number=9, unit='Vrms', quote='9Vrms')])
    values, _, _ = J.to_inputs(read, '2차는 최대 9Vrms', C.inputs(RULES['R05']))
    assert values['ac_input'] is True


def test_rated_in_the_user_text_makes_a_bare_number_an_equality():
    """[왜] '평균 순방향 전류 정격 1A'를 읽기가 'average forward current 1A'로 옮겨 1A 이상이 되자 2A 부품이 나왔다(v3-14)."""
    text = '구매 규격은 TSC 쇼트키 정류형, 반복 피크 역전압 정격 40~60V, 평균 순방향 전류 정격 1A, AEC-Q101 적합 표기가 있는 제품이다.'
    assert J._rated_words('average forward current 1A', text) == 'average forward current 1A (rated)'
    assert J._rated_words('surge 2A', '투입 시 피크 2A이다.') == 'surge 2A'
    assert [c['op'] for c in C.user_conditions([(J._rated_words('average forward current 1A', text), 'IF_AV')])] == ['>=', '<=']


def test_packing_change_question_is_not_a_refusal():
    """[왜] '포장 바꿈(R0G 대신 A0)'을 사양 표에 없는 성질로 거절했다(h3-10). 'R0G'의 '0G'는 숫자+단위가 아니다."""
    read = J.JudgeRead(role='R11', required_specs=[J.RequiredSpec(words='packing change (ordering code R0G instead of A0)', code='none')])
    assert J.outside_corpus(read, {}, '') is None
    assert not J.NUMBER_UNIT.search('R0G') and J.NUMBER_UNIT.search('10 FIT')


def test_user_spec_replaces_a_role_condition_that_misses_a_circuit_value(monkeypatch):
    """[왜] 읽기가 i_max를 다른 역할 이름(i_coil)으로 적어 버려지자 IF_AV ≥ i_max × kI가 모든 후보를 확인 안 됨으로 만들었다(공식 1회차 v3-12).
    사용자가 IF_AV를 숫자로 정했으면 그 규격이 기준이다."""
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    read = J.JudgeRead(role='R22', candidates=['UF4005'], values=[J.Value(name='v_in_max', number=24, unit='V', quote='24V')],
                       required_specs=[J.RequiredSpec(words='평균 순방향 전류 정격 1A', code='IF_AV')])
    rows = [{'part': 'UF4005', 'code': c, 'min': None, 'typ': None, 'max': v, 'unit': u, 'test_condition': None, 'text': None, 'category': '',
             'citation': {'document': 'a.pdf', 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', 'row': c}}
            for c, v, u in (('VRRM', 600.0, 'V'), ('IF_AV', 1.0, 'A'))]
    state = {**STATE, 'conditions': '최대 24V. 평균 순방향 전류 정격 1A.', 'facts': {}, 'judge_read': read.model_dump(mode='json')}
    out = J.judge_agent(state, specs=lambda part, codes=None: rows, find=None, retriever=lambda q, parts=None: [])
    checks = out['judgement']['results'][0]['checks']
    assert not any(c['basis'].startswith('i_max') for c in checks) and any(c['code'] == 'IF_AV' and c['result'] == 'pass' for c in checks)


def test_same_quantity_under_the_other_flyback_role_name_is_kept():
    """[왜] R22를 고르고 R03 이름(i_coil)으로 적으면 값이 버려졌다(공식 1회차 v3-12). 같은 자리 두 역할의 같은 양은 이름을 바꿔 받는다."""
    read = J.JudgeRead(role='R22', values=[J.Value(name='i_coil', number=250, unit='mA', quote='250mA'),
                                           J.Value(name='v_coil', number=24, unit='V', quote='24V')])
    values, _, dropped = J.to_inputs(read, '최대 24V · 정상 전류 250mA', C.inputs(RULES['R22']))
    assert values == {'i_max': 0.25, 'v_in_max': 24.0} and dropped == []


def test_unit_converted_value_is_grounded_and_both_role_names_are_filled():
    """[왜] 읽기가 '250mA'를 0.25 A로 적어 근거 확인에서 버렸고, 역할이 둘(R22 · R03)이면 한 이름만 채워졌다(공식 2회차 v3-12)."""
    kinds = {**C.inputs(RULES['R22']), **C.inputs(RULES['R03'])}
    read = J.JudgeRead(role='R22', role_alt='R03', values=[J.Value(name='i_max', number=0.25, unit='A', quote='정상 전류 250mA'),
                                                           J.Value(name='v_in_max', number=24, unit='V', quote='최대 24V')])
    values, _, dropped = J.to_inputs(read, '최대 24V · 정상 전류 250mA', kinds)
    assert dropped == [] and values['i_max'] == values['i_coil'] == 0.25 and values['v_in_max'] == values['v_coil'] == 24.0
    fake = J.JudgeRead(role='R22', values=[J.Value(name='i_max', number=0.3, unit='A', quote='정상 전류 250mA')])
    assert J.to_inputs(fake, '정상 전류 250mA', kinds)[2] == ['i_max']  # 다른 값은 여전히 버린다


def test_zener_tolerance_survives_split_or_missing_words():
    """[왜] 읽기가 VZ 첫 말('공칭 3.3V')만 적어 공차가 빠졌다(공식 4회차 v3-13)."""
    text = '구매 규격은 TSC 단일 제너, 공칭 제너 전압 3.3V, 공차 ±2%인 B 등급, 전력 정격 500mW 이상이다.'
    assert J._tolerance_words('nominal 3.3V', 'VZ', text) == 'nominal 3.3V ±2%'
    assert J._tolerance_words('nominal 3.3V', 'VZ', '공칭 3.3V, B 등급') == 'nominal 3.3V ±2%'
    assert J._tolerance_words('PD 0.5W', 'PD', text) == 'PD 0.5W'


def test_same_direction_sentence_beats_a_musing_read_as_bidirectional():
    """[왜] '보호 방향도 기존과 같아야 한다'인데 읽기가 '방향 구분도 덜 신경 써도'를 양방향 요구로 적었다(공식 6회차 v3-10)."""
    from backend.judge import verdict as V
    j = V.Judgement(part='SMAJ6.0CA', role='R06', verdict='ROLE_SUFFICIENT')
    read = J.JudgeRead(role='R06', original_part='SMAJ5.0A', required_specs=[J.RequiredSpec(words='bidirectional', code='DIRECTION')])
    out = J._extra_checks(j, read, 'tvs', [], ['R06'], '음의 과도 전압에 대한 보호 방향도 기존과 같아야 한다.')
    assert out.verdict == 'NOT_SUFFICIENT' and out.checks[-1].basis.startswith('단방향')


def test_same_base_part_with_another_ordering_code_is_the_original():
    """[왜] 'BZV55B3V3 L0 대신 TSC BZV55B3V3 L0G로'에서 읽기가 넷리스트 옛 표기(BZX84C3V3)를 원래 부품으로 적었다(공식 7회차 v3-06)."""
    read = J.JudgeRead(role='R04', original_part='BZX84C3V3', candidates=['TSC BZV55B3V3 L0G'])
    text = '원래 표기는 BZX84C3V3이지만 현재 개조 보드에는 TSC BZV55B3V3 L0가 달려 있다. D1에 쓸 BZV55B3V3 L0 대신 TSC BZV55B3V3 L0G로 주문해도 괜찮아?'
    assert J._original_from_text(read, text) == 'BZV55B3V3 L0'
    other = J.JudgeRead(role='R04', original_part='1N5819', candidates=['1N5819H'])
    assert J._original_from_text(other, '지금 1N5819를 1N5819H로 바꿔도 돼?') == '1N5819'  # 기본 품번이 다르면 그대로


def test_spec_that_restates_a_circuit_value_is_dropped():
    """[왜] 'stand-off voltage matching the 13.0V normal maximum'은 정상 최대 13.0V의 되풀이다. maximum 때문에 VRWM ≤ 13이 됐다(v3-09 안정성 측정)."""
    rule = RULES['R06']
    spec = J.RequiredSpec(words='stand-off voltage matching the 13.0V normal maximum', code='VRWM')
    assert J._restates_circuit_value(spec, {'v_line_max': 13.0}, [rule])
    assert not J._restates_circuit_value(J.RequiredSpec(words='VWM 14.0V 이상', code='VRWM'), {'v_line_max': 13.0}, [rule])


def test_limit_sentence_in_the_conditions_is_read_when_every_read_missed_it(monkeypatch):
    """[왜] 읽기 셋이 모두 '다이오드 전압강하는 1.8V까지 허용한다'를 빠뜨린 회차가 있었다(공식 9회차 3세트 v3-04). 숫자가 없는 문장은 읽지 않는다."""
    assert J.TEXT_LIMITS[0][2].search('다이오드 전압강하는 1.8V까지 허용한다.').groups() == ('1.8', 'V')
    assert J.TEXT_LIMITS[1][2].search('역류는 최대 100µA이어야 한다.').groups() == ('100', 'µA')
    assert not J.TEXT_LIMITS[0][2].search('순방향 전압강하는 제한 항목으로 삼지 않는다.')
    monkeypatch.setattr(J, 'interrupt', lambda payload: {'answers': {}})
    read = J.JudgeRead(role='R22', candidates=['UF4007'], values=[J.Value(name='i_max', number=0.25, unit='A', quote='250mA')])
    rows = [{'part': 'UF4007', 'code': 'VF', 'min': None, 'typ': None, 'max': 1.7, 'unit': 'V', 'test_condition': 'IF = 1A, TJ = 25°C',
             'text': None, 'category': '', 'citation': {'document': 'a.pdf', 'page': 2, 'table': 'T', 'row': 'VF'}}]
    state = {**STATE, 'conditions': '전류는 최대 250mA이다. 다이오드 전압강하는 1.8V까지 허용한다.', 'facts': {}, 'judge_read': read.model_dump(mode='json')}
    out = J.judge_agent(state, specs=lambda part, codes=None: rows, find=None, retriever=lambda q, parts=None: [])
    assert any(c['code'] == 'VF' and c['result'] == 'unverified' for c in out['judgement']['results'][0]['checks'])


def test_candidate_that_facts_say_is_not_in_the_corpus_is_refused():
    """[왜] 코퍼스에 없는 1N5408X · UF4007X를 비슷한 품번 문서로 판정해 답했다(#46 v3-32 · 34, 사전 등록 #47). 원래 부품은 거절 이유가 아니다."""
    facts = {'parts': {'1N5408X': False, '1N4007': True}}
    assert J.outside_corpus(J.JudgeRead(role='R01', candidates=['TSC 1N5408X']), facts)[0] == J.Reason.PART_MISSING
    assert J.outside_corpus(J.JudgeRead(role='R01', candidates=['1N4007']), facts) is None
    assert J.outside_corpus(J.JudgeRead(role='R01', original_part='1N5408X', candidates=['1N4007']), facts) is None


def test_judge_report_without_any_judged_candidate_is_a_failure(monkeypatch):
    """[왜] 판정한 후보가 없는 보고를 일부 답(partial)으로 두면 빈 판정이 답으로 나갔다(#46 v3-31, 사전 등록 #47)."""
    def agent(kind):
        return lambda state, **kw: {'judgement': {'kind': kind, 'results': [], 'shown': []}, 'path': ['판정'],
                                    'reports': [{'status': 'partial', 'summary': '0 candidates judged', 'missing': []}]}
    state = {'task': {'id': 1}, 'question_type': 'candidate_judge'}
    for kind, reason in (('no_rule', J.Reason.NOT_FOUND.value), ('judge', J.Reason.NO_RESULT.value)):
        monkeypatch.setattr(J, 'judge_agent', agent(kind))
        r = J.judge_task_node(state, specs=None, find=None, retriever=None)['reports'][0]
        assert (r['status'], r['reason']) == ('fail', reason)


def test_vz_window_is_read_only_from_an_explicit_range():
    """[왜] 구매 규격 '공칭 3.3V, 공차 ±2%'를 vz_min · vz_max = 3.3으로 읽어 3.3V 제너가 모두 불충족이 됐다(v3-13, 사전 등록 #48)."""
    kinds = C.inputs(RULES['R04'])
    text = '공칭 제너 전압 3.3V, 공차 ±2%. 다른 보드는 제너 전압 3.42~3.78V 범위를 쓴다.'
    nominal = J.JudgeRead(role='R04', values=[J.Value(name='vz_min', number=3.3, unit='V', quote='공칭 제너 전압 3.3V, 공차 ±2%'),
                                              J.Value(name='vz_max', number=3.3, unit='V', quote='공칭 제너 전압 3.3V')])
    values, _, dropped = J.to_inputs(nominal, text, kinds)
    assert 'vz_min' not in values and 'vz_max' not in values and {'vz_min', 'vz_max'} <= set(dropped)
    ranged = J.JudgeRead(role='R04', values=[J.Value(name='vz_min', number=3.42, unit='V', quote='제너 전압 3.42~3.78V'),
                                             J.Value(name='vz_max', number=3.78, unit='V', quote='제너 전압 3.42~3.78V')])
    values, _, _ = J.to_inputs(ranged, text, kinds)
    assert (values['vz_min'], values['vz_max']) == (3.42, 3.78)
