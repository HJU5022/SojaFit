import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { Suspense } from 'react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'
import { QueryClient } from '@tanstack/react-query'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/Review', () => ({ default: ({ initialQuestion }: { initialQuestion?: string }) => <div data-testid="review-mock" data-initial-question={initialQuestion ?? ''} /> }))
vi.mock('../components/ApprovedCases', () => ({ default: () => null }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const schematic = { image_url: '/circuit-schematics/c1.png', original_url: 'https://example.test/o', source_repo: 'https://example.test/r', source_commit: 'a'.repeat(40),
  license: 'MIT', license_evidence_url: 'https://example.test/l', attribution: '시험' }
const made = (demoId: string | null, name = '예제') => ({ id: 1, name, source_kind: demoId ? 'demo' : 'upload', demo_id: demoId, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }], nets: [] } })
const catalogue = () => Response.json([{ id: 'c1', name: '예제 회로 1', schematic }])
const disabledSearch = () => failure('UNAVAILABLE', '꺼짐', 503)
// demos: 예제 회로 목록 응답, found: 열려 있는 프로젝트, external: 웹 검색 응답
const api = (demos: () => Response | Promise<Response>, found = made('c1'), external: () => Response = () => Response.json([])) => network((path) => {
  if (path === '/api/demo-circuits') return demos()
  if (path.startsWith('/api/external-circuits/')) return external()
  if (path === '/api/projects') return Response.json([found])
  if (path.split('?')[0] === '/api/projects/1') return Response.json(found)
  return Response.json([])
})
const open = (query = 'projectId=1&targetRef=D1') => renderWithQueries(<MemoryRouter initialEntries={[`/app?${query}`]}><WorkbenchPage /></MemoryRouter>)
const searchBox = () => screen.queryByRole('textbox', { name: /검색어/, hidden: true })
const sheetButton = () => screen.queryByRole('button', { name: /원본 회로도/ })

it('shows only upload when the demo catalogue is unavailable (DEMO_MODE=0), without an error notice', async () => {
  api(() => failure('NOT_FOUND', 'Not Found', 404))
  open()
  await waitFor(() => expect(screen.queryByText('예제 회로를 불러오는 중입니다.')).not.toBeInTheDocument())
  expect(screen.getByText(/KiCad 넷리스트 \(선택, \.net/)).toBeInTheDocument()
  expect(screen.queryByText('파일이 없으면 예제 회로로 시작')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로가 없습니다. KiCad 넷리스트 파일을 선택해 주세요.')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로 목록을 불러오지 못했습니다.')).not.toBeInTheDocument()
})

it('offers the example select and the pre-stored schematic of a demo project when the catalogue is available', async () => {
  api(catalogue)
  open()
  expect(await screen.findByText('파일이 없으면 예제 회로로 시작')).toBeInTheDocument()
  expect(screen.getByText('예제 회로 1', { selector: 'option' })).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: /원본 회로도/ })).toBeInTheDocument()
})

it('still reports a real catalogue failure (not 404)', async () => {
  api(() => failure('UNAVAILABLE', '내부', 503))
  open()
  expect(await screen.findByText('예제 회로 목록을 불러오지 못했습니다.')).toBeInTheDocument()
})

it('keeps the pre-stored schematic for demo projects', async () => {
  api(catalogue, made('c1', '내 보드'))
  open('projectId=1')
  expect((await screen.findByAltText('내 보드 원본 회로도', { exact: true }) as HTMLImageElement).getAttribute('src')).toBe(schematic.image_url)
  expect(searchBox()).toBeNull()
})

it('offers the web search for uploaded projects, defaulting to the project name', async () => {
  api(catalogue, made(null, '내 보드'))
  open('projectId=1')
  await waitFor(() => expect(searchBox()).toHaveValue('내 보드'))
  expect(screen.getByRole('button', { name: '원본 회로도' })).toBeInTheDocument()
})

it.each([['uploaded', null], ['old demo (demo_id kept)', 'c1']])('production (catalogue 404): %s project gets the web search and no catalogue notice', async (_, demoId) => {
  api(() => failure('NOT_FOUND', 'Not Found', 404), made(demoId, '내 보드'))
  open()
  expect(await screen.findByRole('button', { name: /원본 회로도/ })).toBeInTheDocument()
  expect(searchBox()).toHaveValue('내 보드')
  expect(screen.queryByAltText('내 보드 원본 회로도')).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
})

it('demo mode: an uploaded project says the search is unavailable (503 without Retry-After) and hides the search box', async () => {
  api(catalogue, made(null, '내 보드'), disabledSearch)
  open()
  await screen.findByRole('button', { name: /원본 회로도/ })
  fireEvent.click(screen.getByRole('button', { name: '원본 회로도 찾기', hidden: true }))
  expect(await screen.findByText(/이 환경에서는 외부 원본 회로도를 사용할 수 없습니다/, undefined, { timeout: 2000 })).toBeInTheDocument()
  expect(searchBox()).toBeNull()
})

it('does not show the schematic button for a demo project while the catalogue is still pending', async () => {
  api(() => new Promise<Response>(() => {}))
  open()
  await screen.findAllByText('예제')
  await waitFor(() => expect(screen.getByText('D1')).toBeInTheDocument())
  expect(sheetButton()).toBeNull()
})

function mutationApi(reply: () => Response | Promise<Response>) {
  const mutate = vi.fn(reply)
  network((path, init) => {
    if (init.method && init.method !== 'GET') return mutate()
    if (path === '/api/demo-circuits') return catalogue()
    if (path === '/api/projects') return Response.json([made(null, '삭제 시험')])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(made(null, '삭제 시험'))
    if (path === '/api/projects/1/threads') return Response.json([{ id: 't1', project_id: 1, title: '삭제 시험 검토' }])
    if (path === '/api/threads/t1') return Response.json({ id: 't1', project_id: 1, title: '삭제 시험 검토', target_ref: 'D1', target_locked: true, latest_run: null, messages: [], next_before_message_id: null })
    return Response.json([])
  })
  return mutate
}
const deletions = [
  { query: '', label: '삭제 시험 삭제' },
  { query: 'projectId=1', label: '삭제 시험 검토 삭제' },
]
async function confirmDelete(label: string) {
  fireEvent.click(await screen.findByRole('button', { name: label }))
  fireEvent.click(screen.getByRole('button', { name: `${label} 확인` }))
}

function pendingThreadDeletion() {
  let resolve!: (response: Response) => void, removed = false
  const records = ['t1', 't2'].map(id => ({ id, project_id: 1, title: `대화 ${id}`, target_ref: 'D1', target_locked: true, latest_run: null, messages: [], next_before_message_id: null }))
  const remove = vi.fn(() => new Promise<Response>(finish => { resolve = finish }))
  network((path, init) => {
    if (init.method === 'DELETE') return remove()
    if (path === '/api/projects') return Response.json([made(null)])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(made(null))
    if (path === '/api/projects/1/threads') return Response.json(records.filter(item => !removed || item.id !== 't1'))
    if (path.startsWith('/api/threads/')) return Response.json(records.find(item => path.endsWith(item.id)))
    return Response.json([])
  })
  return { remove, finish: () => { removed = true; resolve(new Response(null, { status: 204 })) } }
}
function ThreadRoute() { const location = useLocation(); return <output data-testid="thread-route">{location.search}</output> }

it('sends one deletion for repeated confirmation clicks and leaves the deleted current conversation', async () => {
  const deletion = pendingThreadDeletion()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><ThreadRoute /><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '대화 t1 삭제' }))
  const confirm = screen.getByRole('button', { name: '대화 t1 삭제 확인' })
  act(() => { fireEvent.click(confirm); fireEvent.click(confirm) })
  expect(deletion.remove).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: '대화 t1 삭제 중' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '대화 t2 삭제' })).toBeDisabled()
  await act(async () => { deletion.finish() })
  await waitFor(() => expect(screen.getByTestId('thread-route')).toHaveTextContent(/^\?projectId=1&targetRef=D1$/))
  expect(screen.queryByRole('button', { name: '검토 전: 대화 t1' })).toBeNull()
  expect(screen.getByRole('button', { name: '대화 t2 삭제' })).toBeEnabled()
  expect(screen.queryByRole('alert')).toBeNull()
})

it.each([false, true])('keeps another selected conversation after deletion (switched while pending: %s)', async switched => {
  const deletion = pendingThreadDeletion()
  renderWithQueries(<MemoryRouter initialEntries={[`/app?projectId=1&targetRef=D1&threadId=${switched ? 't1' : 't2'}`]}><ThreadRoute /><WorkbenchPage /></MemoryRouter>)
  await confirmDelete('대화 t1 삭제')
  if (switched) fireEvent.click(screen.getByRole('button', { name: '검토 전: 대화 t2' }))
  await act(async () => { deletion.finish() })
  await waitFor(() => expect(screen.queryByRole('button', { name: '검토 전: 대화 t1' })).toBeNull())
  expect(screen.getByTestId('thread-route')).toHaveTextContent('threadId=t2')
  expect(screen.getByRole('button', { name: '검토 전: 대화 t2' })).toHaveAttribute('aria-current', 'true')
  expect(screen.queryByRole('alert')).toBeNull()
})

it.each(deletions)('dismisses the error for $label and shows a new failure on another attempt', async ({ query, label }) => {
  const remove = mutationApi(() => failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503))
  open(query)
  await confirmDelete(label)
  expect(await screen.findByRole('alert')).toHaveTextContent('삭제하지 못했습니다.')
  fireEvent.click(screen.getByRole('button', { name: '오류 알림 닫기' }))
  expect(screen.queryByRole('alert')).toBeNull()
  expect(remove).toHaveBeenCalledTimes(1)
  await confirmDelete(label)
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후 다시 시도해 주세요.')
  expect(remove).toHaveBeenCalledTimes(2)
})

it.each(deletions)('clears the previous error after successfully retrying $label', async ({ query, label }) => {
  let attempts = 0
  mutationApi(() => ++attempts === 1 ? failure('UNAVAILABLE', '다시 시도해 주세요.', 503) : new Response(null, { status: 204 }))
  open(query)
  await confirmDelete(label)
  await screen.findByRole('alert')
  await confirmDelete(label)
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  expect(attempts).toBe(2)
})

function HistoryControls() {
  const navigate = useNavigate()
  return <><button onClick={() => void navigate(-1)}>이전 화면</button><button onClick={() => void navigate(1)}>다음 화면</button><button onClick={() => void navigate('/settings')}>설정으로 이동</button></>
}

function ProjectNavigationControls() {
  const navigate = useNavigate()
  return <><button onClick={() => void navigate('/app')}>프로젝트 목록으로</button><button onClick={() => void navigate('/app?projectId=2')}>다른 프로젝트로</button><button onClick={() => void navigate(-1)}>이전 화면</button><button onClick={() => void navigate(1)}>다음 화면</button></>
}

function twoProjectApi() {
  const project = made(null, '첫 프로젝트')
  const other = { ...made(null, '다른 프로젝트'), id: 2 }
  network(path => {
    if (path === '/api/projects') return Response.json([project, other])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(project)
    if (path.split('?')[0] === '/api/projects/2') return Response.json(other)
    return Response.json([])
  })
}

it('clears part and project search terms when browser history switches between a project and the list', async () => {
  twoProjectApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app']}><ProjectNavigationControls /><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '첫 프로젝트' }))
  fireEvent.change(await screen.findByRole('textbox', { name: '부품 찾기' }), { target: { value: '1N4148' } })
  fireEvent.click(screen.getByRole('button', { name: '이전 화면' }))
  expect(await screen.findByRole('textbox', { name: '프로젝트 찾기' })).toHaveValue('')
  expect(await screen.findByRole('button', { name: '첫 프로젝트' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '다른 프로젝트' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: '프로젝트 찾기' }), { target: { value: '첫' } })
  fireEvent.click(screen.getByRole('button', { name: '다음 화면' }))
  expect(await screen.findByRole('textbox', { name: '부품 찾기' })).toHaveValue('')
  expect(screen.getByRole('button', { name: 'D1 1N4148 선택' })).toBeInTheDocument()
})

it('clears search terms on browser back and forward between different projects', async () => {
  twoProjectApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1', '/app?projectId=2']}><ProjectNavigationControls /><WorkbenchPage /></MemoryRouter>)
  fireEvent.change(await screen.findByRole('textbox', { name: '부품 찾기' }), { target: { value: '1N4148' } })
  fireEvent.click(screen.getByRole('button', { name: '이전 화면' }))
  expect(await screen.findByRole('textbox', { name: '부품 찾기' })).toHaveValue('')
  expect(screen.getByRole('button', { name: '첫 프로젝트' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: '부품 찾기' }), { target: { value: 'D1' } })
  fireEvent.click(screen.getByRole('button', { name: '다음 화면' }))
  expect(await screen.findByRole('textbox', { name: '부품 찾기' })).toHaveValue('')
  expect(screen.getByRole('button', { name: '다른 프로젝트' })).toBeInTheDocument()
})

it('clears the intake draft and error when switching projects', async () => {
  twoProjectApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '부품 없는 질문 초안' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('부품 번호')
  fireEvent.click(screen.getAllByRole('button', { name: '프로젝트' })[0])
  fireEvent.click(await screen.findByRole('button', { name: '다른 프로젝트' }))
  const nextInput = await screen.findByRole('textbox', { name: '질문' })
  expect(nextInput).toHaveValue('')
  expect(screen.queryByRole('alert')).toBeNull()
})

it('clears the intake draft and error across browser back and forward navigation', async () => {
  twoProjectApi()
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><ProjectNavigationControls /><WorkbenchPage /></MemoryRouter>)
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: '뒤로 가면 사라질 초안' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '다른 프로젝트로' }))
  const projectBInput = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(projectBInput, { target: { value: 'B에서 만든 오류' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '이전 화면' }))
  const previousInput = await screen.findByRole('textbox', { name: '질문' })
  expect(previousInput).toHaveValue('')
  expect(screen.queryByRole('alert')).toBeNull()
  fireEvent.change(previousInput, { target: { value: 'A에서 다시 만든 오류' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }))
  expect(await screen.findByRole('alert')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '다음 화면' }))
  const forwardInput = await screen.findByRole('textbox', { name: '질문' })
  expect(forwardInput).toHaveValue('')
  expect(screen.queryByRole('alert')).toBeNull()
})

it.each(['projectId=1&targetRef=R1', 'projectId=1'])('does not enter a new review for an out-of-scope part (%s)', async query => {
  const found = { ...made(null, '범위 시험'), connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }, { ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([])
    if (path === '/api/projects') return Response.json([found])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(found)
    return Response.json([])
  })
  open(query)
  if (!query.includes('targetRef=')) {
    const outOfScope = await screen.findByRole('button', { name: /R1.*판정 범위 밖/ })
    fireEvent.click(outOfScope)
    expect(outOfScope).toBeDisabled()
    expect(screen.getByRole('textbox', { name: '질문' })).toBeInTheDocument()
  } else {
    expect(await screen.findByText(/현재 다이오드만 판정합니다/)).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '질문' })).toBeNull()
    expect(screen.getAllByRole('button', { name: '부품 고르기' }).length).toBeGreaterThan(0)
  }
})

it('does not forward a draft for a different part when selecting a diode row', async () => {
  const found = { ...made(null, '초안 시험'), connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }, { ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([])
    if (path === '/api/projects') return Response.json([found])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(found)
    return Response.json([])
  })
  open('projectId=1')
  const input = await screen.findByRole('textbox', { name: '질문' })
  fireEvent.change(input, { target: { value: 'R1을 다른 저항으로 바꾸고 싶습니다.' } })
  fireEvent.click(await screen.findByRole('button', { name: /D1.*1N4148/ }))
  expect(await screen.findByTestId('review-mock')).toHaveAttribute('data-initial-question', '')
})

it('offers retry when an out-of-scope saved conversation cannot be loaded', async () => {
  const found = { ...made(null), connections: { parts: [{ ref: 'R1', value: '10k', footprint: '' }], nets: [] } }
  network(path => {
    if (path === '/api/threads/missing') return failure('NOT_FOUND', '대화를 찾을 수 없습니다.', 404)
    if (path === '/api/projects') return Response.json([found])
    if (path.split('?')[0] === '/api/projects/1') return Response.json(found)
    return Response.json([])
  })
  open('projectId=1&targetRef=R1&threadId=missing')
  expect(await screen.findByRole('button', { name: '대화 다시 불러오기' })).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('대화 기록을 불러오지 못했습니다.')
})

it('clears a stale error on browser history navigation and does not bring it back on return', async () => {
  mutationApi(() => failure('UNAVAILABLE', '잠시 후 다시 시도해 주세요.', 503))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1', '/app']}><HistoryControls /><WorkbenchPage /></MemoryRouter>)
  await confirmDelete('삭제 시험 삭제')
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: '이전 화면' }))
  await screen.findByRole('button', { name: '부품 고르기' })
  expect(screen.queryByRole('alert')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '다음 화면' }))
  await screen.findByRole('button', { name: '삭제 시험 삭제' })
  expect(screen.queryByRole('alert')).toBeNull()
})

it('does not show an old deletion failure that arrives after opening another screen', async () => {
  let finish!: (response: Response) => void
  const remove = mutationApi(() => new Promise<Response>(resolve => { finish = resolve }))
  open('')
  await confirmDelete('삭제 시험 삭제')
  await waitFor(() => expect(remove).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: '삭제 시험' }))
  await screen.findByRole('button', { name: '부품 고르기' })
  await act(async () => { finish(failure('NOT_FOUND', '대상을 찾을 수 없습니다.', 404)); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(screen.queryByRole('alert')).toBeNull()
})

it('does not return to the workbench when a pending deletion succeeds after leaving the route', async () => {
  let finish!: (response: Response) => void
  const remove = mutationApi(() => new Promise<Response>(resolve => { finish = resolve }))
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1&threadId=t1']}><HistoryControls /><Routes>
    <Route path="/app" element={<WorkbenchPage />} /><Route path="/settings" element={<h1>설정 화면</h1>} />
  </Routes></MemoryRouter>)
  await confirmDelete('삭제 시험 검토 삭제')
  await waitFor(() => expect(remove).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: '설정으로 이동' }))
  await screen.findByRole('heading', { name: '설정 화면' })
  await act(async () => { finish(new Response(null, { status: 204 })); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(screen.getByRole('heading', { name: '설정 화면' })).toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: '프로젝트와 검토' })).toBeNull()
})

function mockDialogs() {
  // JSDOM에는 브라우저의 dialog 열기·닫기 메서드가 없다.
  for (const dialog of document.querySelectorAll('dialog')) {
    dialog.showModal = function () { this.open = true }
    dialog.close = function () { this.open = false; this.dispatchEvent(new Event('close')) }
  }
}

it.each(['rename', 'delete', 'refresh-fails'])('removes a disappeared project after %s without retrying its mutation', async mode => {
  const other = { ...made(null, '남은 프로젝트'), id: 2 }
  let removed = false, listReads = 0
  const mutations: string[] = []
  network((path, init) => {
    if (path === '/api/projects') {
      listReads++
      return removed && mode === 'refresh-fails' ? failure('UNAVAILABLE', '목록 조회가 늦습니다.', 503) : Response.json(removed ? [other] : [made(null, '사라진 프로젝트'), other])
    }
    if (path === '/api/projects/1' && init.method) { mutations.push(init.method); removed = true; return failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404) }
    return Response.json([])
  })
  const { client } = open('')
  await screen.findByRole('button', { name: '사라진 프로젝트' })
  client.setQueryData(['project', 1, 'old-thread'], made(null, '사라진 프로젝트'))
  client.setQueryData(['threads', 1], [{ id: 'old-thread' }])
  if (mode === 'delete') await confirmDelete('사라진 프로젝트 삭제')
  else {
    mockDialogs(); fireEvent.click(screen.getByRole('button', { name: '사라진 프로젝트 이름 바꾸기' }))
    const dialog = await screen.findByRole('dialog', { name: '프로젝트 이름 바꾸기' })
    fireEvent.submit(within(dialog).getByRole('button', { name: '이름 저장' }).closest('form')!)
  }
  expect(await screen.findByRole('status')).toHaveTextContent('삭제되었거나 더 이상 접근할 수 없는 프로젝트')
  expect(screen.queryByRole('dialog', { name: '프로젝트 이름 바꾸기' })).toBeNull()
  expect(screen.queryByRole('button', { name: '사라진 프로젝트' })).toBeNull()
  expect(screen.getByRole('button', { name: '남은 프로젝트' })).toBeInTheDocument()
  expect(client.getQueryData(['project', 1, 'old-thread'])).toBeUndefined()
  expect(client.getQueryData(['threads', 1])).toBeUndefined()
  expect(mutations).toEqual([mode === 'delete' ? 'DELETE' : 'PATCH'])
  await waitFor(() => expect(listReads).toBe(2))
  if (mode === 'refresh-fails') expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트 목록을 불러오지 못했습니다.')
})

it.each(['', '&threadId=old-thread'])('leaves a cached project when its canonical lookup is missing %s', async suffix => {
  const client = new QueryClient()
  const other = { ...made(null, '다른 프로젝트'), id: 2 }
  client.setQueryData(['project', 1, suffix ? 'old-thread' : ''], made(null, '삭제된 캐시'))
  network((path) => {
    if (path === '/api/projects') return Response.json([other])
    if (path.split('?')[0] === '/api/projects/1') return failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404)
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={[`/app?projectId=1${suffix}`]}><WorkbenchPage /></MemoryRouter>, client)
  expect(await screen.findByText(/삭제되었거나 더 이상 접근할 수 없는 프로젝트/)).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: '다른 프로젝트' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '삭제된 캐시' })).toBeNull()
  expect(client.getQueryData(['project', 1, suffix ? 'old-thread' : ''])).toBeUndefined()
})

it('keeps the project when only the selected conversation version returns 404', async () => {
  let canonicalReads = 0
  network(path => {
    if (path === '/api/projects') return Response.json([made(null, '유효한 프로젝트')])
    if (path === '/api/projects/1') { canonicalReads++; return Response.json(made(null, '유효한 프로젝트')) }
    if (path.startsWith('/api/projects/1?')) return failure('NOT_FOUND', '대화를 찾을 수 없습니다.', 404)
    return Response.json([])
  })
  const { client } = open('projectId=1&threadId=missing')
  expect(await screen.findByText(/회로를 불러오지 못했습니다/)).toBeInTheDocument()
  await waitFor(() => expect(canonicalReads).toBe(1))
  expect(screen.queryByText(/삭제되었거나 더 이상 접근할 수 없는 프로젝트/)).toBeNull()
  expect(client.getQueryData(['projects'])).toEqual([made(null, '유효한 프로젝트')])
})

it.each(['', '&threadId=old-thread'])('does not refetch a confirmed missing project while navigation is pending %s', async suffix => {
  const client = new QueryClient()
  const other = { ...made(null, '다른 프로젝트'), id: 2 }
  client.setQueryData(['project', 1, suffix ? 'old-thread' : ''], made(null, '삭제된 캐시'))
  const reads: string[] = []
  let accessibleAgain = false
  network(path => {
    if (path === '/api/projects') return Response.json([other])
    if (path.split('?')[0] === '/api/projects/1') {
      reads.push(path)
      if (accessibleAgain) return Response.json(made(null, '접근 복구된 프로젝트'))
      // 중복 조회는 대기시켜 잘못된 구현이 무한 요청 대신 횟수 검증으로 실패하게 한다.
      if (reads.filter(read => read === path).length > 1) return new Promise<Response>(() => {})
      return failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404)
    }
    return Response.json([])
  })
  let release!: () => void, blocked = true
  const listReady = new Promise<void>(resolve => { release = () => { blocked = false; resolve() } })
  const navigating = vi.fn()
  function PendingList() {
    const location = useLocation()
    if (!location.search && blocked) { navigating(); throw listReady }
    return <WorkbenchPage />
  }
  try {
    renderWithQueries(<MemoryRouter initialEntries={[`/app?projectId=1${suffix}`, `/app?projectId=1${suffix}`]}><HistoryControls /><Suspense fallback={<p>목록 준비 중</p>}><PendingList /></Suspense></MemoryRouter>, client)
    await waitFor(() => expect(navigating).toHaveBeenCalled())
    // 목록 화면 준비 중에 캐시 갱신으로 기존 화면이 다시 그려져도 재조회하지 않는다.
    await act(async () => { client.setQueryData(['projects'], [other]); await new Promise(resolve => setTimeout(resolve, 0)) })
    expect(reads).toEqual(suffix ? ['/api/projects/1?thread_id=old-thread', '/api/projects/1'] : ['/api/projects/1'])
    await act(async () => { release() })
    expect(await screen.findByText(/삭제되었거나 더 이상 접근할 수 없는 프로젝트/)).toBeInTheDocument()
    expect(client.getQueryData(['project', 1, suffix ? 'old-thread' : ''])).toBeUndefined()
    accessibleAgain = true
    fireEvent.click(screen.getByRole('button', { name: '이전 화면' }))
    await waitFor(() => expect(client.getQueryData(['project', 1, suffix ? 'old-thread' : ''])).toMatchObject({ name: '접근 복구된 프로젝트' }))
    expect(reads).toHaveLength(suffix ? 3 : 2)
  } finally {
    await act(async () => { release(); cleanup() })
    client.clear()
  }
})

it('does not close another rename dialog when an earlier project returns 404 late', async () => {
  let finish!: (value: Response) => void
  let missing = false
  const other = { ...made(null, '다른 프로젝트'), id: 2 }
  network((path, init) => {
    if (path === '/api/projects') return Response.json(missing ? [other] : [made(null, '첫 프로젝트'), other])
    if (path === '/api/projects/1' && init.method === 'PATCH') return new Promise<Response>(resolve => { finish = resolve })
    return Response.json([])
  })
  open(''); await screen.findByRole('button', { name: '첫 프로젝트' }); mockDialogs()
  fireEvent.click(screen.getByRole('button', { name: '첫 프로젝트 이름 바꾸기' }))
  let dialog = await screen.findByRole('dialog', { name: '프로젝트 이름 바꾸기' })
  fireEvent.submit(within(dialog).getByRole('button', { name: '이름 저장' }).closest('form')!)
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
  fireEvent.click(screen.getByRole('button', { name: '다른 프로젝트 이름 바꾸기' }))
  dialog = await screen.findByRole('dialog', { name: '프로젝트 이름 바꾸기' })
  fireEvent.change(within(dialog).getByRole('textbox', { name: '프로젝트 이름' }), { target: { value: '작성 중인 이름' } })
  await act(async () => { missing = true; finish(failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404)) })
  expect(within(dialog).getByRole('textbox', { name: '프로젝트 이름' })).toHaveValue('작성 중인 이름')
  expect(screen.queryByText(/삭제되었거나 더 이상 접근할 수 없는 프로젝트/)).toBeNull()
})

it('does not resurrect a missing project from an older in-flight list response', async () => {
  let finish!: (value: Response) => void
  let reads = 0
  const old = made(null, '이전 목록의 프로젝트'), other = { ...made(null, '남은 프로젝트'), id: 2 }
  network((path, init) => {
    if (path === '/api/projects') {
      if (++reads === 2) return new Promise<Response>(resolve => { finish = resolve })
      return Response.json(reads >= 3 ? [other] : [old, other])
    }
    if (path === '/api/projects/1' && init.method === 'PATCH') return failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404)
    return Response.json([])
  })
  const { client } = open('')
  await screen.findByRole('button', { name: '이전 목록의 프로젝트' }); mockDialogs()
  void client.refetchQueries({ queryKey: ['projects'] })
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: '이전 목록의 프로젝트 이름 바꾸기' }))
  const dialog = await screen.findByRole('dialog', { name: '프로젝트 이름 바꾸기' })
  fireEvent.submit(within(dialog).getByRole('button', { name: '이름 저장' }).closest('form')!)
  await screen.findByText(/삭제되었거나 더 이상 접근할 수 없는 프로젝트/)
  await act(async () => { finish(Response.json([old, other])) })
  expect(screen.queryByRole('button', { name: '이전 목록의 프로젝트' })).toBeNull()
  expect(client.getQueryData(['projects'])).toEqual([other])
})

it.each([
  { openButton: '새 프로젝트', title: '새 프로젝트', submit: '만들기', message: '프로젝트를 만들지 못했습니다.' },
  { openButton: '삭제 시험 이름 바꾸기', title: '프로젝트 이름 바꾸기', submit: '이름 저장', message: '이름을 바꾸지 못했습니다.' },
])('dismisses errors in $title without resubmitting and clears them when the dialog closes', async ({ openButton, title, submit, message }) => {
  const mutate = mutationApi(() => failure('UNAVAILABLE', '다시 시도해 주세요.', 503))
  open('')
  await screen.findByRole('button', { name: '삭제 시험' })
  mockDialogs()
  fireEvent.click(screen.getAllByRole('button', { name: openButton })[0])
  const dialog = await screen.findByRole('dialog', { name: title })
  fireEvent.change(within(dialog).getByRole('textbox', { name: '프로젝트 이름' }), { target: { value: '새 이름' } })
  const form = within(dialog).getByRole('button', { name: submit }).closest('form')!
  fireEvent.submit(form)
  expect(await screen.findByRole('alert')).toHaveTextContent(message)
  fireEvent.click(within(dialog).getByRole('button', { name: '오류 알림 닫기' }))
  expect(screen.queryByRole('alert')).toBeNull()
  expect(mutate).toHaveBeenCalledTimes(1)
  fireEvent.submit(form)
  await screen.findByRole('alert')
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  expect(mutate).toHaveBeenCalledTimes(2)
})

it.each([0, 1])('starts with an empty project name when reopening from create button %i', async (opener) => {
  mutationApi(() => Response.json(made(null, '만든 프로젝트')))
  open('')
  await screen.findByRole('button', { name: '삭제 시험' })
  mockDialogs()
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[opener])
  const dialog = screen.getByRole('dialog', { name: '새 프로젝트' })
  fireEvent.change(within(dialog).getByRole('textbox', { name: '프로젝트 이름' }), { target: { value: '이전 입력' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[opener])
  expect(within(dialog).getByRole('textbox', { name: '프로젝트 이름' })).toHaveValue('')
})

it('starts a fresh form after a project was successfully created', async () => {
  const create = mutationApi(() => Response.json(made(null, '만든 프로젝트')))
  open('')
  await screen.findByRole('button', { name: '삭제 시험' })
  mockDialogs()
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[0])
  const dialog = screen.getByRole('dialog', { name: '새 프로젝트' })
  fireEvent.change(within(dialog).getByRole('textbox', { name: '프로젝트 이름' }), { target: { value: '만든 프로젝트' } })
  fireEvent.submit(within(dialog).getByRole('button', { name: '만들기' }).closest('form')!)
  await screen.findByRole('button', { name: '부품 고르기' })
  fireEvent.click(screen.getByRole('button', { name: '새 프로젝트' }))
  expect(within(dialog).getByRole('textbox', { name: '프로젝트 이름' })).toHaveValue('')
  expect(create).toHaveBeenCalledTimes(1)
})

it('keeps the project name after a failed creation so the same form can retry', async () => {
  const create = mutationApi(() => failure('UNAVAILABLE', '다시 시도해 주세요.', 503))
  open('')
  await screen.findByRole('button', { name: '삭제 시험' })
  mockDialogs()
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[0])
  const dialog = screen.getByRole('dialog', { name: '새 프로젝트' })
  const name = within(dialog).getByRole('textbox', { name: '프로젝트 이름' })
  fireEvent.change(name, { target: { value: '실패해도 유지' } })
  const form = within(dialog).getByRole('button', { name: '만들기' }).closest('form')!
  fireEvent.submit(form)
  await screen.findByRole('alert')
  expect(name).toHaveValue('실패해도 유지')
  expect(dialog).toHaveAttribute('open')
  fireEvent.submit(form)
  await waitFor(() => expect(create).toHaveBeenCalledTimes(2))
  expect(name).toHaveValue('실패해도 유지')
})

it.each(['open', 'copy', 'edit', 'reopen'])('requires a fresh duplicate choice and preserves the form: %s', async choice => {
  const requests: string[] = []
  network((path, init) => {
    if (init.method === 'POST') {
      requests.push(path)
      return path.includes('allow_duplicate=true') ? Response.json(made(null, '새 복사본')) : Response.json({ error: { code: 'CONFLICT', message: '중복', request_id: 'test' }, details: { duplicates: [{ id: 5, name: '기존 회로', matches: ['name', 'netlist'] }] } }, { status: 409 })
    }
    if (path === '/api/projects') return Response.json([])
    if (path === '/api/demo-circuits') return catalogue()
    if (path === '/api/projects/5') return Response.json({ ...made(null, '기존 회로'), id: 5 })
    if (path === '/api/projects/1') return Response.json(made(null, '새 복사본'))
    return Response.json([])
  })
  open(''); await screen.findByText('파일이 없으면 예제 회로로 시작'); mockDialogs()
  fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[0])
  const dialog = screen.getByRole('dialog', { name: '새 프로젝트' })
  const name = within(dialog).getByRole('textbox', { name: '프로젝트 이름' })
  fireEvent.change(name, { target: { value: '겹치는 이름' } })
  const form = within(dialog).getByRole('button', { name: '만들기' }).closest('form')!
  fireEvent.submit(form)
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('이름 중복 · 넷리스트 중복')
  expect(name).toHaveValue('겹치는 이름')
  expect(requests).toEqual(['/api/projects'])
  expect(within(dialog).getByRole('button', { name: '만들기' })).toBeDisabled()
  if (choice === 'open') {
    fireEvent.click(within(dialog).getByRole('button', { name: '기존 프로젝트 열기: 기존 회로' }))
    await screen.findByRole('button', { name: '부품 고르기' })
    expect(requests).toHaveLength(1)
  } else if (choice === 'copy') {
    fireEvent.click(within(dialog).getByRole('button', { name: '중복을 확인하고 새로 만들기' }))
    await screen.findByRole('button', { name: '부품 고르기' })
    expect(requests).toEqual(['/api/projects', '/api/projects?allow_duplicate=true'])
  } else {
    if (choice === 'edit') fireEvent.change(name, { target: { value: '바꾼 이름' } })
    else {
      fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
      fireEvent.click(screen.getAllByRole('button', { name: '새 프로젝트' })[0])
      expect(name).toHaveValue('')
      fireEvent.change(name, { target: { value: '다시 입력' } })
    }
    expect(within(dialog).queryByRole('button', { name: '중복을 확인하고 새로 만들기' })).toBeNull()
    fireEvent.submit(form)
    await waitFor(() => expect(requests).toEqual(['/api/projects', '/api/projects']))
  }
})
