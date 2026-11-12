// 回看本次已生成的真实会话，补足解释与方案的阅读时间，不发送新模型请求。
import path from 'node:path'
import { expect } from '@playwright/test'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5182'
const studentOnly = process.env.DEMO_STUDENT_ONLY === '1'
const recorder = await createRecorder({ base, directory: path.join(root, studentOnly ? '.local/round7-student-review' : '.local/round7-response-review') })
const { page, click } = recorder
async function login(username) {
  await page.goto(base)
  if (await page.locator('.profile').isVisible()) await click(page.locator('.profile'))
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await click(page.getByRole('button', { name: '进入学脉', exact: true }))
  await expect(page.locator('.app-shell')).toBeVisible()
}
async function readTop() {
  await pause(1100)
  await page.locator('.chat-messages').hover()
  await page.mouse.wheel(0, -5000)
  await pause(900)
  await page.locator('.chat-message.assistant .message-label').first().scrollIntoViewIfNeeded()
  await pause(600)
}
await login('student1')
await page.goto(base + '/tutor?course=1')
await click(page.locator('.conversation-list button').filter({ hasText: '我在题目中选了1' }).first())
await readTop()
await recorder.start()
try {
  await recorder.mark('回看学生解释与附件引用')
  await pause(12000)
  await page.mouse.wheel(0, 280)
  await pause(6000)
  if (!studentOnly) {
  await login('teacher')
  await page.goto(base + '/teacher-ai?course=1')
  await click(page.locator('.conversation-list button').filter({ hasText: '请依据这个班' }).first())
  await readTop()
  await recorder.mark('回看教师证据与方案')
  await pause(9000)
  await page.mouse.wheel(0, 310)
  await pause(11000)
  }
} finally {
  await recorder.stop()
}
