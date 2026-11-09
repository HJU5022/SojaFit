import { describe, expect, it } from 'vitest'
import type { JudgementDto, RoleLabel } from '../api/conversations'
import type { Project } from '../api/projects'
import { buildCircuitContext } from './circuitContext'

const project: Project = {
  id: 1, name: 'breadboard_supply', source_kind: 'demo', demo_id: 'breadboard_supply',
  created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: {
    components: [
      { ref: 'D1', value: '1N4001', footprint: 'import_input:DIODE-0.4' },
      { ref: 'F1', value: '500mA', footprint: 'import_input:PTC' },
      { ref: 'S1', value: 'On/Off', footprint: 'import_input:SWITCH-SPST' },
      { ref: 'J1', value: 'POWER_JACKPTH', footprint: 'import_input:POWER_JACK_PTH' },
      { ref: 'U1', value: 'LM317', footprint: 'import_input:TO220-ADJ' },
      { ref: 'C1', value: '100uF', footprint: '' },
    ],
    nets: [
      { name: 'Net-(F1-1)', nodes: [{ ref: 'D1', pin: 'C', pinfunction: 'C' }, { ref: 'F1', pin: 'P$1', pinfunction: '1' }] },
      { name: 'Net-(S1-S)', nodes: [{ ref: 'D1', pin: 'A', pinfunction: 'A' }, { ref: 'S1', pin: '3', pinfunction: 'S' }] },
      { name: 'Net-(S1-P)', nodes: [{ ref: 'J1', pin: 'PWR', pinfunction: 'PWR' }, { ref: 'S1', pin: '2', pinfunction: 'P' }] },
      { name: 'RAW', nodes: [{ ref: 'C1', pin: '1', pinfunction: '+' }, { ref: 'F1', pin: 'P$2', pinfunction: '2' }, { ref: 'U1', pin: 'IN', pinfunction: 'IN' }] },
    ],
  },
}

const judgement: JudgementDto = {
  kind: 'judge', roles: ['R01'], role_evidence: ['D1.K → RAW'], shown: [], unverified: [], capped: false,
  results: [{
    part: 'SS14', role: 'R01', verdict: 'ROLE_SUFFICIENT', missing: ['i_max'],
    checks: [{ code: 'VRRM', value: 40, unit: 'V', condition: '입력 최대 전압', result: 'pass' }],
  }],
}
const roles: RoleLabel[] = [{ code: 'R01', name: '역극성 보호(직렬)' }]

describe('buildCircuitContext', () => {
  it('keeps the target central and classifies direct and two-hop neighbors', () => {
    const context = buildCircuitContext(project, 'D1')
    expect(context.state).toBe('ready')
    expect(context.circuitName).toBe('breadboard_supply')
    expect(context.target).toMatchObject({ ref: 'D1', value: '1N4001' })
    expect(context.nodes.filter(node => node.depth === 1).map(node => node.ref)).toEqual(['F1', 'S1'])
    expect(context.nodes.filter(node => node.depth === 2).map(node => node.ref)).toEqual(expect.arrayContaining(['J1', 'U1']))
    expect(context.nets.map(net => net.name)).toEqual(['Net-(F1-1)', 'Net-(S1-S)', 'RAW', 'Net-(S1-P)'])
    expect(context.nets.every(net => net.direction === undefined)).toBe(true)
  })

  it('uses analysed role evidence and exact user conditions without presenting candidate ratings as circuit values', () => {
    const context = buildCircuitContext(project, 'D1', judgement, roles, ['v_in_max'], '입력 최대 12 V, 부하 250 mA')
    expect(context.role).toEqual({ code: 'R01', name: '역극성 보호(직렬)', evidence: ['D1.K → RAW'] })
    expect(context.conditions).toEqual([{ code: 'USER', label: '사용자 입력', value: '입력 최대 12 V, 부하 250 mA' }])
    expect(context.missing).toEqual(['v_in_max', 'i_max'])
    expect(context.candidates).toHaveLength(1)
    expect(buildCircuitContext(project, 'D1', judgement, roles).conditions).toEqual([])
  })

  it('distinguishes empty connections, missing targets, and absent metadata', () => {
    const empty = buildCircuitContext({ ...project, connections: { components: project.connections.components, nets: [] } }, 'D1')
    expect(empty.state).toBe('no_connections')

    const missing = buildCircuitContext(project, 'D404')
    expect(missing.state).toBe('target_not_found')

    const noMetadata = buildCircuitContext({
      ...project,
      connections: { components: [{ ref: 'D1', value: '', footprint: '' }], nets: [{ name: 'N', nodes: [{ ref: 'D1', pin: '1' }] }] },
    }, 'D1')
    expect(noMetadata.target).toEqual({ ref: 'D1', value: '', footprint: '' })
    expect(noMetadata.conditions).toEqual([])
  })
})
