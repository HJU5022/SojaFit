import { afterEach, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { network } from '../test/network'
import { renderWithQueries } from '../test/projects'
import WorkbenchPage from './WorkbenchPage'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user: { user_id: 7, email: 'user@example.test', role: 'user' }, logout: vi.fn() }) }))
afterEach(() => vi.unstubAllGlobals())

const summary = { source_kind: 'demo', created_at: '', updated_at: '2026-11-13T00:00:00Z' }
const connections = { parts: [{ ref: 'D1', value: 'SS34', footprint: '' }], nets: [] }
const stored = { image_url: '/circuit-schematics/a.png', original_url: 'https://example.test/a', source_repo: '', source_commit: '', license: 'MIT', license_evidence_url: '', attribution: 'Maker' }
function open(demoId: string | null) {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([{ id: 'a', name: 'A', schematic: stored }])
    if (path === '/api/projects/1') return Response.json({ ...summary, id: 1, name: '내 보드', demo_id: demoId, source_kind: demoId ? 'demo' : 'upload', connections })
    return Response.json([])
  })
  renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1']}><WorkbenchPage /></MemoryRouter>)
}

it('keeps the pre-stored schematic for demo projects', async () => {
  open('a')
  expect((await screen.findByAltText('내 보드 원본 회로도', { exact: true }) as HTMLImageElement).getAttribute('src')).toBe(stored.image_url)
  expect(screen.queryByRole('textbox', { name: /검색어/, hidden: true })).toBeNull()
})

it('offers the web search for uploaded projects, defaulting to the project name', async () => {
  open(null)
  await waitFor(() => expect(screen.getByRole('textbox', { name: /검색어/, hidden: true })).toHaveValue('내 보드'))
  expect(screen.getByRole('button', { name: '원본 회로도' })).toBeInTheDocument()
})
