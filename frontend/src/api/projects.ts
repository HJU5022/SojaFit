import { apiFetch } from './client'

export type ProjectSummary = {
  id: number; name: string; source_kind: 'demo' | 'upload'; demo_id: string | null
  created_at: string; updated_at: string
}
export type CircuitPart = { ref: string; value: string; footprint: string; description?: string }
type CircuitNet = { code?: string; name: string; nodes: { ref: string; pin: string; pinfunction?: string; function?: string | null }[] }
export type Project = ProjectSummary & { connections: {
  parts?: CircuitPart[]; components?: CircuitPart[]; nets: CircuitNet[]; sample_id?: string; status?: string
} }
export type DemoCircuit = { id: string; name: string }
export const listProjects = (signal?: AbortSignal) => apiFetch<ProjectSummary[]>('/api/projects', { signal })
export const getProject = (id: number, signal?: AbortSignal) => apiFetch<Project>(`/api/projects/${id}`, { signal })
export const listDemos = (signal?: AbortSignal) => apiFetch<DemoCircuit[]>('/api/demo-circuits', { signal })
export const createDemo = (demo_id: string, name: string) => apiFetch<Project>('/api/projects', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ demo_id, name }),
})
export function uploadProject(name: string, file: File) {
  const body = new FormData(); body.append('name', name); body.append('file', file)
  return apiFetch<Project>('/api/projects/upload', { method: 'POST', body })
}
export const renameProject = (id: number, name: string) => apiFetch<Project>(`/api/projects/${id}`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
})
export const deleteProject = (id: number) => apiFetch<void>(`/api/projects/${id}`, { method: 'DELETE' })
