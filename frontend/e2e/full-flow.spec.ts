import { expect, test } from '@playwright/test'

test('completes judgement, transient price, approval, price-free quote, and case deletion', async ({ page }) => {
  let caseExists = false
  const project = { id: 1, name: '전체 흐름', source_kind: 'upload', demo_id: null, created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
    connections: { parts: [{ ref: 'D1', value: '1N5819', footprint: 'SOD-123' }], nets: [] } }
  const result = { answer: 'SS34는 역할상 충분합니다. [7]', status: 'completed', stage: '완료', question_type: 'candidate_judge',
    evidence: [{ document: 'SS34.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }],
    judgement: { kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
      results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: false }] }, price_parts: ['SS34'], refusal: '', interrupt: {}, request_id: 'req-e2e' }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [] })
    if (path === '/api/projects') return route.fulfill({ json: [{ ...project, connections: undefined }] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads' && request.method() === 'GET') return route.fulfill({ json: [] })
    if (path === '/api/projects/1/threads') return route.fulfill({ status: 201, json: { id: 'thread-1', project_id: 1 } })
    if (path === '/api/threads/thread-1/runs') return route.fulfill({ contentType: 'text/event-stream', body: `event: run_started\ndata: {"run_id":"run-1"}\n\nevent: completed\ndata: ${JSON.stringify(result)}\n\n` })
    if (path === '/api/runs/run-1') return route.fulfill({ json: { id: 'run-1', thread_id: 'thread-1', message_id: 9, result } })
    if (path === '/api/messages/9/approvals') {
      expect(request.postDataJSON()).toEqual({ candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' })
      caseExists = true
      return route.fulfill({ status: 201, json: { id: 3, message_id: 9, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT', case_id: 4 } })
    }
    if (path === '/api/approved-cases' && request.method() === 'GET') return route.fulfill({ json: caseExists ? [{ id: 4, approval_id: 3, candidate_part: 'SS34', verdict: 'ROLE_SUFFICIENT' }] : [] })
    if (path === '/api/approved-cases/4') { caseExists = false; return route.fulfill({ status: 204, body: '' }) }
    if (path === '/api/approvals/3/quotes') {
      expect(request.postDataJSON()).toEqual({ quantity: 2 })
      return route.fulfill({ status: 201, json: { id: 5, approval_id: 3, part_number: 'SS34', quantity: 2 } })
    }
    if (path === '/api/prices') return route.fulfill({ json: { available: true, source: 'Mouser Electronics', fetched_at: '2026-11-09T00:00:00Z', parts: [{ part_number: 'SS34', manufacturer: 'Maker', availability: '10', product_url: null, price_breaks: [{ quantity: 1, price: '1.23', currency: 'USD' }] }] } })
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '없음', request_id: 'req-e2e' } } })
  })
  await page.goto('/app?projectId=1')
  await page.getByRole('button', { name: /^프로젝트 선택:/ }).click()
  await page.getByRole('dialog', { name: '내 프로젝트' }).getByLabel('분석할 부품', { exact: true }).selectOption('D1')
  await page.getByLabel('질문', { exact: true }).fill('D1을 SS34로 바꿔도 되나요?')
  await page.getByRole('button', { name: '질문 전송' }).click()
  await page.getByRole('group', { name: '분석 결과 메뉴' }).getByRole('button', { name: '후보 비교' }).click()
  await page.getByRole('combobox', { name: '자료 열기' }).selectOption('judgement')
  await expect(page.getByText('같은 동작은 보장하지 않습니다.')).toBeVisible()
  await page.getByRole('group', { name: '분석 결과 메뉴' }).getByRole('button', { name: '승인·견적' }).click()
  await page.getByLabel('승인할 후보').selectOption('0')
  await page.getByRole('button', { name: '판정 승인 확인' }).click()
  await expect(page.getByText('SS34 후보의 “역할상 충분” 판정을 승인할까요?')).toBeVisible()
  await page.getByRole('button', { name: '확인 후 승인' }).click()
  await expect(page.getByText('SS34 판정을 승인했습니다.')).toBeVisible()
  await expect(page.getByText('SS34 · ROLE_SUFFICIENT')).toBeVisible()
  await page.getByRole('button', { name: '견적 열기' }).click()
  await page.getByRole('button', { name: '가격·재고 조회' }).last().click()
  await expect(page.getByText('1.23 USD', { exact: true })).toBeVisible()
  await page.getByLabel('수량').fill('2')
  await expect(page.getByText('2개 × 1.23 USD = 2.46 USD', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '수량만 견적에 저장' }).click()
  await expect(page.getByText('SS34 2개 견적을 저장했습니다. 가격은 저장하지 않았습니다.')).toBeVisible()
  await page.getByRole('button', { name: '닫기', exact: true }).click()
  await page.getByRole('button', { name: '사례 삭제' }).click()
  await page.getByRole('button', { name: '삭제 확인' }).click()
  await expect(page.getByText('저장된 승인 사례가 없습니다.')).toBeVisible()
})
