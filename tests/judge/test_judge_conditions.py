"""역할 규칙 읽기 · 기준식 계산(backend/judge/conditions.py) 시험.

- 역할: 기준식 문법(사칙 연산 · 숫자 · 회로 값 · kV · kI · orig.<코드>), 빠진 값, 규칙 모양 검사, 물어볼 값 목록을 본다.
- 하지 않는 일: 실제 roles.yaml 23개 검사(test_judge_rules_file.py), 판정.
- 출처: docs/specs/judge-agent.md How "규칙 파일 형식"
"""
import pytest
import yaml

from backend.judge import conditions as C

RULE = yaml.safe_load('''
name: 역극성 보호(직렬)
recognize: 커넥터 → 다이오드 → 전원 넷
inputs: {v_in_max: number, i_max: number, v_drop_allowed: number, vf_test: condition, pwm: flag}
conditions:
  - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_in_max * kV"}
  - {tier: required, code: IF_AV, op: ">=", basis: "i_max * kI"}
  - {tier: conditional, code: VF, op: "<=", basis: "v_drop_allowed", when: v_drop_allowed, at: vf_test}
  - {tier: conditional, code: TRR, op: "<=", basis: "orig.TRR", when: pwm}
major: {VRRM: higher, IF_AV: higher}
cautions: [발열]
source: "TI SLVA139 [문서]"
''')


def test_evaluate_uses_margins_and_values():
    assert C.evaluate('v_in_max * kV', {'v_in_max': 20.0}) == pytest.approx(25.0)
    assert C.evaluate('i_max * kI', {'i_max': 0.15}) == pytest.approx(0.2142857, rel=1e-6)
    assert C.evaluate('(v_out + v_in_max / n) * 2', {'v_out': 5.0, 'v_in_max': 340.0, 'n': 10.0}) == pytest.approx(78.0)


def test_evaluate_reads_original_part_values():
    assert C.evaluate('orig.TRR', {}, {'TRR': 5e-8}) == pytest.approx(5e-8)


def test_missing_value_gives_none_and_zero_division_gives_none():
    assert C.evaluate('v_in_max * kV', {}) is None
    assert C.evaluate('orig.IR', {}, {}) is None
    assert C.evaluate('v_out / n', {'v_out': 5.0, 'n': 0.0}) is None


@pytest.mark.parametrize('bad', ['__import__("os")', 'v_in_max ** 2', 'max(1, 2)', 'orig.NOPE', 'a if b else c'])
def test_evaluate_rejects_anything_else(bad):
    with pytest.raises(ValueError):
        C.evaluate(bad, {'v_in_max': 1.0, 'a': 1.0, 'b': 1.0, 'c': 1.0})


def test_names_lists_circuit_values_only():
    assert C.names('(v_out + v_in_max / n) * kV') == {'v_out', 'v_in_max', 'n'}
    assert C.names('orig.IR') == set()


def test_check_rule_accepts_good_and_rejects_unknown_input():
    C.check_rule('R01', RULE)
    bad = {**RULE, 'conditions': [{'tier': 'required', 'code': 'VRRM', 'op': '>=', 'basis': 'nope * kV'}]}
    with pytest.raises(ValueError, match='nope'):
        C.check_rule('R01', bad)
    with pytest.raises(ValueError):
        C.check_rule('R01', {**RULE, 'conditions': [{'tier': 'required', 'code': 'VRMS', 'op': '>=', 'basis': '1'}]})


def test_inputs_add_common_temperature():
    assert C.inputs(RULE)['temp'] == 'condition' and C.inputs(RULE)['pwm'] == 'flag'


def test_needed_asks_required_values_and_conditional_triggers():
    """필수 조건의 값과 조건부의 발동 여부만 묻는다. 조건부의 기준 값은 발동한 뒤 판정에서 빠진 값으로 보인다."""
    assert C.needed(RULE, set()) == ['v_in_max', 'i_max', 'v_drop_allowed', 'pwm']
    assert C.needed(RULE, {'v_in_max', 'i_max', 'pwm', 'v_drop_allowed'}) == []


OR_RULE = yaml.safe_load('''
name: x
recognize: x
inputs: {i_coil: number, pulse_test: condition, v_bus: number, v_sw_transient: number}
conditions:
  - {tier: required, any: [{code: IFSM, op: ">=", basis: "i_coil", at: pulse_test}, {code: IF_AV, op: ">=", basis: "i_coil"}]}
  - {tier: required, code: VRRM, op: ">=", basis: "v_sw_transient", default: "v_bus * kV"}
source: x
''')


def test_check_rule_validates_each_any_member():
    C.check_rule('R03', OR_RULE)
    group = OR_RULE['conditions'][0]
    bad = {**group, 'any': [{**group['any'][0], 'basis': 'nope'}, group['any'][1]]}
    with pytest.raises(ValueError, match='nope'):
        C.check_rule('R03', {**OR_RULE, 'conditions': [bad]})
    with pytest.raises(ValueError):
        C.check_rule('R03', {**OR_RULE, 'conditions': [{**group, 'any': [{**group['any'][0], 'code': 'IFSMX'}, group['any'][1]]}]})


def test_check_rule_validates_slot():
    """slot(후보 행에서 볼 칸: min · typ · max)은 그 셋만 받는다(R04 제너 VZ, 11-06)."""
    vz = {'tier': 'required', 'code': 'VZ', 'op': '>=', 'basis': '3.4'}
    C.check_rule('R04', {**RULE, 'conditions': [{**vz, 'slot': 'min'}, {**vz, 'slot': 'max'}]})
    with pytest.raises(ValueError, match='slot'):
        C.check_rule('R04', {**RULE, 'conditions': [{**vz, 'slot': 'avg'}]})


def test_check_rule_validates_exempt():
    trr = {'tier': 'required', 'code': 'TRR', 'op': '<=', 'basis': '35e-9'}
    C.check_rule('R14', {**RULE, 'conditions': [{**trr, 'exempt': 'sic'}, {**trr, 'exempt': 'none'}]})
    with pytest.raises(ValueError, match='exempt'):
        C.check_rule('R14', {**RULE, 'conditions': [{**trr, 'exempt': 'all'}]})


def test_needed_asks_first_any_member_and_default_values_only_when_nothing_is_computable():
    """'A 또는 B'는 계산할 수 있는 멤버가 없을 때만 첫 멤버의 값을, 기본값이 있는 조건은 기준식 값이 없을 때 기본값 식의 값을 묻는다."""
    assert C.needed(OR_RULE, set()) == ['i_coil', 'pulse_test', 'v_bus']
    assert C.needed(OR_RULE, {'i_coil', 'v_sw_transient'}) == []


def test_user_conditions_from_required_specs():
    # [왜] 사용자가 숫자로 적은 규격을 판정 · 찾기 조건으로 써야 규격 밖 후보를 안 보여 준다(11-06 v3-11 · 12)
    from backend.judge.conditions import user_conditions
    got = lambda w, c: [(x['op'], round(float(x['basis']), 12)) for x in user_conditions([(w, c)])]  # noqa: E731
    assert got('반복 피크 역전압 정격 400~600V', 'VRRM') == [('>=', 400.0), ('<=', 600.0)]
    assert got('평균 순방향 전류 정격 1A 이상 2A 미만', 'IF_AV') == [('>=', 1.0), ('<=', 1.999999998)]
    assert got('역회복 시간 최댓값 75ns 이하', 'TRR') == [('<=', 7.5e-08)]
    assert got('10/1000µs 피크 펄스 전력 400W 이상 600W 미만', 'PPPM') == [('>=', 400.0), ('<=', 599.9999994)]  # 1000µs는 W가 아니라 버린다
    assert got('작동 스탠드오프 전압 5.0V', 'VRWM') == [('>=', 5.0)]  # 연산 말 없음 · 정격 아님 → 좋은 방향
    assert got('average forward current rating 1A', 'IF_AV') == [('>=', 1.0), ('<=', 1.0)]  # 정격이면 같음
    assert got('피크 10A 서지 전류 보호 유지', 'IPP') == [('>=', 10.0)] and got('forward voltage drop up to 1.8V', 'VF') == [('<=', 1.8)]
    assert got('smaller reverse leakage', 'IR') == [] and got('AEC-Q101', 'none') == []


def test_english_range_words_use_the_operator_nearest_each_number():
    """[왜] '400W or more and less than 600W'의 400 뒤 글에 600의 'less than'이 같이 있어 400W가 미만으로 읽혔다(11-06 v3-15)."""
    from backend.judge import conditions as C
    got = [(c['op'], round(float(c['basis']))) for c in C.user_conditions([('peak pulse power 400W or more and less than 600W', 'PPPM')])]
    assert got == [('>=', 400), ('<=', 600)]
    assert [c['op'] for c in C.user_conditions([('at least 1A and under 2A', 'IF_AV')])] == ['>=', '<=']


def test_zener_nominal_and_tolerance_class_use_the_typ_min_max_slots():
    """[왜] '공칭 3.3V, 공차 ±2%(B 등급)'를 최대 칸으로 봐 3.3V 제너가 떨어졌고, 'nominal'의 min을 이상으로 읽었다(11-06 v3-13)."""
    from backend.judge import conditions as C
    from backend.judge import verdict as V
    got = [(c['op'], round(float(c['basis']), 3), c.get('slot')) for c in C.user_conditions([('nominal 3.3V, tolerance ±2% (B grade)', 'VZ')])]
    assert got == [('>=', 3.3, 'typ'), ('<=', 3.3, 'typ'), ('>=', 3.184, 'min'), ('<=', 3.284, 'min'), ('>=', 3.316, 'max'), ('<=', 3.416, 'max')]
    assert [c['op'] for c in C.user_conditions([('nominal zener voltage 3.3V', 'VZ')])] == ['>=', '<=']
    rule = {'conditions': C.user_conditions([('nominal 3.3V ±2%', 'VZ')])}
    assert {t.get('slot') for t in V.search_conditions(rule, {})} == {'typ', 'min', 'max'}  # 찾기도 같은 칸으로 거른다

    def row(mn, ty, mx):
        return [{'part': 'X', 'code': 'VZ', 'min': mn, 'typ': None, 'max': None, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'citation': {}},
                {'part': 'X', 'code': 'VZ', 'min': None, 'typ': ty, 'max': None, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'citation': {}},
                {'part': 'X', 'code': 'VZ', 'min': None, 'typ': None, 'max': mx, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'citation': {}}]
    b_grade = V.judge_part(rule, 'R04', 'BZT52B3V3', {}, {}, row(3.23, 3.3, 3.37))
    c_grade = V.judge_part(rule, 'R04', 'BZT52C3V3', {}, {}, row(3.1, 3.3, 3.5))
    assert b_grade.verdict == 'ROLE_SUFFICIENT' and c_grade.verdict == 'NOT_SUFFICIENT'


def test_lone_upper_bound_on_a_higher_is_better_rating_is_a_load_to_withstand():
    """[왜] '투입 피크 최대 2A'를 IFSM ≤ 2A로 읽어 IFSM 30A 후보가 불충족이 됐다(11-06 v3-01). 범위는 그대로 둔다."""
    from backend.judge import conditions as C
    assert [(c['op'], float(c['basis'])) for c in C.user_conditions([('inrush surge up to 2A 8.3ms', 'IFSM')])] == [('>=', 2.0)]
    assert [c['op'] for c in C.user_conditions([('IF(AV) 1A 이상 2A 미만', 'IF_AV')])] == ['>=', '<=']
    assert [c['op'] for c in C.user_conditions([('VF 1.8V까지', 'VF')])] == ['<=']


def test_tolerance_class_excludes_tighter_grades_too():
    """[왜] 공차는 등급이다. ±5% 찾기에 ±2% 부품(BZV55B5V1)이 나왔다(11-06 h3-13). 같은 등급(C 4.8 / 5.4)만 남는다."""
    from backend.judge import conditions as C
    from backend.judge import verdict as V
    rule = {'conditions': C.user_conditions([('nominal 5.1V, tolerance ±5%', 'VZ')])}

    def rows(mn, mx):
        return [{'part': 'X', 'code': 'VZ', 'min': a, 'typ': b, 'max': c, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'citation': {}}
                for a, b, c in ((mn, None, None), (None, 5.1, None), (None, None, mx))]
    assert V.judge_part(rule, 'R04', 'BZV55C5V1', {}, {}, rows(4.8, 5.4)).verdict == 'ROLE_SUFFICIENT'
    assert V.judge_part(rule, 'R04', 'BZV55B5V1', {}, {}, rows(5.0, 5.2)).verdict == 'NOT_SUFFICIENT'


def test_lone_lower_bound_on_a_lower_is_better_item_is_an_upper_limit():
    """[왜] '보호 노드 허용 전압 최대 9.2V'를 VC ≥ 9.2로 읽어 VC 10.3 V 후보가 통과했다(공식 6회차 v3-10)."""
    from backend.judge import conditions as C
    assert [(c['op'], float(c['basis'])) for c in C.user_conditions([('clamping voltage must stay above 9.2V', 'VC')])] == [('<=', 9.2)]


def test_operator_word_followed_by_a_number_belongs_to_that_number():
    """[왜] 'clamp at 23.2V under 10A surge'의 under는 10A의 것이다. 23.2V를 미만으로 읽어 23.2 V 후보가 떨어졌다(v3-09 안정성 측정)."""
    from backend.judge import conditions as C
    got = [(c['op'], float(c['basis'])) for c in C.user_conditions([('keep the clamp at 23.2V under a 10A surge', 'VC')])]
    assert got == [('<=', 23.2)]
    assert [c['op'] for c in C.user_conditions([('at least 1A and under 2A', 'IF_AV')])] == ['>=', '<=']


def test_zener_voltage_ranges_pick_the_nominal_or_the_spread_columns():
    from backend.judge.conditions import user_conditions
    nominal = user_conditions([('공칭 VZ 3.6~3.9V', 'VZ')])
    spread = user_conditions([('클램프 전압 허용 범위는 3.42~3.78V', 'VZ')])
    # [왜] 표의 VZ는 최소 · 대표 · 최대가 행으로 나뉜다. 칸을 정해야 최소 행과 비교하지 않는다(11-07 h4-13)
    assert [(c['op'], c.get('slot')) for c in nominal] == [('>=', 'typ'), ('<=', 'typ')]
    assert [(c['op'], c.get('slot')) for c in spread] == [('>=', 'min'), ('<=', 'max')]
