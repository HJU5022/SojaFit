import { expect, test } from '@playwright/test'

test('serves a verified original circuit image to the browser', async ({ page }) => {
  const response = await page.goto('/circuit-schematics/mosfet_driver.png')
  expect(response?.status()).toBe(200)
  expect(response?.headers()['content-type']).toBe('image/png')
  const image = page.locator('img')
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
})

test('keeps the analysis composer compact at the bottom of the workbench', async ({ page }) => {
  await page.setViewportSize({ width: 1328, height: 864 })
  await page.goto('/app')
  await page.getByRole('button', { name: '프로젝트', exact: true }).click()
  await page.getByRole('button', { name: 'breadboard_supply', exact: true }).click()
  const workbench = await page.getByRole('main', { name: '분석 대화 작업면' }).boundingBox()
  const composer = await page.locator('.composer').boundingBox()
  expect(composer?.height).toBeLessThan(200)
  expect(Math.abs(((composer?.y ?? 0) + (composer?.height ?? 0)) - ((workbench?.y ?? 0) + (workbench?.height ?? 0)))).toBeLessThanOrEqual(2)
  expect((composer?.y ?? 0) + (composer?.height ?? 0)).toBeLessThanOrEqual(864)
  await page.getByRole('button', { name: '사용 조건 추가(선택)' }).click()
  await page.locator('.optional-conditions').evaluate(async element => {
    await Promise.all(element.getAnimations().map(animation => animation.finished))
  })
  const question = await page.getByLabel('질문').boundingBox()
  const conditions = await page.getByLabel('사용 조건 (선택)').boundingBox()
  const closeConditions = page.getByRole('button', { name: '사용 조건 닫기' })
  const closeBox = await closeConditions.boundingBox()
  expect(question?.y ?? 0).toBeLessThan(conditions?.y ?? 0)
  expect((conditions?.y ?? 0) + (conditions?.height ?? 0)).toBeLessThanOrEqual(closeBox?.y ?? 0)
  await expect(closeConditions).toBeInViewport()
  await expect.poll(() => page.locator('.optional-conditions').evaluate(element => getComputedStyle(element).animationName)).toBe('optional-conditions-reveal')
})

test('keeps content width stable and only reveals overlay controls at the scrollbar edge', async ({ page }) => {
  await page.setViewportSize({ width: 1328, height: 864 })
  await page.goto('/app')
  const surface = page.locator('.analysis-surface')
  const widthBefore = await surface.evaluate(element => element.clientWidth)
  const overlay = page.locator('.overlay-scrollbar')
  await expect(overlay).not.toHaveClass(/active/)
  const box = await surface.boundingBox()
  await page.mouse.move((box?.x ?? 0) + (box?.width ?? 0) - 12, (box?.y ?? 0) + 20)
  await expect(overlay).toHaveClass(/active/)
  await expect(overlay).toBeVisible()
  expect(await surface.evaluate(element => element.clientWidth)).toBe(widthBefore)
  const thumb = page.locator('.overlay-scrollbar-thumb')
  const thumbBox = await thumb.boundingBox()
  await page.mouse.move((thumbBox?.x ?? 0) + (thumbBox?.width ?? 0) / 2, (thumbBox?.y ?? 0) + (thumbBox?.height ?? 0) / 2)
  await page.mouse.down()
  await page.mouse.move((thumbBox?.x ?? 0) + (thumbBox?.width ?? 0) / 2, (thumbBox?.y ?? 0) + (thumbBox?.height ?? 0) / 2 + 100)
  await page.mouse.up()
  await expect.poll(() => surface.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  await page.mouse.move((box?.x ?? 0) + (box?.width ?? 0) / 2, (box?.y ?? 0) + 20)
  await expect(overlay).not.toHaveClass(/active/)
  expect(await surface.evaluate(element => element.clientWidth)).toBe(widthBefore)
})

test('shows every verified original inside the workbench', async ({ page }) => {
  await page.goto('/app')
  for (const [project, circuitName, image] of [
    ['breadboard_supply', 'SparkFun Breadboard Power Supply 5V/3.3V', 'breadboard_supply.png'],
    ['mosfet_driver', 'Adafruit MOSFET Driver STEMMA', 'mosfet_driver.png'],
    ['attiny85_dev', 'ATtiny85 dev board', 'attiny85_dev.png'],
    ['franzininho_diy', 'Franzininho DIY', 'franzininho_diy.png'],
    ['pro_micro', 'SparkFun Pro Micro v13', 'pro_micro.png'],
    ['attiny85_time_switch', 'ATtiny85 Time Switch', 'attiny85_time_switch.png'],
    ['fc_rom_vomitter', 'FC ROM Vomitter', 'fc_rom_vomitter.png'],
    ['attiny2313a_thermostat', 'ATtiny2313A Thermostat', 'attiny2313a_thermostat.png'],
    ['tiny85_fan_control', 'tiny85 Fan Control', 'tiny85_fan_control.png'],
    ['ug56_pwm_controller', 'UG56 PWM Controller', 'ug56_pwm_controller.png'],
    ['car_radio_acc_delay', 'Car Radio ACC Delay', 'car_radio_acc_delay.png'],
    ['overengineered_psu', 'OverEngineered PSU', 'overengineered_psu.png'],
    ['tinydimmer', 'tinydimmer', 'tinydimmer.png'],
    ['hrem', 'HRem', 'hrem.png'],
    ['zr7_taillight', 'ZR7 Taillight', 'zr7_taillight.png'],
  ] as const) {
    await page.getByRole('button', { name: '프로젝트', exact: true }).click()
    await page.getByRole('button', { name: project, exact: true }).click()
    await page.getByRole('button', { name: '회로', exact: true }).click()
    await expect(page.getByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
    const original = page.getByRole('img', { name: `${circuitName} 원본 회로도` })
    await expect(original).toHaveAttribute('src', `/circuit-schematics/${image}`)
    await expect.poll(() => original.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await page.getByLabel('대상 부품').selectOption({ index: 1 })
    await page.getByRole('tab', { name: '연결 개념도' }).click()
    await expect(page.getByRole('img', { name: /주변 연결 개념도/ })).toBeVisible()
  }
})

test('verified concept and datasheet flow', async ({ page }) => {
  await page.goto('/app')
  await page.getByRole('button', { name: '프로젝트', exact: true }).click()
  await page.getByRole('button', { name: 'breadboard_supply', exact: true }).click()
  await page.getByRole('button', { name: '회로', exact: true }).click()
  await expect(page.getByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: '연결 개념도' }).click()
  await page.getByLabel('대상 부품').selectOption('D1')
  await expect(page.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'D1 노드', exact: true })).toHaveClass(/target/)
  await page.getByLabel('질문').fill('D1을 SS34L로 바꿔도 되나요?')
  await page.getByRole('button', { name: '분석하기' }).click()
  await page.getByRole('tab', { name: '후보 비교' }).click()
  await page.getByRole('button', { name: 'SS34L 후보 선택' }).click()
  await page.getByRole('tab', { name: '근거', exact: true }).click()
  const official = page.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })
  await expect(official).toHaveAttribute('href', 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf#page=1')
  await expect(official).toHaveAttribute('target', '_blank')
  await expect(official).toHaveAttribute('rel', 'noreferrer noopener')
  await expect(page.getByRole('link', { name: '패키지 외형 4쪽 열기' })).toHaveAttribute('href', /#page=4$/)
  await expect(page.getByText('패키지가 달라질 수 있다는 뜻이며 납땜·재배선 방법을 뜻하지 않습니다.')).toBeVisible()
  await expect(page.getByRole('region', { name: '근거', exact: true })).not.toContainText('바로 교체')
})

test('shows a completed D5 judgement from the local development dummy', async ({ page }) => {
  await page.goto('/app?projectId=1')
  await page.getByLabel('대상 부품').selectOption('D1')
  await page.getByLabel('질문').fill('D1을 SS34L로 바꿔도 되나요?')
  await page.getByRole('button', { name: '분석하기' }).click()
  await page.getByRole('tab', { name: '근거' }).click()
  await expect(page.getByText('SS34L SERIES_C2103.pdf')).toBeVisible()
  await page.getByRole('tab', { name: '후보 비교' }).click()
  await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
  await expect(page.getByText('같은 동작은 보장하지 않습니다.')).toBeVisible()
})
