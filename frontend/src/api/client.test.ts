import { afterEach, expect, it, vi } from 'vitest'
import { apiFetch, apiRequest, dummyFlowEnabled, errorMessage, requestIdProps } from './client'
import { fetchPrices } from './prices'
import { openRunStream } from './conversations'

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs() })

it('expires sessions for HTML 401 errors and keeps the header request id', async () => {
  const expired = vi.fn()
  window.addEventListener('sojafit:session-expired', expired)
  try {
    vi.stubGlobal('fetch', async () => new Response('<html>private proxy text</html>', { status: 401, headers: { 'X-Request-ID': 'proxy-1' } }))
    await expect(apiFetch('/api/auth/me')).rejects.toEqual({ code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', requestId: 'proxy-1' })
    expect(expired).toHaveBeenCalledOnce()
  } finally { window.removeEventListener('sojafit:session-expired', expired) }
})

it.each(['', 'not-json', 'null', '{"error":null}', '{"detail":"private"}', '{"error":{"code":9,"message":{},"request_id":[]}}', '{"error":{"code":"","message":"","request_id":""}}'])('normalizes invalid error body %s', async body => {
  vi.stubGlobal('fetch', async () => new Response(body, { status: 503, headers: { 'X-Request-ID': 'proxy-2' } }))
  await expect(apiFetch('/api/projects')).rejects.toEqual({ code: 'UNAVAILABLE', message: '서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', requestId: 'proxy-2' })
})

it('rejects an HTML success response as a safe API error', async () => {
  vi.stubGlobal('fetch', async () => new Response('<html>wrong server</html>', { headers: { 'X-Request-ID': 'proxy-3' } }))
  await expect(apiFetch('/api/projects')).rejects.toMatchObject({ code: 'INVALID_RESPONSE', requestId: 'proxy-3' })
})

it('normalizes gateway errors for SSE start with the same request id', async () => {
  vi.stubGlobal('fetch', async () => new Response('private gateway response', { status: 503, headers: { 'X-Request-ID': 'sse-proxy' } }))
  await expect(openRunStream('/api/threads/t/runs', {}, new AbortController().signal)).rejects.toMatchObject({ code: 'UNAVAILABLE', requestId: 'sse-proxy' })
})
it('enables the full dummy flow only for the explicit Vite development mode', () => {
  expect(dummyFlowEnabled({ DEV: true, MODE: 'dummy' })).toBe(true)
  expect(dummyFlowEnabled({ DEV: false, MODE: 'dummy' })).toBe(false)
  expect(dummyFlowEnabled({ DEV: true, MODE: 'development' })).toBe(false)
})
it('loads the dummy API on demand only in the dummy development mode', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json('real')))
  expect(await (await apiRequest('/api/judge/roles')).json()).toBe('real')
  vi.stubEnv('MODE', 'dummy')
  expect(await (await apiRequest('/api/judge/roles')).json()).toEqual([{ code: 'R01', name: '역극성 보호(직렬)' }])
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('preserves common error code, message and request id', async () => {
  vi.stubGlobal('fetch', async () => Response.json({ error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'req-1' } }, { status: 401 }))
  await expect(apiFetch('/api/auth/me')).rejects.toMatchObject({ code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', requestId: 'req-1' })
})
it('forces same-origin credentials and preserves request options', async () => {
  let request: RequestInit | undefined
  vi.stubGlobal('fetch', async (_path: string, init: RequestInit) => { request = init; return Response.json({ ok: true }) })
  await expect(apiFetch('/api/auth/logout', { method: 'POST', credentials: 'omit' })).resolves.toEqual({ ok: true })
  expect(request).toMatchObject({ method: 'POST', credentials: 'same-origin', cache: 'no-store' })
})
it('encodes part names and disables browser price caching', async () => {
  let path = ''; let request: RequestInit | undefined
  vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
    path = url; request = init
    return Response.json({ available: false, source: 'Mouser Electronics', reason: 'demo_mode', message: '데모 모드입니다.', parts: [] })
  })
  expect(await fetchPrices(['SS34', '1N4148'])).toMatchObject({ available: false, parts: [] })
  expect(path).toBe('/api/prices?parts=SS34%2C1N4148')
  expect(request).toMatchObject({ cache: 'no-store', credentials: 'same-origin' })
})

it('accepts empty successful 204 responses for owner deletion', async () => {
  vi.stubGlobal('fetch', async () => new Response(null, { status: 204 }))
  await expect(apiFetch('/api/projects/11', { method: 'DELETE' })).resolves.toBeUndefined()
})

it.each([
  [{ code: 'RATE_LIMITED', message: 'RATE_LIMITED', requestId: 'req-9' }, '요청이 많습니다. 잠시 기다린 후 다시 시도해 주세요.'],
  [{ code: 'CONFLICT', message: 'run_in_progress', requestId: 'req-9' }, '이전 질문이 아직 조건 입력을 기다리고 있습니다. 위 칸에 답한 뒤 다시 보내 주세요.'],
  [{ code: 'WEIRD_CODE', message: 'boom', requestId: 'req-9' }, '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'],
  [{ code: 'NOT_FOUND', message: '대화를 찾을 수 없습니다.', requestId: 'req-9' }, '대화를 찾을 수 없습니다.'],
  [new TypeError('Failed to fetch'), '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'],
])('shows a Korean sentence without codes, status or request id: %j', (error, text) => {
  expect(errorMessage(error)).toBe(text)
  expect(errorMessage(error)).not.toMatch(/req-9|[A-Z_]{5,}|run_in_progress|\b[45]\d\d\b|요청 ID/)
})

it('keeps the request id only as a data attribute', () => {
  expect(requestIdProps({ requestId: 'req-9' })).toEqual({ 'data-request-id': 'req-9' })
  expect(requestIdProps(null)).toEqual({})
})
