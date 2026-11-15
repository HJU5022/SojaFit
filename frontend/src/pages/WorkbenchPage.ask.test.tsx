import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { StrictMode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'
import type { ApprovalDto } from '../api/quotes'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/ApprovedCases', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })

it('creates an empty project without calling the demo API, then asks for a netlist in chat', async () => {
  const writes: unknown[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  const empty = { id: 9, name: '빈 보드', source_kind: 'upload', demo_id: null, circuit_version: 0, created_at: '', updated_at: '', connections: { parts: [], nets: [] } }
  network((path, init) => {
    if (path === '/api/demo-circuits') return failure('NOT_FOUND', '없음', 404)
    if (path === '/api/projects' && init.method === 'POST') { writes.push(JSON.parse(String(init.body))); return Response.json(empty, { status: 201 }) }
    if (path === '/api/projects/9') return Response.json(empty)
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app']}><WorkbenchPage /></MemoryRouter>)
  const dialog = document.getElementById('creator-title')!.closest('dialog')!
  dialog.showModal = function () { this.open = true }
  dialog.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[0])
  fireEvent.change(screen.getByLabelText('프로젝트 이름'), { target: { value: '빈 보드' } })
  fireEvent.click(screen.getByRole('button', { name: '만들기' }))
  expect(await screen.findByText(/넷리스트를 첨부해 주세요/)).toBeInTheDocument()
  expect(writes).toEqual([{ name: '빈 보드' }])
  expect(screen.getByRole('button', { name: '파일 첨부 (.net, .txt)' })).toBeEnabled()
})

it('imports a chat attachment into the same project and starts exactly one run in the new version thread', async () => {
  const imports: FormData[] = [], starts: unknown[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  const v2 = { ...project, circuit_version: 2, connections: { parts: [{ ref: 'D7', value: 'NEW-DIODE', footprint: '' }], nets: [] } }
  network((path, init) => {
    if (path === '/api/projects/1/netlist') { imports.push(init.body as FormData); return Response.json({ project: v2, thread_id: 'new-version' }, { status: 201 }) }
    if (path.startsWith('/api/projects/1?thread_id=new-version')) return Response.json(v2)
    if (path.startsWith('/api/projects/1?') || path === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json(savedThread())
    if (path === '/api/threads/new-version') return Response.json({ ...savedThread('new-version', 1, ''), target_ref: null, target_locked: false, messages: [], latest_run: null })
    if (path === '/api/threads/new-version/runs') { starts.push(JSON.parse(String(init.body))); return new Response('') }
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    return Response.json([])
  })
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  await screen.findByText('run-t1 저장된 답변')
  fireEvent.change(screen.getByRole('textbox', { name: '질문' }), { target: { value: 'D7을 SS34로 바꿔도 돼?' } })
  const file = new File(['(export)'], 'next.net')
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  await waitFor(() => expect(starts).toHaveLength(1))
  expect(imports).toHaveLength(1)
  expect(imports[0].get('file')).toEqual(file)
  expect(starts[0]).toEqual({ question: 'D7을 SS34로 바꿔도 돼?', target_ref: 'D7' })
  expect(await screen.findByRole('heading', { level: 1, name: /D7.*NEW-DIODE/ })).toBeInTheDocument()
})

it('keeps the text and file when netlist parsing fails, without starting an analysis', async () => {
  const starts: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path === '/api/projects/1/netlist') return failure('INVALID_NETLIST', '올바른 KiCad 넷리스트를 올려 주세요.', 400)
    if (path.startsWith('/api/projects/1?') || path === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json(savedThread())
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    if (init.method === 'POST') starts.push(path)
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByText('run-t1 저장된 답변')
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: 'D1 질문 초안' } })
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['bad'], 'broken.net')] } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('올바른 KiCad')
  expect(input).toHaveValue('D1 질문 초안')
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('broken.net')
  expect(starts).toEqual([])
})

it.each(['', '다이오드를 검토해 줘'])('imports a file with question %j and waits for explicit part selection without an analysis', async (text) => {
  const posts: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  const empty = { ...project, circuit_version: 0, connections: { parts: [], nets: [] } }
  network((path, init) => {
    if (init.method === 'POST') posts.push(path)
    if (path === '/api/projects/1/netlist') return Response.json({ project: { ...project, circuit_version: 1 }, thread_id: 'fresh' })
    if (path === '/api/projects/1') return Response.json(empty)
    if (path === '/api/projects/1?thread_id=fresh') return Response.json({ ...project, circuit_version: 1 })
    if (path === '/api/threads/fresh') return Response.json({ ...savedThread('fresh', 1, ''), target_ref: null, target_locked: false, messages: [], latest_run: null })
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: text } })
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['(export)'], 'first.net')] } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('button', { name: 'D1 1N4148 선택' })).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue(text)
  expect(posts).toEqual(['/api/projects/1/netlist'])
  expect(screen.queryByText(/대상 부품을 회로에서 찾지 못했습니다/)).toBeNull()
})

it('keeps a single import in flight and preserves the draft after a delayed failure', async () => {
  let reject!: (value: Response) => void
  const writes: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects/1/netlist') return new Promise<Response>(resolve => { reject = resolve })
    if (path === '/api/projects/1') return Response.json({ ...project, connections: { parts: [], nets: [] } })
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '유지할 질문' } })
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['(export)'], 'first.net')] } })
  fireEvent.submit(input.closest('form')!); fireEvent.submit(input.closest('form')!)
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  expect(input).toHaveAttribute('readonly')
  await act(async () => { reject(failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503)) })
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후')
  expect(input).toHaveValue('유지할 질문')
  expect(writes).toEqual(['/api/projects/1/netlist'])
})

it('restores the old thread circuit instead of the latest project circuit after a newer upload', async () => {
  const reads: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network(path => {
    reads.push(path)
    if (path === '/api/projects/1') return Response.json({ ...project, circuit_version: 2, connections: { parts: [{ ref: 'D7', value: 'NEW-DIODE', footprint: '' }], nets: [] } })
    if (path === '/api/projects/1?thread_id=t1') return Response.json({ ...project, circuit_version: 1 })
    if (path === '/api/threads/t1') return Response.json(savedThread())
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByRole('heading', { level: 1, name: /D1.*1N4148/ })).toBeInTheDocument()
  expect(screen.getByText('회로 v1')).toBeInTheDocument()
  expect(reads).toContain('/api/projects/1?thread_id=t1')
  expect(screen.queryByText('NEW-DIODE')).toBeNull()
})

it.each([false, true])('guards a delayed thread creation from double submit and abandoned navigation (leave=%s)', async (leave) => {
  let finish!: (value: Response) => void
  const writes: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects/1/threads' && init.method === 'POST') return new Promise<Response>(resolve => { finish = resolve })
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/new-thread/runs') return new Response('')
    if (path === '/api/threads/new-thread') return Response.json({ ...savedThread('new-thread'), messages: [], latest_run: null })
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: 'D1 질문' } })
  fireEvent.submit(input.closest('form')!); fireEvent.submit(input.closest('form')!)
  expect(writes).toEqual(['/api/projects/1/threads'])
  if (leave) fireEvent.click(within(screen.getByRole('navigation', { name: '프로젝트와 검토' })).getByRole('button', { name: /^프로젝트$/ }))
  await act(async () => { finish(Response.json({ id: 'new-thread' })) })
  if (leave) expect(writes).toEqual(['/api/projects/1/threads'])
  else await waitFor(() => expect(writes).toEqual(['/api/projects/1/threads', '/api/threads/new-thread/runs']))
})

const project = { id: 1, name: '보드', source_kind: 'upload', demo_id: null, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }, { ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
const runs: unknown[] = []
const resumes: unknown[] = []
let reply = ''
const api = (body = '') => { runs.length = 0; resumes.length = 0; reply = body; vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }); network((path, init) => {
  if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
  if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
  if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
  if (path === '/api/threads/t1/runs') { runs.push(JSON.parse(String(init.body))); return new Response(reply, { headers: { 'Content-Type': 'text/event-stream' } }) }
  if (path === '/api/runs/r1/resume') { resumes.push(JSON.parse(String(init.body))); return new Response('', { headers: { 'Content-Type': 'text/event-stream' } }) }
  return Response.json([])
}) }
const ask = async (text: string) => { renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
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

it('preserves the sent draft when run acceptance fails before a run id is received', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
    if (path === '/api/threads/t1/runs' && init.method === 'POST') return failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503)
    return Response.json([])
  })
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: 'D1 질문 초안' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후 다시 시도해 주세요.')
  expect(input).toHaveValue('D1 질문 초안')
})

it('preserves the sent draft on an existing thread when run acceptance fails', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json(savedThread())
    if (path === '/api/threads/t1/runs' && init.method === 'POST') return failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503)
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    return Response.json([])
  })
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '기존 대화의 질문 초안' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후 다시 시도해 주세요.')
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('기존 대화의 질문 초안')
})

it('keeps a new draft typed while run acceptance is pending', async () => {
  let resolveRun!: (response: Response) => void
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
    if (path === '/api/threads/t1/runs' && init.method === 'POST') return new Promise<Response>(resolve => { resolveRun = resolve })
    if (path === '/api/runs/r1') return Response.json(savedRun('r1'))
    return Response.json([])
  })
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '첫 질문' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  const currentInput = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(currentInput, { target: { value: '다음 질문 초안' } })
  await waitFor(() => expect(resolveRun).toBeTypeOf('function'))
  await act(async () => { resolveRun(new Response('event: run_started\ndata: {"run_id":"r1"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } })) })
  await waitFor(() => expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('다음 질문 초안'))
})

it('keeps a forwarded first question in the current composer when run acceptance fails', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1' })
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
    if (path === '/api/threads/t1/runs' && init.method === 'POST') return failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503)
    return Response.json([])
  })
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  fireEvent.change(await screen.findByRole('textbox', { name: '질문' }), { target: { value: 'D1 첫 질문 초안' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후 다시 시도해 주세요.')
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('D1 첫 질문 초안')
})

it('clears the accepted draft including whitespace once and preserves subsequent input', async () => {
  let accept!: (response: Response) => void
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1' })
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
    if (path === '/api/threads/t1/runs' && init.method === 'POST') return new Promise<Response>(resolve => { accept = resolve })
    if (path === '/api/runs/r1') return Response.json(savedRun('r1'))
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.change(await screen.findByRole('textbox', { name: '질문' }), { target: { value: '  D1 질문 초안  ' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  await waitFor(() => expect(accept).toBeTypeOf('function'))
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('  D1 질문 초안  ')
  await act(async () => { accept(new Response(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: ${JSON.stringify(savedRun('r1').result)}\n\n`)) })
  await waitFor(() => expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue(''))
  fireEvent.change(screen.getByRole('textbox', { name: '질문' }), { target: { value: '다음 질문은 유지' } })
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('다음 질문은 유지')
})

it('preserves the draft when the run request fails with a network error', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json(savedThread())
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    if (path === '/api/threads/t1/runs' && init.method === 'POST') throw new TypeError('Failed to fetch')
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  await screen.findByText('run-t1 저장된 답변')
  fireEvent.change(input, { target: { value: '네트워크 오류에도 보존할 질문' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('요청을 처리하지 못했습니다.')
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('네트워크 오류에도 보존할 질문')
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

it('shows a refused answer once in the same chat as the selected circuit', async () => {
  const answer = '요청하신 내용을 데이터시트에서 확인하지 못했어요.'
  const done = { answer, refusal: answer, status: 'refused', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], interrupt: {}, request_id: 'req-1' }
  api(`event: run_started\ndata: ${JSON.stringify({ run_id: 'r1' })}\n\nevent: refused\ndata: ${JSON.stringify(done)}\n\n`)
  await ask('D1의 대체 후보를 찾아 주세요.')
  expect(await screen.findAllByText(answer)).toHaveLength(1)
  const history = screen.getByRole('article', { name: '대화 기록' })
  expect(history).toContainElement(screen.getByText(answer))
  expect(history).toContainElement(screen.getByRole('heading', { level: 1, name: /D1/ }))
})

it('keeps the answer of an earlier question visible next to the selected one, reading each run once', async () => {
  const run = (id: string, answer: string) => ({ id, thread_id: 't1', message_id: null, result: { answer, status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: id } })
  const reads: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
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

const savedThread = (id = 't1', projectId = 1, ref = 'D1') => ({ id, project_id: projectId, title: `${id} 검토`, target_ref: ref, target_locked: true,
  latest_run: { id: `run-${id}`, status: 'completed', message_id: 2 }, next_before_message_id: null,
  messages: [{ id: 1, run_id: `run-${id}`, role: 'user', content: `${id} 저장된 질문`, created_at: '' }] })
const savedRun = (id: string) => ({ id, thread_id: id.replace('run-', ''), message_id: 2,
  result: { answer: `${id} 저장된 답변`, status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: '' } })

it('keeps a saved non-diode conversation readable without offering new replacement questions', async () => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json(savedThread('t1', 1, 'R1'))
    if (path === '/api/runs/run-t1') return Response.json(savedRun('run-t1'))
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByText('run-t1 저장된 답변')).toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: '질문' })).toBeNull()
  expect(screen.queryByRole('button', { name: '질문 보내기' })).toBeNull()
  expect(screen.queryByRole('button', { name: /R1.*SS34/ })).toBeNull()
  expect(writes).toEqual([])
})

it('loads earlier messages after a failed page request without losing selection, draft, or existing replies', async () => {
  const paths: string[] = []
  const writes: string[] = []
  let finish!: (response: Response) => void
  let resize!: () => void
  vi.stubGlobal('ResizeObserver', class {
    callback: () => void
    constructor(callback: () => void) { this.callback = callback }
    observe(element: Element) { if (element.classList.contains('chat-content')) resize = this.callback }
    disconnect() {}
  })
  const messages = Array.from({ length: 100 }, (_, index) => ({ id: index + 1, run_id: `run-${Math.floor(index / 2) + 1}`,
    role: index % 2 ? 'assistant' : 'user', content: index % 2 ? '보관된 답변' : `질문 ${Math.floor(index / 2) + 1}`, created_at: '' }))
  network((path, init) => {
    paths.push(path)
    if (init.method === 'POST') writes.push(path)
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: messages.slice(50), next_before_message_id: 51 })
    if (path === '/api/threads/t1?before_message_id=51') return new Promise<Response>(resolve => { finish = resolve })
    if (path.startsWith('/api/runs/')) return Response.json(path.endsWith('/run-26') ? candidateRun('run-26') : savedRun(path.split('/').pop()!))
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const selected = await screen.findByRole('button', { name: '질문 26' })
  fireEvent.click(selected)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  const sidebar = screen.getByRole('tabpanel', { name: 'SS34L · 질문 1' })
  sidebar.scrollTop = 55
  const area = screen.getByRole('article', { name: '대화 기록' })
  let scrollTop = 80
  let extraHeight = 0
  Object.defineProperty(area, 'scrollTop', { get: () => scrollTop, set: value => { scrollTop = value } })
  Object.defineProperty(area, 'getBoundingClientRect', { value: () => ({ top: 0 }) })
  Object.defineProperty(selected.closest('li'), 'getBoundingClientRect', { value: () => ({
    top: (screen.queryByRole('button', { name: '질문 1' }) ? 1200 : 200) + extraHeight - scrollTop, bottom: 300,
  }) })
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '작성 중인 질문' } })
  expect(screen.queryByRole('button', { name: '질문 1' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '이전 대화 불러오기' }))
  expect(screen.getByRole('button', { name: '이전 대화 불러오는 중' })).toBeDisabled()
  finish(failure('UNAVAILABLE', '일시적 조회 실패', 503))
  expect(await screen.findByRole('alert')).toHaveTextContent('이전 대화를 불러오지 못했습니다.')
  expect(selected).toHaveAttribute('aria-current', 'true')
  expect(screen.getByRole('button', { name: '질문 26' })).toBe(selected)
  expect(input).toHaveValue('작성 중인 질문')
  fireEvent.click(screen.getByRole('button', { name: '이전 대화 다시 불러오기' }))
  // Include the boundary run twice to verify it is not rendered twice.
  finish(Response.json({ ...savedThread(), messages: [...messages.slice(0, 50), messages[50]], next_before_message_id: null }))
  await screen.findByRole('button', { name: '질문 1' })
  expect(screen.queryByRole('button', { name: /이전 대화.*불러/ })).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(selected).toHaveAttribute('aria-current', 'true')
  expect(screen.getAllByRole('button', { name: '질문 26' })).toHaveLength(1)
  expect(screen.getByRole('button', { name: '질문 50' })).toBeInTheDocument()
  expect(input).toHaveValue('작성 중인 질문')
  expect(await screen.findByText('run-1 저장된 답변')).toBeInTheDocument()
  expect(scrollTop).toBe(1080)
  extraHeight = 80
  act(() => resize())
  expect(scrollTop).toBe(1160)
  fireEvent.wheel(area)
  extraHeight = 160
  act(() => resize())
  expect(scrollTop).toBe(1160)
  expect(screen.getByRole('tabpanel', { name: 'SS34L · 질문 26' })).toBe(sidebar)
  expect(sidebar.scrollTop).toBe(55)
  expect(writes).toEqual([])
  expect(paths.filter(path => path.includes('before_message_id'))).toEqual(['/api/threads/t1?before_message_id=51', '/api/threads/t1?before_message_id=51'])
})

it('keeps paging through an assistant-only boundary until the older question is available', async () => {
  const reads: string[] = []
  savedApi(id => {
    reads.push(id)
    if (id === 't1?before_message_id=51') return Response.json({ ...savedThread(),
      messages: [{ id: 50, run_id: 'old', role: 'assistant', content: '오래된 답변', created_at: '' }], next_before_message_id: 50 })
    if (id === 't1?before_message_id=50') return Response.json({ ...savedThread(),
      messages: [{ id: 49, run_id: 'old', role: 'user', content: '오래된 질문', created_at: '' }], next_before_message_id: null })
    return Response.json({ ...savedThread(), next_before_message_id: 51 })
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '이전 대화 불러오기' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '이전 대화 불러오기' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '이전 대화 불러오기' }))
  expect(await screen.findByText('오래된 질문')).toBeInTheDocument()
  expect(await screen.findByText('old 저장된 답변')).toBeInTheDocument()
  expect(screen.getByText('t1 저장된 질문')).toBeInTheDocument()
  expect(reads.filter(id => id.includes('?'))).toEqual(['t1?before_message_id=51', 't1?before_message_id=50'])
})

it('ignores an old page that arrives after switching conversations', async () => {
  let finish!: (response: Response) => void
  const writes = savedApi(id => id === 't1?before_message_id=51' ? new Promise<Response>(resolve => { finish = resolve })
    : Response.json({ ...savedThread(id), next_before_message_id: id === 't1' ? 51 : null }))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '이전 대화 불러오기' }))
  fireEvent.click(await screen.findByRole('button', { name: /t3 검토$/ }))
  await screen.findByText('t3 저장된 질문')
  await act(async () => { finish(Response.json({ ...savedThread(), next_before_message_id: null })); await Promise.resolve() })
  expect(screen.queryByText('t1 저장된 질문')).toBeNull()
  expect(screen.queryByRole('button', { name: /이전 대화.*불러/ })).toBeNull()
  expect(screen.getByText('t3 저장된 질문')).toBeInTheDocument()
  expect(writes).toEqual([])
})

it('shows reception stopped, blocks duplicate analysis, and restores the result with GET while preserving the draft', async () => {
  const posts: string[] = []
  let finish!: (response: Response) => void
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') posts.push(path)
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
    if (path === '/api/threads/t1/runs') return new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: run_started\ndata: {"run_id":"stopped-run"}\n\n'))
      init.signal?.addEventListener('abort', () => controller.error(init.signal?.reason), { once: true })
    } }))
    if (path === '/api/runs/stopped-run') return new Promise<Response>(resolve => { finish = resolve })
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('D1'))
  fireEvent.change(input, { target: { value: 'D1 질문' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  await screen.findByText('AI: 입력 확인')
  fireEvent.click(screen.getByRole('button', { name: '응답 받기 중단' }))
  expect(screen.getByText(/응답 수신 중단\. 서버의 검토/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '응답 받기 중단' })).not.toBeInTheDocument()
  expect(document.querySelector('.activity-steps .spin')).toBeNull()
  expect(screen.queryByText('검토 중입니다. 결과를 받으면 대화에서 확인할 수 있습니다.')).not.toBeInTheDocument()
  fireEvent.change(input, { target: { value: '다음 질문 초안' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  expect(posts).toEqual(['/api/threads/t1/runs'])
  fireEvent.click(screen.getByRole('button', { name: '실행 상태 다시 확인' }))
  expect(screen.getByRole('button', { name: '실행 상태 확인 중' })).toBeDisabled()
  finish(Response.json({ ...savedRun('stopped-run'), result: { ...savedRun('stopped-run').result, status: 'running' } }))
  expect(await screen.findByText('서버에서 아직 검토 중입니다. 잠시 후 실행 상태를 다시 확인해 주세요.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '실행 상태 다시 확인' }))
  finish(Response.json(savedRun('stopped-run')))
  expect(await screen.findByText('stopped-run 저장된 답변')).toBeInTheDocument()
  expect(input).toHaveValue('다음 질문 초안')
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  expect(posts).toEqual(['/api/threads/t1/runs'])
})

function savedApi(detail: (id: string) => Response | Promise<Response> = id => Response.json(savedThread(id, id === 't2' ? 2 : 1))) {
  const writes: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects') return Response.json([project, { ...project, id: 2, name: '다른 보드' }])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path.split('?')[0] === '/api/projects/2') return Response.json({ ...project, id: 2, name: '다른 보드' })
    if (path === '/api/projects/1/threads') return Response.json([savedThread(), savedThread('t3')])
    if (path === '/api/projects/2/threads') return Response.json([savedThread('t2', 2)])
    if (path.startsWith('/api/threads/')) return detail(path.split('/').pop()!)
    if (path.startsWith('/api/runs/')) return Response.json(savedRun(path.split('/').pop()!))
    return Response.json([])
  })
  return writes
}

it.each(['requires_input', 'limited', 'failed'])('restores an attached circuit run as %s instead of an empty judgement', async mode => {
  const writes: string[] = []
  let status = mode === 'failed' ? 'failed' : 'requires_input'
  const error = mode === 'requires_input' ? null : { code: 'LIMIT_EXCEEDED', message: '이번 분석의 실행 한도에 도달했습니다.' }
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path.split('?')[0] === '/api/projects/1') return Response.json({ ...project, circuit_version: 1 })
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), latest_run: { id: 'run-t1', status, message_id: null } })
    if (path.endsWith('/resume')) {
      expect(JSON.parse(String(init.body))).toEqual({ answers: { v_in_max: '12 V' } })
      if (mode === 'limited' && writes.length === 1) return new Response(`event: run_started\ndata: {"run_id":"run-t1"}\n\nevent: requires_input\ndata: ${JSON.stringify({ status, interrupt: { missing: ['v_in_max'] }, error })}\n\n`)
      status = 'completed'
      return new Response(`event: run_started\ndata: {"run_id":"run-t1"}\n\nevent: completed\ndata: ${JSON.stringify(savedRun('run-t1').result)}\n\n`)
    }
    if (path === '/api/runs/run-t1') return Response.json({ ...savedRun('run-t1'), message_id: null,
      result: { ...savedRun('run-t1').result, answer: status === 'completed' ? '검토를 마쳤습니다.' : '', status,
        interrupt: { missing: ['v_in_max'], question: '입력 전압을 알려 주세요.' }, error: status === 'completed' ? null : error } })
    return Response.json([])
  })
  const mount = () => renderWithQueries(<StrictMode><MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter></StrictMode>)
  mount()
  if (mode !== 'failed') expect(await screen.findByLabelText('입력 전원 최대 전압')).toBeInTheDocument()
  if (error) expect(await screen.findByRole('alert')).toHaveTextContent(error.message)
  expect(screen.queryByText('결과에 판정이 없습니다.')).toBeNull()
  expect(writes).toEqual([])
  cleanup(); mount()
  if (mode !== 'failed') expect(await screen.findByLabelText('입력 전원 최대 전압')).toBeInTheDocument()
  if (error) expect(await screen.findByRole('alert')).toHaveTextContent(error.message)
  expect(writes).toEqual([])
  if (mode !== 'failed') {
    fireEvent.change(screen.getByLabelText('입력 전원 최대 전압'), { target: { value: '12 V' } })
    fireEvent.click(screen.getByRole('button', { name: '이 값으로 계속 검토' }))
    if (mode === 'limited') {
      expect(await screen.findByRole('alert')).toHaveTextContent(error!.message)
      expect(screen.getByLabelText('입력 전원 최대 전압')).toHaveValue('12 V')
      expect(writes).toEqual(['/api/runs/run-t1/resume'])
      fireEvent.click(screen.getByRole('button', { name: '이 값으로 계속 검토' }))
    }
    await waitFor(() => expect(screen.queryByLabelText('입력 전원 최대 전압')).toBeNull())
    expect(screen.queryByRole('alert')).toBeNull()
    expect(writes).toEqual(Array(mode === 'limited' ? 2 : 1).fill('/api/runs/run-t1/resume'))
  }
})

it('shows the public resume error while retaining the live input form', async () => {
  api(waiting.replace(/"request_id":"req-2"/, '"error":{"code":"LIMIT_EXCEEDED","message":"실행 한도에 도달했습니다."},"request_id":"req-2"'))
  await ask('D1을 SS34로 바꿔도 되나요?')
  expect(await screen.findByRole('alert')).toHaveTextContent('실행 한도에 도달했습니다.')
  expect(screen.getByRole('button', { name: '이 값으로 계속 검토' })).toBeInTheDocument()
  expect(resumes).toHaveLength(0)
})

it.each(['', '&targetRef=D1', '&targetRef=R1'])('restores saved messages on a fresh mount in StrictMode with target query %s', async (target) => {
  const writes = savedApi()
  renderWithQueries(<StrictMode><MemoryRouter initialEntries={[`/app?projectId=1&threadId=t1${target}`]}><WorkbenchPage /></MemoryRouter></StrictMode>)
  expect(await screen.findByText('t1 저장된 질문')).toBeInTheDocument()
  expect(await screen.findByText('run-t1 저장된 답변', { selector: '.markdown-body span' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1, name: /D1/ })).toBeInTheDocument()
  expect(screen.queryByText(/이 검토의 대상 부품을 회로에서 찾지 못했습니다/)).toBeNull()
  expect(writes).toEqual([])
})

it('restores the selected conversation after visiting another project and returning', async () => {
  const writes = savedApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByText('t1 저장된 질문')
  fireEvent.click(screen.getAllByRole('button', { name: '프로젝트' })[0])
  fireEvent.click(await screen.findByRole('button', { name: '다른 보드' }))
  fireEvent.click(await screen.findByRole('button', { name: /t2 검토$/ }))
  await screen.findByText('t2 저장된 질문')
  fireEvent.click(screen.getAllByRole('button', { name: '프로젝트' })[0])
  fireEvent.click(await screen.findByRole('button', { name: '보드' }))
  fireEvent.click(await screen.findByRole('button', { name: /t1 검토$/ }))
  expect(await screen.findByText('t1 저장된 질문')).toBeInTheDocument()
  expect(await screen.findByText('run-t1 저장된 답변', { selector: '.markdown-body span' })).toBeInTheDocument()
  expect(screen.queryByText('t2 저장된 질문')).toBeNull()
  expect(writes).toEqual([])
})

it('keeps a pending thread lookup in a loading state and lets a failed lookup retry', async () => {
  let finish!: (response: Response) => void
  let attempts = 0
  savedApi(() => ++attempts === 1 ? new Promise<Response>(resolve => { finish = resolve }) : Response.json(savedThread()))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await waitFor(() => expect(attempts).toBe(1))
  expect(screen.queryByText(/이 검토의 대상 부품을 회로에서 찾지 못했습니다/)).toBeNull()
  finish(failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503))
  fireEvent.click(await screen.findByRole('button', { name: '대화 다시 불러오기' }))
  expect(await screen.findByText('t1 저장된 질문')).toBeInTheDocument()
})

it('ignores a late response from a conversation that was left while loading', async () => {
  let finish!: (response: Response) => void
  const writes = savedApi(id => id === 't1' ? new Promise<Response>(resolve => { finish = resolve }) : Response.json(savedThread(id)))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await waitFor(() => expect(finish).toBeDefined())
  const question = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(question, { target: { value: '기록 복원 중 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  fireEvent.keyDown(question, { key: 'Enter' })
  fireEvent.click(await screen.findByRole('button', { name: /t3 검토$/ }))
  await screen.findByText('t3 저장된 질문')
  await act(async () => { finish(Response.json(savedThread())); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(screen.getByText('t3 저장된 질문')).toBeInTheDocument()
  expect(screen.queryByText('t1 저장된 질문')).toBeNull()
  expect(writes).toEqual([])
})

it('does not display a conversation belonging to a different project in the address', async () => {
  savedApi(() => Response.json(savedThread('t1', 2)))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('이 프로젝트의 검토 기록이 아닙니다.')
  expect(screen.queryByText('t1 저장된 질문')).toBeNull()
  expect(screen.queryByRole('textbox', { name: '질문' })).toBeNull()
})

it('clears the saved conversation when starting a new review of the same part', async () => {
  savedApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByText('t1 저장된 질문')
  fireEvent.click(screen.getByRole('button', { name: '새 검토' }))
  await waitFor(() => expect(screen.queryByText('t1 저장된 질문')).toBeNull())
  expect(screen.queryByText('run-t1 저장된 답변')).toBeNull()
  const question = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(question, { target: { value: '새 검토 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
})

it('clears pending restoration when starting a new review without waiting for the old request', async () => {
  let finish!: (response: Response) => void
  savedApi(() => new Promise<Response>(resolve => { finish = resolve }))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(await screen.findByRole('button', { name: '새 검토' }))
  fireEvent.change(await screen.findByRole('textbox', { name: '질문' }), { target: { value: '새 검토 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  await act(async () => { finish(Response.json(savedThread())); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(screen.queryByText('t1 저장된 질문')).toBeNull()
})

const waiting = `event: run_started\ndata: ${JSON.stringify({ run_id: 'r1' })}\n\nevent: requires_input\ndata: ${JSON.stringify({ status: 'requires_input', interrupt: { question: '값을 알려 주세요.', missing: ['VF', 'IR'] }, request_id: 'req-2' })}\n\n`

it('scrolls the circuit and conversation together while preserving the sidebar, composer, draft and files', async () => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const chat = screen.getByRole('region', { name: '채팅' })
  const input = screen.getByRole('textbox', { name: '질문' })
  expect(chat).toContainElement(input)
  const history = within(chat).getByRole('article', { name: '대화 기록' })
  expect(history).toContainElement(within(chat).getByRole('heading', { name: /^회로$/ }))
  expect(history).toContainElement(screen.getByRole('heading', { level: 1, name: /D1/ }))
  expect(history).not.toContainElement(input)
  fireEvent.change(input, { target: { value: '작성 중인 질문' } })
  fireEvent.change(input.closest('form')!.querySelector('input[type=file]')!, { target: { files: [new File(['test'], 'draft.net')] } })
  const end = screen.getByText('대화 끝').parentElement!
  const area = screen.getByRole('article', { name: '대화 기록' })
  const outside = screen.getByRole('region', { name: '검토 내용' })
  const sidebar = screen.getByRole('tabpanel')
  outside.scrollTop = 37
  sidebar.scrollTop = 55
  let bottom = 400
  let position = 0
  Object.defineProperty(area, 'getBoundingClientRect', { value: () => ({ bottom: 500 }) })
  Object.defineProperty(area, 'scrollHeight', { value: 900 })
  Object.defineProperty(area, 'scrollTop', { get: () => position, set: value => { position = value; bottom = 490 } })
  Object.defineProperty(end, 'getBoundingClientRect', { value: () => ({ bottom }) })
  const ancestorScroll = vi.fn()
  Object.defineProperty(end, 'scrollIntoView', { value: ancestorScroll })
  fireEvent.scroll(area)
  expect(screen.queryByRole('button', { name: '대화 맨 아래로 이동' })).toBeNull()
  bottom = 900
  fireEvent.scroll(outside)
  expect(screen.queryByRole('button', { name: '대화 맨 아래로 이동' })).toBeNull()
  fireEvent.scroll(area)
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  fireEvent.click(screen.getByRole('button', { name: '대화 맨 아래로 이동' }))
  expect(position).toBe(900)
  expect(outside.scrollTop).toBe(37)
  expect(sidebar.scrollTop).toBe(55)
  expect(ancestorScroll).not.toHaveBeenCalled()
  expect(input).toHaveValue('작성 중인 질문')
  expect(input).toHaveFocus()
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('draft.net')
  expect(screen.queryByRole('button', { name: '대화 맨 아래로 이동' })).toBeNull()
  expect(requests).not.toHaveBeenCalled()
})

it('updates the jump button when content or viewport size changes without forcing a scroll', async () => {
  candidateApi()
  const resized: (() => void)[] = []
  vi.stubGlobal('ResizeObserver', class { constructor(callback: () => void) { resized.push(callback) } observe() {} disconnect() {} })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const end = screen.getByText('대화 끝').parentElement!
  const area = screen.getByRole('article', { name: '대화 기록' })
  let bottom = 900
  Object.defineProperty(area, 'getBoundingClientRect', { value: () => ({ bottom: 500 }) })
  Object.defineProperty(end, 'getBoundingClientRect', { value: () => ({ bottom }) })
  const scroll = vi.fn()
  Object.defineProperty(end, 'scrollIntoView', { value: scroll })
  act(() => resized.forEach(callback => callback()))
  expect(screen.getByRole('button', { name: '대화 맨 아래로 이동' })).toBeInTheDocument()
  bottom = 400
  act(() => resized.forEach(callback => callback()))
  expect(screen.queryByRole('button', { name: '대화 맨 아래로 이동' })).toBeNull()
  expect(scroll).not.toHaveBeenCalled()
})

function candidateRun(id: string, value = 40) {
  const base = savedRun(id)
  const citation = { document: `${id}-SS34L.pdf`, page: 2, table: 'MAXIMUM RATINGS', row: 'VRRM', source_url: 'https://example.test/ss34l.pdf' }
  const candidate = { part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: true, cautions: ['극성을 확인해 주세요.'],
    checks: [{ code: 'VRRM', basis: `${id} 사용 조건`, threshold: 15, value, unit: 'V', op: '>=', result: 'pass', citation }] }
  return { ...base, message_id: id === 'r1' ? 101 : 102, result: { ...base.result,
    answer: '역할: R01 (근거: 직렬 연결)\n\n**SS34L: 역할상 충분**\n\n| 조건 | 근거 |\n|---|---|\n| VRRM | 반복 표 본문 |\n\n같은 동작은 보장하지 않습니다.',
    judgement: { kind: 'find', roles: [], role_evidence: ['직렬 연결'], results: [], shown: [candidate,
      { part: '1N5819', verdict: 'NOT_VERIFIED', missing: ['VF'], checks: [{ ...candidate.checks[0], value: 20, result: 'unverified', citation: { ...citation, document: `${id}-1N5819.pdf`, source_url: 'https://example.test/1n5819.pdf' } }] }], unverified: [], capped: true },
    evidence: [{ ...citation, section: '', citation_number: '7' }] } }
}
function candidateApi(twoQuestions = false, readRun: (id: string) => unknown = id => candidateRun(id, id === 'r1' ? 40 : 100), stored: ApprovalDto[] = []) {
  const approvals: { path: string; body: unknown }[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [
      { id: 1, run_id: 'r1', role: 'user', content: '첫 후보 질문', created_at: '' },
      ...(twoQuestions ? [{ id: 3, run_id: 'r2', role: 'user', content: '둘째 후보 질문', created_at: '' }] : []),
    ] })
    if (path === '/api/runs/r1' || path === '/api/runs/r2') return Response.json(readRun(path.endsWith('r1') ? 'r1' : 'r2'))
    const message = path.match(/^\/api\/messages\/(\d+)\/approvals$/)
    if (message && init.method !== 'POST') return Response.json(stored.filter(item => item.message_id === Number(message[1])))
    if (message) {
      const body = JSON.parse(String(init.body))
      approvals.push({ path, body })
      const saved = { id: stored.length + 1, message_id: Number(message[1]), candidate_part: body.candidate_part, verdict: body.verdict, case_id: 1 }
      stored.push(saved)
      return Response.json(saved, { status: 201 })
    }
    return Response.json([])
  })
  return approvals
}

it('restores saved approval after closing and reopening a tab and after a fresh page mount', async () => {
  const stored: ApprovalDto[] = []
  const writes = candidateApi(false, id => candidateRun(id), stored)
  let view = renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await waitFor(() => expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '검토하고 승인' }))
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'SS34L · 질문 1 닫기' }))
  fireEvent.click(screen.getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '검토하고 승인' })).toBeNull()
  view.unmount()
  view = renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await screen.findByText('승인됨')).toBeInTheDocument()
  expect(writes).toHaveLength(1)
})

it.each([false, true])('refreshes approval after a case deletion and preserves the lock on failure=%s', async fails => {
  const stored: ApprovalDto[] = [{ id: 7, message_id: 101, candidate_part: '1N5391G', verdict: 'ROLE_SUFFICIENT', case_id: 41 }]
  const writes = candidateApi(false, id => candidateRun(id), stored)
  const base = globalThis.fetch
  network((path, init) => {
    if (path === '/api/approved-cases') return Response.json(stored.map(item => ({ id: item.case_id, approval_id: item.id, candidate_part: item.candidate_part, verdict: item.verdict })))
    if (path === '/api/approved-cases/41' && init.method === 'DELETE') {
      if (fails) return failure('UNAVAILABLE', '삭제 실패', 503)
      stored.splice(0)
      return new Response(null, { status: 204 })
    }
    return base(path, init)
  })
  const Cases = (await vi.importActual<typeof import('../components/ApprovedCases')>('../components/ApprovedCases')).default
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /><Cases /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await screen.findByText('다른 후보가 승인됨')).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button', { name: '1N5391G 사례 삭제' }))
  fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  if (fails) {
    expect(await screen.findByText(/사례를 삭제하지 못했습니다/)).toBeInTheDocument()
    expect(screen.getByText('다른 후보가 승인됨')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '검토하고 승인' })).toBeNull()
    expect(writes).toHaveLength(0)
  } else {
    await waitFor(() => expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '검토하고 승인' }))
    expect(await screen.findByText('승인됨')).toBeInTheDocument()
    expect(writes).toHaveLength(1)
    expect(writes[0].body).toMatchObject({ candidate_part: 'SS34L' })
  }
})

it('matches a persisted approval to its message instead of another question with the same part', async () => {
  candidateApi(true, id => candidateRun(id), [{ id: 1, message_id: 101, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 1 }])
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = (await screen.findByText('첫 후보 질문')).closest('li')!
  fireEvent.click(await within(first).findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('tabpanel')).findByText('승인됨')).toBeInTheDocument()
  const second = screen.getByText('둘째 후보 질문').closest('li')!
  fireEvent.click(within(second).getByRole('button', { name: /SS34L.*상세 보기/ }))
  await waitFor(() => expect(within(screen.getByRole('tabpanel')).getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
  expect(within(screen.getByRole('tabpanel')).queryByText('승인됨')).toBeNull()
})

it.each(['other', 'error', 'conflict'])('handles approval lookup state %s without a duplicate approval', async mode => {
  candidateApi()
  const base = fetch
  const record: ApprovalDto = { id: 1, message_id: 101, candidate_part: mode === 'other' ? '다른 후보' : 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: null }
  let reads = 0, posts = 0
  network((path, init) => {
    if (path === '/api/messages/101/approvals') {
      if (init.method === 'POST') { posts++; return failure('ALREADY_APPROVED', '이미 승인되었습니다.', 409) }
      reads++
      if (mode === 'error' && reads === 1) return failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503)
      return Response.json(mode === 'other' || posts ? [record] : [])
    }
    return base(path, init)
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  if (mode === 'other') {
    expect(await screen.findByText('다른 후보가 승인됨')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '검토하고 승인' })).toBeNull()
  } else {
    if (mode === 'error') {
      expect(await screen.findByRole('alert')).toHaveTextContent('승인 상태를 불러오지 못했습니다.')
      expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeDisabled()
      fireEvent.click(screen.getByRole('button', { name: '승인 상태 다시 확인' }))
    }
    await waitFor(() => expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
    if (mode === 'conflict') {
      fireEvent.click(screen.getByRole('button', { name: '검토하고 승인' }))
      expect(await screen.findByText('승인됨')).toBeInTheDocument()
      expect(screen.queryByRole('alert')).toBeNull()
    }
  }
  expect(posts).toBe(mode === 'conflict' ? 1 : 0)
})

it('distinguishes saved message senders without exposing profile details and preserves question selection', async () => {
  candidateApi(true)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = await screen.findByRole('group', { name: '내 메시지 1' })
  expect(screen.getByRole('group', { name: '내 메시지 2' })).toHaveTextContent('둘째 후보 질문')
  const activity = screen.getByRole('region', { name: '활동' })
  await within(activity).findAllByRole('group', { name: 'AI 답변' })
  expect(within(activity).queryByText(user.email)).toBeNull()
  expect(within(activity).queryByText('SojaFit')).toBeNull()
  expect(within(activity).queryByText('선택됨')).toBeNull()
  expect(activity.querySelector('img')).toBeNull()
  expect(activity.querySelector(`[title="${user.email}"]`)).toBeNull()
  fireEvent.click(within(first).getByRole('button', { name: '첫 후보 질문' }))
  expect(within(first).getByRole('button')).toHaveAttribute('aria-current', 'true')
  fireEvent.click(await within(first.closest('li')!).findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('complementary', { name: '부품 상세' })).findByText('40 V')).toBeInTheDocument()
})

it('uses anonymous sender groups for live messages while retaining the reply actions', async () => {
  api(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: ${JSON.stringify(candidateRun('r1').result)}\n\n`)
  await ask('D1의 대체품을 알려 주세요.')
  expect(await screen.findByRole('group', { name: '내 메시지 1' })).toHaveTextContent('D1의 대체품을 알려 주세요.')
  const answer = await screen.findByRole('group', { name: 'AI 답변' })
  expect(within(answer).getByRole('button', { name: /SS34L.*상세 보기/ })).toBeInTheDocument()
  const activity = screen.getByRole('region', { name: '활동' })
  expect(within(activity).queryByText(user.email)).toBeNull()
  expect(within(activity).queryByText('SojaFit')).toBeNull()
  expect(activity.querySelector('img')).toBeNull()
  expect(runs).toHaveLength(1)
})

it('attaches a dropped netlist anywhere on the active workbench without sending the draft', async () => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '작성 중인 질문' } })
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  const rail = screen.getByRole('navigation', { name: '프로젝트와 검토' })
  const transfer = { types: ['Files'], files: [new File(['(export)'], 'board.NET', { lastModified: 1 })] }
  expect(fireEvent.drop(rail, { dataTransfer: transfer })).toBe(false)
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('board.NET')
  expect(input).toHaveValue('작성 중인 질문')
  expect(input).toHaveFocus()
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  expect(input).toHaveValue('작성 중인 질문')
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('board.NET')
  expect(requests).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'board.NET 첨부 취소' }))
  expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
})

it('rejects a multi-file drop without replacing the existing attachment or draft', async () => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const file = new File(['(export)'], 'board.net', { lastModified: 1 })
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '기존 질문 초안' } })
  const picker = screen.getByRole('textbox', { name: '질문' }).closest('form')!.querySelector('input[type=file]')!
  fireEvent.change(picker, { target: { files: [file] } })
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [file, new File(['memo'], 'notes.txt'), new File(['x'], 'bad.pdf'), new File([], 'empty.net'), new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.net')] } })
  const attached = screen.getByRole('list', { name: '첨부한 파일' })
  expect(within(attached).getAllByRole('listitem')).toHaveLength(1)
  expect(attached).toHaveTextContent('board.net')
  expect(attached).not.toHaveTextContent('notes.txt')
  expect(screen.getByRole('alert')).toHaveTextContent('한 번에 하나')
  expect(input).toHaveValue('기존 질문 초안')
  fireEvent.click(screen.getByRole('button', { name: '첨부 안내 닫기' }))
  expect(screen.queryByRole('alert')).toBeNull()
})

it('shows and clears the drag guide and leaves text dragging alone', async () => {
  candidateApi()
  const view = renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const transfer = { types: ['Files'], files: [] }
  fireEvent.dragEnter(window, { dataTransfer: transfer })
  fireEvent.dragEnter(screen.getByRole('textbox', { name: '질문' }), { dataTransfer: transfer })
  fireEvent.dragLeave(screen.getByRole('textbox', { name: '질문' }), { dataTransfer: transfer })
  expect(screen.getByRole('status', { name: '파일 놓기' })).toBeInTheDocument()
  fireEvent.dragLeave(window, { dataTransfer: transfer })
  expect(screen.queryByRole('status', { name: '파일 놓기' })).toBeNull()
  expect(fireEvent.drop(window, { dataTransfer: { types: ['text/plain'], files: [] } })).toBe(true)
  expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
  view.unmount()
  expect(fireEvent.drop(window, { dataTransfer: transfer })).toBe(true)
})

it('previews local built attachments without sending until the user submits', async () => {
  vi.stubEnv('DEV', false)
  vi.stubEnv('VITE_LOCAL_ATTACHMENT_UI', '1')
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '첨부와 함께 작성한 질문' } })
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  expect(screen.getByRole('button', { name: '파일 첨부 (.net, .txt)' })).toBeEnabled()
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['(export)'], 'local.net')] } })
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('local.net')
  expect(screen.getByText(/전송하면 같은 프로젝트의 새 회로 버전/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  expect(requests).not.toHaveBeenCalled()
  expect(input).toHaveValue('첨부와 함께 작성한 질문')
  fireEvent.click(screen.getByRole('button', { name: 'local.net 첨부 취소' }))
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
})

it('accepts production attachments without sending before explicit submit', async () => {
  vi.stubEnv('DEV', false)
  vi.stubEnv('VITE_LOCAL_ATTACHMENT_UI', '0')
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  expect(fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['(export)'], 'board.net')] } })).toBe(false)
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('board.net')
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  expect(requests).not.toHaveBeenCalled()
})

it('does not attach to the conversation behind an open dialog', async () => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const dialog = document.createElement('dialog')
  dialog.open = true
  document.body.append(dialog)
  try {
    const transfer = { types: ['Files'], files: [new File(['(export)'], 'board.net')] }
    fireEvent.dragEnter(dialog, { dataTransfer: transfer })
    expect(screen.queryByRole('status', { name: '파일 놓기' })).toBeNull()
    expect(fireEvent.drop(dialog, { dataTransfer: transfer })).toBe(false)
    expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
    const picker = document.createElement('input')
    picker.type = 'file'
    dialog.append(picker)
    expect(fireEvent.drop(picker, { dataTransfer: transfer })).toBe(true)
    expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
  } finally { dialog.remove() }
})

it('keeps multiple detail tabs with the correct question and preserves approval when switching back', async () => {
  const approvals = candidateApi(true)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = (await screen.findByText('첫 후보 질문')).closest('li')!
  const second = (await screen.findByText('둘째 후보 질문')).closest('li')!
  fireEvent.click(await within(first).findByRole('button', { name: /SS34L.*상세 보기/ }))
  let panel = screen.getByRole('tabpanel')
  await waitFor(() => expect(within(panel).getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
  fireEvent.click(within(panel).getByRole('button', { name: '검토하고 승인' }))
  await waitFor(() => expect(approvals).toHaveLength(1))
  fireEvent.click(within(second).getByRole('button', { name: /SS34L.*상세 보기/ }))
  panel = screen.getByRole('tabpanel')
  expect(within(panel).getByText('100 V')).toBeVisible()
  fireEvent.click(screen.getByRole('tab', { name: 'SS34L · 질문 1' }))
  panel = screen.getByRole('tabpanel')
  expect(within(panel).getByText('40 V')).toBeVisible()
  expect(within(panel).getByText('승인됨')).toBeVisible()
  expect(approvals).toHaveLength(1)
  expect(screen.getAllByRole('tab')).toHaveLength(3)
  fireEvent.click(within(first).getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(screen.getAllByRole('tab')).toHaveLength(3)
  fireEvent.keyDown(screen.getByRole('tab', { name: 'SS34L · 질문 1' }), { key: 'Delete' })
  expect(screen.queryByRole('tab', { name: 'SS34L · 질문 1' })).toBeNull()
  expect(screen.getByRole('tab', { name: 'SS34L · 질문 2' })).toHaveFocus()
  fireEvent.click(screen.getByRole('tab', { name: '회로 정보' }))
  expect(screen.getByRole('tabpanel', { name: '회로 정보' })).toBeVisible()
  expect(screen.getByRole('complementary', { name: '부품 상세' })).toHaveClass('props-open')
})

it('shows concise part links and opens the chosen candidate checks and evidence only in the sidebar', async () => {
  const approvals = candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const second = await screen.findByRole('button', { name: /1N5819.*상세 보기/ })
  expect(screen.getByText('후보 2개의 검토 결과를 정리했어요.')).toBeInTheDocument()
  expect(screen.getByText(/검색이 후보 수 상한/)).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByText(/상세 보기를 선택/)).toBeInTheDocument()
  expect(screen.queryByText('반복 표 본문')).toBeNull()
  expect(within(screen.getByRole('article')).queryByRole('table')).toBeNull()
  fireEvent.click(second)
  expect(await within(screen.getByRole('tabpanel')).findByRole('heading', { name: '1N5819' })).toHaveFocus()
  expect(within(screen.getByRole('tabpanel')).getByText('20 V')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByText('문서에 없는 값: VF')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByText('r1-1N5819.pdf')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).queryByText('r1-SS34L.pdf')).toBeNull()
  expect(within(screen.getByRole('tabpanel')).queryByRole('heading', { name: '근거' })).toBeNull()
  expect(within(screen.getByRole('tabpanel')).getByRole('button', { name: '검토하고 승인' })).toBeDisabled()
  expect(approvals).toEqual([])
  fireEvent.click(screen.getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('tabpanel')).findByText('40 V')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByText('극성을 확인해 주세요.')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /r1-SS34L.pdf/ })).toHaveAttribute('href', 'https://example.test/ss34l.pdf#page=2')
  expect(within(screen.getByRole('tabpanel')).queryByText('r1-1N5819.pdf')).toBeNull()
})

it('keeps a past question candidate, its values and approval message together', async () => {
  const approvals = candidateApi(true)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = (await screen.findByText('첫 후보 질문')).closest('li')!
  const second = (await screen.findByText('둘째 후보 질문')).closest('li')!
  fireEvent.click(await within(second).findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('tabpanel')).findByText('100 V')).toBeInTheDocument()
  fireEvent.click(within(first).getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('tabpanel')).findByText('40 V')).toBeInTheDocument()
  await waitFor(() => expect(within(screen.getByRole('tabpanel')).getByRole('button', { name: '검토하고 승인' })).toBeEnabled())
  fireEvent.click(within(screen.getByRole('tabpanel')).getByRole('button', { name: '검토하고 승인' }))
  await waitFor(() => expect(approvals).toHaveLength(1))
  expect(approvals[0]).toEqual({ path: '/api/messages/101/approvals', body: { candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' } })
  fireEvent.click(screen.getByRole('button', { name: '새 검토' }))
  expect(screen.queryByRole('heading', { name: 'SS34L' })).toBeNull()
  expect(screen.queryByRole('tab', { name: 'SS34L · 질문 1' })).toBeNull()
})

it('preserves the full answer and document list for questions without candidate judgements', async () => {
  candidateApi(false, id => {
    const run = savedRun(id)
    return { ...run, result: { ...run.result, answer: '문서 질문 설명\n\n| 항목 | 값 |\n|---|---|\n| 마킹 | ABC123 |',
      evidence: [{ document: 'document-answer.pdf', page: 1, table: '', row: '', section: '', citation_number: '3', source_url: 'https://example.test/document-answer.pdf' }] } }
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByText('문서 질문 설명')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'ABC123' })).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /document-answer.pdf/ })).toHaveAttribute('href', 'https://example.test/document-answer.pdf#page=1')
  expect(screen.queryByRole('button', { name: /SS34L.*상세 보기/ })).toBeNull()
})

it('opens a candidate from a live completed response without starting another run', async () => {
  api(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: ${JSON.stringify(candidateRun('r1').result)}\n\n`)
  await ask('D1의 후보를 찾아 주세요.')
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(screen.getByRole('tabpanel')).findByText('40 V')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByRole('heading', { name: 'SS34L' })).toHaveFocus()
  expect(runs).toHaveLength(1)
})

it('preserves package evidence separately from the condition evidence', async () => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    Object.assign(run.result.judgement.shown[0], { package_citation: { document: 'package.pdf', page: 4, table: 'PACKAGE OUTLINE', row: 'SMA', source_url: 'https://example.test/package.pdf' } })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /package.pdf/ })).toHaveAttribute('href', 'https://example.test/package.pdf#page=4')
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /r1-SS34L.pdf/ })).toBeInTheDocument()
})

it.each(['before', 'after'])('preserves document explanations %s a judgement and their additional sources', async position => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    const prose = '마킹은 ABC123입니다 [8].'
    run.result.answer = position === 'before' ? `${prose}\n\n${run.result.answer}` : `${run.result.answer}\n\n${prose}`
    run.result.evidence.push({ document: 'marking.pdf', page: 1, table: '', row: '', source_url: 'https://example.test/marking.pdf', section: '', citation_number: '8' })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  expect(await screen.findByText('마킹은 ABC123입니다.')).toBeInTheDocument()
  expect(within(screen.getByRole('article')).queryByRole('table')).toBeNull()
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /marking.pdf/ })).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).queryByText('r1-SS34L.pdf')).toBeNull()
})

it('keeps comparison values and uncertainty visible while revealing the condition evidence on demand', async () => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    Object.assign(run.result.judgement.shown[1].checks[0], { condition: 'VR=100V, TJ=25°C', why: '시험 역전압이 실제 역전압보다 높아 불충족을 단정할 수 없음' })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /1N5819.*상세 보기/ }))
  const panel = screen.getByRole('tabpanel')
  expect(within(panel).getByText('20 V')).toBeVisible()
  expect(within(panel).getByText('≥ 15 V')).toBeVisible()
  const detail = within(panel).getByText('VRRM', { selector: 'strong' }).closest('details')!
  expect(detail).not.toHaveAttribute('open')
  expect(within(panel).getByText('VR=100V, TJ=25°C')).not.toBeVisible()
  expect(within(screen.getByRole('tabpanel')).getByText('시험 역전압이 실제 역전압보다 높아 불충족을 단정할 수 없음')).toBeVisible()
  fireEvent.click(detail.querySelector('summary')!)
  expect(detail).toHaveAttribute('open')
  expect(within(panel).getByText('VR=100V, TJ=25°C')).toBeVisible()
  expect(within(panel).getByRole('link', { name: /r1-1N5819.pdf/ })).toHaveAttribute('href', 'https://example.test/1n5819.pdf#page=2')
  fireEvent.click(screen.getByRole('button', { name: /SS34L.*상세 보기/ }))
  fireEvent.click(screen.getByRole('tab', { name: '1N5819 · 질문 1' }))
  expect(detail).toHaveAttribute('open')
  expect(within(screen.getByRole('tabpanel')).getByText('역할 근거: 직렬 연결')).toBeVisible()
})

it('keeps repeated condition codes as separate disclosures with their own criteria', async () => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    const checks = run.result.judgement.shown[0].checks
    checks.push({ ...checks[0], basis: '추가 역전압 조건', threshold: 20 })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  const panel = screen.getByRole('tabpanel')
  const conditions = within(panel).getAllByText('VRRM', { selector: 'strong' }).map(item => item.closest('details')!)
  expect(conditions).toHaveLength(2)
  expect(within(panel).getByText('≥ 15 V')).toBeVisible()
  expect(within(panel).getByText('≥ 20 V')).toBeVisible()
  fireEvent.click(conditions[0].querySelector('summary')!)
  expect(conditions[0]).toHaveAttribute('open')
  expect(conditions[1]).not.toHaveAttribute('open')
})

function citedDocumentRun(id: string) {
  const run = savedRun(id)
  return { ...run, result: { ...run.result,
    answer: '**역전압 400 V [2171]**입니다 [2171, 2172].\n\n| 항목 | 값 |\n|---|---|\n| 누설 | 5 µA [2172] |\n\n범위 [0.60 V]와 [2026]은 원문입니다.\n\n추가 표식 [2171, 9999]과 [2172, 넷리스트].\n\n`array[2171]`\n\n```\narray[2172]\n```',
    evidence: [1, 2].map(page => ({ document: `${id}-datasheet.pdf`, page, table: 'ELECTRICAL CHARACTERISTICS', row: page === 1 ? 'VRRM' : 'IR', section: '', citation_number: page === 1 ? '2171' : '2172', source_url: `https://example.test/${id}.pdf${page === 2 ? '#page=2' : ''}` })) } }
}

it('hides corpus citations and opens the selected past answer sources including separate pages', async () => {
  candidateApi(true, citedDocumentRun)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = (await screen.findByText('첫 후보 질문')).closest('li')!
  const open = await within(first).findByRole('button', { name: '문서 근거 보기' })
  expect(within(first).getByText('역전압 400 V')).toBeInTheDocument()
  expect(within(first).getByRole('cell', { name: '5 µA' })).toBeInTheDocument()
  expect(within(first).getByText('범위 [0.60 V]와 [2026]은 원문입니다.')).toBeInTheDocument()
  expect(within(first).getByText('추가 표식 [9999]과 [넷리스트].')).toBeInTheDocument()
  expect(within(first).getByText('array[2171]')).toBeInTheDocument()
  expect(within(first).getByText('array[2172]')).toBeInTheDocument()
  fireEvent.click(open)
  expect(await within(screen.getByRole('tabpanel')).findByRole('heading', { name: '근거' })).toHaveFocus()
  const links = within(screen.getByRole('tabpanel')).getAllByRole('link', { name: /r1-datasheet.pdf/ })
  expect(links.map(link => link.getAttribute('href'))).toEqual(['https://example.test/r1.pdf#page=1', 'https://example.test/r1.pdf#page=2'])
  expect(within(screen.getByRole('tabpanel')).getByText('1쪽 · ELECTRICAL CHARACTERISTICS · VRRM')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).getByText('2쪽 · ELECTRICAL CHARACTERISTICS · IR')).toBeInTheDocument()
  expect(within(screen.getByRole('tabpanel')).queryByText('r2-datasheet.pdf')).toBeNull()
})

it('hides citations and opens sidebar evidence directly from a live document answer without a new run', async () => {
  api(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: ${JSON.stringify(citedDocumentRun('r1').result)}\n\n`)
  await ask('D1의 데이터시트를 설명해 주세요.')
  const open = await screen.findByRole('button', { name: '문서 근거 보기' })
  expect(screen.getByText('역전압 400 V')).toBeInTheDocument()
  fireEvent.click(open)
  expect(screen.getByRole('heading', { name: '근거' })).toHaveFocus()
  expect(screen.getAllByRole('link', { name: /r1-datasheet.pdf/ })).toHaveLength(2)
  expect(runs).toHaveLength(1)
})

it('keeps additional document pages when a candidate cites another page of the same file', async () => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    const otherPage = { ...run.result.evidence[0], page: 5, row: 'MARKING', citation_number: '8' }
    run.result.evidence.push(otherPage)
    run.result.answer += '\n\n마킹 설명입니다 [8].'
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '문서 근거 보기' }))
  expect(within(screen.getByRole('tabpanel')).getByRole('heading', { name: '추가 문서 근거' })).toHaveFocus()
  expect(within(screen.getByRole('tabpanel')).getByRole('link', { name: /r1-SS34L.pdf/ })).toHaveAttribute('href', 'https://example.test/ss34l.pdf#page=5')
  expect(within(screen.getByRole('tabpanel')).getByText('5쪽 · MAXIMUM RATINGS · MARKING')).toBeInTheDocument()
  expect(screen.getByText('마킹 설명입니다.')).toBeInTheDocument()
})

it('resumes with only the filled condition when the other is left blank', async () => {
  api(waiting)
  await ask('D1을 SS34로 바꿔도 되나요?')
  fireEvent.change(await screen.findByLabelText('허용 전압 강하'), { target: { value: ' 0.4 V ' } })
  fireEvent.click(screen.getByRole('button', { name: '이 값으로 계속 검토' }))
  await waitFor(() => expect(resumes).toHaveLength(1))
  expect(resumes[0]).toEqual({ answers: { VF: '0.4 V' } })
})

it('shows condition-specific units and examples while submitting the original input', async () => {
  const fields = [
    ['i_limit', 'IC 전류 제한값', '예: 1 A'],
    ['hot_test', '누설을 볼 고온 사용 온도', '예: TJ=125 °C'],
    ['v_in_max', '입력 전원 최대 전압', '예: 12 V'],
    ['IR', '허용 누설 전류', '예: 10 µA'],
    ['temp', '사용 온도', '예: TA=25 °C'],
    ['vf_test', 'VF를 볼 전류 · 온도', '예: IF=1 A, TJ=25 °C'],
    ['pulse_test', '코일 차단 펄스(전류 · 폭)', '예: IF=1 A, t=10 ms'],
    ['surge_test', '서지 파형(예: 8/20µs)', '예: 8/20 µs'],
    ['c_hold', '피크 홀드 커패시터', '예: 10 µF'],
    ['droop_allowed', '허용 전압 감소율', 'V/s 기준 숫자만 입력. 예: 0.1'],
    ['err_allowed', '허용 오차', '예: 1 %'],
    ['ns_np', '변압기 권선비 Ns/Np', '권선비를 숫자로 입력. 예: 0.5'],
    ['n_diodes', '직렬 다이오드 개수', '개수를 숫자로 입력. 예: 2'],
    ['pwm', 'PWM으로 스위칭하나요? (예/아니오)', '예 또는 아니오'],
    ['op_amp', '연산증폭기 사용', '예 또는 아니오'],
    ['unknown', '추가 조건', '아는 값을 입력해 주세요. 모르면 비워 두세요.'],
  ]
  api(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: requires_input\ndata: ${JSON.stringify({ status: 'requires_input', interrupt: { missing: fields.map(([code]) => code) } })}\n\n`)
  await ask('D1의 추가 조건을 확인해 주세요.')
  await screen.findByLabelText('IC 전류 제한값')
  for (const [, label, placeholder] of fields) {
    expect(screen.getByLabelText(label)).toHaveAttribute('placeholder', placeholder)
    expect(screen.getByLabelText(label)).toHaveValue('')
  }
  fireEvent.change(screen.getByLabelText('IC 전류 제한값'), { target: { value: '150 mA' } })
  fireEvent.change(screen.getByLabelText('누설을 볼 고온 사용 온도'), { target: { value: 'TJ=100 °C' } })
  fireEvent.click(screen.getByRole('button', { name: '이 값으로 계속 검토' }))
  await waitFor(() => expect(resumes).toHaveLength(1))
  expect(resumes[0]).toEqual({ answers: { i_limit: '150 mA', hot_test: 'TJ=100 °C' } })
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

it.each(['missing', 'unverified'])('blocks positive candidate with required condition %s', async mode => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    const candidate = run.result.judgement.shown[0]
    Object.assign(candidate, mode === 'missing' ? { missing: ['v_in_max'] } : { checks: [{ code: 'VRRM', tier: 'required', result: 'unverified' }] })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await screen.findByText('승인 전')
  await waitFor(() => expect(screen.getByRole('button', { name: '검토하고 승인' })).toBeDisabled())
})

it('restores a saved quote when the workbench mounts again', async () => {
  const stored = [{ id: 7, message_id: 101, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 41 }]
  candidateApi(false, id => candidateRun(id), stored)
  const base = globalThis.fetch
  const quotes: { id: number; approval_id: number; part_number: string; quantity: number }[] = []
  network((path, init) => {
    if (path === '/api/projects/1/quotes') return Response.json(quotes)
    if (path === '/api/approvals/7/quotes' && init.method === 'POST') {
      const quote = { id: quotes.length + 1, approval_id: 7, part_number: 'SS34L', quantity: JSON.parse(String(init.body)).quantity }
      quotes.push(quote)
      return Response.json(quote, { status: 201 })
    }
    return base(path, init)
  })
  const show = () => renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  show()
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  fireEvent.change(await screen.findByRole('spinbutton', { name: '수량' }), { target: { value: '25' } })
  fireEvent.click(screen.getByRole('button', { name: '견적 저장' }))
  expect(await screen.findByText('견적 SS34L × 25')).toBeInTheDocument()
  expect(quotes).toHaveLength(1)
  cleanup()
  show()
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await screen.findByText('승인됨')
  expect(await screen.findByText('견적 SS34L × 25')).toBeInTheDocument()
  expect(quotes).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '새 견적 작성' }))
  expect(quotes).toHaveLength(1)
  fireEvent.change(screen.getByRole('spinbutton', { name: '수량' }), { target: { value: '3' } })
  fireEvent.click(screen.getByRole('button', { name: '견적 저장' }))
  expect(await screen.findByText('견적 SS34L × 3')).toBeInTheDocument()
  expect(quotes).toHaveLength(2)
  fireEvent.change(screen.getByRole('combobox', { name: '저장된 견적' }), { target: { value: '1' } })
  expect(screen.getByText('견적 SS34L × 25')).toBeInTheDocument()
  expect(quotes).toHaveLength(2)
})

it('exposes price lookup for the approved candidate without price_parts', async () => {
  const stored = [{ id: 7, message_id: 101, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 41 }]
  candidateApi(false, id => ({ ...candidateRun(id), result: { ...candidateRun(id).result, price_parts: [] } }), stored)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await screen.findByText('승인됨')
  expect(screen.getByRole('button', { name: '가격·재고 조회' })).toBeInTheDocument()
})


it('blocks new quote saving after history lookup fails and recovers through GET only', async () => {
  const stored = [{ id: 7, message_id: 101, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 41 }]
  candidateApi(false, id => candidateRun(id), stored)
  const base = globalThis.fetch
  let fails = true
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects/1/quotes') return fails ? failure('UNAVAILABLE', '조회 실패', 503) : Response.json([{ id: 1, approval_id: 7, part_number: 'SS34L', quantity: 25 }])
    return base(path, init)
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await screen.findByText('승인됨')
  expect(await screen.findByText(/견적 이력을 불러오지 못했습니다/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '견적 저장' })).toBeDisabled()
  fails = false
  fireEvent.click(screen.getByRole('button', { name: '견적 이력 다시 조회' }))
  expect(await screen.findByText('견적 SS34L × 25')).toBeInTheDocument()
  expect(writes).toEqual([])
})

it('looks up the server-approved part and quantity only on click and saves quantity without price fields', async () => {
  const stored = [{ id: 7, message_id: 101, candidate_part: 'SS34L', part_number: 'SS34L-ORDER', verdict: 'ROLE_SUFFICIENT', case_id: 41 }]
  candidateApi(false, id => candidateRun(id), stored)
  const base = globalThis.fetch
  const prices: string[] = [], quotes: unknown[] = []
  network((path, init) => {
    if (path.startsWith('/api/prices?')) {
      prices.push(path)
      return Response.json({ available: true, source: '모의 판매처', fetched_at: '2026-11-16T00:00:00Z', parts: [{ part_number: 'SS34L-ORDER', manufacturer: '예시', availability: '모의', product_url: null, price_breaks: [], estimate: { quantity: 25, break_quantity: 10, unit_price: '0.10', total: '2.50', currency: 'USD' } }] })
    }
    if (path === '/api/approvals/7/quotes') { quotes.push(JSON.parse(String(init.body))); return Response.json({ id: 1, approval_id: 7, part_number: 'SS34L-ORDER', quantity: 25 }, { status: 201 }) }
    return base(path, init)
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  await screen.findByText('승인됨')
  fireEvent.change(screen.getByRole('spinbutton', { name: '수량' }), { target: { value: '25' } })
  expect(prices).toEqual([])
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('2.50 USD')).toBeInTheDocument()
  expect(prices).toEqual(['/api/prices?parts=SS34L-ORDER&quantity=25'])
  fireEvent.click(screen.getByRole('button', { name: '견적 저장' }))
  expect(await screen.findByText('견적 SS34L-ORDER × 25')).toBeInTheDocument()
  expect(quotes).toEqual([{ quantity: 25 }])
  expect(prices).toHaveLength(1)
})
