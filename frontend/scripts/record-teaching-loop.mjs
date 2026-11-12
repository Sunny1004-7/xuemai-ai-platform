// 同一课程、学生和任务的实际业务操作。默认Mock，真实录制须显式开启。
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const preflight = process.env.DEMO_PREFLIGHT === '1'
const real = process.env.DEMO_REAL === '1'
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5181'
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const directory = path.join(root, '.local/round7-loop', stamp)
await mkdir(directory, { recursive: true })
const recorder = preflight ? null : await createRecorder({ base, directory })
const browser = preflight ? await chromium.launch({ channel: 'chrome', headless: true }) : null
const page = recorder?.page || await browser.newPage({ viewport: { width: 1920, height: 1000 }, deviceScaleFactor: 1 })
page.setDefaultTimeout(30000)
const events = [], responses = [], evidence = { course_id: 1, student_username: 'student1', knowledge_id: 2, real, preflight }
let origin = performance.now(), studentToken, teacherToken, teacherQuestions
const dwell = ms => preflight ? Promise.resolve() : pause(ms)
const click = locator => recorder ? recorder.click(locator) : locator.click()
async function mark(name) {
  if (recorder) await recorder.mark(name)
  const event = { name, at: Number(((performance.now() - origin) / 1000).toFixed(3)) }
  events.push(event); console.log(JSON.stringify(event))
  await writeFile(path.join(directory, 'events.json'), JSON.stringify(events, null, 2))
}
async function login(username) {
  await page.goto(base)
  if (await page.locator('.profile').isVisible()) await click(page.locator('.profile'))
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  const reply = page.waitForResponse(response => response.url().endsWith('/api/auth/login'))
  await click(page.getByRole('button', { name: '进入学脉', exact: true }))
  const data = await (await reply).json()
  await expect(page.locator('.app-shell')).toBeVisible()
  return data.token
}
async function readApi(token, route) {
  const response = await page.request.get(base + '/api' + route, { headers: { Authorization: 'Bearer ' + token } })
  if (!response.ok()) throw new Error(`业务读取失败 ${route}`)
  return response.json()
}
async function go(route) {
  await page.goto(base + route)
  await expect(page.locator('main h1')).toBeVisible()
  await expect(page.locator('main .loading')).toHaveCount(0)
}
async function sendChat(role, message) {
  await page.locator('#chat-input').fill(message)
  await dwell(2000)
  const reply = page.waitForResponse(response => response.url().endsWith('/api/ai/chat') && response.request().method() === 'POST', { timeout: 90000 })
  await mark(role + '请求发出')
  await click(page.getByRole('button', { name: '发送', exact: true }))
  const raw = await (await reply).text()
  const parsed = raw.split('\n').filter(line => line.startsWith('data: ')).map(line => JSON.parse(line.slice(6)))
  const done = parsed.findLast(item => item.status === 'complete')
  if (!done) throw new Error(parsed.find(item => item.code)?.message || '问答未完成，保留本次结果后停止')
  responses.push({ role, message, done })
  await writeFile(path.join(directory, 'ai-results.json'), JSON.stringify(responses, null, 2))
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0)
  await mark(role + '回答完成')
  return done
}
async function answer(question) {
  if (['single', 'true_false'].includes(question.type)) {
    const index = question.options.findIndex(option => String(option) === String(question.answer))
    if (index < 0) throw new Error('课程题目选项与答案不一致')
    await page.getByRole('radio').nth(index).check()
  } else if (question.type === 'multiple') {
    for (let index = 0; index < question.options.length; index++) {
      if (question.answer.includes(question.options[index])) await page.locator('.answer-option input[type=checkbox]').nth(index).check()
    }
  } else await page.getByLabel('填写答案').fill(String(question.answer))
  await dwell(1500)
  const reply = page.waitForResponse(response => response.url().endsWith('/api/attempts') && response.request().method() === 'POST')
  await click(page.getByRole('button', { name: '提交答案', exact: true }))
  const result = await (await reply).json()
  if (!result.correct) throw new Error('录制中的复测作答与课程答案未匹配')
  await dwell(2500)
  return result
}
try {
  const health = await page.request.get(base + '/api/health').then(response => response.json())
  if (health.ai_mode !== (real ? 'real' : 'mock')) throw new Error('录制AI模式与显式参数不符')
  const fixture = await page.request.post(base + '/api/auth/login', { data: { username: 'teacher', password: 'Xuemai123!' } }).then(response => response.json())
  teacherQuestions = await readApi(fixture.token, '/questions?course_id=1')
  if (recorder) await recorder.start()
  origin = performance.now()
  if (process.env.DEMO_RESUME_ASSIGNMENT) {
    studentToken = await login('student1')
    const assigned = await readApi(studentToken, '/assignments/' + process.env.DEMO_RESUME_ASSIGNMENT)
    evidence.assignment = assigned
    await mark('学生接收复测任务')
    await go('/practice?course=1&assignment=' + assigned.id)
    await dwell(4500)
    evidence.followup_attempts = []
    for (let index = 0; index < assigned.questions.length; index++) {
      if (index) await click(page.getByRole('button', { name: '下一道练习', exact: true }))
      const question = teacherQuestions.find(item => item.id === assigned.questions[index].id)
      evidence.followup_attempts.push(await answer(question))
    }
  } else {
  await mark('学生进入')
  studentToken = await login('student1')
  await go('/practice?course=1&question=1')
  await mark('首次作答')
  await dwell(3500)
  await page.getByRole('radio').first().check()
  const wrongReply = page.waitForResponse(response => response.url().endsWith('/api/attempts') && response.request().method() === 'POST')
  await click(page.getByRole('button', { name: '提交答案', exact: true }))
  evidence.initial_attempt = await (await wrongReply).json()
  if (evidence.initial_attempt.correct) throw new Error('开场应为实际错误作答')
  await mark('知识证据反馈')
  await dwell(7000)
  await go('/plan?course=1')
  await click(page.getByRole('tab', { name: '预算内路径', exact: true }))
  evidence.path = await readApi(studentToken, '/recommendations?course_id=1')
  await mark('预算内路径')
  await dwell(6500)
  await go('/graph?course=1')
  await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy', 'false')
  await mark('课程知识网络')
  const canvas = await page.locator('.graph-canvas').boundingBox()
  await page.mouse.move(canvas.x + 100, canvas.y + 90); await page.mouse.down()
  if (preflight) await page.mouse.move(canvas.x + 244, canvas.y + 70, { steps: 8 })
  else for (let step = 0; step <= 180; step++) { await page.mouse.move(canvas.x + 100 + step * .8, canvas.y + 90 + Math.sin(step / 40) * 25); await pause(5) }
  await page.mouse.up()
  await page.getByLabel('定位知识点').fill('栈与队列')
  await dwell(3500)
  await go('/experiments?course=1&mode=stack')
  await mark('栈操作实验')
  await page.getByLabel('待加入元素').fill('48')
  await click(page.getByRole('button', { name: '压栈', exact: true })); await dwell(1600)
  await click(page.getByRole('button', { name: '出栈', exact: true })); await dwell(1600)
  await click(page.getByRole('button', { name: '查看栈顶', exact: true })); await dwell(1600)
  await click(page.getByRole('button', { name: '保存实验记录', exact: true }))
  await go('/tutor?course=1&question=1&knowledge=2')
  await page.getByLabel('选择AI模型').selectOption('deepseek-flash')
  await page.getByLabel('选择问答附件').setInputFiles({ name: '操作记录.md', mimeType: 'text/markdown', buffer: Buffer.from('丙牌表示数字3。甲牌、乙牌、丙牌依次入栈，栈顶为丙牌。第一次弹出丙牌，再弹出乙牌，最后甲牌。栈中最后入栈的元素先出栈。') })
  await expect(page.locator('.composer-attachments')).toBeVisible()
  await mark('学生题目与附件')
  await dwell(4000)
  const studentDone = await sendChat('学生', '我在题目中选了1。请根据附件丙牌记录解释为什么先出栈的是3，用简短反例引导我，并检查理解。')
  await dwell(5000)
  await mark('学生引用定位')
  const attachmentSource = page.locator('.message-sources button').filter({ hasText: '操作记录.md' }).last()
  await expect(attachmentSource).toBeVisible()
  await click(attachmentSource); await dwell(5000)
  await click(page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }))
  await mark('学生理解检查')
  const check = studentDone.teaching.check
  if (!check) throw new Error('辅导未形成理解检查')
  const q = teacherQuestions.find(question => question.title === check.title && question.knowledge_id === check.knowledge_id)
  if (!q) throw new Error('检查题未关联课程题库')
  const checkBox = page.locator('.understanding-check').last()
  const index = q.options.findIndex(option => String(option) === String(q.answer))
  await checkBox.getByRole('radio').nth(index).check()
  const checked = page.waitForResponse(response => /\/api\/ai\/checks\/\d+\/answer$/.test(response.url()))
  await click(checkBox.getByRole('button', { name: '提交理解检查', exact: true }))
  evidence.check = await (await checked).json()
  await dwell(6500)
  await mark('教师查看专题证据')
  teacherToken = await login('teacher')
  await go('/analytics?course=1&knowledge=2')
  await click(page.getByRole('tab', { name: '知识矩阵', exact: true }))
  await page.getByLabel('筛选学生', { exact: true }).fill('陈星河')
  const matrix = page.getByRole('button', { name: /^陈星河，栈与队列，/ })
  await click(matrix); await dwell(6500)
  await click(page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }))
  const analytics = await readApi(teacherToken, '/analytics?course_id=1&class_id=1')
  const protagonistGroup = analytics.groups.find(group => group.student_ids.includes(2))
  evidence.protagonist_group = protagonistGroup
  await go('/teacher-ai?course=1&class=1&knowledge=2')
  await mark('教师教学规划输入')
  const teacherDone = await sendChat('教师', `请依据这个班栈与队列的错误安排30分钟讲评课和后续练习。请纳入陈星河所在的${protagonistGroup.name}（${protagonistGroup.id}），每组只选1道合法候选题，目标和三个教学环节简短具体。`)
  const artifact = teacherDone.artifact
  if (!artifact?.id) throw new Error('教师规划未形成合法草稿，保留回答并停止后续写入')
  await dwell(6000)
  await mark('教师编辑教案')
  await click(page.getByRole('button', { name: '编辑与保存教案', exact: true }))
  await page.getByLabel('教案标题', { exact: true }).fill('栈与队列讲评及独立复测')
  await dwell(4500)
  const saveReply = page.waitForResponse(response => /\/teacher-drafts\/\d+\/save$/.test(response.url()))
  await click(page.getByRole('button', { name: '保存为教案草稿', exact: true }))
  evidence.saved_lesson = await (await saveReply).json()
  await expect(page.getByRole('link', { name: '打开教案', exact: true })).toBeVisible()
  await dwell(3500)
  const selectedGroup = artifact.draft.groups?.find(group => group.student_ids?.includes(2))
  const title = '栈与队列独立复测-' + stamp.slice(11, 19)
  if (selectedGroup) {
    await click(page.locator(`a[href*="teaching_draft=${artifact.id}"][href*="group=${encodeURIComponent(selectedGroup.group_id)}"]`).first())
  } else {
    await go('/practice?course=1')
    await click(page.getByRole('button', { name: '发布作业', exact: true }))
    evidence.teacher_decision = '教师采用全班共同复测，手动审核栈与队列题目'
  }
  await mark('教师审核发布')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.locator('input[name=title]').fill(title)
  await dialog.getByRole('combobox', { name: '发布到班级', exact: true }).selectOption('1')
  if (!selectedGroup) await dialog.locator('.checkbox-list label').filter({ hasText: teacherQuestions.find(question => question.id === 1).title }).getByRole('checkbox').check()
  await dwell(6500)
  const assignmentReply = page.waitForResponse(response => response.url().endsWith('/api/assignments') && response.request().method() === 'POST')
  await click(dialog.getByRole('button', { name: '发布作业', exact: true }))
  const assignment = await (await assignmentReply).json()
  const assigned = (await readApi(teacherToken, '/assignments?course_id=1')).find(item => item.id === assignment.id)
  evidence.assignment = assigned
  if (assigned.student_ids.length && !assigned.student_ids.includes(2)) throw new Error('发布对象未包含故事中的学生')
  await mark('学生接收复测任务')
  await login('student1')
  await go('/practice?course=1&assignment=' + assignment.id)
  await dwell(4500)
  evidence.followup_attempts = []
  for (let index = 0; index < assigned.question_ids.length; index++) {
    if (index) await click(page.getByRole('button', { name: '下一道练习', exact: true }))
    const question = teacherQuestions.find(item => item.id === assigned.question_ids[index])
    evidence.followup_attempts.push(await answer(question))
  }
  }
  const assignment = evidence.assignment
  const title = assignment.title
  await mark('教师回看任务结果')
  teacherToken = await login('teacher')
  await go('/practice?course=1')
  await click(page.getByRole('tab', { name: '作业记录', exact: true }))
  await click(page.locator('.assignment-row').filter({ hasText: title }).getByRole('button', { name: '查看结果', exact: true }))
  await dwell(10000)
  evidence.teacher_results = await readApi(teacherToken, `/assignments/${assignment.id}/results`)
  const protagonist = evidence.teacher_results.find(item => item.id === 2)
  if (!protagonist.completed) throw new Error('学生复测未在教师结果中完成')
  await mark('教师形成反馈')
  await go('/classroom?course=1')
  await click(page.getByRole('button', { name: '发起课堂互动', exact: true }))
  const feedback = page.getByRole('dialog')
  await feedback.getByLabel('活动标题', { exact: true }).fill('栈与队列复测反馈')
  await feedback.locator('select[name=kind]').selectOption('feedback')
  await feedback.getByLabel('提问或任务', { exact: true }).fill('陈星河已完成本次独立复测。请再用一句话分别解释栈和队列的移出顺序，并举出一个生活例子。')
  await dwell(4500)
  const feedbackReply = page.waitForResponse(response => response.url().endsWith('/api/classroom') && response.request().method() === 'POST')
  await click(feedback.getByRole('button', { name: '发布到课堂', exact: true }))
  evidence.teacher_feedback = await (await feedbackReply).json()
  await dwell(5000)
  await mark('完整教学流程完成')
  await writeFile(path.join(directory, 'business-evidence.json'), JSON.stringify(evidence, null, 2))
} finally {
  await writeFile(path.join(directory, 'business-evidence.json'), JSON.stringify(evidence, null, 2))
  await writeFile(path.join(directory, 'events.json'), JSON.stringify(events, null, 2))
  if (recorder) await recorder.stop()
  if (browser) await browser.close()
}
console.log(JSON.stringify({ directory, preflight, real, status: 'completed' }))
