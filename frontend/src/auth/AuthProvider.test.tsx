import { StrictMode } from 'react'
import { act, fireEvent, render as renderPlain, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider, dummyAuthEnabled, useAuth } from './AuthProvider'
import { failure, network, user } from '../test/network'
import { renderWithQueries as render } from '../test/projects'

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs() })
it('limits dummy authentication to explicit development-only settings', () => {
  expect(dummyAuthEnabled({ DEV: true, MODE: 'dummy' })).toBe(true)
  expect(dummyAuthEnabled({ DEV: true, MODE: 'development', VITE_DUMMY_AUTH: '1' })).toBe(true)
  expect(dummyAuthEnabled({ DEV: false, MODE: 'dummy', VITE_DUMMY_AUTH: '1' })).toBe(false)
})
function Session() {
  const { user, loading, login, signup, logout, deleteAccount } = useAuth()
  return <><span>{loading ? '복원 중' : user ? `사용자 ${user.user_id}` : '비로그인'}</span><button onClick={() => void login('user@example.test', 'test-only')}>접속</button><button onClick={() => void logout()}>종료</button>
    <button onClick={() => void signup('new@example.test', 'synthetic-8')}>가입</button><button onClick={() => void deleteAccount()}>탈퇴</button></>
}
it('exposes login and logout using the server session and refreshes role after login', async () => {
  let signedIn = false
  const requests: { path: string; init: RequestInit }[] = []
  network((path, init) => {
    requests.push({ path, init })
    if (path.endsWith('/login')) { signedIn = true; return Response.json({ user_id: 7 }) }
    if (path.endsWith('/logout')) { signedIn = false; return Response.json({ ok: true }) }
    return signedIn ? Response.json(user) : failure()
  })
  render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  fireEvent.click(screen.getByText('접속'))
  expect(await screen.findByText('사용자 7')).toBeInTheDocument()
  expect(requests.find(({ path }) => path.endsWith('/login'))?.init).toMatchObject({ method: 'POST', body: JSON.stringify({ email: 'user@example.test', password: 'test-only' }) })
  fireEvent.click(screen.getByText('종료'))
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  expect(requests.find(({ path }) => path.endsWith('/logout'))?.init.method).toBe('POST')
})
it('ignores an older StrictMode restore 401 after a new login succeeds', async () => {
  const restores: { resolve: (response: Response) => void; signal: AbortSignal | null | undefined }[] = []
  let signedIn = false
  network((path, init) => {
    if (path === '/api/auth/login') { signedIn = true; return Response.json({ user_id: 7 }) }
    if (path === '/api/auth/me' && signedIn) return Response.json(user)
    if (path === '/api/auth/me') return new Promise((resolve) => restores.push({ resolve, signal: init.signal }))
    throw new Error(`Unexpected request: ${path}`)
  })
  // [주의] StrictMode가 가장 바깥이어야 effect를 두 번 돈다(QueryClientProvider 안쪽에 두면 한 번)
  renderPlain(<StrictMode><QueryClientProvider client={new QueryClient()}><AuthProvider><Session /></AuthProvider></QueryClientProvider></StrictMode>)
  await waitFor(() => expect(restores).toHaveLength(2))
  await act(async () => { restores[1].resolve(failure()) })
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  fireEvent.click(screen.getByText('접속'))
  expect(await screen.findByText('사용자 7')).toBeInTheDocument()
  // 취소된 fetch가 늦게 응답하는 네트워크 경계도 재현한다.
  await act(async () => { restores[0].resolve(failure()) })
  expect(screen.getByText('사용자 7')).toBeInTheDocument()
  expect(restores[0].signal?.aborted).toBe(true)
})

it('uses the explicit development dummy session without calling the auth API', async () => {
  vi.stubEnv('VITE_DUMMY_AUTH', '1')
  network((path) => { throw new Error(`Dummy auth must not request ${path}`) })
  render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('사용자 0')).toBeInTheDocument()
})

it('uses the dummy session for the explicit dummy Vite mode', async () => {
  vi.stubEnv('MODE', 'dummy')
  network((path) => { throw new Error(`Dummy mode must not request ${path}`) })
  render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('사용자 0')).toBeInTheDocument()
})

it('never enables dummy auth in a production build', async () => {
  vi.stubEnv('DEV', false)
  vi.stubEnv('VITE_DUMMY_AUTH', '1')
  network(() => failure())
  render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
})

it.each([['종료', '/api/auth/logout'], ['탈퇴', '/api/me']])('%s clears cached screen data and tab storage so the next person sees nothing', async (button, path) => {
  let signedIn = true
  const requests: { path: string; init: RequestInit }[] = []
  network((url, init) => {
    requests.push({ path: url, init })
    if (url === path) { signedIn = false; return Response.json(path === '/api/me' ? { deleted: { account: 1 } } : { ok: true }) }
    return signedIn ? Response.json(user) : failure()
  })
  sessionStorage.setItem('previous', 'left behind')
  const { client } = render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('사용자 7')).toBeInTheDocument()
  client.setQueryData(['projects'], [{ id: 1, name: '앞 사람 회로' }])
  fireEvent.click(screen.getByText(button))
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  expect(requests.find(request => request.path === path)?.init.method).toBe(path === '/api/me' ? 'DELETE' : 'POST')
  expect(client.getQueryData(['projects'])).toBeUndefined()
  expect(sessionStorage.length).toBe(0)
})
it('clears cached data when the server reports an expired session', async () => {
  network(() => Response.json(user))
  const { client } = render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('사용자 7')).toBeInTheDocument()
  client.setQueryData(['projects'], [{ id: 1 }])
  act(() => { window.dispatchEvent(new Event('sojafit:session-expired')) })
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  expect(client.getQueryData(['projects'])).toBeUndefined()
})
it('signs up with the required consent flag and restores the new session', async () => {
  let signedIn = false
  const requests: { path: string; init: RequestInit }[] = []
  network((path, init) => {
    requests.push({ path, init })
    if (path === '/api/auth/signup') { signedIn = true; return Response.json({ user_id: 7 }) }
    return signedIn ? Response.json(user) : failure()
  })
  render(<AuthProvider><Session /></AuthProvider>)
  expect(await screen.findByText('비로그인')).toBeInTheDocument()
  fireEvent.click(screen.getByText('가입'))
  expect(await screen.findByText('사용자 7')).toBeInTheDocument()
  expect(requests.find(({ path }) => path === '/api/auth/signup')?.init).toMatchObject({
    method: 'POST', body: JSON.stringify({ email: 'new@example.test', password: 'synthetic-8', consent: true }) })
})
