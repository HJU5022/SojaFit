import type { CandidateDto, JudgementDto, RoleLabel } from '../api/conversations'
import type { CircuitNet, CircuitPart, Project } from '../api/projects'

const MAX_NET_NODES = 8
const MAX_PASS_THROUGH_PINS = 3

export type ContextNode = CircuitPart & { depth: 1 | 2 }
export type ContextNet = {
  name: string
  nodes: string[]
  nodeRefs: string[]
  more: number
  depth: 1 | 2
  direction?: { from: string; to: string }
}
export type ContextCondition = { code: 'USER'; label: '사용자 입력'; value: string }
export type CircuitContext = {
  circuitName: string
  state: 'ready' | 'no_connections' | 'target_not_found'
  target: CircuitPart
  nodes: ContextNode[]
  nets: ContextNet[]
  role: { code: string; name: string; evidence: string[] } | null
  conditions: ContextCondition[]
  missing: string[]
  candidates: CandidateDto[]
}

const EMPTY_TARGET: CircuitPart = { ref: '', value: '', footprint: '' }

// [왜] 판정 표 · 근거 선택 · 승인 · 연결 개념도가 같은 후보 목록과 순서(번호)를 써야 한다. 표의 선택 번호로 다른 화면이 후보를 찾는다
// [주의] 찾기의 results는 줄 세우기 전 전체 후보이고 shown은 그 일부다. 둘을 합치면 같은 후보가 두 번 나온다(판정 질문도 shown = results)
export function candidatesOf(judgement?: JudgementDto | Record<string, never>): CandidateDto[] {
  if (!judgement || !('kind' in judgement)) return []
  return judgement.kind === 'find' ? [...judgement.shown, ...judgement.unverified] : judgement.results
}

function shownNode(netNode: CircuitNet['nodes'][number], parts: Map<string, CircuitPart>) {
  const value = parts.get(netNode.ref)?.value ?? ''
  return `${netNode.ref}.${netNode.pinfunction || netNode.pin}(${value})`
}

export function buildCircuitContext(
  project: Project,
  targetRef: string,
  judgement?: JudgementDto,
  roleLabels: RoleLabel[] = [],
  interruptMissing: string[] = [],
  providedConditionText = '',
): CircuitContext {
  const partList = project.connections.parts ?? project.connections.components ?? []
  const parts = new Map(partList.map(part => [part.ref, part]))
  const target = parts.get(targetRef)
  const base = {
    circuitName: project.name,
    target: target ?? EMPTY_TARGET,
    nodes: [] as ContextNode[],
    nets: [] as ContextNet[],
    role: null,
    conditions: [] as ContextCondition[],
    missing: [] as string[],
    candidates: [] as CandidateDto[],
  }
  if (!target) return { ...base, state: 'target_not_found' }
  if (project.connections.nets.length === 0) return { ...base, state: 'no_connections' }

  const netsOf = new Map<string, string[]>()
  const netByName = new Map(project.connections.nets.map(net => [net.name, net]))
  project.connections.nets.forEach(net => net.nodes.forEach(node => {
    const names = netsOf.get(node.ref) ?? []
    if (!names.includes(net.name)) names.push(net.name)
    netsOf.set(node.ref, names)
  }))

  const directNames = [...(netsOf.get(targetRef) ?? [])]
  const directRefs = new Set(directNames.flatMap(name => netByName.get(name)?.nodes.map(node => node.ref) ?? []))
  directRefs.delete(targetRef)
  const names = [...directNames]
  ;[...directRefs].sort().forEach(ref => {
    if ((netsOf.get(ref)?.length ?? 0) <= MAX_PASS_THROUGH_PINS) {
      netsOf.get(ref)?.forEach(name => { if (!names.includes(name)) names.push(name) })
    }
  })

  const depthByRef = new Map<string, 1 | 2>()
  directRefs.forEach(ref => depthByRef.set(ref, 1))
  names.slice(directNames.length).forEach(name => netByName.get(name)?.nodes.forEach(node => {
    if (node.ref !== targetRef && !depthByRef.has(node.ref)) depthByRef.set(node.ref, 2)
  }))
  const nodes = [...depthByRef].map(([ref, depth]) => ({
    ...(parts.get(ref) ?? { ref, value: '', footprint: '' }), depth,
  })).sort((a, b) => a.depth - b.depth || a.ref.localeCompare(b.ref))

  const nets = names.flatMap((name, index) => {
    const net = netByName.get(name)
    if (!net) return []
    const mine = net.nodes.filter(node => node.ref === targetRef)
    const shown = [...mine, ...net.nodes.filter(node => node.ref !== targetRef)].slice(0, MAX_NET_NODES)
    return [{
      name,
      nodes: shown.map(node => shownNode(node, parts)),
      nodeRefs: shown.map(node => node.ref),
      more: Math.max(0, net.nodes.length - MAX_NET_NODES),
      depth: (index < directNames.length ? 1 : 2) as 1 | 2,
    }]
  })

  const candidates = candidatesOf(judgement)
  const roleCode = judgement?.roles[0]
  const role = roleCode ? {
    code: roleCode,
    name: roleLabels.find(item => item.code === roleCode)?.name ?? '',
    evidence: judgement?.role_evidence ?? [],
  } : null
  const conditions: ContextCondition[] = providedConditionText.trim()
    ? [{ code: 'USER', label: '사용자 입력', value: providedConditionText.trim() }]
    : []
  const missing = [...new Set([...interruptMissing, ...candidates.flatMap(candidate => candidate.missing ?? [])])]

  return { ...base, state: 'ready', nodes, nets, role, conditions, missing, candidates }
}
