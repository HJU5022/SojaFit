"""가격을 저장하지 않고 같은 품번의 수량 구간으로 예상 금액을 계산한다."""
import re
from decimal import Decimal, localcontext


def price_estimate(part: dict, requested: list[str], quantity: int) -> dict | None:
    """다른 품번·통화나 모호한 값을 추정하지 않고 조회 응답 안에서만 계산한다."""
    if type(quantity) is not int or not 1 <= quantity <= 100000:
        return None
    if str(part.get('part_number') or '').strip().casefold() not in {p.strip().casefold() for p in requested}:
        return None
    breaks = [b for b in part.get('price_breaks') or []
              if type(b.get('quantity')) is int and 1 <= b['quantity'] <= quantity]
    if not breaks:
        return None
    currencies = {b.get('currency') for b in breaks}
    if len(currencies) != 1:
        return None
    currency = next(iter(currencies))
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        return None
    threshold = max(b['quantity'] for b in breaks)
    selected = [b for b in breaks if b['quantity'] == threshold]
    values = []
    for row in selected:
        text = row.get('price')
        if not isinstance(text, str) or len(text) > 40:
            return None
        text = text.strip().removeprefix(currency).strip()
        symbols = {'USD': ('US$', '$'), 'EUR': ('€',), 'GBP': ('£',), 'JPY': ('¥',), 'KRW': ('₩',)}
        for symbol in symbols.get(currency, ()):
            text = text.removeprefix(symbol).strip()
        # 구분 기호를 임의로 바꾸지 않는다. 소수점은 '.', 천 단위는 세 자리 ','만 허용한다.
        if not re.fullmatch(r'(?:\d{1,12}|\d{1,3}(?:,\d{3}){1,3})(?:\.\d{1,8})?', text):
            return None
        values.append(Decimal(text.replace(',', '')))
    if len(set(values)) != 1:
        return None
    unit = values[0]
    with localcontext() as context:
        context.prec = 40
        total = unit * quantity
    return {'quantity': quantity, 'break_quantity': threshold, 'unit_price': format(unit, 'f'),
            'total': format(total, 'f'), 'currency': currency}
