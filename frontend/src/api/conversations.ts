import { apiFetch, apiRequest, responseError } from './client'
import type { ProfileHintDto } from './profile'

export type EvidenceDto = { document: string; page: number | string | null; table: string; row: string; section: string; citation_number: string }
export type CitationDto = { document?: string; page?: number | string | null; table?: string; row?: string; chunk_id?: string | number | null; chunk_index?: number | null }
export type CheckDto = { code: string; basis?: string; value?: number | number[] | null; threshold?: number | number[] | null; unit?: string | null; condition?: string | null; result?: string; why?: string; citation?: CitationDto | null }
export type CandidateDto = { part: string; role?: string; verdict: 'IDENTICAL' | 'SPEC_EQUIVALENT' | 'ROLE_SUFFICIENT' | 'NOT_VERIFIED' | 'NOT_SUFFICIENT'; checks?: CheckDto[]; missing?: string[]; uncertain?: string[]; cautions?: string[]; board_change?: boolean | null; package_citation?: CitationDto | null }
export type JudgementDto = { input_conditions?: { code: string; value: string }[]; kind: 'judge' | 'find' | 'no_rule'; roles: string[]; role_evidence: string[]; results: CandidateDto[]; shown: CandidateDto[]; unverified: CandidateDto[]; capped: boolean }
export type InterruptDto = { missing?: string[]; role_choices?: string[]; question?: string }
export type ResultDto = { answer: string; status: string; stage: string; question_type: string; evidence: EvidenceDto[]; judgement: JudgementDto | Record<string, never>; price_parts: string[]; refusal: string; interrupt: InterruptDto; request_id: string; profile_hints?: ProfileHintDto[] }
export type ThreadDto = { id: string; project_id: number; title?: string; created_at?: string; last_activity_at?: string; latest_run_id?: string | null; status?: string | null }
export type SavedMessageDto = { id: number; run_id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export type ThreadDetailDto = ThreadDto & { title: string; target_ref: string | null; target_locked: boolean;
  latest_run: { id: string; status: string; message_id: number | null } | null; messages: SavedMessageDto[]; next_before_message_id: number | null }
export type RunDto = { id: string; thread_id: string; message_id: number | null; result: ResultDto }
export type StreamEvent = { event: 'run_started' | 'status' | 'requires_input' | 'completed' | 'refused' | 'failed'; data: Record<string, unknown> }
export type RoleLabel = { code: string; name: string }
// 키 없는 데모가 재생하는 기록 질문 하나. resume은 조건 질문에 보낼 기록한 답(인터럽트가 없던 질문은 null)
export type DemoQuestionDto = { id: string; kind: string; circuit: string; demo_id: string | null; target: string; question: string; conditions: string
  resume: { answers: Record<string, string>; role: string } | null }

export const listJudgeRoles = (signal?: AbortSignal) => apiFetch<RoleLabel[]>('/api/judge/roles', { signal })
// 키 없는 데모(DEMO_REPLAY=1)에서만 있는 목록. 아니면 404라 화면은 버튼을 숨긴다(getDemoStatus와 같은 방식)
export const listDemoQuestions = (signal?: AbortSignal) => apiFetch<DemoQuestionDto[]>('/api/demo-questions', { signal })
export const listThreads = (projectId: number, signal?: AbortSignal) => apiFetch<ThreadDto[]>(`/api/projects/${projectId}/threads`, { signal })
export const createThread = (projectId: number, signal?: AbortSignal) => apiFetch<ThreadDto>(`/api/projects/${projectId}/threads`, { method: 'POST', signal })
export const getRun = (runId: string, signal?: AbortSignal) => apiFetch<RunDto>(`/api/runs/${runId}`, { signal })
export const recoverRun = (runId: string, signal?: AbortSignal) => apiFetch<RunDto>(`/api/runs/${runId}/recover`, { method: 'POST', signal })
export const getThread = (threadId: string, signal?: AbortSignal, before?: number) => apiFetch<ThreadDetailDto>(`/api/threads/${encodeURIComponent(threadId)}${before === undefined ? '' : `?before_message_id=${before}`}`, { signal })
export const deleteThread = (threadId: string) => apiFetch<void>(`/api/threads/${encodeURIComponent(threadId)}`, { method: 'DELETE' })

export async function openRunStream(path: string, body: unknown, signal: AbortSignal): Promise<Response> {
  const response = await apiRequest(path, { method: 'POST', credentials: 'same-origin', cache: 'no-store', signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!response.ok) throw await responseError(response)
  if (!response.body) throw { code: 'STREAM_CLOSED', message: '실행 스트림을 열 수 없습니다.', requestId: response.headers.get('X-Request-ID') ?? '' }
  return response
}

export async function readEventStream(response: Response, onEvent: (event: StreamEvent) => void, signal: AbortSignal) {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    signal.throwIfAborted()
    buffer += decoder.decode(value, { stream: !done })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary).replace(/\r/g, '')
      buffer = buffer.slice(boundary + 2)
      const event = frame.split('\n').find(line => line.startsWith('event: '))?.slice(7)
      const data = frame.split('\n').find(line => line.startsWith('data: '))?.slice(6)
      if (!event || !data) throw new Error('malformed SSE frame')
      const parsed = JSON.parse(data) as Record<string, unknown>
      if (!['run_started', 'status', 'requires_input', 'completed', 'refused', 'failed'].includes(event)) throw new Error('unknown SSE event')
      onEvent({ event: event as StreamEvent['event'], data: parsed })
      boundary = buffer.indexOf('\n\n')
    }
    if (done) break
  }
  if (buffer.trim()) throw new Error('incomplete SSE frame')
}
