import type { ResultDto, RunDto, ThreadDetailDto } from './conversations'
import type { Project } from './projects'
import { dummyDemos, dummyProjects } from 'virtual:sojafit-dummy-circuits'
import type { ApprovalDto, ApprovedCaseDto } from './quotes'

const REQUEST_ID = 'dummy-request'
const NOW = '2026-11-09T00:00:00Z'
const SS34L_URL = 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf'

const result: ResultDto = {
  answer: 'SS34L는 입력 최대 전압 12 V에 안전 여유 1.25를 적용한 요구치 15 V보다 VRRM 40 V가 높습니다.\n최대 순방향 전류 1 A에 안전 여유 1.43을 적용한 요구치 1.43 A보다 IF(AV) 3 A가 높습니다.\n두 필수 전기 조건은 통과했지만 Sub SMA 패키지는 기존 장착부와 다를 수 있으므로 실제 풋프린트와 극성을 확인해야 합니다. [7]',
  status: 'completed',
  stage: '완료',
  question_type: 'candidate_judge',
  evidence: [{ document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'VRRM', section: 'Absolute Maximum Ratings', citation_number: '7' }],
  judgement: {
    kind: 'judge',
    roles: ['R01'],
    role_evidence: ['D1.C → Net-(F1-1)', 'D1.A → Net-(S1-S)'],
    results: [{
      part: 'SS34L',
      role: 'R01',
      verdict: 'ROLE_SUFFICIENT',
      board_change: true,
      missing: [],
      uncertain: [],
      cautions: ['Sub SMA 패키지의 실제 풋프린트와 극성을 확인해야 합니다.'],
      checks: [{
        code: 'VRRM', tier: 'required', op: '>=',
        basis: '입력 최대 전압 12 V × 안전 여유 1.25', threshold: 15, value: 40, unit: 'V', condition: 'TA=25°C',
        result: 'pass', why: '후보 역전압 정격이 요구 기준 이상입니다.',
        citation: { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'VRRM', source_url: SS34L_URL, outline_page: 4 },
      }, {
        code: 'IF_AV', tier: 'required', op: '>=',
        basis: '최대 순방향 전류 1 A × 안전 여유 1.43', threshold: 1.43, value: 3, unit: 'A', condition: 'TA=25°C',
        result: 'pass', why: '후보 평균 순방향 전류 정격이 요구 기준 이상입니다.',
        citation: { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'IF(AV)', source_url: SS34L_URL, outline_page: 4 },
      }],
      package_citation: { document: 'SS34L SERIES_C2103.pdf', page: 4, table: 'PACKAGE OUTLINE DIMENSIONS', row: 'Sub SMA', source_url: SS34L_URL, outline_page: 4 },
    }],
    shown: [],
    unverified: [],
    capped: false,
  },
  price_parts: ['SS34L'],
  refusal: '',
  interrupt: {},
  request_id: REQUEST_ID,
}

let approval: ApprovalDto | null = null
let approvedCase: ApprovedCaseDto | null = null
let projects: Project[] = structuredClone(dummyProjects)
let threads: ThreadDetailDto[] = []
let runs: RunDto[] = []
let threadSequence = 0
let runSequence = 0

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

  if (method === 'GET' && pathname === '/api/auth/demo') return json({ enabled: true })

  if (method === 'GET' && pathname === '/api/projects') {
    return json(projects.map(({ connections: _connections, ...summary }) => summary))
  }
  const projectMatch = pathname.match(/^\/api\/projects\/(\d+)$/)
  if (method === 'GET' && projectMatch) {
    const found = projects.find(item => item.id === Number(projectMatch[1]))
    return found ? json(found) : notFound()
  }
  if (method === 'PATCH' && projectMatch) {
    const name = String((JSON.parse(String(init.body ?? '{}')) as { name?: string }).name ?? '').trim()
    const found = projects.find(item => item.id === Number(projectMatch[1]))
    if (!found || !name) return found ? json({ error: { code: 'VALIDATION_ERROR', message: '프로젝트 이름을 입력해 주세요.', request_id: REQUEST_ID } }, 422) : notFound()
    projects = projects.map(item => item === found ? { ...item, name, updated_at: NOW } : item)
    return json({ ...found, name, updated_at: NOW })
  }
  if (method === 'DELETE' && projectMatch) {
    projects = projects.filter(item => item.id !== Number(projectMatch[1]))
    return new Response(null, { status: 204 })
  }
  if (method === 'POST' && pathname === '/api/projects') {
    const body = JSON.parse(String(init.body ?? '{}')) as { demo_id?: string; name?: string }
    const source = dummyProjects.find(item => item.demo_id === body.demo_id)
    if (!source) return json({ error: { code: 'VALIDATION_ERROR', message: '등록된 데모 회로를 선택해 주세요.', request_id: REQUEST_ID } }, 422)
    const created: Project = { ...structuredClone(source), id: Math.max(...projects.map(item => item.id), 0) + 1,
      name: body.name?.trim() || source.name, source_kind: 'demo',
      created_at: NOW, updated_at: NOW }
    projects = [...projects, created]
    return json(created, 201)
  }
  if (method === 'POST' && pathname === '/api/projects/upload') {
    return json({ error: { code: 'UNAVAILABLE',
      message: '넷리스트 첨부는 실제 API 서버에 연결한 화면에서 사용할 수 있습니다. 더미 모드에서는 파일을 해석하지 않습니다.',
      request_id: REQUEST_ID } }, 503)
  }
  if (method === 'GET' && pathname === '/api/demo-circuits') {
    const query = (url.searchParams.get('q') ?? '').trim().toLocaleLowerCase()
    const offset = Math.max(0, Number(url.searchParams.get('offset') ?? 0) || 0)
    const limit = Math.min(100, Math.max(1, Number(url.searchParams.get('limit') ?? 100) || 100))
    const demos = query ? dummyDemos.filter(item => `${item.id} ${item.name}`.toLocaleLowerCase().includes(query)) : dummyDemos
    return json(demos.slice(offset, offset + limit))
  }
  if (method === 'GET' && pathname === '/api/judge/roles') return json([{ code: 'R01', name: '역극성 보호(직렬)' }])
  const projectThreadsMatch = pathname.match(/^\/api\/projects\/(\d+)\/threads$/)
  if (method === 'GET' && projectThreadsMatch) {
    const projectId = Number(projectThreadsMatch[1])
    return projects.some(item => item.id === projectId) ? json(threads.filter(item => item.project_id === projectId).map(item => ({
      id: item.id, project_id: item.project_id, title: item.title, created_at: NOW, last_activity_at: NOW,
      latest_run_id: item.latest_run?.id ?? null, status: item.latest_run?.status ?? null,
    })).reverse()) : notFound()
  }
  if (method === 'POST' && projectThreadsMatch) {
    const projectId = Number(projectThreadsMatch[1])
    if (!projects.some(item => item.id === projectId)) return notFound()
    const sequence = threadSequence++
    const id = sequence ? `dummy-thread-${sequence + 1}` : 'dummy-thread'
    threads.push({ id, project_id: projectId, title: '새 대화', target_ref: null, target_locked: false, latest_run: null, messages: [], next_before_message_id: null })
    return json({ id, project_id: projectId }, 201)
  }
  const threadMatch = pathname.match(/^\/api\/threads\/([^/]+)$/)
  if (method === 'DELETE' && threadMatch) {
    const thread = threads.find(item => item.id === threadMatch[1])
    if (!thread) return notFound()
    threads = threads.filter(item => item.id !== thread.id)
    if (approval && thread.messages.some(message => message.id === approval?.message_id)) { approval = null; approvedCase = null }
    runs = runs.filter(item => item.thread_id !== thread.id)
    return new Response(null, { status: 204 })
  }
  if (method === 'GET' && threadMatch) {
    const thread = threads.find(item => item.id === threadMatch[1])
    if (!thread) return notFound()
    const before = Number(url.searchParams.get('before_message_id') ?? Infinity)
    const limit = Number(url.searchParams.get('limit') ?? 50)
    const eligible = thread.messages.filter(message => message.id < before)
    const messages = eligible.slice(-limit)
    return json({ ...thread, messages, next_before_message_id: eligible.length > limit ? messages[0].id : null })
  }

  const startMatch = pathname.match(/^\/api\/threads\/([^/]+)\/runs$/)
  if (method === 'POST' && startMatch) {
    const thread = threads.find(item => item.id === startMatch[1])
    if (!thread) return notFound()
    const input = JSON.parse(String(init.body ?? '{}')) as { question: string; target_ref: string }
    const sequence = runSequence++
    const id = sequence ? `dummy-run-${sequence + 1}` : 'dummy-run'
    const messageId = 9 + sequence * 2
    runs.push({ id, thread_id: thread.id, message_id: messageId, result })
    if (!thread.messages.length) {
      const title = input.question.trim().replace(/\s+/g, ' ')
      thread.title = Array.from(title).slice(0, 60).join('') + (Array.from(title).length > 60 ? '…' : '')
    }
    thread.target_ref = input.target_ref; thread.target_locked = true
    thread.latest_run = { id, status: 'completed', message_id: messageId }
    thread.messages.push({ id: messageId - 1, run_id: id, role: 'user', content: input.question, created_at: NOW },
      { id: messageId, run_id: id, role: 'assistant', content: result.answer, created_at: NOW })
    const body = `${sse('run_started', { run_id: id })}${sse('status', { stage: '근거와 후보 판정' })}${sse('completed', result)}`
    return new Response(body, { headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store' } })
  }
  const runMatch = pathname.match(/^\/api\/runs\/([^/]+)$/)
  const recoverMatch = pathname.match(/^\/api\/runs\/([^/]+)\/recover$/)
  if (method === 'POST' && recoverMatch) {
    const run = runs.find(item => item.id === recoverMatch[1])
    return run ? json(run) : notFound()
  }
  if (method === 'GET' && runMatch) {
    const run = runs.find(item => item.id === runMatch[1])
    return run ? json(run) : notFound()
  }

  if (method === 'POST' && pathname === '/api/messages/9/approvals') {
    approval = { id: 3, message_id: 9, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT', case_id: 4 }
    approvedCase = { id: 4, approval_id: 3, candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' }
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
    const part = url.searchParams.get('parts')?.split(',')[0] || 'SS34L'
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
