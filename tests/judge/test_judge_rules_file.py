"""실제 규칙 파일(backend/judge/rules/roles.yaml) 시험: 23개가 다 있고 모든 기준식 · 이름이 문법에 맞는지 본다.

- 역할: 규칙을 옮겨 적다 생긴 오타(없는 회로 값 이름, 없는 사양 코드, 문법 밖 기준식)를 막는다.
- 하지 않는 일: 규칙 내용이 공학적으로 맞는지(정운 판정 · 연습 문제로 본다).
- 출처: docs/specs/judge-agent.md "역할 23개", 저장소 밖 규칙 원본 3개 파일
"""
from backend.judge import conditions as C


def test_all_23_roles_load_and_validate():
    rules = C.load()
    assert tuple(sorted(rules)) == C.ROLES


def test_every_role_has_a_required_condition_and_a_source():
    for rid, rule in C.load().items():
        assert any(c['tier'] == 'required' for c in rule['conditions']), rid
        assert rule['source'].strip(), rid


def test_or_rules_are_any_groups_and_fallbacks_are_defaults():
    """원본의 "A 또는 B"는 any 묶음, "알면 A, 모르면 B"는 basis · default로 옮긴다(둘 다 필수로 두지 않는다)."""
    rules = C.load()

    def groups(rid):
        return [[m['code'] for m in c['any']] for c in rules[rid]['conditions'] if 'any' in c]

    def vrrm(rid):
        return [(c['basis'], c.get('default')) for c in rules[rid]['conditions'] if c.get('code') in ('VRRM', ['VRRM', 'VR'])]
    assert groups('R03') == [['IFSM', 'IF_AV']] and groups('R06') == [['PPPM', 'IPP']] and groups('R10') == [['CJ', 'TRR']]
    assert vrrm('R14') == [('(v_in_max + v_clamp) * 1.5', 'v_dss * 1.1')]
    assert vrrm('R15') == [('v_sw_transient', 'v_bus * kV')]


def test_r14_high_frequency_trr_exempts_only_sic_schottky():
    """R14: 100 kHz 초과면 trr ≤ 35 ns 또는 SiC 쇼트키만(보류 5개 규칙안, 정운 11-06). 75 ns 조건은 쇼트키 계열 모두 면제."""
    trr = {c['basis']: c.get('exempt', 'schottky') for c in C.load()['R14']['conditions'] if c.get('code') == 'TRR'}
    assert trr == {'75e-9': 'schottky', '35e-9': 'sic'}


def test_r13_uses_spike_margin_by_snubber_flag():
    """R13: 스너버가 있으면 ×1.25, 없거나 모르면 ×2(보류 5개 규칙안, 정운 11-06)."""
    r13 = C.load()['R13']
    bases = {c['basis'] for c in r13['conditions'] if c['code'] == 'VRRM' or c['code'] == ['VRRM']}
    assert '(v_out + v_in_max * ns_np) * kV' in bases and '(v_out + v_in_max * ns_np) * 2' in bases
