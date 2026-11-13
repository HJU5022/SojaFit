import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { StrictMode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/ApprovedCases', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })

const project = { id: 1, name: '보드', source_kind: 'upload', demo_id: null, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }, { ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
const runs: unknown[] = []
const resumes: unknown[] = []
let reply = ''
const api = (body = '') => { runs.length = 0; resumes.length = 0; reply = body; vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }); network((path, init) => {
  if (path === '/api/projects/1') return Response.json(project)
  if (path === '/api/projects/1/threads' && init.method === 'POST') return Response.json({ id: 't1', title: '', status: null, latest_run_id: null, target_ref: 'D1' })
  if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [], latest_run: null })
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

const savedThread = (id = 't1', projectId = 1, ref = 'D1') => ({ id, project_id: projectId, title: `${id} 검토`, target_ref: ref, target_locked: true,
  latest_run: { id: `run-${id}`, status: 'completed', message_id: 2 }, next_before_message_id: null,
  messages: [{ id: 1, run_id: `run-${id}`, role: 'user', content: `${id} 저장된 질문`, created_at: '' }] })
const savedRun = (id: string) => ({ id, thread_id: id.replace('run-', ''), message_id: 2,
  result: { answer: `${id} 저장된 답변`, status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: '' } })
function savedApi(detail: (id: string) => Response | Promise<Response> = id => Response.json(savedThread(id, id === 't2' ? 2 : 1))) {
  const writes: string[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects') return Response.json([project, { ...project, id: 2, name: '다른 보드' }])
    if (path === '/api/projects/1') return Response.json(project)
    if (path === '/api/projects/2') return Response.json({ ...project, id: 2, name: '다른 보드' })
    if (path === '/api/projects/1/threads') return Response.json([savedThread(), savedThread('t3')])
    if (path === '/api/projects/2/threads') return Response.json([savedThread('t2', 2)])
    if (path.startsWith('/api/threads/')) return detail(path.split('/').pop()!)
    if (path.startsWith('/api/runs/')) return Response.json(savedRun(path.split('/').pop()!))
    return Response.json([])
  })
  return writes
}

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
  const question = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(question, { target: { value: '새 검토 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
})

it('clears pending restoration when starting a new review without waiting for the old request', async () => {
  let finish!: (response: Response) => void
  savedApi(() => new Promise<Response>(resolve => { finish = resolve }))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(await screen.findByRole('button', { name: '새 검토' }))
  fireEvent.change(screen.getByRole('textbox', { name: '질문' }), { target: { value: '새 검토 질문' } })
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
  await act(async () => { finish(Response.json(savedThread())); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(screen.queryByText('t1 저장된 질문')).toBeNull()
})

const waiting = `event: run_started\ndata: ${JSON.stringify({ run_id: 'r1' })}\n\nevent: requires_input\ndata: ${JSON.stringify({ status: 'requires_input', interrupt: { question: '값을 알려 주세요.', missing: ['VF', 'IR'] }, request_id: 'req-2' })}\n\n`

it.each(['대화 기록', '검토 내용'])('jumps to the conversation end from %s without losing the draft or making a request', async scrollArea => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const input = screen.getByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '작성 중인 질문' } })
  fireEvent.change(input.closest('form')!.querySelector('input[type=file]')!, { target: { files: [new File(['test'], 'draft.net')] } })
  const end = screen.getByText('대화 끝').parentElement!
  const area = screen.getByRole('region', { name: '검토 내용' })
  const scroller = scrollArea === '대화 기록' ? screen.getByRole('article', { name: scrollArea }) : area
  let bottom = 400
  Object.defineProperty(area, 'getBoundingClientRect', { value: () => ({ bottom: 500 }) })
  Object.defineProperty(end, 'getBoundingClientRect', { value: () => ({ bottom }) })
  const scroll = vi.fn(() => { bottom = 490; fireEvent.scroll(scroller) })
  Object.defineProperty(end, 'scrollIntoView', { value: scroll })
  fireEvent.scroll(scroller)
  expect(screen.queryByRole('button', { name: '대화 맨 아래로 이동' })).toBeNull()
  bottom = 900
  fireEvent.scroll(scroller)
  const jump = screen.getByRole('button', { name: '대화 맨 아래로 이동' })
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  fireEvent.click(jump)
  expect(scroll).toHaveBeenCalledWith({ block: 'end' })
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
  const area = screen.getByRole('region', { name: '검토 내용' })
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
function candidateApi(twoQuestions = false, readRun: (id: string) => unknown = id => candidateRun(id, id === 'r1' ? 40 : 100)) {
  const approvals: { path: string; body: unknown }[] = []
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  network((path, init) => {
    if (path === '/api/projects/1') return Response.json(project)
    if (path === '/api/threads/t1') return Response.json({ ...savedThread(), messages: [
      { id: 1, run_id: 'r1', role: 'user', content: '첫 후보 질문', created_at: '' },
      ...(twoQuestions ? [{ id: 3, run_id: 'r2', role: 'user', content: '둘째 후보 질문', created_at: '' }] : []),
    ] })
    if (path === '/api/runs/r1' || path === '/api/runs/r2') return Response.json(readRun(path.endsWith('r1') ? 'r1' : 'r2'))
    if (path.endsWith('/approvals')) { approvals.push({ path, body: JSON.parse(String(init.body)) }); return Response.json({ id: 1, message_id: 101, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 1 }) }
    return Response.json([])
  })
  return approvals
}

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
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled()
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.submit(input.closest('form')!)
  expect(input).toHaveValue('작성 중인 질문')
  expect(screen.getByRole('list', { name: '첨부한 파일' })).toHaveTextContent('board.NET')
  expect(requests).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'board.NET 첨부 취소' }))
  expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
  expect(screen.getByRole('button', { name: '질문 보내기' })).toBeEnabled()
})

it('shares file validation with the picker and keeps valid files once from a mixed drop', async () => {
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const file = new File(['(export)'], 'board.net', { lastModified: 1 })
  const picker = screen.getByRole('textbox', { name: '질문' }).closest('form')!.querySelector('input[type=file]')!
  fireEvent.change(picker, { target: { files: [file] } })
  fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [file, new File(['memo'], 'notes.txt'), new File(['x'], 'bad.pdf'), new File([], 'empty.net'), new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.net')] } })
  const attached = screen.getByRole('list', { name: '첨부한 파일' })
  expect(within(attached).getAllByRole('listitem')).toHaveLength(2)
  expect(attached).toHaveTextContent('board.net')
  expect(attached).toHaveTextContent('notes.txt')
  expect(screen.getByRole('alert')).toHaveTextContent('5 MiB')
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

it('keeps unsupported production attachments blocked without making a request', async () => {
  vi.stubEnv('DEV', false)
  candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByRole('button', { name: /SS34L.*상세 보기/ })
  const requests = vi.fn(fetch)
  vi.stubGlobal('fetch', requests)
  expect(fireEvent.drop(window, { dataTransfer: { types: ['Files'], files: [new File(['(export)'], 'board.net')] } })).toBe(false)
  expect(screen.queryByRole('list', { name: '첨부한 파일' })).toBeNull()
  expect(screen.getByRole('alert')).toHaveTextContent('현재 운영에서는 질문 파일 첨부를 지원하지 않습니다.')
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

it('shows concise part links and opens the chosen candidate checks and evidence only in the sidebar', async () => {
  const approvals = candidateApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const second = await screen.findByRole('button', { name: /1N5819.*상세 보기/ })
  expect(screen.getByText('후보 2개의 검토 결과를 정리했어요.')).toBeInTheDocument()
  expect(screen.getByText(/검색이 후보 수 상한/)).toBeInTheDocument()
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByText(/상세 보기를 선택/)).toBeInTheDocument()
  expect(screen.queryByText('반복 표 본문')).toBeNull()
  expect(within(screen.getByRole('article')).queryByRole('table')).toBeNull()
  fireEvent.click(second)
  expect(await within(sidebar).findByRole('heading', { name: '1N5819' })).toHaveFocus()
  expect(within(sidebar).getByText('20 V')).toBeInTheDocument()
  expect(within(sidebar).getByText('문서에 없는 값: VF')).toBeInTheDocument()
  expect(within(sidebar).getByText('r1-1N5819.pdf')).toBeInTheDocument()
  expect(within(sidebar).queryByText('r1-SS34L.pdf')).toBeNull()
  expect(within(sidebar).queryByRole('heading', { name: '근거' })).toBeNull()
  expect(within(sidebar).getByRole('button', { name: '검토하고 승인' })).toBeDisabled()
  expect(approvals).toEqual([])
  fireEvent.click(screen.getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(sidebar).findByText('40 V')).toBeInTheDocument()
  expect(within(sidebar).getByText('극성을 확인해 주세요.')).toBeInTheDocument()
  expect(within(sidebar).getByRole('link', { name: /r1-SS34L.pdf/ })).toHaveAttribute('href', 'https://example.test/ss34l.pdf#page=2')
  expect(within(sidebar).queryByText('r1-1N5819.pdf')).toBeNull()
})

it('keeps a past question candidate, its values and approval message together', async () => {
  const approvals = candidateApi(true)
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  const first = (await screen.findByText('첫 후보 질문')).closest('li')!
  const second = (await screen.findByText('둘째 후보 질문')).closest('li')!
  fireEvent.click(await within(second).findByRole('button', { name: /SS34L.*상세 보기/ }))
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(await within(sidebar).findByText('100 V')).toBeInTheDocument()
  fireEvent.click(within(first).getByRole('button', { name: /SS34L.*상세 보기/ }))
  expect(await within(sidebar).findByText('40 V')).toBeInTheDocument()
  fireEvent.click(within(sidebar).getByRole('button', { name: '검토하고 승인' }))
  await waitFor(() => expect(approvals).toHaveLength(1))
  expect(approvals[0]).toEqual({ path: '/api/messages/101/approvals', body: { candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' } })
  fireEvent.click(screen.getByRole('button', { name: '새 검토' }))
  expect(within(sidebar).queryByRole('heading', { name: 'SS34L' })).toBeNull()
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
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByRole('link', { name: /document-answer.pdf/ })).toHaveAttribute('href', 'https://example.test/document-answer.pdf#page=1')
  expect(screen.queryByRole('button', { name: /SS34L.*상세 보기/ })).toBeNull()
})

it('opens a candidate from a live completed response without starting another run', async () => {
  api(`event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: ${JSON.stringify(candidateRun('r1').result)}\n\n`)
  await ask('D1의 후보를 찾아 주세요.')
  fireEvent.click(await screen.findByRole('button', { name: /SS34L.*상세 보기/ }))
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(await within(sidebar).findByText('40 V')).toBeInTheDocument()
  expect(within(sidebar).getByRole('heading', { name: 'SS34L' })).toHaveFocus()
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
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByRole('link', { name: /package.pdf/ })).toHaveAttribute('href', 'https://example.test/package.pdf#page=4')
  expect(within(sidebar).getByRole('link', { name: /r1-SS34L.pdf/ })).toBeInTheDocument()
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
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByRole('link', { name: /marking.pdf/ })).toBeInTheDocument()
  expect(within(sidebar).queryByText('r1-SS34L.pdf')).toBeNull()
})

it('shows test conditions, the reason for an uncertain check and role evidence in the details', async () => {
  candidateApi(false, id => {
    const run = candidateRun(id)
    Object.assign(run.result.judgement.shown[1].checks[0], { condition: 'VR=100V, TJ=25°C', why: '시험 역전압이 실제 역전압보다 높아 불충족을 단정할 수 없음' })
    return run
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&threadId=t1']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /1N5819.*상세 보기/ }))
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByText('시험 조건: VR=100V, TJ=25°C')).toBeVisible()
  expect(within(sidebar).getByText('시험 역전압이 실제 역전압보다 높아 불충족을 단정할 수 없음')).toBeVisible()
  expect(within(sidebar).getByText('역할 근거: 직렬 연결')).toBeVisible()
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
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(await within(sidebar).findByRole('heading', { name: '근거' })).toHaveFocus()
  const links = within(sidebar).getAllByRole('link', { name: /r1-datasheet.pdf/ })
  expect(links.map(link => link.getAttribute('href'))).toEqual(['https://example.test/r1.pdf#page=1', 'https://example.test/r1.pdf#page=2'])
  expect(within(sidebar).getByText('1쪽 · ELECTRICAL CHARACTERISTICS · VRRM')).toBeInTheDocument()
  expect(within(sidebar).getByText('2쪽 · ELECTRICAL CHARACTERISTICS · IR')).toBeInTheDocument()
  expect(within(sidebar).queryByText('r2-datasheet.pdf')).toBeNull()
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
  const sidebar = screen.getByRole('complementary', { name: '부품 상세' })
  expect(within(sidebar).getByRole('heading', { name: '추가 문서 근거' })).toHaveFocus()
  expect(within(sidebar).getByRole('link', { name: /r1-SS34L.pdf/ })).toHaveAttribute('href', 'https://example.test/ss34l.pdf#page=5')
  expect(within(sidebar).getByText('5쪽 · MAXIMUM RATINGS · MARKING')).toBeInTheDocument()
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
