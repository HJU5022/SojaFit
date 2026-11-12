import CircuitSummary from './CircuitSummary'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { network } from '../test/network'
import { demo, first, second, summary, openWorkbench, showDetail } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('selects a server reference in the URL and clears it on project switching', async () => {
  network((path) => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second))
  openWorkbench('/app?projectId=11')
  fireEvent.click(await screen.findByRole('button', { name: /^프로젝트 선택:/ }))
  const select = within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByLabelText('분석할 부품')
  expect(within(select).getByRole('option', { name: 'D1 · 1N4001' })).toBeInTheDocument()
  fireEvent.change(select, { target: { value: 'D1' } })
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
  showDetail('회로')
  expect(await screen.findByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
  expect(screen.queryByText('선택한 대상: D1')).not.toBeInTheDocument()
  expect(screen.queryByText('공개 데모 회로 · 서버에서 확인한 연결 정보')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^프로젝트 선택:/ }))
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  showDetail('회로')
  expect(screen.getByText('현재 프로젝트에서 검토할 부품을 선택하세요.')).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(screen.getByLabelText('현재 경로')).not.toHaveTextContent('targetRef')
  expect(screen.queryByRole('option', { name: 'D1 · 1N4001' })).not.toBeInTheDocument()
})
it('does not treat a URL reference absent from the server DTO as a target', async () => {
  network((path) => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first)] : first))
  openWorkbench('/app?projectId=11&targetRef=FOREIGN')
  showDetail('회로')
  expect(await screen.findByText('대상 부품을 찾을 수 없음')).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: 'FOREIGN 주변 연결 개념도' })).not.toBeInTheDocument()
  expect(screen.queryByText('선택한 대상: FOREIGN')).not.toBeInTheDocument()
})


const visualDemo = { ...demo, schematic: {
  image_url: '/circuit-schematics/mosfet_driver.png', original_url: 'https://cdn-learn.adafruit.com/assets/assets/000/117/028/large1024/adafruit_products_schem.png?1670851887',
  source_repo: 'https://github.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB', source_commit: 'a'.repeat(40),
  license: 'CC BY-SA 3.0', license_evidence_url: 'https://raw.githubusercontent.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB/main/license.txt', attribution: 'Adafruit Industries',
} }

it('defaults to the original and switches to the target-centered connection concept', () => {
  render(<CircuitSummary project={first} demo={visualDemo} targetRef="D1" />)
  expect(screen.getByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('img', { name: `${demo.name} 원본 회로도` })).toBeInTheDocument()
  expect(screen.queryByRole('img', { name: 'D1 주변 연결 개념도' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '연결 개념도' }))
  expect(screen.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
})

it('switches the circuit views with keyboard focus following the selected tab', () => {
  render(<CircuitSummary project={first} demo={visualDemo} targetRef="D1" />)
  const original = screen.getByRole('tab', { name: '원본 회로도' })
  const concept = screen.getByRole('tab', { name: '연결 개념도' })
  expect(concept).toHaveAttribute('tabIndex', '-1')
  original.focus()
  fireEvent.keyDown(original, { key: 'ArrowRight' })
  expect(concept).toHaveFocus()
  expect(concept).toHaveAttribute('aria-selected', 'true')
  fireEvent.keyDown(concept, { key: 'Home' })
  expect(original).toHaveFocus()
  expect(original).toHaveAttribute('aria-selected', 'true')
})

it('resets the view and image errors on project changes and never invents upload originals', () => {
  const { rerender } = render(<CircuitSummary project={first} demo={visualDemo} targetRef="D1" />)
  fireEvent.error(screen.getByRole('img'))
  expect(screen.getByText('검증된 원본 회로도를 제공할 수 없습니다.')).toBeInTheDocument()
  rerender(<CircuitSummary project={second} demo={visualDemo} targetRef="D2" />)
  expect(screen.queryByRole('tab', { name: '원본 회로도' })).not.toBeInTheDocument()
  expect(screen.queryByText('업로드한 넷리스트에는 원본 회로도 이미지와 부품 좌표가 포함되지 않습니다.')).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'D2 주변 연결 개념도' })).toBeInTheDocument()
  rerender(<CircuitSummary project={first} demo={visualDemo} targetRef="D1" />)
  expect(screen.getByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('img', { name: `${demo.name} 원본 회로도` })).toBeInTheDocument()
})

it('uses the concept only when a demo has no verified visual metadata', () => {
  render(<CircuitSummary project={first} demo={{ ...demo, schematic: null }} targetRef="D1" />)
  expect(screen.queryByRole('tab', { name: '원본 회로도' })).not.toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
})

it('keeps the chosen target while switching views without a duplicate selector', () => {
  render(<CircuitSummary project={first} demo={visualDemo} targetRef="D1" />)
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.click(screen.getByRole('tab', { name: '연결 개념도' }))
  expect(screen.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
})
