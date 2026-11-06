"""판정 에이전트(backend/multi_agent/agents/judge.py) 시험: 가짜 LLM · 가짜 사양 표로 읽기 · 숫자 확인 · 인터럽트 · 판정을 본다.

- 역할: AC-02(질문에 없는 숫자는 버림) · AC-07(other) · AC-08(인터럽트 1번) · AC-09(비교는 verdict에서만), 찾기 흐름.
- 하지 않는 일: 실제 LLM · MCP · DB 호출.
- 출처: docs/specs/judge-agent.md What · How · AC
"""
import pytest

from backend.judge import verdict as V
from backend.multi_agent.agents import judge as J

STATE = {'question': 'D1을 TSC 1N5817로 바꿔도 역극성 보호용으로 쓸 수 있어?',
         'conditions': '입력 전압의 최댓값은 20V, D1의 최대 순방향 전류는 150mA이다. 주변 온도는 25°C이다.',
         'target': 'D1', 'target_part': {'ref': 'D1', 'value': '1N4001', 'footprint': 'Diode_THT:D_DO-41_SOD81_P10.16mm',
                                         'nets': [{'name': 'RAW', 'nodes': ['D1.K(1N4001)', 'F1.1(500mA)'], 'more': 0}]},
         'question_type': 'candidate_judge'}


def test_judge_read_calls_llm_once_with_roles_and_circuit():
    seen = []

    def chat(node, system, user, schema):
        seen.append((node, user))
        return J.JudgeRead(role='R01', role_evidence=['D1.K → RAW'])
    out = J.judge_read_agent(STATE, chat=chat)
    assert len(seen) == 1 and seen[0][0] == 'judge_read'
    assert 'R01' in seen[0][1] and 'D1.K(1N4001)' in seen[0][1] and '150mA' in seen[0][1]
    assert out['judge_read']['role'] == 'R01' and out['path'] == ['판정 읽기']


RATINGS = 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'


def specs_of(table):
    def specs(part, codes=None):
        return table.get(part.upper(), [])
    return specs


def r(part, code, mx, unit='V', cond=None, text=None):
    return {'part': part, 'code': code, 'min': None, 'typ': None, 'max': mx, 'text': text, 'unit': unit, 'source_value_text': str(mx),
            'test_condition': cond, 'citation': {'document': f'{part}.pdf', 'page': 1, 'table': RATINGS, 'row': code, 'chunk_index': 1}}


SPECS = {'1N5817': [r('1N5817', 'VRRM', 20.0), r('1N5817', 'IF_AV', 1.0, 'A'), r('1N5817', 'PACKAGE', None, None, text='DO-41')],
         'SS14': [r('SS14', 'VRRM', 40.0), r('SS14', 'IF_AV', 1.0, 'A'), r('SS14', 'PACKAGE', None, None, text='SMA')]}
READ = J.JudgeRead(role='R01', candidates=['1N5817'], values=[
    J.Value(name='v_in_max', number=20, unit='V', quote='입력 전압의 최댓값은 20V'),
    J.Value(name='i_max', number=150, unit='mA', quote='최대 순방향 전류는 150mA'),
    J.Value(name='temp', condition='TA=25°C', quote='주변 온도는 25°C')]).model_dump(mode='json')


def no_interrupt(*a, **k):
    pytest.fail('물을 것이 없는데 인터럽트를 불렀다')


def unknown(payload):
    """사용자가 아무것도 답하지 않은 재개(= 모름). R01의 조건부(허용 전압 강하)는 발동 여부를 늘 묻는다."""
    return {'answers': {}}


def test_ac01_judge_question_gives_not_sufficient(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    out = J.judge_agent({**STATE, 'judge_read': READ}, specs=specs_of(SPECS), find=None, retriever=None)
    j = out['judgement']
    assert j['kind'] == 'judge' and j['results'][0]['verdict'] == 'NOT_SUFFICIENT'
    assert out['reports'][-1]['agent'] == 'judge' and out['path'] == ['판정']


def test_ac02_number_not_in_question_is_dropped_and_asked(monkeypatch):
    read = dict(READ, values=READ['values'] + [{'name': 'v_drop_allowed', 'number': 12, 'unit': 'V', 'flag': None, 'condition': '', 'quote': '12V 허용'}])
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert 'v_drop_allowed' in out['judgement']['dropped']


def test_ac08_interrupt_once_and_reply_fills_values(monkeypatch):
    read = dict(READ, values=[v for v in READ['values'] if v['name'] != 'i_max'])
    calls = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: calls.append(payload) or {'answers': {'i_max': '150mA'}})
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(calls) == 1 and 'i_max' in calls[0]['missing'] and calls[0]['question']
    assert out['judgement']['results'][0]['verdict'] == 'NOT_SUFFICIENT'


def test_empty_reply_keeps_found_values_and_is_not_verified(monkeypatch):
    read = dict(READ, values=[v for v in READ['values'] if v['name'] != 'i_max'])
    monkeypatch.setattr(J, 'interrupt', unknown)
    j = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)['judgement']
    res = j['results'][0]
    assert res['verdict'] == 'NOT_SUFFICIENT'  # VRRM 실패가 확인 안 됨보다 먼저다(SPEC 3절)
    assert 'i_max' in res['missing']


def test_ac07_other_role_gives_no_verdict(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', no_interrupt)
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, role='other')}, specs=specs_of(SPECS), find=None, retriever=None)
    assert out['judgement']['kind'] == 'no_rule' and out['judgement']['results'] == []


def test_find_question_filters_judges_and_ranks(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(conditions)
        return [{'part': 'SS14', 'category': 'schottky-rectifier', 'packages': ['SMA'], 'matches': []},
                {'part': '1N5817', 'category': 'schottky-rectifier', 'packages': ['DO-41'], 'matches': []}]
    read = dict(READ, candidates=[], values=[dict(v, number=12, quote='입력 전압의 최댓값은 12V') if v['name'] == 'v_in_max' else v
                                             for v in READ['values']])
    state = {**STATE, 'question_type': 'candidate_find', 'conditions': STATE['conditions'].replace('20V', '12V'), 'judge_read': read}
    j = J.judge_agent(state, specs=specs_of(SPECS), find=find, retriever=None)['judgement']
    assert seen[0][0] == {'code': 'VRRM', 'gte': pytest.approx(15.0)}
    assert [x['part'] for x in j['shown']] == ['1N5817', 'SS14']  # 1N5817은 DO-41이라 기판 수정 없음 → 먼저
    assert j['kind'] == 'find' and j['capped'] is False


def test_find_does_not_filter_by_original_part_values(monkeypatch):
    """원래 부품 값(orig.*)을 쓰는 조건(R11 TRR ≤ 원래 TRR)은 거르기에 쓰지 않는다. 판정에서 같은 시험 조건 행끼리 본다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(conditions)
        return []
    table = {**SPECS, '1N5819': [r('1N5819', 'VRRM', 40.0), r('1N5819', 'TRR', 5e-8, 's')]}
    read = dict(READ, role='R11', original_part='1N5819', candidates=[],
                values=[READ['values'][0], dict(READ['values'][1], name='i_out')])
    j = J.judge_agent({**STATE, 'question_type': 'candidate_find', 'judge_read': read}, specs=specs_of(table), find=find,
                      retriever=None)['judgement']
    assert [t['code'] for t in seen[0]] == ['VRRM', 'IF_AV'] and j['terms'] == seen[0]


def test_find_passes_original_package_and_category_for_ranking(monkeypatch):
    """찾기는 원래 부품의 패키지 · 분류를 도구에 넘겨 50개로 자르기 전에 그 순서로 줄 세우게 한다(B3). 모르면 None."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(near)
        return []
    rows = [dict(x, category='standard-rectifier') for x in [r('1N4001', 'VRRM', 50.0), r('1N4001', 'PACKAGE', None, None, text='DO-41'),
                                                              r('1N4001', 'PACKAGE', None, None, text='DO-204AL')]]
    for original in ('TSC 1N4001', ''):
        read = dict(READ, original_part=original, candidates=[])
        J.judge_agent({**STATE, 'question_type': 'candidate_find', 'judge_read': read}, specs=specs_of({'1N4001': rows}), find=find,
                      retriever=None)
    assert seen == [{'original_packages': ['DO-41', 'DO-204AL'], 'original_category': 'standard-rectifier'},
                    {'original_packages': None, 'original_category': None}]


def test_ac09_numbers_are_compared_in_verdict_only(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    called = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: called.append(1) or real(*a, **k))
    J.judge_agent({**STATE, 'judge_read': READ}, specs=specs_of(SPECS), find=None, retriever=None)
    assert called


def test_ec02_two_roles_ask_once_and_keep_both_without_answer(monkeypatch):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, role_alt='R08')}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(asked) == 1 and asked[0]['role_choices'] == ['R01', 'R08']
    assert out['judgement']['roles'] == ['R01', 'R08']
    assert out['judgement']['results'][0]['verdict'] == 'NOT_SUFFICIENT'  # 두 역할 중 더 나쁜 판정


def test_ec10_order_code_variant_with_identical_statement_is_identical(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['1N4148 R0G'])
    docs = [{'chunk_id': 7, 'content': 'A0, A0G, R0 and R0G are physically identical; only packing differs.'}]
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=lambda q, parts=None: docs)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and res['checks']  # 주문 코드 품번은 기본 품번의 사양 표 행으로 본다


def ordering_row(code, chunk_id, page=2):
    """검색이 돌려주는 주문 정보 표 한 줄 청크(실제 1N4148 SERIES_K2301.pdf 2쪽 모양)."""
    return {'chunk_id': chunk_id, 'file': '1N4148 SERIES_K2301.pdf', 'page': page, 'table': 'ORDERING INFORMATION',
            'content': f'[1N4148 SERIES_K2301.pdf · {page}쪽 · ORDERING INFORMATION] ORDERING INFORMATION / ORDERING CODE (1): {code}'
                       ' | ORDERING INFORMATION / PACKAGE: DO-35 | ORDERING INFORMATION / PACKING: 10,000 / 14" Reel'}


ORDER_DOCS = [ordering_row('1N4148 R0', 26965), ordering_row('1N4448 R0G', 26973), ordering_row('1N4148 R0G', 26971),
              ordering_row('1N4148 A0G', 99)]


@pytest.mark.parametrize('original,candidate', [('1N4148 A0G', '1N4148 R0G'), ('TSC 1N4148 A0G', '1N4148 r0g'), ('1N4148 A0G', '1N4148')])
def test_order_code_only_difference_is_identical_with_ordering_table_citation(monkeypatch, original, candidate):
    """같은 기본 품번에 주문 코드(R · A · L · M + 글자 하나 + 선택 G)만 다르면 동일품이고, 주문 정보 표의 그 주문 코드 행을 인용한다(B2, 정운 11-06)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    asked = []
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, original_part=original, candidates=[candidate])}, specs=specs_of(table),
                        find=None, retriever=lambda q, parts=None: asked.append(parts) or ORDER_DOCS)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and asked[0] == ['1N4148']
    cite = res['checks'][0]['citation']
    # 'R0'이 'R0G' 안에 있어도 'R0' 행은 고르지 않는다. 후보가 기본 품번뿐이면 원래 품번의 주문 코드 행이다
    want = '1N4148 R0G' if candidate != '1N4148' else None
    assert cite['table'] == 'ORDERING INFORMATION' and cite['page'] == 2 and cite['document'] == '1N4148 SERIES_K2301.pdf'
    assert (cite['row'], cite['chunk_id']) == ((want, 26971) if want else ('1N4148 A0G', 99))


@pytest.mark.parametrize('original,candidate', [('1N4148 A0G', '1N4448 R0G'), ('1N4148', '1N4148 BAT85'), ('1N4148 A0G', '1N4148 R0G')])
def test_order_code_rule_needs_same_base_order_code_shape_and_a_found_row(monkeypatch, original, candidate):
    """기본 품번이 다르거나, 꼬리가 주문 코드 모양이 아니거나, 주문 정보 표에서 그 행을 못 찾으면 코드 규칙으로 동일품을 내지 않는다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0)], '1N4448': [r('1N4448', 'VRRM', 100.0)]}
    docs = [] if candidate == '1N4148 R0G' else ORDER_DOCS  # 마지막 경우: 검색이 주문 정보 행을 못 찾음(지어낸 인용 없음)
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, original_part=original, candidates=[candidate])}, specs=specs_of(table),
                        find=None, retriever=lambda q, parts=None: docs)
    assert out['judgement']['results'][0]['verdict'] != 'IDENTICAL'


def test_identical_by_order_code_survives_schottky_exemption(monkeypatch):
    """쇼트키 후보는 면제 뒤 판정을 다시 정한다. 그때도 주문 코드 동일품은 빠진 값(확인 안 됨)이 있어도 동일품이다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    rows = [dict(x, category='schottky-rectifier') for x in SPECS['1N5817']]
    docs = [dict(ordering_row('1N5817 R0G', 5), file='1N5817 SERIES_H2104.pdf')]
    read = dict(READ, original_part='1N5817 A0G', candidates=['1N5817 R0G'], values=READ['values'][2:])  # 입력 전압 · 전류 없음
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of({'1N5817': rows}), find=None, retriever=lambda q, parts=None: docs)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and 'unverified' in [c['result'] for c in res['checks']]


def test_original_part_with_order_code_reads_base_part_rows(monkeypatch):
    """원래 품번에 주문 코드가 붙어도(1N4148 A0G) 사양 표의 기본 품번(1N4148) 행을 원래 부품 행으로 쓴다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: seen.append(k['original_rows']) or real(*a, **k))
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['SS14'])
    J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=None)
    assert seen == [table['1N4148']]


def test_manufacturer_name_before_part_number_is_dropped_for_spec_lookup(monkeypatch):
    """'TSC 1N5817' · 'Taiwan Semiconductor 1N5817'은 사양 표의 1N5817 행으로 판정한다. 제조사 이름은 품번이 아니다(B1, 11-06)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: seen.append(k['original_rows']) or real(*a, **k))
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0)]}
    for name in ('TSC 1N5817', 'tsc 1N5817', 'Taiwan Semiconductor 1N5817'):
        read = dict(READ, original_part='TSC 1N4148 A0G', candidates=[name])
        res = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=None)['judgement']['results'][0]
        assert res['part'] == name  # 이름은 질문에 쓴 대로 보인다
        assert res['checks'][0]['citation']['document'] == '1N5817.pdf'
    assert seen == [table['1N4148']] * 3


def test_schottky_exemption_follows_the_condition_exempt_key():
    """보통 TRR 조건은 쇼트키 계열 모두 면제, exempt: sic 조건(R14 100 kHz 초과)은 SiC 쇼트키만 면제한다."""
    def trr(exempt):
        return V.Check(code='TRR', tier='required', op='<=', basis='35e-9', threshold=35e-9, value=5e-8, result='fail', exempt=exempt)
    j = V.Judgement(part='X', role='R14', verdict='NOT_SUFFICIENT', checks=[trr('schottky'), trr('sic')])
    general = J._schottky_exempt(j, 'schottky-rectifier')
    assert [c.result for c in general.checks] == ['pass', 'fail'] and general.verdict == 'NOT_SUFFICIENT'
    sic = J._schottky_exempt(j, 'sic-schottky-diode')
    assert [c.result for c in sic.checks] == ['pass', 'pass'] and sic.verdict == 'ROLE_SUFFICIENT'


def test_grounded_requires_quote_in_text_and_same_number():
    text = '입력 전압의 최댓값은 20V'
    assert J.grounded(text, J.Value(name='v_in_max', number=20, unit='V', quote='최댓값은 20V'))
    assert not J.grounded(text, J.Value(name='v_in_max', number=12, unit='V', quote='최댓값은 20V'))
    assert not J.grounded(text, J.Value(name='v_in_max', number=20, unit='V', quote='최댓값은 20 볼트'))


def test_numbers_in_role_rules_do_not_ground_values(monkeypatch):
    """규칙 파일의 알아보는 법 글(R10 '5V 출력과 3.3V 입력')에 있는 숫자는 사용자가 준 숫자가 아니다(AC-02)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    read = dict(READ, values=READ['values'] + [{'name': 'v_drop_allowed', 'number': 3.3, 'unit': 'V', 'flag': None,
                                                 'condition': '', 'quote': '3.3V 입력'}])
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert 'v_drop_allowed' in out['judgement']['dropped']
