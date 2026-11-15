import { beforeEach, expect, it, vi } from 'vitest'
import type { RunDto } from './conversations'

beforeEach(() => vi.resetModules())

async function freshDummy() {
  return (await import('./dummy')).dummyApiFetch
}

async function json(response: Response) {
  return await response.json() as Record<string, unknown>
}

it('reports demo mode for the explicit offline dummy API', async () => {
  const request = await freshDummy()
  expect(await json(await request('/api/auth/demo'))).toEqual({ enabled: true })
})

it('serves the breadboard project, D1 context, and role labels', async () => {
  const request = await freshDummy()
  const projects = await json(await request('/api/projects')) as unknown as { name: string; demo_id: string }[]
  expect(projects.map(item => item.demo_id)).toEqual([
    'breadboard_supply', 'mosfet_driver', 'attiny85_dev', 'pro_micro', 'franzininho_diy', 'attiny85_time_switch',
    'fc_rom_vomitter', 'attiny2313a_thermostat', 'tiny85_fan_control', 'ug56_pwm_controller',
    'car_radio_acc_delay', 'overengineered_psu', 'tinydimmer', 'hrem', 'zr7_taillight', null,
  ])

  const project = await json(await request('/api/projects/1')) as unknown as {
    connections: { components?: { ref: string; value: string }[]; parts?: { ref: string; value: string }[]; nets: { name: string; nodes: { ref: string }[] }[] }
  }
  const parts = project.connections.parts ?? project.connections.components
  expect(parts).toEqual(expect.arrayContaining([
    expect.objectContaining({ ref: 'D1', value: '1N4001' }),
    expect.objectContaining({ ref: 'J1' }),
    expect.objectContaining({ ref: 'S1' }),
    expect.objectContaining({ ref: 'F1' }),
    expect.objectContaining({ ref: 'U1', value: 'LM317' }),
  ]))
  expect(project.connections.nets.flatMap(net => net.nodes.map(node => node.ref))).toEqual(expect.arrayContaining(['D1', 'J1', 'S1', 'F1', 'U1']))
  const nets = Object.fromEntries(project.connections.nets.map(net => [net.name, net.nodes.map(node => node.ref)]))
  expect(nets.RAW).toContain('C1')
  expect(nets.VCC).toContain('C2')
  expect(nets.VCC).not.toContain('C1')
  expect(await json(await request('/api/judge/roles'))).toEqual([{ code: 'R01', name: '역극성 보호(직렬)' }])
  const demos = await json(await request('/api/demo-circuits')) as unknown as { id: string; schematic: null | { image_url: string } }[]
  expect(Object.fromEntries(demos.map(item => [item.id, item.schematic?.image_url ?? null]))).toEqual({
    breadboard_supply: '/circuit-schematics/breadboard_supply.png',
    mosfet_driver: '/circuit-schematics/mosfet_driver.png',
    attiny85_dev: '/circuit-schematics/attiny85_dev.png',
    pro_micro: '/circuit-schematics/pro_micro.png',
    franzininho_diy: '/circuit-schematics/franzininho_diy.png',
    attiny85_time_switch: '/circuit-schematics/attiny85_time_switch.png',
    fc_rom_vomitter: '/circuit-schematics/fc_rom_vomitter.png',
    attiny2313a_thermostat: '/circuit-schematics/attiny2313a_thermostat.png',
    tiny85_fan_control: '/circuit-schematics/tiny85_fan_control.png',
    ug56_pwm_controller: '/circuit-schematics/ug56_pwm_controller.png',
    car_radio_acc_delay: '/circuit-schematics/car_radio_acc_delay.png',
    overengineered_psu: '/circuit-schematics/overengineered_psu.png',
    tinydimmer: '/circuit-schematics/tinydimmer.png',
    hrem: '/circuit-schematics/hrem.png',
    zr7_taillight: '/circuit-schematics/zr7_taillight.png',
  })
})

it('returns a completed SSE run with role evidence, candidate judgement, and datasheet evidence', async () => {
  const request = await freshDummy()
  const thread = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  const response = await request(`/api/threads/${thread.id}/runs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: 'D1을 SS34L로 바꿔도 되나요?', target_ref: 'D1', conditions: '' }),
  })
  const stream = await response.text()
  expect(response.headers.get('Content-Type')).toContain('text/event-stream')
  expect(stream).toContain('event: run_started')
  expect(stream).toContain('event: status')
  expect(stream).toContain('event: completed')
  expect(stream).toContain('D1.A → Net-(S1-S)')
  expect(stream).toContain('ROLE_SUFFICIENT')
  expect(stream).toContain('SS34L SERIES_C2103.pdf')
  expect(stream).toContain('https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf')
  expect(stream).toContain('"outline_page":4')

  const run = await json(await request('/api/runs/dummy-run')) as unknown as RunDto
  expect(run.message_id).toBe(9)
  expect(run.result.price_parts).toEqual(['SS34L'])
  expect(run.result.evidence[0]).toMatchObject({ document: 'SS34L SERIES_C2103.pdf', page: 1, row: 'VRRM' })
  const judgement = run.result.judgement as { results: { checks: unknown[]; package_citation?: unknown }[] }
  expect(judgement.results[0].checks).toEqual(expect.arrayContaining([
    expect.objectContaining({ citation: expect.objectContaining({ page: 1, outline_page: 4 }) }),
  ]))
  expect(judgement.results[0].package_citation).toMatchObject({ page: 4, outline_page: 4 })
})

it('provides realistic requirement and candidate values for the approval demo', async () => {
  const request = await freshDummy()
  const thread = await json(await request('/api/projects/1/threads', { method: 'POST' }))
  await request(`/api/threads/${thread.id}/runs`, { method: 'POST', body: JSON.stringify({ question: 'D1 대체 검토', target_ref: 'D1' }) })
  const run = await json(await request('/api/runs/dummy-run')) as unknown as RunDto
  expect(run.result.judgement).toMatchObject({ results: [{ checks: [
    { code: 'VRRM', op: '>=', threshold: 15, value: 40, unit: 'V', result: 'pass' },
    { code: 'IF_AV', op: '>=', threshold: 1.43, value: 3, unit: 'A', result: 'pass' },
  ] }] })
})

it('keeps price data transient while approval, quote, and approved-case state changes', async () => {
  const request = await freshDummy()
  const thread = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  await request(`/api/threads/${thread.id}/runs`, { method: 'POST', body: JSON.stringify({ question: 'D1 대체 검토', target_ref: 'D1' }) })
  const approvalResponse = await request('/api/messages/9/approvals', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' }),
  })
  expect(approvalResponse.status).toBe(201)
  const approval = await json(approvalResponse) as { id: number; case_id: number }

  const cases = await json(await request('/api/approved-cases')) as unknown as { candidate_part: string; verdict: string }[]
  expect(cases).toEqual([expect.objectContaining({ candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' })])

  const prices = await json(await request('/api/prices?parts=SS34L')) as { available: boolean; parts: unknown[] }
  expect(prices).toMatchObject({ available: true })
  expect(prices.parts).toHaveLength(1)

  const quoteResponse = await request(`/api/approvals/${approval.id}/quotes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quantity: 2 }),
  })
  expect(quoteResponse.status).toBe(201)
  const quote = await json(quoteResponse)
  expect(quote).toEqual({ id: 5, approval_id: approval.id, part_number: 'SS34L', quantity: 2 })
  expect(quote).not.toHaveProperty('price')
  expect(quote).not.toHaveProperty('availability')
  expect(await json(await request('/api/projects/1/quotes'))).toEqual([quote])
  const projects = await json(await request('/api/projects')) as unknown as { id: number }[]
  const otherProject = projects.find(item => item.id !== 1)!
  expect(await json(await request(`/api/projects/${otherProject.id}/quotes`))).toEqual([])
  expect((await request('/api/projects/999999/quotes')).status).toBe(404)

  expect((await request(`/api/approved-cases/${approval.case_id}`, { method: 'DELETE' })).status).toBe(204)
  expect(await json(await request('/api/approved-cases'))).toEqual([])
  expect(await json(await request('/api/projects/1/quotes'))).toEqual([quote])
})

it('removes approval and quote state when its conversation is deleted', async () => {
  const request = await freshDummy()
  const thread = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  await request(`/api/threads/${thread.id}/runs`, { method: 'POST', body: JSON.stringify({ question: 'D1 대체 검토', target_ref: 'D1' }) })
  const approval = await json(await request('/api/messages/9/approvals', {
    method: 'POST', body: JSON.stringify({ candidate_part: 'SS34L', verdict: 'ROLE_SUFFICIENT' }),
  })) as { id: number }
  expect((await request(`/api/approvals/${approval.id}/quotes`, { method: 'POST', body: JSON.stringify({ quantity: 2 }) })).status).toBe(201)
  expect((await request(`/api/threads/${thread.id}`, { method: 'DELETE' })).status).toBe(204)
  expect((await request(`/api/threads/${thread.id}`)).status).toBe(404)
  expect(await json(await request('/api/approved-cases'))).toEqual([])
  expect(await json(await request('/api/projects/1/quotes'))).toEqual([])
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

it('filters and pages the demo catalog like the real API', async () => {
  const request = await freshDummy()
  const response = await request('/api/demo-circuits?q=breadboard&offset=0&limit=1')
  expect(await json(response)).toEqual([
    expect.objectContaining({ id: 'breadboard_supply', name: 'SparkFun Breadboard Power Supply 5V/3.3V' }),
  ])
})

it('creates demo projects through the same POST contract as the real API', async () => {
  const request = await freshDummy()
  const response = await request('/api/projects?allow_duplicate=true', {
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

it('warns about duplicate demo content and does not silently create another project', async () => {
  const request = await freshDummy()
  const before = await json(await request('/api/projects'))
  const response = await request('/api/projects', { method: 'POST', body: JSON.stringify({ demo_id: 'breadboard_supply', name: '다른 이름' }) })
  expect(response.status).toBe(409)
  expect(await json(response)).toMatchObject({ details: { duplicates: [expect.objectContaining({ id: 1, matches: ['netlist'] })] } })
  expect(await json(await request('/api/projects'))).toEqual(before)
})

it('never substitutes demo components for an uploaded netlist', async () => {
  const request = await freshDummy()
  const before = await json(await request('/api/projects'))
  const body = new FormData(); body.append('name', '업로드 회로'); body.append('file', new File(['(export (components))'], 'board.net'))
  const response = await request('/api/projects/upload', { method: 'POST', body })
  expect(response.status).toBe(503)
  expect(await json(response)).toMatchObject({ error: { code: 'UNAVAILABLE', message: expect.stringContaining('실제 API 서버') } })
  expect(await json(await request('/api/projects'))).toEqual(before)
})

it('deletes only one conversation and its runs without reusing surviving IDs', async () => {
  const request = await freshDummy()
  const first = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  const second = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  await request(`/api/threads/${first.id}/runs`, { method: 'POST', body: JSON.stringify({ question: '질문', target_ref: 'D1' }) })
  expect((await request(`/api/threads/${first.id}`, { method: 'DELETE' })).status).toBe(204)
  expect((await request('/api/runs/dummy-run')).status).toBe(404)
  expect((await request(`/api/threads/${first.id}`)).status).toBe(404)
  expect((await request(`/api/threads/${second.id}`)).status).toBe(200)
  const third = await json(await request('/api/projects/1/threads', { method: 'POST' })) as { id: string }
  expect(third.id).not.toBe(second.id)
})
it('provides the candidate list contract for the multi-sheet schematic preview', async () => {
  const request = await freshDummy()
  const response = await request('/api/external-circuits/schematics?q=attiny85')
  expect(response.status).toBe(200)
  expect(await json(response)).toMatchObject({ choices: [], images: [{ sheet: 0 }, { sheet: 1 }] })
})
