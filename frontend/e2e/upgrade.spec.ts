import { test, expect } from '@playwright/test'

test('双端主题保持指定色值，登录布局在桌面完整可见', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.login-form')).toBeInViewport()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: '学生端', exact: true }).click()
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
  await page.getByRole('button', { name: '教师端', exact: true }).click()
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

test('渐进图谱支持章节展开搜索全屏小地图与平移', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toBeVisible()
  await page.goto('/graph')
  await expect(page.locator('.knowledge-node')).toHaveCount(6)
  await page.getByRole('button', {name:/线性结构，展开章节/}).click()
  await expect(page.getByRole('button',{name:/循环队列，掌握度/})).toBeVisible()
  await page.getByLabel('定位知识点').fill('快速排序')
  await expect(page.locator('.node-detail h2')).toHaveText('快速排序')
  await page.getByRole('button', { name: '先修链', exact: true }).click()
  expect(await page.locator('.knowledge-node').count()).toBeGreaterThan(1)
  const cameraBefore = await page.locator('.graph-canvas>svg>g').getAttribute('transform')
  await page.getByRole('button',{name:'全屏查看',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'全屏知识图谱'})).toBeVisible()
  await expect(page.getByLabel('图谱小地图')).toBeVisible()
  await page.getByRole('button',{name:'放大图谱'}).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog',{name:'全屏知识图谱'})).toHaveCount(0)
  await expect(page.locator('.graph-canvas>svg>g')).toHaveAttribute('transform', cameraBefore!)
  const g=page.locator('.graph-canvas>svg>g')
  const before=await g.getAttribute('transform')
  const svg=page.locator('.graph-canvas>svg').first()
  const box=await svg.boundingBox()
  if (!box) throw new Error('图谱缺少画布')
  await page.mouse.move(box.x+20,box.y+70)
  await page.mouse.down();await page.mouse.move(box.x+80,box.y+95,{steps:6});await page.mouse.up()
  await expect(g).not.toHaveAttribute('transform',before!)
  await page.getByRole('button',{name:'全图',exact:true}).click()
  await expect(page.locator('.knowledge-node')).toHaveCount(31)
  await page.getByRole('button',{name:'收起知识详情'}).click()
  for (const viewport of [{width:1920,height:1080},{width:1440,height:1000},{width:1366,height:768},{width:390,height:844}]) {
    await page.setViewportSize(viewport)
    await page.getByRole('button',{name:'重置图谱视角'}).click()
    await expect.poll(() => page.locator('.graph-canvas').evaluate(canvas => {
      const box = canvas.getBoundingClientRect()
      return [...canvas.querySelectorAll('.knowledge-node .node-body')].every(node => {
        const r = node.getBoundingClientRect()
        return r.left>=box.left && r.right<=box.right && r.top>=box.top && r.bottom<=box.bottom
      })
    })).toBe(true)
  }
  await page.getByRole('button',{name:'聚焦阅读',exact:true}).click()
  await expect(page.locator('.graph-controls > span')).toHaveText('115%')
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
    page.locator('.teaching-actions').getByRole('link', { name: '查看概念与先修关系' }),
  ).toHaveAttribute('href', /graph\?/ )
  await page.locator('.understanding-check input').first().check()
  await page.getByRole('button', { name: '提交理解检查', exact: true }).click()
  await expect(page.locator('.understanding-check [role="status"]')).toBeVisible()
  await page.getByRole('button', { name: '对话历史', exact: true }).click()
  await page.locator('.conversation-list>button').nth(1).click()
  await expect(page.locator('.understanding-check [role="status"]')).toBeVisible()
})
