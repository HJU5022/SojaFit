import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Approval } from './ReviewDetails'
import { failure, network } from '../test/network'
import { renderWithQueries } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
const candidate = { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const }
const saved = { id: 3, message_id: 9, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT', case_id: 4, created_at: '2026-11-10T00:00:00Z' }
// Approval은 승인 여부와 저장된 견적을 GET …/approvals(승인마다 quotes) 하나로 읽는다
const stored = (path: string, approval: typeof saved | null, quotes: unknown[]) => path === '/api/messages/9/approvals' ? Response.json(approval ? [{ ...approval, quotes }] : []) : null
const show = () => renderWithQueries(<Approval candidate={candidate} messageId={9} reviewer="user@example.test" />)

it('restores an existing approval and quote from the server after a refresh', async () => {
  network((path, init) => (init.method ?? 'GET') === 'GET' && stored(path, saved, [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 10 }]) || failure('NOT_FOUND', '없음', 404))
  show()
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  expect(await screen.findByText('견적 SS34 × 10')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '검토하고 승인' })).not.toBeInTheDocument()
})

it('treats 409 ALREADY_APPROVED as already approved: re-reads state and shows no error', async () => {
  let approved = false
  network((path, init) => {
    if (path === '/api/messages/9/approvals' && init.method === 'POST') { approved = true; return failure('ALREADY_APPROVED', '이미 승인되었습니다.', 409) }
    const hit = stored(path, approved ? saved : null, []); if (hit) return hit
    return failure('NOT_FOUND', '없음', 404)
  })
  show()
  await waitFor(() => expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '검토하고 승인' }))
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('sends only the quantity when saving a quote and then shows it', async () => {
  const bodies: string[] = []
  let quotes: unknown[] = []
  network((path, init) => {
    const hit = (init.method ?? 'GET') === 'GET' && stored(path, saved, quotes); if (hit) return hit
    if (path === '/api/approvals/3/quotes') { bodies.push(String(init.body)); quotes = [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 1 }]; return Response.json(quotes[0], { status: 201 }) }
    return failure('NOT_FOUND', '없음', 404)
  })
  show()
  fireEvent.click(await screen.findByRole('button', { name: '견적 열기' }))
  await waitFor(() => expect(screen.getByText('견적 SS34 × 1')).toBeInTheDocument())
  expect(bodies).toEqual(['{"quantity":1}'])
})

it('shows the quantity-aware live price with its notice, and never sends price in any body or storage', async () => {
  const sent: string[] = []
  const live = { available: true, source: 'Mouser Electronics', fetched_at: '2026-11-14T00:00:00Z', parts: [{ part_number: 'SS34', manufacturer: 'M', availability: '100 재고', product_url: null,
    price_breaks: [{ quantity: 1, price: '$0.50', currency: 'USD' }, { quantity: 100, price: '$0.30', currency: 'USD' }] }] }
  network((path, init) => {
    if (init.body) sent.push(String(init.body))
    const hit = stored(path, saved, [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 120 }]); if (hit) return hit
    if (path.startsWith('/api/prices?')) return Response.json(live)
    return failure('NOT_FOUND', '없음', 404)
  })
  show()
  fireEvent.click(await screen.findByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('120개 단가')).toBeInTheDocument()
  expect(screen.getAllByText('$0.30 USD')).toHaveLength(2)
  expect(screen.getByText('36.00 USD')).toBeInTheDocument()
  expect(screen.getByText(/실시간 조회 · 조회 시각.*세금·배송비·환율 미포함 · 저장하지 않음/)).toBeInTheDocument()
  expect(sent).toEqual([])
  expect(JSON.stringify({ ...localStorage })).not.toMatch(/0\.30/)
})

it('shows the no-key notice when prices are unavailable', async () => {
  network(path => stored(path, saved, [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 1 }])
    ?? Response.json({ available: false, source: 'Mouser Electronics', reason: 'no_key', message: 'Mouser 키가 없어 조회하지 않아요.', parts: [] }))
  show()
  fireEvent.click(await screen.findByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('Mouser 키가 없어 조회하지 않아요.')).toBeInTheDocument()
})
