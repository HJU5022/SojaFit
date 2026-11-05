"""데이터시트 시험 조건 글을 dict로 읽고, 두 조건이 같은지 정한다.

- 역할: 사양 표 행의 시험 조건(예: "IF = 1A, TJ = 25°C"), 표 제목의 기본 조건("TA = 25°C unless otherwise noted"),
  읽기 노드가 정리한 질문의 조건("IF=10mA, TJ=25°C, PW=0.3ms")을 같은 모양({기호: SI 값})으로 바꾸고 비교한다.
- 하지 않는 일: 정격 값 비교 · 판정(verdict.py), LLM 호출. 단위 환산은 backend/rag/units.py를 읽기만 한다(SPEC 3절).
- 출처: docs/specs/judge-agent.md EC-06 · AC-05
"""
import re
from typing import Literal

from backend.rag.units import to_si

TEMPS = ('TA', 'TJ', 'TC')
# [왜] IZT(시험 전류)와 IZ(실제 전류)는 같은 축이라 한 이름으로 비교한다. PW · tp · t는 모두 펄스 폭이다
KEYS = {'TA': 'TA', 'TJ': 'TJ', 'TC': 'TC', 'IF': 'IF', 'VR': 'VR', 'IZT': 'IZ', 'IZ': 'IZ', 'IPP': 'IPP',
        'PW': 'pulse', 'TP': 'pulse', 'T': 'pulse'}
SYMBOL = re.compile(r'\b(TA|TJ|TC|IF|VR|IZT|IZ|IPP|PW|tp|t)\s*=\s*(\d+(?:\.\d+)?)\s*(°C|℃|[a-zA-Zµμ]*)', re.I)
# [왜] 앞에 = · 글자 · 점 · 빗금이 붙은 숫자는 펄스 폭이 아니다(예: "10/1000µs"는 파형 이름)
BARE_PULSE = re.compile(r'(?<![=\w./])(\d+(?:\.\d+)?)\s*(ms|µs|μs|us)\b')
WAVES = (('8/20', '8/20'), ('10/1000', '10/1000'), ('half sine', 'half_sine'), ('half-sine', 'half_sine'), ('square', 'square'))
RATED_VR = re.compile(r'rated\s+VR', re.I)
TOL = 0.02  # [왜] 반올림 표기(1A · 1.0A)는 같게, 실제로 다른 값(1A · 2A)은 다르게 본다


def _si(num: str, unit: str) -> float | None:
    """숫자 · 단위 글 → SI 값. us는 µs로 읽는다. 모르는 단위면 None."""
    found = to_si(float(num), 'µs' if unit.lower() == 'us' else unit)
    return found[0] if found else None


def parse(text: str | None) -> dict:
    """조건 글 → {'TJ': 25.0, 'IF': 1.0, 'pulse': 0.0083, 'wave': 'half_sine', 'VR': 'rated'}. 못 읽는 글자는 무시한다."""
    if not text:
        return {}
    out = {}
    for sym, num, unit in SYMBOL.findall(text):
        key = KEYS[sym.upper()]
        value = float(num) if key in TEMPS else _si(num, unit)  # 온도는 °C 그대로 둔다
        if value is not None:
            out[key] = value
    if 'pulse' not in out and (m := BARE_PULSE.search(text)):
        if (value := _si(m.group(1), m.group(2))) is not None:
            out['pulse'] = value
    low = text.lower()
    for word, wave in WAVES:
        if word in low:
            out['wave'] = wave
            break
    if RATED_VR.search(text):
        out['VR'] = 'rated'
    return out


def fill(actual: dict, default: dict | None = None) -> dict:
    """행의 조건(actual)에 없는 항목을 표 제목의 기본 조건(default)으로 채운다. 행이 온도를 적었으면 기본 온도는 쓰지 않는다."""
    default = dict(default or {})
    if any(k in actual for k in TEMPS):
        default = {k: v for k, v in default.items() if k not in TEMPS}  # [왜] TJ로 잰 행에 표 기본 TA를 붙이지 않는다
    return {**default, **actual}


def compare(required: dict, actual: dict, default: dict | None = None) -> Literal['same', 'different', 'unknown']:
    """required의 항목이 모두 actual과 같으면 'same', 하나라도 다르면 'different', 값이 없어 못 정하면 'unknown'.

    actual에 없는 항목은 표 제목의 기본 조건(default)으로 채운다(fill).
    """
    have = fill(actual, default)
    result = 'same'
    for key, want in required.items():
        if key not in have:
            result = 'unknown'
            continue
        got = have[key]
        if isinstance(want, str) or isinstance(got, str):
            equal = want == got
        else:
            equal = abs(got - want) <= TOL * max(abs(want), 1e-12)
        if not equal:
            return 'different'
    return result
