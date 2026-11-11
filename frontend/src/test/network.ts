import { vi } from 'vitest'

export const user = { user_id: 7, email: 'user@example.test', role: 'user' as const }
export const administrator = { user_id: 1, email: 'admin@example.test', role: 'admin' as const }
export const accounts = [{ id: 1, email: 'a***@example.test', role: 'admin', is_active: true }, { id: 7, email: 'u***@example.test', role: 'user', is_active: true }]
export const unavailable = { available: false, source: 'Mouser Electronics', reason: 'demo_mode', message: '데모 모드라 Mouser 가격·재고를 조회하지 않아요.', parts: [] }
export const priceResult = { available: true, source: 'Mouser Electronics', fetched_at: '2026-11-09T00:00:00Z', parts: [{ part_number: 'SS34', manufacturer: 'Example Maker', price_breaks: [{ quantity: 1, price: '7.77', currency: 'XXX' }], availability: '시험 재고', product_url: 'https://example.test/p/2' }] }
export function failure(code = 'UNAUTHORIZED', message = '로그인이 필요합니다.', status = 401) {
  return Response.json({ error: { code, message, request_id: 'req-test' } }, { status })
}
export function network(handler: (path: string, init: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal('fetch', (path: string, init: RequestInit = {}) => handler(path, init))
}
