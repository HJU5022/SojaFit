export type ApiError = { code: string; message: string; requestId: string }

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
  const body = await response.json()
  init.signal?.throwIfAborted()
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('sojafit:session-expired'))
    throw { code: body.error.code, message: body.error.message, requestId: body.error.request_id } satisfies ApiError
  }
  return body as T
}

export function errorMessage(error: unknown): string {
  const api = error as Partial<ApiError> | null
  return api?.message && api?.requestId
    ? `${api.message} (요청 ID: ${api.requestId})`
    : '요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.'
}
