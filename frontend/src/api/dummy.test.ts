import { beforeEach, expect, it, vi } from 'vitest'

beforeEach(() => vi.resetModules())

async function freshDummy() {
  return (await import('./dummy')).dummyApiFetch
}

async function json(response: Response) {
  return await response.json() as Record<string, unknown>
}

it('serves the breadboard project, D1 context, and role labels', async () => {
  const request = await freshDummy()
  const projects = await json(await request('/api/projects')) as unknown as { name: string; demo_id: string }[]
  expect(projects).toEqual([expect.objectContaining({ name: 'breadboard_supply', demo_id: 'breadboard_supply' })])

  const project = await json(await request('/api/projects/1')) as unknown as {
    connections: { parts: { ref: string; value: string }[]; nets: { nodes: { ref: string }[] }[] }
  }
  expect(project.connections.parts).toEqual(expect.arrayContaining([
    expect.objectContaining({ ref: 'D1', value: '1N4001' }),
    expect.objectContaining({ ref: 'J1' }),
    expect.objectContaining({ ref: 'S1' }),
    expect.objectContaining({ ref: 'F1' }),
    expect.objectContaining({ ref: 'U1' }),
  ]))
  expect(project.connections.nets.flatMap(net => net.nodes.map(node => node.ref))).toEqual(expect.arrayContaining(['D1', 'J1', 'S1', 'F1', 'U1']))
  expect(await json(await request('/api/judge/roles'))).toEqual([{ code: 'R01', name: '역극성 보호(직렬)' }])
})

it('returns a completed SSE run with role evidence, candidate judgement, and datasheet evidence', async () => {
  const request = await freshDummy()
  const thread = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  const response = await request(`/api/threads/${thread.id}/runs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: 'D1을 SS34로 바꿔도 되나요?', target_ref: 'D1', conditions: '' }),
  })
  const stream = await response.text()
  expect(response.headers.get('Content-Type')).toContain('text/event-stream')
  expect(stream).toContain('event: run_started')
  expect(stream).toContain('event: status')
  expect(stream).toContain('event: completed')
  expect(stream).toContain('D1.K → RAW')
  expect(stream).toContain('ROLE_SUFFICIENT')
  expect(stream).toContain('SS34.pdf')

  const run = await json(await request('/api/runs/dummy-run')) as { message_id: number; result: { price_parts: string[] } }
  expect(run.message_id).toBe(9)
  expect(run.result.price_parts).toEqual(['SS34'])
})

it('keeps price data transient while approval, quote, and approved-case state changes', async () => {
  const request = await freshDummy()
  const approvalResponse = await request('/api/messages/9/approvals', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' }),
  })
  expect(approvalResponse.status).toBe(201)
  const approval = await json(approvalResponse) as { id: number; case_id: number }

  const cases = await json(await request('/api/approved-cases')) as unknown as { candidate_part: string; verdict: string }[]
  expect(cases).toEqual([expect.objectContaining({ candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' })])

  const prices = await json(await request('/api/prices?parts=SS34')) as { available: boolean; parts: unknown[] }
  expect(prices).toMatchObject({ available: true })
  expect(prices.parts).toHaveLength(1)

  const quoteResponse = await request(`/api/approvals/${approval.id}/quotes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quantity: 2 }),
  })
  expect(quoteResponse.status).toBe(201)
  const quote = await json(quoteResponse)
  expect(quote).toEqual({ id: 5, approval_id: approval.id, part_number: 'SS34', quantity: 2 })
  expect(quote).not.toHaveProperty('price')
  expect(quote).not.toHaveProperty('availability')

  expect((await request(`/api/approved-cases/${approval.case_id}`, { method: 'DELETE' })).status).toBe(204)
  expect(await json(await request('/api/approved-cases'))).toEqual([])
})

it('returns a standard 404 without falling through and honors an already aborted request', async () => {
  const request = await freshDummy()
  const missing = await request('/api/not-defined')
  expect(missing.status).toBe(404)
  expect(await json(missing)).toEqual({ error: { code: 'NOT_FOUND', message: '더미 API 경로를 찾을 수 없습니다.', request_id: 'dummy-request' } })

  const controller = new AbortController()
  controller.abort()
  await expect(request('/api/projects', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
})

it('creates demo projects through the same POST contract as the real API', async () => {
  const request = await freshDummy()
  const response = await request('/api/projects', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ demo_id: 'breadboard_supply', name: '내 데모' }),
  })
  expect(response.status).toBe(201)
  const created = await json(response) as { id: number }
  expect(created).toMatchObject({ name: '내 데모', source_kind: 'demo', demo_id: 'breadboard_supply', connections: expect.any(Object) })
  const threads = await request(`/api/projects/${created.id}/threads`)
  expect(threads.status).toBe(200)
  expect(await json(threads)).toEqual([])
})

it('creates uploaded projects through the same multipart contract as the real API', async () => {
  const request = await freshDummy()
  const body = new FormData(); body.append('name', '업로드 회로'); body.append('file', new File(['(export (components))'], 'board.net'))
  const response = await request('/api/projects/upload', { method: 'POST', body })
  expect(response.status).toBe(201)
  expect(await json(response)).toMatchObject({ name: '업로드 회로', source_kind: 'upload', demo_id: null, connections: expect.any(Object) })
})
