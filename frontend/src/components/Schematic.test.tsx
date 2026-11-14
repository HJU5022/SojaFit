import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { focusManager, onlineManager, QueryClientProvider } from '@tanstack/react-query'
import { failure, network } from '../test/network'
import { renderWithQueries } from '../test/projects'
import { ExternalSchematic, SchematicImage } from './Schematic'

afterEach(() => { cleanup(); focusManager.setFocused(undefined); onlineManager.setOnline(true); vi.unstubAllGlobals(); vi.restoreAllMocks() })
const found = { project: 'Board', commit: 'a'.repeat(40), license: 'MIT', attribution: 'Maker', repository_url: 'https://example.test/r', source_url: 'https://example.test/r/board.kicad_sch', source_file: 'board.kicad_sch',
  source_type: 'manufacturer_official' as const, evidence_grade: 2 as const, manufacturer: 'Maker', model: 'Board', revision: 'v1', source_sha256: 'b'.repeat(64), license_evidence_url: 'https://example.test/r/LICENSE',
  choices: [],
  images: [{ sheet: 0, url: '/api/external-circuits/schematics/t/0' }, { sheet: 1, url: '/api/external-circuits/schematics/t/1' }] }
const search = () => fireEvent.click(screen.getByRole('button', { name: '원본 회로도 찾기' }))

const picture = { image_url: '/circuit-schematics/breadboard_supply.png', original_url: 'https://example.test/original.pdf', attribution: 'Maker', license: 'CC BY-SA' }

function readyViewport() {
  const image = screen.getByAltText('Board 원본 회로도')
  const viewport = screen.getByRole('region', { name: '회로도 이미지 이동' })
  Object.defineProperties(viewport, { clientWidth: { value: 400 }, clientHeight: { value: 300 } })
  Object.defineProperties(image, { naturalWidth: { value: 800 }, naturalHeight: { value: 600 } })
  viewport.setPointerCapture = vi.fn()
  viewport.hasPointerCapture = vi.fn(() => true)
  viewport.releasePointerCapture = vi.fn()
  fireEvent.load(image)
  return { image, viewport }
}

it('pans only the image and fits back to the centre even at the same zoom', () => {
  const view = render(<SchematicImage schematic={picture} name="Board" zoom={50} />)
  const { image, viewport } = readyViewport()
  fireEvent.pointerDown(viewport, { button: 0, isPrimary: true, pointerId: 1, clientX: 100, clientY: 100 })
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 140, clientY: 120 })
  expect(image.style.transform).toContain('translate(40px, 20px)')
  expect(image.style.transform).toContain('scale(0.5)')
  expect(viewport.style.transform).toBe('')
  expect(image).toHaveAttribute('draggable', 'false')
  view.rerender(<SchematicImage schematic={picture} name="Board" zoom={50} viewReset={1} />)
  expect(image.style.transform).toMatch(/translate\(0px(?:, 0px)?\)/)
})

it('bounds dragging and releases it on cancel without dragging links or accepting a second pointer', () => {
  renderWithQueries(<SchematicImage schematic={picture} name="Board" zoom={200} />)
  const { image, viewport } = readyViewport()
  fireEvent.pointerDown(viewport, { button: 2, pointerId: 1, clientX: 0, clientY: 0 })
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 50, clientY: 50 })
  expect(image.style.transform).toMatch(/translate\(0px(?:, 0px)?\)/)
  fireEvent.pointerDown(viewport, { button: 0, isPrimary: true, pointerId: 1, clientX: 0, clientY: 0 })
  fireEvent.pointerMove(viewport, { pointerId: 2, clientX: 80, clientY: 80 })
  expect(image.style.transform).toMatch(/translate\(0px(?:, 0px)?\)/)
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 1000, clientY: 1000 })
  expect(image.style.transform).toContain('translate(200px, 150px)')
  fireEvent.pointerCancel(viewport, { pointerId: 1 })
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 0, clientY: 0 })
  expect(image.style.transform).toContain('translate(200px, 150px)')
  expect(viewport.releasePointerCapture).toHaveBeenCalledWith(1)
  expect(viewport).not.toContainElement(screen.getByRole('link', { name: /원본 자료/ }))
})

it('supports keyboard panning and recentres on Home', () => {
  renderWithQueries(<SchematicImage schematic={picture} name="Board" zoom={200} />)
  const { image, viewport } = readyViewport()
  fireEvent.keyDown(viewport, { key: 'ArrowRight' })
  expect(image.style.transform).toMatch(/translate\(-40px(?:, 0px)?\)/)
  fireEvent.keyDown(viewport, { key: 'Home' })
  expect(image.style.transform).toMatch(/translate\(0px(?:, 0px)?\)/)
})

it.each(['조건에 맞는 원본 회로도 검색 결과가 없습니다.', '회로도 후보를 찾았지만 원본 검증을 통과하지 못했습니다.'])(
  'preserves the server failure explanation: %s', async message => {
    const handler = vi.fn(() => failure('SCHEMATIC_NOT_FOUND', message, 404))
    network(handler)
    renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
    search()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(handler).toHaveBeenCalledTimes(1)
  })

it.each(['success', 'error'])('does not repeat a stale %s search on focus, reconnect, or reopening', async state => {
  const handler = vi.fn(() => state === 'success' ? Response.json(found) : failure('SCHEMATIC_NOT_FOUND', '없음', 404))
  network(handler)
  const view = renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  expect(handler).not.toHaveBeenCalled()
  search()
  await waitFor(() => expect(view.client.getQueryState(['external-schematic', 'Board', ''])?.status).toBe(state))
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
  await waitFor(() => expect(view.client.getQueryState(['external-schematic', 'Board', ''])?.status).toBe('success'))
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

it('shows an unverified public schematic with its publishing page', async () => {
  network(() => Response.json({
    ...found, project: null, commit: null, source_type: 'public_web', evidence_grade: null,
    model: 'Tiny85 Fan Control', manufacturer: null, license: '미확인',
    repository_url: 'https://example.org/tiny85', source_url: 'https://example.org/tiny85-schematic.png',
    images: [{ sheet: 0, url: '/api/external-circuits/schematics/t/0' }],
  }))
  renderWithQueries(<ExternalSchematic name="Tiny85 Fan Control" zoom={100} />)
  search()
  expect(await screen.findByAltText('Tiny85 Fan Control 시트 1 원본 회로도')).toHaveAttribute('src', '/api/external-circuits/schematics/t/0')
  expect(screen.getByText('공개 웹 자료 · 출처 확인 필요')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /게시 페이지/ })).toHaveAttribute('href', 'https://example.org/tiny85')
})

it('keeps the chosen source without automatic searches and resets it on an explicit stale search', async () => {
  const other = 'https://example.org/board-v2-schematic.png'
  const paths: string[] = []
  network(path => {
    paths.push(path)
    return Response.json({ ...found, source_url: path.includes('source_url=') ? other : found.source_url,
      choices: [
        { title: 'Board v1', source_url: found.source_url, source_type: 'manufacturer_official', revision: 'v1' },
        { title: 'Board v2', source_url: other, source_type: 'public_web', revision: 'v2' },
      ] })
  })
  const view = renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  const choice = await screen.findByRole('button', { name: 'Board v2 · 출처 확인 필요' })
  fireEvent.click(choice)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Board v2 · 출처 확인 필요' })).toHaveAttribute('aria-pressed', 'true'))
  expect(paths).toEqual(['/api/external-circuits/schematics?q=Board', `/api/external-circuits/schematics?q=Board&source_url=${encodeURIComponent(other)}`])
  vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 16 * 60_000)
  await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  await act(async () => { onlineManager.setOnline(false); onlineManager.setOnline(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(paths).toHaveLength(2)
  expect(screen.getByRole('button', { name: 'Board v2 · 출처 확인 필요' })).toHaveAttribute('aria-pressed', 'true')
  search()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Board v1 · 제조사 공식' })).toHaveAttribute('aria-pressed', 'true'))
  expect(paths).toHaveLength(3)
  expect(paths[2]).toBe('/api/external-circuits/schematics?q=Board')
  view.client.clear()
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
