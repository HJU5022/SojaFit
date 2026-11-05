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
]


def test_prompt_and_schema_name_every_spec_table_item():
    from pydantic import ValidationError

    from backend.rag.spec_lookup import CODES
    assert set(CODES) <= set(re.findall(r'^- `([A-Z_]+)`:', J.PROMPT, re.M))
    with pytest.raises(ValidationError):
        J.RequiredSpec(words='고장률', code='FIT')  # 사양 표 항목 · none 밖의 글자는 형식 검사에서 걸린다


@pytest.mark.parametrize('extra, facts, code', GATE)
def test_requirement_outside_the_corpus_refuses_before_rules(monkeypatch, extra, facts, code):
    monkeypatch.setattr(J, 'interrupt', lambda payload: pytest.fail('거절할 질문인데 빠진 값을 물었다'))
    read = J.JudgeRead(role='R02', candidates=['1N5819'], **extra).model_dump(mode='json')
    out = J.judge_agent({**STATE, 'facts': facts, 'judge_read': read}, specs=lambda *a, **k: pytest.fail('사양 표를 읽었다'),
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
    """[왜] Supervisor LLM이 판정 거절 보고 뒤에 작성으로 보내도 코드가 그 사유로 거절한다(한도 거절과 같은 방식)."""
    from langgraph.checkpoint.memory import InMemorySaver

    from backend.multi_agent import build as B
    from backend.multi_agent.contracts import Decision
    from backend.multi_agent.supervisor import Facts
    queue = [Decision(next='judge', question_type='candidate_find'), J.JudgeRead(role='R02', **extra), Decision(next='writer')]
    seen = []

    def chat(node, system, user, schema):
        seen.append(user)
        return queue.pop(0)
    app = B.build_graph(chat=chat, retriever=lambda q, parts=None: [], lookup=lambda state: Facts(**facts),
                        parse=lambda s: {'question': s['input'], 'target': 'D2', 'conditions': STATE['conditions'],
                                         'target_part': STATE['target_part']},
                        rewrite=lambda s: {'query': 'q'}, grade=lambda s: {'passed': []},
                        generate=lambda s: pytest.fail('거절할 질문인데 답을 썼다'), judge_enabled=True,
                        specs=lambda *a, **k: [], find=lambda *a: [], checkpointer=InMemorySaver())
    out = app.invoke({'input': 'D2 대체 후보를 찾아 줘'}, {'configurable': {'thread_id': code + str(extra)}})
    assert out['path'][-3:] == ['판정', '판단', '거절'] and out['refusal']['code'] == code
    assert 'judge → fail' in seen[-1] and f'reason {code}' in seen[-1]  # Supervisor가 판정 보고의 사유를 읽었다


def test_refusal_names_only_parts_confirmed_missing():
    """[왜] 제조사 거절(part_missing)에서 코퍼스에 있는 품번을 '찾을 수 없어요'라고 말하지 않는다."""
    from backend.multi_agent.contracts import Reason
    from backend.multi_agent.messages import refusal_for
    assert '1N4148' not in refusal_for(Reason.PART_MISSING, {'parts': {'1N4148': True}, 'revisions': {}})
    assert '1N4001' in refusal_for(Reason.PART_MISSING, {'parts': {'1N4001': False, '1N4148': True}, 'revisions': {}})
