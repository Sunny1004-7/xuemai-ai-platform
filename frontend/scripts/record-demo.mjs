// 真实本机页面录制。开发证据是已发生记录的回放，明确不冒充实时生成。
import { chromium, expect } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5175'
const quick = process.env.DEMO_QUICK === '1'
const taskTitle = `Python边界巩固-${new Date().toISOString().slice(11, 19).replaceAll(':', '')}`
const scale = quick ? 0.03 : 1
const totalSeconds=450
const runDir = path.join(
  root,
  '.local',
  'recording',
  new Date().toISOString().replace(/[:.]/g, '-'),
)
await fs.mkdir(runDir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1920, height: 1000 },
  deviceScaleFactor: 1,
})
const page = await context.newPage()
const events = [],
  shots = []
let recording = true,
  caption = '',
  index = 0
const start = Date.now()
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const escape = (s) => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
async function overlay(text) {
  caption = text
  await page.evaluate((text) => {
    document.getElementById('recording-caption')?.remove()
    const el = document.createElement('div')
    el.id = 'recording-caption'
    el.textContent = text
    Object.assign(el.style, {
      position: 'fixed',
      bottom: '0',
      left: '0',
      right: '0',
      zIndex: '999999',
      padding: '16px 35px',
      background: '#172840f2',
      color: 'white',
      font: '20px "Microsoft YaHei", sans-serif',
      lineHeight: '1.55',
      pointerEvents: 'none',
      borderTop: '3px solid #54bfa8',
    })
    document.body.append(el)
  }, text)
}
async function until(second) {
  const delay = start + second * 1000 * scale - Date.now()
  if (delay > 0) await sleep(delay)
}
async function scene(second, name, text, action) {
  await until(second)
  console.log(JSON.stringify({ at: Math.round((Date.now() - start) / 1000), scene: name }))
  events.push({ at: (Date.now() - start) / 1000, name, caption: text })
  if (action) await action()
  if (text) await overlay(text)
}
async function login(username) {
  await page.goto(base)
  if (!(await page.getByLabel('账号', { exact: true }).count())) {
    await page.locator('.profile').click()
  }
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  const response=page.waitForResponse(r=>r.url().endsWith('/api/auth/login'))
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await page.getByRole('navigation', { name: '主导航' }).waitFor()
  return (await (await response).json()).token
}

async function readApi(token,route){
  const response=await fetch(new URL('/api'+route,base),{headers:{Authorization:`Bearer ${token}`}})
  if(!response.ok)throw new Error(`只读演示对象查询失败：${route}`)
  return response.json()
}
async function go(route){
  await page.goto(base+route)
  await expect(page.locator('main h1')).toBeVisible()
  await expect(page.locator('main .loading')).toHaveCount(0)
  if(route.startsWith('/graph')) {
    await expect(page.locator('.knowledge-node').first()).toBeVisible()
    await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy','false')
  }
}
async function correctAnswer(question){
  const index=question.options.findIndex(option=>String(option)===String(question.answer))
  if(index<0)throw new Error('演示题答案与选项不一致')
  await page.getByRole('radio').nth(index).check()
  await page.getByRole('button',{name:'提交答案',exact:true}).click()
  await expect(page.locator('.answer-feedback')).toBeVisible()
}

await page.goto(pathToFileURL(path.join(root, 'docs/development-process/round5-replay.html')).href + '#intro')
const capture = (async () => {
  while (recording) {
    const tick = Date.now()
    const file = `${String(index++).padStart(5, '0')}.png`
    try {
      await page.screenshot({
        path: path.join(runDir, file),
        timeout: 2500,
        animations: 'disabled',
      })
      shots.push({ file, at: (Date.now() - start) / 1000 })
    } catch (error) {
      if (index < 4) console.warn('录制帧暂未成功：' + error.message.slice(0, 250))
    }
    await sleep(Math.max(10, 500 - (Date.now() - tick)))
  }
})()
try {
  await scene(12, '登录', '', () => page.goto(base))
  await until(19)
  await login('student1')
  await scene(25, '学习工作台', '')
  await page.getByLabel('切换当前课程').click()
  await until(28)
  await page.getByRole('option',{name:/Python/}).click()
  await until(32)
  await go('/plan?course=2')
  await until(37)
  await page.getByRole('tab',{name:'预算内路径',exact:true}).click()
  await scene(45, '知识图谱', '', () => go('/graph?course=1'))
  await expect(page.locator('.knowledge-node')).toHaveCount(31)
  await until(55)
  await page.getByLabel('切换当前课程').click()
  await page.getByRole('option',{name:/Python/}).click()
  await expect(page.locator('.knowledge-node')).toHaveCount(27)
  await expect(page.locator('.graph-canvas')).toHaveAttribute('aria-busy','false')
  await until(60)
  await page.getByLabel('定位知识点').fill('循环')
  await until(65)
  await page.getByRole('button', { name: '全屏查看', exact: true }).click()
  await until(70)
  await page.getByRole('button', { name: '先修链', exact: true }).click()
  await until(76)
  await page.getByRole('button', { name: '聚焦阅读', exact: true }).click()
  await until(81)
  await page.keyboard.press('Escape')
  await scene(85, '视频学习', '', async () => {
    await go('/video?course=2')
    const v = page.locator('video')
    await v.waitFor()
    await v.evaluate(async (v) => {
      v.muted = true
      await v.play()
    })
  })
  await until(103)
  const checkpoint = page.getByRole('dialog')
  if (await checkpoint.count()) {
    await checkpoint.getByRole('radio').nth(1).check()
    await checkpoint.getByRole('button', { name: '提交检查' }).click()
  }
  await until(108)
  if (await checkpoint.count()) await checkpoint.getByRole('button', { name: '继续观看' }).click()
  await page.getByRole('button', { name: /我的笔记/ }).click()
  await page.getByPlaceholder('想明白了什么？还有什么问题？').fill('range右端点不包含；每轮累加后，total对应已处理的整数。')
  await page.getByRole('button', { name: '保存笔记' }).click()
  await scene(120, '智能练习', '', () => go('/practice?course=2'))
  await page.getByRole('button',{name:'跳转第10题',exact:true}).click()
  await until(128)
  await page.getByRole('button',{name:'跳转第1题',exact:true}).click()
  await page.getByRole('radio').first().check()
  await until(132)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await scene(145, '上下文辅导', '', () => go('/tutor?course=2'))
  await page.locator('.conversation-list>button:not(.button)').first().click()
  await until(150)
  await page.getByLabel('输入学习问题').fill('请用一个循环边界反例继续解释，再检查我的理解。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await until(162)
  await expect(page.getByRole('button',{name:'停止',exact:true})).toHaveCount(0)
  await page.locator('.collaboration-trace summary').last().click()
  await page.locator('.understanding-check').last().scrollIntoViewIfNeeded()
  await until(170)
  await page.locator('.understanding-check input').last().check()
  await page.getByRole('button', { name: '提交理解检查', exact: true }).last().click()
  await until(178)
  await page.getByRole('button', { name: '对话历史', exact: true }).click()
  await scene(185, '交互实验', '', () => go('/experiments?course=2&mode=py-loop'))
  for (let i = 0; i < 5; i++) {
    await until(188 + i * 2)
    await page.getByRole('button', { name: '下一步', exact: true }).click()
  }
  let teacherToken
  await scene(205, '教师工作台', '', async () => {teacherToken=await login('teacher');await go('/analytics?course=2')})
  await until(213)
  await page.getByLabel('筛选学情章节').selectOption({label:'条件与循环'})
  await until(218)
  await page.locator('.matrix-cell').first().click()
  await until(226)
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('tab',{name:'教学群组',exact:true}).click()
  const questions=(await readApi(teacherToken,'/questions?course_id=2')).filter(q=>q.type==='single'&&q.status==='approved').slice(0,2)
  await scene(230, '针对性任务', '', async () => {
    await go('/practice?course=2')
    await page.getByRole('button',{name:'发布作业',exact:true}).click()
  })
  await until(235)
  await page.getByRole('dialog').locator('input[name=title]').fill(taskTitle)
  await page.getByRole('dialog').locator('select[name=class_id]').selectOption({index:1})
  for(const q of questions) await page.getByRole('dialog').locator('.checkbox-list label').filter({hasText:q.title}).getByRole('checkbox').check()
  await until(242)
  await page.getByRole('dialog').getByRole('button', { name: '发布作业', exact: true }).click()
  const assignment=(await readApi(teacherToken,'/assignments?course_id=2')).find(a=>a.title===taskTitle)
  if(!assignment)throw new Error('已发布任务未落库')
  await scene(250, '学生完成', '', async () => {
    await login('student1')
    await go(`/practice?course=2&assignment=${assignment.id}`)
  })
  await correctAnswer(questions[0])
  await until(257)
  await page.getByRole('button', { name: '下一道练习', exact: true }).click()
  await correctAnswer(questions[1])
  await scene(265, '任务结果', '', async () => {
    await login('teacher')
    await go('/practice?course=2')
    await page.getByRole('tab',{name:'作业记录',exact:true}).click()
    await page
      .locator('.assignment-row')
      .filter({ hasText: taskTitle })
      .getByRole('button', { name: '查看结果', exact: true })
      .click()
  })
  const replay = pathToFileURL(path.join(root, 'docs/development-process/round5-replay.html')).href
  for (const [at, id, name] of [
    [280, 'chain1', '知识图谱开发'],
    [320, 'chain2', '学习证据开发'],
    [360, 'chain3', '人工智能服务开发'],
    [400, 'methods', '四项方法与验证'],
    [412, 'path-results', '路径约束实验'],
    [426, 'group-results', '错因分层实验'],
  ]) {
    await scene(at, name, '', () => page.goto(replay + '#' + id))
  }
  await until(440)
  await page.goto(replay + '#outro')
  await until(totalSeconds)
} catch (error) {
  recording = false
  await capture
  await fs.writeFile(
    path.join(runDir, 'failed.json'),
    JSON.stringify({ message: error.message, events }, null, 2),
  )
  await browser.close()
  throw error
}
recording = false
await capture
await browser.close()
await fs.writeFile(
  path.join(runDir, 'recording.json'),
  JSON.stringify({ width: 1920, height: 1080, contentHeight:1000, subtitleBand:80, duration:totalSeconds, quick, events, shots }, null, 2),
)
if (!shots.length) throw new Error('没有捕获任何有效视频帧，停止导出')
if (quick) {
  console.log(JSON.stringify({ preflight: 'ok', runDir, seconds: shots.at(-1).at }))
  process.exit(0)
}
const lines = ['ffconcat version 1.0']
for (let i = 0; i < shots.length; i++) {
  lines.push(`file '${shots[i].file}'`)
  lines.push(`duration ${Math.max(0.01, (shots[i + 1]?.at || totalSeconds) - shots[i].at).toFixed(3)}`)
}
lines.push(`file '${shots.at(-1).file}'`)
await fs.writeFile(path.join(runDir, 'frames.ffconcat'), lines.join('\n'))
const python = path.join(root, '.venv/Scripts/python.exe')
const ffmpeg = execFileSync(
  python,
  ['-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],
  { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
).trim()
const out = path.join(root, '最终参赛提交材料/学脉XueMai-演示视频.mp4')
await fs.mkdir(path.dirname(out), { recursive: true })
execFileSync(
  ffmpeg,
  [
    '-y',
    '-loglevel',
    'error',
    '-f',
    'concat',
    '-safe',
    '0',
    '-i',
    path.join(runDir, 'frames.ffconcat'),
    '-r',
    '24',
    '-vf',
    'pad=1920:1080:0:0:color=0xf7f6f2',
    '-t',
    String(totalSeconds),
    '-c:v',
    'libx264',
    '-preset',
    'fast',
    '-crf',
    '23',
    '-pix_fmt',
    'yuv420p',
    '-movflags',
    '+faststart',
    out,
  ],
  { stdio: 'inherit' },
)
console.log(
  JSON.stringify({
    output: out,
    frames: shots.length,
    recorded_seconds: shots.at(-1).at,
    development_evidence_seconds: 120,
    runDir,
  }),
)
