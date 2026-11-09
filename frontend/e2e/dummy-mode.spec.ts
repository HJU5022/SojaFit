import { expect, test } from '@playwright/test'

test('completes the interactive development dummy flow without route interception', async ({ page }) => {
  await page.goto('/app')
  await expect(page.getByText('더미 실행 모드 · 저장되지 않음')).toBeVisible()

  await page.getByRole('button', { name: 'breadboard_supply' }).click()
  await page.getByLabel('대상 부품').selectOption('D1')
  await expect(page.getByText('D1 / 1N4001')).toBeVisible()

  await page.getByLabel('질문').fill('D1을 SS34로 바꿔도 되나요?')
  await page.getByRole('button', { name: 'D5에 질문하기' }).click()
  await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
  await expect(page.getByText('SS34.pdf')).toBeVisible()

  await page.getByLabel('승인할 후보').selectOption('0')
  await page.getByRole('button', { name: '판정 승인 확인' }).click()
  await page.getByRole('button', { name: '확인 후 승인' }).click()
  await expect(page.getByText('SS34 판정을 승인했습니다.')).toBeVisible()
  await expect(page.getByText('SS34 · ROLE_SUFFICIENT')).toBeVisible()

  await page.getByRole('button', { name: '견적 열기' }).click()
  await page.getByRole('button', { name: '가격·재고 조회' }).last().click()
  await expect(page.getByText('1.23 USD')).toBeVisible()
  await page.getByLabel('수량').fill('2')
  await page.getByRole('button', { name: '가격 없이 견적 저장' }).click()
  await expect(page.getByText('SS34 2개 견적을 저장했습니다. 가격은 저장하지 않았습니다.')).toBeVisible()

  await page.getByRole('button', { name: '사례 삭제' }).click()
  await page.getByRole('button', { name: '삭제 확인' }).click()
  await expect(page.getByText('저장된 승인 사례가 없습니다.')).toBeVisible()
})
