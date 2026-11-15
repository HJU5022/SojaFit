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

it('passes the reset signal through external multi-sheet previews', async () => {
  network(() => Response.json(found)); const view = renderWithQueries(<ExternalSchematic name="Board" zoom={200} viewReset={0} />); search()
  const image = await screen.findByAltText('Board 시트 1 원본 회로도'); const viewport = screen.getAllByRole('region', { name: '회로도 이미지 이동' })[0]
  Object.defineProperties(viewport, { clientWidth: { value: 400 }, clientHeight: { value: 300 } }); Object.defineProperties(image, { naturalWidth: { value: 800 }, naturalHeight: { value: 600 } }); viewport.setPointerCapture = vi.fn(); viewport.hasPointerCapture = vi.fn(() => true); viewport.releasePointerCapture = vi.fn(); fireEvent.load(image)
  fireEvent.pointerDown(viewport, { button: 0, isPrimary: true, pointerId: 1, clientX: 100, clientY: 100 }); fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 140, clientY: 120 }); expect(image.style.transform).toContain('translate(40px, 20px)')
  view.rerender(<QueryClientProvider client={view.client}><ExternalSchematic name="Board" zoom={200} viewReset={1} /></QueryClientProvider>); expect(image.style.transform).toMatch(/translate\(0px(?:, 0px)?\)/)
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
  expect(screen.getAllByText('제조사 공식 여부: 확인됨 · 2등급')).toHaveLength(2)
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
  ['diode', 194, true],
  ['diode', 195, false],
  ['', 200, true],
  ['', 201, false],
] as const)('applies the %s query length boundary at %i characters', (componentType, length, valid) => {
  const handler = vi.fn(() => Response.json(found))
  network(handler)
  renderWithQueries(<ExternalSchematic name={'x'.repeat(length)} zoom={100} defaultComponentType={componentType} />)
  const input = screen.getByRole('textbox')
  expect(input).toHaveAttribute('maxLength', String(componentType === 'diode' ? 194 : 200))
  expect(screen.getByText(`2자 이상 ${componentType === 'diode' ? 194 : 200}자 이하로 입력해 주세요.`)).toBeInTheDocument()
  const button = screen.getByRole('button', { name: '원본 회로도 찾기' })
  if (valid) expect(button).toBeEnabled()
  else expect(button).toBeDisabled()
})

it('preserves a 200-character product query when switching to diode and disables search without truncating it', () => {
  const handler = vi.fn(() => Response.json(found))
  network(handler)
  renderWithQueries(<ExternalSchematic name={'x'.repeat(200)} zoom={100} />)
  const input = screen.getByRole('textbox')
  fireEvent.change(screen.getByRole('combobox', { name: '검색 대상' }), { target: { value: 'diode' } })
  expect(input).toHaveValue('x'.repeat(200))
  expect(input).toHaveAttribute('maxLength', '194')
  expect(screen.getByRole('button', { name: '원본 회로도 찾기' })).toBeDisabled()
  fireEvent.change(screen.getByRole('combobox', { name: '검색 대상' }), { target: { value: '' } })
  expect(input).toHaveValue('x'.repeat(200))
  expect(screen.getByRole('button', { name: '원본 회로도 찾기' })).toBeEnabled()
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
  expect(screen.getByText('공개 웹 자료')).toBeInTheDocument()
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
  const choice = await screen.findByRole('button', { name: '이 자료 보기: Board v2 · 제조사 공식 여부 미확인' })
  fireEvent.click(choice)
  await waitFor(() => expect(screen.getByRole('button', { name: '현재 보는 자료: Board v2 · 제조사 공식 여부 미확인' })).toHaveAttribute('aria-pressed', 'true'))
  expect(paths).toEqual(['/api/external-circuits/schematics?q=Board', `/api/external-circuits/schematics?q=Board&source_url=${encodeURIComponent(other)}`])
  vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 16 * 60_000)
  await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  await act(async () => { onlineManager.setOnline(false); onlineManager.setOnline(true); await new Promise(resolve => setTimeout(resolve, 0)) })
  expect(paths).toHaveLength(2)
  expect(screen.getByRole('button', { name: '현재 보는 자료: Board v2 · 제조사 공식 여부 미확인' })).toHaveAttribute('aria-pressed', 'true')
  search()
  await waitFor(() => expect(screen.getByRole('button', { name: '현재 보는 자료: Board v1 · 제조사 공식' })).toHaveAttribute('aria-pressed', 'true'))
  expect(paths).toHaveLength(3)
  expect(paths[2]).toBe('/api/external-circuits/schematics?q=Board')
  view.client.clear()
})

it('lets the user choose another matching circuit source', async () => {
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
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  const choice = await screen.findByRole('button', { name: '이 자료 보기: Board v2 · 제조사 공식 여부 미확인' })
  expect(screen.getByRole('button', { name: /현재 보는 자료: Board v1/ })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(choice)
  await waitFor(() => expect(paths).toContain(`/api/external-circuits/schematics?q=Board&source_url=${encodeURIComponent(other)}`))
  expect(await screen.findByRole('button', { name: /현재 보는 자료: Board v2/ })).toHaveAttribute('aria-pressed', 'true')
})

it('labels community candidates and loads a different root from the same repository', async () => {
  const community = 'https://example.org/r/blob/abc/other.kicad_sch'
  const paths: string[] = []
  network(path => {
    paths.push(path)
    const selected = path.includes('source_url=')
    return Response.json({ ...found, source_type: selected ? 'community' : 'manufacturer_official', evidence_grade: selected ? 3 : 2,
      source_url: selected ? community : found.source_url,
      images: [{ sheet: 0, url: selected ? '/api/external-circuits/schematics/community/0' : found.images[0].url }],
      choices: [
        { title: 'Board v1', source_url: found.source_url, source_type: 'manufacturer_official', revision: 'v1' },
        { title: 'Board · other.kicad_sch', source_url: community, source_type: 'community', revision: null },
      ] })
  })
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  const choice = await screen.findByRole('button', { name: '이 자료 보기: Board · other.kicad_sch · 커뮤니티 참고 자료' })
  fireEvent.click(choice)
  await waitFor(() => expect(paths).toContain(`/api/external-circuits/schematics?q=Board&source_url=${encodeURIComponent(community)}`))
  expect(await screen.findByRole('button', { name: /현재 보는 자료: Board · other.kicad_sch/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('커뮤니티 참고 자료 · 3등급')).toBeInTheDocument()
  expect(screen.getByAltText('Board 시트 1 원본 회로도')).toHaveAttribute('src', '/api/external-circuits/schematics/community/0')
})

it('does not keep the previous current label while a selected source fails', async () => {
  const community = 'https://example.org/r/blob/abc/other.kicad_sch'
  network(path => path.includes('source_url=')
    ? failure('SCHEMATIC_NOT_FOUND', '없음', 404)
    : Response.json({ ...found, choices: [
      { title: 'Board v1', source_url: found.source_url, source_type: 'manufacturer_official', revision: 'v1' },
      { title: 'Board · other.kicad_sch', source_url: community, source_type: 'community', revision: null },
    ] }))
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  fireEvent.click(await screen.findByRole('button', { name: /이 자료 보기: Board · other.kicad_sch/ }))
  await screen.findByRole('alert')
  expect(screen.queryByRole('button', { name: /현재 보는 자료:/ })).toBeNull()
  expect(screen.queryByAltText(/원본 회로도/)).toBeNull()
})

it('does not search while editing after choosing a source', async () => {
  const community = 'https://example.org/r/blob/abc/other.kicad_sch'
  const paths: string[] = []
  network(path => {
    paths.push(path)
    return Response.json({ ...found, choices: [
      { title: 'Board v1', source_url: found.source_url, source_type: 'manufacturer_official', revision: 'v1' },
      { title: 'Board · other.kicad_sch', source_url: community, source_type: 'community', revision: null },
    ] })
  })
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  fireEvent.click(await screen.findByRole('button', { name: /이 자료 보기: Board · other.kicad_sch/ }))
  await waitFor(() => expect(paths).toHaveLength(2))
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New Board' } })
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(paths).toHaveLength(2)
  search()
  await waitFor(() => expect(paths).toHaveLength(3))
  expect(paths[2]).toBe('/api/external-circuits/schematics?q=New%20Board')
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

it('shows source links before the image and distinguishes official status from license uncertainty', async () => {
  network(() => Response.json({ ...found, source_type: 'public_web', evidence_grade: null, license: '미확인', images: [found.images[0]] }))
  renderWithQueries(<ExternalSchematic name="Board" zoom={100} />)
  search()
  const image = await screen.findByAltText('Board 시트 1 원본 회로도')
  const link = screen.getByRole('link', { name: /원본 자료 열기/ })
  expect(link).toHaveAttribute('href', found.source_url)
  expect(link.compareDocumentPosition(image) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getByText('제조사 공식 여부: 미확인')).toBeInTheDocument()
  expect(screen.getByText('라이선스: 이용·재배포 조건 미확인')).toBeInTheDocument()
  expect(screen.queryByText(/출처 확인 필요/)).toBeNull()
})

it('sends diode context and clears the previous source selection when changing search purpose', async () => {
  const paths: string[] = []
  network(path => { paths.push(path); return Response.json(found) })
  renderWithQueries(<ExternalSchematic name="SS33" zoom={100} defaultComponentType="diode" />)
  search()
  await waitFor(() => expect(paths).toEqual(['/api/external-circuits/schematics?q=SS33&component_type=diode']))
  fireEvent.change(screen.getByRole('combobox', { name: '검색 대상' }), { target: { value: '' } })
  expect(screen.queryByAltText('Board 시트 1 원본 회로도')).toBeNull()
  search()
  await waitFor(() => expect(paths).toContain('/api/external-circuits/schematics?q=SS33'))
})

it('explains missing diode evidence instead of showing an unrelated circuit', async () => {
  network(() => failure('SCHEMATIC_NOT_FOUND', '없음', 404))
  renderWithQueries(<ExternalSchematic name="SS33" zoom={100} defaultComponentType="diode" />)
  search()
  expect(await screen.findByRole('alert')).toHaveTextContent('다이오드 품번과 관련된 회로 자료를 확인하지 못했습니다')
  expect(screen.queryByRole('img')).toBeNull()
})
