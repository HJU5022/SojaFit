import { apiFetch } from './client'

export type User = { user_id: number; role: 'admin' | 'user' }
export const getMe = () => apiFetch<User>('/api/auth/me')
export const getGoogleStatus = () => apiFetch<{ enabled: boolean }>('/api/auth/google/status')
export const login = (email: string, password: string) => apiFetch<{ user_id: number }>('/api/auth/login', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
})
export const logout = () => apiFetch<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
