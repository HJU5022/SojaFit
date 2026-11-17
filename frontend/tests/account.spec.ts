/** 현재 백엔드에서 인증·기억·업로드·회로 버전 격리를 확인한다. 분석 호출은 하지 않는다. */
import { test, expect } from '@playwright/test';
test('설정 저장·복원과 A/B 계정 격리', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 A' }).click();
  await expect(page).toHaveURL(/\/app/);
  // 내 설정 · 로그아웃은 사이드바 계정 메뉴 안에 있다(#43)
  await page.getByRole('button', { name: /계정 메뉴$/ }).click();
  await page.getByRole('menuitem', { name: '내 설정' }).click();
  await page.getByLabel('소속', { exact: true }).fill('데모 회로설계팀');
  await page.getByLabel('직무', { exact: true }).fill('하드웨어 회로 설계');
  await page.getByLabel('선호 실장 방식', { exact: true }).selectOption('smd');
  await page.getByRole('button', { name: '설정 저장' }).click();
  await expect(page.getByText('내 설정을 저장했습니다.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('소속', { exact: true })).toHaveValue('데모 회로설계팀');
  await expect(page.getByLabel('직무', { exact: true })).toHaveValue('하드웨어 회로 설계');
  await page.getByLabel('소속', { exact: true }).fill('');
  await page.getByLabel('직무', { exact: true }).fill('');
  await page.getByRole('button', { name: '설정 저장' }).click();
  await expect(page.getByText('내 설정을 저장했습니다.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('소속', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('직무', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: /계정 메뉴$/ }).click();
  await page.getByRole('menuitem', { name: '로그아웃' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('button', { name: '데모 사용자 B' }).click();
  await page.getByRole('button', { name: /계정 메뉴$/ }).click();
  await page.getByRole('menuitem', { name: '내 설정' }).click();
  await expect(page.getByLabel('소속', { exact: true })).toHaveValue('');
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: '관리자만 접근할 수 있습니다.' })).toBeVisible();
});
test('첨부한 넷리스트는 새 버전·대화를 만들고 기존 대화의 회로를 보존한다', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 B' }).click();
  await expect(page).toHaveURL(/\/app/);
  // 사이드바 "프로젝트" 머리글의 +(#31)
  await page.getByRole('button', { name: '새 프로젝트', exact: true }).click();
  await page.getByRole('button', { name: '나중에 첨부', exact: true }).click();
  const name = '넷리스트 첨부 검증 ' + Date.now();
  await page.getByLabel('프로젝트 이름').fill(name);
  await page.getByRole('button', { name: '프로젝트 만들기' }).click();
  // 회로 패널(#39)은 평소 닫혀 있다. 회로가 처음 생기면(아래 첫 첨부) 저절로 열린다
  await expect(page.getByRole('button', { name: '회로 보기' })).toBeVisible();
  const net = (ref: string) =>
    `(export (version "E") (components (comp (ref "${ref}") (value "1N4001") (footprint "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal")) (comp (ref "R1") (value "1k"))) (nets (net (code "1") (name "VIN") (node (ref "${ref}") (pin "1")) (node (ref "R1") (pin "1"))) (net (code "2") (name "GND") (node (ref "${ref}") (pin "2")) (node (ref "R1") (pin "2")))))`;
  await page
    .locator('.attach-button input')
    .setInputFiles({ name: 'test.net', mimeType: 'text/plain', buffer: Buffer.from(net('D1')) });
  await page.getByRole('button', { name: '넷리스트 보내기' }).click();
  await expect(page.getByLabel('회로의 다이오드')).toContainText('D1');
  const first = page.url();
  await page
    .locator('.attach-button input')
    .setInputFiles({ name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from(net('D2')) });
  await page.getByRole('button', { name: '넷리스트 보내기' }).click();
  await expect(page.getByLabel('회로의 다이오드')).toContainText('D2');
  await expect(page).not.toHaveURL(first);
  // 회로가 있는 프로젝트를 열면 패널이 한 번 저절로 열린다(#47). 머리 단추를 누르면 오히려 닫힌다
  await page.goto(first);
  await expect(page.getByLabel('회로의 다이오드')).toBeVisible();
  await expect(page.getByLabel('회로의 다이오드')).toContainText('D1');
  await expect(page.getByLabel('회로의 다이오드')).not.toContainText('D2');
  // 과거 버전의 점검표에서 시작한 검토도 그 회로에 고정되어야 한다.
  await page.getByRole('button', { name: '부품 점검표', exact: true }).click();
  await page
    .getByRole('row')
    .filter({ has: page.getByRole('cell', { name: 'D1', exact: true }) })
    .getByRole('button', { name: '이 부품 검토', exact: true })
    .click();
  await expect(page.getByLabel('검토 질문')).toHaveValue('D1을 다른 부품으로 바꿔도 될까?');
  await expect(page.getByLabel('회로의 다이오드')).toContainText('D1');
  await expect(page.getByLabel('회로의 다이오드')).not.toContainText('D2');
  const draftThread = new URL(page.url()).searchParams.get('thread');
  expect(draftThread).toBeTruthy();
  const draft = await page.request.get('/api/threads/' + draftThread);
  expect(draft.ok()).toBe(true);
  const draftDetail = await draft.json();
  expect(draftDetail.circuit_version).toBe(1);
  expect(draftDetail.messages).toEqual([]); // 보내기 전에는 분석을 실행하지 않는다.
  // 사이드바 프로젝트 줄 ⋯ 메뉴로 이 시험의 프로젝트를 지운다(확인 창). 옛 /projects는 /app으로 바뀐다(#34)
  await page.goto('/projects');
  await expect(page).toHaveURL(/\/app$/);
  await page.getByRole('button', { name: name + ' 메뉴', exact: true }).click();
  await page.getByRole('menuitem', { name: '삭제' }).click();
  await page.getByRole('dialog').getByRole('button', { name: '삭제', exact: true }).click();
  await expect(page.getByRole('button', { name: name + ' 메뉴', exact: true })).toHaveCount(0);
});

test('인증 화면은 정확한 경로만 연다', async ({ page }) => {
  for (const path of ['/signup-extra', '/password-reset-extra']) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: '로그인', exact: true })).toBeVisible();
  }
});

test('새 프로젝트에서 회로도 첨부를 선택할 수 있다', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 B' }).click();
  await page.getByRole('button', { name: '새 프로젝트', exact: true }).click();
  await page.getByRole('button', { name: '넷리스트 업로드', exact: true }).click();
  await expect(page.getByRole('dialog').locator('input[type=file]')).toHaveAttribute(
    'accept',
    /\.kicad_sch/,
  );
});

for (const sendMethod of ['버튼', 'Enter'] as const) {
  test(`동일 질문을 다시 보내도 질문을 즉시 표시하고 직전 답변을 유지한다 [${sendMethod}]`, async ({
    page,
  }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: '데모 사용자 B' }).click();
    await expect(page).toHaveURL(/\/app/);
    const headers = {
      Origin: new URL(process.env.SOJAFIT_BASE_URL || 'http://localhost:8000').origin,
    };
    const project = await page.request.post('/api/projects?allow_duplicate=true', {
      headers,
      data: { name: `BUG009 ${Date.now()}`, demo_id: 'attiny85_dev' },
    });
    expect(project.status()).toBe(201);
    const pid = (await project.json()).id;
    const thread = await page.request.post(`/api/projects/${pid}/threads`, { headers });
    const tid = (await thread.json()).id;
    const first = await page.request.post(`/api/threads/${tid}/runs`, {
      headers,
      data: { question: 'D996를 다른 부품으로 바꿔도 될까?' },
    });
    expect(first.ok()).toBe(true);
    await first.text();
    await page.goto(`/app?project=${pid}&thread=${tid}`);
    await expect(page.locator('.assistant-reply').last()).toContainText('D996');
    let release!: () => void;
    let ready!: () => void;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    const responseReady = new Promise<void>((resolve) => {
      ready = resolve;
    });
    let runRequests = 0;
    await page.route('**/api/threads/*/runs', async (route) => {
      runRequests++;
      const response = await route.fetch();
      ready();
      await held;
      await route.fulfill({ response });
    });
    await page.getByLabel('검토 질문').fill('D996를 다른 부품으로 바꿔도 될까?');
    if (sendMethod === 'Enter') await page.getByLabel('검토 질문').press('Enter');
    else await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
    await responseReady;
    try {
      await expect(page.getByLabel('검토 질문')).toHaveValue('');
      await expect(
        page
          .locator('.conversation-scroll .user-message p')
          .filter({ hasText: /^D996를 다른 부품으로 바꿔도 될까\?$/ }),
      ).toHaveCount(2);
      await expect(page.locator('.assistant-reply').first()).toContainText('D996');
      if (sendMethod === 'Enter') {
        await page.getByLabel('검토 질문').press('Enter');
        expect(runRequests).toBe(1);
        if (process.env.SOJAFIT_EVIDENCE_DIR)
          await page.screenshot({
            path: process.env.SOJAFIT_EVIDENCE_DIR + '/BUG-010-enter-repeat-local.png',
            fullPage: true,
          });
      }
    } finally {
      release();
    }
    await expect(page.locator('.assistant-reply').last()).toContainText('D996');
    await expect(page.locator('.assistant-reply')).toHaveCount(2);
  });

  test(`새 대화 생성 응답을 기다리는 동안 전송 질문을 표시하고 입력을 비운다 [${sendMethod}]`, async ({
    page,
  }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: '데모 사용자 B' }).click();
    await expect(page).toHaveURL(/\/app/);
    await page.getByRole('button', { name: '새 대화', exact: true }).click();
    let release!: () => void;
    let ready!: () => void;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    const responseReady = new Promise<void>((resolve) => {
      ready = resolve;
    });
    let projectRequests = 0;
    await page.route('**/api/projects?allow_duplicate=true', async (route) => {
      projectRequests++;
      const response = await route.fetch();
      ready();
      await held;
      await route.fulfill({ response });
    });
    await page.getByLabel('새 대화 질문').fill('D1을 다른 부품으로 바꿔도 될까?');
    if (sendMethod === 'Enter') await page.getByLabel('새 대화 질문').press('Enter');
    else await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
    await responseReady;
    try {
      await expect(page.getByLabel('새 대화 질문')).toHaveValue('');
      await expect(page.locator('.user-message')).toHaveText('D1을 다른 부품으로 바꿔도 될까?');
      if (sendMethod === 'Enter') {
        await page.getByLabel('새 대화 질문').press('Enter');
        expect(projectRequests).toBe(1);
        if (process.env.SOJAFIT_EVIDENCE_DIR)
          await page.screenshot({
            path: process.env.SOJAFIT_EVIDENCE_DIR + '/BUG-010-enter-newchat-local.png',
            fullPage: true,
          });
      }
    } finally {
      release();
    }
    await expect(page.getByTestId('circuit-request')).toBeVisible();
  });
}

test('최신 대화는 아래로 이동하고 이전 기록을 읽는 동안에는 위치를 유지한다', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 B' }).click();
  await expect(page).toHaveURL(/\/app/);
  const headers = {
    Origin: new URL(process.env.SOJAFIT_BASE_URL || 'http://localhost:8000').origin,
  };
  const project = await page.request.post('/api/projects?allow_duplicate=true', {
    headers,
    data: { name: `BUG007 ${Date.now()}`, demo_id: 'attiny85_dev' },
  });
  expect(project.status()).toBe(201);
  const pid = (await project.json()).id;
  const thread = await page.request.post(`/api/projects/${pid}/threads`, { headers });
  const tid = (await thread.json()).id;
  for (let n = 900; n < 908; n++) {
    const response = await page.request.post(`/api/threads/${tid}/runs`, {
      headers,
      data: { question: `D${n}를 다른 부품으로 바꿔도 될까?` },
    });
    expect(response.ok()).toBe(true);
    await response.text();
  }
  await page.goto(`/app?project=${pid}&thread=${tid}`);
  const scroll = page.locator('.conversation-scroll');
  await expect(page.locator('.assistant-reply').last()).toContainText('D907');
  const gap = () => scroll.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight);
  await expect.poll(gap).toBeLessThan(5);
  // 실제 서버 결과를 잠깐 보류하여, 답변 도착 전에 사용자가 위로 읽는 상황을 만든다.
  let release!: () => void;
  let ready!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const responseReady = new Promise<void>((resolve) => {
    ready = resolve;
  });
  await page.route('**/api/threads/*/runs', async (route) => {
    const response = await route.fetch();
    ready();
    await held;
    await route.fulfill({ response });
  });
  await scroll.evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.getByLabel('검토 질문').fill('D995를 다른 부품으로 바꿔도 될까?');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await responseReady;
  await expect.poll(gap).toBeLessThan(5); // 직접 보낸 질문은 아래로 보낸다.
  await scroll.evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.waitForTimeout(100); // 실제 scroll 이벤트 처리 후 답변을 전달한다.
  release();
  await expect(page.locator('.assistant-reply').last()).toContainText('D995');
  await expect.poll(() => scroll.evaluate((el) => el.scrollTop)).toBeLessThan(5);
  expect(await gap()).toBeGreaterThan(100);
});

test('종료 프레임이 유실되면 재분석 없이 저장된 결과를 자동으로 복원한다', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 B' }).click();
  await expect(page).toHaveURL(/\/app/);
  const headers = {
    Origin: new URL(process.env.SOJAFIT_BASE_URL || 'http://localhost:8000').origin,
  };
  const project = await page.request.post('/api/projects?allow_duplicate=true', {
    headers,
    data: { name: `BUG006 ${Date.now()}`, demo_id: 'attiny85_dev' },
  });
  expect(project.status()).toBe(201);
  const pid = (await project.json()).id;
  const thread = await page.request.post(`/api/projects/${pid}/threads`, { headers });
  const tid = (await thread.json()).id;
  await page.goto(`/app?project=${pid}&thread=${tid}`);
  let runRequests = 0;
  await page.route('**/api/threads/*/runs', async (route) => {
    runRequests++;
    // 실제 서버의 실행·저장은 완료시키고 전달 중 마지막 SSE 프레임만 유실시킨다.
    const response = await route.fetch();
    const body = (await response.text())
      .split('\n\n')
      .filter((frame) => !/^event:\s*(completed|requires_input|refused|failed)\s*$/m.test(frame))
      .join('\n\n');
    await route.fulfill({ response, body });
  });
  await page.getByLabel('검토 질문').fill('D997를 다른 부품으로 바꿔도 될까?');
  await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
  await expect(page.locator('.assistant-reply').last()).toContainText('D997', { timeout: 10000 });
  await expect(
    page.getByText('실시간 수신을 멈췄습니다. 서버 검토는 계속될 수 있습니다.'),
  ).toHaveCount(0);
  await page.getByLabel('검토 질문').fill('다음 질문');
  await expect(page.getByRole('button', { name: '질문 보내기', exact: true })).toBeEnabled();
  expect(runRequests).toBe(1);
});

for (const kind of ['net', 'kicad_sch'] as const) {
  test(`대화 중 ${kind} 첨부는 이전 기록과 함께 쓴 질문을 보존한다`, async ({ page }) => {
    test.skip(
      kind === 'kicad_sch' && !process.env.SOJAFIT_SCHEMATIC_FILE,
      '로컬 KiCad 렌더러와 실제 회로도 경로 필요',
    );
    await page.goto('/login');
    await page.getByRole('button', { name: '데모 사용자 B' }).click();
    await expect(page).toHaveURL(/\/app/);
    const headers = {
      Origin: new URL(process.env.SOJAFIT_BASE_URL || 'http://localhost:8000').origin,
    };
    const project = await page.request.post('/api/projects?allow_duplicate=true', {
      headers,
      data: { name: `BUG004 ${kind} ${Date.now()}`, demo_id: 'attiny85_dev' },
    });
    expect(project.status()).toBe(201);
    const pid = (await project.json()).id;
    const thread = await page.request.post(`/api/projects/${pid}/threads`, { headers });
    const tid = (await thread.json()).id;
    // 회로에 없는 참조는 코드가 답하므로 실제 모델 호출 없이 대화 기록을 만든다.
    const firstQuestion = 'D999를 다른 부품으로 바꿔도 될까?';
    const started = await page.request.post(`/api/threads/${tid}/runs`, {
      headers,
      data: { question: firstQuestion },
    });
    expect(started.ok()).toBe(true);
    await started.text();
    const original = await (await page.request.get(`/api/threads/${tid}`)).json();
    expect(original.messages).toHaveLength(2);
    const originalUrl = `/app?project=${pid}&thread=${tid}`;
    await page.goto(originalUrl);
    await expect(
      page.locator('.conversation-scroll').getByText(firstQuestion, { exact: true }),
    ).toBeVisible();
    const secondQuestion = 'D998를 다른 부품으로 바꿔도 될까?';
    await page.getByLabel('검토 질문').fill(secondQuestion);
    const net =
      '(export (version "E") (components (comp (ref "D1") (value "1N4001"))) (nets (net (code "1") (name "VIN") (node (ref "D1") (pin "1"))) (net (code "2") (name "GND") (node (ref "D1") (pin "2")))))';
    const file =
      kind === 'kicad_sch'
        ? process.env.SOJAFIT_SCHEMATIC_FILE!
        : { name: 'updated.net', mimeType: 'text/plain', buffer: Buffer.from(net) };
    await page.locator('.attach-button input').setInputFiles(file);
    let postedQuestions = 0;
    page.on('request', (request) => {
      if (request.method() === 'POST' && /\/api\/threads\/[^/]+\/runs$/.test(request.url()))
        postedQuestions++;
    });
    await page.getByRole('button', { name: '넷리스트 보내기', exact: true }).click();
    await expect(
      page.locator('.conversation-scroll').getByText(secondQuestion, { exact: true }),
    ).toBeVisible({ timeout: 45000 });
    await expect(
      page.locator('.conversation-scroll').getByText(firstQuestion, { exact: true }),
    ).toBeVisible();
    await expect(page).not.toHaveURL(new RegExp(`thread=${tid}`));
    const childId = new URL(page.url()).searchParams.get('thread');
    expect(childId).not.toBe(tid);
    await expect
      .poll(async () => {
        const detail = await (await page.request.get(`/api/threads/${childId}`)).json();
        return detail.messages.length;
      })
      .toBe(2);
    expect(postedQuestions).toBe(1);
    const child = await (await page.request.get(`/api/threads/${childId}`)).json();
    expect(child.circuit_version).toBe(2);
    expect(child.previous_thread_id).toBe(tid);
    expect((await (await page.request.get(`/api/threads/${tid}`)).json()).messages).toEqual(
      original.messages,
    );
    await page.reload();
    await expect(
      page.locator('.conversation-scroll').getByText(firstQuestion, { exact: true }),
    ).toBeVisible();
    await expect(
      page.locator('.conversation-scroll').getByText(secondQuestion, { exact: true }),
    ).toBeVisible();
    // 파일만 다시 첨부해도 이전 두 대화의 기록이 새로고침 뒤까지 이어진다.
    await page.locator('.attach-button input').setInputFiles(file);
    await page.getByRole('button', { name: '넷리스트 보내기', exact: true }).click();
    await expect(page).not.toHaveURL(new RegExp(`thread=${childId}`));
    await page.reload();
    await expect(
      page.locator('.conversation-scroll').getByText(firstQuestion, { exact: true }),
    ).toBeVisible();
    await expect(
      page.locator('.conversation-scroll').getByText(secondQuestion, { exact: true }),
    ).toBeVisible();
    expect(postedQuestions).toBe(1);
    if (kind === 'kicad_sch' && process.env.SOJAFIT_EVIDENCE_DIR) {
      await page.screenshot({
        path: process.env.SOJAFIT_EVIDENCE_DIR + '/BUG-004-after.png',
        fullPage: true,
      });
    }
  });
}

// API 응답 fixture로 실제 UI 배치·드래그만 검사하며 모델·DB 호출을 하지 않는다.
for (const width of [1440, 390]) {
  test(`사용 조건 팝업을 이동해도 초안이 유지된다 (${width}px)`, async ({ page }, testInfo) => {
    const project = {
      id: 987654,
      name: '사용 조건 배치 검사',
      source_kind: 'empty',
      demo_id: null,
      circuit_version: 0,
      has_circuit: false,
      connections: {},
    };
    const writes: string[] = [];
    await page.route('**/api/**', async (route) => {
      const request = route.request();
      if (request.method() !== 'GET') {
        writes.push(request.url());
        return route.fulfill({
          status: 503,
          json: { error: { message: '배치 검사에서는 쓰기를 하지 않습니다.' } },
        });
      }
      const path = new URL(request.url()).pathname;
      const json =
        path === '/api/auth/me'
          ? { user_id: 1, email: 'layout@example.test', role: 'user' }
          : path === '/api/projects'
            ? [project]
            : path === '/api/projects/987654'
              ? project
              : [];
      await route.fulfill({ json });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/app?project=987654');
    const question = page.getByRole('textbox', { name: '검토 질문', exact: true });
    await question.fill('추가 조건으로 확인할 수 있는 내용은 없어');
    const toggle = page.getByRole('button', { name: '사용 조건', exact: true });
    await toggle.click();
    const popup = page.getByRole('dialog', { name: '사용 조건', exact: true });
    await expect(popup).toBeVisible();
    const conditions = popup.getByRole('textbox', { name: '전압·전류·온도 등', exact: true });
    await conditions.fill('입력 5 V, 최대 전류 40 mA, 주변 온도 25°C');
    const mainBox = (await question.boundingBox())!;
    const initialBox = (await popup.boundingBox())!;
    expect(initialBox.y + initialBox.height).toBeLessThanOrEqual(mainBox.y);
    const handle = popup.getByRole('button', { name: '사용 조건 창 이동', exact: true });
    const handleBox = (await handle.boundingBox())!;
    await page.mouse.move(handleBox.x + 25, handleBox.y + 15);
    await page.mouse.down();
    await page.mouse.move(handleBox.x - 95, handleBox.y - 85, { steps: 5 });
    await page.mouse.up();
    const moved = (await popup.boundingBox())!;
    expect(moved.y).toBeLessThan(initialBox.y - 20);
    expect(moved.x).toBeGreaterThanOrEqual(12);
    expect(moved.x + moved.width).toBeLessThanOrEqual(width - 12);
    await handle.press('ArrowRight');
    expect((await popup.boundingBox())!.x).toBeGreaterThan(moved.x);
    await question.fill('메인 질문도 계속 입력할 수 있습니다.');
    await expect(popup).toBeVisible();
    await popup.getByRole('button', { name: '사용 조건 창 닫기' }).click();
    await expect(popup).toHaveCount(0);
    await toggle.click();
    await expect(conditions).toHaveValue('입력 5 V, 최대 전류 40 mA, 주변 온도 25°C');
    await expect(question).toHaveValue('메인 질문도 계속 입력할 수 있습니다.');
    const edgeHandle = (await handle.boundingBox())!;
    await page.mouse.move(edgeHandle.x + 25, edgeHandle.y + 15);
    await page.mouse.down();
    await page.mouse.move(width - 1, 843, { steps: 5 });
    await page.mouse.up();
    const edge = (await popup.boundingBox())!;
    expect(edge.x + edge.width).toBeLessThanOrEqual(width - 12);
    expect(edge.y + edge.height).toBeLessThanOrEqual(832);
    const smallerWidth = Math.min(width, 900);
    await page.setViewportSize({ width: smallerWidth, height: 500 });
    await expect
      .poll(async () => {
        const box = (await popup.boundingBox())!;
        return (
          box.x >= 12 &&
          box.y >= 12 &&
          box.x + box.width <= smallerWidth - 12 &&
          box.y + box.height <= 488
        );
      })
      .toBe(true);
    await page.setViewportSize({ width, height: 844 });
    await handle.press('Escape');
    await expect(popup).toHaveCount(0);
    await toggle.click();
    await page.screenshot({ path: testInfo.outputPath(`conditions-popup-${width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    expect(writes).toEqual([]);
  });
}

for (const scenario of ['접수 성공', '새 대화 접수 성공', '접수 거절', '접수 전 새 초안']) {
  test(`사용 조건 초안 정리: ${scenario}`, async ({ page }) => {
    const project = {
      id: 987654,
      name: '초안 검사',
      source_kind: 'empty',
      demo_id: null,
      circuit_version: 0,
      has_circuit: false,
      connections: {},
    };
    const result = {
      answer: '화면 시험 응답',
      status: 'completed',
      stage: '완료',
      evidence: [],
      judgement: {},
      price_parts: [],
      interrupt: {},
    };
    let sent: any;
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/api/**', async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() === 'POST' && path === '/api/projects/987654/threads')
        return route.fulfill({ status: 201, json: { id: 'layout-thread' } });
      if (request.method() === 'POST' && path === '/api/threads/layout-thread/runs') {
        sent = request.postDataJSON();
        if (scenario === '접수 전 새 초안') await gate;
        if (scenario === '접수 거절')
          return route.fulfill({
            status: 503,
            json: { error: { code: 'UNAVAILABLE', message: '접수하지 못했습니다.' } },
          });
        return route.fulfill({
          contentType: 'text/event-stream',
          body: `event: run_started\ndata: {"run_id":"layout-run"}\n\nevent: completed\ndata: ${JSON.stringify(result)}\n\n`,
        });
      }
      if (request.method() !== 'GET') throw new Error(`예상하지 않은 쓰기: ${path}`);
      const json =
        path === '/api/auth/me'
          ? { user_id: 1, email: 'layout@example.test', role: 'user' }
          : path === '/api/projects'
            ? [project]
            : path === '/api/projects/987654'
              ? project
              : path === '/api/threads/layout-thread'
                ? {
                    id: 'layout-thread',
                    target_ref: '',
                    title: '초안 검사',
                    messages: [],
                    latest_run: null,
                  }
                : path === '/api/runs/layout-run'
                  ? { id: 'layout-run', thread_id: 'layout-thread', message_id: null, result }
                  : [];
      await route.fulfill({ json });
    });
    await page.goto(
      scenario === '새 대화 접수 성공'
        ? '/app?project=987654'
        : '/app?project=987654&thread=layout-thread',
    );
    const question = page.getByRole('textbox', { name: '검토 질문', exact: true });
    await question.fill('다이오드 사양을 검토해 주세요.');
    await page.getByRole('button', { name: '사용 조건', exact: true }).click();
    const conditions = page.getByRole('textbox', { name: '전압·전류·온도 등', exact: true });
    await conditions.fill('입력 5 V');
    await page.getByRole('button', { name: '질문 보내기', exact: true }).click();
    await expect.poll(() => sent?.conditions).toBe('입력 5 V');
    if (scenario === '접수 전 새 초안') {
      await conditions.fill('다음 질문: 입력 12 V');
      release();
    }
    if (scenario === '접수 거절')
      await expect(page.getByRole('alert')).toContainText('접수하지 못했습니다.');
    else await expect(page.locator('.assistant-reply').last()).toBeVisible();
    if (!(await conditions.isVisible()))
      await page.getByRole('button', { name: '사용 조건', exact: true }).click();
    await expect(conditions).toHaveValue(
      scenario === '접수 성공' || scenario === '새 대화 접수 성공'
        ? ''
        : scenario === '접수 거절'
          ? '입력 5 V'
          : '다음 질문: 입력 12 V',
    );
  });
}
