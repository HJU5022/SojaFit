"""표 값 단위 환산(backend.rag.units) 계약.

- 역할: 데이터시트 단위(mA, µA, nA, ns, pF, kV, mW, °C)가 SI 기본 단위와 배수로 바뀌는지, 모르는 단위는 None인지 본다.
- 하지 않는 일: 값 비교·판정(backend/judge/)은 보지 않는다.
- 출처: SPEC.md 3절(단위 환산은 rag에서 만들고 judge가 읽기만 함), db/schema/table-definition.md 5.7 normalized_unit
"""
import pytest

from backend.rag.units import to_si


@pytest.mark.parametrize('value, unit, expected, base', [
    (150, 'mA', 0.15, 'A'),
    (5, 'µA', 5e-6, 'A'),   # [주의] µ(마이크로 기호 U+00B5)
    (5, 'μA', 5e-6, 'A'),   # [주의] μ(그리스 문자 U+03BC). 데이터시트마다 둘을 섞어 쓴다
    (5, 'uA', 5e-6, 'A'),
    (25, 'nA', 25e-9, 'A'),
    (4, 'ns', 4e-9, 's'),
    (15, 'pF', 15e-12, 'F'),
    (8, 'kV', 8e3, 'V'),
    (8, 'KV', 8e3, 'V'),    # [왜] 표에 KV로 적힌 문서가 있다(TESDU5V0 SERIES)
    (500, 'mW', 0.5, 'W'),
    (600, 'W', 600, 'W'),
    (150, '°C', 150, 'degC'),
    (1.1, 'V', 1.1, 'V'),
])
def test_known_units(value, unit, expected, base):
    si, norm = to_si(value, unit)
    assert si == pytest.approx(expected)
    assert norm == base


@pytest.mark.parametrize('unit', ['MA', 'Ω', '°C/W', 'mV/°C', '', None, 'S', 'mm'])
def test_unknown_units_are_none(unit):
    # [왜] 모르는 단위를 V·A로 짐작하면 mA·A 같은 1000배 오류가 표에 들어간다
    assert to_si(1.0, unit) is None
