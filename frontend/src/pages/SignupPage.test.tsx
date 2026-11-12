import { fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network, user } from '../test/network'
import { renderWithQueries as render } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
function Location() { return <output aria-label="현재 주소">{useLocation().pathname + useLocation().search}</output> }
function open(path = '/signup') { return render(<MemoryRouter initialEntries={[path]}><App /><Location /></MemoryRouter>) }
function fill() { fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'new@example.test' } }) }

it('requests email proof without sending a password, fabricating consent, or creating a session', async () => {
  const bodies: string[] = []
  network((path, init) => {
    if (path === '/api/auth/signup') { bodies.push(String(init.body)); return Response.json({ ok: true }) }
    return path.endsWith('/status') ? Response.json({ enabled: false }) : failure()
  })
  open()
  expect(await screen.findByRole('link', { name: '개인정보처리방침' })).toHaveAttribute('href', '/privacy')
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  const submit = screen.getByRole('button', { name: '인증 메일 요청' })
  expect(submit).toBeDisabled()
  fill()
  fireEvent.click(submit)
  expect(await screen.findByText(/가입 가능한 이메일이라면/)).toBeInTheDocument()
  expect(bodies).toEqual([JSON.stringify({ email: 'new@example.test' })])
  expect(screen.queryByLabelText(/비밀번호/)).not.toBeInTheDocument()
  expect(screen.getByLabelText('현재 주소')).toHaveTextContent('/signup')
})

it('shows a mail service failure with its request id without automatic retry', async () => {
  const bodies: string[] = []
  network((path, init) => {
    if (path === '/api/auth/signup') { bodies.push(String(init.body)); return failure('UNAVAILABLE', '메일 인증 서비스를 준비 중입니다.', 503) }
    return path.endsWith('/status') ? Response.json({ enabled: false }) : failure()
  })
  open()
  await screen.findByRole('heading', { name: 'SojaFit 회원가입' })
  fill()
  fireEvent.click(screen.getByRole('button', { name: '인증 메일 요청' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('요청 ID: req-test')
  expect(bodies).toHaveLength(1)
})

it('logout from a project address leaves no project id in the address or cached data', async () => {
  let signedIn = true
  network((path) => {
    if (path.endsWith('/logout')) { signedIn = false; return Response.json({ ok: true }) }
    if (path === '/api/projects' || path === '/api/demo-circuits') return Response.json([])
    if (path.startsWith('/api/projects/')) return failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404)
    if (path.endsWith('/status')) return Response.json({ enabled: false })
    return signedIn ? Response.json(user) : failure()
  })
  const { client } = open('/app?projectId=12&targetRef=D1')
  expect(await screen.findByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  await waitFor(() => expect(client.getQueryData(['projects'])).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: /@example\.test$/ }))
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
  expect(await screen.findByRole('heading', { name: 'SojaFit에 로그인' })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 주소')).toHaveTextContent(/^\/login$/)
  expect(client.getQueryData(['projects'])).toBeUndefined()
})
