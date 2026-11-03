import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const output = path.join(root, 'docs/screenshots')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
for (const role of ['student1', 'teacher']) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } })
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:5173')
  await page.getByLabel('账号', { exact: true }).fill(role)
  await page.getByRole('button', { name: '进入学脉' }).click()
  await page.getByRole('navigation', { name: '主导航' }).waitFor()
  await page.locator('.loading').waitFor({ state: 'hidden' })
  if (role === 'student1') {
    await page.screenshot({ path: path.join(output, 'student-dashboard.png'), fullPage: true })
    await page.goto('http://127.0.0.1:5173/graph?knowledge=6')
    await page.getByRole('button', { name: /冒泡排序，掌握度/ }).waitFor()
    await page.screenshot({ path: path.join(output, 'knowledge-graph.png'), fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('http://127.0.0.1:5173')
    await page.locator('.loading').waitFor({ state: 'hidden' })
    await page.screenshot({ path: path.join(output, 'student-mobile.png'), fullPage: true })
  } else {
    await page.goto('http://127.0.0.1:5173/analytics')
    await page.locator('.knowledge-analysis').waitFor()
    await page.locator('.loading').waitFor({ state: 'hidden' })
    await page.screenshot({ path: path.join(output, 'teacher-analytics.png'), fullPage: true })
  }
  await context.close()
}
await browser.close()
console.log('已保存师生桌面、知识图谱与390px窄屏实际截图；未调用真实AI。')
