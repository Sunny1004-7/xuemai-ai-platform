import { test, expect } from '@playwright/test'

for (const role of ['student', 'teacher']) {
  test(`侧栏精简保留${role === 'teacher' ? '教师' : '学生'}导航与面包屑`, async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('账号', { exact: true }).fill(role === 'teacher' ? 'teacher' : 'student1')
    await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
    await page.getByRole('button', { name: '进入学脉', exact: true }).click()
    const sidebar = page.locator('.sidebar')
    await expect(page.locator('.app-shell')).toHaveAttribute('data-role', role)
    for (const viewport of [{ width: 1440, height: 900 }, { width: 1366, height: 650 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport)
      await expect(sidebar.locator('.workspace-label')).toHaveCount(0)
      await expect(sidebar).not.toContainText(/学习空间|学生端|教学空间|教师端/)
      await expect(sidebar.getByRole('navigation', { name: '主导航' }).getByRole('link')).toHaveCount(role === 'teacher' ? 9 : 10)
      await expect(page.locator('.breadcrumb')).toContainText(role === 'teacher' ? '教学空间' : '学习空间')
      await expect(sidebar.locator('.profile')).toBeVisible()
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.getByLabel('收起或展开导航').click()
    await expect(page.locator('.app-shell')).toHaveClass(/nav-collapsed/)
    await sidebar.getByRole('link', { name: '知识图谱', exact: true }).click()
    await expect(page.locator('.graph-canvas')).toBeVisible()
    await page.getByLabel('收起或展开导航').click()
    await expect(page.locator('.app-shell')).not.toHaveClass(/nav-collapsed/)
    await sidebar.locator('.profile').click()
    await expect(page.getByLabel('账号', { exact: true })).toBeVisible()
  })
}
