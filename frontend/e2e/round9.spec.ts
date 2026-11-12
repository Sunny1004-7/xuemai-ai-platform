import { test, expect } from '@playwright/test'

test('外围背景共用静态构图且不改变卡片与键盘操作', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1366, height: 650 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    for (const role of ['学生端', '教师端']) {
      await page.getByRole('button', { name: role, exact: true }).click()
      const card = await page.locator('.login-scene').boundingBox()
      const decoration = page.locator('.login-backdrop')
      await expect(decoration).toHaveAttribute('aria-hidden', 'true')
      expect(await decoration.evaluate(element => getComputedStyle(element).pointerEvents)).toBe('none')
      expect(await decoration.locator('button, input, a, [tabindex]').count()).toBe(0)
      expect(await decoration.evaluate(element => element.getAnimations({ subtree: true }).length)).toBe(0)
      await decoration.evaluate(element => { (element as HTMLElement).style.display = 'none' })
      expect(await page.locator('.login-scene').boundingBox()).toEqual(card)
      await decoration.evaluate(element => { (element as HTMLElement).style.display = '' })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      const expected = role === '学生端' ? 'rgb(18, 47, 48)' : 'rgb(52, 43, 38)'
      expect(await page.locator('.login-page').evaluate(element => getComputedStyle(element).backgroundColor)).toBe(expected)
    }
  }
  await page.getByLabel('账号', { exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('密码', { exact: true })).toBeFocused()
  await page.getByRole('button', { name: '显示密码', exact: true }).click()
  await expect(page.getByLabel('密码', { exact: true })).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: '隐藏密码', exact: true }).click()
  await page.getByLabel('密码', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-role', 'teacher')
})
