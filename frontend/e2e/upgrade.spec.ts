import { test, expect } from '@playwright/test'

test('双端主题保持指定色值，登录布局在桌面完整可见', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.login-form')).toBeInViewport()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: '体验学生端', exact: true }).click()
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-role', 'student')
  expect(
    await page
      .locator('.app-shell')
      .evaluate((el) =>
        getComputedStyle(el).getPropertyValue('--brand-primary').trim().toUpperCase(),
      ),
  ).toBe('#2E6A67')
  await page.goto('/experiments')
  await expect(page.locator('.experiment-layout')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.locator('.profile').click()
  await page.getByRole('button', { name: '体验教师端', exact: true }).click()
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-role', 'teacher')
  await page.goto('/')
  await expect(page.locator('.teacher-desk')).toBeVisible()
  expect(
    await page
      .locator('.app-shell')
      .evaluate((el) =>
        getComputedStyle(el).getPropertyValue('--brand-primary').trim().toUpperCase(),
      ),
  ).toBe('#7E6554')
})

test('三十节点图谱支持主题分簇搜索先修和拖动', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '知识图谱', exact: true })
    .click()
  await expect(page.locator('.knowledge-node')).toHaveCount(30)
  await expect(page.locator('.knowledge-cluster')).toHaveCount(6)
  await page.getByLabel('定位知识点').fill('快速排序')
  await expect(page.locator('.node-detail h2')).toHaveText('快速排序')
  await page.getByRole('button', { name: '先修链', exact: true }).click()
  expect(await page.locator('.knowledge-node:not(.dim)').count()).toBeGreaterThan(1)
  const node = page.getByRole('button', { name: /快速排序，掌握度/ })
  const before = await node.getAttribute('transform'),
    box = await node.boundingBox()
  if (!box) throw new Error('节点没有位置')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 35, box.y + box.height / 2 + 20, { steps: 6 })
  await page.mouse.up()
  await expect(node).not.toHaveAttribute('transform', before!)
})

test('辅导结构化动作执行理解检查并在历史保留评分', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
  await page.goto('/tutor?knowledge=2&question=1')
  await page.getByLabel('输入学习问题').fill('请对照解释栈与队列，再检查我的理解。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.locator('.rich-text h3')).toContainText('栈与队列')
  await expect(
    page.locator('.teaching-actions').getByRole('link', { name: '逐步运行交互实验' }),
  ).toHaveAttribute('href', /mode=stack/)
  await page.locator('.understanding-check input').first().check()
  await page.getByRole('button', { name: '提交理解检查', exact: true }).click()
  await expect(page.locator('.understanding-check [role="status"]')).toBeVisible()
  await page.getByRole('button', { name: '对话历史', exact: true }).click()
  await page.locator('.conversation-list>button').nth(1).click()
  await expect(page.locator('.understanding-check [role="status"]')).toBeVisible()
})
