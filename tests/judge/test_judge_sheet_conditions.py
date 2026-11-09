"""시험 조건 읽기(backend/judge/sheet_conditions.py) 시험: 사양 표에 실제로 있는 조건 글로 확인한다.

- 역할: 기호 = 값, 펄스 폭 · 파형, "rated VR", 표 제목 기본 조건을 읽고, 같은 조건만 'same'인지 본다.
- 하지 않는 일: 값 비교 · 판정(test_judge_verdict.py).
- 출처: docs/specs/judge-agent.md EC-06 · AC-05
"""
import pytest

from backend.judge.sheet_conditions import compare, parse


@pytest.mark.parametrize('text, want', [
    ('IF = 1A, TJ = 25°C', {'IF': 1.0, 'TJ': 25.0}),
    ('IF = 1.0A, TJ = 25°C', {'IF': 1.0, 'TJ': 25.0}),
    ('@ rated VR; TJ = 125°C', {'VR': 'rated', 'TJ': 125.0}),
    ('IZT = 5 mA', {'IZ': 0.005}),
    ('8.3ms single half sine-wave superimposed on rated load', {'pulse': 0.0083, 'wave': 'half_sine'}),
    ('t = 1.0ms', {'pulse': 0.001}),
    ('ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)', {'TA': 25.0}),
    ('IF=10mA, TJ=25°C, PW=0.3ms', {'IF': 0.01, 'TJ': 25.0, 'pulse': 0.0003}),
    ('IPP = 10/1000µs waveform', {'wave': '10/1000'}),
    (None, {}),
])
def test_parse_reads_symbols_pulses_and_waves(text, want):
    got = parse(text)
    assert set(got) == set(want)
    for k, v in want.items():
        assert got[k] == pytest.approx(v) if isinstance(v, float) else got[k] == v


def test_same_condition_is_same_and_rounding_does_not_matter():
    assert compare(parse('IF=1A, TJ=25°C'), parse('IF = 1.0A, TJ = 25°C')) == 'same'


def test_different_current_is_different():
    assert compare(parse('IF=10mA, TJ=25°C'), parse('IF = 1A, TJ = 25°C')) == 'different'


def test_table_default_fills_missing_temperature():
    """조건 칸이 비면 표 제목의 기본 조건(TA = 25°C)을 쓴다(EC-06)."""
    table = parse('ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)')
    assert compare({'TA': 25.0}, parse(None), table) == 'same'


def test_junction_temperature_does_not_match_ambient():
    """[왜] TA와 TJ는 다른 온도다. 행이 TJ를 적었으면 표 기본 TA를 쓰지 않는다(TJ만 준 질문은 확인 안 됨)."""
    table = parse('ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)')
    assert compare({'TA': 25.0}, parse('IF = 1A, TJ = 25°C'), table) == 'unknown'
    assert compare({'TJ': 25.0}, parse(None), table) == 'unknown'


def test_pulse_width_must_match():
    """1 ms 단발 펄스 기준에 8.3 ms 반정현파 값은 쓰지 않는다(AC-05)."""
    assert compare({'pulse': 0.001}, parse('8.3ms single half sine-wave superimposed on rated load')) == 'different'


def test_empty_requirement_is_same():
    assert compare({}, parse('IF = 1A, TJ = 25°C')) == 'same'


def test_conditions_written_by_the_card_code_reader_are_read():
    """카드를 코드가 먼저 읽으면(card_read.read_values, 사전 등록 #43) 조건 글은 예전 사양 표와 같은 모양이다. 실제 카드로 판정이 읽는지 본다.

    [왜] LLM은 제너 시험 전류를 '@ IZT'로 적어 값이 빠졌고, 코드는 같은 행의 시험 전류 칸에서 'IZT = 20 mA'를 적는다.
         VBR의 'IT = 1 mA' · VC의 'IPPM = …'처럼 판정이 쓰지 않는 기호는 LLM 글('@ IT')과 똑같이 무시된다.
    """
    from backend.judge.verdict import _pick
    from backend.rag.card_read import SI, read_values
    elec = 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'
    zener = {'chunk_id': 19739, 'document': 'MMSZ5221B SERIES_I2503.pdf', 'page': 2, 'table': elec, 'row': 'MMSZ5231B',
             'content': f'[MMSZ5221B SERIES_I2503.pdf · 2쪽 · {elec}] PART NUMBER: MMSZ5231B | MARKING CODE: Z5V1'
                        ' | ZENER VOLTAGE / VZ @ IZT / V / Min: 4.85 | ZENER VOLTAGE / VZ @ IZT / V / Nom: 5.1'
                        ' | ZENER VOLTAGE / VZ @ IZT / V / Max: 5.36 | TEST CURRENT / IZT / mA: 20 | LEAKAGE CURRENT / IR @ VR / µA / Max: 5'
                        ' | LEAKAGE CURRENT / IR @ VR / V: 2'}
    leak = {'chunk_id': 36639, 'document': 'SS14ALH SERIES_B2103.pdf', 'page': 2, 'table': elec, 'row': 'Reverse current @ rated VR(2)',
            'content': f'[SS14ALH SERIES_B2103.pdf · 2쪽 · {elec}] PARAMETER: Reverse current @ rated VR(2) | PARAMETER: SS14ALH SS16ALH'
                       ' | CONDITIONS: TJ = 25°C | SYMBOL: IR | TYP: - | MAX: 100 | UNIT: µA'}
    tvs = {'chunk_id': 33939, 'document': 'SMBJ SERIES_R2104.pdf', 'page': 2, 'table': elec, 'row': 'SMBJ14A',
           'content': f'[SMBJ SERIES_R2104.pdf · 2쪽 · {elec}] Part number: SMBJ14A | Breakdown voltage VBR@IT (V) (Note 1) / Min: 15.6'
                      ' | Test current IT (mA): 1 | Maximum peak impulse current IPP (A) (Note 2): 27.0 | Maximum clamping voltage VC@IPP (V): 23.2'}
    parts = {'MMSZ5221B SERIES_I2503.pdf': ['MMSZ5231B'], 'SS14ALH SERIES_B2103.pdf': ['SS14ALH', 'SS16ALH'], 'SMBJ SERIES_R2104.pdf': ['SMBJ14A']}
    rows, _ = read_values([zener, leak, tvs], list(SI), parts, chat=None)  # 세 장 모두 코드가 읽는다(chat을 부르면 실패)
    cond = {(r['part'], r['code']): parse(r['test_condition']) for r in rows}
    assert cond[('MMSZ5231B', 'VZ')] == {'IZ': pytest.approx(0.02)} and cond[('MMSZ5231B', 'IR')] == {'VR': 2.0}
    assert cond[('SS14ALH', 'IR')] == {'VR': 'rated', 'TJ': 25.0}
    assert cond[('SMBJ14A', 'VC')] == {'IPP': 27.0} and cond[('SMBJ14A', 'VBR')] == {}
    # 판정이 시험 조건으로 행을 고른다: 제너 시험 전류 20 mA를 요구하면 코드 행(Min · Nom · Max)을 고르고, LLM 모양 '@ IZT' 행은 못 고른다
    vz = [r for r in rows if r['code'] == 'VZ']
    assert _pick(vz, ['VZ'], {'IZ': 0.02})[1] == vz
    assert _pick([{**r, 'test_condition': '@ IZT'} for r in vz], ['VZ'], {'IZ': 0.02})[1] == []
    assert _pick([r for r in rows if r['part'] == 'SS14ALH'], ['IR'], {'TJ': 25.0})[1][0]['max'] == pytest.approx(1e-4)
