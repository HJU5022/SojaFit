export type ApiError = { code: string; message: string; requestId: string }

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, credentials: 'same-origin', cache: 'no-store' })
  init.signal?.throwIfAborted()
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
