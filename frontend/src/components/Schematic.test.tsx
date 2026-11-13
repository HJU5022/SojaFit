import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { focusManager, onlineManager, QueryClientProvider } from '@tanstack/react-query'
import { failure, network } from '../test/network'
import { renderWithQueries } from '../test/projects'
import { ExternalSchematic } from './Schematic'

afterEach(() => { cleanup(); focusManager.setFocused(undefined); onlineManager.setOnline(true); vi.unstubAllGlobals(); vi.restoreAllMocks() })
const found = { project: 'Board', commit: 'a'.repeat(40), license: 'MIT', attribution: 'Maker', repository_url: 'https://example.test/r', source_url: 'https://example.test/r/board.kicad_sch', source_file: 'board.kicad_sch',
  source_type: 'manufacturer_official' as const, evidence_grade: 2 as const, manufacturer: 'Maker', model: 'Board', revision: 'v1', source_sha256: 'b'.repeat(64), license_evidence_url: 'https://example.test/r/LICENSE',
  images: [{ sheet: 0, url: '/api/external-circuits/schematics/t/0' }, { sheet: 1, url: '/api/external-circuits/schematics/t/1' }] }
const search = () => fireEvent.click(screen.getByRole('button', { name: '원본 회로도 찾기' }))

it.each(['success', 'error'])('does not repeat a stale %s search on focus, reconnect, or reopening', async state => {
  const handler = vi.fn(() => state === 'success' ? Response.json(found) : failure('SCHEMATIC_NOT_FOUND', '없음', 404))
  network(handler)
  const view = renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  expect(handler).not.toHaveBeenCalled()
  search()
  await waitFor(() => expect(view.client.getQueryState(['external-schematic', 'Board'])?.status).toBe(state))
  const later = Date.now() + 16 * 60_000
  vi.spyOn(Date, 'now').mockReturnValue(later)
  await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(handler).toHaveBeenCalledTimes(1)
  await act(async () => { onlineManager.setOnline(false); onlineManager.setOnline(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(handler).toHaveBeenCalledTimes(1)
  view.unmount()
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />, view.client)
  expect(handler).toHaveBeenCalledTimes(1)
  search()
  await waitFor(() => expect(handler).toHaveBeenCalledTimes(2))
  view.client.clear()
})

it('reuses a fresh successful search but explicitly refreshes the same term after five minutes', async () => {
  const handler = vi.fn(() => Response.json(found))
  network(handler)
  const view = renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  await waitFor(() => expect(view.client.getQueryState(['external-schematic', 'Board'])?.status).toBe('success'))
  search()
  expect(handler).toHaveBeenCalledTimes(1)
  const later = Date.now() + 6 * 60_000
  vi.spyOn(Date, 'now').mockReturnValue(later)
  view.rerender(<QueryClientProvider client={view.client}><ExternalSchematic name="Board" zoom={125} /></QueryClientProvider>)
  expect(handler).toHaveBeenCalledTimes(1)
  search()
  await waitFor(() => expect(handler).toHaveBeenCalledTimes(2))
  view.client.clear()
})

it('only searches again after an image error when its retry button is pressed', async () => {
  const handler = vi.fn(() => Response.json(found))
  network(handler)
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  const images = await screen.findAllByAltText(/원본 회로도/)
  fireEvent.error(images[0])
  expect(screen.getByRole('alert')).toHaveTextContent('원본 회로도를 불러오지 못했습니다.')
  expect(handler).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '다시 검색하기' }))
  await waitFor(() => expect(handler).toHaveBeenCalledTimes(2))
})

it('searches the project name only when asked, and shows every sheet in order with attribution', async () => {
  const paths: string[] = []
  network(path => { paths.push(path); return Response.json(found) })
  renderWithQueries(<ExternalSchematic name="My Board" zoom={100} />)
  expect(screen.getByRole('textbox')).toHaveValue('My Board')
  expect(paths).toEqual([])
  search()
  const images = await screen.findAllByAltText(/원본 회로도/, { exact: false })
  expect(paths).toEqual(['/api/external-circuits/schematics?q=My%20Board'])
  expect(images.map(image => image.getAttribute('src'))).toEqual(found.images.map(image => image.url))
  expect(images.map(image => image.getAttribute('alt'))).toEqual(['Board 시트 1 원본 회로도', 'Board 시트 2 원본 회로도'])
  expect(screen.getAllByText('출처: Maker')).toHaveLength(2)
  expect(screen.getAllByText('라이선스: MIT')).toHaveLength(2)
  expect(screen.getAllByText('제조사 공식 원본 · 2등급')).toHaveLength(2)
  expect(screen.getAllByText('Maker · Board · v1')).toHaveLength(2)
  expect(screen.getAllByRole('link')[0]).toHaveAttribute('href', found.source_url)
})

it('blocks queries outside 2-200 characters without calling the API', () => {
  const handler = vi.fn(() => Response.json(found))
  network(handler)
  renderWithQueries(<ExternalSchematic name="A" zoom={100} />)
  expect(screen.getByRole('button', { name: '원본 회로도 찾기' })).toBeDisabled()
  expect(screen.getByText('2자 이상 200자 이하로 입력해 주세요.')).toBeInTheDocument()
  fireEvent.submit(screen.getByRole('textbox').closest('form')!)
  expect(handler).not.toHaveBeenCalled()
})

it.each([
  ['not found', failure('SCHEMATIC_NOT_FOUND', '없음', 404), /공개된 원본 회로도를 찾지 못했습니다/, true],
  ['rate limited', Response.json({ error: { code: 'UNAVAILABLE', message: 'x', request_id: 'r' } }, { status: 503, headers: { 'Retry-After': '120' } }), /2분 뒤에 다시/, true],
  ['disabled', failure('UNAVAILABLE', 'x', 503), /이 환경에서는 외부 원본 회로도를 사용할 수 없습니다/, false],
])('shows the %s state', async (_name, response, message, canRetry) => {
  network(() => response.clone())
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  expect(await screen.findByText(message)).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByRole('button', { name: '원본 회로도 찾기' }) !== null).toBe(canRetry))
})
