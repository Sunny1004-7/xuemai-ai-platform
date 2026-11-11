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
const apiUrl = 'http://127.0.0.1:8002'
const baseUrl = 'http://127.0.0.1:5176'
const python = path.join(
  root,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
)
const children = []
const failures = []
const files = []
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
}

async function shot(page, state, label, viewport = 'desktop', options = {}) {
  await settle(page)
  const folder = `${currentModule.role}/${currentModule.id}`
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
  await shot(page, state, label, viewport, { fullPage: true })
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

async function question(page, id) {
  await go(page, `/practice?question=${id}`)
}
async function submit(page) {
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.answer-feedback')).toBeVisible()
}

async function details(page, module, fixture) {
  const capture = (id, label) => full(page, id, label)
  const modal = (button, id, label) => openDialog(page, button, id, label)
  if (module.role === 'public') {
    await page.getByLabel('账号', { exact: true }).fill('unknown-review-account')
    await page.getByLabel('密码', { exact: true }).fill('invalid-review-password')
    await page.getByRole('button', { name: '进入学脉', exact: true }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await capture('login-error', '账号验证错误反馈')
    return
  }
  if (module.role === 'student') {
    switch (module.id) {
      case 'plan':
        await page.getByRole('button', { name: '设定学习目标', exact: true }).first().click()
        await page.getByLabel('目标名称', { exact: true }).fill('独立掌握栈与队列')
        await page.getByLabel('写给自己的说明').fill('合成审阅示例 · 用实验和练习验证理解')
        await dialog(page, 'goal-form', '个人目标填写表单')
        await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
        await expect(page.getByRole('dialog')).toHaveCount(0)
        await page.getByRole('button', { name: '新增学习安排', exact: true }).click()
        await page.getByLabel('学习安排', { exact: true }).fill('完成一次栈操作实验并复盘')
        await dialog(page, 'plan-form', '个人学习安排表单')
        await page.getByRole('dialog').getByRole('button', { name: '保存', exact: true }).click()
        await expect(page.getByRole('dialog')).toHaveCount(0)
        await capture('populated', '目标与安排保存后的页面')
        break
      case 'courses':
        await modal('加入班级', 'join', '邀请码加入班级表单')
        break
      case 'graph':
        await page.getByRole('button', { name: /冒泡排序，掌握度/ }).click()
        await capture('focused', '选中知识点与资源联动')
        await page.getByLabel('定位知识点').fill('快速排序')
        await capture('searched','搜索定位知识点')
        await page.getByLabel('定位知识点').fill('')
        await page.getByRole('button', {name:'邻近知识',exact:true}).click()
        await capture('neighbors','邻近节点聚焦')
        await page.getByRole('button', {name:'先修链',exact:true}).click()
        await capture('ancestors','先修链展开')
        await page.getByRole('button', {name:'全图',exact:true}).click()
        await capture('all-network','章节聚类与圆滑先修连线')
        await page.getByRole('button',{name:'聚焦阅读',exact:true}).click()
        await capture('reading-focus','固定阅读比例与选中知识')
        await page.getByRole('button',{name:'收起知识详情',exact:true}).click()
        await capture('detail-collapsed','收起详情后的图谱空间')
        await page.getByRole('button',{name:'重置图谱视角',exact:true}).click()
        await capture('fit-network','按当前画布完整适配知识网络')
        await page.getByRole('button',{name:'章节总览',exact:true}).click()
        await capture('chapters','章节总览')
        await page.getByLabel('选择图谱章节').selectOption('1')
        await capture('chapter-network','章节内知识网络')
        await page.getByRole('button',{name:'全屏查看',exact:true}).click()
        await capture('fullscreen','独立全屏工作区与小地图')
        await page.getByRole('button',{name:'放大图谱'}).click()
        await page.keyboard.press('Escape')
        await capture('camera-restored','退出全屏后保留选中与视角')
        break
      case 'practice':
        await question(page, 1)
        await page.getByRole('button', { name: '查看第一条提示', exact: true }).click()
        await capture('hint', '渐进提示')
        await page.getByRole('radio').nth(0).check()
        await submit(page)
        await capture('incorrect', '错误作答与订正引导')
        await question(page, 1)
        await page.getByRole('radio').nth(2).check()
        await submit(page)
        await capture('correct', '正确作答与解析')
        for (const [id, state, answer] of [
          [2, 'multiple', null],
          [4, 'true-false', null],
          [5, 'fill', '有序'],
          [
            6,
            'short-pending',
            '每次选取极端枢轴会产生不平衡划分，递归规模依次减少一，累计比较次数为平方级。',
          ],
          [
            fixture.stepId,
            'step-pending',
            '第一步比较相邻元素。第二步交换逆序元素。第三步最大元素移到末尾。',
          ],
        ]) {
          await question(page, id)
          if (id === 2) {
            for (const index of [0, 1, 3]) await page.getByRole('checkbox').nth(index).check()
          } else if (id === 4) await page.getByRole('radio').nth(0).check()
          else await page.getByLabel('填写答案').fill(answer)
          await submit(page)
          await capture(state, `题型与作答结果 · ${state}`)
        }
        await go(page, '/practice')
        await page.getByRole('button', { name: fixture.assignmentTitle, exact: true }).click()
        await capture('assignment', '班级作业与题目进度')
        break
      case 'tutor':
        await page.getByLabel('输入学习问题').fill('栈与队列有什么区别？请结合资料给出提示。')
        await page.getByRole('button', { name: '发送', exact: true }).click()
        await expect(page.locator('.message-sources > span').first()).toBeVisible()
        await expect(page.getByRole('button', { name: '停止生成', exact: true })).toHaveCount(0)
        await expect(page.getByRole('button',{name:'提交理解检查',exact:true})).toBeVisible()
        await page.locator('.chat-messages').evaluate(el => {el.scrollTop=0})
        await capture('conversation-start','辅导对话开头与课程上下文')
        await page.locator('.chat-messages').evaluate(el => {el.scrollTop=el.scrollHeight})
        await page.locator('.collaboration-trace summary').last().click()
        await capture('collaboration','诊断策略校验协作记录')
        await capture('conversation', 'Mock流式辅导与课程引用')
        await capture('understanding-check','辅导后的结构化动作与理解检查')
        await page.locator('.understanding-check input').first().check()
        await page.getByRole('button',{name:'提交理解检查',exact:true}).click()
        await expect(page.locator('.understanding-check [role="status"]')).toBeVisible()
        await capture('check-result','实际理解检查评分与下一教学动作')
        await page.getByRole('button', { name: '对话历史', exact: true }).click()
        await capture('history', '可恢复的辅导历史')
        await page.route('**/api/ai/chat', (route) =>
          route.fulfill({
            status: 503,
            contentType: 'application/json',
            body: JSON.stringify({ detail: '审阅故障样例：AI服务暂时不可用，请稍后重试。' }),
          }),
        )
        await page.getByLabel('输入学习问题').fill('请继续解释')
        await page.getByRole('button', { name: '发送', exact: true }).click()
        await expect(page.locator('.chat-message.error')).toBeVisible()
        await capture('service-error', '模拟503服务异常的界面反馈')
        await page.unroute('**/api/ai/chat')
        break
      case 'review':
        await page.getByRole('radio').nth(2).check()
        await submit(page)
        await capture('correction', '错题订正与复测结果')
        break
      case 'experiments':
        for (let i = 0; i < 3; i++)
          await page.getByRole('button', { name: '下一步', exact: true }).click()
        await capture('sort-running', '排序运行状态与算法解释')
        for (const [state, name] of [
          ['stack', '栈的操作'],
          ['queue', '队列操作'],
          ['tree', '二叉搜索树'],
          ['bfs', '广度优先搜索'],
        ]) {
          await page.getByRole('button', { name, exact: true }).click()
          if (state === 'stack' || state === 'queue') {
            await page.getByLabel('待加入元素').fill('42')
            await page
              .getByRole('button', { name: state === 'stack' ? '压栈' : '入队', exact: true })
              .click()
          } else await page.getByRole('button', { name: '下一步', exact: true }).click()
          await capture(state, `${name}实际执行状态`)
        }
        break
      case 'classroom':
        await page
          .locator('.classroom-card')
          .first()
          .getByRole('textbox')
          .fill('合成审阅回答 · 排队买票体现先进先出，撤销操作体现后进先出。')
        await page.getByRole('button', { name: '提交课堂回答', exact: true }).first().click()
        await expect(
          page.getByText('合成审阅回答 · 排队买票体现先进先出，撤销操作体现后进先出。').first(),
        ).toBeVisible()
        await capture('submitted', '学生提交课堂回答')
        break
      case 'video':
        await page.getByRole('button', { name: '字幕检索', exact: true }).click()
        await page.getByLabel('搜索视频字幕').fill('比较')
        await capture('subtitle-search', '视频字幕关键词检索')
        await page.getByRole('button', { name: /我的笔记/ }).click()
        await page
          .getByPlaceholder('想明白了什么？还有什么问题？')
          .fill('合成审阅笔记 · 一轮冒泡将最大元素移至右端。')
        await page.getByRole('button', { name: '保存笔记', exact: true }).click()
        await expect(page.getByText('合成审阅笔记 · 一轮冒泡将最大元素移至右端。')).toBeVisible()
        await capture('notes', '时间戳笔记保存结果')
        await page.getByRole('button', { name: '随堂理解检查 1', exact: true }).click()
        await page.getByRole('dialog').getByRole('radio').nth(1).check()
        await page.getByRole('button', { name: '提交检查', exact: true }).click()
        await dialog(page, 'checkpoint', '视频互动检查与反馈')
        await close(page)
        break
      case 'resources':
        await page
          .locator('.resource-card')
          .filter({ hasText: '栈与队列学习讲义' })
          .getByRole('button', { name: '查看内容' })
          .click()
        await dialog(page, 'document', '课程讲义内容与引用版本')
        await close(page)
        break
    }
    return
  }
  switch (module.id) {
    case 'manage':
      await modal('创建课程', 'course-form', '创建课程表单')
      await modal('编辑', 'course-edit', '课程信息编辑')
      await modal('新增章节', 'chapter-form', '章节组织表单')
      await modal('新建班级', 'class-form', '创建班级表单')
      await modal('添加已有学生', 'member-form', '班级成员管理表单')
      break
    case 'graph':
      await page.getByRole('button',{name:'全屏查看',exact:true}).click()
      await capture('fullscreen','教师全屏图谱与编辑工具')
      await page.keyboard.press('Escape')
      await modal('新增知识点', 'node-form', '新增知识点与学习目标')
      await modal('编辑知识点', 'node-edit', '编辑当前知识点')
      await modal('编辑先修关系', 'prerequisites', '先修关系管理与现有连线')
      break
    case 'resources':
      await modal('上传资料或视频', 'upload', '教学资料与视频上传')
      await page.getByRole('button', { name: '编辑栈与队列学习讲义', exact: true }).click()
      await dialog(page, 'resource-edit', '讲义正文与知识点编辑')
      await close(page)
      await page.getByRole('button', { name: 'AI 备课', exact: true }).first().click()
      await page.getByLabel('本课知识点').selectOption('2')
      await page.getByLabel('教学意图').fill('面向初学者讲解栈与队列，用生活实例安排一次理解检查。')
      await dialog(page, 'lesson-intent', 'AI备课教学意图')
      await page.getByRole('button', { name: '生成可编辑草稿', exact: true }).click()
      await expect(page.getByRole('dialog', { name: '编辑并审核教学草稿' })).toBeVisible()
      await dialog(page, 'lesson-draft', 'Mock教案草稿与教师审核')
      await close(page)
      await page
        .locator('.resource-card')
        .filter({ hasText: '栈与队列学习讲义' })
        .getByRole('button', { name: '查看内容' })
        .click()
      await dialog(page, 'document', '教师讲义预览与版本记录')
      await close(page)
      break
    case 'practice':
      await modal('编辑题目', 'question-edit', '题库编辑与审核表单')
      await modal('复制新版本', 'question-copy', '题目变式与新版本草稿')
      await modal('发布作业', 'assignment-form', '班级作业组卷与发布表单')
      await page
        .locator('.assignment-row')
        .filter({ hasText: fixture.assignmentTitle })
        .getByRole('button', { name: '查看结果' })
        .click()
      await capture('assignment-results', '逐学生作业完成与成绩')
      break
    case 'video':
      await modal('编辑字幕与检查点', 'timeline-editor', '字幕、知识片段和互动时间轴完整表单')
      break
    case 'analytics':
      await page.getByLabel('筛选学情章节').selectOption('1')
      await capture('matrix-filtered','章节筛选下的多人知识矩阵')
      await page.getByRole('tab',{name:'教学干预',exact:true}).click()
      await capture('intervention-workspace','动态群组与知识教学关注工作区')
      await page.getByRole('button',{name:'安排匹配任务',exact:true}).first().click()
      await dialog(page,'group-task','动态群组匹配题目与目标学生')
      await close(page)
      await page.getByRole('button',{name:'查看证据',exact:true}).first().click()
      await dialog(page,'learning-evidence','学生作答证据与参数下钻')
      await close(page)
      await page.locator('.assignment-row').first().getByRole('button',{name:'查看结果',exact:true}).click()
      await capture('intervention-results','教学任务完成与证据状态对照')
      await page.getByRole('button', { name: '分层任务', exact: true }).first().click()
      await dialog(page, 'targeted-task', '分层任务发布与目标学生')
      await close(page)
      await page.getByRole('tab',{name:'学生轨迹',exact:true}).click()
      await capture('student-trajectories','学生学习轨迹与差异分析')
      await page.getByRole('tab',{name:/作答复核/}).click()
      await capture('review-workspace','主观作答复核工作区')
      await page.getByRole('button', { name: '查看并复核', exact: true }).first().click()
      await dialog(page, 'subjective-review', '学生主观作答与评分量规')
      await page.getByRole('button', { name: '获取 AI 量规建议', exact: true }).click()
      await expect(page.locator('.rubric-advice')).toBeVisible()
      await dialog(page, 'rubric-advice', 'Mock量规建议与教师最终评分')
      await close(page)
      break
    case 'classroom':
      await modal('发起课堂互动', 'activity-form', '课堂即时提问与任务发布')
      await capture('responses', '教师查看真实提交的课堂回答')
      break
  }
}

function escapeHtml(text) {
  return String(text).replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char],
  )
}

try {
  await freePort(8002)
  await freePort(5176)
  const sourceFingerprint = await fingerprint()
  await mkdir(path.join(root, '.local/review-captures'), { recursive: true })
  await mkdir(path.dirname(output), { recursive: true })
  await mkdir(output)
  outputCreated = true
  console.log('正在执行严格TypeScript检查与生产构建')
  await run(process.execPath, ['node_modules/typescript/bin/tsc', '-b'], { cwd: frontend })
  await run(process.execPath, ['node_modules/vite/bin/vite.js', 'build'], { cwd: frontend })
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
      '--host',
      '127.0.0.1',
      '--port',
      '5176',
      '--strictPort',
    ],
    {
      cwd: frontend,
      env: { ...process.env, VITE_API_PROXY_TARGET: apiUrl },
    },
  )
  await ready(baseUrl, web)
  browser = await chromium.launch({
    channel: process.platform === 'win32' ? 'chrome' : undefined,
    headless: true,
  })
  const pages = {}
  const tokens = {}
  for (const role of ['public', 'student', 'teacher']) {
    const context = await browser.newContext({
      viewport: plan.desktop,
      locale: 'zh-CN',
      reducedMotion: 'reduce',
    })
    const page = await context.newPage()
    page.setDefaultTimeout(12000)
    page.on('pageerror', (error) => failures.push({ role, message: error.message }))
    pages[role] = page
    if (role !== 'public')
      tokens[role] = await login(page, role === 'student' ? 'student1' : 'teacher')
  }
  const ai = await api(tokens.teacher, '/ai/status')
  if (ai.mode !== 'mock') throw new Error('截图只允许在Mock模式运行')
  const step = await api(tokens.teacher, '/questions', {
    course_id: 1,
    knowledge_id: 6,
    type: 'step',
    title: '合成审阅题 · 分步描述一轮冒泡排序，并说明循环不变量。',
    options: [],
    answer: '比较相邻元素，交换逆序对，依次向右推进，最大元素归位。',
    difficulty: 2,
    hints: ['关注每轮末尾的元素。'],
  })
  const assignmentTitle = '合成审阅作业 · 栈与排序巩固'
  const assignment = await api(tokens.teacher, '/assignments', {
    course_id: 1,
    class_id: 1,
    title: assignmentTitle,
    question_ids: [1, 3],
    description: '审阅截图专用的本地合成数据',
  })
  const questions = await api(tokens.teacher, '/questions?course_id=1')
  for (const id of [1, 3])
    await api(tokens.student, '/attempts', {
      question_id: id,
      answer: questions.find((q) => q.id === id).answer,
      assignment_id: assignment.id,
    })
  for (const role of ['student', 'teacher']) {
    const actual = await pages[role]
      .getByRole('navigation', { name: '主导航' })
      .locator('a')
      .evaluateAll((nodes) => nodes.map((n) => new URL(n.href).pathname).sort())
    const expected = plan.modules
      .filter((m) => m.role === role && m.navigation)
      .map((m) => new URL(m.route, baseUrl).pathname)
      .sort()
    expect(actual, `${role}导航必须完整列入截图计划`).toEqual(expected)
  }
  for (const module of plan.modules) {
    currentModule = module
    const page = pages[module.role]
    console.log(`正在截图 ${module.role} / ${module.label}`)
    await page.setViewportSize(plan.desktop)
    await go(page, module.route)
    if (module.id === 'video') {
      await page.locator('video').evaluate(async (video) => {
        video.muted = true
        await video.play()
        video.pause()
      })
    }
    await full(page, 'full', `${module.label} · 桌面全页`)
    for (const viewport of ['desktop_compact','desktop_wide']) {
      await page.setViewportSize(plan[viewport])
      await full(page,'full',`${module.label} · ${plan[viewport].width}px全页`,viewport)
    }
    await page.setViewportSize(plan.mobile)
    await settle(page)
    await full(page, 'full', `${module.label} · 手机窄屏全页`, 'mobile')
    await page.setViewportSize(plan.desktop)
    await details(page, module, { stepId: step.id, assignmentTitle })
  }
  if (failures.length) throw new Error(`浏览器运行错误 ${JSON.stringify(failures)}`)
  if (sourceFingerprint !== (await fingerprint()))
    throw new Error('截图期间源码变更，请重新执行截图')
  const manifest = {
    version: 1,
    status: 'complete',
    captured_at: new Date().toISOString(),
    round_record: record,
    source_fingerprint: sourceFingerprint,
    ai_mode: 'mock',
    real_ai_requests: 0,
    fixture: '独立SQLite合成演示数据，主观作答和课堂回答由本脚本实际提交',
    source_commit_at_capture: spawnSync('git', ['rev-parse', 'HEAD'], {
      cwd: root,
      encoding: 'utf8',
    }).stdout.trim(),
    viewports: Object.fromEntries(Object.entries(plan).filter(([key]) => key !== "modules")),
    modules: plan.modules,
    files,
    page_errors: failures,
  }
  await writeFile(path.join(output, '截图清单.json'), JSON.stringify(manifest, null, 2), 'utf8')
  const intro =
    '# 学脉全模块界面截图\n\n本组截图来自本轮生产构建、真实浏览器和隔离的合成演示数据库。AI功能使用本地Mock，503异常为浏览器故障注入。每个模块包含桌面与390px手机窄屏全页图，长页面和长弹窗另附重叠分段图。交互详情图使用桌面尺寸。\n\n'
  let markdown = intro
  let html =
    '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>学脉界面截图总览</title><style>body{font:16px system-ui;margin:32px;background:#f4f7f8;color:#172b36}h2{margin-top:48px}section{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px}figure{margin:0;background:white;padding:12px;border-radius:12px}img{width:100%;height:230px;object-fit:contain;object-position:top}a{color:#126b60}figcaption{padding:10px}</style><h1>学脉全模块界面截图</h1><p>真实浏览器截图 · 独立合成数据 · 本地Mock · 点击图片查看原图</p>'
  for (const module of plan.modules) {
    const title = `${module.role} · ${module.label}`
    markdown += `## ${title}\n\n`
    html += `<h2>${escapeHtml(title)}</h2><section>`
    for (const file of files.filter((f) => f.role === module.role && f.module === module.id)) {
      markdown += `- [${file.label} · ${file.width}×${file.height}](${file.path})\n`
      html += `<figure><a href="${file.path}"><img loading="lazy" src="${file.path}" alt="${escapeHtml(file.label)}"></a><figcaption>${escapeHtml(file.label)} · ${file.width}×${file.height}</figcaption></figure>`
    }
    markdown += '\n'
    html += '</section>'
  }
  await writeFile(path.join(output, '截图索引.md'), markdown, 'utf8')
  await writeFile(path.join(output, '截图总览.html'), html + '</html>', 'utf8')
  console.log(`截图完成 ${plan.modules.length} 个模块，${files.length} 张PNG\n${output}`)
} catch (error) {
  if (currentModule && browser) {
    const contexts = browser.contexts()
    for (const context of contexts) {
      for (const page of context.pages()) {
        if (page.url().includes(baseUrl)) {
          await page
            .screenshot({
              path: path.join(output, `失败现场_${contexts.indexOf(context)}.png`),
              fullPage: true,
            })
            .catch(() => {})
        }
      }
    }
  }
  if (outputCreated) {
    await writeFile(
      path.join(output, '截图失败.json'),
      JSON.stringify(
        { status: 'failed', module: currentModule, error: error.message, files },
        null,
        2,
      ),
    ).catch(() => {})
  }
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
