/// <reference lib="webworker" />

import ELK from 'elkjs/lib/elk.bundled.js'
import type { ElkExtendedEdge, ElkNode } from 'elkjs/lib/elk-api.js'
import type { LayoutGraph, LayoutResult } from '../components/circuitLayout'

const elk = new ELK()

type LayoutRequest = { requestId: number; graph: LayoutGraph }
type LayoutResponse = { requestId: number; result?: LayoutResult; error?: string }

function toResult(graph: LayoutGraph, layout: ElkNode): LayoutResult {
  const nodeMap = new Map(graph.nodes.map(node => [node.id, node]))
  const edgeMap = new Map(graph.edges.map(edge => [edge.id, edge]))
  const nodes = (layout.children ?? []).flatMap(node => {
    const source = nodeMap.get(node.id)
    if (!source || node.x == null || node.y == null) return []
    return [{ ...source, x: node.x, y: node.y }]
  })
  const edges = ((layout.edges ?? []) as ElkExtendedEdge[]).flatMap(edge => {
    const source = edgeMap.get(edge.id)
    const section = edge.sections?.[0]
    if (!source || !section) return []
    return [{ ...source, points: [section.startPoint, ...(section.bendPoints ?? []), section.endPoint] }]
  })
  return {
    width: Math.max(1, layout.width ?? 1),
    height: Math.max(1, layout.height ?? 1),
    nodes,
    edges,
  }
}
self.onmessage = async (event: MessageEvent<LayoutRequest>) => {
  const { requestId, graph } = event.data
  try {
    const layout = await elk.layout({
      id: 'circuit-context',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.spacing.nodeNode': '38',
        'elk.layered.spacing.nodeNodeBetweenLayers': '72',
        'elk.padding': '[top=28,left=28,bottom=28,right=28]',
        'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
      },
      children: graph.nodes.map(node => ({ id: node.id, width: node.width, height: node.height })),
      edges: graph.edges.map(edge => ({ id: edge.id, sources: [edge.source], targets: [edge.target] })),
    })
    const result = toResult(graph, layout)
    self.postMessage({ requestId, result } satisfies LayoutResponse)
  } catch (error) {
    self.postMessage({ requestId, error: error instanceof Error ? error.message : String(error) } satisfies LayoutResponse)
  }
}
