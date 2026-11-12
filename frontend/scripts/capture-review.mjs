// 使用独立数据库和本地 Mock，逐页操作后保存实际浏览器截图。
import { chromium, expect } from '@playwright/test'
import { createHash } from 'node:crypto'
import { spawn, spawnSync } from 'node:child_process'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const frontend = path.join(root, 'frontend')
const record = process.argv[2]
if (!record || path.isAbsolute(record) || !record.startsWith('docs/rounds/')) {
  throw new Error('请传入本轮记录路径，例如 docs/rounds/本轮记录.md')
}
await readFile(path.join(root, record))
const plan = JSON.parse(
  await readFile(path.join(frontend, 'scripts/review-capture-plan.json'), 'utf8'),
)
const stamp = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})
  .format(new Date())
  .replace(/[-:]/g, '')
  .replace(' ', '_')
const output = path.join(root, '交付审阅包', `界面截图_${stamp}`)
const buildDirectory = path.join(root, '.local', 'review-builds', stamp)
const apiUrl = 'http://127.0.0.1:8002'
const baseUrl = 'http://127.0.0.1:5176'
const python = path.join(
  root,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
)
const children = []
const failures = []
const files = []
let currentCourse
let currentModule
let browser
let outputCreated = false

async function fingerprint() {
  const paths = []
  async function visit(relative) {
    for (const entry of await readdir(path.join(root, relative), { withFileTypes: true })) {
      const name = `${relative}/${entry.name}`
      if (entry.isDirectory() && entry.name !== '__pycache__') await visit(name)
      else if (entry.isFile() && !entry.name.endsWith('.pyc')) paths.push(name)
    }
  }
  for (const dir of ['frontend/src', 'frontend/public', 'backend/app', 'backend/migrations']) {
    await visit(dir)
  }
  paths.push(
    'frontend/index.html',
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/vite.config.ts',
    'frontend/scripts/review-capture-plan.json',
  )
  const hash = createHash('sha256')
  for (const name of paths.sort())
    hash
      .update(name)
      .update('\0')
      .update(await readFile(path.join(root, name)))
      .update('\0')
  return hash.digest('hex')
}

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: root,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    ...options,
  })
  child.output = ''
  child.stdout.on('data', (data) => {
    child.output = (child.output + data).slice(-5000)
  })
  child.stderr.on('data', (data) => {
    child.output = (child.output + data).slice(-5000)
  })
  child.on('error', (error) => {
    child.launchError = error.message
  })
  children.push(child)
  return child
}

async function run(command, args, options) {
  const child = start(command, args, options)
  await new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code) => (code === 0 ? resolve() : reject(new Error(child.output))))
  })
}

async function freePort(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', () => reject(new Error(`截图隔离端口 ${port} 被占用，请先检查相关进程`)))
    server.listen(port, '127.0.0.1', () => server.close(resolve))
  })
}

async function ready(url, child) {
  await expect
    .poll(
      async () => {
        if (child.launchError || child.exitCode !== null)
          throw new Error(child.launchError || child.output)
        try {
          return (await fetch(url)).ok
        } catch {
          return false
        }
      },
      { timeout: 30000 },
    )
    .toBe(true)
}

async function settle(page) {
  await expect.poll(() => page.locator('.loading:visible').count(), { timeout: 15000 }).toBe(0)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(250)
}

async function go(page, route) {
  await page.goto(baseUrl + route)
  await settle(page)
  await expect(page.locator('h1').first()).toBeVisible()
  if(new URL(page.url()).pathname==='/graph'){
    await expect(page.locator('.knowledge-node').first()).toBeVisible()
    await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy','false')
  }
  if(new URL(page.url()).pathname==='/video'){
    await expect.poll(()=>page.locator('video').evaluate(v=>v.readyState>=2&&!v.seeking),{timeout:20000}).toBe(true)
    await page.locator('video').evaluate(async v=>{
      v.muted=true
      await v.play()
      await new Promise(resolve=>v.requestVideoFrameCallback(()=>v.requestVideoFrameCallback(resolve)))
      v.pause()
    })
    await page.mouse.move(0,0)
  }
}

async function shot(page, state, label, viewport = 'desktop', options = {}) {
  await settle(page)
  if(currentCourse && viewport!=='mobile') expect(await page.evaluate(()=>document.documentElement.scrollHeight), `${currentModule.id}/${state}首屏`).toBeLessThanOrEqual(page.viewportSize().height+2)
  const folder = `${currentModule.role}/${currentModule.id}/${currentCourse?.code || 'public'}`
  const filename = `${folder}/${viewport}_${state}.png`
  await mkdir(path.join(output, folder), { recursive: true })
  const content = await page.screenshot({
    path: path.join(output, filename),
    animations: 'disabled',
    ...options,
  })
  files.push({
    path: filename,
    role: currentModule.role,
    module: currentModule.id,
    module_label: currentModule.label,
    course: currentCourse?.code || null,
    course_label: currentCourse?.title || null,
    layout: await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      width: document.documentElement.scrollWidth,
      viewportHeight: innerHeight,
      viewportWidth: innerWidth,
      devicePixelRatio,
      cssZoom: getComputedStyle(document.documentElement).zoom,
      navigationExpanded: !document.querySelector('.app-shell')?.classList.contains('nav-collapsed'),
      tabs: [...document.querySelectorAll('[role=tab][aria-selected=true]')].map(
        (n) => n.textContent,
      ),
      pages: [...document.querySelectorAll('.workspace-pager')]
        .filter((n) => n.getBoundingClientRect().height)
        .map((n) => n.textContent),
    })),
    state,
    label,
    viewport,
    bytes: content.length,
    sha256: createHash('sha256').update(content).digest('hex'),
    width: content.readUInt32BE(16),
    height: content.readUInt32BE(20),
    route: new URL(page.url()).pathname + new URL(page.url()).search,
  })
}

async function full(page, state, label, viewport = 'desktop') {
  await page.evaluate(() => window.scrollTo(0, 0))
  await shot(page, state, label, viewport, { fullPage: viewport === 'mobile' })
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  const screen = page.viewportSize().height
  if (height > screen * 1.4) {
    for (let y = 0, index = 1; y < height; y += screen - 140, index++) {
      await page.evaluate((offset) => window.scrollTo(0, offset), y)
      await shot(
        page,
        `${state}_part${String(index).padStart(2, '0')}`,
        `${label} · 分段 ${index}`,
        viewport,
      )
      if (y + screen >= height) break
    }
  }
  await page.evaluate(() => window.scrollTo(0, 0))
}

async function dialog(page, state, label) {
  const modal = page.getByRole('dialog')
  await expect(modal).toBeVisible()
  await modal.evaluate((node) => {
    node.scrollTop = 0
  })
  await shot(page, state, label)
  const { height, visible } = await modal.evaluate((node) => ({
    height: node.scrollHeight,
    visible: node.clientHeight,
  }))
  for (
    let y = visible - 100, index = 2;
    y < height && height > visible + 2;
    y += visible - 100, index++
  ) {
    await modal.evaluate((node, offset) => {
      node.scrollTop = offset
    }, y)
    await shot(
      page,
      `${state}_part${String(index).padStart(2, '0')}`,
      `${label} · 弹窗分段 ${index}`,
    )
    if (y + visible >= height) break
  }
}

async function close(page) {
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

async function openDialog(page, button, state, label) {
  await page.getByRole('button', { name: button, exact: true }).first().click()
  await dialog(page, state, label)
  await close(page)
}

async function login(page, account) {
  await page.goto(baseUrl)
  await page.getByLabel('账号', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  const response = page.waitForResponse((r) => r.url().endsWith('/api/auth/login'))
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  const data = await (await response).json()
  await page.getByRole('navigation', { name: '主导航' }).waitFor()
  await settle(page)
  return data.token
}

async function api(token, route, body) {
  const response = await fetch(apiUrl + '/api' + route, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok)
    throw new Error(`截图合成数据操作失败 ${route} ${response.status} ${await response.text()}`)
  return response.json()
}

const viewports = Object.fromEntries(
  Object.entries(plan).filter(([key]) => !['modules', 'courses'].includes(key)),
)
const route = (module, params = {}) =>
  module.route + '?' + new URLSearchParams({ course: currentCourse.id, ...params })
const button = (page, name) => page.getByRole('button', { name, exact: true })
async function captureTabs(page) {
  const names = await page.locator('main [role=tab]:visible').allTextContents()
  for (let i = 0; i < names.length; i++) {
    const tab = page.getByRole('tab', { name: names[i], exact: true }).first()
    if (!(await tab.isVisible())) continue
    await tab.click()
    await full(page, `view-${i + 1}`, `工作视图 · ${names[i]}`)
    const next = page
      .locator('main .workspace-pager:visible button')
      .filter({ has: page.locator('svg.lucide-chevron-right') })
      .first()
    if ((await next.count()) && (await next.isEnabled())) {
      await next.click()
      await full(page, `view-${i + 1}-page2`, `${names[i]} · 第2页`)
    }
  }
}
async function details(page, module, tokens) {
  const shotState = (state, label) => full(page, state, label)
  const modal = async (name, state, label = name) => openDialog(page, name, state, label)
  const tab = async (name) => page.getByRole('tab', { name, exact: true }).click()
  await captureTabs(page)
  await go(page, route(module))
  switch (module.id) {
    case 'dashboard':
      await page.getByLabel('切换当前课程').click()
      await shotState('course-selector', '顶部课程选择器')
      await page.keyboard.press('Escape')
      if (module.role === 'student') {
        await page.getByLabel('切换当前课程').click()
        await button(page, '加入班级').click()
        await dialog(page, 'join', '加入班级')
        await close(page)
      }
      break
    case 'plan':
      await modal('设定学习目标', 'goal-form')
      await modal('新增学习安排', 'plan-form')
      break
    case 'graph':
      await button(page, '章节总览').click()
      await shotState('chapters', '章节总览')
      await button(page, '全图').click()
      await button(page, '聚焦阅读').click()
      await shotState('reading-focus', '阅读聚焦')
      await button(page, '重置图谱视角').click()
      await button(page, '全屏查看').click()
      await expect(page.getByRole('dialog', { name: '全屏知识图谱' })).toBeVisible()
      await shotState('fullscreen', '全屏知识网络')
      await page.keyboard.press('Escape')
      if (module.role === 'teacher') {
        await modal('新增知识点', 'node-form')
        await modal('编辑先修关系', 'prerequisites')
      }
      break
    case 'practice': {
      if (module.role === 'teacher') {
        await button(page, '编辑题目').click()
        await dialog(page, 'question-edit', '题目编辑')
        await close(page)
        await modal('发布作业', 'assignment-form')
        await tab('作业记录')
        await button(page, '查看结果').first().click()
        await dialog(page, 'assignment-results', '作业提交与评分')
        await close(page)
      } else {
        await shotState('question-navigation', '完整题号导航')
        const qs = await api(tokens.teacher, `/questions?course_id=${currentCourse.id}`)
        const q = qs.find((q) => q.type === 'single' && q.status === 'approved')
        await go(page, route(module, { question: q.id }))
        let options = page.getByRole('radio')
        const answer = String(q.answer)
        let correct = q.options.findIndex((v) => String(v) === answer)
        if (correct < 0) correct = Number(answer)
        await options.nth((correct + 1) % (await options.count())).check()
        await button(page, '提交答案').click()
        await expect(page.locator('.answer-feedback')).toBeVisible()
        await shotState('incorrect', '错误作答与后续路径')
        await go(page, route(module, { question: q.id }))
        await options.nth(correct).check()
        await button(page, '提交答案').click()
        await shotState('correct', '正确作答与证据变化')
        const subjective = qs.find((q) => q.type === 'short' && q.status === 'approved')
        if (subjective) {
          await go(page, route(module, { question: subjective.id }))
          await page
            .locator('.question-workspace textarea')
            .fill('先明确输入与不变量，再检查边界条件，最后验证结果。')
          await button(page, '提交答案').click()
          await shotState('subjective', '主观作答等待教师复核')
        }
      }
      break
    }
    case 'review':
      await shotState('correction', '错题订正工作区与复习日程')
      break
    case 'tutor':
      await page.locator('.conversation-list>button:not(.button)').first().click()
      await expect(page.locator('.chat-message').first()).toBeVisible()
      await shotState('history', '已有多轮辅导历史')
      await page
        .getByLabel('输入学习问题')
        .fill(
          currentCourse.code === 'CS101'
            ? '请解释循环边界，给出反例并检查我的理解'
            : '请对照解释栈和队列，给出反例并检查我的理解',
        )
      await button(page, '发送').click()
      await expect(button(page, '停止')).toHaveCount(0, { timeout: 20000 })
      await expect(page.locator('.teaching-actions').last()).toBeVisible()
      await shotState('conversation', '续问与协作教学动作')
      await page.locator('.understanding-check input').last().check()
      await button(page, '提交理解检查').last().click()
      await expect(page.locator('.understanding-check [role=status]').last()).toBeVisible()
      await shotState('check-result', '理解检查与持久化反馈')
      await captureAIInputs(page, module, shotState)
      break
    case 'teacher-ai':
      await captureAIInputs(page, module, shotState)
      await button(page, '开启新对话').click()
      await page.locator('#chat-input').fill('这个班有哪些典型错误？安排40分钟讲评课和两组后续练习。')
      await button(page, '发送').click()
      await expect(button(page, '编辑与保存教案')).toBeVisible()
      await shotState('teaching-draft', '班级证据与教学方案草稿')
      await button(page, '编辑与保存教案').click()
      await dialog(page, 'draft-editor', '可编辑的教学安排')
      await button(page, '关闭').click()
      await button(page, '开启新对话').click()
      await page.locator('#chat-input').fill(`为${currentCourse.title}生成一道基础单选题供审核。`)
      await button(page, '发送').click()
      await expect(page.getByRole('link', { name: '进入题库审核' })).toBeVisible()
      await shotState('question-draft', '教师助手生成题库待审核草稿')
      break
    case 'experiments':
      await button(page, '下一步').click()
      await button(page, '下一步').click()
      await shotState('running', '受控教学实验执行')
      if (currentCourse.code === 'CS101')
        for (const mode of ['py-branch', 'py-list', 'py-function']) {
          await go(page, route(module, { mode }))
          await button(page, '下一步').click()
          await shotState(mode, 'Python · ' + mode)
        }
      else
        for (const mode of ['stack', 'queue', 'tree', 'bfs']) {
          await go(page, route(module, { mode }))
          await shotState(mode, '数据结构 · ' + mode)
          if (mode === 'stack') {
            await button(page, '压栈').click()
            await expect(button(page, '出栈')).toBeEnabled()
            await shotState('stack-push', '栈入栈后的指针与状态')
            await button(page, '出栈').click()
            await expect(button(page, '出栈')).toBeEnabled()
            await shotState('stack-pop', '栈出栈结果与新栈顶')
            for (let index = 0; index < 3; index++) { await button(page, '出栈').click(); await expect(button(page, '出栈')).toBeEnabled() }
            await button(page, '出栈').click()
            await expect(page.locator('.collection-message')).toContainText('结构为空')
            await shotState('stack-empty', '栈为空时的边界反馈')
          }
        }
      break
    case 'classroom':
      if (module.role === 'teacher') {
        await modal('发起课堂互动', 'activity-form')
        await shotState('responses', '真实课堂参与记录')
      } else {
        await page.locator('.activity-list button').filter({ hasText: '已结束' }).first().click()
        await shotState('history', '已结束活动中的本人回答')
        await page.locator('.activity-list button').filter({ hasText: '进行中' }).first().click()
        await page
          .locator('.classroom-answer textarea')
          .fill('我先按步骤检查边界，再用一个反例检验结果，最后比较两种处理方法。')
        await button(page, '提交课堂回答').click()
        await shotState('submitted', '当前活动参与后的保存状态')
      }
      break
    case 'video':
      await expect
        .poll(() => page.locator('video').evaluate((v) => v.readyState))
        .toBeGreaterThanOrEqual(2)
      if (module.role === 'teacher') {
        await button(page, '编辑字幕与检查点').click()
        await dialog(page, 'timeline-editor', '字幕编辑')
        await tab('知识片段')
        await dialog(page, 'editor-segment', '知识片段编辑')
        await tab('理解检查')
        await dialog(page, 'editor-check', '理解检查编辑')
        await close(page)
      } else {
        await page.locator('video').evaluate(async (v) => {
          v.muted = true
          await v.play()
        })
        await page.waitForTimeout(500)
        await page.locator('video').evaluate((v) => v.pause())
        await shotState('playing', '真实视频解码与播放')
        for (const name of ['我的笔记', '课程目录', '片段与检查']) {
          await page.getByRole('button', { name: new RegExp('^' + name) }).click()
          await shotState('video-' + name, name)
        }
        await page.getByRole('button', { name: /随堂理解检查 1/ }).click()
        await dialog(page, 'checkpoint', '视频片段理解检查')
        await close(page)
      }
      break
    case 'resources':
      await button(page, '课程讲义').click()
      await button(page, '查看内容').first().click()
      await dialog(page, 'document', '完整课程讲义阅读')
      await close(page)
      if (module.role === 'teacher') {
        await modal('上传资料或视频', 'upload')
        await modal('新建资料', 'resource-form')
        await button(page, 'AI 备课').click()
        await page.getByRole('dialog').locator('select').selectOption({ index: 1 })
        await page
          .getByRole('dialog')
          .locator('textarea')
          .first()
          .fill('围绕本课程的核心概念设计有对照例子与即时检查的20分钟教学活动')
        await button(page, '生成可编辑草稿').click()
        await expect(page.getByRole('dialog')).toBeVisible()
        await expect(button(page, '生成可编辑草稿')).toHaveCount(0)
        await dialog(page, 'lesson-draft', '本地Mock备课草稿待审核')
        await close(page)
      }
      break
    case 'manage':
      await modal('创建课程', 'course-form')
      await tab('章节内容')
      await modal('新增章节', 'chapter-form')
      await tab('授课班级')
      await modal('新建班级', 'class-form')
      break
    case 'analytics':
      await page.locator('.matrix-cell').first().click()
      await dialog(page, 'matrix-drill', '知识证据钻取')
      await close(page)
      await page.getByRole('tab', { name: /作答复核/ }).click()
      await button(page, '查看并复核').first().click()
      await dialog(page, 'review-form', '主观题量规复核')
      await close(page)
      break
  }
}

async function captureAIInputs(page, module, shotState) {
  await button(page, '开启新对话').click()
  await page.getByLabel('选择AI模型').selectOption('deepseek-v4-pro')
  await shotState('model-switch', '逐请求选择DeepSeek Pro')
  await page.getByLabel('选择问答附件').setInputFiles({ name: '课程补充笔记.md', mimeType: 'text/markdown', buffer: Buffer.from(currentCourse.code === 'CS101' ? 'Python列表别名共享对象，切片创建新的外层列表，嵌套元素仍可能共享。' : '队列遵循先进先出，BFS在入队时标记顶点，避免重复加入队列。') })
  await expect(page.locator('.composer-attachments')).toBeVisible()
  await page.locator('#chat-input').fill('根据这份笔记解释核心概念，并引用来源。')
  await button(page, '发送').click()
  await expect(button(page, '停止')).toHaveCount(0, { timeout: 25000 })
  await expect(page.locator('.message-sources').last()).toBeVisible()
  await shotState('attachment', '附件进入问答与定位引用')
  await button(page, '开启新对话').click()
  await page.getByLabel('选择语音文件').setInputFiles(path.join(root, '.local/round6-voice-sample.mp3'))
  await expect(page.locator('#chat-input')).not.toHaveValue('', { timeout: 60000 })
  await shotState('voice-input', '本地识别后可编辑的语音文字')
}
function escapeHtml(text) {
  return String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;')
}
try {
  await freePort(8002)
  await freePort(5176)
  await mkdir(output, { recursive: true })
  outputCreated = true
  await run(process.execPath, ['node_modules/typescript/bin/tsc', '-b'], { cwd: frontend })
  await run(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--outDir', buildDirectory, '--emptyOutDir'], { cwd: frontend })
  const sourceFingerprint = await fingerprint()
  const backend = start(
    python,
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8002'],
    {
      env: {
        ...process.env,
        AI_MODE: 'mock',
        DATABASE_PATH: `.local/review-captures/${stamp}.db`,
        PYTHONIOENCODING: 'utf-8',
      },
    },
  )
  await ready(apiUrl + '/api/health', backend)
  const web = start(
    process.execPath,
    [
      'node_modules/vite/bin/vite.js',
      'preview',
      '--outDir',
      buildDirectory,
      '--host',
      '127.0.0.1',
      '--port',
      '5176',
      '--strictPort',
    ],
    { cwd: frontend, env: { ...process.env, VITE_API_PROXY_TARGET: apiUrl } },
  )
  await ready(baseUrl, web)
  browser = await chromium.launch({
    channel: process.platform === 'win32' ? 'chrome' : undefined,
    headless: true,
  })
  const pages = {},
    tokens = {}
  for (const role of ['public', 'student', 'teacher']) {
    const context = await browser.newContext({
      viewport: plan.desktop,
      locale: 'zh-CN',
      reducedMotion: 'reduce',
      deviceScaleFactor: 1,
    })
    const page = await context.newPage()
    page.setDefaultTimeout(15000)
    page.on('pageerror', (error) => failures.push({ role, message: error.message }))
    pages[role] = page
    if (role !== 'public')
      tokens[role] = await login(page, role === 'student' ? 'student1' : 'teacher')
  }
  if ((await api(tokens.teacher, '/ai/status')).mode !== 'mock') throw new Error('截图只允许Mock')
  const courses = await api(tokens.teacher, '/courses')
  for (const module of plan.modules) {
    currentModule = module
    const page = pages[module.role]
    for (const code of module.role === 'public' ? [null] : plan.courses) {
      currentCourse = code ? courses.find((c) => c.code === code) : null
      if (code && !currentCourse) throw new Error(`缺少正常初始化课程 ${code}`)
      console.log(`正在截图 ${module.role}/${module.id}/${code || 'public'}`)
      for (const [viewport, size] of Object.entries(viewports)) {
        await page.setViewportSize(size)
        await go(page, code ? route(module) : module.route)
        if (module.id === 'graph')
          await expect(page.locator('.knowledge-node').first()).toBeVisible()
        if (viewport !== 'mobile' && code) {
          const height = await page.evaluate(() => document.documentElement.scrollHeight)
          expect(height, `${code}/${module.id}/${viewport}整页应在首屏内`).toBeLessThanOrEqual(
            size.height + 2,
          )
        }
        await full(
          page,
          'full',
          `${module.label} · ${currentCourse?.title || '登录'} · ${viewport}`,
          viewport,
        )
      }
      await page.setViewportSize(plan.desktop)
      await go(page, code ? route(module) : module.route)
      if (module.role === 'public') {
        await button(page, '教师端').click()
        await full(page, 'teacher', '教师登录')
        await page.setViewportSize(plan.mobile)
        await full(page, 'teacher-mobile', '教师登录 · 手机窄屏', 'mobile')
        await page.setViewportSize(plan.desktop_short)
        await full(page, 'teacher-short', '教师登录 · 短窗口', 'desktop_short')
        await page.setViewportSize(plan.desktop)
        await button(page, '学生端').click()
      } else await details(page, module, tokens)
    }
  }
  if (failures.length) throw new Error(JSON.stringify(failures))
  if (sourceFingerprint !== (await fingerprint())) throw new Error('截图期间源码变更')
  const manifest = {
    version: 1,
    status: 'complete',
    captured_at: new Date().toISOString(),
    round_record: record,
    source_fingerprint: sourceFingerprint,
    ai_mode: 'mock',
    real_ai_requests: 0,
    fixture: '普通init_db版本化样例；脚本仅执行学习、阅读与表单预览，不创建基础课程内容',
    source_commit_at_capture: spawnSync('git', ['rev-parse', 'HEAD'], {
      cwd: root,
      encoding: 'utf8',
    }).stdout.trim(),
    viewports,
    courses: plan.courses,
    modules: plan.modules,
    files,
    page_errors: failures,
  }
  await writeFile(path.join(output, '截图清单.json'), JSON.stringify(manifest, null, 2), 'utf8')
  let markdown =
    '# 第六轮双角色双课程界面截图\n\n桌面100%缩放首屏，保留导航、顶部栏和完整工作区。手机全页及分段。每图记录课程、路由、标签、分页、视口、devicePixelRatio和SHA256。\n\n'
  let html =
    '<html lang="zh-CN"><meta charset="utf-8"><title>学脉双课程界面审阅</title><style>body{font:16px system-ui;background:#f1f0e8;color:#254b46;margin:32px}section{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}figure{margin:0;background:white;padding:12px;border-radius:12px}img{width:100%;height:230px;object-fit:contain;object-position:top}figcaption{padding:10px}h2{margin-top:45px}</style><h1>学脉双课程界面审阅</h1><p>桌面首屏 · 手机全页 · 关键交互状态 · 正常初始化 · 本地Mock</p>'
  for (const module of plan.modules)
    for (const code of module.role === 'public' ? [null] : plan.courses) {
      const title = `${module.role} / ${module.label} / ${code || 'public'}`
      markdown += `## ${title}\n\n`
      html += `<h2>${title}</h2><section>`
      for (const f of files.filter(
        (f) => f.role === module.role && f.module === module.id && f.course === code,
      )) {
        markdown += `- [${f.label} · ${f.width}×${f.height}](${f.path})\n`
        html += `<figure><a href="${f.path}"><img loading="lazy" src="${f.path}"></a><figcaption>${escapeHtml(f.label)}</figcaption></figure>`
      }
      markdown += '\n'
      html += '</section>'
    }
  await writeFile(path.join(output, '截图索引.md'), markdown, 'utf8')
  await writeFile(path.join(output, '截图总览.html'), html + '</html>', 'utf8')
  console.log(`截图完成：${files.length}张PNG\n${output}`)
} catch (error) {
  if (outputCreated)
    await writeFile(
      path.join(output, '截图失败.json'),
      JSON.stringify(
        {
          status: 'failed',
          module: currentModule,
          course: currentCourse?.code,
          error: error.message,
          files,
        },
        null,
        2,
      ),
    )
  throw error
} finally {
  await browser?.close().catch(() => {})
  for (const child of children.reverse()) {
    if (child.exitCode !== null || !child.pid) continue
    if (process.platform === 'win32')
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
        windowsHide: true,
        stdio: 'ignore',
      })
    else child.kill('SIGTERM')
  }
}
