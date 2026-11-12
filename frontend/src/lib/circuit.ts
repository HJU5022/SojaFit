import type { CircuitPart, Project } from '../api/projects'

export type Neighbor = { ref: string; value: string }
export type ContextNet = { name: string; pin: string; neighbors: Neighbor[]; more: number }

export const partsOf = (project: Project | undefined): CircuitPart[] => project?.connections.parts ?? project?.connections.components ?? []

// 첫 범위는 다이오드다. 참조 번호가 D로 시작하고 값에 LED가 없는 부품을 먼저 보인다.
export const isDiode = (part: CircuitPart) => /^D\d/i.test(part.ref) && !/led/i.test(part.value)

const PER_NET = 5

// 대상 부품의 핀이 닿는 넷과, 그 넷에 함께 달린 부품만 뽑는다. 연결은 넷리스트 그대로다.
export function contextOf(project: Project | undefined, targetRef: string): ContextNet[] {
  if (!project || !targetRef) return []
  const values = new Map(partsOf(project).map(part => [part.ref, part.value]))
  return project.connections.nets.flatMap((net) => {
    const own = net.nodes.find(node => node.ref === targetRef)
    if (!own) return []
    const others = [...new Set(net.nodes.filter(node => node.ref !== targetRef).map(node => node.ref))]
    return [{ name: net.name, pin: own.pinfunction || own.pin,
      neighbors: others.slice(0, PER_NET).map(ref => ({ ref, value: values.get(ref) ?? '' })), more: Math.max(0, others.length - PER_NET) }]
  })
}
