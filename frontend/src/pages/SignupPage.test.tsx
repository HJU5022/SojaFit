import { fireEvent, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network, user } from '../test/network'
import { renderWithQueries as render } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
function Location() { return <output aria-label="현재 주소">{useLocation().pathname + useLocation().search}</output> }
function open(path = '/signup') { return render(<MemoryRouter initialEntries={[path]}><App /><Location /></MemoryRouter>) }
function fill(password = 'synthetic-8') {
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'new@example.test' } })
  fireEvent.change(screen.getByLabelText('비밀번호(8자 이상)'), { target: { value: password } })
}

it('shows the privacy notice and sends nothing until consent and an 8+ character password', async () => {
  const requested: string[] = []
  network((path) => { requested.push(path); return path.endsWith('/status') ? Response.json({ enabled: false }) : failure() })
  open()
  const notice = await screen.findByRole('region', { name: '개인정보 처리 안내' })
  for (const text of ['쓰는 목적', '계정(이메일', '내 설정 3칸', '60일', '30일', '직접 지울 때까지', '바로 지웁니다', '질문 · 답변 글을 넣지 않습니다', '이름 · 모델 · 토큰 · 비용 · 시간만 보냅니다', '서비스 데이터베이스에 저장', 'OpenRouter', 'Voyage', '거부하면 가입할 수 없습니다'])
    expect(notice).toHaveTextContent(text)
  const submit = screen.getByRole('button', { name: '가입' })
  fill('short-7'); fireEvent.click(screen.getByRole('checkbox', { name: /개인정보 수집 · 이용에 동의합니다/ }))
  expect(submit).toBeDisabled()  // 8자 미만
  fill(); fireEvent.click(screen.getByRole('checkbox', { name: /동의합니다/ }))
  expect(submit).toBeDisabled()  // 동의를 다시 끔
  fireEvent.submit(submit.closest('form')!)
  expect(requested).not.toContain('/api/auth/signup')
})

it('signs up with consent, opens the workbench, and offers login from the signup page', async () => {
  let signedIn = false
  const bodies: string[] = []
  network((path, init) => {
    if (path === '/api/auth/signup') { bodies.push(String(init.body)); signedIn = true; return Response.json({ user_id: 7 }) }
    if (path === '/api/projects' || path === '/api/demo-circuits') return Response.json([])
    if (path.endsWith('/status')) return Response.json({ enabled: false })
    return signedIn ? Response.json(user) : failure()
  })
  open()
  expect(await screen.findByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login')
  fill(); fireEvent.click(screen.getByRole('checkbox', { name: /동의합니다/ }))
  fireEvent.click(screen.getByRole('button', { name: '가입' }))
  expect(await screen.findByRole('heading', { name: '회로에 맞는 대체 부품을 찾아보세요' })).toBeInTheDocument()
  expect(bodies).toEqual([JSON.stringify({ email: 'new@example.test', password: 'synthetic-8', consent: true })])
})

it('shows a duplicate email error with its request id and clears the password', async () => {
  network((path) => path === '/api/auth/signup' ? failure('CONFLICT', '이미 가입된 이메일입니다.', 409)
    : path.endsWith('/status') ? Response.json({ enabled: false }) : failure())
  open()
  await screen.findByRole('region', { name: '개인정보 처리 안내' })
  fill(); fireEvent.click(screen.getByRole('checkbox', { name: /동의합니다/ }))
  fireEvent.click(screen.getByRole('button', { name: '가입' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('이미 가입된 이메일입니다. (요청 ID: req-test)')
  expect(screen.getByLabelText('비밀번호(8자 이상)')).toHaveValue('')
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
  expect(client.getQueryData(['projects'])).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: /사용자 \d+/ }))
  fireEvent.click(screen.getByRole('menuitem', { name: '로그아웃' }))
  expect(await screen.findByRole('heading', { name: '로그인' })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 주소')).toHaveTextContent(/^\/login$/)
  expect(client.getQueryData(['projects'])).toBeUndefined()
})
