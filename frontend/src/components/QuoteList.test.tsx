import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import QuoteList from './QuoteList'
import { failure, network, priceResult } from '../test/network'
import { renderWithQueries } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
const rows = [{ id: 5, approval_id: 3, part_number: 'SS34', quantity: 10, created_at: '2026-11-10T09:00:00Z', thread_id: 't1' }]

it('lists quotes (part, quantity, date) and reopens the thread with its target part', async () => {
  const opened = vi.fn()
  network(path => path === '/api/projects/1/quotes' ? Response.json(rows) : path === '/api/threads/t1' ? Response.json({ id: 't1', target_ref: 'D1', messages: [] }) : failure('NOT_FOUND', '없음', 404))
  renderWithQueries(<QuoteList projectId={1} onOpen={opened} />)
  expect(await screen.findByText('SS34')).toBeInTheDocument()
  expect(screen.getByText('2026-11-10')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'SS34 견적이 나온 검토 열기' }))
  await waitFor(() => expect(opened).toHaveBeenCalledWith('t1', 'D1'))
})

it('looks up the live price only when asked, with no request body', async () => {
  const calls: { path: string; body: unknown }[] = []
  network((path, init) => { calls.push({ path, body: init.body }); return path === '/api/projects/1/quotes' ? Response.json(rows) : Response.json(priceResult) })
  renderWithQueries(<QuoteList projectId={1} onOpen={vi.fn()} />)
  await screen.findByText('SS34')
  expect(calls.map(call => call.path)).toEqual(['/api/projects/1/quotes'])
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('10개 합계')).toBeInTheDocument()
  expect(calls.at(-1)).toEqual({ path: '/api/prices?parts=SS34', body: undefined })
})

it('renders nothing when there are no quotes', async () => {
  network(() => Response.json([]))
  const { container } = renderWithQueries(<QuoteList projectId={1} onOpen={vi.fn()} />)
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  expect(container).toBeEmptyDOMElement()
})
