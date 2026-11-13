import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/Review', () => ({ default: () => null }))
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

it.each(deletions)('dismisses the error for $label and shows a new failure on another attempt', async ({ query, label }) => {
  const remove = mutationApi(() => failure('NOT_FOUND', '대상을 찾을 수 없습니다.', 404))
  open(query)
  await confirmDelete(label)
  expect(await screen.findByRole('alert')).toHaveTextContent('삭제하지 못했습니다.')
  fireEvent.click(screen.getByRole('button', { name: '오류 알림 닫기' }))
  expect(screen.queryByRole('alert')).toBeNull()
  expect(remove).toHaveBeenCalledTimes(1)
  await confirmDelete(label)
  expect(await screen.findByRole('alert')).toHaveTextContent('대상을 찾을 수 없습니다.')
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

it('clears a stale error on browser history navigation and does not bring it back on return', async () => {
  mutationApi(() => failure('NOT_FOUND', '대상을 찾을 수 없습니다.', 404))
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
