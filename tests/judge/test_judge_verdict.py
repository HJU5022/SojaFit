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


def test_rank_drops_not_sufficient_and_puts_no_board_change_first():
    def j(part, verdict, board):
        return V.Judgement(part=part, role='R01', verdict=verdict, board_change=board)
    shown, unverified = V.rank([j('B', 'ROLE_SUFFICIENT', True), j('A', 'ROLE_SUFFICIENT', False), j('C', 'NOT_SUFFICIENT', False),
                                j('D', 'SPEC_EQUIVALENT', True), j('E', 'NOT_VERIFIED', False)])
    assert [x.part for x in shown] == ['D', 'A', 'B'] and [x.part for x in unverified] == ['E']


def test_rank_limits_per_verdict_and_total():
    many = [V.Judgement(part=f'P{i}', role='R01', verdict='ROLE_SUFFICIENT') for i in range(6)]
    shown, _ = V.rank(many)
    assert len(shown) == 3


def test_worse_prefers_the_worse_verdict():
    assert V.worse('ROLE_SUFFICIENT', 'NOT_SUFFICIENT') == 'NOT_SUFFICIENT'
    assert V.worse('SPEC_EQUIVALENT', 'NOT_VERIFIED') == 'NOT_VERIFIED'


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
