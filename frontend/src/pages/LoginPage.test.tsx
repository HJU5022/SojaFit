import { renderWithQueries as render } from '../test/projects'
import { fireEvent, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network, user } from '../test/network'
import '../styles.css'

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs() })
function open() { render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>) }
function fill() {
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'user@example.test' } })
  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'test-only' } })
  fireEvent.click(screen.getByRole('button', { name: '로그인' }))
}
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
  expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  expect(await screen.findByRole('link', { name: 'Google로 계속하기' })).toHaveAttribute('href', '/api/auth/google/start')
})
it('explains the existing Google callback failure redirect', async () => {
  network((path) => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  render(<MemoryRouter initialEntries={['/login?google=error']}><App /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.')
})

it('explains when Google login availability cannot be checked', async () => {
  network((path) => path.endsWith('/status') ? failure('TEMPORARY', '상태 확인 실패', 503) : failure())
  open()
  expect(await screen.findByText('Google 로그인을 사용할 수 없습니다. 이메일 로그인으로 진행해 주세요.')).toBeInTheDocument()
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
  const google = await screen.findByRole('link', { name: 'Google로 계속하기' })
  expect(google).toHaveAttribute('href', '/api/auth/google/start')
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
})
