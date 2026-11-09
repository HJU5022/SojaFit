import { apiFetch } from './client'
import type { User } from './auth'

export type Account = { id: number; email: string; role: User['role']; is_active: boolean }
export const getUsers = () => apiFetch<{ users: Account[] }>('/api/admin/users')
export const setUserActive = (id: number, is_active: boolean) => apiFetch<{ ok: boolean }>(`/api/admin/users/${id}`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active }),
})
