import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import ApprovalPanel from './ApprovalPanel'
import ApprovedCasesPanel from './ApprovedCasesPanel'

afterEach(() => vi.unstubAllGlobals())
const judgement = { kind: 'judge' as const, roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
  results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const, board_change: false }] }

it('names the candidate and verdict before approval and sends no price fields to a quote', async () => {
  const calls: { path: string; body?: string | null }[] = []
  vi.stubGlobal('fetch', vi.fn((path: string, init: RequestInit = {}) => {
    calls.push({ path, body: init.body?.toString() })
    if (path === '/api/runs/run-1') return Promise.resolve(Response.json({ id: 'run-1', thread_id: 'thread-1', message_id: 9, result: { request_id: 'req-1' } }))
    if (path === '/api/messages/9/approvals') return Promise.resolve(Response.json({ id: 3, message_id: 9, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT', case_id: 4 }, { status: 201 }))
    if (path === '/api/approvals/3/quotes') return Promise.resolve(Response.json({ id: 5, approval_id: 3, part_number: 'SS34', quantity: 2 }, { status: 201 }))
    if (path.startsWith('/api/prices?')) return Promise.resolve(Response.json({ available: false, source: 'Mouser Electronics', reason: 'demo_mode', message: '가격 없음', parts: [] }))
    if (path === '/api/me/memory') return Promise.resolve(Response.json([{ kind: 'affiliation', value: '한빛전자', text: '이 사용자의 소속은 한빛전자이다.', version: 1, updated_at: '', source: 'user_settings' }]))
    throw new Error(`unexpected ${path}`)
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><ApprovalPanel runId="run-1" judgement={judgement} /></QueryClientProvider>)
  expect(screen.getByRole('button', { name: '견적 열기' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('승인할 후보'), { target: { value: '0' } })
  fireEvent.click(screen.getByRole('button', { name: '판정 승인 확인' }))
  expect(screen.getByText('SS34 후보의 “역할상 충분” 판정을 승인할까요?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '확인 후 승인' }))
  await screen.findByText('SS34 판정을 승인했습니다.')
  expect(JSON.parse(calls.find(call => call.path === '/api/messages/9/approvals')!.body!)).toEqual({ candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' })
  expect(calls.some(call => call.path === '/api/me/memory')).toBe(false)  // 견적을 열기 전에는 내 설정을 읽지 않는다
  fireEvent.click(screen.getByRole('button', { name: '견적 열기' }))
  expect(await screen.findByText('소속: 한빛전자')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await screen.findByText('가격 없음')
  fireEvent.change(screen.getByLabelText('수량'), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: '가격 없이 견적 저장' }))
  await screen.findByText('SS34 2개 견적을 저장했습니다. 가격은 저장하지 않았습니다.')
  expect(JSON.parse(calls.find(call => call.path === '/api/approvals/3/quotes')!.body!)).toEqual({ quantity: 2 })
  expect(calls.some(call => call.path.startsWith('/api/prices?parts=SS34'))).toBe(true)
})

it('requires confirmation before deleting an approved case', async () => {
  const fetcher = vi.fn((path: string, init: RequestInit = {}) => {
    if (path === '/api/approved-cases' && init.method === 'DELETE') throw new Error('wrong path')
    if (path === '/api/approved-cases') return Promise.resolve(Response.json([{ id: 4, approval_id: 3, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' }]))
    if (path === '/api/approved-cases/4') return Promise.resolve(new Response(null, { status: 204 }))
    throw new Error(`unexpected ${path}`)
  })
  vi.stubGlobal('fetch', fetcher)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><ApprovedCasesPanel /></QueryClientProvider>)
  await screen.findByText('SS34 · ROLE_SUFFICIENT')
  fireEvent.click(screen.getByRole('button', { name: '사례 삭제' }))
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/api/approved-cases/4', expect.objectContaining({ method: 'DELETE' })))
})
