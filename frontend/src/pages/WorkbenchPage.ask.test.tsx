import { fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/ApprovedCases', () => ({ default: () => null }))
afterEach(() => vi.unstubAllGlobals())

const project = { id: 1, name: '보드', source_kind: 'upload', demo_id: null, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }, { ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
const runs: unknown[] = []
const api = () => { runs.length = 0; vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }); network((path, init) => {
  if (path === '/api/projects/1') return Response.json(project)
  if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
  if (path === '/api/threads/t1/runs') { runs.push(JSON.parse(String(init.body))); return new Response('', { headers: { 'Content-Type': 'text/event-stream' } }) }
  return Response.json([])
}) }
const ask = async (text: string) => { renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.change(await screen.findByRole('textbox', { name: '질문' }), { target: { value: text } }); fireEvent.click(screen.getByRole('button', { name: '질문 보내기' })) }

it('opens the review of the part named in the question and sends it once as the first run', async () => {
  api()
  await ask('D1을 SS34로 바꿔도 되나요?')
  await waitFor(() => expect(runs).toHaveLength(1))
  expect(runs[0]).toEqual({ question: 'D1을 SS34로 바꿔도 되나요?', target_ref: 'D1' })
  expect(await screen.findByRole('heading', { level: 1, name: /D1/ })).toBeInTheDocument()
  await new Promise(resolve => setTimeout(resolve, 100))
  expect(runs).toHaveLength(1)
})

it('explains a question without a part number and sends nothing', async () => {
  api()
  await ask('다이오드를 바꿔도 되나요?')
  expect(await screen.findByRole('alert')).toHaveTextContent('어느 부품에 대한 질문인지 알 수 없습니다.')
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('다이오드를 바꿔도 되나요?')
  expect(runs).toHaveLength(0)
})

it('says a part outside the scope cannot be judged', async () => {
  api()
  await ask('R1을 바꿔도 되나요?')
  expect(await screen.findByRole('alert')).toHaveTextContent('R1은(는) 현재 판정 범위 밖입니다. 지금은 다이오드만 판정합니다.')
  expect(runs).toHaveLength(0)
})
