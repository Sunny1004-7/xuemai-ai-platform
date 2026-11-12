import { test, expect } from '@playwright/test'

test('双身份登录诗句保持表单位置与完整可读', async ({ page }) => {
  await page.goto('/')
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1366, height: 650 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    await page.getByRole('button', { name: '学生端', exact: true }).click()
    await expect(page.locator('.login-form h1')).toHaveText('读书破万卷，下笔如有神。')
    const studentForm = await page.locator('.login-form').boundingBox()
    await page.getByRole('button', { name: '教师端', exact: true }).click()
    await expect(page.locator('.login-form h1')).toHaveText('随风潜入夜，润物细无声。')
    const teacherForm = await page.locator('.login-form').boundingBox()
    expect(teacherForm?.y).toBe(studentForm?.y)
    const geometry = await page.locator('.login-form h1').evaluate(element => ({
      width: element.clientWidth, scroll: element.scrollWidth,
      zoom: window.devicePixelRatio,
    }))
    expect(geometry.scroll).toBeLessThanOrEqual(geometry.width)
  }
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-role', 'teacher')
})

test('短窗口完整显示师生全部导航项', async ({ page }) => {
  for (const role of ['学生端', '教师端']) {
    await page.goto('/')
    if (await page.locator('.profile').isVisible()) await page.locator('.profile').click()
    await page.getByRole('button', { name: role, exact: true }).click()
    await page.getByRole('button', { name: '进入学脉', exact: true }).click()
    await expect(page.locator('.app-shell')).toBeVisible()
    for (const height of [768, 650]) {
      await page.setViewportSize({ width: 1366, height })
      const sizes = await page.locator('.sidebar nav').evaluate(nav => {
        const bounds = nav.getBoundingClientRect()
        return { bottom: bounds.bottom,
          height: nav.clientHeight, scroll: nav.scrollHeight,
          links: [...nav.querySelectorAll('a')].map(link => link.getBoundingClientRect().bottom) }
      })
      expect(sizes.scroll).toBeLessThanOrEqual(sizes.height + 1)
      expect(Math.max(...sizes.links)).toBeLessThanOrEqual(sizes.bottom + 1)
    }
  }
})
