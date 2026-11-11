import { test, expect, type Page } from '@playwright/test'
async function login(page: Page, role: string) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill(role === 'student' ? 'student1' : 'teacher')
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toBeVisible()
  await expect(page.locator('main h1')).toBeVisible()
}
for (const role of ['student', 'teacher'])
  for (const course of [1, 2])
    test(`第五轮首屏 ${role} 课程${course}`, async ({ page }) => {
      test.setTimeout(180000)
      await login(page, role)
      const routes =
        role === 'student'
          ? [
              '/',
              '/plan',
              '/video',
              '/resources',
              '/graph',
              '/practice',
              '/review',
              '/tutor',
              '/experiments',
              '/classroom',
            ]
          : [
              '/',
              '/manage',
              '/graph',
              '/resources',
              '/practice',
              '/video',
              '/analytics',
              '/classroom',
            ]
      const errors: string[] = []
      page.on('pageerror', (e) => errors.push(e.message))
      for (const viewport of [
        { width: 1920, height: 1080 },
        { width: 1440, height: 900 },
        { width: 1366, height: 768 },
        { width: 1366, height: 650 },
      ]) {
        await page.setViewportSize(viewport)
        for (const route of routes) {
          await page.goto(`${route}?course=${course}`)
          await expect(page.locator('main h1')).toBeVisible()
          await expect(page.locator('main .loading')).toHaveCount(0)
          if (route === '/graph') {
            await expect(page.locator('.knowledge-node').first()).toBeVisible()
            await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy','false')
            await expect.poll(()=>page.locator('.graph-canvas').evaluate(canvas=>{
              const box=canvas.getBoundingClientRect()
              return [...canvas.querySelectorAll('.knowledge-node')].every(node=>{
                const r=node.getBoundingClientRect()
                return r.left>=box.left&&r.right<=box.right&&r.top>=box.top&&r.bottom<=box.bottom
              })
            })).toBe(true)
          }
          const m = await page.evaluate(() => ({
            height: document.scrollingElement!.scrollHeight,
            client: innerHeight,
            width: document.scrollingElement!.scrollWidth,
            viewport: innerWidth,
            zoom: devicePixelRatio,
          }))
          expect(m.height, `${route} ${viewport.height} 整页高度`).toBeLessThanOrEqual(m.client + 2)
          expect(m.width).toBeLessThanOrEqual(m.viewport + 2)
          const controls = await page
            .locator(
              'main .workspace-pager:visible,main .question-navigation:visible,main .chat-composer:visible,main .experiment-controls:visible',
            )
            .evaluateAll(elements => elements.map(element => {
              const box = element.getBoundingClientRect()
              return { bottom: box.bottom, height: box.height }
            }))
          for (const box of controls) {
            expect(box.height, route).toBeGreaterThan(0)
            expect(box.bottom, route).toBeLessThanOrEqual(viewport.height + 2)
          }
        }
      }
      expect(errors).toEqual([])
    })
test('第五轮课程选择器键盘操作和课程上下文清理', async ({ page }) => {
  await login(page, 'student')
  await page.goto('/graph?course=1&knowledge=6&chapter=1')
  await page.getByLabel('切换当前课程').click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/course=2/)
  await expect(page).not.toHaveURL(/knowledge|chapter/)
  await expect(page.locator('.knowledge-node')).toHaveCount(27)
  await expect(page.getByLabel('切换当前课程')).toBeFocused()
  await page.getByLabel('切换当前课程').click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await page.reload()
  await expect(page.getByLabel('切换当前课程')).toContainText('Python')
  await page.goBack()
  await expect(page.getByLabel('切换当前课程')).toContainText('数据结构')
})
test('第五轮Python导航、辅导历史、实验和归档回答', async ({ page }) => {
  await login(page, 'student')
  await page.goto('/practice?course=2')
  for (let i = 1; i <= 10; i++) {
    await page.getByRole('button', { name: `跳转第${i}题`, exact: true }).click()
    await expect(page.locator('.question-meta')).toContainText(`第 ${i} /`)
  }
  await page.goto('/tutor?course=2')
  await page.locator('.conversation-list>button:not(.button)').first().click()
  await expect(page.locator('.chat-message')).toHaveCount(4)
  await page.getByLabel('输入学习问题').fill('请用另一个边界例子继续说明')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.locator('.chat-message')).toHaveCount(6)
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0)
  await page.goto('/experiments?course=2&mode=py-loop')
  await expect(page.locator('main h1')).toContainText('Python')
  await page.getByRole('button', { name: '下一步', exact: true }).click()
  await page.getByRole('button', { name: '下一步', exact: true }).click()
  await page.getByRole('button', { name: '保存实验记录', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('实验记录已保存')
  await page.goto('/classroom?course=2')
  await page.locator('.activity-list button').filter({ hasText: '已结束' }).first().click()
  await expect(page.getByLabel('历史回答')).toContainText('我的历史回答')
})
test('第五轮窄屏计划正文保留足够阅读宽度',async({page})=>{
  await page.setViewportSize({width:390,height:844})
  await login(page,'student')
  for(const course of [1,2]){
    await page.goto(`/plan?course=${course}`)
    await expect(page.locator('.personal-plan-list h3').first()).toBeVisible()
    const width=await page.locator('.personal-plan-list>div>div:nth-child(2)').first().evaluate(e=>e.getBoundingClientRect().width)
    expect(width).toBeGreaterThan(180)
    await expect(page.locator('.plan-item-actions').first()).toBeVisible()
  }
})
