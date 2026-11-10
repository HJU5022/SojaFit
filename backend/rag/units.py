"""표 값의 단위를 SI 기본 단위로 바꾼다.

- 역할: 데이터시트 표에 적힌 단위(mA, µA, ns, pF, kV, mW, °C 등)를 SI 기본 단위(V, A, W, s, F, degC)의 값으로 바꾼다.
  카드 읽기(`card_read.py`)가 쓰고, judge는 읽기만 한다.
- 하지 않는 일: 값 비교·판정(`backend/judge/`). 비율 단위(°C/W, mV/°C)와 모르는 단위는 짐작하지 않고 None을 돌려준다.
- 출처: SPEC.md 3절(단위 환산은 rag에서 만들고 judge가 읽기만 함), db/schema/table-definition.md 5.7 `normalized_unit`(A-08)
"""

BASE = {'V': 'V', 'A': 'A', 'W': 'W', 's': 's', 'F': 'F'}  # 단위 끝 글자 → 정규화 단위
# [주의] 대문자 K는 표에 'KV'로 적힌 kV다. 대문자 M(메가)·S(지멘스)는 다이오드 표에서 mA·ms를 잘못 적은 것일 수 있어 넣지 않는다
PREFIX = {'': 1.0, 'k': 1e3, 'K': 1e3, 'm': 1e-3, 'µ': 1e-6, 'u': 1e-6, 'n': 1e-9, 'p': 1e-12}
CELSIUS = {'°C', '℃', 'oC', 'degC'}


def to_si(value: float, unit: str | None) -> tuple[float, str] | None:
    """(값, 단위 글) → (SI 기본 단위 값, 정규화 단위). 모르는 단위면 None."""
    # [왜] μ(그리스 문자 U+03BC)와 µ(마이크로 기호 U+00B5)를 데이터시트마다 섞어 써서 하나로 맞춘다(parse.py와 같은 규칙)
    u = (unit or '').replace('μ', 'µ').replace(' ', '')
    if u in CELSIUS:
        return value, 'degC'  # 온도는 배수 없이 그대로(°C 그대로 저장, A-08의 degC)
    if 1 <= len(u) <= 2 and u[-1] in BASE and u[:-1] in PREFIX:
        return value * PREFIX[u[:-1]], BASE[u[-1]]
    return None
