import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import CircuitSchematic from './CircuitSchematic'

const schematic = {
  image_url: '/circuit-schematics/pro_micro.png',
  original_url: 'https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro-Micro-v13.pdf',
  source_repo: 'https://github.com/sparkfun/Pro_Micro',
  source_commit: 'a'.repeat(40), license: 'CC BY-SA 4.0', license_evidence_url: 'https://github.com/sparkfun/Pro_Micro', attribution: 'SparkFun Electronics',
}

it('shows the supplied original with attribution and safe source links', () => {
  render(<CircuitSchematic circuitName="SparkFun Pro Micro v13" targetRef="D2" schematic={schematic} />)
  const image = screen.getByRole('img', { name: 'SparkFun Pro Micro v13 원본 회로도' })
  expect(image).toHaveAttribute('src', '/circuit-schematics/pro_micro.png')
  expect(image).toHaveAttribute('loading', 'lazy')
  expect(image).toHaveAttribute('decoding', 'async')
  expect(screen.getByText('선택 대상 D2')).toBeInTheDocument()
  expect(screen.getByText(/SparkFun Electronics.*CC BY-SA 4.0/)).toBeInTheDocument()
  for (const name of ['원본 자료 열기', '원본 저장소 열기']) {
    expect(screen.getByRole('link', { name })).toHaveAttribute('target', '_blank')
    expect(screen.getByRole('link', { name })).toHaveAttribute('rel', 'noreferrer noopener')
  }
  expect(screen.getByText('이 이미지는 공개 원본 회로도입니다. 선택 부품의 연결 해석은 연결 개념도에서 확인하세요.')).toBeInTheDocument()
})

it('zooms the original and pans it by dragging', () => {
  render(<CircuitSchematic circuitName="SparkFun Pro Micro v13" targetRef="D2" schematic={schematic} />)
  const viewport = screen.getByRole('region', { name: '원본 회로도 확대 및 이동' })
  const image = screen.getByRole('img', { name: 'SparkFun Pro Micro v13 원본 회로도' })
  expect(screen.getByText('100%')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '확대' }))
  expect(screen.getByText('125%')).toBeInTheDocument()
  expect(image).toHaveStyle({ width: '125%' })

  viewport.scrollLeft = 80
  viewport.scrollTop = 40
  fireEvent.pointerDown(viewport, { pointerId: 1, button: 0, clientX: 100, clientY: 100 })
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 70, clientY: 80 })
  fireEvent.pointerUp(viewport, { pointerId: 1 })
  expect(viewport.scrollLeft).toBe(110)
  expect(viewport.scrollTop).toBe(60)

  fireEvent.click(screen.getByRole('button', { name: '화면에 맞춤' }))
  expect(screen.getByText('100%')).toBeInTheDocument()
  expect(viewport.scrollLeft).toBe(0)
  expect(viewport.scrollTop).toBe(0)
})

it('does not replace missing originals with an invented image', () => {
  render(<CircuitSchematic circuitName="회로" targetRef="D1" />)
  expect(screen.getByText('검증된 원본 회로도를 제공할 수 없습니다.')).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('hides a broken image and clears the error when the target changes', () => {
  const { rerender } = render(<CircuitSchematic circuitName="회로" targetRef="D1" schematic={schematic} />)
  fireEvent.error(screen.getByRole('img'))
  expect(screen.getByText('검증된 원본 회로도를 제공할 수 없습니다.')).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  rerender(<CircuitSchematic circuitName="회로" targetRef="D2" schematic={schematic} />)
  expect(screen.getByRole('img')).toBeInTheDocument()
})

it('omits unsafe source URLs', () => {
  render(<CircuitSchematic circuitName="회로" targetRef="D1" schematic={{ ...schematic, original_url: 'javascript:alert(1)', source_repo: 'file:///tmp/source' }} />)
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
})
