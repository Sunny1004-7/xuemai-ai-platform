import { test, expect, type Page } from '@playwright/test'

async function login(page: Page, username: string) {
  await page.goto('/')
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉' }).click()
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
}

// 用已登录浏览器读取保存后的事实或恢复共享视频夹具，不代替被验收的 UI 操作。
async function authenticatedJson(page: Page, path: string, method = 'GET', body?: unknown) {
  return page.evaluate(
    async ({ path, method, body }) => {
      const session = JSON.parse(sessionStorage.getItem('xuemai.session.v1') || 'null')
      const response = await fetch(`/api${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${session?.token || ''}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      if (!response.ok) throw new Error(`验收数据读取失败：${response.status}`)
      return response.json()
    },
    { path, method, body },
  )
}

test('教师用视频表单保存字幕片段与检查点，学生可检索并定位新字幕', async ({ browser }) => {
  const teacherContext = await browser.newContext(),
    studentContext = await browser.newContext()
  const teacher = await teacherContext.newPage(),
    student = await studentContext.newPage()
  await login(teacher, 'teacher')
  const original = (await authenticatedJson(teacher, '/resources?course_id=1')).find(
    (r: { id: number }) => r.id === 100,
  )
  expect(original).toBeTruthy()
  const marker = `表单字幕验收${Date.now()}`
  const segmentTitle = `定位片段${Date.now()}`
  try {
    await teacher.goto('/video?resource=100')
    await teacher.getByRole('button', { name: '编辑字幕与检查点' }).click()
    let dialog = teacher.getByRole('dialog', { name: '视频字幕与互动时间轴' })
    await expect(dialog.getByLabel('视频时长（秒）')).toHaveValue(
      String(original.metadata.duration),
    )
    const subtitleCount = await dialog.getByRole('textbox', { name: /^字幕 \d+ 文字$/ }).count()
    await dialog.getByRole('button', { name: '添加字幕', exact: true }).click()
    await dialog.getByLabel(`字幕 ${subtitleCount + 1} 开始时间（秒）`, { exact: true }).fill('1')
    await dialog.getByLabel(`字幕 ${subtitleCount + 1} 结束时间（秒）`, { exact: true }).fill('2')
    await dialog
      .getByLabel(`字幕 ${subtitleCount + 1} 文字`, { exact: true })
      .fill(`${marker}：比较相邻元素，让较大元素向右移动。`)
    const segmentCount = await dialog.getByRole('textbox', { name: /^知识片段 \d+ 名称$/ }).count()
    await dialog.getByRole('button', { name: '添加知识片段', exact: true }).click()
    await dialog
      .getByLabel(`知识片段 ${segmentCount + 1} 定位时间（秒）`, { exact: true })
      .fill('3')
    await dialog.getByLabel(`知识片段 ${segmentCount + 1} 名称`, { exact: true }).fill(segmentTitle)
    await dialog
      .getByLabel(`知识片段 ${segmentCount + 1} 关联知识点`, { exact: true })
      .selectOption('6')
    await dialog.getByLabel('互动检查 1 暂停时间（秒）', { exact: true }).fill('21')
    await dialog.getByLabel('互动检查 1 题目', { exact: true }).selectOption('3')
    const saving = teacher.waitForResponse(
      (r) => r.url().endsWith('/api/resources/100') && r.request().method() === 'PATCH',
    )
    await dialog.getByRole('button', { name: '保存时间轴', exact: true }).click()
    const response = await saving
    expect(response.ok()).toBeTruthy()
    const saved = await response.json()
    expect(saved.metadata.synthetic).toBe(original.metadata.synthetic)
    expect(
      saved.metadata.subtitles.some(
        (s: { text: string; start: number; end: number }) =>
          s.text.includes(marker) && s.start === 1 && s.end === 2,
      ),
    ).toBeTruthy()
    expect(
      saved.metadata.timeline.some(
        (s: { title: string; time: number; knowledge_id: number }) =>
          s.title === segmentTitle && s.time === 3 && s.knowledge_id === 6,
      ),
    ).toBeTruthy()
    expect(saved.metadata.checkpoints[0]).toMatchObject({ time: 21, question_id: 3 })
    await expect(dialog).not.toBeVisible()
    await teacher.reload()
    await teacher.getByRole('button', { name: '编辑字幕与检查点' }).click()
    dialog = teacher.getByRole('dialog', { name: '视频字幕与互动时间轴' })
    await expect
      .poll(() =>
        dialog
          .getByRole('textbox', { name: /^字幕 \d+ 文字$/ })
          .evaluateAll((elements) => elements.map((e) => (e as HTMLTextAreaElement).value)),
      )
      .toContain(`${marker}：比较相邻元素，让较大元素向右移动。`)
    await expect
      .poll(() =>
        dialog
          .getByRole('textbox', { name: /^知识片段 \d+ 名称$/ })
          .evaluateAll((elements) => elements.map((e) => (e as HTMLInputElement).value)),
      )
      .toContain(segmentTitle)
    await expect(dialog.getByLabel('互动检查 1 暂停时间（秒）', { exact: true })).toHaveValue('21')
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await login(student, 'student1')
    await student.goto('/video?resource=100')
    const video = student.locator('video')
    await expect
      .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
      .toBeGreaterThanOrEqual(1)
    await student.getByLabel('搜索视频字幕').fill(marker)
    const subtitle = student.locator('.transcript-list>button').filter({ hasText: marker })
    await expect(subtitle).toHaveCount(1)
    await subtitle.click()
    await expect
      .poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime))
      .toBeGreaterThanOrEqual(1)
    await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeLessThan(2)
  } finally {
    // 资源 100 由其他视频用例共用；验收后恢复标题和时间轴，避免用例顺序改变其含义。
    await authenticatedJson(teacher, '/resources/100', 'PATCH', {
      title: original.title,
      metadata: original.metadata,
    })
    await teacherContext.close()
    await studentContext.close()
  }
})

test('Mock 备课草稿编辑发布形成可检索版本，AI 题目审核后学生可独立作答', async ({ browser }) => {
  const teacherContext = await browser.newContext(),
    studentContext = await browser.newContext()
  const teacher = await teacherContext.newPage(),
    student = await studentContext.newPage()
  await login(teacher, 'teacher')
  // 模式不符时在点击任何 AI 操作前失败，保证该测试永远不会消耗真实额度。
  expect((await authenticatedJson(teacher, '/ai/status')).mode).toBe('mock')
  await teacher.getByRole('link', { name: 'AI 备课与资料', exact: true }).click()
  await teacher.getByRole('button', { name: 'AI 备课', exact: true }).click()
  let dialog = teacher.getByRole('dialog', { name: 'AI 辅助教学准备' })
  await dialog.getByLabel('本课知识点').selectOption('6')
  await dialog
    .getByLabel('教学意图')
    .fill('面向初学者准备冒泡排序课堂，强调相邻比较、一轮结束与理解检查。')
  const lessonGeneration = teacher.waitForResponse(
    (r) => r.url().endsWith('/api/ai/generate') && r.request().postDataJSON()?.kind === 'lesson',
  )
  await dialog.getByRole('button', { name: '生成可编辑草稿', exact: true }).click()
  expect((await (await lessonGeneration).json()).mode).toBe('mock')
  dialog = teacher.getByRole('dialog', { name: '编辑并审核教学草稿' })
  await expect(dialog.getByText('AI 生成草稿 · 教师审核后保存', { exact: true })).toBeVisible()
  const lessonTitle = `备课审核验收${Date.now()}`
  await dialog.getByLabel('资料标题').fill(lessonTitle)
  const content = dialog.getByLabel('正文内容')
  await expect(content).not.toBeEmpty()
  const firstContent = await content.inputValue()
  await content.fill(
    `${firstContent}\n\n教师补充：先让学生手工追踪一轮排序，再解释最大元素为何到达末尾。`,
  )
  await dialog.getByRole('button', { name: '审核并保存资料', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await teacher.getByLabel('搜索课程资料').fill(lessonTitle)
  let card = teacher
    .locator('.resource-card')
    .filter({ has: teacher.getByRole('heading', { name: lessonTitle, exact: true }) })
  await expect(card).toContainText('版本 1')
  await card.getByRole('button', { name: `编辑${lessonTitle}`, exact: true }).click()
  dialog = teacher.getByRole('dialog', { name: '编辑课程资料' })
  const revisionMarker = `课堂迁移检查${Date.now()}`
  await dialog
    .getByLabel('正文内容')
    .fill(
      `${await dialog.getByLabel('正文内容').inputValue()}\n\n${revisionMarker}：请学生解释已排序后能否提前终止。`,
    )
  await dialog.getByRole('button', { name: '审核并保存资料', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await teacher.reload()
  await teacher.getByLabel('搜索课程资料').fill(revisionMarker)
  card = teacher
    .locator('.resource-card')
    .filter({ has: teacher.getByRole('heading', { name: lessonTitle, exact: true }) })
  await expect(card).toContainText('版本 2')
  await login(student, 'student1')
  await student.goto('/resources')
  await student.getByLabel('搜索课程资料').fill(revisionMarker)
  const studentCard = student
    .locator('.resource-card')
    .filter({ has: student.getByRole('heading', { name: lessonTitle, exact: true }) })
  await expect(studentCard).toContainText('版本 2')
  await studentCard.getByRole('button', { name: '查看内容', exact: true }).click()
  await expect(
    student.getByRole('dialog', { name: lessonTitle }).locator('.resource-document'),
  ).toContainText(revisionMarker)
  await teacher.goto('/practice?knowledge=6')
  const questionGeneration = teacher.waitForResponse(
    (r) => r.url().endsWith('/api/ai/generate') && r.request().postDataJSON()?.kind === 'question',
  )
  await teacher.getByRole('button', { name: 'AI 出题', exact: true }).click()
  expect((await (await questionGeneration).json()).mode).toBe('mock')
  dialog = teacher.getByRole('dialog', { name: '审核 AI 题目草稿' })
  await expect(
    dialog.getByText('待审核草稿 · 请核对知识与参考答案后保存', { exact: true }),
  ).toBeVisible()
  const questionTitle = `AI 出题审核验收${Date.now()}：冒泡排序第一轮后确定的是？`
  await dialog.getByLabel('题目内容').fill(questionTitle)
  await dialog.getByLabel('题型', { exact: true }).selectOption('single')
  await dialog.getByLabel('关联知识点').selectOption('6')
  await dialog
    .getByLabel('选项（每行一个，填空/简答可留空）')
    .fill('最大元素的位置\n最小元素的位置\n所有元素的位置\n中间元素的位置')
  await dialog.getByLabel('参考答案', { exact: true }).fill('最大元素的位置')
  await dialog.getByLabel('答案解析').fill('一轮相邻比较交换会将未排序部分最大元素移至末尾。')
  await dialog.getByLabel('审核状态').selectOption('approved')
  const savingQuestion = teacher.waitForResponse(
    (r) => r.url().endsWith('/api/questions') && r.request().method() === 'POST',
  )
  await dialog.getByRole('button', { name: '审核并保存题目', exact: true }).click()
  const response = await savingQuestion
  expect(response.ok()).toBeTruthy()
  const savedQuestion = await response.json()
  await expect(dialog).not.toBeVisible()
  await expect(teacher.locator('.question-bank')).toContainText(questionTitle)
  await student.goto(`/practice?knowledge=6&question=${savedQuestion.id}`)
  await expect(student.locator('.question-title')).toHaveText(questionTitle)
  await expect(student.locator('.teacher-answer-preview')).toHaveCount(0)
  await student.getByRole('radio').nth(0).check()
  await student.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(
    student.getByRole('heading', { name: '思路清晰，回答正确', exact: true }),
  ).toBeVisible()
  await teacherContext.close()
  await studentContext.close()
})
