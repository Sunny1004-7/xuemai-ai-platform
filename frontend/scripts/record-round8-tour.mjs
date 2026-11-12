// 读取既有真实教学记录与正常接口新增单元，所有AI生成请求均由路由拦截阻止。
import path from 'node:path'
import { writeFile } from 'node:fs/promises'
import { expect } from '@playwright/test'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const base = 'http://127.0.0.1:5182'
const directory = path.join(root, '.local/round8-tour')
const recorder = await createRecorder({ base, directory })
const { page, click } = recorder
await page.route('**/api/ai/chat', route => route.abort())
const timeline = []
let origin
async function mark(name) {
  const at = (performance.now() - origin) / 1000
  timeline.push({ name, at })
  await recorder.mark(name)
  console.log(name, at.toFixed(2))
}
async function login(username) {
  await page.goto(base)
  if (await page.locator('.profile').isVisible()) await click(page.locator('.profile'))
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await click(page.getByRole('button', { name: '进入学脉', exact: true }))
  await expect(page.locator('.app-shell')).toBeVisible()
}
await recorder.start()
origin = performance.now()
try {
  await mark('登录诗句')
  await pause(3500)
  await click(page.getByRole('button', { name: '教师端', exact: true }))
  await pause(4500)
  await mark('学生回看辅导')
  await login('student1')
  await page.goto(base + '/tutor?course=1')
  await click(page.locator('.conversation-list button').filter({ hasText: '我在题目中选了1' }).first())
  await pause(1400)
  await page.locator('.chat-messages').hover()
  await page.mouse.wheel(0, -5000)
  await pause(1500)
  await mark('学生解释可读')
  await pause(11000)
  await mark('学生接收教师反馈')
  await page.goto(base + '/classroom?course=1')
  await pause(5500)
  const response = page.getByRole('textbox').first()
  if (await response.isVisible()) {
    await response.fill('栈按最后进入的元素先移出，队列按最先进入的元素先移出。撤销操作对应栈，排队服务对应队列。')
    const submit = page.getByRole('button', { name: /提交|发送/ }).first()
    if (await submit.isVisible()) await click(submit)
  }
  await pause(9500)
  await mark('教师回看反馈')
  await login('teacher')
  await page.goto(base + '/classroom?course=1')
  await pause(7000)
  await mark('新增原创单元')
  await page.goto(base + '/graph?course=3')
  await expect(page.locator('.knowledge-node').first()).toBeVisible()
  await pause(6000)
  await page.goto(base + '/resources?course=3')
  await pause(6500)
  await login('student1')
  await page.goto(base + '/practice?course=3')
  await pause(8500)
  await mark('Python课程学习')
  await page.goto(base + '/video?course=2')
  await expect(page.locator('video')).toBeVisible()
  await page.locator('video').evaluate(async video => { video.muted = true; await video.play() })
  await pause(12000)
  await page.goto(base + '/graph?course=2')
  await expect(page.locator('.knowledge-node').first()).toBeVisible()
  await pause(12000)
  await mark('补充演示结束')
} finally {
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
  await recorder.stop()
}
