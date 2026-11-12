import path from 'node:path'
import { expect } from '@playwright/test'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5181'
const recorder = await createRecorder({ base, directory: path.join(root, '.local/round7-motion-sample') })
const { page, click, mark } = recorder
await page.getByLabel('账号', { exact: true }).fill('student1')
await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
await click(page.getByRole('button', { name: '进入学脉', exact: true }))
await expect(page.locator('.app-shell')).toBeVisible()
await page.goto(base + '/graph?course=1')
await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy', 'false')
await recorder.start()
try {
  await mark('图谱连续平移')
  const box = await page.locator('.graph-canvas').boundingBox()
  await page.mouse.move(box.x + 100, box.y + 90)
  await page.mouse.down()
  for (let step = 0; step <= 240; step++) {
    await page.mouse.move(box.x + 100 + step * 1.1, box.y + 90 + Math.sin(step / 45) * 60)
    await pause(5)
  }
  await page.mouse.up()
  await mark('搜索与关系聚焦', async () => { await page.getByLabel('定位知识点').fill('栈与队列') })
  await pause(2000)
  await page.goto(base + '/experiments?course=1&mode=stack')
  await mark('栈操作连续动画')
  await page.getByLabel('待加入元素').fill('48')
  await click(page.getByRole('button', { name: '压栈', exact: true }))
  await pause(1400)
  await click(page.getByRole('button', { name: '出栈', exact: true }))
  await pause(1400)
  await click(page.getByRole('button', { name: '回放操作过程', exact: true }))
  await pause(3500)
} finally {
  await recorder.stop()
}
