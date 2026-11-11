import { renderWithQueries as render, demo, first, second, summary } from './test/projects'
import { StrictMode } from 'react'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App, { DummyModeNotice } from './App'
import WorkbenchPage from './pages/WorkbenchPage'
import { administrator, failure, network, user } from './test/network'

afterEach(() => vi.unstubAllGlobals())
it('uses the shared brand and signed-in email on the redesigned settings route', async () => {
  network(path => Response.json(path === '/api/auth/me' ? user : []))
  render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: '내 설정' })).toBeInTheDocument()
  expect(screen.getByRole('main')).toHaveClass('settings-main')
  expect(within(screen.getByRole('banner')).getByRole('img', { name: 'SOJAFIT' })).toHaveAttribute('src', '/assets/sojafit-logo.svg')
  expect(within(screen.getByRole('banner')).getByText(user.email)).toBeInTheDocument()
  expect(screen.getByRole('banner')).toHaveClass('app-topbar')
  expect(within(screen.getByRole('banner')).queryByRole('button', { name: '로그아웃' })).not.toBeInTheDocument()
  const navigation = screen.getByRole('navigation', { name: '설정 항목' })
  expect(within(navigation).getByRole('link', { name: '개인 설정' })).toHaveAttribute('href', '#profile-heading')
  expect(within(navigation).getByRole('link', { name: '계정 관리' })).toHaveAttribute('href', '#leave-heading')
  expect(screen.getByLabelText('소속')).toBeInTheDocument()
  expect(screen.getByLabelText('직무')).toBeInTheDocument()
  expect(screen.getByLabelText('선호 실장 방식')).toBeInTheDocument()
  expect(screen.queryByText(/여기 적은 사실은 다음 대화에서도/)).not.toBeInTheDocument()
})
it('shares account actions and preserves logout errors and retry from settings', async () => {
  let failed = true, signedIn = true
  network((path, init) => {
    if (path === '/api/auth/me') return signedIn ? Response.json(user) : failure()
    if (path === '/api/auth/logout' && init.method === 'POST') {
      if (failed) return failure('UNAVAILABLE', '로그아웃을 완료하지 못했습니다.', 503)
      signedIn = false; return new Response(null, { status: 204 })
    }
    return Response.json(path.startsWith('/api/auth/') ? { enabled: false } : [])
  })
  render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: user.email }))
  expect(screen.getByRole('menuitem', { name: '내 설정 관리' })).toBeInTheDocument()
  expect(screen.queryByRole('menuitem', { name: '사용자 관리' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('로그아웃을 완료하지 못했습니다.')
  expect(screen.getByRole('heading', { name: '내 설정' })).toBeInTheDocument()
  failed = false
  fireEvent.click(screen.getByRole('button', { name: user.email }))
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
  expect(await screen.findByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
})
it('shares the saved motion preference and updates the workbench immediately', async () => {
  const previous = localStorage.getItem('sojafit-reduce-motion')
  localStorage.setItem('sojafit-reduce-motion', 'false')
  network(path => Response.json(path === '/api/auth/me' ? user : []))
  try {
    render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: user.email }))
    fireEvent.click(screen.getByRole('menuitem', { name: '개인 설정' }))
    fireEvent.click(screen.getByRole('checkbox', { name: '동작 효과 줄이기' }))
    fireEvent.click(screen.getByRole('button', { name: /^확인$/ }))
    fireEvent.click(screen.getByRole('link', { name: /^작업대$/ }))
    expect(await screen.findByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
    expect(document.querySelector('.workbench-shell')).toHaveClass('motion-reduced')
    expect(screen.getByRole('banner')).toHaveClass('app-topbar')
    openAccountMenu()
    fireEvent.click(screen.getByRole('menuitem', { name: '개인 설정' }))
    expect(screen.getByRole('checkbox', { name: '동작 효과 줄이기' })).toBeChecked()
    fireEvent.click(screen.getByRole('checkbox', { name: '동작 효과 줄이기' }))
    expect(document.querySelector('.workbench-shell')).not.toHaveClass('motion-reduced')
  } finally {
    if (previous === null) localStorage.removeItem('sojafit-reduce-motion')
    else localStorage.setItem('sojafit-reduce-motion', previous)
  }
})
function openProjectCreator() {
  const trigger = screen.queryAllByRole('button', { name: '프로젝트 추가' })[0]
  if (trigger) fireEvent.click(trigger)
  else if (screen.queryByRole('button', { name: /^프로젝트$/ })) {
    fireEvent.click(screen.getByRole('button', { name: /^프로젝트$/ }))
    fireEvent.click(screen.getByRole('button', { name: '새 프로젝트 만들기' }))
  }
  else {
    fireEvent.click(screen.getByRole('button', { name: 'D1을 SS34로 바꿔도 되나요?' }))
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
  }
}
function openProjectList() { fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' })) }
function openAccountMenu() { fireEvent.click(screen.getByRole('button', { name: /@example\.test$/ })) }
function logoutFromWorkbench() { openAccountMenu(); fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' })) }
it('shows a persistent non-storage notice only when dummy mode is enabled', () => {
  const { rerender } = render(<DummyModeNotice enabled />)
  expect(screen.getByText('더미 실행 모드 · 저장되지 않음')).toBeVisible()
  rerender(<DummyModeNotice enabled={false} />)
  expect(screen.queryByText('더미 실행 모드 · 저장되지 않음')).not.toBeInTheDocument()
})
it.each(['/app', '/admin/users'])('anonymous %s entry redirects to login without requesting admin data', async (path) => {
  const requested: string[] = []
  network((url) => { requested.push(url); return url.endsWith('/me') ? failure() : Response.json({ enabled: false }) })
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '사용자 관리' })).not.toBeInTheDocument()
  expect(requested).not.toContain('/api/admin/users')
})

it('shows the approved public landing without requesting protected project data', async () => {
  const calls: string[] = []
  network(path => { calls.push(path); return failure() })
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: /부품을 바꾸기 전에/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '회로 검토 시작' })).toHaveAttribute('href', '/login')
  fireEvent.click(screen.getByRole('button', { name: /문서 근거/ }))
  expect(screen.getByRole('button', { name: /문서 근거/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('합성 예시 화면')).toBeInTheDocument()
  expect(calls.some(path => path.startsWith('/api/projects'))).toBe(false)
})

it('keeps one main landmark on login and workbench routes', async () => {
  network(path => {
    if (path === '/api/auth/me') return failure()
    if (path === '/api/auth/google/status') return Response.json({ enabled: false })
    return Response.json([])
  })
  const view = render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
  expect(await screen.findByRole('main')).toBeInTheDocument()
  view.unmount()
  network(path => {
    if (path === '/api/auth/me') return Response.json(user)
    if (path === '/api/projects' || path === '/api/demo-circuits' || path === '/api/judge/roles') return Response.json([])
    return Response.json([])
  })
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  await screen.findByRole('heading', { name: 'SojaFit 에이전트' })
  expect(screen.getAllByRole('main')).toHaveLength(1)
})

it('links anonymous users to the public signup page', async () => {
  network(path => Response.json(path === '/api/auth/google/status' ? { enabled: false } : {}, { status: path === '/api/auth/me' ? 401 : 200 }))
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
  expect(await screen.findByRole('link', { name: '회원가입' })).toHaveAttribute('href', '/signup')
})
it('restores a session before showing the workbench and admin navigation', async () => {
  network(path => Response.json(path === '/api/auth/me' ? administrator : []))
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
  openAccountMenu()
  expect(screen.getByRole('menuitem', { name: '사용자 관리' })).toBeInTheDocument()
})
it('shows restore failures instead of granting access', async () => {
  network(() => failure('SERVICE_UNAVAILABLE', '로그인 서비스를 사용할 수 없습니다.', 503))
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('로그인 서비스를 사용할 수 없습니다.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(screen.queryByRole('heading', { name: 'SojaFit 에이전트' })).not.toBeInTheDocument()
})


it('removes owned project cache immediately on logout before another session can mount', async () => {
  network(path => {
    if (path === '/api/auth/me') return Response.json(administrator)
    if (path === '/api/auth/logout') return Response.json({ ok: true })
    if (path === '/api/auth/google/status') return Response.json({ enabled: false })
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/demo-circuits') return Response.json([demo])
    throw new Error(`Unexpected request: ${path}`)
  })
  const { client } = render(<StrictMode><MemoryRouter initialEntries={['/app?projectId=11']}><App /></MemoryRouter></StrictMode>)
  fireEvent.click(await screen.findByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByRole('heading', { name: first.name })
  expect(client.getQueryData(['projects'])).toEqual([summary(first)])
  vi.useFakeTimers()
  try {
    openAccountMenu()
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
    })
    expect(screen.getByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
    expect(client.getQueryData(['projects'])).toBeUndefined()
    expect(client.getQueryData(['project', 11])).toBeUndefined()
  } finally { vi.useRealTimers() }
})

it.each(['demo', 'upload', 'rename', 'delete'] as const)('keeps the relogged-in session when an old %s response settles', async (kind) => {
  let session = 0; let finish!: (response: Response) => void
  let signal: AbortSignal | null | undefined; let reads = 0
  network((path, init) => {
    if (path === '/api/auth/me') return Response.json(session ? user : administrator)
    if (path === '/api/auth/logout') return Response.json({ ok: true })
    if (path === '/api/auth/login') { session++; return Response.json({ user_id: 7 }) }
    if (path === '/api/auth/google/status') return Response.json({ enabled: false })
    if (['POST', 'PATCH', 'DELETE'].includes(init.method ?? '')) {
      signal = init.signal; return new Promise(resolve => { finish = resolve })
    }
    reads++
    if (path === '/api/projects') return Response.json([summary(session ? second : first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/12') return Response.json(second)
    if (path === '/api/demo-circuits') return Response.json([demo])
    throw new Error(`Unexpected request: ${path}`)
  })
  render(<StrictMode><MemoryRouter initialEntries={['/app?projectId=11']}><App /></MemoryRouter></StrictMode>)
  fireEvent.click(await screen.findByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByRole('heading', { name: first.name })
  if (kind === 'demo' || kind === 'upload') {
    openProjectCreator()
    fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '진행 중 회로' } })
    if (kind === 'demo') {
      await screen.findByRole('option', { name: demo.name })
      fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
      fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
    } else {
      fireEvent.change(screen.getByLabelText('KiCad 넷리스트'), { target: { files: [new File(['server input'], 'board.net')] } })
      fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
    }
  } else if (kind === 'rename') {
    openProjectList()
    fireEvent.change(screen.getByLabelText('프로젝트 이름 변경'), { target: { value: '진행 중 이름' } })
    fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  } else {
    openProjectList()
    fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  logoutFromWorkbench()
  await screen.findByRole('heading', { name: 'SojaFit에 로그인' })
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'next@example.test' } })
  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'test-only' } })
  fireEvent.click(screen.getByRole('button', { name: '로그인' }))
  fireEvent.click(await screen.findByRole('button', { name: '프로젝트 열기' }))
  fireEvent.click(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: second.name }))
  await screen.findByRole('heading', { name: second.name })
  fireEvent.change(screen.getByLabelText('대상 부품'), { target: { value: 'D2' } })
  const before = reads
  await act(async () => { finish(failure()) })
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByText('선택한 대상: D2')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /@example\.test$/ })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'SojaFit에 로그인' })).not.toBeInTheDocument()
  expect(reads).toBe(before)
  expect(signal?.aborted).toBe(true)
})

it.each(['demo', 'upload', 'rename', 'delete'] as const)('skips post-unmount invalidation and selection for an old successful %s request', async (kind) => {
  let finish!: (response: Response) => void; let signal: AbortSignal | null | undefined; let reads = 0
  network((path, init) => {
    if (['POST', 'PATCH', 'DELETE'].includes(init.method ?? '')) {
      signal = init.signal; return new Promise(resolve => { finish = resolve })
    }
    reads++
    return Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second)
  })
  const { unmount, client } = render(<MemoryRouter initialEntries={['/app?projectId=11']}><WorkbenchPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByRole('heading', { name: first.name })
  if (kind === 'demo' || kind === 'upload') {
    openProjectCreator()
    fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '진행 중 회로' } })
    if (kind === 'demo') {
      await screen.findByRole('option', { name: demo.name })
      fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
      fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
    } else {
      fireEvent.change(screen.getByLabelText('KiCad 넷리스트'), { target: { files: [new File(['server input'], 'board.net')] } })
      fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
    }
  } else if (kind === 'rename') { openProjectList(); fireEvent.click(screen.getByRole('button', { name: '이름 저장' })) }
  else {
    openProjectList()
    fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  unmount()
  // Keep another Workbench active on the same QueryClient so stale invalidation is observable as GETs.
  render(<MemoryRouter initialEntries={['/app?projectId=12']}><WorkbenchPage /></MemoryRouter>, client)
  fireEvent.click(await screen.findByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByRole('heading', { name: second.name })
  const before = reads
  await act(async () => finish(kind === 'delete' ? new Response(null, { status: 204 }) : Response.json(first)))
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(reads).toBe(before)
  expect(signal?.aborted).toBe(true)
})


it.each(['/app', '/settings'])('groups admin account actions and opens existing user management from %s', async (path) => {
  network(url => Response.json(url === '/api/auth/me' ? administrator : url === '/api/admin/users' ? { users: [] } : []))
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: administrator.email }))
  const menu = screen.getByRole('menu', { name: '계정 메뉴' })
  expect(within(menu).getByText('관리자', { exact: true })).toBeInTheDocument()
  const group = within(menu).getByRole('group', { name: '관리자 메뉴' })
  const manage = within(group).getByRole('menuitem', { name: '사용자 관리' })
  expect(manage).toHaveAttribute('href', '/admin/users')
  fireEvent.click(manage)
  expect(await screen.findByRole('heading', { name: '사용자 관리' })).toBeInTheDocument()
  expect(screen.queryByRole('menu', { name: '계정 메뉴' })).not.toBeInTheDocument()
})

it.each(['/app', '/settings'])('hides the admin account group and never fetches admin data for a user on %s', async (path) => {
  const requested: string[] = []
  network(url => { requested.push(url); return Response.json(url === '/api/auth/me' ? user : []) })
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: user.email }))
  const menu = screen.getByRole('menu', { name: '계정 메뉴' })
  expect(within(menu).getByText('일반 사용자', { exact: true })).toBeInTheDocument()
  expect(within(menu).queryByRole('group', { name: '관리자 메뉴' })).not.toBeInTheDocument()
  expect(within(menu).queryByRole('menuitem', { name: '사용자 관리' })).not.toBeInTheDocument()
  expect(within(menu).getByRole('menuitem', { name: '내 설정 관리' })).toBeInTheDocument()
  expect(requested).not.toContain('/api/admin/users')
})
