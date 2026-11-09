import { renderWithQueries as render, demo, first, summary } from './test/projects'
import { StrictMode } from 'react'
import { act, fireEvent, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { administrator, failure, network } from './test/network'

afterEach(() => vi.unstubAllGlobals())
it.each(['/', '/app', '/admin/users'])('anonymous %s entry redirects to login without requesting admin data', async (path) => {
  const requested: string[] = []
  network((url) => { requested.push(url); return url.endsWith('/me') ? failure() : Response.json({ enabled: false }) })
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: '로그인' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '사용자 관리' })).not.toBeInTheDocument()
  expect(requested).not.toContain('/api/admin/users')
})
it('restores a session before showing the workbench and admin navigation', async () => {
  network(path => Response.json(path === '/api/auth/me' ? administrator : []))
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '사용자 관리' })).toBeInTheDocument()
})
it('shows restore failures instead of granting access', async () => {
  network(() => failure('SERVICE_UNAVAILABLE', '로그인 서비스를 사용할 수 없습니다.', 503))
  render(<MemoryRouter initialEntries={['/app']}><App /></MemoryRouter>)
  expect(await screen.findByRole('alert')).toHaveTextContent('로그인 서비스를 사용할 수 없습니다.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
  expect(screen.queryByRole('heading', { name: '회로 작업대' })).not.toBeInTheDocument()
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
  await screen.findByRole('heading', { name: first.name })
  expect(client.getQueryData(['projects'])).toEqual([summary(first)])
  vi.useFakeTimers()
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '로그아웃' })) })
    expect(screen.getByRole('heading', { name: '로그인' })).toBeInTheDocument()
    expect(client.getQueryData(['projects'])).toBeUndefined()
    expect(client.getQueryData(['project', 11])).toBeUndefined()
  } finally { vi.useRealTimers() }
})
