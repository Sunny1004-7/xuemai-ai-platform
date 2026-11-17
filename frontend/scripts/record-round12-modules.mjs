// 按师生模块顺序原生连续录屏，回看既有官方回答，禁止新模型生成。
import { chromium, expect } from '@playwright/test'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const preflight = process.argv.includes('--preflight')
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5187'
const directory = path.join(root, '.local', 'round12-modules-' + Date.now())
await mkdir(directory, { recursive: true })
const scenes = JSON.parse(await readFile(path.join(root, 'docs/demo/第十二轮演示源/scenes.json'), 'utf8'))
  .filter(scene => ['student', 'teacher', 'authentication'].includes(scene.role))
const recorder = preflight ? null : await createRecorder({ base, directory })
const browser = preflight ? await chromium.launch({ channel: 'chrome', headless: true }) : null
const page = recorder?.page || await browser.newPage({ viewport: { width: 1920, height: 1000 }, deviceScaleFactor: 1 })
const timeline = [], errors = [], evidence = { new_model_calls: 0, course_id: 1, student_id: 2, reused_conversation_ids: [11, 12] }
const click = locator => recorder ? recorder.click(locator) : locator.click()
const dwell = ms => preflight ? Promise.resolve() : pause(ms)
page.on('pageerror', error => errors.push(error.message))
await page.route('**/api/ai/chat', route => route.abort())
await page.route('**/api/ai/generate', route => route.abort())
page.setDefaultTimeout(15000)

async function api(token, route, body) {
  const response = await page.request.fetch(base + '/api' + route, {
    method: body ? 'POST' : 'GET', headers: { Authorization: 'Bearer ' + token },
    ...(body ? { data: body } : {}),
  })
  if (!response.ok()) throw new Error('录制业务操作失败 ' + route + ' ' + response.status())
  return response.json()
}

async function login(username, navigate = true) {
  if (navigate) await page.goto(base)
  if (await page.locator('.profile').isVisible()) await click(page.locator('.profile'))
  await click(page.getByRole('button', { name: username === 'teacher' ? '教师端' : '学生端', exact: true }))
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  const response = page.waitForResponse(response => response.url().endsWith('/api/auth/login'))
  await click(page.getByRole('button', { name: '进入学脉', exact: true }))
  const session = await (await response).json()
  await expect(page.locator('.app-shell')).toBeVisible()
  return session.token
}

async function settled() {
  await expect(page.locator('main h1')).toBeVisible()
  await expect.poll(() => page.locator('.loading:visible').count()).toBe(0)
  await page.evaluate(() => document.fonts.ready)
  await expect(page.locator('.sidebar')).toBeVisible()
}

async function closeDialog() {
  await click(page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }))
}

async function operate(scene, question, assignment, teacherToken) {
  const button = name => page.getByRole('button', { name, exact: true })
  if (scene.module === 'dashboard') {
    await click(page.getByLabel('切换当前课程'))
    await dwell(1600)
    await page.keyboard.press('Escape')
  } else if (scene.module === 'plan') {
    await dwell(2000)
    await click(page.getByRole('tab', { name: '学习目标', exact: true }))
    await dwell(2400)
    await click(page.getByRole('tab', { name: '预算内路径', exact: true }))
    await expect(page.locator('.plan-workspace')).toBeVisible()
  } else if (scene.module === 'video') {
    await expect.poll(() => page.locator('video').evaluate(video => video.readyState)).toBeGreaterThanOrEqual(2)
    if (scene.role === 'student') {
      await page.locator('video').evaluate(async video => { video.muted = true; await video.play() })
      await dwell(4300)
      await click(page.getByRole('button', { name: /^我的笔记/ }))
    } else {
      await dwell(1500)
      await click(button('编辑字幕与检查点'))
      await expect(page.getByRole('dialog')).toBeVisible()
    }
  } else if (scene.module === 'resources') {
    await click(button('课程讲义'))
    await dwell(1400)
    await click(button('查看内容').first())
    await expect(page.getByRole('dialog')).toBeVisible()
  } else if (scene.module === 'graph') {
    await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy', 'false')
    await dwell(2500)
    await click(page.locator('.knowledge-node').filter({ hasText: '栈与队列' }).first())
    if (scene.role === 'teacher') {
      await dwell(1300)
      await click(button('编辑先修关系'))
      await expect(page.getByRole('dialog')).toBeVisible()
    } else {
      await dwell(3800)
      await click(button('先修链'))
    }
  } else if (scene.module === 'practice' && scene.role === 'student') {
    await dwell(3000)
    const index = question.options.findIndex(option => String(option) === String(question.answer))
    if (index < 0) throw new Error('题目答案未匹配选项')
    await page.getByRole('radio').nth(index).check()
    await dwell(1600)
    const response = page.waitForResponse(response => response.url().endsWith('/api/attempts') && response.request().method() === 'POST')
    await click(button('提交答案'))
    evidence.attempt = await (await response).json()
    if (!evidence.attempt.correct) throw new Error('任务作答未通过')
    await expect(page.locator('.answer-feedback')).toBeVisible()
  } else if (scene.module === 'review') {
    const tabs = page.getByRole('tab')
    if (await tabs.count() > 1) {
      await dwell(2000)
      await click(tabs.nth(1))
    }
  } else if (scene.module === 'experiments') {
    await dwell(2000)
    await click(button('压栈'))
    await dwell(2400)
    await click(button('查看栈顶'))
    await dwell(2000)
    await click(button('出栈'))
  } else if (scene.module === 'tutor' || scene.module === 'teacher-ai') {
    const title = scene.role === 'student' ? '我在题目中选了1' : '请依据这个班栈与队列的错误安排30分钟'
    await click(page.locator('.conversation-list button').filter({ hasText: title }).first())
    await expect(page.locator('.chat-message').first()).toBeVisible()
    await dwell(3000)
    const messages = page.locator('.chat-messages')
    await messages.hover()
    await page.mouse.wheel(0, -4500)
    await dwell(4500)
    await page.mouse.wheel(0, 3600)
    if (scene.role === 'teacher') {
      await click(button('编辑与保存教案'))
      await expect(page.getByRole('dialog', { name: '编辑教学安排' })).toBeVisible()
      await dwell(2300)
      const response = page.waitForResponse(response => /\/api\/ai\/teacher-drafts\/\d+\/save$/.test(response.url()))
      await click(button('保存为教案草稿'))
      evidence.saved_lesson = await (await response).json()
    }
  } else if (scene.module === 'classroom') {
    if (scene.role === 'student') {
      const active = page.locator('.activity-list button').filter({ hasText: '进行中' }).first()
      if (await active.count()) await click(active)
    } else {
      await dwell(1800)
      await click(page.locator('.activity-list button').first())
    }
  } else if (scene.module === 'manage') {
    await dwell(2000)
    await click(page.getByRole('tab', { name: '章节内容', exact: true }))
    await dwell(2500)
    await click(page.getByRole('tab', { name: '授课班级', exact: true }))
  } else if (scene.module === 'practice' && scene.role === 'teacher') {
    await click(page.getByRole('tab', { name: '作业记录', exact: true }))
    await click(page.locator('.assignment-row').filter({ hasText: assignment.title }).first().getByRole('button', { name: '查看结果', exact: true }))
    evidence.teacher_results = await api(teacherToken, `/assignments/${assignment.id}/results`)
    if (!evidence.teacher_results.find(student => student.id === 2)?.completed) throw new Error('教师结果未接收学生本次作答')
    await dwell(4300)
    await closeDialog()
    await click(button('发布作业'))
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('作业标题', { exact: true }).fill('栈与队列后续巩固')
    await dialog.locator('select[name=class_id]').selectOption({ index: 1 })
    await dialog.locator('input[type=checkbox]').first().check()
    await dwell(2000)
    const response = page.waitForResponse(response => response.url().endsWith('/api/assignments') && response.request().method() === 'POST')
    await click(dialog.getByRole('button', { name: '发布作业', exact: true }))
    evidence.next_assignment = await (await response).json()
  } else if (scene.module === 'analytics') {
    await dwell(2300)
    await click(page.locator('.matrix-cell').first())
    await expect(page.getByRole('dialog')).toBeVisible()
    await dwell(3400)
    await closeDialog()
    await click(page.getByRole('tab', { name: '教学群组', exact: true }))
  }
}

try {
  const health = await page.request.get(base + '/api/health').then(response => response.json())
  if (health.ai_mode !== 'mock') throw new Error('本轮补录必须以Mock服务回看既有真实回答')
  let teacherToken = await login('teacher')
  const questions = await api(teacherToken, '/questions?course_id=1')
  const question = questions.find(question => question.id === (preflight ? 1 : 11))
  const assignment = await api(teacherToken, '/assignments', { course_id: 1, title: '栈与队列独立检查', question_ids: [question.id], student_ids: [2], knowledge_id: 2 })
  evidence.assignment = assignment
  await click(page.locator('.profile'))
  await click(page.getByRole('button', { name: '学生端', exact: true }))
  if (recorder) await recorder.start()
  for (const scene of scenes) {
    const authentication = scene.role === 'authentication'
    if (await page.getByRole('dialog').count()) await closeDialog()
    if (authentication) {
      if (await page.locator('.profile').isVisible()) await click(page.locator('.profile'))
      await click(page.getByRole('button', { name: scene.identity === 'teacher' ? '教师端' : '学生端', exact: true }))
      await expect(page.locator('.login-form')).toBeVisible()
    } else {
      const parameters = new URLSearchParams({ course: '1' })
      if (scene.module === 'experiments') parameters.set('mode', 'stack')
      if (scene.module === 'practice' && scene.role === 'student') parameters.set('assignment', String(assignment.id))
      await page.goto(base + scene.route + '?' + parameters)
      await settled()
    }
    await dwell(900)
    if (recorder) await recorder.mark(scene.scene_id)
    const captureAt = recorder?.events.at(-1).at || 0
    const started = performance.now()
    if (authentication) {
      await page.screenshot({ path: path.join(directory, scene.scene_id + '-form.png') })
      await dwell(2300)
      const token = await login(scene.identity === 'teacher' ? 'teacher' : 'student1', false)
      if (scene.identity === 'teacher') teacherToken = token
      await settled()
    } else {
      await operate(scene, question, assignment, teacherToken)
    }
    const screenshot = scene.scene_id + '.png'
    await page.screenshot({ path: path.join(directory, screenshot) })
    const elapsed = (performance.now() - started) / 1000
    if (!preflight && elapsed > scene.duration - .3) throw new Error(scene.scene_id + '操作超出镜头时长：' + elapsed)
    await dwell(Math.max(0, scene.duration * 1000 - (performance.now() - started)))
    await dwell(1000)
    if (recorder) await recorder.mark(scene.scene_id + ':结束保护')
    timeline.push({ scene_id: scene.scene_id, role: scene.role, module: scene.module,
      route: page.url().replace(base, ''), capture_at: captureAt, duration: scene.duration,
      valid_until: recorder?.events.at(-1).at || scene.duration + 1,
      operation_seconds: elapsed, screenshot })
    console.log(scene.scene_id, '完成', elapsed.toFixed(2))
  }
  if (errors.length) throw new Error('页面错误：' + errors.join('；'))
} finally {
  await writeFile(path.join(directory, 'business-evidence.json'), JSON.stringify(evidence, null, 2))
  await writeFile(path.join(directory, 'page-errors.json'), JSON.stringify(errors))
  if (recorder) {
    await recorder.stop()
    const recording = JSON.parse(await readFile(path.join(directory, 'recording.json'), 'utf8'))
    const actual = Number(execFileSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', 'import av,sys;v=av.open(sys.argv[1]);print(v.duration/av.time_base)', path.join(directory, 'continuous.mp4')], { encoding: 'utf8', windowsHide: true }).trim())
    evidence.native_duration_seconds = actual
    evidence.clock = 'MediaRecorder控制页单调时钟，片段前后保护留白'
    await writeFile(path.join(directory, 'business-evidence.json'), JSON.stringify(evidence, null, 2))
  }
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
  if (browser) await browser.close()
}
if (timeline.length !== 21) throw new Error('模块覆盖不足')
await writeFile(path.join(root, '.local', preflight ? 'round12-preflight-current.json' : 'round12-modules-current.json'), JSON.stringify({ directory }))
console.log(JSON.stringify({ directory, modules: timeline.length, preflight }))
