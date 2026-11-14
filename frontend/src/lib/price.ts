// Mouser가 준 단가 문자열('$0.45', '0,45 €', '1,234.50')에서 숫자를 읽고, 수량에 맞는 가격 구간을 고른다.
// 화면 계산 전용이다. 읽은 값은 어디에도 저장하거나 서버로 보내지 않는다(ADR 0009).
export type PriceBreak = { quantity: number | null; price: string | null; currency: string | null }

/** 통화 기호를 떼고 소수점 표기('.' 또는 ',')를 추정해 숫자로 바꾼다. 읽지 못하면 null. */
export function parsePrice(text: string | null): number | null {
  const digits = (text ?? '').replace(/[^\d.,]/g, '')
  if (!/\d/.test(digits)) return null
  const comma = digits.lastIndexOf(','), dot = digits.lastIndexOf('.')
  let normalized: string
  if (comma >= 0 && dot >= 0) normalized = comma > dot ? digits.replaceAll('.', '').replace(',', '.') : digits.replaceAll(',', '') // 마지막 구분자가 소수점
  else if (comma >= 0) normalized = /^\d{1,3}(,\d{3})+$/.test(digits) ? digits.replaceAll(',', '') : digits.replace(',', '.') // '1,234'만 천 단위, '0,45'는 소수
  else normalized = digits
  const value = Number(normalized)
  return Number.isFinite(value) ? value : null
}

/** 수량 이하의 가장 큰 구간. 최소 주문 수량보다 적으면 null. */
export function breakFor(breaks: PriceBreak[], quantity: number) {
  const rows = breaks.flatMap(item => item.quantity != null && item.quantity <= quantity && parsePrice(item.price) != null ? [{ ...item, unit: parsePrice(item.price)! }] : [])
  return rows.sort((a, b) => b.quantity! - a.quantity!)[0] ?? null
}
