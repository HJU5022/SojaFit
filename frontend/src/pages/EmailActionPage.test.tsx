import { StrictMode } from 'react'
import { act, fireEvent, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { failure, network } from '../test/network'
import { renderWithQueries as render } from '../test/projects'

const token = 'x'.repeat(43)
const password = 'correct horse battery staple'
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState({}, '', '/') })
function open(path: string, linkToken = '') {
  window.history.replaceState({}, '', path + (linkToken ? '#token=' + linkToken : ''))
  render(<StrictMode><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></StrictMode>)
}
function fill(value = password, confirmation = value) {
  fireEvent.change(screen.getByLabelText('새 비밀번호(12자 이상)'), { target: { value } })
  fireEvent.change(screen.getByLabelText('새 비밀번호 확인'), { target: { value: confirmation } })
}

it.each(['/verify-email', '/reset-password'])('shows only the first unmet requirement while typing on %s', async path => {
  network(() => failure())
  open(path, token)
  const input = await screen.findByLabelText('새 비밀번호(12자 이상)')
  const issue = screen.getByRole('status')
  expect(screen.queryByText('12~1,024자로 입력해 주세요.')).not.toBeInTheDocument()
  expect(input).not.toHaveAttribute('aria-invalid')
  for (const [value, reason] of [
    ['short', '12자 이상 입력해 주세요.'],
    ['x'.repeat(1025), '1,024자 이하로 입력해 주세요.'],
    [' '.repeat(12), '공백만 사용할 수 없어요.'],
    ['１２３４５６７８９０１２', '숫자 외 문자도 넣어 주세요.'],
    ['abcabcabcabc', '단순 반복은 사용할 수 없어요.'],
  ]) {
    fireEvent.change(input, { target: { value } })
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription(reason)
    expect(issue).toHaveTextContent(reason)
  }
  fill()
  expect(input).not.toHaveAttribute('aria-invalid')
  expect(input).not.toHaveAttribute('aria-describedby')
  expect(issue).toBeEmptyDOMElement()
  expect(screen.getByRole('button', { name: path === '/verify-email' ? '인증하고 가입 완료' : '비밀번호 변경' })).toBeEnabled()
  fireEvent.change(input, { target: { value: '' } })
  expect(issue).toBeEmptyDOMElement()
})

it('removes the token from the address and verifies email only after confirmed password submission', async () => {
  const requests: { path: string; body: string }[] = []
  network((path, init) => { requests.push({ path, body: String(init.body) }); return path.endsWith('/confirm') ? Response.json({ ok: true }) : failure() })
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  open('/verify-email', token)
  await screen.findByRole('heading', { name: '이메일 인증 및 비밀번호 설정' })
  expect(window.location.hash).toBe('')
  expect(requests.filter(x => x.path.endsWith('/confirm'))).toHaveLength(0)
  fill()
  fireEvent.click(screen.getByRole('button', { name: '인증하고 가입 완료' }))
  expect(await screen.findByText('가입이 완료되었습니다. 로그인해 주세요.')).toBeInTheDocument()
  expect(requests.find(x => x.path.endsWith('/confirm'))).toEqual({ path: '/api/auth/signup/confirm', body: JSON.stringify({ token, password }) })
  expect(storage).not.toHaveBeenCalled()
})

it.each(['12345678', ' '.repeat(15), '1'.repeat(15), 'abcabcabcabcabc', '🔒🔑🚀🌙🌟🎯📚💡'])('blocks a weak password before completing an email action: %s', async weak => {
  network(() => failure())
  open('/verify-email', token)
  await screen.findByRole('heading', { name: '이메일 인증 및 비밀번호 설정' })
  fill(weak)
  expect(screen.getByRole('button', { name: '인증하고 가입 완료' })).toBeDisabled()
})

it('requires matching passwords and clears both values after a failed completion', async () => {
  network(path => path.endsWith('/confirm') ? failure('BAD_REQUEST', '링크를 사용할 수 없습니다.', 400) : failure())
  open('/reset-password', token)
  await screen.findByRole('heading', { name: '새 비밀번호 설정' })
  fill(password, 'different valid passphrase')
  expect(screen.getByRole('button', { name: '비밀번호 변경' })).toBeDisabled()
  expect(screen.getByLabelText('새 비밀번호 확인')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText('새 비밀번호 확인')).toHaveAccessibleDescription('비밀번호가 일치하지 않습니다.')
  fill()
  expect(screen.getByLabelText('새 비밀번호 확인')).not.toHaveAttribute('aria-invalid')
  fireEvent.click(screen.getByRole('button', { name: '비밀번호 변경' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('요청 ID: req-test')
  expect(screen.getByLabelText('새 비밀번호(12자 이상)')).toHaveValue('')
  expect(screen.getByLabelText('새 비밀번호 확인')).toHaveValue('')
})

it('requests password recovery without disclosing whether an account exists', async () => {
  const bodies: string[] = []
  network((path, init) => { if (path === '/api/auth/password-reset') { bodies.push(String(init.body)); return Response.json({ ok: true }) } return failure() })
  open('/reset-password')
  await screen.findByRole('heading', { name: '비밀번호 재설정' })
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'old@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: '재설정 메일 요청' }))
  expect(await screen.findByRole('status')).toHaveTextContent('가능한 계정이라면')
  expect(bodies).toEqual([JSON.stringify({ email: 'old@example.test' })])
})

it('never accepts a verification page without a valid link token', async () => {
  network(() => failure())
  open('/verify-email')
  expect(await screen.findByRole('alert')).toHaveTextContent('링크')
  expect(screen.queryByLabelText('새 비밀번호(12자 이상)')).not.toBeInTheDocument()
})

it('reads a new mail fragment while the reset request page is already open', async () => {
  network(() => failure())
  open('/reset-password')
  await screen.findByRole('heading', { name: '비밀번호 재설정' })
  window.history.replaceState({}, '', '/reset-password#token=' + token)
  fireEvent(window, new HashChangeEvent('hashchange'))
  expect(await screen.findByRole('heading', { name: '새 비밀번호 설정' })).toBeInTheDocument()
  expect(window.location.hash).toBe('')
})

it('ignores a late completion from the previous link after a new link arrives', async () => {
  let finish: ((response: Response) => void) | undefined
  network(path => path.endsWith('/confirm') ? new Promise<Response>(resolve => { finish = resolve }) : failure())
  open('/verify-email', token)
  await screen.findByRole('heading', { name: '이메일 인증 및 비밀번호 설정' })
  fill()
  fireEvent.click(screen.getByRole('button', { name: '인증하고 가입 완료' }))
  window.history.replaceState({}, '', '/verify-email#token=' + 'y'.repeat(43))
  fireEvent(window, new HashChangeEvent('hashchange'))
  fill('a different safe passphrase')
  await act(async () => { finish!(Response.json({ ok: true })) })
  expect(screen.queryByText('가입이 완료되었습니다. 로그인해 주세요.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('새 비밀번호(12자 이상)')).toHaveValue('a different safe passphrase')
})


it.each([['safe-word-1', false], ['safe-word-12', true]])('checks the 12 character boundary: %s', async (value, allowed) => {
  network(() => failure())
  open('/verify-email', token)
  await screen.findByRole('heading', { name: '이메일 인증 및 비밀번호 설정' })
  fill(String(value))
  const button = screen.getByRole('button', { name: '인증하고 가입 완료' })
  if (allowed) expect(button).toBeEnabled()
  else expect(button).toBeDisabled()
})
