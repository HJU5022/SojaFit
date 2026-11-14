export type DuplicateProject = { id: number; name: string; matches: ('name' | 'netlist')[] }
export type ApiError = { code: string; message: string; requestId: string; retryAfter?: number; duplicates?: DuplicateProject[] }

export function dummyFlowEnabled(env: { DEV: boolean; MODE: string }) {
  return env.DEV && env.MODE === 'dummy'
}

export function apiRequest(path: string, init: RequestInit = {}) {
  // [왜] dummyFlowEnabled와 같은 조건을 import.meta.env 칸으로 바로 쓴다. 빌드가 이 칸을 상수(false)로 바꿔야
  //      운영 번들에서 dummy.ts를 통째로 뺀다. 함수에 env 객체를 넘기면 빌드가 조건을 못 접어 목업이 번들에 남았다
  if (import.meta.env.DEV && import.meta.env.MODE === 'dummy') return import('./dummy').then(dummy => dummy.dummyApiFetch(path, init))
  return fetch(path, init)
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiRequest(path, { ...init, credentials: 'same-origin', cache: 'no-store' })
  init.signal?.throwIfAborted()
  if (response.status === 204 && response.ok) return undefined as T
  if (!response.ok) throw await responseError(response)
  const body = await response.json().catch(() => { throw { code: 'INVALID_RESPONSE', message: '서버 응답을 확인할 수 없습니다.', requestId: response.headers.get('X-Request-ID') ?? '' } satisfies ApiError })
  init.signal?.throwIfAborted()
  return body as T
}

export async function responseError(response: Response): Promise<ApiError> {
  if (response.status === 401) window.dispatchEvent(new Event('sojafit:session-expired'))
  const body = await response.json().catch(() => null)
  const error = body?.error
  const candidates: unknown = body?.details?.duplicates
  const duplicates = response.status === 409 && error?.code === 'CONFLICT' && Array.isArray(candidates) ? candidates.slice(0, 5).filter((value): value is DuplicateProject => {
    const item = value as Partial<DuplicateProject> | null
    return item !== null && typeof item === 'object' && Number.isSafeInteger(item.id) && item.id! > 0
      && typeof item.name === 'string' && item.name.trim().length > 0 && item.name.length <= 200
      && Array.isArray(item.matches) && item.matches.length > 0 && item.matches.length <= 2
      && item.matches.every(match => match === 'name' || match === 'netlist')
  }) : []
  const codes: Record<number, string> = { 400: 'VALIDATION_ERROR', 401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'CONFLICT',
    413: 'PAYLOAD_TOO_LARGE', 422: 'VALIDATION_ERROR', 429: 'RATE_LIMITED', 502: 'UPSTREAM_ERROR', 503: 'UNAVAILABLE', 504: 'TIMEOUT' }
  return { code: typeof error?.code === 'string' && error.code.trim() ? error.code : codes[response.status] ?? 'HTTP_ERROR',
    message: typeof error?.message === 'string' && error.message.trim() ? error.message : response.status === 401 ? '로그인이 필요합니다.' : '서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.',
    requestId: typeof error?.request_id === 'string' && error.request_id ? error.request_id : response.headers.get('X-Request-ID') ?? '',
    ...(Number(response.headers.get('Retry-After')) > 0 && { retryAfter: Number(response.headers.get('Retry-After')) }),
    ...(duplicates.length > 0 && { duplicates }) }
}

const FALLBACK = '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
// 서버가 한국어 문장을 보내지 않았을 때 쓰는, 오류 코드별 안내(SPEC.md 공통 오류 16개)
const CODE_MESSAGES: Record<string, string> = {
  UNAUTHORIZED: '로그인이 필요합니다. 다시 로그인해 주세요.',
  FORBIDDEN: '이 작업을 할 권한이 없습니다.',
  ORIGIN_MISMATCH: '요청을 허용할 수 없습니다. 공식 서비스 주소에서 다시 접속해 주세요.',
  NOT_FOUND: '찾는 항목이 없습니다. 목록을 새로고침해 주세요.',
  VALIDATION_ERROR: '입력한 내용을 확인한 뒤 다시 시도해 주세요.',
  CONDITION_PENDING: '조건 질문에 먼저 답해 주세요.',
  ALREADY_APPROVED: '이미 승인했거나 승인할 수 없는 판정입니다.',
  CONFLICT: '지금 상태에서는 처리할 수 없습니다. 새로고침한 뒤 다시 시도해 주세요.',
  PAYLOAD_TOO_LARGE: '보낸 내용이 너무 큽니다. 줄여서 다시 보내 주세요.',
  RATE_LIMITED: '요청이 많습니다. 잠시 기다린 후 다시 시도해 주세요.',
  LIMIT_EXCEEDED: '사용 한도에 도달했습니다. 나중에 다시 시도해 주세요.',
  UPSTREAM_ERROR: '외부 서비스에 문제가 있습니다. 잠시 후 다시 시도해 주세요.',
  UNAVAILABLE: '서비스를 지금 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.',
  SCHEMATIC_NOT_FOUND: '원본 회로도를 찾지 못했습니다. 검색어를 바꿔 보세요.',
  TIMEOUT: '응답이 늦어지고 있습니다. 잠시 후 다시 시도해 주세요.',
  INTERNAL_ERROR: '서비스에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.',
}
// 서버가 문장 대신 식별자 문자열을 detail로 보내는 경우(backend/api/conversations.py · projects.py의 409)
const DETAIL_MESSAGES: Record<string, string> = {
  run_in_progress: '이전 질문이 아직 조건 입력을 기다리고 있습니다. 위 칸에 답한 뒤 다시 보내 주세요.',
}
// 사용자에게는 코드 · 상태 번호 · 요청 ID를 보이지 않는다. 요청 ID는 data-request-id로만 남긴다
export function errorMessage(error: unknown): string {
  const api = error as Partial<ApiError> | null
  const message = api?.message ?? ''
  if (DETAIL_MESSAGES[message]) return DETAIL_MESSAGES[message]
  if (/[가-힣]/.test(message)) return message
  return CODE_MESSAGES[api?.code ?? ''] ?? FALLBACK
}
export const requestIdProps = (error: unknown) => {
  const id = (error as Partial<ApiError> | null)?.requestId
  return id ? { 'data-request-id': id } : {}
}
