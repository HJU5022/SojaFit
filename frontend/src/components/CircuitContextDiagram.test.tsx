import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
    expect(screen.getByText('LM317')).toBeInTheDocument()
    expect(screen.getByText('import_input:TO220-ADJ')).toBeInTheDocument()
    expect(screen.getByText('전압·전류 정보 필요')).toBeInTheDocument()
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
