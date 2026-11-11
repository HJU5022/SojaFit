import { expect, test } from '@playwright/test'

test('lays out the circuit concept with net junctions and non-overlapping component blocks', async ({ page }) => {
  await page.goto('/app')
  await page.getByRole('button', { name: '프로젝트', exact: true }).click()
  await page.getByRole('button', { name: 'breadboard_supply', exact: true }).click()
  await page.getByRole('button', { name: '회로', exact: true }).click()
  await page.getByLabel('대상 부품').selectOption('C1')
  await page.getByRole('tab', { name: '연결 개념도' }).click()

  const diagram = page.getByRole('img', { name: /주변 연결 개념도/ })
  await expect(diagram).toHaveAttribute('data-layout', 'worker')
  await expect(diagram.locator('[data-kind="net"]')).not.toHaveCount(0)
  await expect(diagram.locator('.context-edge path')).not.toHaveCount(0)
  await expect(diagram.locator('.context-edge line')).toHaveCount(0)

  const overlappingPairs = await diagram.evaluate(svg => {
    const boxes = [...svg.querySelectorAll<SVGGElement>('.context-node, .context-junction, .context-overflow')]
      .map(node => ({ id: node.getAttribute('aria-label') ?? node.textContent ?? '', box: node.getBBox() }))
    const overlaps: string[] = []
    for (let left = 0; left < boxes.length; left += 1) {
      for (let right = left + 1; right < boxes.length; right += 1) {
        const a = boxes[left]
        const b = boxes[right]
        if (a.box.x < b.box.x + b.box.width && a.box.x + a.box.width > b.box.x
          && a.box.y < b.box.y + b.box.height && a.box.y + a.box.height > b.box.y) {
          overlaps.push(`${a.id} / ${b.id}`)
        }
      }
    }
    return overlaps
  })
  expect(overlappingPairs).toEqual([])
})
