"""부품 사양 표 변환(backend.rag.pipeline.specs) 계약: 코퍼스 파일 없이 작은 가짜 청크로 확인한다.

- 역할: 표 행 청크 모양별(정류 PARAMETER/SYMBOL/VALUE/UNIT, 품번 열, 일부 품번 전용 행, 제너 VZ 최소·대표·최대,
  TVS 품번 한 줄, ESD MIN/TYP/MAX) 변환과, 모호한 값을 표 대신 검토 목록으로 보내는 규칙
  (계열 범위, 충돌, 모르는 단위, 원문에 없는 숫자, 음수, 머리 밀림, 대상 불명), PPK·RMS 제외, 대조표 표본 수를 본다.
- 하지 않는 일: 실제 코퍼스(52,244청크) 실행과 채움률은 보지 않는다(작업 기록에 실측을 남긴다).
- 출처: db/schema/table-definition.md 5.7, 원형 전자_데이터시트/evidence/spec_table/README.md의 대조 오류 수정
"""
import json

import pytest

from backend.rag.pipeline import specs

ABS = 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'
ELEC = 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'


def cover(doc, parts, cat='standard-rectifier-12'):
    """chunk.py가 만드는 표지 청크 모양."""
    return {'doc': doc, 'category': cat, 'idx': 0, 'kind': 'cover', 'page': None, 'table': None, 'row': None,
            'text': f'[{doc}] 이 데이터시트의 품번: {", ".join(parts)}'}


def row(doc, idx, table, label, cells, cat='standard-rectifier-12', page=1):
    """chunk.py가 만드는 표 행 청크 모양: '[파일 · 쪽 · 표] 머리 경로: 값 | ...'."""
    body = ' | '.join(f'{h}: {v}' for h, v in cells)
    return {'doc': doc, 'category': cat, 'idx': idx, 'kind': 'table_row', 'page': page, 'table': table, 'row': label,
            'text': f'[{doc} · {page}쪽 · {table}] {body}'}


def run(*chunks):
    out = specs.build(list(chunks))
    return out['rows'], out['review']


def pick(rows, part, code):
    return [r for r in rows if r['part'] == part and r['parameter_code'] == code]


def reasons(review):
    return sorted(r['reason'] for r in review)


def test_rectifier_parameter_rows_and_part_columns():
    doc = 'S1A SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['S1A', 'S1B']),
        row(doc, 1, ABS, 'Repetitive peak reverse voltage',
            [(f'{ABS} / PARAMETER', 'Repetitive peak reverse voltage'), (f'{ABS} / SYMBOL', 'VRRM'),
             (f'{ABS} / S1A', '50'), (f'{ABS} / S1B', '100'), (f'{ABS} / UNIT', 'V')]),
        row(doc, 2, ABS, 'Average forward current',
            [(f'{ABS} / PARAMETER', 'Average forward current'), (f'{ABS} / SYMBOL', 'IF(AV)'),
             (f'{ABS} / VALUE', '1'), (f'{ABS} / UNIT', 'A')]),
    )
    assert [r['maximum_value'] for r in pick(rows, 'S1A', 'VRRM')] == [50]
    assert [r['maximum_value'] for r in pick(rows, 'S1B', 'VRRM')] == [100]
    r = pick(rows, 'S1B', 'IF_AV')[0]
    assert (r['maximum_value'], r['normalized_unit'], r['source_unit'], r['source_value_text']) == (1, 'A', 'A', '1 A')
    assert (r['page_number'], r['table_name'], r['row_label'], r['chunk']) == (1, ABS, 'Average forward current',
                                                                               {'doc': doc, 'idx': 2})
    assert r['checks'] == {'value_in_source': True, 'plausible': True}
    assert review == []


def test_row_applies_only_to_parts_named_in_parameter_cell():
    # [왜] 원형 1차 대조 오류 4건: 일부 품번 전용 VF 행을 문서의 모든 품번에 붙였다
    doc = 'MBR2545CT SERIES_A01.pdf'
    rows, _ = run(
        cover(doc, ['MBR2545CT', 'MBR2590CT']),
        row(doc, 1, ELEC, 'Forward voltage',
            [(f'{ELEC} / PARAMETER', 'Forward voltage'), (f'{ELEC} / PARAMETER', 'MBR2590CT'),
             (f'{ELEC} / CONDITIONS', 'IF = 12.5A, TJ = 25°C'), (f'{ELEC} / SYMBOL', 'VF'),
             (f'{ELEC} / MAX', '0.85'), (f'{ELEC} / UNIT', 'V')]),
    )
    assert [r['part'] for r in rows] == ['MBR2590CT']
    assert rows[0]['test_condition'] == 'IF = 12.5A, TJ = 25°C'


def test_zener_vz_min_nom_max_per_part_row():
    doc = 'BZX55C SERIES_A01.pdf'
    t = 'PART NUMBER'
    rows, review = run(
        cover(doc, ['BZX55C5V1', 'BZX55C5V6'], 'zener-diode-35'),
        row(doc, 5, t, 'BZX55C5V1',
            [('PART NUMBER', 'BZX55C5V1'), ('Zener voltage / VZ @ IZT / V / Min', '4.8'),
             ('Zener voltage / VZ @ IZT / V / Nom', '5.1'), ('Zener voltage / VZ @ IZT / V / Max', '5.4'),
             ('Test current IZT mA', '5')], 'zener-diode-35', page=2),
    )
    vz = pick(rows, 'BZX55C5V1', 'VZ')
    assert [(r['minimum_value'], r['typical_value'], r['maximum_value']) for r in vz] == [
        (4.8, None, None), (None, 5.1, None), (None, None, 5.4)]
    assert {r['test_condition'] for r in vz} == {'IZT = 5 mA'}
    assert specs.code_of('LEAKAGE CURRENT / VR V', strict=True) == (None, None), 'IR을 잰 전압 칸은 VR 정격이 아니다'
    assert not pick(rows, 'BZX55C5V6', 'VZ') and review == []


def test_tvs_one_row_per_part():
    doc = 'SMBJ SERIES_A01.pdf'
    t = 'ELECTRICAL SPECIFICATIONS'
    rows, review = run(
        cover(doc, ['SMBJ40A', 'SMBJ43A'], 'tvs-18'),
        row(doc, 81, t, 'SMBJ40A',
            [(t, 'SMBJ40A'), ('Marking code', 'MR'), ('Breakdown voltage VBR@IT (V) (Note 1) / Min', '44.4'),
             ('Breakdown voltage VBR@IT (V) (Note 1) / Max', '49.1'), ('Test current IT (mA)', '1'),
             ('Working stand-off voltage VWM (V)', '40'), ('Maximum peak impulse current IPP (A) (Note 2)', '9.7'),
             ('Maximum clamping voltage VC@IPP (V)', '64.5')], 'tvs-18', page=3),
    )
    vbr = pick(rows, 'SMBJ40A', 'VBR')
    assert [(r['minimum_value'], r['maximum_value']) for r in vbr] == [(44.4, None), (None, 49.1)]
    assert vbr[0]['test_condition'] == 'IT = 1 mA'
    assert [r['maximum_value'] for r in pick(rows, 'SMBJ40A', 'VRWM')] == [40]
    assert [r['maximum_value'] for r in pick(rows, 'SMBJ40A', 'IPP')] == [9.7]
    vc = pick(rows, 'SMBJ40A', 'VC')
    assert [r['maximum_value'] for r in vc] == [64.5] and vc[0]['test_condition'] == 'IPP = 9.7 A'
    assert not pick(rows, 'SMBJ40A', 'VR'), 'VWM은 VR이 아니라 VRWM으로 나눈다'
    assert not pick(rows, 'SMBJ43A', 'VBR') and review == []


def test_esd_min_typ_max_rows_with_conditions():
    doc = 'TESD5V0_A01.pdf'
    cat = 'esd-protection-19'
    rows, review = run(
        cover(doc, ['TESD5V0'], cat),
        row(doc, 20, ELEC, 'Reverse breakdown voltage',
            [(f'{ELEC} / PARAMETER', 'Reverse breakdown voltage (1)'), (f'{ELEC} / CONDITIONS', 'IR = 1 mA'),
             (f'{ELEC} / SYMBOL', 'V(BR)'), (f'{ELEC} / MIN', '6'), (f'{ELEC} / TYP', '-'), (f'{ELEC} / MAX', '-'),
             (f'{ELEC} / UNIT', 'V')], cat, page=2),
        row(doc, 21, ELEC, 'Junction capacitance',
            [(f'{ELEC} / PARAMETER', 'Junction capacitance'), (f'{ELEC} / CONDITIONS', 'VR = 0V, f = 1MHz'),
             (f'{ELEC} / SYMBOL', 'CJ'), (f'{ELEC} / MIN', '-'), (f'{ELEC} / TYP', '0.3'), (f'{ELEC} / MAX', '0.5'),
             (f'{ELEC} / UNIT', 'pF')], cat, page=2),
        row(doc, 14, ABS, 'ESD per IEC 61000-4-2 (Contact)',
            [(f'{ABS} / PARAMETER', 'ESD per IEC 61000-4-2 (Contact)'), (f'{ABS} / SYMBOL VALUE', '± 8'),
             (f'{ABS} / UNIT', 'KV')], cat),
        row(doc, 15, ABS, 'ESD per IEC 61000-4-2 (Air)',
            [(f'{ABS} / PARAMETER', 'ESD per IEC 61000-4-2 (Air)'), (f'{ABS} / SYMBOL VALUE', '± 15'),
             (f'{ABS} / UNIT', 'KV')], cat),
    )
    vbr = pick(rows, 'TESD5V0', 'VBR')
    assert [(r['minimum_value'], r['test_condition']) for r in vbr] == [(6, 'IR = 1 mA')]
    cj = pick(rows, 'TESD5V0', 'CJ')
    assert [r['typical_value'] or r['maximum_value'] for r in cj] == pytest.approx([0.3e-12, 0.5e-12])
    assert {r['normalized_unit'] for r in cj} == {'F'}
    # [왜] 접촉·공기 방전은 시험 조건이 달라 충돌이 아니다
    assert sorted(r['maximum_value'] for r in pick(rows, 'TESD5V0', 'VESD')) == [8000, 15000]
    assert review == []


def test_series_range_split_when_named_parts_match_count():
    doc = 'MBR2035CT SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['MBR2035CT', 'MBR2045CT', 'MBR2060CT']),
        row(doc, 1, ABS, 'Repetitive peak reverse voltage',
            [(f'{ABS} / PARAMETER', 'Repetitive peak reverse voltage'), (f'{ABS} / PARAMETER', 'MBR2035CT MBR2045CT'),
             (f'{ABS} / SYMBOL', 'VRRM'), (f'{ABS} / VALUE', '35 - 45'), (f'{ABS} / UNIT', 'V')]),
        row(doc, 2, ELEC, 'Forward voltage',
            [(f'{ELEC} / PARAMETER', 'Forward voltage'), (f'{ELEC} / PARAMETER', 'MBR2035CT MBR2045CT'),
             (f'{ELEC} / SYMBOL', 'VF'), (f'{ELEC} / MAX', '0.84 0.95'), (f'{ELEC} / UNIT', 'V')]),
    )
    assert [r['maximum_value'] for r in pick(rows, 'MBR2035CT', 'VRRM')] == [35]
    assert [r['maximum_value'] for r in pick(rows, 'MBR2045CT', 'VRRM')] == [45]
    assert [r['source_value_text'] for r in pick(rows, 'MBR2045CT', 'VF')] == ['0.95 V']
    assert not pick(rows, 'MBR2060CT', 'VRRM') and review == []


def test_series_range_unsplittable_goes_to_review():
    doc = 'S1A SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['S1A', 'S1B', 'S1D']),
        row(doc, 9, 'KEY PARAMETERS', 'VRRM',
            [('KEY PARAMETERS / PARAMETER', 'VRRM'), ('KEY PARAMETERS / VALUE', '50 - 600'),
             ('KEY PARAMETERS / UNIT', 'V')]),
    )
    assert rows == []
    assert reasons(review) == ['range_unsplittable']
    assert review[0]['parts'] == ['S1A', 'S1B', 'S1D'] and review[0]['chunks'] == [{'doc': doc, 'idx': 9}]


def test_conflict_same_slot_same_condition_excludes_both():
    doc = '1N4148 SERIES_A01.pdf'
    cells = lambda v: [(f'{ABS} / PARAMETER', 'Forward current'), (f'{ABS} / SYMBOL', 'IF'),  # noqa: E731
                       (f'{ABS} / 1N4148', v), (f'{ABS} / UNIT', 'mA')]
    rows, review = run(
        cover(doc, ['1N4148'], 'switching-diode-36'),
        row(doc, 18, ABS, 'Forward current', cells('150'), 'switching-diode-36'),
        row(doc, 19, ABS, 'Forward current', cells('450'), 'switching-diode-36'),
    )
    assert pick(rows, '1N4148', 'IF_AV') == []
    assert reasons(review) == ['conflict']
    assert review[0]['parts'] == ['1N4148'] and len(review[0]['chunks']) == 2


def test_different_conditions_are_kept():
    doc = '1N4148 SERIES_A01.pdf'
    cells = lambda cond, v: [(f'{ELEC} / PARAMETER', 'Forward voltage'), (f'{ELEC} / CONDITIONS', cond),  # noqa: E731
                             (f'{ELEC} / SYMBOL', 'VF'), (f'{ELEC} / MAX', v), (f'{ELEC} / UNIT', 'V')]
    rows, review = run(
        cover(doc, ['1N4148'], 'switching-diode-36'),
        row(doc, 24, ELEC, 'Forward voltage', cells('IF = 10mA', '0.72'), 'switching-diode-36', page=2),
        row(doc, 25, ELEC, 'Forward voltage', cells('IF = 100mA', '1'), 'switching-diode-36', page=2),
    )
    vf = pick(rows, '1N4148', 'VF')
    assert sorted((r['test_condition'], r['maximum_value']) for r in vf) == [('IF = 100mA', 1), ('IF = 10mA', 0.72)]
    assert review == []


def test_unknown_unit_for_current_goes_to_review():
    doc = 'S1A SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['S1A']),
        row(doc, 3, ABS, 'Peak forward surge current',
            [(f'{ABS} / PARAMETER', 'Peak forward surge current'), (f'{ABS} / SYMBOL', 'IFSM'),
             (f'{ABS} / VALUE', '30')]),
    )
    assert rows == [] and reasons(review) == ['unknown_unit']


def test_value_not_in_source_and_implausible_checks():
    text = '[a.pdf · 1쪽 · T] T / PARAMETER: Forward voltage | T / MAX: 0.85 | T / UNIT: V'
    assert specs.auto_checks(['0.85'], {'maximum_value': 0.85}, 'VF', text) == {
        'value_in_source': True, 'plausible': True}
    assert specs.auto_checks(['0.95'], {'maximum_value': 0.95}, 'VF', text)['value_in_source'] is False
    assert specs.auto_checks(['-55', '+150'], {'minimum_value': -55, 'maximum_value': 150}, 'TJ_MAX',
                             '[a · 1쪽 · T] T / VALUE: - 55 to +150')['plausible'] is True
    doc = 'S1A SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['S1A']),
        row(doc, 4, ABS, 'Reverse voltage',
            [(f'{ABS} / PARAMETER', 'DC blocking voltage'), (f'{ABS} / SYMBOL', 'VDC'), (f'{ABS} / VALUE', '-50'),
             (f'{ABS} / UNIT', 'V')]),
    )
    assert rows == [] and reasons(review) == ['implausible']


def test_peak_pulse_power_is_never_pd_and_rms_is_excluded():
    doc = 'SMAJ SERIES_A01.pdf'
    cat = 'tvs-18'
    rows, _ = run(
        cover(doc, ['SMAJ5.0A'], cat),
        row(doc, 10, ABS, 'Peak pulse power dissipation',
            [(f'{ABS} / PARAMETER', 'Peak pulse power dissipation (Note 1)'), (f'{ABS} / SYMBOL', 'PPK'),
             (f'{ABS} / VALUE', '400'), (f'{ABS} / UNIT', 'W')], cat),
        row(doc, 11, 'KEY PARAMETERS', 'PPPSM',
            [('KEY PARAMETERS / PARAMETER', 'PPPSM'), ('KEY PARAMETERS / VALUE', '400'),
             ('KEY PARAMETERS / UNIT', 'W')], cat),
        row(doc, 12, ABS, 'Maximum RMS voltage',
            [(f'{ABS} / PARAMETER', 'Maximum RMS voltage'), (f'{ABS} / SYMBOL', 'VRMS'),
             (f'{ABS} / VALUE', '35'), (f'{ABS} / UNIT', 'V')], cat),
        row(doc, 13, ABS, 'Reverse voltage, total rms value',
            [(f'{ABS} / PARAMETER', 'Reverse voltage, total rms value'), (f'{ABS} / SYMBOL', 'VR(RMS)'),
             (f'{ABS} / VALUE', '35'), (f'{ABS} / UNIT', 'V')], cat),
    )
    assert pick(rows, 'SMAJ5.0A', 'PD') == []
    assert [r['maximum_value'] for r in pick(rows, 'SMAJ5.0A', 'PPPM')] == [400]
    assert {r['parameter_code'] for r in rows} == {'PPPM'}, '실효값(RMS)은 VR이 아니다'


def test_shifted_header_and_unnamed_subset_go_to_review():
    doc = '5KSMC SERIES_A01.pdf'
    cat = 'tvs-18'
    rows, review = run(
        cover(doc, ['5KSMC10AH', '5KSMC16AH'], cat),
        # [왜] 첫 데이터 행이 머리로 올라가 머리 끝에 숫자가 붙은 표(5KSMC10(C)AH SERIES_B2509.pdf)
        row(doc, 33, 'ELECTRICAL Part number', '5KSMC16AH',
            [('ELECTRICAL Part number / 5KSMC10AH', '5KSMC16AH'), ('SPECIFICATIONS IR max / µA / 5', '1')], cat, 2),
        row(doc, 14, ABS, 'Forward voltage',
            [(f'{ABS} / PARAMETER', 'Forward Voltage @ IF = 50A for Uni-directional only'),
             (f'{ABS} / SYMBOL', 'VF'), (f'{ABS} / VALUE', '3.5'), (f'{ABS} / UNIT', 'V')], cat),
    )
    assert rows == []
    assert reasons(review) == ['garbled_table', 'scope_unclear']


def test_merged_part_rows_and_unlabelled_breakdown_go_to_review():
    doc = 'SMBJ SERIES_A01.pdf'
    cat = 'tvs-18'
    t = 'ELECTRICAL SPECIFICATIONS'
    rows, review = run(
        cover(doc, ['SMBJ110', 'SMBJ110A', 'SMBJ120A'], cat),
        # [왜] 실측(SMBJ SERIES_R2104.pdf): 파서가 두 품번 행을 합쳐 'Min: 111 122'의 111이 다른 행 값이었다. 수가 맞아도 나누지 않는다
        row(doc, 110, t, 'SMBJ110 SMBJ110A',
            [(t, 'SMBJ110 SMBJ110A'), ('Breakdown voltage VBR@IT (V) (Note 1) / Min', '111 122')], cat, 3),
        # [왜] 실측(1.5KE SERIES_O2104.pdf): 'Min' 표시가 잘린 VBR 칸. 대표값으로 짐작하지 않는다
        row(doc, 111, t, 'SMBJ120A', [(t, 'SMBJ120A'), ('SPECIFICATIONS Breakdown voltage VBR@IT (V) (Note', '133')],
            cat, 3),
    )
    assert rows == []
    assert reasons(review) == ['garbled_table', 'slot_unclear']


def test_one_part_row_with_merged_cell_is_shifted_and_reviewed():
    # [왜] 실측(1.5SMC SERIES): 'VWM (V): 12.1 1'처럼 칸이 합쳐지면 뒤 칸 값이 밀려 IR 칸에 IPPM 값 71이 들어갔다
    doc = '1.5SMCH SERIES_A01.pdf'
    cat = 'tvs-18'
    rows, review = run(
        cover(doc, ['1.5SMC15H'], cat),
        row(doc, 70, 'Part number', '1.5SMC15H',
            [('Part number', '1.5SMC15H'), ('Working stand-off voltage VWM (V)', '12.1 1'),
             ('Maximum blocking leakage current IR@VWM (µA)', '71')], cat, 3),
    )
    assert rows == []
    assert reasons(review) == ['garbled_table', 'garbled_table']


def test_condition_keeps_symbol_and_at_style_header():
    assert specs.label_condition('IF = 10mA, TJ = 25°C') == 'IF = 10mA, TJ = 25°C'
    assert specs.label_condition('VF at IF = 100mA') == 'at IF = 100mA'
    F = specs.fields('[a · 2쪽 · T] Maximum peak impulse current IPPM (A): 95.1 | '
                     'Maximum clamping voltage VC at IPPM (V): 69.4')
    assert specs.at_condition('Maximum clamping voltage VC at IPPM (V)', F) == 'IPPM = 95.1 A'
    assert specs.at_condition('Maximum blocking leakage current IR at VWM TJ =175°C (µA)', F) == '@VWM; TJ =175°C'


def test_part_group_found_in_conditions_cell():
    doc = 'SK52BH SERIES_A01.pdf'
    cat = 'schottky-rectifier-3'
    rows, _ = run(
        cover(doc, ['SK52BH', 'SK56BH'], cat),
        row(doc, 36, 'ELECTRICAL SPECIFICATIONS', 'Reverse current @ rated',
            [('ELECTRICAL SPECIFICATIONS', 'Reverse current @ rated'), ('CONDITIONS', 'SK52BH'), ('SYMBOL TYP', '-'),
             ('MAX', '500'), ('UNIT', 'µA')], cat, 2),
    )
    assert [(r['part'], r['maximum_value']) for r in rows] == [('SK52BH', pytest.approx(500e-6))]


def test_packages_are_doc_level():
    doc = 'S1A SERIES_A01.pdf'
    out = specs.build([
        cover(doc, ['S1A', 'S1B']),
        {'doc': doc, 'category': 'standard-rectifier-12', 'idx': 5, 'kind': 'text', 'page': 1, 'table': None,
         'row': None, 'text': f'[{doc} · 1쪽] Case: SMA (DO-214AC), molded plastic'},
        row(doc, 6, 'KEY PARAMETERS', 'Package',
            [('KEY PARAMETERS / PARAMETER', 'Package'), ('KEY PARAMETERS / VALUE', 'SMA'),
             ('KEY PARAMETERS / UNIT', 'SMA')]),
    ])
    assert [(p['part'], p['packages']) for p in out['packages']] == [('S1A', ['SMA', 'DO-214AC']),
                                                                      ('S1B', ['SMA', 'DO-214AC'])]


def test_allocate_floor_cap_and_total():
    counts = {f'f{i:02d}': c for i, c in enumerate([3000, 900, 600, 500, 400, 300, 200, 150, 150, 100, 60, 40, 30])}
    alloc = specs.allocate(counts, 50)
    assert sum(alloc.values()) == 50
    assert all(3 <= k <= 5 for k in alloc.values())
    assert alloc['f00'] == 5 and alloc['f12'] == 3


def test_build_and_sample_cli(tmp_path):
    doc = 'SMBJ SERIES_A01.pdf'
    t = 'ELECTRICAL SPECIFICATIONS'
    chunks = [cover(doc, ['SMBJ40A'], 'tvs-18'),
              row(doc, 81, t, 'SMBJ40A', [(t, 'SMBJ40A'), ('Working stand-off voltage VWM (V)', '40')], 'tvs-18', 3)]
    src = tmp_path / 'chunks.jsonl'
    src.write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in chunks), encoding='utf-8')
    out = tmp_path / 'specs'
    specs.main(['build', str(src), str(out)])
    assert {p.name for p in out.iterdir()} == {'part_specifications.jsonl', 'review.jsonl', 'packages.jsonl',
                                                'summary.json'}
    summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
    assert summary['coverage']['tvs']['VRWM'] == {'parts_with_value': 1, 'parts': 1}
    sheet = tmp_path / 'sheet.md'
    specs.main(['sample', str(out), str(sheet), '--n', '50', '--seed', '0'])
    text = sheet.read_text(encoding='utf-8')
    assert 'SMBJ40A' in text and 'corpus/tsc/pdf/SMBJ SERIES_A01.pdf' in text and 'O/X' in text
    assert 'VBR' in text  # [왜] 빠진 핵심 값도 사람이 보게 적는다
