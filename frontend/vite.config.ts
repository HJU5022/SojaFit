import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const DUMMY_CIRCUITS_ID = 'virtual:sojafit-dummy-circuits'
const DUMMY_CIRCUITS_RESOLVED_ID = `\0${DUMMY_CIRCUITS_ID}`
const repositoryRoot = fileURLToPath(new URL('../', import.meta.url))
type CatalogEntry = { name: string; connections_path: string }

function demoSources() {
  const raw = JSON.parse(readFileSync(resolve(repositoryRoot, 'data/circuits/catalog.json'), 'utf8')) as Record<string, CatalogEntry>
  return Object.entries(raw).map(([id, entry]) => [id, entry.name, entry.connections_path] as const)
}

function dummyCircuitsPlugin() {
  return {
    name: 'sojafit-dummy-circuits',
    resolveId(id: string) { return id === DUMMY_CIRCUITS_ID ? DUMMY_CIRCUITS_RESOLVED_ID : undefined },
    load(id: string) {
      if (id !== DUMMY_CIRCUITS_RESOLVED_ID) return undefined
      const visuals = JSON.parse(readFileSync(resolve(repositoryRoot, 'data/circuits/visuals.json'), 'utf8'))
      const createdAt = '2026-11-09T00:00:00Z'
      const sources = demoSources()
      const demos = sources.map(([demoId, name]) => ({ id: demoId, name, schematic: visuals[demoId] ? {
        image_url: visuals[demoId].image_url,
        original_url: visuals[demoId].original_url,
        source_repo: visuals[demoId].source_repo,
        source_commit: visuals[demoId].source_commit,
        license: visuals[demoId].license,
        license_evidence_url: visuals[demoId].license_evidence_url,
        attribution: visuals[demoId].attribution,
      } : null }))
      const projects = sources.map(([demoId, , source], index) => ({
        id: index + 1, name: demoId, source_kind: 'demo', demo_id: demoId,
        created_at: createdAt, updated_at: createdAt,
        connections: JSON.parse(readFileSync(resolve(repositoryRoot, source), 'utf8')),
      }))
      return `export const dummyDemos = ${JSON.stringify(demos)}; export const dummyProjects = ${JSON.stringify(projects)};`
    },
  }
}

export default defineConfig({
  plugins: [react(), dummyCircuitsPlugin()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  test: { environment: 'jsdom', css: true, setupFiles: ['./src/test/setup.ts'] },
})
