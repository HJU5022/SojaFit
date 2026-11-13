import { fireEvent, screen, waitFor } from '@testing-library/react'
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
const made = (demoId: string | null, name = '예제') => ({ id: 1, name, source_kind: demoId ? 'demo' : 'upload', demo_id: demoId, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }], nets: [] } })
const catalogue = () => Response.json([{ id: 'c1', name: '예제 회로 1', schematic }])
const disabledSearch = () => failure('UNAVAILABLE', '꺼짐', 503)
// demos: 예제 회로 목록 응답, found: 열려 있는 프로젝트, external: 웹 검색 응답
const api = (demos: () => Response | Promise<Response>, found = made('c1'), external: () => Response = () => Response.json([])) => network((path) => {
  if (path === '/api/demo-circuits') return demos()
  if (path.startsWith('/api/external-circuits/')) return external()
  if (path === '/api/projects') return Response.json([found])
  if (path === '/api/projects/1') return Response.json(found)
  return Response.json([])
})
const open = (query = 'projectId=1&targetRef=D1') => renderWithQueries(<MemoryRouter initialEntries={[`/app?${query}`]}><WorkbenchPage /></MemoryRouter>)
const searchBox = () => screen.queryByRole('textbox', { name: /검색어/, hidden: true })
const sheetButton = () => screen.queryByRole('button', { name: /원본 회로도/ })

it('shows only upload when the demo catalogue is unavailable (DEMO_MODE=0), without an error notice', async () => {
  api(() => failure('NOT_FOUND', 'Not Found', 404))
  open()
  await waitFor(() => expect(screen.queryByText('예제 회로를 불러오는 중입니다.')).not.toBeInTheDocument())
  expect(screen.getByText(/KiCad 넷리스트 \(\.net/)).toBeInTheDocument()
  expect(screen.queryByText('파일이 없으면 예제 회로로 시작')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로가 없습니다. KiCad 넷리스트 파일을 선택해 주세요.')).not.toBeInTheDocument()
  expect(screen.queryByText('예제 회로 목록을 불러오지 못했습니다.')).not.toBeInTheDocument()
})

it('offers the example select and the pre-stored schematic of a demo project when the catalogue is available', async () => {
  api(catalogue)
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

it('keeps the pre-stored schematic for demo projects', async () => {
  api(catalogue, made('c1', '내 보드'))
  open('projectId=1')
  expect((await screen.findByAltText('내 보드 원본 회로도', { exact: true }) as HTMLImageElement).getAttribute('src')).toBe(schematic.image_url)
  expect(searchBox()).toBeNull()
})

it('offers the web search for uploaded projects, defaulting to the project name', async () => {
  api(catalogue, made(null, '내 보드'))
  open('projectId=1')
  await waitFor(() => expect(searchBox()).toHaveValue('내 보드'))
  expect(screen.getByRole('button', { name: '원본 회로도' })).toBeInTheDocument()
})

it.each([['uploaded', null], ['old demo (demo_id kept)', 'c1']])('production (catalogue 404): %s project gets the web search and no catalogue notice', async (_, demoId) => {
  api(() => failure('NOT_FOUND', 'Not Found', 404), made(demoId, '내 보드'))
  open()
  expect(await screen.findByRole('button', { name: /원본 회로도/ })).toBeInTheDocument()
  expect(searchBox()).toHaveValue('내 보드')
  expect(screen.queryByAltText('내 보드 원본 회로도')).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
})

it('demo mode: an uploaded project says the search is unavailable (503 without Retry-After) and hides the search box', async () => {
  api(catalogue, made(null, '내 보드'), disabledSearch)
  open()
  await screen.findByRole('button', { name: /원본 회로도/ })
  fireEvent.click(screen.getByRole('button', { name: '원본 회로도 찾기', hidden: true }))
  expect(await screen.findByText(/이 환경에서는 외부 원본 회로도를 사용할 수 없습니다/, undefined, { timeout: 2000 })).toBeInTheDocument()
  expect(searchBox()).toBeNull()
})

it('does not show the schematic button for a demo project while the catalogue is still pending', async () => {
  api(() => new Promise<Response>(() => {}))
  open()
  await screen.findAllByText('예제')
  await waitFor(() => expect(screen.getByText('D1')).toBeInTheDocument())
  expect(sheetButton()).toBeNull()
})
