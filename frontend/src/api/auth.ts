import { apiFetch } from './client'

export type User = { user_id: number; role: 'admin' | 'user'; email: string }
// 탈퇴 응답: 지운 건수(분석 thread · 회로 · checkpoint · 내 설정 항목 · 프로젝트 · 견적 · 계정)
export type DeletedCounts = Record<string, number>
export const getMe = (signal?: AbortSignal) => apiFetch<User>('/api/auth/me', { signal })
export const getGoogleStatus = () => apiFetch<{ enabled: boolean }>('/api/auth/google/status')
export const login = (email: string, password: string) => apiFetch<{ user_id: number }>('/api/auth/login', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
})
// consent는 처리방침 고지를 읽고 동의했다는 표시다. 서버는 true가 아니면 422로 거절한다(개인정보 보호법 15조)
export const signup = (email: string, password: string) => apiFetch<{ user_id: number }>('/api/auth/signup', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password, consent: true }),
})
// 데모 모드(DEMO_MODE=1)에서만 있는 버튼 로그인. 아니면 둘 다 404라 화면은 버튼을 숨긴다
export type DemoAccount = 'a' | 'b'
export const getDemoStatus = () => apiFetch<{ enabled: boolean }>('/api/auth/demo')
export const demoLogin = (account: DemoAccount) => apiFetch<{ user_id: number }>('/api/auth/demo-login', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account }),
})
export const logout = () => apiFetch<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
export const deleteAccount = () => apiFetch<{ deleted: DeletedCounts }>('/api/me', { method: 'DELETE' })
