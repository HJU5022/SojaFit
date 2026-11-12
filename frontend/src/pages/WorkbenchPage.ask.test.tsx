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
const resumes: unknown[] = []
let reply = ''
const api = (body = '') => { runs.length = 0; resumes.length = 0; reply = body; vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }); network((path, init) => {
  if (path === '/api/projects/1') return Response.json(project)
  if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
  if (path === '/api/threads/t1/runs') { runs.push(JSON.parse(String(init.body))); return new Response(reply, { headers: { 'Content-Type': 'text/event-stream' } }) }
  if (path === '/api/runs/r1/resume') { resumes.push(JSON.parse(String(init.body))); return new Response('', { headers: { 'Content-Type': 'text/event-stream' } }) }
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

it('shows every line of a completed answer, including a markdown list', async () => {
  const done = { answer: '첫 줄 요약\n\n- 첫째 근거\n- 둘째 근거', status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: 'req-1' }
  api(`event: run_started\ndata: ${JSON.stringify({ run_id: 'r1' })}\n\nevent: completed\ndata: ${JSON.stringify(done)}\n\n`)
  await ask('D1을 SS34로 바꿔도 되나요?')
  expect(await screen.findByText('둘째 근거')).toBeInTheDocument()
  expect(screen.getByText('첫째 근거').tagName).toBe('LI')
})

it('keeps the answer of an earlier question visible next to the selected one, reading each run once', async () => {
  const run = (id: string, answer: string) => ({ id, thread_id: 't1', message_id: null, result: { answer, status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: id } })
  const reads: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path) => {
    if (path === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json({ id: 't1', project_id: 1, title: '', status: null, target_ref: 'D1', target_locked: true, latest_run: null, next_before_message_id: null,
      messages: [{ id: 1, run_id: 'r1', role: 'user', content: '첫 질문', created_at: '' }, { id: 2, run_id: 'r2', role: 'user', content: '둘째 질문', created_at: '' }] })
    if (path.startsWith('/api/runs/')) { const id = path.split('/').pop()!; reads.push(id); return Response.json(run(id, `${id}의 요약\n\n${id}의 본문`)) }
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByText('r1의 본문')).toBeInTheDocument()
  expect(await screen.findByText('r2의 본문')).toBeInTheDocument()
  expect([...reads].sort()).toEqual(['r1', 'r2'])
})

const waiting = `event: run_started\ndata: ${JSON.stringify({ run_id: 'r1' })}\n\nevent: requires_input\ndata: ${JSON.stringify({ status: 'requires_input', interrupt: { question: '값을 알려 주세요.', missing: ['VF', 'IR'] }, request_id: 'req-2' })}\n\n`

it('resumes with only the filled condition when the other is left blank', async () => {
  api(waiting)
  await ask('D1을 SS34로 바꿔도 되나요?')
  fireEvent.change(await screen.findByLabelText('허용 전압 강하'), { target: { value: ' 0.4 V ' } })
  fireEvent.click(screen.getByRole('button', { name: '이 값으로 계속 검토' }))
  await waitFor(() => expect(resumes).toHaveLength(1))
  expect(resumes[0]).toEqual({ answers: { VF: '0.4 V' } })
})

it('resumes with no answers when the user does not know any value', async () => {
  api(waiting)
  await ask('D1을 SS34로 바꿔도 되나요?')
  fireEvent.click(await screen.findByRole('button', { name: '모두 모름으로 계속' }))
  await waitFor(() => expect(resumes).toHaveLength(1))
  expect(resumes[0]).toEqual({ answers: {} })
})

it('blocks the composer while the run waits for conditions', async () => {
  api(waiting)
  await ask('D1을 SS34로 바꿔도 되나요?')
  const box = await screen.findByPlaceholderText("위 조건 질문에 먼저 답하거나 '모두 모름으로 계속'을 눌러 주세요.")
  fireEvent.change(box, { target: { value: '또 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  fireEvent.keyDown(box, { key: 'Enter' })
  await new Promise(resolve => setTimeout(resolve, 100))
  expect(runs).toHaveLength(1)
})
