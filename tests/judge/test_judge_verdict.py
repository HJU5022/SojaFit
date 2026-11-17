"""판정(backend/judge/verdict.py) 시험: 작은 규칙 · 가짜 사양 표 행으로 판정 5종 순서와 찾기 · 정렬을 본다.

- 역할: AC-01(불충족) · AC-03(필수 빠짐 → 확인 안 됨) · AC-04(조건부 모름 → 불확실) · AC-05(시험 조건 다름) · AC-06(찾기 조건 · 정렬).
- 하지 않는 일: LLM · DB · MCP 호출, 실제 roles.yaml 검사.
- 출처: SPEC 3절, docs/specs/judge-agent.md AC
"""
import pytest
import yaml

from backend.judge import verdict as V

RATINGS = 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'
R01 = yaml.safe_load('''
name: 역극성 보호(직렬)
recognize: x
inputs: {v_in_max: number, i_max: number, v_drop_allowed: number, vf_test: condition}
conditions:
  - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_in_max * kV"}
  - {tier: required, code: IF_AV, op: ">=", basis: "i_max * kI"}
  - {tier: conditional, code: VF, op: "<=", basis: "v_drop_allowed", when: v_drop_allowed, at: vf_test}
major: {VRRM: higher, IF_AV: higher}
cautions: [발열]
source: x
''')
R03 = yaml.safe_load('''
name: 릴레이 플라이백
recognize: x
inputs: {v_coil: number, i_coil: number, pulse_test: condition, pwm: flag}
conditions:
  - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_coil * kV"}
  - {tier: required, code: IFSM, op: ">=", basis: "i_coil", at: pulse_test}
  - {tier: conditional, code: TRR, op: "<=", basis: "orig.TRR", when: pwm}
source: x
''')


def row(part, code, mx, cond=None, unit='V', table=RATINGS, mn=None):
    return {'part': part, 'code': code, 'min': mn, 'typ': None, 'max': mx, 'text': None, 'unit': unit,
            'source_value_text': str(mx), 'test_condition': cond,
            'citation': {'document': f'{part}.pdf', 'page': 1, 'table': table, 'row': code, 'chunk_index': 3}}


N5817 = [row('1N5817', 'VRRM', 20.0), row('1N5817', 'IF_AV', 1.0, unit='A'),
         row('1N5817', 'IFSM', 25.0, '8.3ms single half sine-wave superimposed on rated load', 'A'),
         row('1N5817', 'PACKAGE', None, unit=None) | {'text': 'DO-41'}]
TEMP = {'temp': {'TA': 25.0}}


def test_ac01_rating_below_threshold_is_not_sufficient():
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 20.0, 'i_max': 0.15}, TEMP, N5817)
    assert j.verdict == 'NOT_SUFFICIENT'
    vrrm = next(c for c in j.checks if c.code == 'VRRM')
    assert vrrm.result == 'fail' and vrrm.threshold == pytest.approx(25.0) and vrrm.value == 20.0
    assert vrrm.citation['document'] == '1N5817.pdf' and j.cautions == ['발열']


def test_passing_ratings_without_original_is_role_sufficient():
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 12.0, 'i_max': 0.15}, TEMP, N5817)
    assert j.verdict == 'ROLE_SUFFICIENT'  # 원래 부품을 모르면 사양 동등을 내지 않는다(EC-05)


def test_ac03_missing_required_value_is_not_verified_but_keeps_found_values():
    j = V.judge_part(R03, 'R03', '1N5817', {'v_coil': 12.0}, {**TEMP, 'pulse_test': {'pulse': 0.0083, 'wave': 'half_sine'}}, N5817)
    assert j.verdict == 'NOT_VERIFIED' and j.missing == ['i_coil']
    assert next(c for c in j.checks if c.code == 'VRRM').result == 'pass'  # 찾은 값은 그대로 남는다


def test_ac04_unknown_trigger_skips_condition_and_marks_uncertain():
    j = V.judge_part(R03, 'R03', '1N5817', {'v_coil': 12.0, 'i_coil': 0.08}, {**TEMP, 'pulse_test': {'pulse': 0.0083, 'wave': 'half_sine'}}, N5817)
    assert j.verdict == 'ROLE_SUFFICIENT'
    assert any('pwm' in u for u in j.uncertain) and all(c.code != 'TRR' for c in j.checks)


def test_ac05_different_pulse_is_unverified_not_guessed():
    j = V.judge_part(R03, 'R03', '1N5817', {'v_coil': 12.0, 'i_coil': 0.08, 'pwm': False}, {**TEMP, 'pulse_test': {'pulse': 0.001}}, N5817)
    ifsm = next(c for c in j.checks if c.code == 'IFSM')
    assert ifsm.result == 'unverified' and '시험 조건' in ifsm.why and j.verdict == 'NOT_VERIFIED'


def test_missing_temperature_is_uncertain_not_blocking():
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 12.0, 'i_max': 0.15}, {}, N5817)
    assert j.verdict == 'ROLE_SUFFICIENT' and any('온도' in u for u in j.uncertain)


def test_junction_temperature_question_cannot_use_ambient_ratings():
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 12.0, 'i_max': 0.15}, {'temp': {'TJ': 25.0}}, N5817)
    assert j.verdict == 'NOT_VERIFIED'  # 표는 TA=25°C 정격이고 질문은 TJ만 줬다


@pytest.mark.parametrize('temp', [{'TA': 85.0}, {'TJ': 25.0}])
def test_voltage_ratings_ignore_temperature_but_current_ratings_do_not(temp):
    """역전압 정격(VRRM)은 온도로 줄지 않아 표 기본 온도(TA=25°C) 값을 쓴다. 전류 정격(IF_AV)은 온도가 같아야 한다."""
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 12.0, 'i_max': 0.15}, {'temp': temp}, N5817)
    checks = {c.code: c.result for c in j.checks}
    assert checks == {'VRRM': 'pass', 'IF_AV': 'unverified'} and j.verdict == 'NOT_VERIFIED'


def test_spec_equivalent_needs_original_and_no_worse_major_ratings():
    orig = [row('1N5819', 'VRRM', 40.0), row('1N5819', 'IF_AV', 1.0, unit='A')]
    better = [row('SS14', 'VRRM', 40.0), row('SS14', 'IF_AV', 1.0, unit='A')]
    j = V.judge_part(R01, 'R01', 'SS14', {'v_in_max': 12.0, 'i_max': 0.5}, TEMP, better, original_rows=orig)
    assert j.verdict == 'SPEC_EQUIVALENT'
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 12.0, 'i_max': 0.5}, TEMP, N5817, original_rows=orig)
    assert j.verdict == 'ROLE_SUFFICIENT'  # VRRM 20 < 원래 40


CHAR = 'ELECTRICAL CHARACTERISTICS (TA = 25°C unless otherwise noted)'
VF_RULE = yaml.safe_load('''
name: x
recognize: x
inputs: {vf_test: condition}
conditions:
  - {tier: required, code: VF, op: "<=", basis: "orig.VF", at: vf_test}
source: x
''')
ORIG_VF = [row('1N5819', 'VF', 0.45, 'IF = 1A', table=CHAR), row('1N5819', 'VF', 0.80, 'IF = 3A', table=CHAR)]


def test_original_value_comes_from_the_same_test_condition():
    """orig.VF는 원래 부품의 첫 행(1 A, 0.45 V)이 아니라 후보 행과 시험 조건이 같은 행(3 A, 0.80 V)의 값이다."""
    cand = [row('SS14', 'VF', 0.50, 'IF = 1A', table=CHAR), row('SS14', 'VF', 0.75, 'IF = 3A', table=CHAR)]
    j = V.judge_part(VF_RULE, 'R08', 'SS14', {}, {**TEMP, 'vf_test': {'IF': 3.0}}, cand, original_rows=ORIG_VF)
    vf = j.checks[0]
    assert vf.result == 'pass' and vf.threshold == pytest.approx(0.80) and vf.value == pytest.approx(0.75)


def test_no_original_row_at_the_same_test_condition_is_unverified():
    cand = [row('SS14', 'VF', 0.75, 'IF = 3A', table=CHAR)]
    j = V.judge_part(VF_RULE, 'R08', 'SS14', {}, {**TEMP, 'vf_test': {'IF': 3.0}}, cand, original_rows=ORIG_VF[:1])
    assert j.checks[0].result == 'unverified' and j.checks[0].why == '원래 부품의 같은 시험 조건 값 없음'


def test_identical_comes_first():
    j = V.judge_part(R01, 'R01', '1N5817', {'v_in_max': 20.0, 'i_max': 0.15}, TEMP, N5817, identical=True)
    assert j.verdict == 'IDENTICAL'


def test_board_change_by_package_name():
    assert V.board_change('Diode_THT:D_DO-41_SOD81_P10.16mm', ['DO-41']) is False
    assert V.board_change('Diode_SMD:D_SOD-323', ['DO-41']) is True
    assert V.board_change(None, ['DO-41']) is None


def test_ac06_search_conditions_skip_test_condition_dependent_values():
    terms = V.search_conditions(R01, {'v_in_max': 12.0, 'i_max': 0.01, 'v_drop_allowed': 1.0})
    assert terms == [{'code': 'VRRM', 'gte': pytest.approx(15.0)}, {'code': 'IF_AV', 'gte': pytest.approx(0.0142857, rel=1e-5)}]


def test_r04_search_conditions_include_active_voltage_range():
    """사용자가 준 R04 VZ 범위는 conditional이어도 후보 검색의 기준이 된다."""
    from backend.judge import conditions as C
    rule = C.load()['R04']
    terms = V.search_conditions(rule, {'vz_min': 8.0, 'vz_max': 12.0, 'data_line': True})
    assert {'code': 'VZ', 'gte': 8.0, 'slot': 'min'} in terms
    assert {'code': 'VZ', 'lte': 12.0, 'slot': 'max'} in terms


def test_search_conditions_skip_inactive_or_original_conditional_values():
    rule = {'conditions': [
        {'tier': 'conditional', 'code': 'VZ', 'op': '>=', 'basis': 'lo', 'when': 'enabled'},
        {'tier': 'conditional', 'code': 'PD', 'op': '>=', 'basis': 'orig.PD', 'when': 'enabled'},
    ]}
    assert V.search_conditions(rule, {'lo': 8.0, 'enabled': False}) == []
    assert V.search_conditions(rule, {'lo': 8.0, 'enabled': True}) == [{'code': 'VZ', 'gte': 8.0}]


def test_rank_drops_not_sufficient_and_puts_no_board_change_first():
    def j(part, verdict, board):
        return V.Judgement(part=part, role='R01', verdict=verdict, board_change=board)
    shown, unverified = V.rank([j('B', 'ROLE_SUFFICIENT', True), j('A', 'ROLE_SUFFICIENT', False), j('C', 'NOT_SUFFICIENT', False),
                                j('D', 'SPEC_EQUIVALENT', True), j('E', 'NOT_VERIFIED', False)])
    assert [x.part for x in shown] == ['D', 'A', 'B'] and [x.part for x in unverified] == ['E']


def test_rank_puts_preferred_parts_first_only_within_the_same_verdict_and_board_change():
    def j(part, verdict, board):
        return V.Judgement(part=part, role='R01', verdict=verdict, board_change=board)
    found = [j('A', 'ROLE_SUFFICIENT', False), j('B', 'ROLE_SUFFICIENT', False), j('C', 'ROLE_SUFFICIENT', True),
             j('D', 'SPEC_EQUIVALENT', True), j('E', 'NOT_VERIFIED', False), j('F', 'NOT_VERIFIED', False)]
    before = V.rank(found)
    assert [x.part for x in before[0]] == ['D', 'A', 'B', 'C'] and V.rank(found, preferred=set()) == before  # 비면 예전 순서 그대로
    shown, unverified = V.rank(found, preferred={'B', 'C', 'F'})
    # [왜] 선호는 판정(D가 먼저) · 기판 수정 불필요(A · B가 C보다 먼저)를 넘지 않고, 같은 칸 안에서만 앞으로 온다. 확인 안 됨 순서는 그대로
    assert [x.part for x in shown] == ['D', 'B', 'A', 'C'] and [x.part for x in unverified] == [x.part for x in before[1]] == ['E', 'F']


def test_rank_limits_per_verdict_and_total():
    many = [V.Judgement(part=f'P{i}', role='R01', verdict='ROLE_SUFFICIENT') for i in range(6)]
    shown, _ = V.rank(many)
    assert len(shown) == 3


OR_RULE = yaml.safe_load('''
name: x
recognize: x
inputs: {v_in_max: number, i_coil: number, pulse_test: condition}
conditions:
  - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_in_max * kV"}
  - {tier: required, any: [{code: IFSM, op: ">=", basis: "i_coil", at: pulse_test}, {code: IF_AV, op: ">=", basis: "i_coil"}]}
source: x
''')
HALF_SINE = {'pulse_test': {'pulse': 0.0083, 'wave': 'half_sine'}}


def test_any_group_passes_when_one_member_passes_and_reports_that_member():
    j = V.judge_part(OR_RULE, 'R03', '1N5817', {'v_in_max': 12.0, 'i_coil': 0.08}, {**TEMP, 'pulse_test': {'pulse': 0.001}}, N5817)
    c = next(c for c in j.checks if c.code != 'VRRM')
    assert c.result == 'pass' and c.code == 'IF_AV' and c.basis == 'IFSM >= i_coil 또는 IF_AV >= i_coil'


def test_any_group_fails_only_when_every_member_is_computed_and_fails():
    j = V.judge_part(OR_RULE, 'R03', '1N5817', {'v_in_max': 12.0, 'i_coil': 30.0}, {**TEMP, **HALF_SINE}, N5817)
    assert [c.result for c in j.checks if c.code != 'VRRM'] == ['fail']
    j = V.judge_part(OR_RULE, 'R03', '1N5817', {'v_in_max': 12.0, 'i_coil': 30.0}, {**TEMP, 'pulse_test': {'pulse': 0.001}}, N5817)
    c = next(c for c in j.checks if c.code != 'VRRM')
    assert c.result == 'unverified' and j.missing == []  # IFSM은 펄스가 달라 확인 안 됨, IF_AV는 실패


def test_any_group_missing_values_are_the_union_when_no_member_is_computable():
    j = V.judge_part(OR_RULE, 'R03', '1N5817', {'v_in_max': 12.0}, TEMP, N5817)
    assert j.verdict == 'NOT_VERIFIED' and j.missing == ['i_coil', 'pulse_test']


def test_failed_any_group_reports_its_trr_member_for_the_schottky_exemption():
    """R10 "CJ 또는 TRR"이 통과가 아니면 TRR 멤버로 알린다. 판정 노드가 쇼트키 후보의 TRR을 면제하면 묶음이 통과가 된다."""
    rule = yaml.safe_load('''
name: x
recognize: x
conditions:
  - {tier: required, any: [{code: CJ, op: "<=", basis: "1e-12"}, {code: TRR, op: "<=", basis: "1e-9"}]}
source: x
''')
    rows = [row('BAT54', 'CJ', 1e-11, unit='F') | {'typ': 1e-11}, row('BAT54', 'TRR', 5e-9, unit='s')]
    c = V.judge_part(rule, 'R10', 'BAT54', {}, TEMP, rows).checks[0]
    assert c.result == 'fail' and c.code == 'TRR' and c.basis == 'CJ <= 1e-12 또는 TRR <= 1e-9'


def test_original_search_conditions_replace_missing_circuit_values_with_original_ratings():
    """회로 값이 없으면 값이 빠진 필수 조건의 기준을 원래 부품의 같은 코드 값으로 대신한다(11-17). 시험 조건(at) 조건은 그대로 뺀다."""
    orig = [row('1N4001', 'VRRM', 50.0), row('1N4001', 'IF_AV', 1.0, unit='A'), row('1N4001', 'VF', 1.1, 'IF = 1A', table=CHAR)]
    assert V.search_conditions(R01, {}) == []  # 값이 없으면 기존 찾기 조건은 빈다
    assert V.original_search_conditions(R01, {}, orig) == [{'code': 'VRRM', 'gte': 50.0}, {'code': 'IF_AV', 'gte': 1.0}]
    # 값을 받은 조건은 대신하지 않는다(그 조건은 search_conditions가 낸다)
    assert V.original_search_conditions(R01, {'v_in_max': 12.0}, orig) == [{'code': 'IF_AV', 'gte': 1.0}]
    # 원래 문서가 VRRM 대신 VR만 적었으면 그 값을 쓰되 찾기 코드는 첫 코드(VRRM)다
    assert V.original_search_conditions(R01, {}, [row('1N4148', 'VR', 75.0)]) == [{'code': 'VRRM', 'gte': 75.0}]
    assert V.original_search_conditions(R01, {}, []) == []  # 원래 부품 문서가 없으면 대신할 값이 없다


def test_original_search_conditions_skip_original_based_default_and_any_conditions():
    """원래 부품 값(orig.*) 기준 · 기본값(default)으로 물러나는 조건 · "A 또는 B"는 시험 조건이 같은 행끼리 판정에서 봐야 해 찾기에 쓰지 않는다."""
    rule = {'conditions': [
        {'tier': 'required', 'code': 'IR', 'op': '<=', 'basis': 'ir_allowed', 'default': 'orig.IR'},
        {'tier': 'required', 'code': 'TRR', 'op': '<=', 'basis': 'orig.TRR'},
        {'tier': 'required', 'any': [{'code': 'IF_AV', 'op': '>=', 'basis': 'i_coil'}]},
        {'tier': 'conditional', 'code': 'IFSM', 'op': '>=', 'basis': 'i_peak', 'when': 'i_peak'},
        {'tier': 'required', 'code': 'PD', 'op': '>=', 'basis': 'p_load'}]}
    orig = [row('X', c, 1.0) for c in ('IR', 'TRR', 'IF_AV', 'IFSM', 'PD')]
    assert V.original_search_conditions(rule, {}, orig) == [{'code': 'PD', 'gte': 1.0}]


def test_search_conditions_skip_any_groups():
    assert V.search_conditions(OR_RULE, {'v_in_max': 12.0, 'i_coil': 0.08}) == [{'code': 'VRRM', 'gte': pytest.approx(15.0)}]


def test_check_carries_the_condition_exempt_key():
    rule = yaml.safe_load('''
name: x
recognize: x
conditions:
  - {tier: required, code: TRR, op: "<=", basis: "75e-9"}
  - {tier: required, code: TRR, op: "<=", basis: "35e-9", exempt: sic}
source: x
''')
    assert [c.exempt for c in V.judge_part(rule, 'R14', '1N5817', {}, TEMP, N5817).checks] == ['schottky', 'sic']


def test_default_basis_reports_its_own_missing_values():
    """기본값 기준식(default)에도 쓸 회로 값이 없으면 그 값을 빠진 값으로 알린다(R17 처짐 기본값처럼 회로 값을 쓰는 기본값)."""
    rule = yaml.safe_load('''
name: x
recognize: x
inputs: {droop_allowed: number, v_peak: number, c_hold: number}
conditions:
  - {tier: required, code: IR, op: "<=", basis: "droop_allowed * c_hold", default: "0.01 * v_peak * c_hold"}
source: x
''')
    j = V.judge_part(rule, 'R17', '1N5817', {'v_peak': 1.0}, TEMP, N5817)
    assert j.verdict == 'NOT_VERIFIED' and j.missing == ['c_hold']


ZTABLE = 'ELECTRICAL PART NUMBER'  # [왜] 실제 제너 VZ 행의 표 이름. 청크를 나눌 때 "(TA = 25°C unless otherwise noted)"가 떨어졌다


def zener(part, vz_min, vz_typ, vz_max, cond='IZT = 5 mA'):
    """실제 사양 표처럼 VZ 최소 · 대표 · 최대가 한 행씩 따로인 제너 행(최소 행이 먼저)."""
    rows = [row(part, 'VZ', None, cond, table=ZTABLE, mn=vz_min), row(part, 'VZ', None, cond, table=ZTABLE) | {'typ': vz_typ},
            row(part, 'VZ', vz_max, cond, table=ZTABLE)]
    return rows + [row(part, 'PD', 0.5, unit='W')]


SLOTTED = yaml.safe_load('''
name: x
recognize: x
inputs: {lo: number, hi: number}
conditions:
  - {tier: required, code: VZ, op: ">=", basis: "lo", slot: min}
  - {tier: required, code: VZ, op: "<=", basis: "hi", slot: max}
source: x
''')


def test_slot_condition_reads_only_that_cell():
    """slot을 적은 조건은 그 칸 값만 본다(최소 4.85 ≥ 3.42 통과, 최대 5.36 ≤ 3.78 실패). 최소 행이 최대로 물러나 읽히지 않는다."""
    rows = zener('BZT52C5V1', 4.85, 5.1, 5.36)
    j = V.judge_part(SLOTTED, 'R04', 'BZT52C5V1', {'lo': 3.42, 'hi': 3.78}, {}, rows)
    assert [(c.result, c.value) for c in j.checks] == [('pass', 4.85), ('fail', 5.36)] and j.verdict == 'NOT_SUFFICIENT'
    top = {**SLOTTED, 'conditions': [{**SLOTTED['conditions'][0], 'slot': 'max'}]}  # 최대 VZ ≥ 5 V
    assert [(c.result, c.value) for c in V.judge_part(top, 'R04', 'BZT52C5V1', {'lo': 5.0}, {}, rows).checks] == [('pass', 5.36)]


def test_original_vz_is_the_maximum_vz():
    """orig.VZ는 원래 부품의 최대 VZ다(R04 규칙 주석). 최소 행이 표의 첫 행이어도 최대 칸 값을 쓴다."""
    assert V.first_values(zener('BZT52C3V6', 3.42, 3.6, 3.78))['VZ'] == 3.78
    assert V.first_values(N5817)['VRRM'] == 20.0  # 다른 코드는 그대로 첫 행


@pytest.mark.parametrize('temp,result', [({'TA': 25.0}, 'pass'), ({'TA': 85.0}, 'unverified'), ({'TJ': 25.0}, 'unverified')])
def test_vz_rows_without_table_condition_are_read_at_ta_25(temp, result):
    """표 제목에 조건이 없는 VZ 행은 TA = 25°C로 본다(온도를 적은 VZ 행은 모두 25°C, 11-06 실측). TJ로 물으면 여전히 모른다."""
    j = V.judge_part(SLOTTED, 'R04', 'BZT52C3V6', {'lo': 3.4, 'hi': 3.8}, {'temp': temp}, zener('BZT52C3V6', 3.42, 3.6, 3.78))
    assert {c.result for c in j.checks} == {result}


def test_room_temperature_is_read_like_unknown_temperature():
    """[왜] 주변 25°C를 준 질문이 온도를 안 준 질문보다 엄격하면 안 된다. 읽기가 'TA=25°C'를 적은 회차만 표 제목에 조건이 없는 행이
    '적혀 있지 않음'이 되어 판정이 회차마다 바뀌었다(11-06 일관성 측정). 다른 온도(85°C)는 그대로 엄격하다."""
    rows = [row('X', 'VRRM', 40.0, table=ZTABLE), row('X', 'IF_AV', 1.0, unit='A', table=ZTABLE)]
    for temp in (TEMP, {}):
        j = V.judge_part(R01, 'R01', 'X', {'v_in_max': 12.0, 'i_max': 0.15}, temp, rows)
        assert [(c.code, c.result) for c in j.checks] == [('VRRM', 'pass'), ('IF_AV', 'pass')]
    hot = V.judge_part(R01, 'R01', 'X', {'v_in_max': 12.0, 'i_max': 0.15}, {'temp': {'TA': 85.0}}, rows)
    assert [(c.code, c.result) for c in hot.checks] == [('VRRM', 'pass'), ('IF_AV', 'unverified')]


def test_unless_turns_off_on_any_given_value_like_when_turns_on():
    """unless는 when과 같이 '값이 있고 거짓이 아니면' 꺼진다. 숫자를 주면 꺼지고, 없거나 False면 남는다(플래그는 전과 같음)."""
    rule = {**SLOTTED, 'inputs': {'lo': 'number', 'hi': 'number', 'off': 'flag'},
            'conditions': [{'tier': 'required', 'code': 'PD', 'op': '>=', 'basis': '0.1', 'unless': 'lo'},
                           {'tier': 'required', 'code': 'PD', 'op': '>=', 'basis': '0.2', 'unless': 'off'}]}
    rows = zener('X', 1.0, 1.1, 1.2)

    def bases(values):
        return [c.basis for c in V.judge_part(rule, 'R04', 'X', values, {}, rows).checks]
    assert bases({'lo': 3.42, 'off': True}) == [] and bases({'off': False}) == ['0.1', '0.2'] and bases({}) == ['0.1', '0.2']
    assert V.search_conditions(rule, {'lo': 3.42}) == [{'code': 'PD', 'gte': 0.2}]


def test_tvs_compares_rated_values_when_both_sheets_use_same_waveform():
    # [왜] 사용자가 서지 파형을 말하지 않아도 두 문서가 같은 정격 파형(10/1000µs · tp = 1ms)이면 정격 VC끼리 비교한다(판정 기준표 R06)
    from backend.judge import conditions as C
    from backend.judge import verdict as V

    def row(part, code, mx, cond=None):
        return {'part': part, 'code': code, 'min': None, 'typ': None, 'max': mx, 'unit': 'V', 'test_condition': cond,
                'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL', 'row': part}}
    orig = [row('SMBJ14A', 'VRWM', 14.0), row('SMBJ14A', 'VC', 23.2, 'IPP = 27.0 A'), row('SMBJ14A', 'PPPM', 600.0, '10/1000µs waveform'),
            row('SMBJ14A', 'IPP', 27.0)]
    cand = [row('SMCJ14A', 'VRWM', 14.0), row('SMCJ14A', 'VC', 23.2, 'IPPM = 67 A'), row('SMCJ14A', 'PPPM', 1500.0, 'at TA = 25°C, tp = 1ms'),
            row('SMCJ14A', 'IPP', 67.0)]
    j = V.judge_part(C.load()['R06'], 'R06', 'SMCJ14A', {'v_line_max': 13.8}, {}, cand, original_rows=orig)
    assert [(c.code, c.result) for c in j.checks] == [('VRWM', 'pass'), ('VC', 'pass'), ('PPPM', 'pass')]
    assert j.verdict == 'SPEC_EQUIVALENT'  # 주요 정격(PPPM 1500 ≥ 600, VC 23.2 ≤ 23.2)도 같은 정격 파형 값끼리 비교한다(판정 dev 19)
    other = [r if r['code'] != 'PPPM' else {**r, 'test_condition': '8/20µs'} for r in cand]  # 파형이 다르면 확인 안 됨
    assert V.judge_part(C.load()['R06'], 'R06', 'X', {'v_line_max': 13.8}, {}, other, original_rows=orig).verdict == 'NOT_VERIFIED'


def test_user_surge_on_the_rated_waveform_is_compared_at_rated_values():
    # [왜] 사용자가 정격과 같은 파형의 서지(10A, 10/1000µs)를 말해도 데이터시트에는 정격 IPP 행만 있다. 서지 전류가 정격 IPP 이하면
    #      정격 VC끼리 비교한다(판정 기준표 R06, v3-09 SMBJ14AH). 다른 파형이나 정격을 넘는 서지는 그대로 확인 안 됨
    from backend.judge import conditions as C
    from backend.judge import verdict as V

    def row(part, code, mx, cond=None):
        return {'part': part, 'code': code, 'min': None, 'typ': None, 'max': mx, 'unit': 'V', 'test_condition': cond,
                'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL', 'row': part}}
    orig = [row('SMBJ14A', 'VRWM', 14.0), row('SMBJ14A', 'VC', 23.2, 'IPP = 27.0 A'), row('SMBJ14A', 'IPP', 27.0, '10/1000µs waveform'),
            row('SMBJ14A', 'PPPM', 600.0, '10/1000µs waveform')]
    cand = [{**r, 'part': 'SMBJ14AH'} for r in orig]

    def checks(surge):
        j = V.judge_part(C.load()['R06'], 'R06', 'SMBJ14AH', {'v_line_max': 13.0}, {'surge_test': surge}, cand, original_rows=orig)
        return {c.code: c.result for c in j.checks}
    assert checks({'IPP': 10.0, 'wave': '10/1000'}) == {'VRWM': 'pass', 'VC': 'pass', 'PPPM': 'pass'}
    assert checks({'IPP': 10.0, 'wave': '8/20'})['VC'] == 'unverified'   # 다른 파형
    assert checks({'IPP': 50.0, 'wave': '10/1000'})['VC'] == 'unverified'  # 정격 IPP(27A)를 넘는 서지


def test_ir_fail_at_higher_test_voltage_is_not_verified_and_room_temperature_row_is_used():
    # [왜] 사용 온도를 모르면 25°C 행을 쓰고, 실제 역전압보다 높은 시험 전압(정격 VR)의 누설 초과는 불충족을 단정하지 않는다(11-06 v3-07)
    from backend.judge import conditions as C
    from backend.judge import verdict as V

    def row(code, mx, cond=None):
        return {'part': 'SS16', 'code': code, 'min': None, 'typ': None, 'max': mx, 'unit': None, 'test_condition': cond,
                'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL', 'row': code}}
    rows = [row('VRRM', 60.0), row('IF_AV', 1.0), row('IR', 0.0002, '@ rated; TJ = 25°C'), row('IR', 0.005, '@ rated; TJ = 100°C')]
    rule = C.load()['R02']
    low = V.judge_part(rule, 'R02', 'SS16', {'i_max': 0.25, 'ir_allowed': 1e-4, 'v_reverse_max': 5.25}, {}, rows, original_rows=[])
    ir = [c for c in low.checks if c.code == 'IR'][0]
    assert ir.value == 0.0002 and ir.result == 'unverified'  # 25°C 행, 60 V > 5.25 V라 단정 못 함
    high = V.judge_part(rule, 'R02', 'SS16', {'i_max': 0.25, 'ir_allowed': 1e-4, 'v_reverse_max': 60.0}, {}, rows, original_rows=[])
    assert [c for c in high.checks if c.code == 'IR'][0].result == 'fail'


def test_conditional_check_without_an_original_value_is_left_out_not_unverified():
    """[왜] 외부 단자의 VESD를 원래 SMBJ14A 문서가 적지 않아 SMBJ14AH가 확인 안 됨이 됐다(11-06 v3-09). 빼고 사람이 확인할 것으로 남긴다."""
    from backend.judge import verdict as V
    rule = {'conditions': [{'tier': 'required', 'code': 'VRWM', 'op': '>=', 'basis': 'v_line_max'},
                           {'tier': 'conditional', 'code': 'VESD', 'op': '>=', 'basis': 'orig.VESD', 'when': 'external_port'}]}
    rows = [{'part': 'X', 'code': 'VRWM', 'min': None, 'typ': None, 'max': 14.0, 'unit': 'V', 'test_condition': None, 'citation': {}}]
    j = V.judge_part(rule, 'R06', 'X', {'v_line_max': 13.0, 'external_port': True}, {}, rows, original_rows=[{**rows[0], 'part': 'O'}])
    assert [c.code for c in j.checks] == ['VRWM'] and j.verdict != 'NOT_VERIFIED' and any('VESD' in u for u in j.uncertain)


def test_spec_equivalent_also_needs_same_condition_extra_ratings_not_worse():
    """[왜] 사람 판정(judge_dev README 해석 6)은 역할 major 밖의 같은 조건 정격(VWM · VBR · IR · PD …)도 본다. SMBJ14A → SMBJ13A는 VWM이 낮아
    역할상 충분이다(판정 dev 20). 같은 조건 짝이 없는 추가 항목은 건너뛴다."""
    from backend.judge import conditions as C
    from backend.judge import verdict as V

    def row(part, code, mx, cond=None, mn=None):
        return {'part': part, 'code': code, 'min': mn, 'typ': None, 'max': mx, 'unit': 'V', 'test_condition': cond,
                'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL', 'row': part}}
    orig = [row('SMBJ14A', 'VRWM', 14.0), row('SMBJ14A', 'VC', 23.2, 'IPP = 27.0 A'), row('SMBJ14A', 'PPPM', 600.0, '10/1000µs waveform'),
            row('SMBJ14A', 'IPP', 27.0), row('SMBJ14A', 'VBR', 17.2, 'IT = 1 mA', 15.6)]
    lower = [row('SMBJ13A', 'VRWM', 13.0), row('SMBJ13A', 'VC', 21.5, 'IPP = 29.0 A'), row('SMBJ13A', 'PPPM', 600.0, '10/1000µs waveform'),
             row('SMBJ13A', 'IPP', 29.0), row('SMBJ13A', 'VBR', 15.9, 'IT = 1 mA', 14.4)]
    rule = C.load()['R06']
    assert V.judge_part(rule, 'R06', 'SMBJ13A', {'v_line_max': 12.6}, {}, lower, original_rows=orig).verdict == 'ROLE_SUFFICIENT'
    same = [{**r, 'part': 'SMBJ14AH'} for r in orig]
    assert V.judge_part(rule, 'R06', 'SMBJ14AH', {'v_line_max': 12.6}, {}, same, original_rows=orig).verdict == 'SPEC_EQUIVALENT'
    split = orig[:-1] + [row('SMBJ14A', 'VBR', None, 'IT = 1 mA', 15.6), row('SMBJ14A', 'VBR', 17.2, 'IT = 1 mA')]  # 최소 · 최대가 다른 행
    split_same = [{**r, 'part': 'SMBJ14AH'} for r in split]
    assert V.judge_part(rule, 'R06', 'SMBJ14AH', {'v_line_max': 12.6}, {}, split_same, original_rows=split).verdict == 'SPEC_EQUIVALENT'


def test_user_vf_limit_is_checked_at_the_circuit_current():
    """[왜] '전압강하 1.8V까지'는 동작 전류(250mA)에서의 한계다. 표의 1A VF로 통과시키지 않고, 그 전류 행이 없으면 확인 안 됨(v3-04 정답)."""
    from backend.judge import conditions as C
    from backend.judge import verdict as V
    rule = {'conditions': C.user_conditions([('다이오드 전압강하는 1.8V까지 허용', 'VF')])}
    rows = [{'part': 'UF4007', 'code': 'VF', 'min': None, 'typ': None, 'max': 1.7, 'unit': 'V', 'test_condition': 'IF = 1A, TJ = 25°C', 'citation': {}}]
    assert V.judge_part(rule, 'R22', 'UF4007', {'i_max': 0.25}, {}, rows).checks[0].result == 'unverified'
    at_op = [{**rows[0], 'test_condition': 'IF = 0.25A, TJ = 25°C'}]
    assert V.judge_part(rule, 'R22', 'UF4007', {'i_max': 0.25}, {}, at_op).checks[0].result == 'pass'


def test_rated_vr_test_condition_compares_the_actual_rated_voltages():
    """[왜] '@ rated VR'은 품번마다 실제 전압이 다르다(SS34 40 V · SS36 60 V). 같은 조건으로 보고 IR을 비교했다(판정 dev 02: 확인 안 됨)."""
    from backend.judge import verdict as V

    def row(part, code, mx, cond=None):
        return {'part': part, 'code': code, 'min': None, 'typ': None, 'max': mx, 'unit': None, 'test_condition': cond,
                'citation': {'document': 'a.pdf', 'page': 2, 'table': 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)', 'row': part}}
    ss34 = [row('SS34', 'VRRM', 40.0), row('SS34', 'IR', 0.0005, '@ rated VR, TJ = 25°C')]
    ss36 = [row('SS36', 'VRRM', 60.0), row('SS36', 'IR', 0.0005, '@ rated VR, TJ = 25°C')]
    assert not V._same_condition(ss34[1], ss36[1], ss34, ss36)
    assert V._same_condition(ss34[1], {**ss34[1], 'part': 'X'}, ss34, ss34) and V._same_condition(ss34[1], ss36[1])


def test_missing_circuit_values_still_show_the_candidate_value_and_its_citation():
    j = V.judge_part(R01, 'R01', '1N5817', {}, {}, N5817, footprint='SOD-323', packages=['DO-41'])
    vrrm = next(c for c in j.checks if c.code == 'VRRM')
    # [왜] 기준(v_in_max)을 몰라도 후보 정격과 그 쪽을 보인다. 판정은 그대로 '확인 안 됨'이다(11-07 v2 draft30-h04)
    assert j.verdict == 'NOT_VERIFIED' and vrrm.result == 'unverified' and vrrm.value == 20.0 and vrrm.citation['document'] == '1N5817.pdf'
    assert j.board_change is True and j.package_citation['document'] == '1N5817.pdf'


def test_unverified_find_candidates_keep_found_order_with_fewest_unknown_checks_first():
    a = V.Judgement(part='B', role='R01', verdict='NOT_VERIFIED', checks=[V.Check(code='VRRM', tier='required', op='>=', basis='x', result='unverified')] * 2)
    b = V.Judgement(part='A', role='R01', verdict='NOT_VERIFIED', checks=[V.Check(code='VRRM', tier='required', op='>=', basis='x', result='unverified')])
    c = V.Judgement(part='C', role='R01', verdict='NOT_VERIFIED', checks=[V.Check(code='VRRM', tier='required', op='>=', basis='x', result='unverified')])
    shown, unverified = V.rank([a, c, b])
    assert shown == [] and [j.part for j in unverified] == ['C', 'A', 'B']  # 확인 안 된 조건 수 → 찾은 순서(이름순 아님)


R07 = yaml.safe_load('''
name: 병렬 역극성 보호
recognize: x
inputs: {v_in_max: number, i_short: number}
conditions:
  - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_in_max * kV"}
  - {tier: required, code: IFSM, op: ">=", basis: "i_short", default: "orig.IFSM"}
source: x
''')


def test_defaulted_condition_without_an_original_document_is_dropped_not_unverified():
    j = V.judge_part(R07, 'R07', '1N5817', {'v_in_max': 12.0}, {}, N5817, original_rows=[])
    # [왜] i_short가 없어 원래 IFSM으로 대신하려는데 원래 부품 문서도 없으면 비교 기준이 없다: 빼고 역할상 충분(11-07 c20-01)
    assert j.verdict == 'ROLE_SUFFICIENT' and [c.code for c in j.checks] == ['VRRM'] and any('원래 부품 문서에 값이 없어' in u for u in j.uncertain)


def test_orig_nominal_only_compares_nominal_to_nominal():
    # [왜] 원래 1N5231B 문서는 VZ 공칭 5.1 V만 적는다. 후보 MMSZ5231B의 최대 5.36 V와 비교해 같은 5.1 V 제너가 불충족이 났다(판정 dev 16, 11-09)
    from backend.judge import verdict as V
    cond = {'tier': 'required', 'code': 'VZ', 'op': '<=', 'basis': 'orig.VZ', 'slot': 'max'}
    cite = {'document': 'x.pdf', 'page': 2, 'table': 'ELECTRICAL SPECIFICATIONS'}
    orig = [{'code': 'VZ', 'min': None, 'typ': 5.1, 'max': None, 'test_condition': 'IZT = 20 mA', 'citation': cite}]
    cand = [{'code': 'VZ', 'min': 4.85, 'typ': None, 'max': None, 'test_condition': 'IZT = 20 mA', 'citation': cite},
            {'code': 'VZ', 'min': None, 'typ': 5.1, 'max': None, 'test_condition': 'IZT = 20 mA', 'citation': cite},
            {'code': 'VZ', 'min': None, 'typ': None, 'max': 5.36, 'test_condition': 'IZT = 20 mA', 'citation': cite}]
    check, _, _ = V._check(cond, {}, {}, cand, orig)
    assert check.result == 'pass' and check.value == 5.1
