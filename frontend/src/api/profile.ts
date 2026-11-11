import { apiFetch } from './client'

// 내 설정(사용자 사실 기억, SPEC 8.5). 사용자 id는 서버가 세션에서 정하므로 보내지 않는다.
export type ProfileKind = 'affiliation' | 'job_role' | 'mounting_preference'
export type ProfileFactDto = { kind: ProfileKind; value: string; text: string; version: number; updated_at: string; source: string }
export type ProfileHintDto = { kind: ProfileKind; value: string; text: string }
export type ProfileChanges = Partial<Record<ProfileKind, string>>

export const JOB_ROLES: Record<string, string> = { design: '설계', purchasing: '구매', student: '학생', other: '기타' }
export const MOUNTING: Record<string, string> = { smd: 'SMD', through_hole: '스루홀', any: '상관없음' }

export const getProfile = (signal?: AbortSignal) => apiFetch<ProfileFactDto[]>('/api/me/memory', { signal })
export const updateProfile = (changes: ProfileChanges, signal?: AbortSignal) => apiFetch<ProfileFactDto[]>('/api/me/memory', {
  method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes),
})
export const deleteProfile = (kind?: ProfileKind, signal?: AbortSignal) => apiFetch<void>(kind ? `/api/me/memory?kind=${kind}` : '/api/me/memory', { method: 'DELETE', signal })
