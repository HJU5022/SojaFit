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


# ---- 11-05 PDF 대조(50개 품번)에서 나온 오류·누락을 고친 규칙. 실측 문서 이름은 각 테스트의 [왜]에 적는다 ----

def text(doc, idx, body, cat='tvs-18', page=1):
    """chunk.py가 만드는 표 밖 글 청크 모양."""
    return {'doc': doc, 'category': cat, 'idx': idx, 'kind': 'text', 'page': page, 'table': None, 'row': None,
            'text': f'[{doc} · {page}쪽] {body}'}


def values(rows, part, code):
    """(조건, 최소, 대표, 최대) 목록. 조건 글 순, 같은 조건이면 최소·대표·최대 칸 순."""
    out = [(r['test_condition'], r['minimum_value'], r['typical_value'], r['maximum_value']) for r in pick(rows, part, code)]
    return sorted(out, key=lambda t: (t[0] or '', [x is None for x in t[1:]], [x or 0 for x in t[1:]]))


TVS_ROW = [('Breakdown voltage VBR@IT (V) / Min', '56.7'), ('Breakdown voltage VBR@IT (V) / Max', '69.3'),
           ('Test current IT (mA)', '1'), ('Working stand-off voltage VWM (V)', '51')]


def test_bidirectional_part_takes_unidirectional_row_only_when_doc_says_so():
    # [왜] 실측(SMCJH SERIES_A2102.pdf, P4KE SERIES_N2104.pdf): C·CA 품번은 자기 행이 없고 1쪽 주석에
    # 'Electrical characteristics apply in both directions'가 있다. 주석이 없는 문서에서는 옮기지 않는다
    yes, no = 'SMCJH SERIES_A01.pdf', 'SMCJX SERIES_A01.pdf'
    rows, _ = run(
        cover(yes, ['SMCJ51H', 'SMCJ51CH'], 'tvs-18'),
        text(yes, 5, 'Notes 1. For bidirectional use CH or CAH suffix 2. Electrical characteristics apply in both directions'),
        row(yes, 60, 'Part number', 'SMCJ51H', [('Part number', 'SMCJ51H')] + TVS_ROW, 'tvs-18', 3),
        cover(no, ['SMCJ51X', 'SMCJ51CX'], 'tvs-18'),
        row(no, 60, 'Part number', 'SMCJ51X', [('Part number', 'SMCJ51X')] + TVS_ROW, 'tvs-18', 3),
    )
    assert values(rows, 'SMCJ51CH', 'VBR') == values(rows, 'SMCJ51H', 'VBR') == [
        ('IT = 1 mA', 56.7, None, None), ('IT = 1 mA', None, None, 69.3)]
    assert {r['row_label'] for r in pick(rows, 'SMCJ51CH', 'VRWM')} == {'SMCJ51H'}
    assert pick(rows, 'SMCJ51CH', 'VRWM')[0]['footnote_text'] == 'Electrical characteristics apply in both directions'
    assert pick(rows, 'SMCJ51CX', 'VBR') == []


def test_bidirectional_column_names_its_own_part():
    # [왜] 실측(SMDJH SERIES_B2104.pdf): 'Part number / Bi' 칸에 양방향 품번이 같은 행으로 적혀 있다(행 합침이 아니다)
    doc = 'SMDJH SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['SMDJ60AH', 'SMDJ60CAH'], 'tvs-18'),
        row(doc, 53, 'Part number', 'SMDJ60AH',
            [('Part number / Uni', 'SMDJ60AH'), ('Part number / Bi', 'SMDJ60CAH'), ('Marking code / Uni', 'PGK')]
            + TVS_ROW, 'tvs-18', 2),
    )
    assert values(rows, 'SMDJ60CAH', 'VRWM') == [(None, None, None, 51)]
    assert review == []


def test_condition_blocks_recovered_from_merged_condition_cells():
    # [왜] 실측(MBRF1545CT-Y SERIES_D2105.pdf): 같은 품번 묶음이 조건마다 되풀이되고, 조건 글은 묶음 가운데 한 행에만
    # 'IF = 7.5A,TJ =' + 값 칸의 '25°C'로 쪼개져 있다
    doc = 'MBRF1545CT-Y SERIES_A01.pdf'
    cat = 'schottky-rectifier-3'
    parts = ['MBRF1545CT-Y', 'MBRF1560CT-Y']

    def vf(idx, cell, typ, mx):
        return row(doc, idx, 'PARAMETER', 'Forward voltage per',
                   [('PARAMETER', 'Forward voltage per'), ('PARAMETER', cell), ('TYP', typ), ('MAX', mx), ('UNIT', 'V')],
                   cat, 2)
    rows, review = run(
        cover(doc, parts, cat),
        vf(26, 'MBRF1545CT-Y', '-', '0.84'), vf(27, 'IF = 15A,TJ = MBRF1560CT-Y', '25°C -', '0.95'),
        vf(28, 'MBRF1545CT-Y', '-', '0.57'), vf(29, 'IF = 7.5A,TJ = MBRF1560CT-Y', '125°C -', '0.65'),
    )
    assert values(rows, 'MBRF1545CT-Y', 'VF') == [('IF = 15A, TJ = 25°C', None, None, 0.84),
                                                  ('IF = 7.5A, TJ = 125°C', None, None, 0.57)]
    assert [r for r in review if r['reason'] == 'conflict'] == []


def test_one_cell_with_two_conditions_spans_two_blocks_in_order():
    # [왜] 실측(MBRS1035CT SERIES_M2103.pdf): 'IF = 10A, TJ = 25°C IF = 5A, TJ = 125°C'가 두 묶음 행 모두에 붙어 있다
    doc = 'MBRS1035CT SERIES_A01.pdf'
    cat = 'schottky-rectifier-3'

    def vf(idx, parts, cond, mx):
        return row(doc, idx, 'PARAMETER', 'Forward voltage per',
                   [('PARAMETER', 'Forward voltage per'), ('CONDITIONS', f'{cond} {parts}'.strip()), ('MAX', mx),
                    ('UNIT', 'V')], cat, 2)
    two = 'IF = 10A, TJ = 25°C IF = 5A, TJ = 125°C'
    rows, _ = run(
        cover(doc, ['MBRS1035CT', 'MBRS1050CT'], cat),
        vf(29, 'MBRS1035CT', '', '0.70'), vf(30, 'MBRS1050CT', 'IF = 5A, TJ = 25°C', '0.80'),
        vf(33, 'MBRS1035CT', two, '0.80'), vf(34, 'MBRS1050CT', two, '0.90'),
        vf(37, 'MBRS1035CT', two, '0.57'), vf(38, 'MBRS1050CT', two, '0.65'),
    )
    assert values(rows, 'MBRS1035CT', 'VF') == [('IF = 10A, TJ = 25°C', None, None, 0.8),
                                                ('IF = 5A, TJ = 125°C', None, None, 0.57),
                                                ('IF = 5A, TJ = 25°C', None, None, 0.7)]


def test_esd_air_and_contact_discharge_are_different_conditions():
    # [왜] 실측(TESDH3V3B02P4Q2_A2203.pdf): 'ESD according to IEC61000-4-2 air discharge' 15 kV와 contact 10 kV
    doc = 'TESDH3V3_A01.pdf'
    cat = 'esd-protection-19'
    esd = lambda idx, how, v: row(doc, idx, ABS, f'ESD according to IEC61000-4-2 {how} discharge', [  # noqa: E731
        (f'{ABS} / PARAMETER', f'ESD according to IEC61000-4-2 {how} discharge'), (f'{ABS} / SYMBOL', 'VESD'),
        (f'{ABS} / VALUE', v), (f'{ABS} / UNIT', 'kV')], cat, 2)
    rows, review = run(cover(doc, ['TESDH3V3'], cat), esd(16, 'air', '±15'), esd(17, 'contact', '±10'))
    assert sorted(r['maximum_value'] for r in pick(rows, 'TESDH3V3', 'VESD')) == [10000, 15000]
    assert review == []


def test_part_columns_with_title_prefix_and_family_pattern_columns():
    # [왜] 실측(GBU25JGA SERIES_A2507.pdf): 품번 열 이름 앞에 표 제목 조각이 붙었다('otherwise GBU25J GA').
    # KEY PARAMETERS의 계열 범위 '600 - 1000'은 검토로 가도, 품번 열 값이 표에 들어가야 한다
    doc = 'GBU25JGA SERIES_A01.pdf'
    cat = 'bridge-6'
    rows, _ = run(
        cover(doc, ['GBU25JGA', 'GBU25KGA'], cat),
        row(doc, 11, 'KEY PARAMETERS', 'VRRM', [('KEY PARAMETERS / PARAMETER', 'VRRM'),
                                                ('KEY PARAMETERS / VALUE', '600 - 1000'), ('KEY PARAMETERS / UNIT', 'V')], cat),
        row(doc, 18, 'ABSOLUTE MAXIMUM RATINGS (TA PARAMETER', 'Repetitive peak reverse voltage',
            [('ABSOLUTE MAXIMUM RATINGS (TA PARAMETER', 'Repetitive peak reverse voltage'),
             ('= 25°C unless SYMBOL', 'VRRM'), ('otherwise GBU25J GA', '600'), ('noted) GBU25K GA', '800'),
             ('UNIT', 'V')], cat),
    )
    assert values(rows, 'GBU25JGA', 'VRRM') == [(None, None, None, 600)]
    # [왜] 실측(GBPC15_25_35 SERIES_M2211.pdf): 'GBPC15, 25, 35 / 005' 열은 GBPC15005·GBPC25005·GBPC35005다
    doc = 'GBPC15_25_35 SERIES_A01.pdf'
    rows, _ = run(
        cover(doc, ['GBPC15005', 'GBPC25005', 'GBPC35005', 'GBPC1501'], cat),
        row(doc, 16, ABS, 'Repetitive peak reverse voltage',
            [(f'{ABS} / PARAMETER', 'Repetitive peak reverse voltage'), (f'{ABS} / SYMBOL', 'VRRM'),
             (f'{ABS} / GBPC15, 25, 35 / 005', '50'), (f'{ABS} / GBPC15, 25, 35 / 01', '100'), (f'{ABS} / UNIT', 'V')],
            cat),
    )
    assert [r['maximum_value'] for r in pick(rows, 'GBPC25005', 'VRRM')] == [50]
    assert [r['maximum_value'] for r in pick(rows, 'GBPC1501', 'VRRM')] == [100]
    # [주의] 실측(MBR3035PT SERIES_K2103.pdf): 'CONDITIONS MBR3035PT MBR3045PT'는 조건 열 머리다. 끝 낱말이 품번이어도 품번 열이 아니다
    doc = 'MBR3035PT SERIES_A01.pdf'
    E = 'ELECTRICAL SPECIFICATIONS'
    rows, _ = run(
        cover(doc, ['MBR3035PT', 'MBR3045PT', 'MBR3050PT'], 'schottky-rectifier-3'),
        row(doc, 45, E, 'Reverse current @ rated VR per diode (2)', [
            (f'{E} / PARAMETER', 'Reverse current @ rated VR per diode (2)'),
            (f'{E} / CONDITIONS MBR3035PT MBR3045PT', 'MBR3050PT'), ('열3', 'TJ = 25°C'), ('MAX', '1000'), ('UNIT', 'µA')],
            'schottky-rectifier-3', 2),
    )
    assert [r['part'] for r in rows] == ['MBR3050PT']


def test_zener_slots_from_glued_subheader_split_header_and_order_check():
    # [왜] 실측(BZY55B2V4 SERIES_D2301.pdf): Min·Nom·Max 머리 행이 첫 데이터 행 칸에 붙어 들어갔다('SPECIFICATIONS Min 2.35').
    # 같은 표의 다른 행은 같은 자리(열 순서)의 칸이라 그 자리 이름을 쓴다
    doc = 'BZY55B2V4 SERIES_A01.pdf'
    cat = 'zener-diode-35'
    vz = lambda a, b, c: [('ZENER VOLTAGE (1) / VZ @ IZT', a), ('ZENER VOLTAGE (1) / VZ @ IZT / V', b),  # noqa: E731
                          ('ZENER VOLTAGE (1) / VZ @ IZT', c), ('TEST CURRENT IZT mA', '5')]
    rows, review = run(
        cover(doc, ['BZY55B2V4', 'BZY55B6V8'], cat),
        row(doc, 22, 'PART NUMBER', 'ELECTRICAL BZY55B2V4', [('PART NUMBER', 'ELECTRICAL BZY55B2V4'), ('MARKING CODE', '2V4')]
            + vz('SPECIFICATIONS Min 2.35', 'Nom 2.40', '(TA = Max 2.45'), cat, 2),
        row(doc, 33, 'PART NUMBER', 'BZY55B6V8', [('PART NUMBER', 'BZY55B6V8'), ('MARKING CODE', '6V8')]
            + vz('6.66', '6.80', '6.94'), cat, 2),
    )
    assert values(rows, 'BZY55B6V8', 'VZ') == [('IZT = 5 mA', 6.66, None, None), ('IZT = 5 mA', None, 6.8, None),
                                               ('IZT = 5 mA', None, None, 6.94)]
    assert len(pick(rows, 'BZY55B2V4', 'VZ')) == 3 and review == []
    # [왜] 실측(1N4740A SERIES_O2104.pdf): 'RATINGS Zener voltage VZ @ IZT / V / Min' 뒤 칸 머리가 'AND / V / Nom'으로 잘렸다.
    # 1M130Z 행은 파서가 옆 행과 값을 바꿔(Nom 130 > Max 126) 최소 ≤ 대표 ≤ 최대가 어긋나므로 검토로 보낸다
    doc = '1N4740A SERIES_A01.pdf'
    zz = lambda p, cells: row(doc, 25, 'MAXIMUM Device (1)', p, [('MAXIMUM Device (1)', p)] + cells  # noqa: E731
                              + [('Test current / IZT / mA', '17.0')], cat, 2)
    rows, review = run(cover(doc, ['1N4744A', '1M130Z'], cat),
                       zz('1N4744A', [('RATINGS Zener voltage VZ @ IZT / V / Min', '14.25'), ('AND / V / Nom (2)(3)', '15'),
                                      ('ELECTRICAL / V / Max', '15.75')]),
                       # 실측: 1M130Z 행은 Min 칸이 없고 Nom 130·Max 126.00(옆 1M120Z의 최대)만 남았다
                       zz('1M130Z', [('AND / V / Nom (2)(3)', '130'), ('ELECTRICAL / V / Max', '126.00')]))
    assert values(rows, '1N4744A', 'VZ') == [('IZT = 17.0 mA', 14.25, None, None), ('IZT = 17.0 mA', None, 15, None),
                                             ('IZT = 17.0 mA', None, None, 15.75)]
    assert pick(rows, '1M130Z', 'VZ') == [] and {r['reason'] for r in review} == {'garbled_table'}
    # [왜] 'Zener Voltage / IZT / Min'의 IZT(시험 전류 기호)가 VZ 낱말을 막으면 안 된다
    assert specs.code_of('Zener Voltage / IZT / Min', strict=True)[0] == 'VZ'


def test_package_columns_go_to_parts_of_that_package():
    # [왜] 실측(TS4148 SERIES_A2301.pdf): 정격표 열은 패키지(0603·0805·1206)로 나뉘고, 주문표가 TS4148 RBG = 0805라 알려 준다.
    # 0603·1206 전용 VF 행은 RBG에 붙이면 안 된다
    doc = 'TS4148 SERIES_A01.pdf'
    cat = 'switching-diode-36'
    R = 'RATINGS (TA = 25°C unless otherwise noted)'
    E = ELEC
    pk = lambda idx, code, pkg: row(doc, idx, 'ORDERING INFORMATION', code, [  # noqa: E731
        ('ORDERING INFORMATION / ORDERING CODE', code), ('ORDERING INFORMATION / PACKAGE', pkg)], cat, 2)
    rows, review = run(
        cover(doc, ['TS4148 RAG', 'TS4148 RBG', 'TS4148 RCG'], cat),
        row(doc, 13, 'ABSOLUTE MAXIMUM', 'Package', [('ABSOLUTE MAXIMUM / PARAMETER', 'Package'),
            (f'{R} / TS4148', '0603 (Ceramics)'), (f'{R} / TS4148', '0805 (Ceramics)'), (f'{R} / TS4148', '1206 (Ceramics)')],
            cat),
        row(doc, 15, 'ABSOLUTE MAXIMUM', 'Forward current', [('ABSOLUTE MAXIMUM / PARAMETER', 'Forward current'),
            (f'{R} / SYMBOL', 'IF'), (f'{R} / TS4148', '100'), (f'{R} / TS4148', '150'), (f'{R} / TS4148', '150'),
            (f'{R} / UNIT', 'mA')], cat),
        row(doc, 21, E, 'Forward voltage', [(f'{E} / PARAMETER', 'Forward voltage'),
            (f'{E} / PARAMETER', '0603, 1206 (Ceramics)'), (f'{E} / CONDITIONS', 'IF = 10mA, TJ = 25°C'),
            (f'{E} / SYMBOL', 'VF'), (f'{E} / MAX', '1.00'), (f'{E} / UNIT', 'V')], cat, 2),
        row(doc, 22, E, 'Forward voltage', [(f'{E} / PARAMETER', 'Forward voltage'),
            (f'{E} / PARAMETER', '(1) 0805 (Ceramics)'), (f'{E} / CONDITIONS', 'IF = 100mA, TJ = 25°C'),
            (f'{E} / SYMBOL', 'VF'), (f'{E} / MAX', '1.00'), (f'{E} / UNIT', 'V')], cat, 2),
        pk(28, 'TS4148 RCG', '0603 (Ceramics)'), pk(29, 'TS4148 RBG', '0805 (Ceramics)'),
        pk(30, 'TS4148 RAG', '1206 (Ceramics)'),
    )
    assert values(rows, 'TS4148 RBG', 'IF_AV') == [(None, None, None, pytest.approx(0.15))]
    assert values(rows, 'TS4148 RCG', 'IF_AV') == [(None, None, None, pytest.approx(0.1))]
    assert values(rows, 'TS4148 RBG', 'VF') == [('IF = 100mA, TJ = 25°C', None, None, 1.0)]
    assert [r['test_condition'] for r in pick(rows, 'TS4148 RCG', 'VF')] == ['IF = 10mA, TJ = 25°C']


def test_continuation_rows_merged_group_cell_and_part_ranges():
    # [왜] 실측(SFS1601G SERIES_O2103.pdf): 둘째·셋째 묶음 행은 이름 없이 품번 칸과 TYP·MAX 칸만 있다(위 행을 이어받음)
    doc = 'SFS1601G SERIES_A01.pdf'
    cat = 'super-fast-recovery-15'
    parts = ['SFS1601G', 'SFS1602G', 'SFS1605G', 'SFS1606G']
    rows, _ = run(
        cover(doc, parts, cat),
        row(doc, 21, 'ELECTRICAL SPECIFICATIONS', 'Forward voltage per diode', [
            ('ELECTRICAL SPECIFICATIONS', 'Forward voltage per diode'), ('열2', '(1) SFS1601G SFS1602G'),
            ('CONDITIONS', 'IF = 8A, TJ = 25°C'), ('SYMBOL', 'VF'), ('TYP', '-'), ('MAX', '0.975'), ('UNIT', 'V')], cat, 2),
        row(doc, 22, 'ELECTRICAL SPECIFICATIONS', 'SFS1605G SFS1606G', [
            ('열2', 'SFS1605G SFS1606G'), ('TYP', '-'), ('MAX', '1.300'), ('UNIT', 'V')], cat, 2),
    )
    assert values(rows, 'SFS1606G', 'VF') == [('per diode; IF = 8A, TJ = 25°C', None, None, 1.3)]
    assert values(rows, 'SFS1601G', 'VF') == [('per diode; IF = 8A, TJ = 25°C', None, None, 0.975)]
    # 이어지는 행에 자기 조건 칸이 있으면 위 행 조건 대신 그것을 쓴다
    rows, _ = run(
        cover(doc, parts, cat),
        row(doc, 21, 'ELECTRICAL SPECIFICATIONS', 'Forward voltage per diode', [
            ('ELECTRICAL SPECIFICATIONS', 'Forward voltage per diode'), ('열2', 'SFS1601G SFS1602G SFS1605G SFS1606G'),
            ('CONDITIONS', 'IF = 8A, TJ = 25°C'), ('SYMBOL', 'VF'), ('MAX', '0.975'), ('UNIT', 'V')], cat, 2),
        row(doc, 22, 'ELECTRICAL SPECIFICATIONS', '-', [('열2', 'SFS1601G SFS1602G SFS1605G SFS1606G'),
            ('CONDITIONS', 'IF = 8A, TJ = 125°C'), ('MAX', '0.80'), ('UNIT', 'V')], cat, 2),
    )
    assert values(rows, 'SFS1606G', 'VF') == [('per diode; IF = 8A, TJ = 125°C', None, None, 0.8),
                                              ('per diode; IF = 8A, TJ = 25°C', None, None, 0.975)]
    # [왜] 실측(SFA1001G SERIES_K2103.pdf): 묶음 셋이 첫 행 한 칸에 합쳐지고 나머지 값은 이름 없는 행에 있다. 나눌 수 없어 검토로 보낸다
    doc = 'SFA1001G SERIES_A01.pdf'
    rows, review = run(
        cover(doc, ['SFA1001G', 'SFA1002G', 'SFA1005G'], cat),
        row(doc, 23, 'ELECTRICAL SPECIFICATIONS', 'Forward voltage (1)', [
            ('ELECTRICAL SPECIFICATIONS', 'Forward voltage (1)'),
            ('CONDITIONS', 'SFA1001G SFA1002G IF = 10A, TJ = 25°C SFA1005G'), ('SYMBOL', 'VF'), ('MAX', '0.975'),
            ('UNIT', 'V')], cat, 2),
        row(doc, 24, 'ELECTRICAL SPECIFICATIONS', '-', [('TYP', '-'), ('MAX', '1.300'), ('UNIT', 'V')], cat, 2),
    )
    assert pick(rows, 'SFA1005G', 'VF') == [] and {r['reason'] for r in review} == {'garbled_table'}
    # [왜] 실측(SFF10L04GA SERIES_E2108.pdf): 머리 행 조건 칸에 조건 둘이 합쳐져 있고, 이어지는 행이 품번 묶음을 되풀이한다.
    # 이어받은 조건도 묶음 나누기에 써서 첫 되풀이는 첫 조건, 둘째 되풀이는 둘째 조건을 받는다
    doc = 'SFF10L04GA SERIES_A01.pdf'
    cont = lambda idx, p, typ: row(doc, idx, 'PARAMETER', p, [('열2', p), ('TYP', typ), ('UNIT', 'V')], cat, 2)  # noqa: E731
    rows, review = run(
        cover(doc, ['SFF10L04GA', 'SFF10L05GA'], cat),
        row(doc, 27, 'PARAMETER', 'Forward voltage per', [('PARAMETER', 'Forward voltage per'), ('열2', 'SFF10L04GA'),
            ('CONDITIONS', 'IF = 5A, TJ = 25°C IF = 5A, TJ = 125°C'), ('SYMBOL', 'VF'), ('TYP', '0.94'), ('UNIT', 'V')],
            cat, 2),
        cont(28, 'SFF10L05GA', '1.04'), cont(31, 'SFF10L04GA', '0.82'), cont(32, 'SFF10L05GA', '0.98'),
    )
    assert values(rows, 'SFF10L04GA', 'VF') == [('IF = 5A, TJ = 125°C', None, 0.82, None),
                                                ('IF = 5A, TJ = 25°C', None, 0.94, None)]
    # 'SFA1001G - SFA1004G'·'SFA1001G~1004G' 범위는 안쪽 품번으로 펼치고 바깥 품번에는 붙이지 않는다
    doc = 'SFA1001G SERIES_A02.pdf'
    rows, _ = run(
        cover(doc, ['SFA1001G', 'SFA1003G', 'SFA1004G', 'SFA1005G'], cat),
        row(doc, 23, ELEC, 'Forward voltage', [(f'{ELEC} / PARAMETER', 'Forward voltage'),
            (f'{ELEC} / PARAMETER', 'SFA1001G~1004G'), (f'{ELEC} / CONDITIONS', 'IF = 10A'), (f'{ELEC} / SYMBOL', 'VF'),
            (f'{ELEC} / MAX', '0.975'), (f'{ELEC} / UNIT', 'V')], cat, 2),
    )
    assert sorted(r['part'] for r in pick(rows, 'SFA1003G', 'VF') + pick(rows, 'SFA1005G', 'VF')) == ['SFA1003G']


def test_part_name_and_condition_in_one_cell_and_vertical_part_cells():
    # [왜] 실측(BAT42W SERIES_H2606.pdf): 품번 칸이 세로로 합쳐져 가운데 행에만 'BAT42W IF = 50mA'가 있다.
    # 위아래 행(IF = 10mA·200mA)도 BAT42W 행이고, 품번을 뺀 'IF = 50mA'는 시험 조건이다
    doc = 'BAT42W SERIES_A01.pdf'
    cat = 'schottky-diode-37'
    vf = lambda idx, cond, v: row(doc, idx, ELEC, 'Forward voltage (1)', [  # noqa: E731
        (f'{ELEC} / PARAMETER', 'Forward voltage (1)'), (f'{ELEC} / CONDITIONS', cond), (f'{ELEC} / SYMBOL', 'VF'),
        (f'{ELEC} / MAX', v), (f'{ELEC} / UNIT', 'V')], cat, 2)
    rows, _ = run(cover(doc, ['BAT42W', 'BAT43W'], cat),
                  vf(28, 'IF = 10mA', '0.40'), vf(29, 'BAT42W IF = 50mA', '0.65'), vf(30, 'IF = 200mA', '1.00'),
                  vf(31, 'IF = 2mA', '0.33'), vf(32, 'BAT43W IF = 15mA', '0.45'), vf(33, 'IF = 200mA', '1.00'))
    assert values(rows, 'BAT42W', 'VF') == [('IF = 10mA', None, None, 0.4), ('IF = 200mA', None, None, 1.0),
                                            ('IF = 50mA', None, None, 0.65)]
    assert [r['test_condition'] for r in pick(rows, 'BAT43W', 'VF')].count('IF = 10mA') == 0


def test_ifsm_keeps_each_pulse_width_as_its_own_row():
    # [왜] 실측(S2DAL SERIES_B2103.pdf, MBRF1545CT-Y SERIES_D2105.pdf): 'Surge peak forward current' 행이 빠져
    # 1.0ms 값(140 A)이나 조건 없는 KEY PARAMETERS 값만 남았다. 펄스 폭마다 따로, 조건과 함께 넣는다
    doc = 'S2DAL SERIES_A01.pdf'
    cat = 'standard-rectifier-12'
    surge = lambda idx, label, t, v: row(doc, idx, ABS, label, [  # noqa: E731
        (f'{ABS} / PARAMETER', label), (f'{ABS} / PARAMETER', t), (f'{ABS} / SYMBOL', 'IFSM'), (f'{ABS} / S2GAL', v),
        (f'{ABS} / UNIT', 'A')], cat)
    rows, _ = run(
        cover(doc, ['S2GAL'], cat),
        row(doc, 10, 'KEY PARAMETERS', 'IFSM', [('KEY PARAMETERS / PARAMETER', 'IFSM'), ('KEY PARAMETERS / VALUE', '50'),
                                                ('KEY PARAMETERS / UNIT', 'A')], cat),
        surge(18, 'Surge peak forward current single half sine wave superimposed on', 't = 8.3ms', '50'),
        surge(19, 'rated load', 't = 1.0ms', '140'),
    )
    assert values(rows, 'S2GAL', 'IFSM') == [('t = 1.0ms', None, None, 140), ('t = 8.3ms', None, None, 50)]
    assert specs.code_of('Surge peak forward current, 8.3ms single half sine wave')[0] == 'IFSM'
    assert specs.code_of('Non-repetitive peak forward surge current', 'IFSM')[0] == 'IFSM'  # 실측: TS4148 SERIES
    assert specs.code_of('Repetitive peak forward surge current', 'IFRM') == (None, None)
    assert specs.code_of('Peak forward current', 'IFM') == (None, None), '반복 첨두 순방향 전류(IFM)는 평균 전류가 아니다'
