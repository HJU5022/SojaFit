import { screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchPage from './WorkbenchPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user, logout: vi.fn() }) }))
vi.mock('../components/Review', () => ({ default: () => null }))
vi.mock('../components/ApprovedCases', () => ({ default: () => null }))
afterEach(() => vi.unstubAllGlobals())

const schematic = { image_url: '/circuit-schematics/c1.png', original_url: 'https://example.test/o', source_repo: 'https://example.test/r', source_commit: 'a'.repeat(40),
  license: 'MIT', license_evidence_url: 'https://example.test/l', attribution: '시험' }
const demoProject = { id: 1, name: '예제', source_kind: 'demo', demo_id: 'c1', created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }], nets: [] } }
const api = (demos: () => Response) => network((path) => {
  if (path === '/api/demo-circuits') return demos()
  if (path === '/api/projects') return Response.json([demoProject])
  if (path === '/api/projects/1') return Response.json(demoProject)
  return Response.json([])
})
const open = () => renderWithQueries(<MemoryRouter initialEntries={['/app?projectId=1&targetRef=D1']}><WorkbenchPage /></MemoryRouter>)

it('shows only upload when the demo catalogue is unavailable (DEMO_MODE=0), without an error notice', async () => {
  api(() => failure('NOT_FOUND', 'Not Found', 404))
  open()
  await waitFor(() => expect(screen.queryByText('예제 회로를 불러오는 중입니다.')).not.toBeInTheDocument())
  expect(screen.getByText(/KiCad 넷리스트 \(\.net/)).toBeInTheDocument()
  expect(screen.queryByText('파일이 없으면 예제 회로로 시작')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로가 없습니다. KiCad 넷리스트 파일을 선택해 주세요.')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로 목록을 불러오지 못했습니다.')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /원본 회로도/ })).not.toBeInTheDocument()
})

it('offers the example select and the pre-stored schematic of a demo project when the catalogue is available', async () => {
  api(() => Response.json([{ id: 'c1', name: '예제 회로 1', schematic }]))
  open()
  expect(await screen.findByText('파일이 없으면 예제 회로로 시작')).toBeInTheDocument()
  expect(screen.getByText('예제 회로 1', { selector: 'option' })).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: /원본 회로도/ })).toBeInTheDocument()
})

it('still reports a real catalogue failure (not 404)', async () => {
  api(() => failure('UNAVAILABLE', '내부', 503))
  open()
  expect(await screen.findByText('예제 회로 목록을 불러오지 못했습니다.')).toBeInTheDocument()
})
