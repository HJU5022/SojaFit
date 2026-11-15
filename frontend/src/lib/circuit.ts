import type { CircuitPart, Project } from '../api/projects'

export type Neighbor = { ref: string; value: string }
export type ContextNet = { name: string; pin: string; neighbors: Neighbor[]; more: number }

export const partsOf = (project: Project | undefined): CircuitPart[] => project?.connections.parts ?? project?.connections.components ?? []

export function unsupportedPartReason(part: CircuitPart): string {
  const identifiers = [part.value, part.footprint].join(' ')
  const description = (part.description ?? '').trim()
  // 용도 설명의 "diode for LED backlight"는 부품 종류가 LED라는 뜻이 아니다.
  const ledDescription = /light[\s-]*emitting[\s-]*diode|발광\s*다이오드|^(?:(?:red|green|blue|white|yellow|amber|orange|rgb)\s+)?leds?$/i.test(description)
  if (/(^|[^a-z0-9])leds?(?=$|[^a-z])/i.test(identifiers) || ledDescription || /^LED\d/i.test(part.ref)) {
    return `${part.ref}은(는) LED로 식별됩니다. 현재 LED 대체 판정은 지원하지 않습니다. 일반 다이오드를 선택해 주세요.`
  }
  if (/(^|[^a-z0-9])(?:7|seven)[\s_-]*seg(?:ment)?/i.test(identifiers)) {
    return `${part.ref}은(는) 표시기로 식별됩니다. 현재 표시기 대체 판정은 지원하지 않습니다. 일반 다이오드를 선택해 주세요.`
  }
  return /^D\d/i.test(part.ref) ? '' : `${part.ref}은(는) 현재 판정 범위 밖입니다. 지금은 다이오드만 판정합니다.`
}

// 값이 STAT 같은 별칭이어도 설명·풋프린트에서 LED를 확인한다.
export const isDiode = (part: CircuitPart) => !unsupportedPartReason(part)

// 질문에서 먼저 나오는 부품을 찾는다. 참조 번호 앞뒤에 영문·숫자가 없어야 하므로 D1은 D10·LED1에 걸리지 않고 'D1을'은 맞는다.
export function partIn(question: string, parts: CircuitPart[]): CircuitPart | undefined {
  const at = (part: CircuitPart) => question.search(new RegExp(`(?<![A-Za-z0-9])${part.ref.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Za-z0-9])`, 'i'))
  return parts.map(part => ({ part, index: at(part) })).filter(hit => hit.index >= 0).sort((a, b) => a.index - b.index)[0]?.part
}

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
