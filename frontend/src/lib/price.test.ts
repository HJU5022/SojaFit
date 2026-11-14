import { expect, it } from 'vitest'
import { breakFor, parsePrice } from './price'

it.each([['$0.45', 0.45], ['0,45 €', 0.45], ['1,234.50', 1234.5], ['1.234,50 €', 1234.5], ['1,234', 1234], ['7.77', 7.77], ['', null], [null, null], ['무료', null]])('parses %s', (text, value) => {
  expect(parsePrice(text)).toBe(value)
})

it('picks the largest break not above the quantity, or none below the minimum order', () => {
  const breaks = [{ quantity: 1, price: '$0.50', currency: 'USD' }, { quantity: 100, price: '$0.30', currency: 'USD' }, { quantity: 1000, price: '$0.20', currency: 'USD' }]
  expect(breakFor(breaks, 99)?.unit).toBe(0.5)
  expect(breakFor(breaks, 100)?.unit).toBe(0.3)
  expect(breakFor(breaks, 5000)?.unit).toBe(0.2)
  expect(breakFor([{ quantity: 10, price: '$1', currency: 'USD' }], 5)).toBeNull()
})
