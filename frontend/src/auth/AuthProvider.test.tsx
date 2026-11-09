import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthProvider'
import { failure, network, user } from '../test/network'

afterEach(() => vi.unstubAllGlobals())
function Session() {
  const { user, loading, login, logout } = useAuth()
  return <><span>{loading ? '복원 중' : user ? `사용자 ${user.user_id}` : '비로그인'}</span><button onClick={() => void login('user@example.test', 'test-only')}>접속</button><button onClick={() => void logout()}>종료</button></>
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
