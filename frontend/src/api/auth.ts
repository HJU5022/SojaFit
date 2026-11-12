import { apiFetch } from './client'

// 신규 설정에만 적용한다. 기존 계정 로그인은 서버의 기존 해시 검증을 사용한다.
export function newPasswordIssue(password: string): string {
  const chars = Array.from(password)
  if (chars.length < 12) return '12자 이상 입력해 주세요.'
  if (chars.length > 1024) return '1,024자 이하로 입력해 주세요.'
  const compact = password.replace(/[\s\u0085\u001c-\u001f]/gu, '')
  if (!compact.length) return '공백만 사용할 수 없어요.'
  if (/^\p{Decimal_Number}+$/u.test(compact)) return '숫자 외 문자도 넣어 주세요.'
  const repeated = [1, 2, 3, 4].some(width => chars.every((char, index) => char === chars[index % width]))
  return repeated ? '단순 반복은 사용할 수 없어요.' : ''
}

export type User = { user_id: number; role: 'admin' | 'user'; email: string }
// 탈퇴 응답: 지운 건수(분석 thread · 회로 · checkpoint · 내 설정 항목 · 프로젝트 · 견적 · 계정)
export type DeletedCounts = Record<string, number>
export const getMe = (signal?: AbortSignal) => apiFetch<User>('/api/auth/me', { signal })
export const getGoogleStatus = () => apiFetch<{ enabled: boolean }>('/api/auth/google/status')
export const getGoogleOnboarding = () => apiFetch<{ email: string }>('/api/auth/google/onboarding')
export const googleSignup = () => apiFetch<{ user_id: number }>('/api/auth/google/signup', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
})
export const googleLink = (email: string, password: string) => apiFetch<{ user_id: number }>('/api/auth/google/link', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
})
export const login = (email: string, password: string) => apiFetch<{ user_id: number }>('/api/auth/login', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
})
export const signup = (email: string) => apiFetch<{ ok: boolean }>('/api/auth/signup', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
})
export const completeSignup = (token: string, password: string) => apiFetch<{ ok: boolean }>('/api/auth/signup/confirm', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, password }),
})
export const requestPasswordReset = (email: string) => apiFetch<{ ok: boolean }>('/api/auth/password-reset', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
})
export const completePasswordReset = (token: string, password: string) => apiFetch<{ ok: boolean }>('/api/auth/password-reset/confirm', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, password }),
})
// 데모 모드(DEMO_MODE=1)에서만 있는 버튼 로그인. 아니면 둘 다 404라 화면은 버튼을 숨긴다
export type DemoAccount = 'a' | 'b'
export const getDemoStatus = () => apiFetch<{ enabled: boolean }>('/api/auth/demo')
export const demoLogin = (account: DemoAccount) => apiFetch<{ user_id: number }>('/api/auth/demo-login', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account }),
})
export const logout = () => apiFetch<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
export const deleteAccount = () => apiFetch<{ deleted: DeletedCounts }>('/api/me', { method: 'DELETE' })
