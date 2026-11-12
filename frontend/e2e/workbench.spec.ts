import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'

test('uses the Google entry without demo access in a production build', async ({ page }, testInfo) => {
  test.skip(process.env.SOJA_E2E_MODE !== 'production', 'Run against the built Vite preview')
  const paths: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    paths.push(path)
    if (path === '/api/auth/google/status' || path === '/api/auth/demo') return route.fulfill({ json: { enabled: true } })
    if (path === '/api/auth/google/start') return route.fulfill({ status: 303, headers: { location: '/login?google=error' }, body: '' })
    return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'req-production-login' } } })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  const google = page.getByRole('link', { name: 'Google로 계속하기', exact: true })
  await expect(google).toBeVisible()
  await expect(google).toHaveAttribute('href', '/api/auth/google/start')
  await expect(page.getByRole('group', { name: '데모 로그인' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /데모 사용자/ })).toHaveCount(0)
  expect(paths).not.toContain('/api/auth/demo')
  await expect.poll(() => page.getByRole('img', { name: 'SOJAFIT 브랜드 로고' }).evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await page.screenshot({ path: testInfo.outputPath('production-google-login.png'), fullPage: true })
  await google.click()
  await expect(page).toHaveURL(/\/login\?google=error$/)
  await expect(page.getByRole('alert')).toContainText('Google 로그인을 확인할 수 없습니다.')
  expect(paths.filter(path => path === '/api/auth/google/start')).toHaveLength(1)
  expect(paths).not.toContain('/api/auth/demo-login')
})

test.describe('recovery mock', () => {
  const pause = { missing: ['v_in_max'], role_choices: [], question: '최대 입력 전압을 알려주세요.' }
  const result = (status: string) => ({ id: 'mock-run', thread_id: 'mock-thread', message_id: null,
    result: { status, stage: '입력 확인', answer: status === 'completed' ? '복구된 완료 답변' : status === 'refused' ? '복구된 거절 답변' : '',
      evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: status === 'requires_input' ? pause : {}, request_id: 'req-recovery' } })
  const stream = (route: Route, ...frames: [string, object][]) => route.fulfill({ contentType: 'text/event-stream',
    body: frames.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('') })
  async function open(page: Page, overrides: Record<string, (route: Route) => Promise<void>>, saved = false) {
    const calls: string[] = []
    const project = { id: 1, name: '복구 시험 회로', source_kind: 'upload', demo_id: null,
      connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } }
    const handlers: Record<string, (route: Route) => Promise<void>> = {
      'GET /api/auth/me': route => route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } }),
      'GET /api/projects': route => route.fulfill({ json: [project] }),
      'GET /api/projects/1': route => route.fulfill({ json: project }),
      'GET /api/projects/1/threads': route => route.fulfill({ json: [{ id: 'mock-thread', project_id: 1, title: '복구 시험 대화', status: 'running' }] }),
      'POST /api/projects/1/threads': route => route.fulfill({ status: 201, json: { id: 'mock-thread', project_id: 1 } }),
      'GET /api/threads/mock-thread': route => route.fulfill({ json: { id: 'mock-thread', project_id: 1, title: '복구 시험 대화',
        target_ref: 'D1', target_locked: true, latest_run: { id: 'mock-run', status: 'running', message_id: null }, messages: [], next_before_message_id: null } }),
      'GET /api/judge/roles': route => route.fulfill({ json: [] }),
      'GET /api/demo-circuits': route => route.fulfill({ json: [] }),
      ...overrides,
    }
    await page.route(/^https?:\/\/[^/]+\/api\//, route => {
      const key = `${route.request().method()} ${new URL(route.request().url()).pathname}`
      calls.push(key)
      return handlers[key]?.(route) ?? route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '시험 경로 없음', request_id: 'req-mock' } } })
    })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`/app?projectId=1&targetRef=D1${saved ? '&threadId=mock-thread' : ''}`)
    return calls
  }
  async function ask(page: Page) {
    await page.getByLabel('질문', { exact: true }).fill('연결 복구 시험')
    await page.getByRole('button', { name: '질문 전송', exact: true }).click()
  }
  const submissions = (calls: string[]) => calls.filter(call => /^POST .*\/(runs|resume)$/.test(call))

  test('shows a thread creation error once and retries only when the user sends again', async ({ page }) => {
    let attempts = 0
    const calls = await open(page, {
      'POST /api/projects/1/threads': route => ++attempts === 1
        ? route.fulfill({ status: 503, body: '', headers: { 'X-Request-ID': 'req-create-thread' } })
        : route.fulfill({ status: 201, json: { id: 'mock-thread', project_id: 1 } }),
      'POST /api/threads/mock-thread/runs': route => stream(route, ['run_started', { run_id: 'mock-run' }], ['completed', result('completed').result]),
    })
    await ask(page)
    await expect(page.getByRole('alert')).toContainText('요청 ID: req-create-thread')
    await expect(page.getByRole('alert')).toHaveCount(1)
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('연결 복구 시험')
    expect(attempts).toBe(1)
    expect(submissions(calls)).toEqual([])
    await page.getByRole('button', { name: '질문 전송', exact: true }).click()
    await expect(page.getByText('복구된 완료 답변', { exact: true })).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect(attempts).toBe(2)
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs'])
  })

  for (const status of ['completed', 'refused', 'requires_input']) test(`restores ${status} after a disconnected stream without reposting`, async ({ page }) => {
    const calls = await open(page, {
      'POST /api/threads/mock-thread/runs': route => stream(route, ['run_started', { run_id: 'mock-run' }]),
      'GET /api/runs/mock-run': route => route.fulfill({ json: result(status) }),
    })
    await ask(page)
    if (status === 'requires_input') await expect(page.getByLabel('입력 전원 최대 전압', { exact: true })).toBeVisible()
    else await expect(page.getByText(status === 'completed' ? '복구된 완료 답변' : '복구된 거절 답변', { exact: true })).toBeVisible()
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs'])
    expect(calls.filter(call => call === 'GET /api/runs/mock-run')).toHaveLength(1)
  })

  test('stops after 30 running reads and manually recovers without another analysis', async ({ page }, testInfo) => {
    test.setTimeout(60_000)
    let complete = false
    const calls = await open(page, {
      'POST /api/threads/mock-thread/runs': route => stream(route, ['run_started', { run_id: 'mock-run' }]),
      'GET /api/runs/mock-run': route => route.fulfill({ json: result('running') }),
      'POST /api/runs/mock-run/recover': route => route.fulfill({ json: result(complete ? 'completed' : 'running') }),
    })
    await ask(page)
    const refresh = page.getByRole('button', { name: '실행 상태 확인', exact: true })
    await expect(refresh).toBeVisible({ timeout: 45_000 })
    await expect(page.getByRole('alert')).toContainText('요청 ID: req-recovery')
    await expect(page.locator('.status-card')).toHaveCount(0)
    await expect(page.getByText('아직 실행 상태를 확정할 수 없습니다.', { exact: false })).toHaveCount(1)
    expect(calls.filter(call => call === 'GET /api/runs/mock-run')).toHaveLength(30)
    expect(calls.filter(call => call === 'POST /api/runs/mock-run/recover')).toHaveLength(1)
    await page.waitForTimeout(1500)
    expect(calls.filter(call => call === 'GET /api/runs/mock-run')).toHaveLength(30)
    await page.screenshot({ path: testInfo.outputPath('pending-recovery.png'), fullPage: true })
    complete = true
    await refresh.click()
    await expect(page.getByText('복구된 완료 답변', { exact: true })).toBeVisible()
    expect(calls.filter(call => call === 'POST /api/runs/mock-run/recover')).toHaveLength(2)
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs'])
  })

  for (const active of [false, true]) test(`saved refresh preserves active=${active} without analysis or resume`, async ({ page }) => {
    let state = 'running'
    const calls = await open(page, {
      'GET /api/runs/mock-run': route => route.fulfill({ json: result(state) }),
      'POST /api/runs/mock-run/recover': route => { state = active ? 'running' : 'failed'; return route.fulfill({ json: result(state) }) },
      'GET /api/projects/1/threads': route => route.fulfill({ json: [{ id: 'mock-thread', project_id: 1, title: '복구 시험 대화', status: state }] }),
    }, true)
    await expect(page.getByRole('button', { name: '실행 상태 새로고침', exact: true })).toBeVisible()
    const listReads = calls.filter(call => call === 'GET /api/projects/1/threads').length
    await page.getByRole('button', { name: '실행 상태 새로고침', exact: true }).click()
    await expect.poll(() => calls.filter(call => call === 'GET /api/projects/1/threads').length).toBeGreaterThan(listReads)
    if (active) {
      await expect(page.getByRole('button', { name: '실행 상태 새로고침', exact: true })).toBeEnabled()
      await expect(page.getByText('이 실행은 중단된 상태입니다.', { exact: false })).toHaveCount(0)
    } else {
      await expect(page.getByText('이 실행은 중단된 상태입니다.', { exact: false })).toBeVisible()
      await expect(page.getByTitle('복구 시험 대화', { exact: true })).toHaveAttribute('aria-busy', 'false')
    }
    expect(calls.filter(call => call.startsWith('POST '))).toEqual(['POST /api/runs/mock-run/recover'])
  })

  for (const system of [false, true]) test(`resume error system=${system} keeps only a valid waiting checkpoint`, async ({ page }, testInfo) => {
    const answers: unknown[] = []
    const calls = await open(page, {
      'POST /api/threads/mock-thread/runs': route => stream(route, ['run_started', { run_id: 'mock-run' }], ['requires_input', result('requires_input').result]),
      'GET /api/runs/mock-run': route => route.fulfill({ json: result(system ? 'failed' : 'requires_input') }),
      'POST /api/runs/mock-run/resume': route => {
        answers.push(route.request().postDataJSON())
        if (system) return stream(route, ['failed', { ...result('failed').result, error: { code: 'UNAVAILABLE', message: '시스템 시험 오류' } }])
        if (answers.length === 1) return route.fulfill({ status: 422, json: { error: { code: 'VALIDATION_ERROR', message: '전압 입력을 확인하세요.', request_id: 'req-input' } } })
        return stream(route, ['completed', result('completed').result])
      },
    })
    await ask(page)
    await page.getByLabel('입력 전원 최대 전압', { exact: true }).fill('잘못된 값')
    await page.getByRole('button', { name: '같은 실행 계속하기', exact: true }).click()
    if (system) {
      await expect(page.getByRole('alert')).toContainText('시스템 시험 오류 (요청 ID: req-recovery)')
      await expect(page.getByLabel('입력 전원 최대 전압', { exact: true })).toHaveCount(0)
      expect(answers).toHaveLength(1)
    } else {
      await expect(page.getByRole('alert')).toContainText('전압 입력을 확인하세요. (요청 ID: req-input)')
      await expect(page.getByLabel('입력 전원 최대 전압', { exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath('resume-error-form.png'), fullPage: true })
      await page.getByLabel('입력 전원 최대 전압', { exact: true }).fill('12 V')
      await page.getByRole('button', { name: '같은 실행 계속하기', exact: true }).click()
      await expect(page.getByText('복구된 완료 답변', { exact: true })).toBeVisible()
      expect(answers).toEqual([{ answers: { v_in_max: '잘못된 값' } }, { answers: { v_in_max: '12 V' } }])
    }
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs', ...answers.map(() => 'POST /api/runs/mock-run/resume')])
  })

  for (const surface of ['project', 'stream']) {
    test(`HTML 401 expires the session on ${surface}`, async ({ page }) => {
      let expired = false
      const denied = (route: Route) => { expired = true; return route.fulfill({ status: 401, contentType: 'text/html', headers: { 'X-Request-ID': 'req-html-401' }, body: '<html>PRIVATE_GATEWAY</html>' }) }
      await open(page, {
        'GET /api/auth/me': route => route.fulfill({ json: expired ? null : { user_id: 7, email: 'user@example.test', role: 'user' } }),
        [surface === 'project' ? 'GET /api/projects/1' : 'POST /api/threads/mock-thread/runs']: denied,
      })
      if (surface === 'stream') await ask(page)
      await expect(page).toHaveURL(/\/login$/)
      await expect(page.getByRole('heading', { name: 'SojaFit에 로그인', exact: true })).toBeVisible()
      await expect(page.getByText('user@example.test', { exact: true })).toHaveCount(0)
      await expect(page.getByText('PRIVATE_GATEWAY', { exact: false })).toHaveCount(0)
    })
    for (const body of ['', '{"error":broken']) test(`normalizes ${body ? 'broken JSON' : 'empty 503'} on ${surface} with header ID`, async ({ page }, testInfo) => {
      await open(page, {
        [surface === 'project' ? 'GET /api/projects/1' : 'POST /api/threads/mock-thread/runs']: route => route.fulfill({ status: 503, contentType: 'application/json', headers: { 'X-Request-ID': 'req-proxy-503' }, body }),
      })
      if (surface === 'stream') await ask(page)
      await expect(page.getByRole('alert')).toContainText('서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요. (요청 ID: req-proxy-503)')
      await expect(page.getByRole('alert')).not.toContainText(/SyntaxError|Unexpected token|broken/)
      if (surface === 'stream') {
        await expect(page.locator('.status-card')).toHaveCount(0)
        await expect(page.getByText('서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', { exact: false })).toHaveCount(1)
      }
      if (surface === 'stream' && !body) await page.screenshot({ path: testInfo.outputPath('safe-api-error.png'), fullPage: true })
    })
  }
})

test('shows processing on the session and send icon until the reply finishes', async ({ page }, testInfo) => {
  let releaseCreation!: () => void
  const creation = new Promise<void>(resolve => { releaseCreation = resolve })
  let created = false, completed = false
  const project = { id: 1, name: '진행 표시 시험', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, role: 'user', email: 'user@example.test' } })
    if (path === '/api/projects') return route.fulfill({ json: [project] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads' && route.request().method() === 'POST') {
      await creation; created = true
      return route.fulfill({ status: 201, json: { id: 'working-thread', project_id: 1 } })
    }
    if (path === '/api/projects/1/threads') return route.fulfill({ json: created ? [{ id: 'working-thread', title: '진행 표시 확인', status: 'running' }] : [] })
    if (path === '/api/threads/working-thread/runs') return route.fulfill({ contentType: 'text/event-stream', body: 'event: run_started\ndata: {"run_id":"working-run"}\n\nevent: status\ndata: {"stage":"문서 근거 확인"}\n\n' })
    if (path === '/api/runs/working-run') return route.fulfill({ json: { id: 'working-run', thread_id: 'working-thread', message_id: completed ? 2 : null,
      result: { status: completed ? 'completed' : 'running', stage: '문서 근거 확인', answer: '시험 응답이 완료됐습니다.', evidence: [], judgement: {}, interrupt: {} } } })
    return route.fulfill({ json: [] })
  })
  try {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/app?projectId=1&targetRef=D1')
    await page.getByLabel('질문', { exact: true }).fill('진행 표시 확인')
    const send = page.getByRole('button', { name: '질문 전송', exact: true })
    await send.click()
    await expect(send).toBeDisabled()
    await expect(send).toHaveAttribute('aria-busy', 'true')
    await expect(send.locator('.processing-icon')).toBeVisible()
    releaseCreation()
    const stop = page.getByRole('button', { name: '응답 수신 중단', exact: true })
    const session = page.getByTitle('진행 표시 확인', { exact: true })
    await expect(stop).toHaveAttribute('aria-busy', 'true')
    await expect(stop.locator('.processing-icon rect')).toBeVisible()
    await expect(session).toHaveAttribute('aria-busy', 'true')
    await expect(session.locator('.processing-icon')).toBeVisible()
    await expect(session.locator('.workspace-current-dot')).toHaveCount(0)
    await expect(session.locator('.processing-ring')).toHaveCSS('animation-name', 'processing-spin')
    await page.screenshot({ path: testInfo.outputPath('processing.png'), fullPage: true })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(session.locator('.processing-ring')).toHaveCSS('animation-name', 'none')
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    completed = true
    await expect(page.getByText('시험 응답이 완료됐습니다.', { exact: true })).toBeVisible()
    await expect(session).toHaveAttribute('aria-busy', 'false')
    await expect(session.locator('.processing-icon')).toHaveCount(0)
    await expect(session.locator('.workspace-current-dot')).toBeVisible()
    await expect(page.getByRole('button', { name: '질문 전송', exact: true }).locator('.processing-icon')).toHaveCount(0)
  } finally { releaseCreation() }
})

test('creates a project then selects its target in the header dialog before chatting', async ({ page }) => {
  let created = false
  const writes: string[] = []
  const project = { id: 2, name: '새 회로', source_kind: 'demo', demo_id: 'breadboard_supply', created_at: '', updated_at: '',
    connections: { parts: [{ ref: 'D1', value: '1N4001' }, { ref: 'C1', value: '100uF' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects' && route.request().method() === 'POST') { created = true; return route.fulfill({ status: 201, json: project }) }
    if (path === '/api/projects') return route.fulfill({ json: created ? [project] : [] })
    if (path === '/api/projects/2') return route.fulfill({ json: project })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [{ id: project.demo_id, name: '데모 회로' }] })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  await page.getByRole('button', { name: '프로젝트 추가', exact: true }).click()
  await page.getByLabel('새 프로젝트 이름', { exact: true }).fill(project.name)
  await page.getByLabel('데모 회로', { exact: true }).selectOption(project.demo_id)
  await page.getByRole('button', { name: '데모로 만들기', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '내 프로젝트', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByLabel('분석할 부품')).toBeEnabled()
  await expect(dialog.getByRole('heading', { name: '내 프로젝트', exact: true })).toHaveCount(1)
  const projectList = dialog.getByRole('navigation', { name: '프로젝트 목록' })
  const settings = dialog.getByRole('region', { name: '선택 프로젝트 설정' })
  expect((await projectList.boundingBox())!.x).toBeLessThan((await settings.boundingBox())!.x)
  expect((await projectList.getByRole('heading').boundingBox())!.y).toBeLessThan((await projectList.getByRole('button', { name: project.name }).boundingBox())!.y)
  await expect(settings).toContainText('부품 2개 · 넷 0개')
  await expect(settings.getByRole('button', { name: '프로젝트 삭제', exact: true })).toBeVisible()
  await dialog.getByLabel('분석할 부품').selectOption('C1')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('button', { name: '프로젝트 선택: 새 회로' })).toContainText('C1 · 100uF')
  await expect(page.getByLabel('질문', { exact: true })).toBeEnabled()
  const conversation = page.getByRole('region', { name: '에이전트 대화' })
  await expect(conversation.getByRole('combobox')).toHaveCount(0)
  await expect(conversation.getByRole('heading')).toHaveCount(0)
  expect((await page.locator('.conversation-stream').boundingBox())!.height).toBeGreaterThan(300)
  expect((await page.locator('.composer').boundingBox())!.height).toBeLessThan(160)
  expect(writes).toEqual(['/api/projects'])
})

test('manages pinned conversations and confirmed deletions on desktop', async ({ page }) => {
  const first = '11111111-1111-4111-8111-111111111111', pinned = '22222222-2222-4222-8222-222222222222'
  let records = [{ id: first, title: '현재 기록', status: 'completed' }, { id: pinned, title: '고정 대상', status: 'completed' }, { id: '33333333-3333-4333-8333-333333333333', title: '실행 중 기록', status: 'running' }]
  let fail = true
  const deleted: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: '대화 관리 시험' }] })
    if (path === '/api/projects/1') return route.fulfill({ json: { id: 1, name: '대화 관리 시험', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: 'SS34' }], nets: [] } } })
    if (path === '/api/projects/1/threads') return route.fulfill({ json: records.map(record => ({ ...record, project_id: 1 })) })
    if (route.request().method() === 'DELETE') {
      deleted.push(path)
      if (fail) return route.fulfill({ status: 409, json: { error: { code: 'CONFLICT', message: '분석 중인 대화입니다.', request_id: 'thread-delete-test' } } })
      records = records.filter(record => path !== `/api/threads/${record.id}`)
      return route.fulfill({ status: 204, body: '' })
    }
    if (path.startsWith('/api/threads/')) return route.fulfill({ json: { id: path.split('/').pop(), project_id: 1, target_ref: 'D1', latest_run: null, messages: [], next_before_message_id: null } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app?projectId=1&targetRef=D1')
  const row = page.locator('.workspace-session-list > li').filter({ has: page.getByTitle('고정 대상', { exact: true }) })
  await row.hover()
  await row.getByRole('button', { name: '대화 고정', exact: true }).click()
  await expect(page.locator('.workspace-session-list > li').first()).toContainText('고정 대상')
  await page.reload()
  await row.hover()
  await expect(row.getByRole('button', { name: '대화 고정 해제', exact: true })).toBeVisible()
  await row.getByRole('button', { name: '대화 고정 해제', exact: true }).click()
  await expect(page.locator('.workspace-session-list > li').first()).toContainText('현재 기록')
  await expect(row.getByRole('button', { name: '대화 고정', exact: true })).toBeFocused()
  await row.getByRole('button', { name: '대화 고정', exact: true }).click()
  await page.getByLabel('질문', { exact: true }).fill('유지할 초안')
  await row.hover()
  await row.getByRole('button', { name: '대화 삭제', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '대화 삭제', exact: true })
  await expect(dialog).toContainText('연결된 승인·견적·사례')
  expect(deleted).toEqual([])
  await dialog.getByRole('button', { name: '취소', exact: true }).press('Escape')
  await expect(page.getByTitle('고정 대상', { exact: true })).toBeFocused()
  await row.getByRole('button', { name: '대화 삭제', exact: true }).click()
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('분석 중인 대화입니다.')
  await expect(row).toBeVisible()
  fail = false
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(row).toHaveCount(0)
  await expect(page.getByLabel('질문', { exact: true })).toHaveValue('유지할 초안')
  await page.getByTitle('현재 기록', { exact: true }).click()
  const current = page.locator('.workspace-session-list > li').filter({ has: page.getByTitle('현재 기록', { exact: true }) })
  await current.hover()
  await current.getByRole('button', { name: '대화 삭제', exact: true }).click()
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(page.getByLabel('질문', { exact: true })).toHaveValue('')
  expect(page.url()).not.toContain('threadId=')
  const running = page.locator('.workspace-session-list > li').filter({ has: page.getByTitle('실행 중 기록', { exact: true }) })
  await running.hover()
  await expect(running.getByRole('button', { name: '대화 삭제', exact: true })).toBeDisabled()
  expect(deleted).toEqual([`/api/threads/${pinned}`, `/api/threads/${pinned}`, `/api/threads/${first}`])
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('sojafit-pinned-threads:7:1') ?? '[]'))).toEqual([])
})

test('collapses owned projects after two and clears the list when another account logs in', async ({ page }) => {
  let userId: number | null = 7
  const projects = [31, 22, 13].map((id, index) => ({ id, name: `A 프로젝트 ${index + 1}`, source_kind: 'upload', demo_id: null, created_at: '', updated_at: '' }))
  const other = { ...projects[0], id: 40, name: 'B 프로젝트' }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/logout') { userId = null; return route.fulfill({ status: 204, body: '' }) }
    if (path === '/api/auth/login') { userId = 8; return route.fulfill({ json: { user_id: 8 } }) }
    if (path === '/api/auth/me') return userId === null
      ? route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.' } } })
      : route.fulfill({ json: { user_id: userId, email: userId === 7 ? 'a@example.test' : 'b@example.test', role: 'user' } })
    if (path === '/api/auth/demo' || path === '/api/auth/google/status') return route.fulfill({ json: { enabled: false } })
    if (path === '/api/projects') return route.fulfill({ json: userId === 7 ? projects : [other] })
    if (/^\/api\/projects\/\d+$/.test(path)) return route.fulfill({ json: { ...projects.find(project => path.endsWith(`/${project.id}`)), connections: { parts: [], nets: [] } } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  const list = page.getByRole('list', { name: '저장된 프로젝트' })
  await expect(list.getByRole('button')).toHaveText(['A 프로젝트 1', 'A 프로젝트 2'])
  await page.getByRole('button', { name: '더보기 (1)' }).click()
  await expect(list.getByRole('button')).toHaveText(projects.map(project => project.name))
  await list.getByRole('button', { name: 'A 프로젝트 3', exact: true }).click()
  await expect(list.getByRole('button', { name: 'A 프로젝트 3', exact: true })).toHaveAttribute('aria-current', 'true')
  await page.getByRole('button', { name: '접기', exact: true }).click()
  await expect(list.getByRole('button')).toHaveCount(2)
  await page.getByRole('button', { name: 'a@example.test', exact: true }).click()
  await page.getByRole('menuitem', { name: '로그아웃', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'SojaFit에 로그인' })).toBeVisible()
  await expect.poll(() => page.getByRole('img', { name: 'SOJAFIT', exact: true }).evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await page.getByLabel('이메일', { exact: true }).fill('b@example.test')
  await page.getByLabel('비밀번호', { exact: true }).fill('synthetic-valid')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await expect(list.getByRole('button')).toHaveText(['B 프로젝트'])
  await expect(page.getByRole('button', { name: /더보기/ })).toHaveCount(0)
})

test('connects the new public landing and login to the existing session API and new workspace', async ({ page }, testInfo) => {
  let signedIn = false
  const submissions: unknown[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/login') {
      const body = route.request().postDataJSON()
      submissions.push(body)
      if (body.password === 'synthetic-valid') { signedIn = true; return route.fulfill({ json: { user_id: 7 } }) }
    }
    if (path === '/api/auth/me' && signedIn) return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/auth/google/status' || path === '/api/auth/demo') return route.fulfill({ json: { enabled: false } })
    if (path.startsWith('/api/auth/')) return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인을 확인해 주세요.', request_id: 'req-login-test' } } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await page.getByRole('link', { name: '회로 검토 시작', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'SojaFit에 로그인' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /회로를 이해하고/ })).toBeVisible()
  const brand = page.getByRole('img', { name: 'SOJAFIT 브랜드 로고', exact: true })
  await expect.poll(() => brand.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  expect((await brand.boundingBox())!.width).toBeGreaterThan(400)
  await expect(page.locator('.public-auth-story .public-circuit')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('login-brand.png'), fullPage: true })
  await page.getByLabel('이메일', { exact: true }).fill('user@example.test')
  await page.getByLabel('비밀번호', { exact: true }).fill('synthetic-invalid')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('req-login-test')
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveValue('')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.getByLabel('비밀번호', { exact: true }).fill('synthetic-valid')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'SojaFit 에이전트' })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '작업 메뉴 펼치기' }).click()
  await expect(page.getByRole('heading', { name: '현재 프로젝트', exact: true })).toBeVisible()
  await expect(page.getByText('저장된 프로젝트가 없습니다.', { exact: true })).toBeVisible()
  expect(submissions).toHaveLength(2)
})

test('shows a completed D5 judgement from a local fake backend', async ({ page }) => {
  const submissions: unknown[] = []
  const project = { id: 1, name: '데모 회로', source_kind: 'demo', demo_id: 'breadboard_supply', created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
    connections: { parts: [{ ref: 'D1', value: '1N5819', footprint: 'SOD-123' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [] })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: project.name, source_kind: 'demo', demo_id: project.demo_id, created_at: project.created_at, updated_at: project.updated_at }] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads' && route.request().method() === 'GET') return route.fulfill({ json: [] })
    if (path === '/api/projects/1/threads') return route.fulfill({ status: 201, json: { id: 'thread-1', project_id: 1 } })
    if (path === '/api/threads/thread-1/runs') {
      submissions.push(route.request().postDataJSON())
      const result = { answer: 'SS34는 역할상 충분합니다. [7]', status: 'completed', stage: '완료', question_type: 'candidate_judge',
        evidence: [{ document: 'SS34.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }],
        judgement: { kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
          results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: false }] }, price_parts: ['SS34'], refusal: '', interrupt: {}, request_id: 'req-e2e' }
      return route.fulfill({ contentType: 'text/event-stream', body: `event: run_started\ndata: {"run_id":"run-1"}\n\nevent: completed\ndata: ${JSON.stringify(result)}\n\n` })
    }
    return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: '없음', request_id: 'req-e2e' } } })
  })
  await page.goto('/app?projectId=1')
  await page.getByRole('button', { name: /^프로젝트 선택:/ }).click()
  await page.getByRole('dialog', { name: '내 프로젝트' }).getByLabel('분석할 부품', { exact: true }).selectOption('D1')
  await expect(page.getByRole('group', { name: '분석 결과 메뉴' })).toHaveCount(0)
  await page.setViewportSize({ width: 1440, height: 900 })
  const question = page.getByLabel('질문', { exact: true })
  await question.fill('D1을 SS34로 바꿔도 되나요?')
  await question.press('Shift+Enter')
  await expect(question).toHaveValue('D1을 SS34로 바꿔도 되나요?\n')
  expect(submissions).toHaveLength(0)
  await question.pressSequentially('입력 12 V입니다.')
  await question.press('Enter')
  await expect(page.getByRole('group', { name: '분석 결과 메뉴' }).getByRole('button')).toHaveText(['분석 현황', '후보 비교', '문서 근거', '승인·견적'])
  await page.getByRole('group', { name: '분석 결과 메뉴' }).getByRole('button', { name: '문서 근거' }).click()
  expect(submissions).toEqual([{ question: 'D1을 SS34로 바꿔도 되나요?\n입력 12 V입니다.', target_ref: 'D1', conditions: '' }])
  await page.getByRole('tab', { name: '근거' }).click()
  await expect(page.getByText('SS34.pdf')).toBeVisible()
  await page.getByRole('tab', { name: '후보 비교' }).click()
  await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
  await expect(page.getByText('같은 동작은 보장하지 않습니다.')).toBeVisible()
  const header = page.locator('.workbench-topbar')
  await expect(header.getByRole('button', { name: 'user@example.test', exact: true })).toBeVisible()
  await expect(header.getByText('판정 완료', { exact: true })).toHaveCount(0)
})

test('opens saved messages, selects their results and restores history after reload without POST', async ({ page }) => {
  const thread = '11111111-1111-4111-8111-111111111111'
  const paths: string[] = []
  const messages = [
    { id: 1, run_id: 'old-run', role: 'user', content: '이전 질문', created_at: '2026-11-11T00:00:00Z' },
    { id: 2, run_id: 'old-run', role: 'assistant', content: '이전 답변', created_at: '2026-11-11T00:00:01Z' },
    { id: 3, run_id: 'new-run', role: 'user', content: '최신 질문', created_at: '2026-11-11T00:00:02Z' },
    { id: 4, run_id: 'new-run', role: 'assistant', content: '최신 답변', created_at: '2026-11-11T00:00:03Z' },
  ]
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    paths.push(`${request.method()} ${path}`)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: '저장 기록 프로젝트' }] })
    if (path === '/api/projects/1') return route.fulfill({ json: { id: 1, name: '저장 기록 프로젝트', source_kind: 'upload', demo_id: null,
      connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } } })
    if (path === '/api/projects/1/threads') return route.fulfill({ json: [{ id: thread, project_id: 1, title: '저장 검토 기록', status: 'completed' }] })
    if (path === `/api/threads/${thread}`) return route.fulfill({ json: { id: thread, project_id: 1, title: '저장 검토 기록', target_ref: 'D1', target_locked: true,
      latest_run: { id: 'new-run', status: 'completed', message_id: 4 }, messages, next_before_message_id: null } })
    if (path.startsWith('/api/runs/')) {
      const old = path.endsWith('old-run')
      return route.fulfill({ json: { id: old ? 'old-run' : 'new-run', thread_id: thread, message_id: old ? 2 : 4,
        result: { status: 'completed', answer: old ? '이전 답변' : '최신 답변', evidence: [{ document: old ? 'old.pdf' : 'new.pdf', page: 2 }],
          judgement: { kind: 'judge', roles: [], results: [{ part: old ? '1N5819' : 'SS34', verdict: 'ROLE_SUFFICIENT' }], shown: [], unverified: [] }, interrupt: {}, profile_hints: [] } } })
    }
    return route.fulfill({ json: [] })
  })
  await page.goto('/app?projectId=1&targetRef=D1')
  await page.getByRole('button', { name: /저장 검토 기록/ }).click()
  await expect(page.getByRole('region', { name: '저장된 대화' })).toBeVisible()
  await expect(page.getByText('최신 질문', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'SS34 후보 선택', exact: true })).toBeVisible()
  const older = page.getByRole('article', { name: '2번 에이전트 메시지' })
  await expect(older.getByRole('group', { name: '분석 결과 메뉴' })).toHaveCount(0)
  await older.getByRole('button', { name: '분석 결과 확인', exact: true }).click()
  await older.getByRole('button', { name: '후보 비교', exact: true }).click()
  await expect(page.getByRole('button', { name: '1N5819 후보 선택', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('region', { name: '저장된 대화' })).toBeVisible()
  await expect(page.getByRole('button', { name: '정보 패널 펼치기' })).toBeVisible()
  await expect(page.getByRole('tablist', { name: '정보 보기' })).toHaveCount(0)
  await page.getByRole('article', { name: '4번 에이전트 메시지' }).getByRole('button', { name: '후보 비교', exact: true }).click()
  await page.getByRole('tab', { name: '후보 비교', exact: true }).click()
  await expect(page.getByRole('button', { name: 'SS34 후보 선택', exact: true })).toBeVisible()
  expect(paths.every(path => path.startsWith('GET '))).toBe(true)
})
