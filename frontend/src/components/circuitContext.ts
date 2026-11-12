import type { CandidateDto, JudgementDto, RoleLabel } from '../api/conversations'
import type { CircuitNet, CircuitPart, Project } from '../api/projects'

// [왜] 인터럽트는 roles.yaml inputs의 내부 이름(v_in_max)으로 값을 묻는다. 뜻은 backend/prompts/judge_read.md "Value names"를 옮겼다.
// [주의] 판정이 물을 수 있는 이름(필수 조건의 기준식 · 시험 조건, 조건부의 when)만 적었다. 없는 이름은 내부 이름 그대로 보인다
export const INPUT_LABELS: Record<string, string> = {
  VF: '허용 전압 강하', IR: '허용 누설 전류',
  v_ac_rms: '교류 입력 실효 전압', v_out_abs: '음전압 출력의 절댓값', v_peak: '피크 전압',
  i_boot_peak: '부트스트랩 초기 피크 전류', c_hold: '피크 홀드 커패시터', droop_allowed: '허용 전압 감소율',
  err_allowed: '허용 오차', op_amp: '연산증폭기 사용', temp: '사용 온도',
  v_in_max: '입력 전원 최대 전압', v_in_min: '입력 전원 최소 전압', v_reverse_max: '역전압을 거는 다른 전원의 최대 전압',
  v_coil: '릴레이 코일 전압', v_line_max: '보호하는 넷의 정상 최대 전압', v_cc: '로직 전원 전압', v_dd_min: '부하에 필요한 최소 VDD',
  v_logic_max: '두 로직 전압 중 큰 값', v_logic_margin: '로직 여유 전압(받는 쪽 입력 Low 문턱 − 보내는 쪽 출력 Low 최대)',
  v_out: '출력 전압', v_ovp: 'IC 과전압 보호 문턱', v_clamp: '스너버 커패시터(클램프) 전압', v_dss: '스위치(MOSFET) 드레인-소스 정격 전압',
  v_bus: '하프브리지 버스 전압', v_sw_transient: '스위칭 노드 과도 전압', v_signal_pp: '신호 피크-피크 전압',
  v_gs_on: 'MOSFET을 충분히 켜는 게이트 전압', v_gs_max: 'MOSFET VGS 최대 정격', v_gate_drive: '게이트 구동 전압',
  v_drop_allowed: '다이오드에서 허용하는 전압 강하', vz_min: '요구하는 제너 전압 범위의 최솟값', vz_max: '요구하는 제너 전압 범위의 최댓값',
  i_max: '다이오드 최대 순방향(부하) 전류', i_coil: '릴레이 코일 정상 전류', i_z: '제너 전류', i_short: '전원 단락 전류',
  i_fault: '입력 핀으로 들어오는 고장 전류', i_out: '컨버터 최대 출력 전류', i_limit: 'IC 전류 제한값', i_d: '스위치(MOSFET) 정격 드레인 전류',
  ir_allowed: '허용 역누설 전류', ns_np: '변압기 권선비 Ns/Np', n_diodes: '직렬 다이오드 개수',
  vf_test: 'VF를 볼 전류 · 온도', pulse_test: '코일 차단 펄스(전류 · 폭)', hot_test: '누설을 볼 고온 사용 온도', surge_test: '서지 파형(예: 8/20µs)',
  // 예 · 아니오 값(flag)
  vf_selects_source: '다이오드 VF가 부하에 전원을 대는 쪽을 정하나요? (예/아니오)', pwm: 'PWM으로 스위칭하나요? (예/아니오)',
  data_line: '데이터 · 신호선에 달려 있나요? (예/아니오)', ac_input: '입력이 AC인가요? (예/아니오)',
  discrete_bridge: '브리지를 다이오드 4개로 만들었나요? (예/아니오)', bulk_cap: '정류기 뒤에 큰 평활 커패시터가 있나요? (예/아니오)',
  external_port: '보호하는 넷이 외부 커넥터로 나가나요? (예/아니오)', battery: '전원이 배터리인가요? (예/아니오)',
  orig_schottky: '원래 다이오드가 쇼트키인가요? (예/아니오)', high_impedance: '보호하는 입력이 고임피던스인가요? (예/아니오)',
  fast_signal: '빠른 신호(UART · SPI · 고주파)인가요? (예/아니오)', large_pullup: '풀업 저항이 큰가요? (예/아니오)',
  f_over_100khz: '스위칭 주파수가 100kHz보다 높나요? (예/아니오)', long_high_side: '하이사이드 스위치가 오래 켜져 있나요? (예/아니오)',
  negative_out: '차지 펌프가 음전압을 만드나요? (예/아니오)', peak_hold: '방전 저항 없는 피크 홀드인가요? (예/아니오)',
  snubber: '변압기 1차 측에 스너버 · 클램프가 있나요? (예/아니오)', strong_driver: '게이트 드라이버 출력 피크 전류가 큰가요? (예/아니오)',
  large_timing_r: '리셋 타이밍 저항이 큰가요? (예/아니오)', high_stall: '모터 정지(stall) 전류가 큰가요? (예/아니오)',
}


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
export type ContextCondition = { code: string; label: string; value: string }
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

export function approvableCandidatesOf(judgement?: JudgementDto | Record<string, never>): CandidateDto[] {
  return candidatesOf(judgement).filter(item => item.verdict === 'IDENTICAL' || item.verdict === 'SPEC_EQUIVALENT' || item.verdict === 'ROLE_SUFFICIENT')
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
  const verified = judgement && 'kind' in judgement ? judgement.input_conditions ?? [] : []
  const conditions: ContextCondition[] = verified.length
    ? verified.map(item => ({ code: item.code, label: INPUT_LABELS[item.code] ?? item.code, value: item.value }))
    : providedConditionText.trim()
    ? [{ code: 'USER', label: '사용자 입력', value: providedConditionText.trim() }]
    : []
  const missing = [...new Set([...interruptMissing, ...candidates.flatMap(candidate => candidate.missing ?? [])])]

  return { ...base, state: 'ready', nodes, nets, role, conditions, missing, candidates }
}
