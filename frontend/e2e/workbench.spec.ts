import { expect, test } from '@playwright/test'

test('shows a completed judgement from a local fake backend', async ({ page }) => {
  const project = { id: 1, name: '데모 회로', source_kind: 'demo', demo_id: 'breadboard_supply', created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
    connections: { parts: [{ ref: 'D1', value: '1N5819', footprint: 'SOD-123' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, role: 'user' } })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [] })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: project.name, source_kind: 'demo', demo_id: project.demo_id, created_at: project.created_at, updated_at: project.updated_at }] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads' && route.request().method() === 'GET') return route.fulfill({ json: [] })
    if (path === '/api/projects/1/threads') return route.fulfill({ status: 201, json: { id: 'thread-1', project_id: 1 } })
    if (path === '/api/threads/thread-1/runs') {
      const result = { answer: 'SS34는 역할상 충분합니다. [7]', status: 'completed', stage: '완료', question_type: 'candidate_judge',
        evidence: [{ document: 'SS34.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }],
        judgement: { kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
          results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: false }] }, price_parts: ['SS34'], refusal: '', interrupt: {}, request_id: 'req-e2e' }
      return route.fulfill({ contentType: 'text/event-stream', body: `event: run_started\ndata: {"run_id":"run-1"}\n\nevent: completed\ndata: ${JSON.stringify(result)}\n\n` })
    }
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '없음', request_id: 'req-e2e' } } })
  })
  await page.goto('/app?projectId=1')
  await page.getByLabel('대상 부품').selectOption('D1')
  await page.getByLabel('질문').fill('D1을 SS34로 바꿔도 되나요?')
  await page.getByRole('button', { name: '질문하기' }).click()
  await expect(page.getByText('SS34.pdf')).toBeVisible()
  await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
  await expect(page.getByText('같은 동작은 보장하지 않습니다.')).toBeVisible()
})
