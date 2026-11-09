import { afterEach, expect, it, vi } from 'vitest'
import { apiFetch } from './client'
import { fetchPrices } from './prices'

afterEach(() => vi.unstubAllGlobals())
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
