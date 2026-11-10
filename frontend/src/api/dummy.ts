import type { ResultDto } from './conversations'
import type { Project } from './projects'
import type { ApprovalDto, ApprovedCaseDto } from './quotes'

const REQUEST_ID = 'dummy-request'
const NOW = '2026-11-09T00:00:00Z'

const project: Project = {
  id: 1,
  name: 'breadboard_supply',
  source_kind: 'demo',
  demo_id: 'breadboard_supply',
  created_at: NOW,
  updated_at: NOW,
  connections: {
    sample_id: 'breadboard_supply',
    status: 'ready',
    parts: [
      { ref: 'D1', value: '1N4001', footprint: 'Diode_THT:D_DO-41_SOD81' },
      { ref: 'J1', value: 'DC_IN', footprint: 'Connector_BarrelJack:BarrelJack_Horizontal' },
      { ref: 'S1', value: 'POWER', footprint: 'Button_Switch_THT:SW_CuK_JS202011SCQN' },
      { ref: 'F1', value: '500mA', footprint: 'Fuse:Fuse_Bourns_MF-RG300' },
      { ref: 'U1', value: 'LM7805', footprint: 'Package_TO_SOT_THT:TO-220-3_Vertical' },
      { ref: 'C1', value: '10uF', footprint: 'Capacitor_THT:CP_Radial_D5.0mm_P2.00mm' },
    ],
    nets: [
      { name: 'RAW', nodes: [
        { ref: 'D1', pin: '1', pinfunction: 'K' },
        { ref: 'F1', pin: '2' },
        { ref: 'U1', pin: '1', pinfunction: 'IN' },
      ] },
      { name: 'RETURN', nodes: [
        { ref: 'D1', pin: '2', pinfunction: 'A' },
        { ref: 'J1', pin: '2' },
        { ref: 'S1', pin: '2' },
      ] },
      { name: '+5V', nodes: [
        { ref: 'U1', pin: '3', pinfunction: 'OUT' },
        { ref: 'C1', pin: '1' },
      ] },
    ],
  },
}

const result: ResultDto = {
  answer: 'SS34는 D1의 역극성 보호 역할에 사용할 수 있는 후보로 판정했습니다. 근거와 실제 사용 조건을 함께 확인하세요. [7]',
  status: 'completed',
  stage: '완료',
  question_type: 'candidate_judge',
  evidence: [{ document: 'SS34.pdf', page: 2, table: 'MAXIMUM RATINGS', row: 'VRRM', section: 'Absolute Maximum Ratings', citation_number: '7' }],
  judgement: {
    kind: 'judge',
    roles: ['R01'],
    role_evidence: ['D1.K → RAW', 'D1.A → RETURN'],
    results: [{
      part: 'SS34',
      role: 'R01',
      verdict: 'ROLE_SUFFICIENT',
      board_change: false,
      missing: [],
      uncertain: [],
      cautions: ['실제 최대 전압·전류 조건은 사용자가 확인해야 합니다.'],
      checks: [{
        code: 'ROLE',
        basis: '역극성 보호 역할과 정류 다이오드 계열 확인',
        result: 'pass',
        why: '역할 기준을 충족하는 문서 근거가 있습니다.',
        citation: { document: 'SS34.pdf', page: 2, table: 'MAXIMUM RATINGS', row: 'VRRM' },
      }],
      package_citation: { document: 'SS34.pdf', page: 1, table: 'FEATURES', row: 'DO-214AB' },
    }],
    shown: [],
    unverified: [],
    capped: false,
  },
  price_parts: ['SS34'],
  refusal: '',
  interrupt: {},
  request_id: REQUEST_ID,
}

let approval: ApprovalDto | null = null
let approvedCase: ApprovedCaseDto | null = null
let projects: Project[] = [project]

function json(data: unknown, status = 200) {
  return Response.json(data, { status })
}

function notFound() {
  return json({ error: { code: 'NOT_FOUND', message: '더미 API 경로를 찾을 수 없습니다.', request_id: REQUEST_ID } }, 404)
}

function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

export async function dummyApiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  init.signal?.throwIfAborted()
  const url = new URL(path, 'http://dummy.local')
  const method = (init.method ?? 'GET').toUpperCase()
  const pathname = url.pathname

  if (method === 'GET' && pathname === '/api/projects') {
    return json(projects.map(({ connections: _connections, ...summary }) => summary))
  }
  const projectMatch = pathname.match(/^\/api\/projects\/(\d+)$/)
  if (method === 'GET' && projectMatch) {
    const found = projects.find(item => item.id === Number(projectMatch[1]))
    return found ? json(found) : notFound()
  }
  if (method === 'POST' && pathname === '/api/projects') {
    const body = JSON.parse(String(init.body ?? '{}')) as { demo_id?: string; name?: string }
    const created: Project = { ...project, id: Math.max(...projects.map(item => item.id)) + 1,
      name: body.name?.trim() || project.name, demo_id: body.demo_id ?? project.demo_id, source_kind: 'demo',
      created_at: NOW, updated_at: NOW }
    projects = [...projects, created]
    return json(created, 201)
  }
  if (method === 'POST' && pathname === '/api/projects/upload') {
    const body = init.body instanceof FormData ? init.body : null
    const created: Project = { ...project, id: Math.max(...projects.map(item => item.id)) + 1,
      name: String(body?.get('name') || project.name), demo_id: null, source_kind: 'upload',
      created_at: NOW, updated_at: NOW }
    projects = [...projects, created]
    return json(created, 201)
  }
  if (method === 'GET' && pathname === '/api/demo-circuits') return json([{ id: 'breadboard_supply', name: 'breadboard_supply' }])
  if (method === 'GET' && pathname === '/api/judge/roles') return json([{ code: 'R01', name: '역극성 보호(직렬)' }])
  const projectThreadsMatch = pathname.match(/^\/api\/projects\/(\d+)\/threads$/)
  if (method === 'GET' && projectThreadsMatch) {
    return projects.some(item => item.id === Number(projectThreadsMatch[1])) ? json([]) : notFound()
  }
  if (method === 'POST' && pathname === '/api/projects/1/threads') return json({ id: 'dummy-thread', project_id: 1 }, 201)

  if (method === 'POST' && pathname === '/api/threads/dummy-thread/runs') {
    const body = `${sse('run_started', { run_id: 'dummy-run' })}${sse('status', { stage: '근거와 후보 판정' })}${sse('completed', result)}`
    return new Response(body, { headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store' } })
  }
  if (method === 'GET' && pathname === '/api/runs/dummy-run') {
    return json({ id: 'dummy-run', thread_id: 'dummy-thread', message_id: 9, result })
  }

  if (method === 'POST' && pathname === '/api/messages/9/approvals') {
    approval = { id: 3, message_id: 9, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT', case_id: 4 }
    approvedCase = { id: 4, approval_id: 3, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' }
    return json(approval, 201)
  }
  if (method === 'GET' && pathname === '/api/approved-cases') return json(approvedCase ? [approvedCase] : [])
  if (method === 'DELETE' && pathname === '/api/approved-cases/4') {
    approvedCase = null
    return new Response(null, { status: 204 })
  }
  if (method === 'POST' && pathname === '/api/approvals/3/quotes' && approval) {
    const body = JSON.parse(String(init.body ?? '{}')) as { quantity?: number }
    return json({ id: 5, approval_id: approval.id, part_number: approval.candidate_part, quantity: body.quantity ?? 1 }, 201)
  }
  if (method === 'GET' && pathname === '/api/prices') {
    const part = url.searchParams.get('parts')?.split(',')[0] || 'SS34'
    return json({
      available: true,
      source: '더미 공급사',
      fetched_at: NOW,
      parts: [{ part_number: part, manufacturer: 'Dummy Semiconductor', availability: '더미 재고 120개', product_url: null,
        price_breaks: [{ quantity: 1, price: '1.23', currency: 'USD' }] }],
    })
  }
  return notFound()
}
