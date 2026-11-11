import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, username: string) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉' }).click()
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
}
const unique = (prefix: string) => `${prefix}${Date.now()}`

test('教师创建课程章节知识班级，学生邀请码加入后读取同一图谱', async ({ browser }) => {
  const tc = await browser.newContext(),
    sc = await browser.newContext()
  const tp = await tc.newPage(),
    sp = await sc.newPage()
  await login(tp, 'teacher')
  await tp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '课程与班级', exact: true })
    .click()
  await tp.getByRole('button', { name: '创建课程', exact: true }).click()
  const courseTitle = unique('UI 教学闭环课程')
  let dialog = tp.getByRole('dialog')
  await dialog.getByLabel('课程名称', { exact: true }).fill(courseTitle)
  await dialog.getByLabel('课程代码').fill(`E2E${Date.now()}`)
  await dialog.getByLabel('课程介绍').fill('用真实创建、授权与学习路径验证师生课程协作。')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(tp.locator('.course-summary')).toContainText(courseTitle)
  await tp.getByRole('tab', { name: '章节内容', exact: true }).click()
  await tp.getByRole('button', { name: '新增章节' }).click()
  dialog = tp.getByRole('dialog')
  await dialog.getByLabel('章节名称').fill('认识递归')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(tp.locator('.chapter-list')).toContainText('认识递归')
  await tp.getByRole('tab', { name: '授课班级', exact: true }).click()
  await tp.getByRole('button', { name: '新建班级' }).click()
  dialog = tp.getByRole('dialog')
  await dialog.getByLabel('班级名称').fill('UI 共学班')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(tp.locator('.class-card')).toContainText('UI 共学班')
  const joinCode = await tp
    .locator('.class-card')
    .filter({ hasText: 'UI 共学班' })
    .locator('.join-code strong')
    .innerText()
  await tp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '知识图谱', exact: true })
    .click()
  await tp.getByRole('button', { name: '新增知识点' }).click()
  dialog = tp.getByRole('dialog')
  await dialog.getByLabel('知识点名称').fill('递归终止条件')
  await dialog.getByLabel('所属章节').selectOption({ label: '认识递归' })
  await dialog.getByLabel('知识说明').fill('递归必须有可达到的终止条件。')
  await dialog.getByLabel('学习目标（每行一个）').fill('能够辨认递归终止条件\n能够解释递归推进方向')
  await dialog.getByRole('button', { name: '保存知识点' }).click()
  await expect(tp.getByRole('button', { name: /递归终止条件，掌握度/ })).toBeVisible()
  await login(sp, 'student1')
  await sp.getByLabel('切换当前课程').click()
  await sp.getByRole('button', { name: '加入班级', exact: true }).click()
  dialog = sp.getByRole('dialog')
  await dialog.getByLabel('班级邀请码').fill(joinCode)
  await dialog.getByRole('button', { name: '加入班级', exact: true }).click()
  await sp.getByLabel('切换当前课程').click()
  await sp.getByRole('option', { name: courseTitle }).click()
  await sp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '知识图谱', exact: true })
    .click()
  await sp.getByRole('button', { name: /递归终止条件，掌握度/ }).click()
  await expect(sp.getByRole('button', { name: /递归终止条件，掌握度/ })).toBeVisible()
  await expect(sp.locator('.node-objectives')).toContainText('能够辨认递归终止条件')
  await expect(sp.getByRole('button', { name: '新增知识点' })).toHaveCount(0)
  await tc.close()
  await sc.close()
})

test('从图谱进入视频，完成互动检查并真实写回事件', async ({ page }) => {
  await login(page, 'student1')
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '知识图谱', exact: true })
    .click()
  await page.getByLabel('定位知识点').fill('冒泡排序')
  await page.getByRole('button', { name: /冒泡排序，掌握度/ }).click()
  await page.locator('.resource-links a').filter({ hasText: '看见算法：冒泡排序' }).click()
  await expect(page).toHaveURL(/\/video\?resource=100/)
  const video = page.locator('video')
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(1)
  await page.getByRole('button', { name: '片段与检查', exact: true }).click()
  await page.locator('.video-timeline button').nth(1).click()
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
    .toBeGreaterThanOrEqual(9)
  await page.getByRole('button', { name: '随堂理解检查 1' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('radio').nth(1).check()
  const persisted = page.waitForResponse(
    (r) =>
      r.url().endsWith('/api/events') &&
      r.request().method() === 'POST' &&
      r.request().postDataJSON()?.kind === 'video_checkpoint',
  )
  await dialog.getByRole('button', { name: '提交检查' }).click()
  await expect(dialog.getByRole('heading', { name: '回答正确' })).toBeVisible()
  expect((await persisted).ok()).toBeTruthy()
})

test('原题进入 Mock 辅导，资料引用与历史可接续，服务故障反馈明确', async ({ page }) => {
  await login(page, 'student1')
  await page.goto('/practice?question=1&knowledge=2')
  await page.getByRole('radio').nth(0).check()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await page.getByRole('link', { name: '针对这道题聊一聊' }).click()
  await expect(page).toHaveURL(/question=1/)
  await page
    .locator('.starter-prompts')
    .getByRole('button', { name: '请先给这道题一点提示，不要直接告诉我答案', exact: true })
    .click()
  await expect(page.locator('.chat-message.assistant .message-content')).not.toBeEmpty()
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0)
  await expect(page.locator('.message-sources>button').first()).toBeVisible()
  const answer = await page.locator('.chat-message.assistant .message-content').innerText()
  await page.reload()
  await page.locator('.conversation-list>button:not(.button)').first().click()
  await expect(page.locator('.chat-message.assistant .message-content')).toHaveText(answer)
  await page.getByRole('button', { name: '开启新对话' }).click()
  await page.route('**/api/ai/chat', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '测试故障：辅导服务暂不可用，请稍后重试' }),
    }),
  )
  await page.getByLabel('输入学习问题').fill('栈为什么后进先出？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.locator('.chat-message.error')).toContainText('辅导服务暂不可用')
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible()
})

test('教师根据学情发布定向任务，学生完成后再次分析作答增量', async ({ browser }) => {
  const tc = await browser.newContext(),
    sc = await browser.newContext()
  const tp = await tc.newPage(),
    sp = await sc.newPage()
  await login(tp, 'teacher')
  await tp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '学情与分层', exact: true })
    .click()
  await tp.getByRole('tab', { name: '知识关注', exact: true }).click()
  const attemptStat = tp
    .locator('.stats-row .stat')
    .filter({ hasText: '累计作答' })
    .locator('strong')
  await expect(attemptStat).toBeVisible()
  const before = Number(await attemptStat.innerText())
  await tp
    .locator('.knowledge-analysis>div')
    .filter({ has: tp.getByRole('heading', { name: '数组与链表', exact: true }) })
    .getByRole('button', { name: '分层任务' })
    .click()
  const dialog = tp.getByRole('dialog')
  const title = unique('数组知识定向巩固')
  await dialog.getByLabel('任务名称').fill(title)
  await dialog
    .locator('.checkbox-list label')
    .filter({ hasText: '陈星河' })
    .getByRole('checkbox')
    .check()
  await dialog.getByRole('button', { name: '发布分层任务' }).click()
  await expect(dialog).not.toBeVisible()
  await login(sp, 'student1')
  await sp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '智能练习', exact: true })
    .click()
  await sp.getByLabel('选择作业范围').selectOption({ label: title })
  await sp.getByRole('radio').nth(0).check()
  await sp.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(sp.getByRole('heading', { name: '思路清晰，回答正确' })).toBeVisible()
  await sp.getByRole('button', { name: '下一道练习', exact: true }).click()
  await sp.getByRole('radio').nth(0).check()
  await sp.getByRole('button', { name: '提交答案', exact: true }).click()
  await tp.getByRole('button', { name: '刷新学习状态' }).click()
  await expect.poll(async () => Number(await attemptStat.innerText())).toBeGreaterThan(before)
  await tp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '题库与作业', exact: true })
    .click()
  await tp.getByRole('tab', { name: '作业记录', exact: true }).click()
  const row = tp.locator('.assignment-row').filter({ hasText: title })
  await row.getByRole('button', { name: '查看结果' }).click()
  await expect(row.getByText('陈星河', { exact: true })).toBeVisible()
  await expect(row.getByText('许沐晴', { exact: true })).toHaveCount(0)
  await expect(row.getByText('已完成', { exact: true })).toBeVisible()
  await tc.close()
  await sc.close()
})

test('个人目标计划编辑持久化，课堂互动回答同步给教师', async ({ browser }) => {
  const sc = await browser.newContext(),
    tc = await browser.newContext()
  const sp = await sc.newPage(),
    tp = await tc.newPage()
  await login(sp, 'student1')
  await sp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '目标与计划', exact: true })
    .click()
  await sp.getByRole('button', { name: '设定学习目标', exact: true }).click()
  let dialog = sp.getByRole('dialog')
  const goalTitle = unique('理解图的搜索')
  await dialog.getByLabel('目标名称').fill(goalTitle)
  await dialog.getByLabel('每天计划投入（分钟）').fill('20')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(sp.locator('.goal-card').filter({ hasText: goalTitle })).toContainText(goalTitle)
  await sp.getByRole('button', { name: `编辑目标${goalTitle}` }).click()
  dialog = sp.getByRole('dialog')
  await dialog.getByLabel('每天计划投入（分钟）').fill('30')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(sp.locator('.goal-card').filter({ hasText: goalTitle })).toContainText(
    '每天 30 分钟',
  )
  await sp.getByRole('button', { name: '新增学习安排' }).click()
  dialog = sp.getByRole('dialog')
  const planTitle = unique('搜索实验练习')
  await dialog.getByLabel('学习安排', { exact: true }).fill(planTitle)
  await dialog.getByLabel('关联目标').selectOption({ label: goalTitle })
  await dialog.getByLabel('学习形式').selectOption('experiment')
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await sp.getByRole('button', { name: `完成计划${planTitle}` }).click()
  await sp.reload()
  await sp.getByRole('tab', { name: '完成记录', exact: true }).click()
  await expect(
    sp.locator('.personal-plan-list>div.completed').filter({ hasText: planTitle }),
  ).toContainText(planTitle)
  await login(tp, 'teacher')
  await tp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '课堂互动', exact: true })
    .click()
  await tp.getByRole('button', { name: '发起课堂互动' }).click()
  dialog = tp.getByRole('dialog')
  const activityTitle = unique('课堂理解检查')
  await dialog.getByLabel('活动标题').fill(activityTitle)
  await dialog.getByLabel('提问或任务').fill('请用一句话说明 BFS 使用什么数据结构。')
  await dialog.getByRole('button', { name: '发布到课堂' }).click()
  await sp
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '课堂互动', exact: true })
    .click()
  await sp.locator('.activity-list').getByRole('button').filter({ hasText: activityTitle }).click()
  const studentActivity = sp.locator('.classroom-card').filter({ hasText: activityTitle })
  await studentActivity.getByLabel(`回答${activityTitle}`).fill('BFS 使用队列按层访问节点。')
  await studentActivity.getByRole('button', { name: '提交课堂回答' }).click()
  await expect(tp.locator('.classroom-card').filter({ hasText: activityTitle })).toContainText(
    'BFS 使用队列按层访问节点。',
    { timeout: 12000 },
  )
  await tc.close()
  await sc.close()
})

test('真实算法状态支持预测与执行，实验操作保存到学习事件', async ({ page }) => {
  await login(page, 'student1')
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '交互实验室', exact: true })
    .click()
  await page.getByLabel('下一步的序列是什么？用逗号分隔').fill('36,18,52,24,9,43')
  await page.getByRole('button', { name: '检查预测' }).click()
  await expect(page.getByRole('status')).toContainText('预测正确')
  await page.getByRole('button', { name: '下一步', exact: true }).click()
  await expect(page.locator('.algorithm-explanation')).toContainText('比较 36 与 18')
  await page.getByRole('button', { name: '下一步', exact: true }).click()
  await expect(page.locator('.sort-bar').first().getByText('18', { exact: true })).toBeVisible()
  let persisted = page.waitForResponse(
    (r) => r.url().endsWith('/api/events') && r.request().postDataJSON()?.kind === 'experiment',
  )
  await page.getByRole('button', { name: '保存实验记录' }).click()
  expect((await persisted).ok()).toBeTruthy()
  await page.getByRole('button', { name: '队列操作', exact: true }).click()
  await page.getByRole('button', { name: '入队', exact: true }).click()
  await page.getByRole('button', { name: '出队', exact: true }).click()
  await page.getByRole('button', { name: '入队', exact: true }).click()
  await expect(page.locator('.experiment-stage-head')).toContainText('3 次操作')
  persisted = page.waitForResponse(
    (r) => r.url().endsWith('/api/events') && r.request().postDataJSON()?.kind === 'experiment',
  )
  await page.getByRole('button', { name: '保存实验记录' }).click()
  expect((await persisted).ok()).toBeTruthy()
})
