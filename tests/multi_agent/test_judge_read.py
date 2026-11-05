"""판정 읽기(backend/multi_agent/agents/judge.py · backend/prompts/judge_read.md) 시험: 값 이름이 규칙에 닿는지.

- 역할: 읽기 LLM이 받는 글에 역할마다 그 역할의 값 이름이 있는지, 프롬프트가 모든 값 이름의 뜻을 담았는지,
  고른 역할의 이름으로 읽은 값은 남고 다른 이름은 버려 `dropped`에 남는지.
- 하지 않는 일: 실제 LLM · MCP · DB 호출.
- 출처: SPEC 8.3 "회로 값 이름", docs/specs/judge-agent.md How
"""
import re

import pytest

from backend.judge import conditions as C
from backend.multi_agent.agents import judge as J

RULES = C.load()
STATE = {'question': 'D2를 TSC 1N5819로 바꿔도 돼?',
         'conditions': '반대편 5V 레일의 최대 전압은 5V이다. D2의 최대 부하 전류는 10mA이다.',
         'target': 'D2', 'target_part': {'ref': 'D2', 'value': '1N5819', 'footprint': 'SOD-123', 'nets': []},
         'question_type': 'candidate_judge'}


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
    assert j['dropped'] == ['i_out'] and 'i_max' in j['asked']  # 다른 역할 이름은 버리고, 그 역할의 이름으로 묻는다
