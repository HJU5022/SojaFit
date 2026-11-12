import { expect, test } from '@playwright/test'
import type { Page, Route } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

for (const kind of ['credentials', 'validation', 'origin', 'limited', 'server', 'network', 'html503', 'session'] as const) test(`explains login failures safely for ${kind}`, async ({ page }, testInfo) => {
  let posts = 0
  const calls: string[] = []
  const cases = {
    credentials: [401, 'UNAUTHORIZED', '이메일과 비밀번호 또는 가입 방법을 확인해 주세요.'],
    validation: [422, 'VALIDATION_ERROR', '이메일 형식과 비밀번호 입력을 확인해 주세요.'],
    origin: [403, 'ORIGIN_MISMATCH', '공식 서비스 주소에서 다시 접속해 주세요.'],
    limited: [429, 'RATE_LIMITED', '로그인 시도가 많습니다.'],
    server: [503, 'UNAVAILABLE', '로그인 서비스가 일시적으로 원활하지 않습니다.'],
    network: [0, '', '네트워크 연결'],
    html503: [503, 'UNAVAILABLE', '로그인 서비스가 일시적으로 원활하지 않습니다.'],
    session: [200, '', '로그인 상태를 확인하지 못했습니다.'],
  } as const
  const [status, code, message] = cases[kind]
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    calls.push(path)
    if (path === '/api/auth/google/status') return route.fulfill({ json: { enabled: true } })
    if (path === '/api/auth/me') return route.fulfill({ status: kind === 'session' && posts ? 503 : 401, json: { error: { code: kind === 'session' && posts ? 'UNAVAILABLE' : 'UNAUTHORIZED', message: 'private details', request_id: 'req-login-mock' } } })
    if (path === '/api/auth/login') {
      posts++
      if (kind === 'network') return route.abort('failed')
      if (kind === 'html503') return route.fulfill({ status: 503, contentType: 'text/html', headers: { 'X-Request-ID': 'req-login-mock' }, body: '<html>private failure</html>' })
      if (kind === 'session') return route.fulfill({ json: { user_id: 7 } })
      return route.fulfill({ status, json: { error: { code, message: 'private details', request_id: 'req-login-mock' } } })
    }
    return route.fulfill({ status: 404 })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  // The initial session lookup is anonymous, regardless of the submitted login failure.
  await page.getByRole('checkbox').check()
  await expect(page.getByRole('button', { name: 'Google 로그인', exact: true })).toBeEnabled()
  await page.getByLabel('이메일', { exact: true }).fill('synthetic@example.test')
  await page.getByLabel('비밀번호', { exact: true }).fill('synthetic-only-password')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  const alert = page.getByRole('alert')
  await expect(alert).toContainText(message)
  await expect(alert).not.toContainText('private')
  if (kind !== 'network') await expect(alert).toContainText('req-login-mock')
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('이메일', { exact: true })).toHaveValue('synthetic@example.test')
  if (kind === 'credentials') {
    await expect(alert).toContainText('탈퇴했거나 아직 가입하지 않았다면 회원가입이 필요합니다.')
    await expect(alert).toContainText('Google로 가입했다면 Google 로그인을 이용하세요.')
  } else await expect(alert).not.toContainText('회원가입이 필요합니다')
  expect(posts).toBe(1)
  expect(calls.every(path => ['/api/auth/me', '/api/auth/google/status', '/api/auth/login'].includes(path))).toBe(true)
  if (kind === 'credentials' || kind === 'server') await page.screenshot({ path: testInfo.outputPath(`login-${kind}.png`), fullPage: true, animations: 'disabled' })
})

test('shows self deletion completion only in the current session and guides a failed login', async ({ page }, testInfo) => {
  let signedIn = true
  const writes: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(`${route.request().method()} ${path}`)
    if (path === '/api/auth/me') return route.fulfill({ status: signedIn ? 200 : 401, json: signedIn ? { user_id: 7, role: 'user', email: 'synthetic@example.test' } : { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'req-delete-mock' } } })
    if (path === '/api/auth/google/status') return route.fulfill({ json: { enabled: true } })
    if (path === '/api/me' && route.request().method() === 'DELETE') { signedIn = false; return route.fulfill({ json: { deleted: {} } }) }
    if (path === '/api/auth/login') return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '이메일 또는 비밀번호를 확인해 주세요.', request_id: 'req-delete-mock' } } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/settings')
  await page.getByRole('button', { name: '계정 삭제', exact: true }).click()
  await page.getByRole('button', { name: '계정 삭제 확인', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('status')).toContainText('계정 삭제가 완료되었습니다.')
  await page.getByLabel('이메일', { exact: true }).fill('synthetic@example.test')
  await page.getByLabel('비밀번호', { exact: true }).fill('synthetic-only-password')
  await page.getByRole('button', { name: '로그인', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('탈퇴했거나 아직 가입하지 않았다면 회원가입이 필요합니다.')
  await page.screenshot({ path: testInfo.outputPath('deleted-account-login.png'), fullPage: true, animations: 'disabled' })
  expect(writes).toEqual(['DELETE /api/me', 'POST /api/auth/login'])
  await page.reload()
  await page.getByRole('checkbox').check()
  await expect(page.getByRole('button', { name: 'Google 로그인', exact: true })).toBeEnabled()
  await expect(page.getByText(/계정 삭제가 완료되었습니다/)).toHaveCount(0)
})

for (const role of ['user', 'admin'] as const) test(`provides basic help and removes personal settings navigation for ${role}`, async ({ page }, testInfo) => {
  const writes: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, role, email: 'user@example.test' } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  await page.getByLabel('질문', { exact: true }).fill('도움말 확인 뒤 유지할 질문')
  const help = page.getByRole('button', { name: '도움말', exact: true })
  await help.click()
  const dialog = page.getByRole('dialog', { name: '기본 사용방법' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: '프로젝트 등록', exact: true })).toBeVisible()
  await expect(dialog).toContainText('Shift+Enter')
  await expect(dialog).toContainText('현재 운영에서는 질문 파일 첨부를 지원하지 않으므로')
  const close = dialog.getByRole('button', { name: '닫기', exact: true })
  await expect(close).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(close).toBeFocused()
  await page.screenshot({ path: testInfo.outputPath('basic-help.png'), fullPage: true, animations: 'disabled' })
  await dialog.getByRole('heading', { name: '넷리스트 첨부 안내', exact: true }).scrollIntoViewIfNeeded()
  await expect(dialog.getByText(/현재 운영에서는 질문 파일 첨부를 지원하지 않으므로/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(help).toBeFocused()
  await help.click()
  await dialog.getByRole('button', { name: '닫기', exact: true }).click()
  await expect(page.getByLabel('질문', { exact: true })).toHaveValue('도움말 확인 뒤 유지할 질문')
  await page.getByRole('button', { name: 'user@example.test', exact: true }).click()
  await page.getByRole('menuitem', { name: '내 설정 관리', exact: true }).click()
  await expect(page.getByRole('heading', { name: '프로필 정보', exact: true })).toBeVisible()
  await expect(page.getByText('개인 설정', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('소속', { exact: true })).toBeVisible()
  await expect(page.getByLabel('직무', { exact: true })).toBeVisible()
  await expect(page.getByLabel('선호 실장 방식', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '계정 관리', exact: true })).toHaveCount(role === 'user' ? 1 : 0)
  if (role === 'admin') {
    await expect(page.locator('.settings-sidebar')).toHaveCount(0)
    expect((await page.locator('.settings-content').boundingBox())!.width).toBeGreaterThan(700)
  }
  await page.screenshot({ path: testInfo.outputPath('settings-navigation.png'), fullPage: true, animations: 'disabled' })
  expect(writes).toEqual([])
})

test('keeps the composer editable before selection and avoids unsupported production attachments', async ({ page }, testInfo) => {
  const writes: string[] = []
  const project = { id: 1, name: '입력 준비 회로', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, role: 'user', email: 'user@example.test' } })
    if (path === '/api/projects') return route.fulfill({ json: [project] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads' && route.request().method() === 'POST') return route.fulfill({ json: { id: 'composer-thread', project_id: 1 } })
    if (path === '/api/threads/composer-thread/runs') return route.fulfill({ contentType: 'text/event-stream', body: 'event: run_started\ndata: {"run_id":"composer-run"}\n\nevent: requires_input\ndata: {"status":"requires_input","interrupt":{"missing":["v_in_max"],"question":"입력 전압을 알려 주세요."}}\n\n' })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  const question = page.getByLabel('질문', { exact: true })
  await expect(question).toBeEditable()
  await question.fill('프로젝트 선택 전에 작성한 질문')
  await question.press('Enter')
  expect(writes).toEqual([])
  await expect(page.getByLabel('첨부 파일 선택', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '파일 첨부', exact: true })).toHaveCount(0)
  await expect(question).toBeEditable()
  await page.getByRole('button', { name: project.name, exact: true }).click()
  await page.getByRole('button', { name: /^프로젝트 선택:/ }).click()
  await page.getByRole('dialog', { name: '내 프로젝트' }).getByLabel('분석할 부품', { exact: true }).selectOption('D1')
  await expect(question).toHaveValue('프로젝트 선택 전에 작성한 질문')
  await expect(page.getByRole('button', { name: '질문 전송', exact: true })).toBeEnabled()
  await page.screenshot({ path: testInfo.outputPath('composer-attachment-ready.png'), fullPage: true })
  expect(writes).toEqual([])
  await question.press('Enter')
  await expect(page.getByRole('button', { name: '응답 수신 중단', exact: true })).toBeVisible()
  await question.fill('응답을 기다리면서 다음 질문 작성')
  await question.press('Enter')
  await expect(question).toHaveValue('응답을 기다리면서 다음 질문 작성')
  expect(writes).toEqual(['/api/projects/1/threads', '/api/threads/composer-thread/runs'])
})

test('reads NET and TXT through the real local API and agent graph with a fake model', async ({ page }, testInfo) => {
  test.skip(!process.env.SOJA_ATTACHMENT_SERVER, 'Requires the isolated no-DB/no-paid-model test server')
  const thread = '11111111-1111-4111-8111-111111111111'
  const paths: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (request.method() !== 'GET') paths.push(path)
    if (path.endsWith('/runs/attachments')) {
      const response = await page.request.post(process.env.SOJA_ATTACHMENT_SERVER + path, {
        data: request.postDataBuffer()!, headers: { 'content-type': request.headers()['content-type'], origin: 'http://127.0.0.1:5195' },
      })
      return route.fulfill({ response })
    }
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: '첨부 연결 시험' }] })
    if (path === '/api/projects/1') return route.fulfill({ json: { id: 1, name: '첨부 연결 시험', source_kind: 'upload', demo_id: null,
      connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } } })
    if (path === '/api/projects/1/threads' && request.method() === 'POST') return route.fulfill({ status: 201, json: { id: thread, project_id: 1 } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app?projectId=1&targetRef=D1')
  await expect(page.getByRole('button', { name: '프로젝트 선택: 첨부 연결 시험' })).toBeVisible()
  const question = page.getByLabel('질문', { exact: true })
  await question.fill('첨부 회로와 현재 회로를 비교해줘')
  await page.getByLabel('첨부 파일 선택').setInputFiles([
    { name: 'second.net', mimeType: 'application/octet-stream', buffer: Buffer.from('(export (components (comp (ref D2) (value SS34))) (nets (net (code 1) (name VIN) (node (ref D2) (pin 1)))))') },
    { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('검토용 메모') },
  ])
  await expect(page.getByRole('button', { name: '질문 전송' })).toBeEnabled()
  await question.press('Enter')
  await expect(page.getByText('로컬 연결 시험: 현재 프로젝트의 D1과 별도로 첨부 회로의 D2 연결을 읽었습니다 [첨부].')).toBeVisible()
  await expect(question).toHaveValue('')
  await expect(page.getByRole('list', { name: '선택한 첨부 파일' })).toHaveCount(0)
  await expect(page.locator('.user-card')).toContainText('second.net, notes.txt')
  await expect(page).toHaveURL(/projectId=1&targetRef=D1/)
  expect(paths).toEqual(['/api/projects/1/threads', `/api/threads/${thread}/runs/attachments`])
  await page.screenshot({ path: testInfo.outputPath('net-txt-agent-connected.png'), fullPage: true, animations: 'disabled' })
})

test('creates a chat from sidebar plus and reopens the empty session before its first question', async ({ page }, testInfo) => {
  const project = { id: 1, name: '새 대화 시험 회로', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } }
  let attempts = 0
  let created = false
  const runs: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, role: 'user', email: 'user@example.test' } })
    if (path === '/api/projects') return route.fulfill({ json: [project] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/1/threads') {
      if (route.request().method() === 'POST') {
        if (++attempts === 1) return route.fulfill({ status: 503, json: { error: { code: 'SERVICE_UNAVAILABLE', message: '대화를 생성하지 못했습니다.', request_id: 'mock-plus' } } })
        created = true
        return route.fulfill({ status: 201, json: { id: 'plus-thread', project_id: 1 } })
      }
      return route.fulfill({ json: created ? [{ id: 'plus-thread', project_id: 1, title: '새 대화', status: null, latest_run_id: null }] : [] })
    }
    if (path === '/api/threads/plus-thread') return route.fulfill({ json: { id: 'plus-thread', project_id: 1, title: '새 대화', target_ref: null, target_locked: false, latest_run: null, messages: [], next_before_message_id: null } })
    if (path === '/api/threads/plus-thread/runs') {
      runs.push(path)
      return route.fulfill({ contentType: 'text/event-stream', body: 'event: completed\ndata: {"status":"completed","answer":"새 세션에서 받은 답변","judgement":{},"evidence":[],"interrupt":{}}\n\n' })
    }
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app?projectId=1&targetRef=D1')
  const plus = page.getByRole('button', { name: '새 대화', exact: true })
  const question = page.getByLabel('질문', { exact: true })
  const projectPlus = page.getByRole('button', { name: '프로젝트 추가', exact: true })
  await question.focus()
  await page.mouse.move(1000, 400)
  await expect(projectPlus).toHaveCSS('opacity', '0')
  await expect(plus).toHaveCSS('opacity', '0')
  const position = await projectPlus.boundingBox()
  await page.getByRole('list', { name: '저장된 프로젝트' }).hover()
  await expect(projectPlus).toHaveCSS('opacity', '1')
  await expect(plus).toHaveCSS('opacity', '0')
  expect(await projectPlus.boundingBox()).toEqual(position)
  await page.getByText('저장된 대화가 없습니다.', { exact: true }).hover()
  await expect(projectPlus).toHaveCSS('opacity', '0')
  await expect(plus).toHaveCSS('opacity', '1')
  await page.mouse.move(1000, 400)
  await expect(plus).toHaveCSS('opacity', '0')
  await page.getByRole('button', { name: /^프로젝트 선택:/ }).focus()
  await page.keyboard.press('Tab')
  await expect(projectPlus).toBeFocused()
  await expect(projectPlus).toHaveCSS('opacity', '1')
  await plus.focus()
  await expect(plus).toHaveCSS('opacity', '1')
  await expect(plus).toBeEnabled()
  await question.fill('실패 시 보존할 초안')
  await plus.click()
  await expect(page.getByRole('alert')).toContainText('대화를 생성하지 못했습니다.')
  await expect(question).toHaveValue('실패 시 보존할 초안')
  await plus.click()
  await expect(question).toBeFocused()
  await expect(question).toHaveValue('')
  await expect(page.locator('#session-plus-thread')).toHaveAttribute('aria-current', 'true')
  expect(attempts).toBe(2)
  expect(runs).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('plus-created-session.png'), fullPage: true })
  await page.reload()
  await page.locator('#session-plus-thread').click()
  await expect(question).toBeEnabled()
  await expect(question).toBeFocused()
  await question.fill('D1 확인해줘')
  await question.press('Enter')
  await expect(page.getByText('새 세션에서 받은 답변', { exact: true })).toBeVisible()
  expect(attempts).toBe(2)
  expect(runs).toEqual(['/api/threads/plus-thread/runs'])
})

test('uses the Google entry without demo access in a production build', async ({ page }, testInfo) => {
  test.skip(process.env.SOJA_E2E_MODE !== 'production', 'Run against the built Vite preview')
  const paths: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    paths.push(path)
    if (path === '/api/auth/google/status' || path === '/api/auth/demo') return route.fulfill({ json: { enabled: true } })
    if (path === '/api/auth/google/start') { expect(new URL(route.request().url()).searchParams.get('consent')).toBe('1'); return route.fulfill({ status: 303, headers: { location: '/login?google=error' }, body: '' }) }
    return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'req-production-login' } } })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/login')
  const google = page.getByRole('button', { name: 'Google 로그인', exact: true })
  await expect(google).toBeVisible()
  await expect(google).toBeDisabled()
  await page.getByRole('checkbox').check()
  await expect(page.getByRole('link', { name: 'Google 관리자 로그인' })).toHaveCount(0)
  await expect(google).toBeEnabled()
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

test('redirects unsupported mail signup and reset URLs without issuing mail requests', async ({ page }) => {
  test.skip(process.env.SOJA_E2E_MODE !== 'production', 'Run against the built Vite preview')
  const calls: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    calls.push(`${route.request().method()} ${path}`)
    if (path === '/api/auth/google/status') return route.fulfill({ json: { enabled: true } })
    return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'offline-signup' } } })
  })
  for (const path of ['/signup', '/verify-email#token=offline-example', '/reset-password']) {
    await page.goto(path)
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'SojaFit에 로그인' })).toBeVisible()
    await expect(page.getByRole('link', { name: '회원가입', exact: true })).toHaveCount(0)
  }
  expect(calls.every(value => ['GET /api/auth/me', 'GET /api/auth/google/status'].includes(value))).toBe(true)
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
    await expect(page.locator('.conversation-panel:not(.empty-conversation)')).toBeVisible()
    await page.getByLabel('질문', { exact: true }).fill('연결 복구 시험')
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('연결 복구 시험')
    await expect(page.getByRole('button', { name: '질문 전송', exact: true })).toBeEnabled()
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
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('')
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect(attempts).toBe(2)
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs'])
  })

  test('keeps a rejected run question for retry and clears it only after acceptance', async ({ page }) => {
    let attempts = 0
    const calls = await open(page, {
      'POST /api/threads/mock-thread/runs': route => ++attempts === 1
        ? route.fulfill({ status: 503, body: '', headers: { 'X-Request-ID': 'req-run-rejected' } })
        : stream(route, ['run_started', { run_id: 'mock-run' }], ['completed', result('completed').result]),
    })
    await ask(page)
    await expect(page.getByRole('alert')).toContainText('req-run-rejected')
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('연결 복구 시험')
    expect(attempts).toBe(1)
    await page.getByRole('button', { name: '질문 전송', exact: true }).click()
    await expect(page.getByText('복구된 완료 답변', { exact: true })).toBeVisible()
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('')
    expect(submissions(calls)).toEqual(['POST /api/threads/mock-thread/runs', 'POST /api/threads/mock-thread/runs'])
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
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('')
    await page.getByLabel('질문', { exact: true }).fill('응답을 기다리며 작성한 다음 질문')
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
    await expect(page.getByLabel('질문', { exact: true })).toHaveValue('응답을 기다리며 작성한 다음 질문')
    await expect(session).toHaveAttribute('aria-busy', 'false')
    await expect(session.locator('.processing-icon')).toHaveCount(0)
    await expect(session.locator('.workspace-current-dot')).toBeVisible()
    await expect(page.getByRole('button', { name: '질문 전송', exact: true }).locator('.processing-icon')).toHaveCount(0)
  } finally { releaseCreation() }
})

test('creates a project then selects its target from the sidebar without a header summary', async ({ page }, testInfo) => {
  let created = false
  const writes: string[] = []
  const project = { id: 2, name: '새 회로', source_kind: 'demo', demo_id: 'breadboard_supply', created_at: '', updated_at: '',
    connections: { parts: [{ ref: 'D1', value: '1N4001' }, { ref: 'C1', value: '100uF' }], nets: [] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/demo') return route.fulfill({ json: { enabled: true } })
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects' && route.request().method() === 'POST') { created = true; return route.fulfill({ status: 201, json: project }) }
    if (path === '/api/projects') return route.fulfill({ json: created ? [project] : [] })
    if (path === '/api/projects/2') return route.fulfill({ json: project })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [{ id: project.demo_id, name: '데모 회로' }] })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  const header = page.locator('.workbench-topbar')
  await expect(header.locator('.workbench-context')).toHaveCount(0)
  await expect(header.getByRole('button', { name: /^프로젝트 선택:/ })).toHaveCount(0)
  await expect(page.getByText('대상 부품 미선택', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('navigation', { name: '작업 메뉴' }).getByRole('button', { name: '프로젝트 선택: 프로젝트 없음' })).toHaveText('현재 프로젝트')
  await page.screenshot({ path: testInfo.outputPath('header-summary-removed.png'), fullPage: true })
  await page.getByRole('button', { name: '프로젝트 추가', exact: true }).click()
  await page.getByLabel('새 프로젝트 이름', { exact: true }).fill(project.name)
  await page.getByLabel('데모 회로', { exact: true }).selectOption(project.demo_id)
  await page.getByRole('button', { name: '데모로 만들기', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '프로젝트 선택: 새 회로' }).click()
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
  await expect(page.locator('.analysis-heading .target-badge')).toHaveCount(0)
  await expect(page).toHaveURL(/targetRef=C1/)
  await expect(page.getByLabel('질문', { exact: true })).toBeEnabled()
  const conversation = page.getByRole('region', { name: '에이전트 대화' })
  await expect(conversation.getByRole('combobox')).toHaveCount(0)
  await expect(conversation.getByRole('heading')).toHaveCount(0)
  expect((await page.locator('.conversation-stream').boundingBox())!.height).toBeGreaterThan(300)
  expect((await page.locator('.composer').boundingBox())!.height).toBeLessThan(160)
  expect(writes).toEqual(['/api/projects'])
})

for (const target of ['D7', 'R9']) test(`uploads a file-only project and immediately opens its concept around ${target}`, async ({ page }, testInfo) => {
  let created = false
  const writes: string[] = []
  const project = { id: 3, name: '파일 프로젝트', source_kind: 'upload', demo_id: null, created_at: '', updated_at: '',
    connections: { parts: [{ ref: 'R9', value: '4.7k', footprint: '' }, ...(target === 'D7' ? [{ ref: 'D7', value: '1N4148', footprint: '' }] : []), { ref: 'C2', value: '0.1u', footprint: '' }],
      nets: [{ name: 'UPLOADED-SIGNAL', nodes: [{ ref: 'R9', pin: '1' }, ...(target === 'D7' ? [{ ref: 'D7', pin: '1' }] : []), { ref: 'C2', pin: '1' }] }] } }
  const netlist = `(export (version "E") (components ${project.connections.parts.map(part => `(comp (ref "${part.ref}") (value "${part.value}"))`).join(' ')}) (nets (net (code "1") (name "UPLOADED-SIGNAL") ${project.connections.nets[0].nodes.map(node => `(node (ref "${node.ref}") (pin "${node.pin}"))`).join(' ')})))`
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/auth/demo') return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'Not found', request_id: 'synthetic-demo-off' } } })
    if (path === '/api/projects/upload') {
      const body = route.request().postDataBuffer()!.toString('utf8')
      expect(body).toContain('filename="board.net"')
      expect(body).toContain(project.name)
      expect(body).toContain(netlist)
      created = true
      return route.fulfill({ status: 201, json: project })
    }
    if (path === '/api/projects') return route.fulfill({ json: created ? [project] : [] })
    if (path === '/api/projects/3') return route.fulfill({ json: project })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app')
  await page.getByRole('button', { name: '프로젝트 추가', exact: true }).click()
  const creator = page.getByRole('dialog', { name: '프로젝트 만들기', exact: true })
  await expect(creator.getByLabel('KiCad 넷리스트')).toBeVisible()
  await expect(creator.getByRole('form', { name: '데모 회로로 시작' })).toHaveCount(0)
  await expect(creator.getByRole('button', { name: '데모로 만들기' })).toHaveCount(0)
  await creator.getByLabel('새 프로젝트 이름').fill(project.name)
  await creator.getByLabel('KiCad 넷리스트').setInputFiles({ name: 'board.net', mimeType: 'text/plain', buffer: Buffer.from(netlist) })
  await expect(creator).toHaveCSS('opacity', '1')
  await page.screenshot({ path: testInfo.outputPath('production-file-only.png'), fullPage: true, animations: 'disabled' })
  await creator.getByRole('button', { name: '파일로 만들기', exact: true }).click()
  await expect(page.getByRole('button', { name: '프로젝트 선택: 파일 프로젝트' })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`projectId=3&targetRef=${target}`))
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '회로', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByLabel('대상 부품', { exact: true })).toHaveCount(0)
  await expect(page.getByText('업로드한 회로 · 서버에서 확인한 연결 정보', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('img', { name: `${target} 주변 연결 개념도` })).toHaveAttribute('data-layout', 'worker')
  await expect(page.getByText('UPLOADED-SIGNAL', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '연결 개념도 확대 및 이동' })).toBeInViewport({ ratio: 1 })
  await expect(page.getByRole('button', { name: `${target} 노드`, exact: true })).toBeInViewport({ ratio: 1 })
  await expect(page.getByRole('textbox', { name: '질문', exact: true })).toBeEditable()
  await page.screenshot({ path: testInfo.outputPath('project-created-no-popup.png'), fullPage: true, animations: 'disabled' })
  expect(writes).toEqual(['/api/projects/upload'])
  await page.getByRole('button', { name: '프로젝트 선택: 파일 프로젝트' }).click()
  const managerSelect = page.getByRole('dialog', { name: '내 프로젝트', exact: true }).getByLabel('분석할 부품', { exact: true })
  await managerSelect.focus()
  await managerSelect.screenshot({ path: testInfo.outputPath('manager-select-arrow.png'), animations: 'disabled' })
  await managerSelect.selectOption('C2')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page).toHaveURL(/targetRef=C2/)
  await expect(page.getByRole('img', { name: 'C2 주변 연결 개념도' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: '질문', exact: true })).toBeEnabled()
  expect(writes).toEqual(['/api/projects/upload'])
})

test('deletes projects from hover or keyboard actions without losing another project draft', async ({ page }, testInfo) => {
  const first = { id: 11, name: '작업 프로젝트', source_kind: 'upload', demo_id: null, created_at: '', updated_at: '', connections: { parts: [{ ref: 'D1', value: '1N4148', footprint: '' }], nets: [] } }
  const second = { ...first, id: 12, name: '삭제 대상 프로젝트' }
  const removed = new Set<number>()
  const writes: string[] = []
  let rejectOnce = true
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (route.request().method() === 'DELETE') {
      writes.push(path)
      if (rejectOnce) { rejectOnce = false; return route.fulfill({ status: 409, json: { error: { code: 'CONFLICT', message: '진행 중인 분석이 있습니다.', request_id: 'synthetic-project-delete' } } }) }
      removed.add(Number(path.split('/').pop()))
      return route.fulfill({ status: 204, body: '' })
    }
    if (path === '/api/projects') return route.fulfill({ json: [first, second].filter(project => !removed.has(project.id)) })
    if (path === '/api/projects/11') return route.fulfill({ json: first })
    if (path === '/api/projects/12') return route.fulfill({ json: second })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app?projectId=11&targetRef=D1')
  await page.getByRole('textbox', { name: '질문', exact: true }).fill('다른 프로젝트를 지워도 보존할 초안')
  const list = page.getByRole('list', { name: '저장된 프로젝트' })
  const row = list.getByRole('listitem').filter({ has: page.getByRole('button', { name: second.name, exact: true }) })
  const remove = row.locator('.workspace-project-delete')
  await expect(remove).toBeHidden()
  await row.getByRole('button', { name: second.name, exact: true }).focus()
  await expect(remove).toBeVisible()
  await page.getByRole('searchbox').focus()
  await expect(remove).toBeHidden()
  await row.hover()
  await expect(remove).toBeVisible()
  await list.screenshot({ path: testInfo.outputPath('project-hover-delete.png'), animations: 'disabled' })
  await remove.click()
  const dialog = page.getByRole('dialog', { name: '프로젝트 삭제', exact: true })
  await expect(dialog).toContainText(second.name)
  await expect(page).toHaveURL(/projectId=11&targetRef=D1/)
  expect(writes).toEqual([])
  await dialog.getByRole('button', { name: '취소', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(row.getByRole('button', { name: second.name, exact: true })).toBeFocused()
  expect(writes).toEqual([])
  await remove.click()
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('synthetic-project-delete')
  await expect(list.getByRole('button', { name: second.name, exact: true })).toBeVisible()
  await expect(page.getByRole('textbox', { name: '질문', exact: true })).toHaveValue('다른 프로젝트를 지워도 보존할 초안')
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(list.getByRole('button', { name: second.name, exact: true })).toHaveCount(0)
  await expect(page).toHaveURL(/projectId=11&targetRef=D1/)
  await expect(page.getByRole('textbox', { name: '질문', exact: true })).toHaveValue('다른 프로젝트를 지워도 보존할 초안')
  const current = list.getByRole('listitem').filter({ has: page.getByRole('button', { name: first.name, exact: true }) })
  await current.hover()
  await current.getByRole('button', { name: `${first.name} 프로젝트 삭제`, exact: true }).click()
  await dialog.getByRole('button', { name: '삭제 확인', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(/\/app$/)
  await expect(list.locator('.workspace-project-select')).toHaveCount(0)
  expect(writes).toEqual(['/api/projects/12', '/api/projects/12', '/api/projects/11'])
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
  await expect(list.locator('.workspace-project-select')).toHaveText(['A 프로젝트 1', 'A 프로젝트 2'])
  await page.getByRole('button', { name: '더보기 (1)' }).click()
  await expect(list.locator('.workspace-project-select')).toHaveText(projects.map(project => project.name))
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
  await expect(list.locator('.workspace-project-select')).toHaveText(['B 프로젝트'])
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
  await expect(page.getByRole('button', { name: '프로젝트 선택: 프로젝트 없음', exact: true })).toBeVisible()
  await expect(page.getByText('저장된 프로젝트가 없습니다.', { exact: true })).toBeVisible()
  expect(submissions).toHaveLength(2)
})

test('expands the detail panel to half the workspace and zooms the concept diagram', async ({ page }, testInfo) => {
  const writes: string[] = []
  const project = { id: 11, name: '연결 개념도 검토', source_kind: 'upload', demo_id: null,
    connections: { parts: [{ ref: 'R3', value: '4.7k' }, { ref: 'U1', value: 'ATtiny' }, { ref: 'J1', value: 'UART' }, { ref: 'D1', value: '1N4001' }, { ref: 'C1', value: '0.1u' }],
      nets: [{ name: 'SIGNAL', nodes: [{ ref: 'R3', pin: '1' }, { ref: 'U1', pin: '1' }, { ref: 'J1', pin: '1' }] },
        { name: '+5V', nodes: [{ ref: 'R3', pin: '2' }, { ref: 'D1', pin: '1' }, { ref: 'C1', pin: '1' }] },
        { name: 'GND', nodes: [{ ref: 'C1', pin: '2' }, { ref: 'U1', pin: '2' }] }] } }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() !== 'GET') writes.push(`${request.method()} ${path}`)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [project] })
    if (path === '/api/projects/11') return route.fulfill({ json: project })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/app?projectId=11&targetRef=R3')
  await expect(page.getByRole('tablist', { name: '정보 보기' })).toHaveCount(0)
  await page.getByRole('combobox', { name: '자료 열기' }).selectOption('circuit')
  const diagram = page.getByRole('img', { name: 'R3 주변 연결 개념도' })
  await expect(diagram).toHaveAttribute('data-layout', 'worker')
  const widths: unknown[] = []
  for (const width of [1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 })
    const handle = page.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
    const box = (await handle.boundingBox())!
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(0, box.y + box.height / 2, { steps: 8 })
    await page.mouse.up()
    await expect.poll(async () => Math.abs((await page.locator('.analysis-surface').boundingBox())!.width - (await page.locator('.information-console').boundingBox())!.width)).toBeLessThanOrEqual(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    widths.push({ viewport: width, center: (await page.locator('.analysis-surface').boundingBox())!.width, detail: (await page.locator('.information-console').boundingBox())!.width })
  }
  const viewport = page.getByRole('region', { name: '연결 개념도 확대 및 이동' })
  await viewport.scrollIntoViewIfNeeded()
  const initial = (await diagram.boundingBox())!
  const viewBox = await diagram.getAttribute('viewBox')
  await expect(page.getByRole('button', { name: '연결 개념도 확대', exact: true })).toHaveCount(0)
  const area = (await viewport.boundingBox())!
  const pointer = { x: area.x + area.width * .45, y: area.y + area.height * .45 }
  const anchor = { x: (pointer.x - initial.x) / initial.width, y: (pointer.y - initial.y) / initial.height }
  const panelScroll = await page.locator('.console-content').evaluate(element => element.scrollTop)
  await page.mouse.move(pointer.x, pointer.y)
  for (let i = 0; i < 4; i++) {
    await page.mouse.wheel(0, -100)
    await expect(page.getByLabel('연결 개념도 배율')).toHaveText(`${125 + i * 25}%`)
  }
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('200%')
  const enlarged = (await diagram.boundingBox())!
  expect(Math.abs(enlarged.width - initial.width * 2)).toBeLessThanOrEqual(2)
  expect(Math.abs(enlarged.height - initial.height * 2)).toBeLessThanOrEqual(2)
  expect(Math.abs((pointer.x - enlarged.x) / enlarged.width - anchor.x)).toBeLessThan(.005)
  expect(Math.abs((pointer.y - enlarged.y) / enlarged.height - anchor.y)).toBeLessThan(.005)
  expect(await page.locator('.console-content').evaluate(element => element.scrollTop)).toBe(panelScroll)
  await expect(diagram).toHaveAttribute('viewBox', viewBox!)
  await page.mouse.wheel(0, 100)
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('175%')
  await page.mouse.wheel(0, -100)
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('200%')
  const beforePan = await viewport.evaluate(element => [element.scrollLeft, element.scrollTop])
  await page.mouse.down()
  await page.mouse.move(pointer.x - 80, pointer.y - 60, { steps: 5 })
  await expect(viewport).toHaveClass(/dragging/)
  await page.mouse.up()
  await expect(viewport).not.toHaveClass(/dragging/)
  expect(await viewport.evaluate(element => [element.scrollLeft, element.scrollTop])).toEqual([beforePan[0] + 80, beforePan[1] + 60])
  await page.mouse.down()
  await page.mouse.move(pointer.x - 40, pointer.y - 30, { steps: 5 })
  await page.mouse.up()
  expect(await viewport.evaluate(element => [element.scrollLeft, element.scrollTop])).toEqual([beforePan[0] + 40, beforePan[1] + 30])
  await viewport.focus()
  await viewport.press('ArrowRight')
  await viewport.press('ArrowDown')
  await expect.poll(() => viewport.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)
  await expect.poll(() => viewport.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'U1 노드', exact: true }).click()
  await expect(page.getByRole('heading', { name: '선택 노드 U1' })).toBeVisible()
  const otherNode = page.getByRole('button', { name: 'D1 노드', exact: true })
  await otherNode.scrollIntoViewIfNeeded()
  const nodeBox = (await otherNode.boundingBox())!
  await page.mouse.move(nodeBox.x + nodeBox.width / 2, nodeBox.y + nodeBox.height / 2)
  await page.mouse.down()
  await page.mouse.move(nodeBox.x + nodeBox.width / 2 - 12, nodeBox.y + nodeBox.height / 2 - 12, { steps: 3 })
  await page.mouse.up()
  await expect(page.getByRole('heading', { name: '선택 노드 U1' })).toBeVisible()
  await otherNode.click()
  await expect(page.getByRole('heading', { name: '선택 노드 D1' })).toBeVisible()
  await page.getByRole('button', { name: 'U1 노드', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: '선택 노드 U1' })).toBeVisible()
  const panArea = (await viewport.boundingBox())!
  await page.mouse.move(panArea.x + panArea.width / 2, panArea.y + panArea.height / 2)
  await page.mouse.down()
  await page.mouse.move(panArea.x - 30, panArea.y + panArea.height / 2 - 30, { steps: 6 })
  await expect(viewport).toHaveClass(/dragging/)
  await page.mouse.up()
  await expect(viewport).not.toHaveClass(/dragging/)
  await page.getByRole('button', { name: '연결 개념도 화면에 맞춤' }).click()
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('100%')
  expect(await viewport.evaluate(element => [element.scrollLeft, element.scrollTop])).toEqual([0, 0])
  await expect(page.getByRole('heading', { name: '선택 노드 U1' })).toBeVisible()
  await viewport.focus()
  await viewport.press('+')
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('125%')
  await page.getByRole('combobox', { name: '자료 열기' }).selectOption('activity')
  await page.getByRole('tab', { name: '회로', exact: true }).click()
  await expect(page.getByLabel('연결 개념도 배율')).toHaveText('125%')
  await page.getByRole('button', { name: '진행 기록 탭 닫기' }).click()
  expect(writes).toEqual([])
  await testInfo.attach('panel-widths.json', { body: JSON.stringify(widths), contentType: 'application/json' })
  await page.screenshot({ path: testInfo.outputPath('half-width-concept.png'), fullPage: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    if (width === 390) {
      await expect(page.getByRole('tab', { name: '회로', exact: true })).toHaveCount(0)
      await page.getByRole('combobox', { name: '자료 열기' }).selectOption('circuit')
      await expect(page.getByRole('dialog', { name: '회로와 분석 정보', exact: true })).toBeVisible()
    }
    const toolbar = page.getByRole('group', { name: '연결 개념도 보기 도구' })
    const fit = toolbar.getByRole('button', { name: '연결 개념도 화면에 맞춤' })
    await expect(fit).toBeVisible()
    await expect(fit).toHaveText('')
    await expect(fit.locator('svg')).toHaveCount(1)
    await expect.poll(() => toolbar.evaluate(element => {
      const tool = element.getBoundingClientRect()
      const frame = element.parentElement!.getBoundingClientRect()
      const button = element.querySelector('button')!.getBoundingClientRect()
      return { top: tool.top - frame.top, right: frame.right - tool.right, fits: tool.left >= frame.left && tool.bottom <= frame.bottom, width: button.width, height: button.height }
    })).toEqual({ top: 8, right: 8, fits: true, width: 44, height: 44 })
    await expect(viewport).toHaveCSS('background-color', 'rgb(13, 19, 26)')
    await expect(viewport).not.toHaveCSS('background-image', 'none')
    await expect(diagram).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    await expect(diagram).toHaveCSS('background-image', 'none')
    await fit.click()
    await expect(page.getByLabel('연결 개념도 배율')).toHaveText('100%')
    await expect(diagram).toHaveAttribute('style', 'width: 100%; height: 100%;')
    await expect.poll(async () => Math.abs((await diagram.boundingBox())!.width - await viewport.evaluate(element => element.clientWidth))).toBeLessThanOrEqual(1)
    const fixedArea = await viewport.boundingBox()
    const fullGraph = await diagram.boundingBox()
    for (const scale of [50, 100, 200]) {
      await fit.click()
      await viewport.focus()
      for (let step = 100; step !== scale; step += scale < 100 ? -25 : 25) await viewport.press(scale < 100 ? '-' : '+')
      await expect(page.getByLabel('연결 개념도 배율')).toHaveText(`${scale}%`)
      await expect(diagram).toHaveAttribute('style', `width: ${scale}%; height: ${scale}%;`)
      const area = (await viewport.boundingBox())!
      expect(area.width).toBe(fixedArea!.width)
      expect(area.height).toBe(fixedArea!.height)
      await expect.poll(async () => Math.abs((await diagram.boundingBox())!.width - fullGraph!.width * scale / 100)).toBeLessThanOrEqual(1)
      await expect.poll(async () => Math.abs((await diagram.boundingBox())!.height - fullGraph!.height * scale / 100)).toBeLessThanOrEqual(1)
      if (scale === 50) await page.screenshot({ path: testInfo.outputPath(`concept-fixed-canvas-${width}.png`), fullPage: true })
    }
    await viewport.focus()
    await viewport.press('+')
    await fit.focus()
    await expect(fit).toBeFocused()
    await fit.press('Enter')
    await expect(page.getByLabel('연결 개념도 배율')).toHaveText('100%')
    expect(await viewport.evaluate(element => [element.scrollLeft, element.scrollTop])).toEqual([0, 0])
    await page.screenshot({ path: testInfo.outputPath(`concept-fit-icon-${width}.png`), fullPage: true })
  }
})

test('shows a completed D5 judgement from a local fake backend', async ({ page }, testInfo) => {
  const submissions: unknown[] = []
  const project = { id: 1, name: '데모 회로', source_kind: 'demo', demo_id: 'breadboard_supply', created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
    connections: { parts: [{ ref: 'D1', value: '1N5819', footprint: 'SOD-123' }], nets: [] } }
  const otherProject = { ...project, id: 2, name: '다른 회로' }
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/judge/roles') return route.fulfill({ json: [] })
    if (path === '/api/demo-circuits') return route.fulfill({ json: [] })
    if (path === '/api/projects') return route.fulfill({ json: [project, otherProject] })
    if (path === '/api/projects/1') return route.fulfill({ json: project })
    if (path === '/api/projects/2') return route.fulfill({ json: otherProject })
    if (path === '/api/projects/2/threads') return route.fulfill({ json: [] })
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
  const picker = page.getByRole('combobox', { name: '자료 열기' })
  await expect(picker).toBeVisible()
  await expect(page.getByRole('tablist', { name: '열린 자료' })).toHaveCount(0)
  await expect(page.getByRole('complementary', { name: '회로와 분석 정보' })).toHaveCount(0)
  const fullWidth = (await page.locator('.analysis-surface').boundingBox())!.width
  expect(fullWidth).toBe(1440 - 208)
  await picker.focus()
  await picker.selectOption('evidence')
  await expect(page.getByRole('tabpanel', { name: '문서 근거', exact: true })).toBeVisible()
  await picker.selectOption('circuit')
  await picker.selectOption('evidence')
  await expect(page.getByRole('tab')).toHaveText(['문서 근거', '회로'])
  await page.getByRole('button', { name: '회로 탭 닫기' }).click()
  await expect(page.getByRole('tab', { name: '문서 근거', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.information-console .result-tabs')).toHaveCount(0)
  await page.getByRole('button', { name: '문서 근거 탭 닫기' }).click()
  await expect(picker).toBeFocused()
  await expect(page.getByRole('complementary', { name: '회로와 분석 정보' })).toHaveCount(0)
  expect((await page.locator('.analysis-surface').boundingBox())!.width).toBe(fullWidth)
  await expect(question).toHaveValue('D1을 SS34로 바꿔도 되나요?')
  await page.screenshot({ path: testInfo.outputPath('contextual-closed.png'), fullPage: true, animations: 'disabled' })
  await question.press('Shift+Enter')
  await expect(question).toHaveValue('D1을 SS34로 바꿔도 되나요?\n')
  expect(submissions).toHaveLength(0)
  await question.pressSequentially('입력 12 V입니다.')
  await question.press('Enter')
  await expect(page.getByRole('group', { name: '분석 결과 메뉴' }).getByRole('button')).toHaveText(['분석 현황', '후보 비교', '문서 근거', '승인·견적'])
  await expect(question).toHaveValue('')
  await question.fill('후속 질문 작성 중')
  const citation = page.getByRole('button', { name: '문서 근거 [7] 보기', exact: true })
  await citation.click()
  expect(submissions).toEqual([{ question: 'D1을 SS34로 바꿔도 되나요?\n입력 12 V입니다.', target_ref: 'D1', conditions: '' }])
  await expect(page.getByText('SS34.pdf')).toBeVisible()
  await expect(page.getByRole('tab', { name: '문서 근거', exact: true })).toHaveAttribute('aria-selected', 'true')
  await picker.selectOption('judgement')
  await page.getByRole('tab', { name: '문서 근거', exact: true }).click()
  await page.screenshot({ path: testInfo.outputPath('contextual-evidence.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '후보 비교 탭 닫기' }).click()
  await citation.click()
  await page.getByRole('button', { name: '문서 근거 탭 닫기' }).click()
  await expect(citation).toBeFocused()
  expect((await page.locator('.analysis-surface').boundingBox())!.width).toBe(fullWidth)
  await expect(question).toHaveValue('후속 질문 작성 중')
  await page.getByRole('combobox', { name: '자료 열기' }).selectOption('judgement')
  await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
  await expect(page.getByText('같은 동작은 보장하지 않습니다.')).toBeVisible()
  const header = page.locator('.workbench-topbar')
  await expect(header.getByRole('button', { name: 'user@example.test', exact: true })).toBeVisible()
  await expect(header.getByText('판정 완료', { exact: true })).toHaveCount(0)
  await page.getByRole('list', { name: '저장된 프로젝트' }).getByRole('button', { name: otherProject.name, exact: true }).click()
  await expect(page).toHaveURL(/projectId=2/)
  await expect(page.getByRole('complementary', { name: '회로와 분석 정보' })).toHaveCount(0)
  await expect(page.getByRole('tablist', { name: '열린 자료' })).toHaveCount(0)
  await expect(question).toHaveValue('후속 질문 작성 중')
})

test('keeps four live turns, preserves reading position and restores all messages from the saved thread', async ({ page }, testInfo) => {
  const thread = '33333333-3333-4333-8333-333333333333'
  const messages: any[] = []
  let creations = 0, requests = 0
  let finishFourth!: () => void
  const fourth = new Promise<void>(resolve => { finishFourth = resolve })
  const answer = (n: number) => `${n}번째 응답: ${'회로 연결과 확인한 근거를 설명합니다. '.repeat(38)}`.trim()
  const result = (n: number) => ({ status: n === 2 ? 'refused' : 'completed', answer: answer(n), evidence: [], judgement: {}, interrupt: {}, profile_hints: [] })
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: '누적 대화 검토' }] })
    if (path === '/api/projects/1') return route.fulfill({ json: { id: 1, name: '누적 대화 검토', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } } })
    if (path === '/api/projects/1/threads' && request.method() === 'POST') { creations++; return route.fulfill({ status: 201, json: { id: thread, project_id: 1 } }) }
    if (path === `/api/threads/${thread}/runs`) {
      const n = ++requests, question = request.postDataJSON().question
      if (n === 4) await fourth
      messages.push({ id: n * 2 - 1, run_id: `turn-${n}`, role: 'user', content: question }, { id: n * 2, run_id: `turn-${n}`, role: 'assistant', content: answer(n) })
      return route.fulfill({ contentType: 'text/event-stream', body: `event: run_started\ndata: {"run_id":"turn-${n}"}\n\nevent: ${n === 2 ? 'refused' : 'completed'}\ndata: ${JSON.stringify(result(n))}\n\n` })
    }
    if (path === `/api/threads/${thread}`) return route.fulfill({ json: { id: thread, project_id: 1, target_ref: 'D1', target_locked: true,
      latest_run: { id: 'turn-4', status: 'completed', message_id: 8 }, messages, next_before_message_id: null } })
    if (path === '/api/runs/turn-4') return route.fulfill({ json: { id: 'turn-4', thread_id: thread, message_id: 8, result: result(4) } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/app?projectId=1&targetRef=D1')
  await expect(page.getByRole('button', { name: '프로젝트 선택: 누적 대화 검토' })).toBeVisible()
  const question = page.getByLabel('질문', { exact: true })
  const stream = page.locator('.conversation-stream')
  for (let n = 1; n <= 3; n++) {
    await question.fill(`${n}번째 질문`)
    await question.press('Enter')
    await expect(page.getByText(answer(n), { exact: true })).toBeVisible()
    await expect(question).toHaveValue('')
  }
  await question.fill('4번째 질문'); await question.press('Enter')
  await expect.poll(() => requests).toBe(4)
  await question.fill('응답을 기다리며 작성한 초안')
  await stream.hover(); await page.mouse.wheel(0, -5000)
  await expect.poll(() => stream.evaluate(node => node.scrollTop)).toBe(0)
  finishFourth()
  await expect(page.getByText(answer(4), { exact: true })).toBeVisible()
  expect(await stream.evaluate(node => node.scrollTop)).toBeLessThanOrEqual(2)
  await expect(page.getByRole('heading', { name: '1번째 질문' })).toBeInViewport()
  await expect(question).toHaveValue('응답을 기다리며 작성한 초안')
  await expect(question).toBeInViewport()
  expect(creations).toBe(1)
  await expect(stream.locator('.user-card')).toHaveCount(4)
  await expect(stream.locator('.final-card')).toHaveCount(4)
  await page.screenshot({ path: testInfo.outputPath('live-transcript-scroll.png'), fullPage: true, animations: 'disabled' })
  await page.goto(`/app?projectId=1&targetRef=D1&threadId=${thread}`)
  await expect(page.getByRole('region', { name: '저장된 대화' })).toBeVisible()
  await expect(stream.locator('.user-card')).toHaveCount(4)
  await expect(stream.locator('.final-card')).toHaveCount(4)
  await stream.hover(); await page.mouse.wheel(0, -5000)
  await expect(page.getByText('1번째 질문', { exact: true })).toBeInViewport()
  expect(requests).toBe(4); expect(creations).toBe(1)
})

test('loads older saved messages on scroll without losing the reading anchor or making a POST', async ({ page }, testInfo) => {
  const thread = '44444444-4444-4444-8444-444444444444'
  let olderReads = 0
  const writes: string[] = []
  let finishOlder!: () => void
  const pending = new Promise<void>(resolve => { finishOlder = resolve })
  const message = (id: number) => ({ id, run_id: `run-${Math.ceil(id / 2)}`, role: id % 2 ? 'user' : 'assistant',
    content: id % 2 ? `${id}번 질문` : `${id}번 응답: ${'저장된 대화 내용입니다. '.repeat(55)}` })
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (request.method() !== 'GET') writes.push(path)
    if (path === '/api/auth/me') return route.fulfill({ json: { user_id: 7, email: 'user@example.test', role: 'user' } })
    if (path === '/api/projects') return route.fulfill({ json: [{ id: 1, name: '이전 페이지 검토' }] })
    if (path === '/api/projects/1') return route.fulfill({ json: { id: 1, name: '이전 페이지 검토', source_kind: 'upload', demo_id: null, connections: { parts: [{ ref: 'D1', value: '1N4001' }], nets: [] } } })
    if (path === `/api/threads/${thread}`) {
      const older = url.searchParams.get('before_message_id') === '5'
      if (older) { olderReads++; await pending }
      return route.fulfill({ json: { id: thread, project_id: 1, target_ref: 'D1', target_locked: true, latest_run: { id: 'run-4', status: 'completed', message_id: 8 },
        messages: (older ? [1, 2, 3, 4] : [5, 6, 7, 8]).map(message), next_before_message_id: older ? null : 5 } })
    }
    if (path === '/api/runs/run-4') return route.fulfill({ json: { id: 'run-4', thread_id: thread, message_id: 8, result: { status: 'completed', answer: message(8).content, evidence: [], judgement: {}, interrupt: {} } } })
    return route.fulfill({ json: [] })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`/app?projectId=1&threadId=${thread}`)
  const stream = page.locator('.saved-conversation .conversation-stream')
  const anchor = page.getByText('5번 질문', { exact: true })
  await expect(page.getByText(message(8).content, { exact: true })).toBeVisible()
  await stream.hover(); await page.mouse.wheel(0, -5000)
  await expect.poll(() => olderReads).toBe(1)
  await expect.poll(() => stream.evaluate(node => node.scrollTop)).toBe(0)
  const before = (await anchor.boundingBox())!.y
  finishOlder()
  await expect(stream.locator('.conversation-card')).toHaveCount(8)
  await expect.poll(async () => Math.abs((await anchor.boundingBox())!.y - before)).toBeLessThanOrEqual(2)
  expect(olderReads).toBe(1); expect(writes).toEqual([])
  await stream.hover(); await page.mouse.wheel(0, -5000)
  await expect(page.getByText('1번 질문', { exact: true })).toBeInViewport()
  await page.screenshot({ path: testInfo.outputPath('saved-transcript-scroll.png'), fullPage: true, animations: 'disabled' })
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
  await expect(page.getByRole('complementary', { name: '회로와 분석 정보' })).toHaveCount(0)
  await page.getByRole('article', { name: '4번 에이전트 메시지' }).getByRole('button', { name: '후보 비교', exact: true }).click()
  await expect(page.getByRole('button', { name: 'SS34 후보 선택', exact: true })).toBeVisible()
  const older = page.getByRole('article', { name: '2번 에이전트 메시지' })
  await expect(older.getByRole('group', { name: '분석 결과 메뉴' })).toHaveCount(0)
  await older.getByRole('button', { name: '분석 결과 확인', exact: true }).click()
  await older.getByRole('button', { name: '후보 비교', exact: true }).click()
  await expect(page.getByRole('button', { name: '1N5819 후보 선택', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('region', { name: '저장된 대화' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: '자료 열기' })).toBeVisible()
  await expect(page.getByRole('tablist', { name: '정보 보기' })).toHaveCount(0)
  await page.getByRole('article', { name: '4번 에이전트 메시지' }).getByRole('button', { name: '후보 비교', exact: true }).click()
  await page.getByRole('combobox', { name: '자료 열기' }).selectOption('judgement')
  await expect(page.getByRole('button', { name: 'SS34 후보 선택', exact: true })).toBeVisible()
  expect(paths.every(path => path.startsWith('GET '))).toBe(true)
})


for (const width of [1440, 1200, 1024, 820, 768, 700, 390, 320]) test(`landing sections scroll at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 })
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  const calls: string[] = []
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    calls.push(new URL(route.request().url()).pathname)
    return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'landing-check' } } })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /회로를 읽고/ })).toBeVisible()
  const loaded = await page.evaluate(async () => {
    const faces = await document.fonts.load('400 18px "Noto Sans KR Variable"', '회로 조건과 문서 근거')
    return faces.some(face => face.status === 'loaded')
  })
  expect(loaded).toBe(true)
  expect(await page.locator('.public-lead').evaluate(node => getComputedStyle(node).fontFamily)).toContain('Noto Sans KR Variable')
  expect(await page.locator('.public-lead').evaluate(node => parseFloat(getComputedStyle(node).fontSize))).toBeGreaterThanOrEqual(16)
  const stats = await page.locator('.landing-stats > div').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().top))
  expect(stats).toHaveLength(3)
  expect(Math.max(...stats) - Math.min(...stats)).toBeLessThan(2)
  await expect(page.locator('.public-hero img')).toHaveCount(0)
  expect(await page.locator('.landing-stats dd').evaluateAll(nodes => nodes.every(node => node.scrollWidth <= node.clientWidth && node.getBoundingClientRect().bottom <= innerHeight))).toBe(true)
  await expect(page.locator('[data-metric="recall"]')).toContainText('93.42%')
  await expect(page.locator('[data-metric="all-evidence"]')).toContainText('92.11%')
  await expect(page.locator('[data-metric="latency"]')).toContainText('1.18초')
  const map = page.locator('.landing-guide-map')
  const nodes = page.getByRole('group', { name: '회로 검토 사용 흐름' }).getByRole('button')
  await expect(nodes).toHaveCount(9)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const mapHeight = (await map.boundingBox())!.height
  if (width >= 900) {
    const x = await nodes.evaluateAll(items => [0, 1, 3, 5].map(index => items[index].getBoundingClientRect().x))
    expect(x.every((value, index) => index === 0 || value > x[index - 1])).toBe(true)
  }
  async function checkGuideBounds(expectedHeight = mapHeight) {
    await expect.poll(() => map.evaluate(area => {
      const a = area.getBoundingClientRect(), p = area.querySelector('.landing-guide-popup')!.getBoundingClientRect()
      return p.width <= 461 && p.height <= 381 && p.left >= a.left + 10 && p.right <= a.right - 10 && p.top >= a.top + 10 && p.bottom <= a.bottom - 10
    })).toBe(true)
    expect(Math.abs((await map.boundingBox())!.height - expectedHeight)).toBeLessThan(2)
  }
  for (let index = 0; index < 9; index++) {
    const node = nodes.nth(index), title = await node.innerText()
    await node.click()
    await expect(page.getByRole('dialog', { name: title, exact: true })).toBeVisible()
    await checkGuideBounds()
    const sceneButtons = page.getByRole('group', { name: '세부 과정' }).getByRole('button')
    for (let scene = 0; scene < await sceneButtons.count(); scene++) {
      await sceneButtons.nth(scene).click()
      await expect(page.locator('.landing-guide-scenes [aria-pressed="true"]')).toHaveCount(1)
      await checkGuideBounds()
    }
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(node).toBeFocused()
  }
  await map.screenshot({ path: testInfo.outputPath(`landing-steps-${width}.png`) })
  await nodes.getByText('문서 근거', { exact: true }).click()
  await checkGuideBounds()
  if (width === 1440) {
    await page.setViewportSize({ width: 1024, height: 720 })
    await checkGuideBounds(480)
    await page.setViewportSize({ width, height: 900 })
    await checkGuideBounds()
    const body = page.locator('.landing-guide-body'), scrollY = await page.evaluate(() => window.scrollY)
    expect(await body.evaluate(node => node.scrollHeight > node.clientHeight)).toBe(true)
    await body.hover(); await page.mouse.wheel(0, 600)
    await expect.poll(() => body.evaluate(node => node.scrollTop)).toBeGreaterThan(0)
    expect(Math.abs(await page.evaluate(() => window.scrollY) - scrollY)).toBeLessThan(2)
    await expect(page.getByRole('button', { name: '과정 설명 닫기' })).toBeInViewport()
    await map.screenshot({ path: testInfo.outputPath('bounded-popup-1440.png') })
  }
  const enlarge = page.getByRole('button', { name: '예시 화면 크게 보기', exact: true })
  await enlarge.click()
  await expect(page.getByRole('dialog', { name: '문서 근거 예시 화면', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '문서 근거 예시 화면', exact: true })).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: '문서 근거', exact: true })).toBeVisible()
  await expect(enlarge).toBeFocused()
  await enlarge.hover()
  expect(await enlarge.evaluate(node => getComputedStyle(node).backgroundColor)).toBe('rgba(0, 0, 0, 0)')
  await page.getByRole('button', { name: '과정 설명 닫기' }).click()
  if (width === 1440) {
    const raw = JSON.parse(readFileSync(resolve('../evals/results/retrieval/service_r1_bits_2026-11-04.json'), 'utf8'))
    const questions = readFileSync(resolve('../evals/samples/retrieval_r1.jsonl'), 'utf8').trim().split(/\r?\n/).map(line => JSON.parse(line))
    const ids = questions.filter(q => q.split === 'test').map(q => q.id)
    const rows = raw.r1.rows.filter((row: { id: string }) => ids.includes(row.id))
    expect(rows).toHaveLength(38)
    for (const [metric, key] of [['recall', 'page_recall@5'], ['all-evidence', 'all_evidence@5']]) {
      expect(Number((rows.reduce((sum: number, row: Record<string, number>) => sum + row[key], 0) / 38).toFixed(4))).toBe(raw.r1.test[key])
      await expect(page.locator(`[data-metric="${metric}"]`)).toContainText((raw.r1.test[key] * 100).toFixed(2) + '%')
    }
    const times = [...raw.r1.rows, ...raw.v2.rows].map((row: { sec: number }) => row.sec).sort((a, b) => a - b)
    expect(times).toHaveLength(103)
    const median = times[Math.ceil(times.length / 2) - 1]
    expect(median).toBe(raw.latency.retrieve.p50)
    await expect(page.locator('[data-metric="latency"]')).toContainText(median.toFixed(2) + '초')
  }
  const conditions = page.getByText('측정 조건과 지표', { exact: true })
  await conditions.click()
  await expect(page.locator('.landing-measurement-details')).toContainText('35/38')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await conditions.click()
  await expect(page.getByText(/예시 데이터 · 실제 분석 결과가 아닙니다/)).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true })
  await page.screenshot({ path: testInfo.outputPath(`landing-viewport-${width}.png`) })
  await page.locator('.landing-stats').screenshot({ path: testInfo.outputPath(`landing-stats-${width}.png`) })
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await page.screenshot({ path: testInfo.outputPath(`landing-footer-${width}.png`) })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  const navigation = page.getByRole('navigation', { name: '서비스 안내' })
  for (const [label, id] of [['서비스 소개', 'service'], ['사용 방법', 'how-it-works']]) {
    const link = navigation.getByRole('link', { name: label })
    await expect(link).toBeVisible()
    await link.click()
    await expect(page).toHaveURL(new RegExp(`#${id}$`))
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(200)
    await expect.poll(() => page.locator(`#${id}`).evaluate(node => {
      const header = document.querySelector('.landing-page .public-header')!.getBoundingClientRect()
      const rect = node.getBoundingClientRect()
      return rect.top >= header.bottom - 1 && rect.top < innerHeight / 2
    })).toBe(true)
    await expect(page.locator(`#${id}`)).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.emulateMedia({ reducedMotion: 'reduce' })
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe('auto')
  await navigation.getByRole('link', { name: '서비스 소개' }).focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#service$/)
  await expect(page.locator('#service')).toBeFocused()
  expect(calls.some(path => path.startsWith('/api/projects') || path.includes('/runs'))).toBe(false)
  expect(pageErrors).toEqual([])
  expect(await page.locator('.brand-logo').evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
  if (width === 1440) {
    await page.getByRole('link', { name: '로그인', exact: true }).click()
    await expect(page.locator('.login-page')).toBeVisible()
    expect(await page.locator('.login-page').evaluate(node => getComputedStyle(node).fontFamily)).not.toContain('Noto Sans KR Variable')
  }
})
