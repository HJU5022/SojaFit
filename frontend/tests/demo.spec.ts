/** 실제 데모 서버에서 사용자 흐름과 뷰포트를 확인한다. 고정 응답을 가로채지 않는다. */
import { test, expect, type Page } from '@playwright/test';
// [왜] 화면 아래의 지연 로딩 이미지도 실제 스크롤로 읽어, 모든 이미지가 그림으로 받아졌는지(HTML 대체가 아닌지) 확인한다.
async function readyLanding(page: Page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let top = 0; top < height; top += 700) {
    await page.evaluate((y) => window.scrollTo(0, y), top);
    await page.waitForTimeout(100);
  }
  await page.evaluate(() => Promise.all([...document.images].map((img) => img.decode())));
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(600);
}
test('데모 로그인 → 검토 → 조건 재개 → 승인·견적 → 기억', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  await readyLanding(page);
  expect(await page.evaluate(() => [...document.images].every((i) => i.naturalWidth > 0))).toBe(
    true,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(450);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('link', { name: '내 회로 검토하기' }).first().click();
  await page.getByRole('button', { name: '데모 사용자 A' }).click();
  await expect(page).toHaveURL(/\/app/);
  // 대화가 먼저(#30): 회로 없이 질문하면 에이전트가 대화 안에서 회로를 묻고, 데모 회로를 고르면 그 작업대가 열린다.
  // 대상을 정하지 않으면 그 데모 회로의 기록 질문이 모두 보인다
  await page.getByRole('button', { name: '새 대화', exact: true }).click();
  await page.getByLabel('새 대화 질문').fill('D1을 다른 부품으로 바꿔도 될까요?');
  await page.getByRole('button', { name: '질문 보내기' }).click();
  await page
    .getByTestId('circuit-request')
    .getByRole('button', { name: 'ATtiny85 Time Switch', exact: true })
    .last() // 같은 이름의 기존 프로젝트 뒤에 있는 데모 생성 버튼을 고른다.
    .click();
  await page.locator('[data-demo-id="v3-01"]').click();
  await expect(page.getByTestId('requires-input')).toBeVisible({ timeout: 45000 });
  await expect(page.getByTestId('requires-input').getByRole('textbox')).toHaveAttribute(
    'placeholder',
    '예: 0.5 V',
  );
  // [왜] 서버가 요구하는 분석 호출 간격(기본 2초)을 실제 사용자 흐름에서도 지킨다.
  await page.waitForTimeout(2100);
  await page.getByRole('button', { name: '기록한 답으로 계속하기' }).click();
  await expect(page.locator('.candidate-card').first()).toBeVisible({ timeout: 45000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(450);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('.candidate-card').first().click();
  await expect(page.locator('.check-row').first()).toBeVisible();
  await page.locator('.check-row summary').first().click();
  await expect(page.locator('.check-evidence .citation').first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(450);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: '닫기', exact: true }).click();
  await page.locator('.demo-questions summary').click();
  await page.waitForTimeout(2100);
  await page.locator('[data-demo-id="demo-ask"]').click();
  await expect(page.getByTestId('requires-input')).toBeVisible({ timeout: 45000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(450);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(2100);
  await page.getByLabel('다이오드에서 허용하는 전압 강하').fill('1.5V');
  await page.getByRole('button', { name: '이 값으로 계속 검토' }).click();
  await expect(page.locator('.candidate-card').first()).toBeVisible({ timeout: 45000 });
  await page.locator('.candidate-card').first().click();
  await page.getByRole('button', { name: '가격·재고 조회', exact: true }).click();
  await expect(page.getByText('데모 모드라 Mouser 가격·재고를 조회하지 않아요.')).toBeVisible();
  await page.getByRole('button', { name: '이 후보 승인하기' }).click();
  await expect(page.getByText('승인된 후보', { exact: true })).toBeVisible();
  await page.getByLabel('견적 수량').fill('100');
  await page.getByRole('button', { name: '견적서 저장' }).click();
  await expect(page.locator('.saved-quote').first()).toContainText('100');
  await page.getByRole('button', { name: '닫기', exact: true }).click();
  await page.reload();
  await page.locator('.candidate-card').first().click();
  await expect(page.getByText('승인된 후보', { exact: true })).toBeVisible();
  await expect(page.locator('.saved-quote').first()).toContainText('100');
  await page.getByRole('button', { name: '닫기', exact: true }).click();
  await page.getByRole('button', { name: '견적 목록', exact: true }).click();
  await expect(page.locator('.quote-item').first()).toContainText('100');
  await page.getByRole('button', { name: '닫기', exact: true }).click();
  // 사이드바 나무: 열린 대화는 그 프로젝트 아래에 강조되어 있고 ⋯ 메뉴로 그 자리에서 이름을 바꾼다
  await page.locator('.thread-row.selected').getByRole('button', { name: '대화 메뉴' }).click();
  await page.getByRole('menuitem', { name: '이름 변경' }).click();
  await page.getByLabel('대화 이름').fill('전원 입력 D1 검토');
  await page.getByLabel('대화 이름').press('Enter');
  await expect(page.locator('.thread-row.selected')).toContainText('전원 입력 D1 검토');
  await page.getByRole('link', { name: '승인 사례', exact: true }).click();
  await expect(page.locator('.case-list article').first()).toBeVisible();
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
  await expect(page.getByLabel('선호 실장 방식')).toHaveValue('smd');
  expect(errors).toEqual([]);
});

test('예/아니오 조건은 선택값을 보내고 모름으로 되돌려 실제 데모를 재개한다', async ({
  page,
}, testInfo) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 A', exact: true }).click();
  await expect(page).toHaveURL(/\/app/);
  const circuits = await (await page.request.get('/api/demo-circuits')).json();
  const circuit = circuits.find((c: { name: string }) => c.name === 'Franzininho DIY');
  expect(circuit).toBeTruthy();
  const created = await page.request.post('/api/projects?allow_duplicate=true', {
    headers: { Origin: new URL(page.url()).origin },
    data: { demo_id: circuit.id, name: `예·아니오 입력 ${Date.now()}` },
  });
  expect(created.status()).toBe(201);
  const project = await created.json();
  await page.goto(`/app?project=${project.id}`);
  await page.locator('[data-demo-id="demo-find"]').click();
  const card = page.getByTestId('requires-input');
  await expect(card).toBeVisible({ timeout: 45000 });
  const groups = card.getByRole('group');
  await expect(groups).toHaveCount(3);
  await expect(card.getByRole('textbox')).toHaveCount(0);
  for (const group of await groups.all()) {
    await expect(group.getByRole('radio', { name: '모름', exact: true })).toBeChecked();
  }
  const original = card.getByRole('group', { name: '원래 다이오드가 쇼트키인가요?' });
  const impedance = card.getByRole('group', { name: '보호하는 입력이 고임피던스인가요?' });
  await original.getByRole('radio', { name: '예', exact: true }).check();
  await original.getByRole('radio', { name: '예', exact: true }).press('ArrowRight');
  await expect(original.getByRole('radio', { name: '아니오', exact: true })).toBeChecked();
  await expect(original.getByRole('radio', { name: '예', exact: true })).not.toBeChecked();
  await impedance.getByRole('radio', { name: '예', exact: true }).check();
  await card.screenshot({ path: testInfo.outputPath('boolean-input-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button', { name: '회로 패널 닫기', exact: true }).click();
  await card.screenshot({ path: testInfo.outputPath('boolean-input-mobile.png') });
  await page.setViewportSize({ width: 1440, height: 1000 });
  // 실제 전송 본문을 확인한다. 기록과 다른 답의 검증 오류는 HTTP 200 SSE의 조건 질문으로 복구된다.
  const sent = page.waitForRequest(
    (r) => r.method() === 'POST' && /\/api\/runs\/[^/]+\/resume$/.test(r.url()),
  );
  const rejected = page.waitForResponse((r) => /\/api\/runs\/[^/]+\/resume$/.test(r.url()));
  await card.getByRole('button', { name: '이 값으로 계속 검토' }).click();
  expect((await sent).postDataJSON()).toEqual({
    answers: { orig_schottky: '아니오', high_impedance: '예' },
  });
  const rejectedResponse = await rejected;
  expect(rejectedResponse.status()).toBe(200);
  const rejectedEvents = await rejectedResponse.text();
  expect(rejectedEvents).toContain('event: requires_input');
  expect(rejectedEvents).toContain('키 없는 데모는 기록한 답');
  await page.waitForTimeout(2100);
  for (const group of await groups.all()) {
    await group.getByRole('radio', { name: '모름', exact: true }).check();
  }
  const resumed = page.waitForRequest(
    (r) => r.method() === 'POST' && /\/api\/runs\/[^/]+\/resume$/.test(r.url()),
  );
  await card.getByRole('button', { name: '이 값으로 계속 검토' }).click();
  expect((await resumed).postDataJSON()).toEqual({ answers: {} });
  await expect(card).toHaveCount(0, { timeout: 45000 });
  await expect(page.locator('.assistant-reply').last()).toBeVisible();
});

test('답변 표는 열 제목과 짧은 값을 유지하고 표 영역만 가로 스크롤한다', async ({
  page,
}, testInfo) => {
  await page.goto('/login');
  await page.getByRole('button', { name: '데모 사용자 A', exact: true }).click();
  await expect(page).toHaveURL(/\/app/);
  const circuits = await (await page.request.get('/api/demo-circuits')).json();
  const circuit = circuits.find((c: { name: string }) => c.name === 'Franzininho DIY');
  const created = await page.request.post('/api/projects?allow_duplicate=true', {
    headers: { Origin: new URL(page.url()).origin },
    data: { demo_id: circuit.id, name: `답변 표 너비 ${Date.now()}` },
  });
  expect(created.status()).toBe(201);
  const project = await created.json();
  await page.goto(`/app?project=${project.id}`);
  await page.waitForTimeout(2100);
  await page.locator('[data-demo-id="demo-find"]').click();
  await expect(page.getByTestId('requires-input')).toBeVisible({ timeout: 45000 });
  await page.waitForTimeout(2100);
  await page.getByRole('button', { name: '기록한 답으로 계속하기' }).click();
  await expect(page.locator('.candidate-card').first()).toBeVisible({ timeout: 45000 });
  await page.locator('.full-answer summary').click();
  const table = page.locator('.markdown table').first();
  await expect(table).toBeVisible();
  await expect(table.locator('th')).toHaveText([
    '조건',
    '기준',
    '후보 값',
    '시험 조건',
    '결과',
    '근거',
  ]);
  // 실제 텍스트 줄 수로 글자가 쪼개지는 현상을 검사한다.
  for (const cell of await table
    .locator(
      'th, tbody tr:first-child td:nth-child(1), tbody tr:first-child td:nth-child(3), tbody tr:first-child td:nth-child(4), tbody tr:first-child td:nth-child(5)',
    )
    .all()) {
    const lines = await cell.evaluate((element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      return range.getClientRects().length;
    });
    expect(lines, await cell.innerText()).toBe(1);
  }
  const desktopWidth = await table.evaluate((element) => element.getBoundingClientRect().width);
  const content = await table.innerText();
  const scroll = table.locator('..');
  await expect(scroll).toHaveClass('markdown-table-scroll');
  await expect(scroll).toHaveAttribute('tabindex', '0');
  await scroll.screenshot({ path: testInfo.outputPath('markdown-table-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '회로 패널 닫기', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  expect(await scroll.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
  expect(
    await table.evaluate((element) => element.getBoundingClientRect().width),
  ).toBeGreaterThanOrEqual(desktopWidth * 0.9);
  await expect(table).toHaveText(content.replace(/\s+/g, ' ').trim(), { useInnerText: true });
  await scroll.evaluate((element) => element.scrollIntoView({ block: 'center' }));
  await scroll.screenshot({ path: testInfo.outputPath('markdown-table-mobile.png') });
  await scroll.focus();
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => scroll.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
});
