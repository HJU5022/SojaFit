import { apiFetch } from './client'

export type ProjectSummary = {
  id: number; name: string; source_kind: 'demo' | 'upload'; demo_id: string | null; circuit_version?: number
  created_at: string; updated_at: string
}
export type CircuitPart = { ref: string; value: string; footprint: string; description?: string }
export type CircuitNode = { ref: string; pin: string; pinfunction?: string; function?: string | null }
export type CircuitNet = { code?: string; name: string; nodes: CircuitNode[] }
export type Project = ProjectSummary & { connections: {
  parts?: CircuitPart[]; components?: CircuitPart[]; nets: CircuitNet[]; sample_id?: string; status?: string
} }
export type DemoSchematic = {
  image_url: string
  original_url: string
  source_repo: string
  source_commit: string
  license: string
  license_evidence_url: string
  attribution: string
}
export type DemoCircuit = { id: string; name: string; schematic: DemoSchematic | null }
export const listProjects = (signal?: AbortSignal) => apiFetch<ProjectSummary[]>('/api/projects', { signal })
export const getProject = (id: number, signal?: AbortSignal, threadId = '') => apiFetch<Project>(`/api/projects/${id}${threadId ? `?thread_id=${encodeURIComponent(threadId)}` : ''}`, { signal })
export const createEmptyProject = (name: string) => apiFetch<Project>('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
export function attachNetlist(id: number, file: File, signal?: AbortSignal) {
  const body = new FormData(); body.append('file', file)
  return apiFetch<{ project: Project; thread_id: string }>(`/api/projects/${id}/netlist`, { method: 'POST', body, signal })
}
export const listDemos = (signal?: AbortSignal) => apiFetch<DemoCircuit[]>('/api/demo-circuits', { signal })
export const createDemo = (demo_id: string, name: string, signal?: AbortSignal) => apiFetch<Project>('/api/projects', {
  method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ demo_id, name }),
})
export function uploadProject(name: string, file: File, signal?: AbortSignal) {
  const body = new FormData(); body.append('name', name); body.append('file', file)
  return apiFetch<Project>('/api/projects/upload', { method: 'POST', body, signal })
}
export const renameProject = (id: number, name: string, signal?: AbortSignal) => apiFetch<Project>(`/api/projects/${id}`, {
  method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
})
export const deleteProject = (id: number, signal?: AbortSignal) => apiFetch<void>(`/api/projects/${id}`, { method: 'DELETE', signal })
