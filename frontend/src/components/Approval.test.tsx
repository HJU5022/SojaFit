import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Approval } from './Review'
import { failure, network } from '../test/network'
import { renderWithQueries } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
const candidate = { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const }
const saved = { id: 3, message_id: 9, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT', case_id: 4, created_at: '2026-11-10T00:00:00Z' }
const show = () => renderWithQueries(<Approval candidate={candidate} messageId={9} reviewer="user@example.test" />)

it('restores an existing approval and quote from the server after a refresh', async () => {
  network(path => path === '/api/messages/9/approval' ? Response.json({ approval: saved, quotes: [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 10 }] }) : failure('NOT_FOUND', '없음', 404))
  show()
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  expect(screen.getByText('견적 SS34 × 10')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '검토하고 승인' })).not.toBeInTheDocument()
})

it('treats 409 ALREADY_APPROVED as already approved: re-reads state and shows no error', async () => {
  let approved = false
  network((path, init) => {
    if (path === '/api/messages/9/approval') return Response.json({ approval: approved ? saved : null, quotes: [] })
    if (path === '/api/messages/9/approvals' && init.method === 'POST') { approved = true; return failure('ALREADY_APPROVED', '이미 승인되었습니다.', 409) }
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
    if (path === '/api/messages/9/approval') return Response.json({ approval: saved, quotes })
    if (path === '/api/approvals/3/quotes') { bodies.push(String(init.body)); quotes = [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 1 }]; return Response.json(quotes[0], { status: 201 }) }
    return failure('NOT_FOUND', '없음', 404)
  })
  show()
  fireEvent.click(await screen.findByRole('button', { name: '견적 열기' }))
  await waitFor(() => expect(screen.getByText('견적 SS34 × 1')).toBeInTheDocument())
  expect(bodies).toEqual(['{"quantity":1}'])
})
