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
