import type { CircuitContext, ContextNet, ContextNode } from './circuitContext'

export const NETS_PER_PAGE = 6
export const NEIGHBORS_PER_NET = 5

export type LayoutNodeKind = 'target' | 'component' | 'net' | 'overflow'
export type LayoutNode = {
  id: string
  kind: LayoutNodeKind
  label: string
  value?: string
  depth: 0 | 1 | 2
  width: number
  height: number
}
export type LayoutEdge = { id: string; source: string; target: string; depth: 1 | 2 }
export type LayoutGraph = {
  page: number
  pageCount: number
  visibleNetNames: string[]
  nodes: LayoutNode[]
  edges: LayoutEdge[]
}
export type LayoutPoint = { x: number; y: number }
export type LayoutedNode = LayoutNode & { x: number; y: number }
export type LayoutedEdge = LayoutEdge & { points: LayoutPoint[] }
export type LayoutResult = { width: number; height: number; nodes: LayoutedNode[]; edges: LayoutedEdge[] }

function componentNode(node: CircuitContext['target'] | ContextNode, targetRef: string): LayoutNode {
  const isTarget = node.ref === targetRef
  const label = isTarget ? `${node.ref} / ${node.value || '정보 필요'}` : node.ref
  return {
    id: `component:${node.ref}`,
    kind: isTarget ? 'target' : 'component',
    label,
    value: isTarget ? undefined : node.value,
    depth: isTarget ? 0 : ('depth' in node ? node.depth : 1),
    width: Math.max(isTarget ? 132 : 92, label.length * 9 + 30),
    height: isTarget ? 66 : 54,
  }
}

function sortedNets(nets: ContextNet[]) {
  return [...nets].sort((a, b) => a.depth - b.depth || a.name.localeCompare(b.name))
}

export function buildLayoutGraph(context: CircuitContext, requestedPage: number): LayoutGraph {
  const nets = sortedNets(context.nets)
  const pageCount = Math.max(1, Math.ceil(nets.length / NETS_PER_PAGE))
  const page = Math.min(Math.max(0, requestedPage), pageCount - 1)
  const visibleNets = nets.slice(page * NETS_PER_PAGE, (page + 1) * NETS_PER_PAGE)
  const nodeByRef = new Map(context.nodes.map(node => [node.ref, node]))
  const nodes: LayoutNode[] = [componentNode(context.target, context.target.ref)]
  const edges: LayoutEdge[] = []
  const addedComponents = new Set([context.target.ref])

  visibleNets.forEach(net => {
    const uniqueRefs = [...new Set(net.nodeRefs)]
    const depthOneAnchor = uniqueRefs.filter(ref => nodeByRef.get(ref)?.depth === 1).sort()[0]
    const anchorRef = uniqueRefs.includes(context.target.ref) ? context.target.ref : depthOneAnchor
    if (!anchorRef) return

    const netId = `net:${net.name}`
    nodes.push({
      id: netId,
      kind: 'net',
      label: net.name,
      depth: net.depth,
      width: Math.max(76, net.name.length * 8 + 26),
      height: 34,
    })
    if (!addedComponents.has(anchorRef)) {
      const anchor = nodeByRef.get(anchorRef)
      if (anchor) {
        nodes.push(componentNode(anchor, context.target.ref))
        addedComponents.add(anchorRef)
      }
    }
    edges.push({ id: `edge:${anchorRef}:${net.name}`, source: `component:${anchorRef}`, target: netId, depth: net.depth })

    const neighbors = uniqueRefs.filter(ref => ref !== anchorRef).sort().slice(0, NEIGHBORS_PER_NET)
    neighbors.forEach(ref => {
      if (!addedComponents.has(ref)) {
        const node = nodeByRef.get(ref)
        if (node) {
          nodes.push(componentNode(node, context.target.ref))
          addedComponents.add(ref)
        }
      }
      if (addedComponents.has(ref)) {
        edges.push({ id: `edge:${net.name}:${ref}`, source: netId, target: `component:${ref}`, depth: net.depth })
      }
    })

    const hiddenCount = Math.max(0, uniqueRefs.length - 1 - neighbors.length) + net.more
    if (hiddenCount > 0) {
      const overflowId = `overflow:${net.name}`
      nodes.push({ id: overflowId, kind: 'overflow', label: `+${hiddenCount}`, depth: net.depth, width: 48, height: 34 })
      edges.push({ id: `edge:${net.name}:overflow`, source: netId, target: overflowId, depth: net.depth })
    }
  })

  return { page, pageCount, visibleNetNames: visibleNets.map(net => net.name), nodes, edges }
}

export function fallbackLayout(graph: LayoutGraph): LayoutResult {
  const target = graph.nodes.find(node => node.kind === 'target')
  const nets = graph.nodes.filter(node => node.kind === 'net')
  const others = graph.nodes.filter(node => node.kind === 'component' || node.kind === 'overflow')
  const positions = new Map<string, LayoutedNode>()
  if (target) positions.set(target.id, { ...target, x: 24, y: Math.max(24, (nets.length - 1) * 46) })
  nets.forEach((node, index) => positions.set(node.id, { ...node, x: 260, y: 24 + index * 92 }))
  others.forEach((node, index) => positions.set(node.id, { ...node, x: 500, y: 18 + index * 68 }))

  const edges = graph.edges.flatMap(edge => {
    const source = positions.get(edge.source)
    const targetNode = positions.get(edge.target)
    if (!source || !targetNode) return []
    const start = { x: source.x + source.width, y: source.y + source.height / 2 }
    const end = { x: targetNode.x, y: targetNode.y + targetNode.height / 2 }
    const middleX = (start.x + end.x) / 2
    return [{ ...edge, points: [start, { x: middleX, y: start.y }, { x: middleX, y: end.y }, end] }]
  })
  const laidOutNodes = [...positions.values()]
  return {
    width: Math.max(640, ...laidOutNodes.map(node => node.x + node.width + 24)),
    height: Math.max(300, ...laidOutNodes.map(node => node.y + node.height + 24)),
    nodes: laidOutNodes,
    edges,
  }
}
