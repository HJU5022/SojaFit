"""실제 규칙 파일(backend/judge/rules/roles.yaml) 시험: 23개가 다 있고 모든 기준식 · 이름이 문법에 맞는지 본다.

- 역할: 규칙을 옮겨 적다 생긴 오타(없는 회로 값 이름, 없는 사양 코드, 문법 밖 기준식)를 막는다.
- 하지 않는 일: 규칙 내용이 공학적으로 맞는지(조장 판정 · 연습 문제로 본다).
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
    """R14: 100 kHz 초과면 trr ≤ 35 ns 또는 SiC 쇼트키만(보류 5개 규칙안 R14, 11-06). 75 ns 조건은 쇼트키 계열 모두 면제."""
    trr = {c['basis']: c.get('exempt', 'schottky') for c in C.load()['R14']['conditions'] if c.get('code') == 'TRR'}
    assert trr == {'75e-9': 'schottky', '35e-9': 'sic'}


def test_r13_uses_spike_margin_by_snubber_flag():
    """R13: 스너버가 있으면 ×1.25, 없거나 모르면 ×2(보류 5개 규칙안 R13, 11-06)."""
    r13 = C.load()['R13']
    bases = {c['basis'] for c in r13['conditions'] if c['code'] == 'VRRM' or c['code'] == ['VRRM']}
    assert '(v_out + v_in_max * ns_np) * kV' in bases and '(v_out + v_in_max * ns_np) * 2' in bases


def _zener(part, vz_min, vz_typ, vz_max):
    """실제 사양 표 모양의 제너 행(VZ 최소 · 대표 · 최대 따로, 표 제목에 조건 없음, PD는 정격 표)."""
    cite = {'document': f'{part}.pdf', 'page': 2, 'table': 'ELECTRICAL PART NUMBER', 'row': part, 'chunk_index': 1}
    vz = [{'part': part, 'code': 'VZ', 'min': a, 'typ': b, 'max': c, 'unit': 'V', 'test_condition': 'IZT = 5 mA', 'citation': cite}
          for a, b, c in ((vz_min, None, None), (None, vz_typ, None), (None, None, vz_max))]
    pd = {'part': part, 'code': 'PD', 'min': None, 'typ': None, 'max': 0.5, 'unit': 'W', 'test_condition': None,
          'citation': {**cite, 'page': 1, 'table': 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'}}
    return vz + [pd]


TA25 = {'temp': {'TA': 25.0}}


def test_r04_user_vz_range_judges_without_the_original_part():
    """R04: 질문의 VZ 범위(vz_min · vz_max)가 있으면 그 범위로 본다. 원래 부품을 몰라도 판정된다(평가 n04: 3.42~3.78 V에 BZT52C5V1은 불충족)."""
    from backend.judge import verdict as V
    r04 = C.load()['R04']
    assert {k: r04['inputs'][k] for k in ('vz_min', 'vz_max')} == {'vz_min': 'number', 'vz_max': 'number'}
    rng = {'vz_min': 3.42, 'vz_max': 3.78, 'i_z': 0.005}
    j = V.judge_part(r04, 'R04', 'BZT52C5V1', rng, TA25, _zener('BZT52C5V1', 4.85, 5.1, 5.36))
    assert j.verdict == 'NOT_SUFFICIENT'
    assert [(c.code, c.op, c.result, c.value) for c in j.checks if c.code == 'VZ'] == [('VZ', '>=', 'pass', 4.85), ('VZ', '<=', 'fail', 5.36)]
    ok = V.judge_part(r04, 'R04', 'BZT52C3V6', rng, TA25, _zener('BZT52C3V6', 3.42, 3.6, 3.78))
    assert ok.verdict == 'ROLE_SUFFICIENT'  # PD ≥ 5 mA × 3.78 V × kI도 vz_max로 계산
    assert C.needed(r04, set(rng) | {'data_line'}) == []


def test_r04_without_range_compares_the_maximum_vz_with_the_original():
    """R04: 범위가 없으면 후보 최대 VZ = 원래 최대 VZ(orig.VZ는 최대 VZ). 최소 행이 먼저여도 같은 부품끼리 통과한다."""
    from backend.judge import verdict as V
    r04 = C.load()['R04']
    orig = _zener('BZT52C3V6', 3.42, 3.6, 3.78)
    j = V.judge_part(r04, 'R04', 'MMSZ3V6', {'i_z': 0.005}, TA25, _zener('MMSZ3V6', 3.42, 3.6, 3.78), original_rows=orig)
    vz = [c for c in j.checks if c.code == 'VZ']
    assert [(c.result, c.threshold, c.value) for c in vz] == [('pass', 3.78, 3.78), ('pass', 3.78, 3.78)]
    assert j.verdict == 'SPEC_EQUIVALENT'
    other = V.judge_part(r04, 'R04', 'BZT52C5V1', {}, TA25, _zener('BZT52C5V1', 4.85, 5.1, 5.36), original_rows=orig)
    assert other.verdict == 'NOT_SUFFICIENT'
