import { afterEach, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { failure, network } from '../test/network'
import { renderWithQueries } from '../test/projects'
import { ExternalSchematic } from './Schematic'

afterEach(() => vi.unstubAllGlobals())
const found = { project: 'Board', commit: 'a'.repeat(40), license: 'MIT', attribution: 'Maker', repository_url: 'https://example.test/r', source_url: 'https://example.test/r/board.kicad_sch', source_file: 'board.kicad_sch',
  images: [{ sheet: 0, url: '/api/external-circuits/schematics/t/0' }, { sheet: 1, url: '/api/external-circuits/schematics/t/1' }] }
const search = () => fireEvent.click(screen.getByRole('button', { name: '원본 회로도 찾기' }))

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
