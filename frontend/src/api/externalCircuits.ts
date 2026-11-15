import { apiFetch } from './client'

export type ExternalSchematicResult = {
  project: string | null; commit: string | null; license: string; attribution: string
  repository_url: string | null; source_url: string; source_file: string
  source_type: 'manufacturer_official' | 'community' | 'public_web'
  evidence_grade: 2 | 3 | null
  manufacturer: string | null; model: string | null; revision: string | null
  source_sha256: string | null; license_evidence_url: string | null
  images: { sheet: number; url: string }[]
  choices: { title: string; source_url: string; source_type: 'manufacturer_official' | 'public_web' | 'community'; revision: string | null }[]
  circuit_version?: number | null
}
export type SchematicContext = { projectId: number; circuitVersion: number; threadId?: string }
// 각 시트 이미지(GET /api/external-circuits/schematics/{token}/{sheet})는 images[].url을 <img>가 같은 세션 쿠키로 불러온다.
export const findSchematic = (q: string, signal?: AbortSignal, sourceUrl?: string, context?: SchematicContext, componentType?: 'diode') =>
  apiFetch<ExternalSchematicResult>(`/api/external-circuits/schematics?q=${encodeURIComponent(q)}${sourceUrl ? `&source_url=${encodeURIComponent(sourceUrl)}` : ''}${context ? `&project_id=${context.projectId}&circuit_version=${context.circuitVersion}${context.threadId ? `&thread_id=${encodeURIComponent(context.threadId)}` : ''}` : '&reference_only=true'}${componentType ? `&component_type=${componentType}` : ''}`, { signal })
