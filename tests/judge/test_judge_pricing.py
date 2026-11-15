"""손으로 쓴 가격 구간의 수량별 계산. 실제 판매처 값·네트워크·저장 없음."""
import pytest

from backend.judge.pricing import price_estimate


def part(breaks=None, number='SS34'):
    return {'part_number': number, 'price_breaks': breaks if breaks is not None else [
        {'quantity': 10, 'price': '$0.10', 'currency': 'USD'},
        {'quantity': 1, 'price': '0.30', 'currency': 'USD'}]}


def test_selects_highest_applicable_break_and_multiplies_exactly():
    assert price_estimate(part(), ['ss34'], 25) == {
        'quantity': 25, 'break_quantity': 10, 'unit_price': '0.10', 'total': '2.50', 'currency': 'USD'}
    assert price_estimate(part(), ['SS34'], 1)['total'] == '0.30'
    assert price_estimate(part([{'quantity': 1, 'price': '₩1,234.50', 'currency': 'KRW'}]), ['SS34'], 2)['total'] == '2469.00'


@pytest.mark.parametrize('breaks', [
    [], [{'quantity': 100, 'price': '1', 'currency': 'USD'}],
    [{'quantity': 1, 'price': '1,23', 'currency': 'EUR'}],
    [{'quantity': 1, 'price': 'NaN', 'currency': 'USD'}],
    [{'quantity': 1, 'price': '-1', 'currency': 'USD'}],
    [{'quantity': 1, 'price': '€1', 'currency': 'USD'}],
    [{'quantity': 1, 'price': '1', 'currency': None}],
    [{'quantity': 1, 'price': '1', 'currency': 'USD'}, {'quantity': 10, 'price': '0.5', 'currency': 'EUR'}],
    [{'quantity': 1, 'price': '1', 'currency': 'USD'}, {'quantity': 10, 'price': '문의', 'currency': 'USD'}],
    [{'quantity': 1, 'price': '1', 'currency': 'USD'}, {'quantity': 1, 'price': '2', 'currency': 'USD'}],
])
def test_ambiguous_or_unavailable_prices_are_not_guessed(breaks):
    assert price_estimate(part(breaks), ['SS34'], 25) is None


def test_wrong_part_and_invalid_quantity_are_not_estimated():
    assert price_estimate(part(number='SS340'), ['SS34'], 25) is None
    for quantity in [0, -1, 100001, 1.5, True]:
        assert price_estimate(part(), ['SS34'], quantity) is None
