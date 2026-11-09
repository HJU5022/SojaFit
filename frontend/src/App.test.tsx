import { renderWithQueries as render, demo, first, second, summary } from './test/projects'
import { StrictMode } from 'react'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App, { DummyModeNotice } from './App'
import WorkbenchPage from './pages/WorkbenchPage'
import { administrator, failure, network, user } from './test/network'

afterEach(() => vi.unstubAllGlobals())
it('shows a persistent non-storage notice only when dummy mode is enabled', () => {
  const { rerender } = render(<DummyModeNotice enabled />)
  expect(screen.getByText('더미 실행 모드 · 저장되지 않음')).toBeVisible()
  rerender(<DummyModeNotice enabled={false} />)
  expect(screen.queryByText('더미 실행 모드 · 저장되지 않음')).not.toBeInTheDocument()
})
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
  expect(screen.getByRole('link', { name: '내 설정' })).toBeInTheDocument()
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
  await screen.findByRole('heading', { name: first.name })
  if (kind === 'demo' || kind === 'upload') {
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
    fireEvent.change(screen.getByLabelText('프로젝트 이름 변경'), { target: { value: '진행 중 이름' } })
    fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  } else {
    fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('button', { name: '로그아웃' }))
  await screen.findByRole('heading', { name: '로그인' })
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'next@example.test' } })
  fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'test-only' } })
  fireEvent.click(screen.getByRole('button', { name: '로그인' }))
  fireEvent.click(await screen.findByRole('button', { name: second.name }))
  await screen.findByRole('heading', { name: second.name })
  fireEvent.change(screen.getByLabelText('대상 부품'), { target: { value: 'D2' } })
  const before = reads
  await act(async () => { finish(failure()) })
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByText('선택한 대상: D2')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '로그아웃' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '로그인' })).not.toBeInTheDocument()
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
  await screen.findByRole('heading', { name: first.name })
  if (kind === 'demo' || kind === 'upload') {
    fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '진행 중 회로' } })
    if (kind === 'demo') {
      await screen.findByRole('option', { name: demo.name })
      fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
      fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
    } else {
      fireEvent.change(screen.getByLabelText('KiCad 넷리스트'), { target: { files: [new File(['server input'], 'board.net')] } })
      fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
    }
  } else if (kind === 'rename') fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  else {
    fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  unmount()
  // Keep another Workbench active on the same QueryClient so stale invalidation is observable as GETs.
  render(<MemoryRouter initialEntries={['/app?projectId=12']}><WorkbenchPage /></MemoryRouter>, client)
  await screen.findByRole('heading', { name: second.name })
  const before = reads
  await act(async () => finish(kind === 'delete' ? new Response(null, { status: 204 }) : Response.json(first)))
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(reads).toBe(before)
  expect(signal?.aborted).toBe(true)
})
