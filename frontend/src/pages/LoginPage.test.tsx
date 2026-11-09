import { renderWithQueries as render } from '../test/projects'
import { fireEvent, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network, user } from '../test/network'
import '../styles.css'

afterEach(() => vi.unstubAllGlobals())
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
  expect(await screen.findByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '로그아웃' }))
  expect(await screen.findByRole('heading', { name: '로그인' })).toBeInTheDocument()
  expect(local).not.toHaveBeenCalled(); local.mockRestore()
})
it('shows login error and request id, clears password, and offers configured Google login', async () => {
  network((path) => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  open(); await screen.findByLabelText('이메일'); fill()
  expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  expect(await screen.findByRole('link', { name: 'Google 관리자 로그인' })).toHaveAttribute('href', '/api/auth/google/start')
})
it('explains the existing Google callback failure redirect', async () => {
  network((path) => path.endsWith('/status') ? Response.json({ enabled: true }) : failure())
  render(<MemoryRouter initialEntries={['/login?google=error']}><App /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Google 로그인을 확인할 수 없습니다. 다시 시도해 주세요.')
})

it('uses the dark editor theme by default', () => {
  const root = getComputedStyle(document.documentElement)
  expect(root.colorScheme).toBe('dark')
  expect(root.getPropertyValue('--canvas').trim()).toBe('#0b0f14')
  expect(root.getPropertyValue('--trace').trim()).toBe('#35d0ba')
})
