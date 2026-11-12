import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { CircuitContext } from './circuitContext'
import CircuitContextDiagram from './CircuitContextDiagram'

const context: CircuitContext = {
  circuitName: 'breadboard_supply', state: 'ready',
  target: { ref: 'D1', value: '1N4001', footprint: 'import_input:DIODE-0.4' },
  nodes: [
    { ref: 'F1', value: '500mA', footprint: 'import_input:PTC', depth: 1 },
    { ref: 'S1', value: 'On/Off', footprint: 'import_input:SWITCH-SPST', depth: 1 },
    { ref: 'J1', value: 'POWER_JACKPTH', footprint: 'import_input:POWER_JACK_PTH', depth: 2 },
    { ref: 'U1', value: 'LM317', footprint: 'import_input:TO220-ADJ', depth: 2 },
  ],
  nets: [
    { name: 'Net-(F1-1)', nodes: ['D1.C(1N4001)', 'F1.1(500mA)'], nodeRefs: ['D1', 'F1'], more: 0, depth: 1 },
    { name: 'Net-(S1-S)', nodes: ['D1.A(1N4001)', 'S1.S(On/Off)'], nodeRefs: ['D1', 'S1'], more: 0, depth: 1 },
    { name: 'RAW', nodes: ['F1.2(500mA)', 'U1.IN(LM317)'], nodeRefs: ['F1', 'U1'], more: 0, depth: 2 },
    { name: 'Net-(S1-P)', nodes: ['J1.PWR(POWER_JACKPTH)', 'S1.P(On/Off)'], nodeRefs: ['J1', 'S1'], more: 0, depth: 2 },
  ],
  role: { code: 'R01', name: '역극성 보호(직렬)', evidence: ['D1.K → RAW'] },
  conditions: [], missing: ['v_in_max'], candidates: [],
}

describe('CircuitContextDiagram', () => {
  it('attaches after the diagram becomes ready and cleans wheel and pointer capture on unmount', () => {
    const { rerender, unmount } = render(<CircuitContextDiagram context={{ ...context, state: 'no_connections' }} />)
    rerender(<CircuitContextDiagram context={context} />)
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    expect(fireEvent.wheel(viewport, { deltaY: -100 })).toBe(false)
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('125%')
    const node = screen.getByRole('button', { name: 'U1 노드' })
    node.setPointerCapture = vi.fn()
    node.hasPointerCapture = () => true
    node.releasePointerCapture = vi.fn()
    fireEvent.pointerDown(node, { pointerId: 7, button: 0 })
    expect(node.setPointerCapture).toHaveBeenCalledWith(7)
    unmount()
    expect(node.releasePointerCapture).toHaveBeenCalledWith(7)
    expect(fireEvent.wheel(viewport, { deltaY: -100 })).toBe(true)
  })
  it('anchors wheel zoom at the pointer and preserves browser zoom shortcuts', () => {
    render(<CircuitContextDiagram context={context} />)
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    const diagram = screen.getByRole('img', { name: 'D1 주변 연결 개념도' })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue({ left: 10, top: 20 } as DOMRect)
    vi.spyOn(diagram, 'getBoundingClientRect').mockImplementation(() => ({ width: 400 * parseFloat(diagram.style.width) / 100, height: 300 * parseFloat(diagram.style.height) / 100 }) as DOMRect)
    viewport.scrollLeft = 80; viewport.scrollTop = 40
    fireEvent.wheel(viewport, { deltaY: -100, clientX: 110, clientY: 80 })
    expect(viewport.scrollLeft).toBe(125)
    expect(viewport.scrollTop).toBe(65)
    expect(fireEvent.wheel(viewport, { deltaY: 0 })).toBe(true)
    expect(fireEvent.wheel(viewport, { deltaY: -100, ctrlKey: true })).toBe(true)
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('125%')
    fireEvent.keyDown(viewport, { key: '-' })
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('100%')
    fireEvent.keyDown(viewport, { key: '+' })
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('125%')
  })
  it('pans from a node without activating it and stops on pointer cancellation', () => {
    render(<CircuitContextDiagram context={context} />)
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    const node = screen.getByRole('button', { name: 'U1 노드' })
    viewport.scrollLeft = 80; viewport.scrollTop = 60
    fireEvent.pointerDown(node, { pointerId: 1, button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(node, { pointerId: 1, clientX: 70, clientY: 80 })
    expect(viewport.scrollLeft).toBe(110)
    expect(viewport.scrollTop).toBe(80)
    expect(viewport).toHaveClass('dragging')
    fireEvent.pointerUp(node, { pointerId: 1 })
    fireEvent.click(node, { detail: 1 })
    expect(screen.getByText('선택 노드 D1')).toBeInTheDocument()
    expect(viewport).not.toHaveClass('dragging')
    fireEvent.pointerDown(node, { pointerId: 2, button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerUp(node, { pointerId: 2 })
    fireEvent.click(node, { detail: 1 })
    expect(screen.getByText('선택 노드 U1')).toBeInTheDocument()
    fireEvent.pointerDown(viewport, { pointerId: 3, button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerCancel(viewport, { pointerId: 3 })
    fireEvent.pointerMove(viewport, { pointerId: 3, clientX: 0, clientY: 0 })
    expect(viewport.scrollLeft).toBe(110)
    expect(viewport.scrollTop).toBe(80)
  })
  it('resets zoom and scroll when opening another net page', () => {
    render(<CircuitContextDiagram context={{ ...context, nets: Array.from({ length: 7 }, (_, i) => ({ ...context.nets[0], name: `NET-${i}` })) }} />)
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    fireEvent.wheel(viewport, { deltaY: -100 })
    viewport.scrollLeft = 80; viewport.scrollTop = 40
    fireEvent.click(screen.getByRole('button', { name: '다음' }))
    expect(screen.getByText('2 / 2')).toBeInTheDocument()
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('100%')
    expect(viewport.scrollLeft).toBe(0)
    expect(viewport.scrollTop).toBe(0)
  })
  it('zooms within bounds, retains node selection and resets scale and scroll on fit', () => {
    render(<CircuitContextDiagram context={context} />)
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    const diagram = screen.getByRole('img', { name: 'D1 주변 연결 개념도' })
    const zoom = screen.getByLabelText('연결 개념도 배율')
    expect(screen.queryByRole('button', { name: '연결 개념도 확대' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '연결 개념도 축소' })).not.toBeInTheDocument()
    expect(fireEvent.wheel(viewport, { deltaY: -100 })).toBe(false)
    expect(zoom).toHaveTextContent('125%')
    expect(diagram).toHaveStyle({ width: '125%', height: '125%' })
    fireEvent.click(screen.getByRole('button', { name: 'U1 노드' }))
    for (let i = 0; i < 20; i++) fireEvent.wheel(viewport, { deltaY: -100 })
    expect(zoom).toHaveTextContent('300%')
    expect(screen.getByText('선택 노드 U1')).toBeInTheDocument()
    for (let i = 0; i < 20; i++) fireEvent.wheel(viewport, { deltaY: 100 })
    expect(zoom).toHaveTextContent('50%')
    viewport.scrollLeft = 80; viewport.scrollTop = 40
    fireEvent.click(screen.getByRole('button', { name: '연결 개념도 화면에 맞춤' }))
    expect(zoom).toHaveTextContent('100%')
    expect(viewport.scrollLeft).toBe(0)
    expect(viewport.scrollTop).toBe(0)
    expect(screen.getByText('선택 노드 U1')).toBeInTheDocument()
  })

  it.each(['target', 'circuit'] as const)('retains zoom on condition updates and resets on %s changes', change => {
    const { rerender } = render(<CircuitContextDiagram context={context} />)
    fireEvent.wheel(screen.getByRole('region', { name: '연결 개념도 확대 및 이동' }), { deltaY: -100 })
    rerender(<CircuitContextDiagram context={{ ...context, conditions: [{ code: 'v_in_max', label: '입력 전압', value: '12 V' }] }} analysisStatus="completed" />)
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('125%')
    const viewport = screen.getByRole('region', { name: '연결 개념도 확대 및 이동' })
    viewport.scrollLeft = 80; viewport.scrollTop = 40
    rerender(<CircuitContextDiagram context={change === 'target' ? { ...context, target: { ...context.target, ref: 'D2' } } : { ...context, circuitName: 'other' }} />)
    expect(screen.getByLabelText('연결 개념도 배율')).toHaveTextContent('100%')
    expect(viewport.scrollLeft).toBe(0)
    expect(viewport.scrollTop).toBe(0)
  })
  it('shows accepted voltage/current and temperature instead of asking for missing information', () => {
    render(<CircuitContextDiagram context={{ ...context, missing: [], conditions: [
      { code: 'v_in_max', label: '입력 전원 최대 전압', value: '20 V' },
      { code: 'i_max', label: '다이오드 최대 순방향(부하) 전류', value: '0.15 A' },
      { code: 'temp', label: '사용 온도', value: 'TA=25 °C' }] }} analysisStatus="completed" />)
    expect(screen.getByText('판정에 사용한 조건')).toBeInTheDocument()
    expect(screen.getByText('20 V')).toBeInTheDocument()
    expect(screen.getByText('0.15 A')).toBeInTheDocument()
    expect(screen.getByText('TA=25 °C')).toBeInTheDocument()
    expect(screen.queryByText('판정 결과에서 확인된 사용 조건이 없습니다.')).not.toBeInTheDocument()
  })
  it('renders the central target, direct and two-hop nodes without direction markers', () => {
    const { container } = render(<CircuitContextDiagram context={context} analysisStatus="completed" />)
    expect(screen.getByText('D1 / 1N4001')).toBeInTheDocument()
    for (const ref of ['J1', 'S1', 'F1', 'U1']) expect(screen.getByText(ref)).toBeInTheDocument()
    expect(screen.getByText('역극성 보호(직렬)')).toBeInTheDocument()
    expect(screen.getByText('D1.K → RAW')).toBeInTheDocument()
    expect(screen.getByText('실제 회로도가 아닌 대상 부품 주변 연결 개념도입니다.')).toBeInTheDocument()
    expect(container.querySelector('.context-diagram')).toBeInTheDocument()
    expect(container.querySelector('marker')).not.toBeInTheDocument()
    expect(container.querySelector('[marker-end]')).not.toBeInTheDocument()
  })

  it('shows known metadata when a node is selected and never guesses absent conditions', () => {
    render(<CircuitContextDiagram context={context} analysisStatus="requires_input" />)
    fireEvent.click(screen.getByRole('button', { name: 'U1 노드' }))
    expect(screen.getByText('선택 노드 U1')).toBeInTheDocument()
    expect(screen.getByText('LM317', { selector: 'dd' })).toBeInTheDocument()
    expect(screen.getByText('import_input:TO220-ADJ')).toBeInTheDocument()
    expect(screen.getByText('판정 결과에서 확인된 사용 조건이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('사용 조건 부족')).toBeInTheDocument()
  })

  it.each([
    ['no_connections', '연결 정보 없음'],
    ['target_not_found', '대상 부품을 찾을 수 없음'],
  ] as const)('renders %s state', (state, label) => {
    render(<CircuitContextDiagram context={{ ...context, state }} analysisStatus="idle" />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it.each([
    ['idle', '역할 분석 전'],
    ['running', 'loading'],
    ['completed', '판정 완료'],
    ['failed', '분석 오류'],
  ] as const)('renders %s analysis state', (analysisStatus, label) => {
    render(<CircuitContextDiagram context={{ ...context, missing: [], role: null }} analysisStatus={analysisStatus} />)
    expect(screen.getByRole('status')).toHaveTextContent(label)
  })
})
