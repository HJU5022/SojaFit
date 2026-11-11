import { describe, expect, it } from 'vitest'
import type { CircuitContext, ContextNet } from './circuitContext'
import { buildLayoutGraph } from './circuitLayout'

const target = { ref: 'C1', value: '100uF', footprint: 'CPOL-RADIAL' }

function contextWith(nets: ContextNet[]): CircuitContext {
  const refs = [...new Set(nets.flatMap(net => net.nodeRefs))].filter(ref => ref !== target.ref)
  return {
    circuitName: 'power_supply',
    state: 'ready',
    target,
    nodes: refs.map((ref, index) => ({ ref, value: `VALUE-${ref}`, footprint: `PKG-${ref}`, depth: index < 8 ? 1 : 2 })),
    nets,
    role: null,
    conditions: [],
    missing: [],
    candidates: [],
  }
}

describe('buildLayoutGraph', () => {
  it('represents a net as a junction between the target and connected components', () => {
    const context = contextWith([{
      name: 'VOUT',
      nodes: ['C1.1(100uF)', 'U1.OUT(LM7805)', 'R1.1(1k)'],
      nodeRefs: ['C1', 'U1', 'R1'],
      more: 0,
      depth: 1,
    }])

    const graph = buildLayoutGraph(context, 0)

    expect(graph.nodes.map(node => [node.id, node.kind])).toEqual([
      ['component:C1', 'target'],
      ['net:VOUT', 'net'],
      ['component:R1', 'component'],
      ['component:U1', 'component'],
    ])
    expect(graph.edges.map(edge => [edge.source, edge.target])).toEqual([
      ['component:C1', 'net:VOUT'],
      ['net:VOUT', 'component:R1'],
      ['net:VOUT', 'component:U1'],
    ])
  })

  it('paginates six nets and limits each net to five neighbors with an overflow node', () => {
    const manyNeighbors = Array.from({ length: 7 }, (_, index) => `P${index + 1}`)
    const nets: ContextNet[] = Array.from({ length: 7 }, (_, index) => ({
      name: `NET-${index + 1}`,
      nodes: index === 0 ? ['C1.1(100uF)', ...manyNeighbors.map(ref => `${ref}.1(X)`)] : ['C1.1(100uF)', `X${index}.1(X)`],
      nodeRefs: index === 0 ? ['C1', ...manyNeighbors] : ['C1', `X${index}`],
      more: 0,
      depth: 1,
    }))

    const first = buildLayoutGraph(contextWith(nets), 0)
    const second = buildLayoutGraph(contextWith(nets), 1)

    expect(first.pageCount).toBe(2)
    expect(first.visibleNetNames).toEqual(['NET-1', 'NET-2', 'NET-3', 'NET-4', 'NET-5', 'NET-6'])
    expect(first.nodes.filter(node => node.kind === 'overflow')).toEqual([
      expect.objectContaining({ id: 'overflow:NET-1', label: '+2' }),
    ])
    expect(second.visibleNetNames).toEqual(['NET-7'])
  })

  it('keeps output stable when input nets and references arrive in a different order', () => {
    const a: ContextNet = { name: 'A', nodes: ['C1.1(100uF)', 'U1.1(X)', 'R1.1(X)'], nodeRefs: ['C1', 'U1', 'R1'], more: 0, depth: 1 }
    const b: ContextNet = { name: 'B', nodes: ['C1.2(100uF)', 'D1.1(X)'], nodeRefs: ['C1', 'D1'], more: 0, depth: 1 }
    const first = buildLayoutGraph(contextWith([b, a]), 0)
    const second = buildLayoutGraph(contextWith([{ ...a, nodeRefs: [...a.nodeRefs].reverse() }, b]), 0)

    expect(first).toEqual(second)
  })
})
