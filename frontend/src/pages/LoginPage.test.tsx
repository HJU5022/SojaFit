import { renderWithQueries as render } from '../test/projects'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network, user } from '../test/network'
import '../styles.css'

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs() })
function open() { render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>) }

it.each(['signup', 'link'])('finishes Google %s only after an explicit action', async action => {
  let signedIn = false
  const posts: { path: string; body: unknown }[] = []
  network((path, init) => {
    if (path === '/api/auth/me') return signedIn ? Response.json(user) : failure()
    if (path === '/api/auth/google/status') return Response.json({ enabled: true })
    if (path === '/api/auth/google/onboarding') return Response.json({ email: 'u***@example.test' })
    if (init.method === 'POST') { posts.push({ path, body: JSON.parse(String(init.body)) }); signedIn = true; return Response.json({ user_id: user.user_id }) }
    return Response.json([])
  })
  render(<MemoryRouter initialEntries={['/login?google=finish']}><App /></MemoryRouter>)
  expect(await screen.findByText('u***@example.test')).toBeInTheDocument()
  expect(posts).toHaveLength(0)
  if (action === 'link') {
    fireEvent.change(screen.getByLabelText('이메일'), { target: { value: user.email } })
    fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'existing password' } })
    fireEvent.click(screen.getByRole('button', { name: '기존 계정에 연결' }))
  } else fireEvent.click(screen.getByRole('button', { name: 'Google 계정으로 가입' }))
  await waitFor(() => expect(posts).toEqual([{ path: '/api/auth/google/' + action, body: action === 'link' ? { email: user.email, password: 'existing password' } : {} }]))
  await waitFor(() => expect(screen.queryByText('u***@example.test')).not.toBeInTheDocument())
})

it('blocks Google completion when the pending identity has expired', async () => {
  const posts: string[] = []
  network((path, init) => {
    if (init.method === 'POST') posts.push(path)
    return path.endsWith('/status') ? Response.json({ enabled: true }) : failure('VALIDATION_ERROR', 'Google 인증이 만료되었습니다.', 400)
  })
  render(<MemoryRouter initialEntries={['/login?google=finish']}><App /></MemoryRouter>)
  expect(await screen.findByRole('link', { name: 'Google 인증 다시 시작' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '기존 계정에 연결' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Google 계정으로 가입' })).not.toBeInTheDocument()
  expect(posts).toEqual([])
})
function fill() {
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'user@example.test' } })
  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'test-only' } })
  fireEvent.click(screen.getByRole('button', { name: '로그인' }))
}
it.each([
  ['UNAUTHORIZED', 401, '이메일과 비밀번호 또는 가입 방법을 확인해 주세요.'],
  ['VALIDATION_ERROR', 422, '이메일 형식과 비밀번호 입력을 확인해 주세요.'],
  ['ORIGIN_MISMATCH', 403, '공식 서비스 주소에서 다시 접속해 주세요.'],
  ['RATE_LIMITED', 429, '로그인 시도가 많습니다. 잠시 기다린 후 다시 시도해 주세요.'],
  ['UNAVAILABLE', 503, '로그인 서비스가 일시적으로 원활하지 않습니다.'],
] as const)('explains %s without disclosing account existence', async (code, status, message) => {
  network(path => path.endsWith('/status') ? Response.json({ enabled: true }) : path.endsWith('/login') ? failure(code, '원문 오류를 그대로 표시하지 않음', status) : failure())
  open(); await screen.findByLabelText('이메일'); fill()
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(message)
  expect(alert).toHaveTextContent('req-test')
  expect(alert).not.toHaveTextContent('원문 오류')
  expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  expect(screen.getByLabelText('이메일')).toHaveValue('user@example.test')
  if (code === 'UNAUTHORIZED') {
    expect(alert).toHaveTextContent('탈퇴했거나 아직 가입하지 않았다면 회원가입이 필요합니다.')
    expect(alert).toHaveTextContent('Google로 가입했다면 Google 로그인을 이용하세요.')
    expect(alert).toHaveTextContent('15분 뒤')
  }
})

it.each(['network', 'html503', 'broken200'] as const)('handles %s safely instead of showing credential advice', async kind => {
  network(path => {
    if (path.endsWith('/status')) return Response.json({ enabled: true })
    if (path.endsWith('/login')) {
      if (kind === 'network') return Promise.reject(new TypeError('Failed to fetch private endpoint'))
      return new Response('<html>private failure</html>', { status: kind === 'html503' ? 503 : 200, headers: { 'X-Request-ID': 'req-header' } })
    }
    return failure()
  })
  open(); await screen.findByLabelText('이메일'); fill()
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(kind === 'network' ? '네트워크 연결' : kind === 'html503' ? '일시적으로 원활하지 않습니다' : '서버 응답을 확인하지 못했습니다')
  expect(alert).not.toHaveTextContent('private')
  expect(alert).not.toHaveTextContent('회원가입이 필요합니다')
  if (kind !== 'network') expect(alert).toHaveTextContent('req-header')
})

it('distinguishes session confirmation failure after a successful login without retrying POST', async () => {
  let posts = 0
  network(path => {
    if (path.endsWith('/status')) return Response.json({ enabled: true })
    if (path.endsWith('/login')) { posts++; return Response.json({ user_id: 7 }) }
    return posts ? failure('UNAVAILABLE', '세션 조회 장애', 503) : failure()
  })
  open(); await screen.findByLabelText('이메일'); fill()
  expect(await screen.findByRole('alert')).toHaveTextContent('로그인 상태를 확인하지 못했습니다.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(posts).toBe(1)
})

it.each([true, false])('shows deletion confirmation only after successful self deletion (success=%s)', async success => {
  let signedIn = true
  network((path, init) => {
    if (path === '/api/auth/me') return signedIn ? Response.json(user) : failure()
    if (path === '/api/me' && init.method === 'DELETE') { if (success) signedIn = false; return success ? Response.json({ deleted: {} }) : failure('CONFLICT', '진행 중인 분석이 있습니다.', 409) }
    if (path.endsWith('/status')) return Response.json({ enabled: true })
    return Response.json([])
  })
  render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: '계정 삭제' }))
  fireEvent.click(screen.getByRole('button', { name: '계정 삭제 확인' }))
  if (success) {
    await screen.findByRole('heading', { name: 'SojaFit에 로그인' })
    expect(screen.getByRole('status')).toHaveTextContent('계정 삭제가 완료되었습니다.')
  } else {
    await screen.findByRole('alert')
    expect(screen.queryByText(/계정 삭제가 완료되었습니다/)).not.toBeInTheDocument()
  }
})

it('clears deletion feedback after signup and logout without persisting it in browser storage', async () => {
  let signedIn = true
  network((path, init) => {
    if (path === '/api/auth/me') return signedIn ? Response.json(user) : failure()
    if (path === '/api/me' && init.method === 'DELETE') { signedIn = false; return Response.json({ deleted: {} }) }
    if (path === '/api/auth/signup') return Response.json({ ok: true })
    if (path === '/api/auth/logout') { signedIn = false; return new Response(null, { status: 204 }) }
    if (path.endsWith('/status')) return Response.json({ enabled: true })
    return Response.json([])
  })
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  try {
    render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: '계정 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '계정 삭제 확인' }))
    await screen.findByText(/계정 삭제가 완료되었습니다/)
    fireEvent.click(screen.getByRole('link', { name: '회원가입' }))
    fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'new@example.test' } })
    fireEvent.click(screen.getByRole('button', { name: '인증 메일 요청' }))
    await screen.findByRole('status')
    fireEvent.click(screen.getByRole('link', { name: '로그인' }))
    await screen.findByRole('heading', { name: 'SojaFit에 로그인' })
    await waitFor(() => expect(screen.queryByText(/계정 삭제가 완료되었습니다/)).not.toBeInTheDocument())
    expect(storage).not.toHaveBeenCalled()
  } finally { storage.mockRestore() }
})
it('logs in and out through real pages without browser storage', async () => {
  let signedIn = false
  network((path) => {
    if (path.endsWith('/login')) { signedIn = true; return Response.json({ user_id: 7 }) }
    if (path.endsWith('/logout')) { signedIn = false; return Response.json({ ok: true }) }
    if (path === '/api/projects' || path === '/api/demo-circuits') return Response.json([])
    if (path.endsWith('/status')) return Response.json({ enabled: false })
    return signedIn ? Response.json(user) : failure()
  })
  const local = vi.spyOn(Storage.prototype, 'setItem')
  open(); await screen.findByLabelText('이메일'); fill()
  expect(await screen.findByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /@example\.test$/ }))
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
  expect(await screen.findByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
  expect(local).not.toHaveBeenCalled(); local.mockRestore()
})
it('shows login error and request id, clears password, and offers configured Google login', async () => {
  network((path) => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  open(); await screen.findByLabelText('이메일'); fill()
  expect(await screen.findByRole('alert')).toHaveTextContent('이메일과 비밀번호 또는 가입 방법을 확인해 주세요.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  expect(await screen.findByRole('button', { name: 'Google 로그인' })).toBeEnabled()
})
it('starts Google authentication without fabricating a consent flag', async () => {
  network(path => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  open()
  const start = await screen.findByRole('button', { name: 'Google 로그인' })
  expect(start).toBeEnabled()
  expect(start.closest('form')).toHaveAttribute('action', '/api/auth/google/start')
  expect(new FormData(start.closest('form')!).get('consent')).toBeNull()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})
it('keeps email login available for a legacy consent redirect', async () => {
  network(path => path.endsWith('/status') ? Response.json({ enabled: false }) : failure())
  render(<MemoryRouter initialEntries={['/login?google=consent']}><App /></MemoryRouter>)
  expect(await screen.findByLabelText('이메일')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Google 로그인' })).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})
it('explains the existing Google callback failure redirect', async () => {
  network((path) => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  render(<MemoryRouter initialEntries={['/login?google=error']}><App /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.')
})

it('explains when Google login availability cannot be checked', async () => {
  network((path) => path.endsWith('/status') ? failure('TEMPORARY', '상태 확인 실패', 503) : failure())
  open()
  expect(await screen.findByText('Google 로그인 연결 상태를 확인하지 못했습니다. 잠시 후 다시 시도하거나 이메일 로그인을 이용하세요.')).toBeInTheDocument()
})

it('uses the dark editor theme by default', () => {
  const root = getComputedStyle(document.documentElement)
  expect(root.colorScheme).toBe('dark')
  expect(root.getPropertyValue('--canvas').trim()).toBe('#1e2229')
  expect(root.getPropertyValue('--trace').trim()).toBe('#ff5722')
})

it('shows demo A/B buttons above the password form only in demo mode and logs in without a password', async () => {
  let signedIn = false
  const bodies: string[] = []
  network((path, init) => {
    if (path === '/api/auth/demo') return Response.json({ enabled: true })
    if (path === '/api/auth/demo-login') { bodies.push(String(init.body)); signedIn = true; return Response.json({ user_id: 8 }) }
    if (path === '/api/projects' || path === '/api/demo-circuits') return Response.json([])
    if (path.endsWith('/status')) return Response.json({ enabled: false })
    return signedIn ? Response.json({ user_id: 8, role: 'user' }) : failure()
  })
  open()
  const buttons = await screen.findByRole('group', { name: '데모 로그인' })
  expect(buttons).toHaveTextContent('평가 계정 아님')
  expect(screen.getByRole('link', { name: '회원가입' })).toHaveAttribute('href', '/signup')
  expect(buttons.compareDocumentPosition(screen.getByLabelText('이메일')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '데모 사용자 B로 들어가기' }))
  expect(await screen.findByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
  expect(bodies).toEqual([JSON.stringify({ account: 'b' })])
})
it('uses Google without demo access in production even when the server advertises demo mode', async () => {
  vi.stubEnv('DEV', false)
  const paths: string[] = []
  network(path => {
    paths.push(path)
    if (path === '/api/auth/google/status' || path === '/api/auth/demo') return Response.json({ enabled: true })
    return failure()
  })
  open()
  const google = await screen.findByRole('button', { name: 'Google 로그인' })
  expect(google.closest('form')).toHaveAttribute('action', '/api/auth/google/start')
  expect(google.closest('form')).toHaveAttribute('method', 'get')
  expect(google).toBeEnabled()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(new FormData(google.closest('form')!).get('consent')).toBeNull()
  expect(screen.getAllByRole('button', { name: 'Google 로그인' })).toHaveLength(1)
  expect(screen.queryByRole('link', { name: 'Google 관리자 로그인' })).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Google로 시작하기' })).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: '개인정보 처리 안내' })).not.toBeInTheDocument()
  expect(google.compareDocumentPosition(screen.getByLabelText('이메일')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.queryByRole('group', { name: '데모 로그인' })).not.toBeInTheDocument()
  expect(paths).not.toContain('/api/auth/demo')
})
it('hides the demo buttons when the server is not in demo mode', async () => {
  network((path) => path === '/api/auth/demo' ? failure('NOT_FOUND', 'Not Found', 404)
    : path.endsWith('/status') ? Response.json({ enabled: false }) : failure())
  open()
  expect(await screen.findByLabelText('이메일')).toBeInTheDocument()
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(screen.queryByRole('group', { name: '데모 로그인' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '데모 사용자 A로 들어가기' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '가입' })).not.toBeInTheDocument()  // 상단 내비에도 로그인 화면에도 이메일 가입 링크가 없다
})


it('provides email signup in production without a consent gate', async () => {
  vi.stubEnv('DEV', false)
  network(path => path === '/api/auth/me' ? failure() : Response.json({ enabled: true }))
  open()
  const signup = await screen.findByRole('link', { name: '회원가입' })
  expect(signup).toHaveAttribute('href', '/signup')
  fireEvent.click(signup)
  expect(await screen.findByRole('heading', { name: 'SojaFit 회원가입' })).toBeVisible()
  expect(screen.getByLabelText('이메일')).toBeVisible()
  expect(screen.queryByLabelText(/비밀번호/)).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '개인정보처리방침' })).toHaveAttribute('href', '/privacy')
})
