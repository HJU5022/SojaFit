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
