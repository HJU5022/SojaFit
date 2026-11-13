import { apiFetch } from './client'

export type ExternalSchematicResult = {
  project: string; commit: string; license: string; attribution: string
  repository_url: string; source_url: string; source_file: string
  images: { sheet: number; url: string }[]
}
// 각 시트 이미지(GET /api/external-circuits/schematics/{token}/{sheet})는 images[].url을 <img>가 같은 세션 쿠키로 불러온다.
export const findSchematic = (q: string, signal?: AbortSignal) =>
  apiFetch<ExternalSchematicResult>(`/api/external-circuits/schematics?q=${encodeURIComponent(q)}`, { signal })
