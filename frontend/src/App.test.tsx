import { renderWithQueries as render, demo, first, second, summary, showDetail } from './test/projects'
import { StrictMode } from 'react'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App, { DummyModeNotice } from './App'
import WorkbenchPage from './pages/WorkbenchPage'
import { administrator, failure, network, user } from './test/network'

afterEach(() => vi.unstubAllGlobals())
it.each(['/', '/login', '/signup'])('opens the public privacy notice from %s without protected requests or consent submission', async (path) => {
  const calls: string[] = []
  network(url => { calls.push(url); return url === '/api/auth/me' ? failure() : Response.json({ enabled: false }) })
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
  const link = await screen.findByRole('link', { name: /^개인정보처리방침/ })
  expect(link).toHaveAttribute('href', '/privacy')
  document.documentElement.scrollTop = 500
  fireEvent.click(link)
  expect(await screen.findByRole('heading', { name: '개인정보처리방침', level: 1 })).toBeVisible()
  expect(screen.getAllByRole('region', { name: '개인정보 처리 안내' })).toHaveLength(1)
  expect(screen.getByText(/운영자명·문의 연락처/)).toBeVisible()
  expect(document.documentElement.scrollTop).toBe(0)
  expect(calls).not.toContain('/api/projects')
  expect(calls).not.toContain('/api/auth/signup')
})
it.each([null, user])('allows direct privacy entry regardless of login state: %j', async (account) => {
  network(() => account ? Response.json(account) : failure())
  render(<MemoryRouter initialEntries={['/privacy']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: '개인정보처리방침', level: 1 })).toBeVisible()
  expect(screen.getByText('안내 초안')).toBeVisible()
  expect(screen.getByRole('link', { name: '서비스 소개로 돌아가기' })).toHaveAttribute('href', '/')
})
it('shows factual privacy sections, cleanup limits, browser storage and unresolved operator details', async () => {
  network(() => failure())
  render(<MemoryRouter initialEntries={['/privacy']}><App /></MemoryRouter>)
  await screen.findByRole('heading', { name: '개인정보처리방침', level: 1 })
  const contents = screen.getByRole('navigation', { name: '개인정보처리방침 목차' })
  for (const link of within(contents).getAllByRole('link'))
    expect(document.querySelector(link.getAttribute('href')!)).toBeInTheDocument()
  expect(screen.getByRole('table', { name: '개인정보 보유 기준' })).toHaveTextContent('60일')
  expect(screen.getByRole('table', { name: '개인정보 보유 기준' })).toHaveTextContent('30일')
  expect(screen.getByText(/새 분석 요청 때 작은 묶음으로/)).toBeVisible()
  expect(screen.getByRole('table', { name: '쿠키와 브라우저 저장 정보' })).toHaveTextContent('sojafit_session')
  expect(screen.getByRole('table', { name: '외부 서비스 처리 현황' })).toHaveTextContent('OpenRouter')
  expect(screen.getByRole('region', { name: '공개 전 확정할 항목' })).toBeVisible()
  expect(document.querySelectorAll('a[href^="mailto:"]')).toHaveLength(0)
})
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
  expect(screen.queryByText('개인 설정')).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '프로필 정보' })).toBeInTheDocument()
  expect(within(navigation).getByRole('link', { name: '계정 관리' })).toHaveAttribute('href', '#leave-heading')
  expect(screen.getByLabelText('소속')).toBeInTheDocument()
  expect(screen.getByLabelText('직무')).toBeInTheDocument()
  expect(screen.getByLabelText('선호 실장 방식')).toBeInTheDocument()
  expect(screen.queryByText(/여기 적은 사실은 다음 대화에서도/)).not.toBeInTheDocument()
})
it('shares account actions and preserves logout errors and retry from settings', async () => {
  let failed = true, signedIn = true
  network((path, init) => {
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
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
it('removes personal settings from both account menus while preserving saved reduced motion', async () => {
  const previous = localStorage.getItem('sojafit-reduce-motion')
  localStorage.setItem('sojafit-reduce-motion', 'true')
  network(path => Response.json(path === '/api/auth/me' ? user : []))
  try {
    render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: user.email }))
    expect(screen.queryByRole('menuitem', { name: '개인 설정' })).not.toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '내 설정 관리' })).toHaveAttribute('href', '/settings')
    fireEvent.click(screen.getByRole('link', { name: /^작업대$/ }))
    expect(await screen.findByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
    expect(document.querySelector('.workbench-shell')).toHaveClass('motion-reduced')
    expect(screen.getByRole('banner')).toHaveClass('app-topbar')
    openAccountMenu()
    expect(screen.queryByRole('menuitem', { name: '개인 설정' })).not.toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '내 설정 관리' })).toHaveAttribute('href', '/settings')
    expect(screen.queryByRole('dialog', { name: '개인 설정' })).not.toBeInTheDocument()
    expect(localStorage.getItem('sojafit-reduce-motion')).toBe('true')
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
  expect(await screen.findByRole('heading', { name: /회로를 읽고/ })).toBeInTheDocument()
  for (const link of screen.getAllByRole('link', { name: '회로 검토 시작' })) expect(link).toHaveAttribute('href', '/login')
  const guides = screen.getByRole('group', { name: '회로 검토 사용 흐름' })
  expect(document.querySelector('.public-hero img')).not.toBeInTheDocument()
  expect(within(guides).getAllByRole('button')).toHaveLength(9)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  fireEvent.click(within(guides).getByRole('button', { name: '문서 근거' }))
  expect(document.querySelector('[data-metric="recall"]')).toHaveTextContent('93.42%')
  expect(document.querySelector('[data-metric="all-evidence"]')).toHaveTextContent('92.11%')
  expect(document.querySelector('[data-metric="latency"]')).toHaveTextContent('1.18초')
  expect(screen.queryByText('57.89%')).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: '문서 근거 참고 화면' })).toBeInTheDocument()
  const enlarge = screen.getByRole('button', { name: '예시 화면 크게 보기' })
  enlarge.focus()
  fireEvent.click(enlarge)
  expect(screen.getByRole('dialog', { name: '문서 근거 예시 화면' })).toBeInTheDocument()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog', { name: '문서 근거 예시 화면' })).not.toBeInTheDocument()
  expect(enlarge).toHaveFocus()
  expect(screen.getByText(/예시 데이터 · 실제 분석 결과가 아닙니다/)).toBeInTheDocument()
  expect(screen.getByText(/과거 검색 실험이며 현재 운영 답변 정확도를 뜻하지 않습니다/)).toBeInTheDocument()
  expect(calls.some(path => path.startsWith('/api/projects'))).toBe(false)
})

it('links landing menus to separate sections beyond the hero', async () => {
  network(() => failure())
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
  await screen.findByRole('heading', { name: /회로를 읽고/ })
  const nav = screen.getByRole('navigation', { name: '서비스 안내' })
  expect(within(nav).getByRole('link', { name: '서비스 소개' })).toHaveAttribute('href', '#service')
  expect(within(nav).getByRole('link', { name: '사용 방법' })).toHaveAttribute('href', '#how-it-works')
  const hero = document.querySelector('.public-hero')!
  for (const id of ['service', 'how-it-works']) {
    const section = document.getElementById(id)!
    expect(section.tagName).toBe('SECTION')
    expect(hero.contains(section)).toBe(false)
    expect(section).toHaveAttribute('tabindex', '-1')
  }
  expect(screen.getByRole('region', { name: '사용 방법' })).toHaveTextContent('넷리스트 첨부')
})

it('keeps one main landmark on login and workbench routes', async () => {
  network(path => {
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
    if (path === '/api/auth/me') return failure()
    if (path === '/api/auth/google/status') return Response.json({ enabled: false })
    return Response.json([])
  })
  const view = render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
  expect(await screen.findByRole('main')).toBeInTheDocument()
  view.unmount()
  network(path => {
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
    if (path === '/api/auth/me') return Response.json(user)
    if (path === '/api/projects' || path === '/api/demo-circuits' || path === '/api/judge/roles') return Response.json([])
    return Response.json([])
  })
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  await screen.findByRole('heading', { name: 'SojaFit 에이전트' })
  expect(screen.getAllByRole('main')).toHaveLength(1)
})

it('offers verified email signup and recovery outside demo mode', async () => {
  network(path => path === '/api/auth/me' ? failure() : Response.json({ enabled: false }))
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '회원가입' })).toHaveAttribute('href', '/signup')
  expect(screen.getByRole('link', { name: '비밀번호를 잊으셨나요?' })).toHaveAttribute('href', '/reset-password')
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
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
    if (path === '/api/auth/me') return Response.json(administrator)
    if (path === '/api/auth/logout') return Response.json({ ok: true })
    if (path === '/api/auth/google/status') return Response.json({ enabled: false })
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/demo-circuits') return Response.json([demo])
    throw new Error(`Unexpected request: ${path}`)
  })
  const { client } = render(<StrictMode><MemoryRouter initialEntries={['/app?projectId=11']}><App /></MemoryRouter></StrictMode>)
  await screen.findByLabelText('자료 열기'); showDetail('회로')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
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
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
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
  await screen.findByLabelText('자료 열기'); showDetail('회로')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
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
  await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })
  fireEvent.change(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByLabelText('분석할 부품'), { target: { value: 'D2' } })
  showDetail('회로')
  const before = reads
  await act(async () => { finish(failure()) })
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'D2 주변 연결 개념도' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /@example\.test$/ })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'SojaFit에 로그인' })).not.toBeInTheDocument()
  expect(reads).toBe(before)
  expect(signal?.aborted).toBe(true)
})

it.each(['demo', 'upload', 'rename', 'delete'] as const)('skips post-unmount invalidation and selection for an old successful %s request', async (kind) => {
  let finish!: (response: Response) => void; let signal: AbortSignal | null | undefined; let reads = 0
  network((path, init) => {
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
    if (['POST', 'PATCH', 'DELETE'].includes(init.method ?? '')) {
      signal = init.signal; return new Promise(resolve => { finish = resolve })
    }
    reads++
    return Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second)
  })
  const { unmount, client } = render(<MemoryRouter initialEntries={['/app?projectId=11']}><WorkbenchPage /></MemoryRouter>)
  await screen.findByLabelText('자료 열기'); showDetail('회로')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
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
  await screen.findByLabelText('자료 열기'); showDetail('회로')
  await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })
  const before = reads
  await act(async () => finish(kind === 'delete' ? new Response(null, { status: 204 }) : Response.json(first)))
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
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
