import { test, expect, type Page } from '@playwright/test'
import { existsSync } from 'node:fs'

async function login(page: Page, teacher = false) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill(teacher ? 'teacher' : 'student1')
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await expect(page.locator('.app-shell')).toBeVisible()
}

test('分组导航与教师帮助保留课程上下文，短窗口导航可达', async ({ page }) => {
  await login(page, true)
  await page.setViewportSize({ width: 1366, height: 650 })
  await page.goto('/analytics?course=2')
  for (const group of ['教学组织', '备课与资源', '教学实施', '分析与研讨']) await expect(page.getByRole('heading', { name: group, exact: true })).toBeVisible()
  const assistant = page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: 'AI 教学助手' })
  await assistant.scrollIntoViewIfNeeded()
  await assistant.click()
  await expect(page).toHaveURL(/teacher-ai/)
  await page.getByLabel('帮助', { exact: true }).click()
  await expect(page).toHaveURL(/course=2/)
  await expect(page.locator('.app-shell')).toHaveAttribute('data-role', 'teacher')
})

test('模型与文档附件进入问答，引用位置和历史消息可重开', async ({ page }) => {
  await login(page)
  await page.goto('/tutor?course=1')
  await page.getByLabel('选择AI模型').selectOption('deepseek-v4-pro')
  await page.getByLabel('选择问答附件').setInputFiles({ name: '队列课后笔记.md', mimeType: 'text/markdown', buffer: Buffer.from('队列保持先进先出，广度优先搜索中先发现的节点先处理。') })
  await expect(page.locator('.composer-attachments')).toContainText('队列课后笔记.md')
  await page.locator('#chat-input').fill('根据笔记说明队列先进先出。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0)
  await expect(page.locator('.chat-message.assistant .message-label')).toContainText('DeepSeek Pro')
  await expect(page.locator('.message-sources')).toContainText('队列课后笔记.md')
  await page.locator('.message-sources button').filter({ hasText: '队列课后笔记.md' }).first().click()
  await expect(page.getByRole('dialog')).toContainText('段')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.reload()
  await page.locator('.conversation-list > button:not(.button)').first().click()
  await expect(page.locator('.chat-message.assistant .message-label')).toContainText('DeepSeek Pro')
  await expect(page.locator('.message-attachments').first()).toContainText('队列课后笔记.md')
})

test('教师从班级证据生成草稿，编辑保存并带群组进入作业发布', async ({ page }) => {
  await login(page, true)
  await page.goto('/teacher-ai?course=1&class=1')
  await page.locator('#chat-input').fill('这个班队列和栈有哪些典型错误？安排40分钟讲评课和两组后续练习。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('button', { name: '编辑与保存教案', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑与保存教案', exact: true }).click()
  await page.getByLabel('教案标题', { exact: true }).fill('队列与栈讲评课浏览器验收')
  await page.getByRole('button', { name: '保存为教案草稿', exact: true }).click()
  await expect(page.getByRole('link', { name: '打开教案', exact: true })).toBeVisible()
  await page.getByRole('link', { name: '审核并发布任务', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('当前任务面向')
  await dialog.getByRole('combobox', { name: '发布到班级', exact: true }).selectOption({ index: 1 })
  await page.getByRole('button', { name: '发布作业', exact: true }).last().click()
  await expect(dialog).toHaveCount(0)
})

test('栈操作回放与边界处理保存前后状态，预测与参与分开', async ({ page }) => {
  await login(page)
  await page.goto('/experiments?course=1&mode=stack')
  await expect(page.locator('.structure-item')).toHaveCount(3)
  await page.getByLabel('待加入元素').fill('48')
  await page.getByRole('button', { name: '压栈', exact: true }).click()
  await expect(page.locator('.structure-pointer')).toContainText('48')
  await expect(page.getByRole('button', { name: '出栈', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '出栈', exact: true }).click()
  await expect(page.locator('.result-port > strong')).toHaveText('48')
  await expect(page.getByRole('button', { name: '查看栈顶', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '查看栈顶', exact: true }).click()
  await expect(page.locator('.structure-item')).toHaveCount(3)
  await page.getByText('预测与操作记录', { exact: true }).click()
  await page.getByLabel('预测移出元素').fill('36')
  await page.getByRole('button', { name: '检查预测', exact: true }).click()
  await expect(page.getByText('预测正确', { exact: true })).toBeVisible()
  const saved = page.waitForResponse(response => response.url().endsWith('/api/events') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '保存实验记录', exact: true }).click()
  const response = await saved
  const payload = response.request().postDataJSON().payload
  expect(payload.operation_sequence).toHaveLength(3)
  expect(payload.operation_sequence[0].before).toEqual([12, 24, 36])
  expect(payload.operation_sequence[1].after).toEqual([12, 24, 36])
  expect(payload.understanding_correct).toBe(true)
})

test('教师题库最后一行与分页边界及控件命中正常', async ({ page }) => {
  await login(page, true)
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }, { width: 1366, height: 650 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/practice?course=2')
    await expect(page.locator('.question-bank > button').first()).toBeVisible()
    await page.waitForTimeout(180)
    const boundary = await page.locator('.question-bank').evaluate(element => {
      const pager = element.nextElementSibling!.getBoundingClientRect()
      const last = element.lastElementChild!.getBoundingClientRect()
      const button = element.lastElementChild as HTMLElement
      const x = last.x + last.width / 2, y = Math.min(last.bottom - 4, last.y + last.height / 2)
      return { lastBottom: last.bottom, pagerTop: pager.top, hit: button.contains(document.elementFromPoint(x, y)), font: getComputedStyle(button.querySelector('h3')!).fontSize }
    })
    expect(boundary.lastBottom).toBeLessThanOrEqual(boundary.pagerTop + 1)
    expect(boundary.hit).toBe(true)
    expect(parseFloat(boundary.font)).toBeGreaterThanOrEqual(15)
    await page.locator('.question-bank > button').last().click()
  }
})

test('真实音频经本地识别进入可编辑输入框', async ({ page }) => {
  test.skip(!existsSync('../.local/round6-voice-sample.mp3'), '本机固定音频专项')
  await login(page)
  await page.goto('/tutor?course=1')
  await page.getByLabel('选择语音文件').setInputFiles('../.local/round6-voice-sample.mp3')
  await expect(page.locator('#chat-input')).toHaveValue(/栈.*队列/, { timeout: 45000 })
  await expect(page.locator('.chat-message')).toHaveCount(0)
})
