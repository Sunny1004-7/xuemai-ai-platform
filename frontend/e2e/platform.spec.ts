import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, username: string) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉' }).click()
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
}

test('教师发布作业，学生真实提交，教师查看结果与学情', async ({ browser }) => {
  const errors: string[] = []
  const teacher = await browser.newContext()
  const student = await browser.newContext()
  const tp = await teacher.newPage()
  const sp = await student.newPage()
  for (const page of [tp, sp]) page.on('pageerror', (e) => errors.push(e.message))
  await login(tp, 'teacher')
  await tp.getByRole('link', { name: '题库与作业', exact: true }).click()
  await tp.getByRole('button', { name: '发布作业', exact: true }).click()
  const title = `师生闭环验证${Date.now()}`
  const dialog = tp.getByRole('dialog')
  await dialog.getByLabel('作业标题').fill(title)
  await dialog.getByLabel('发布到班级').selectOption('1')
  await dialog.getByRole('checkbox').first().check()
  await dialog.getByRole('button', { name: '发布作业', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(tp.getByRole('heading', { name: title, exact: true })).toBeVisible()
  await login(sp, 'student1')
  await sp.getByRole('link', { name: '智能练习', exact: true }).click()
  await sp.getByRole('button', { name: title, exact: true }).click()
  await sp.getByRole('radio').nth(2).check()
  await sp.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(sp.getByText('思路清晰，回答正确')).toBeVisible()
  await tp.reload()
  const row = tp.locator('.assignment-row').filter({ hasText: title })
  await row.getByRole('button', { name: '查看结果' }).click()
  await expect(row.getByText('陈星河', { exact: true })).toBeVisible()
  await expect(row.getByText('已完成', { exact: true })).toBeVisible()
  await tp.getByRole('link', { name: '学情与分层', exact: true }).click()
  await expect(tp.locator('main')).toContainText('掌握')
  expect(errors).toEqual([])
  await teacher.close()
  await student.close()
})

test('知识图谱定位视频、真实播放、时间戳笔记持久化', async ({ page }) => {
  await login(page, 'student1')
  await page.goto('/video?t=10')
  const video = page.locator('video')
  await expect(video).toBeVisible()
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(1)
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThanOrEqual(9)
  await video.evaluate((v: HTMLVideoElement) => {
    v.muted = true
    return v.play()
  })
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThan(10)
  await video.evaluate((v: HTMLVideoElement) => v.pause())
  await page.getByRole('button', { name: /我的笔记/ }).click()
  const note = `视频定位笔记${Date.now()}`
  await page.getByPlaceholder('想明白了什么？还有什么问题？').fill(note)
  await page.getByRole('button', { name: '保存笔记' }).click()
  await expect(page.getByText(note, { exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: /我的笔记/ }).click()
  await expect(page.getByText(note, { exact: true })).toBeVisible()
})

test('双端主要页面无崩溃，窄屏无横向溢出', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await login(page, 'student1')
  for (const route of ['/graph', '/courses', '/review', '/experiments', '/classroom', '/tutor']) {
    await page.goto(route)
    await expect(page.locator('main h1')).toBeVisible()
    await expect(page.locator('main')).not.toContainText('Internal Server Error')
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('main h1')).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
  await page.screenshot({ path: 'test-results/student-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.screenshot({ path: 'test-results/student-dashboard.png', fullPage: true })
  expect(errors).toEqual([])
})
