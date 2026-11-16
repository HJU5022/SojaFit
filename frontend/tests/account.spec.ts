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
  await page.goto(first);
  await page.getByRole('button', { name: '회로 보기' }).click();
  await expect(page.getByLabel('회로의 다이오드')).toContainText('D1');
  await expect(page.getByLabel('회로의 다이오드')).not.toContainText('D2');
  // 사이드바 프로젝트 줄 ⋯ 메뉴로 이 시험의 프로젝트를 지운다(확인 창). 옛 /projects는 /app으로 바뀐다(#34)
  await page.goto('/projects');
  await expect(page).toHaveURL(/\/app$/);
  await page.getByRole('button', { name: name + ' 메뉴', exact: true }).click();
  await page.getByRole('menuitem', { name: '삭제' }).click();
  await page.getByRole('dialog').getByRole('button', { name: '삭제', exact: true }).click();
  await expect(page.getByRole('button', { name: name + ' 메뉴', exact: true })).toHaveCount(0);
});
