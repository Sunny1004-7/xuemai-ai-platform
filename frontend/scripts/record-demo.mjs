// 真实本机页面录制。开发证据是已发生记录的回放，明确不冒充实时生成。
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5175'
const quick = process.env.DEMO_QUICK === '1'
const taskTitle = `数组知识巩固-${new Date().toISOString().slice(11, 19).replaceAll(':', '')}`
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
  viewport: { width: 1920, height: 1080 },
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
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await page.getByRole('navigation', { name: '主导航' }).waitFor()
}

await page.goto(pathToFileURL(path.join(root, 'docs/development-process/round4-replay.html')).href + '#intro')
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
  await scene(45, '知识图谱', '', () => page.goto(`${base}/graph`))
  await until(52)
  await page.getByRole('button', { name: /线性结构，展开章节/ }).click()
  await until(59)
  await page.getByLabel('定位知识点').fill('快速排序')
  await until(65)
  await page.getByRole('button', { name: '全屏查看', exact: true }).click()
  await until(70)
  await page.getByRole('button', { name: '先修链', exact: true }).click()
  await until(76)
  await page.getByRole('button', { name: '聚焦阅读', exact: true }).click()
  await until(81)
  await page.keyboard.press('Escape')
  await scene(85, '视频学习', '', async () => {
    await page.goto(`${base}/video?t=1`)
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
  await page
    .getByPlaceholder('想明白了什么？还有什么问题？')
    .fill('每轮相邻比较后，当前最大元素到达末尾。')
  await page.getByRole('button', { name: '保存笔记' }).click()
  await scene(120, '智能练习', '', () => page.goto(`${base}/practice?question=1`))
  await until(128)
  await page.getByRole('radio').nth(2).check()
  await until(132)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await scene(145, '上下文辅导', '', () => page.goto(`${base}/tutor?knowledge=2&question=1`))
  await until(150)
  await page.getByLabel('输入学习问题').fill('请对照解释栈与队列，再检查我的理解。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await until(162)
  await page.locator('.collaboration-trace summary').click()
  await page.locator('.understanding-check').scrollIntoViewIfNeeded()
  await until(170)
  await page.locator('.understanding-check input').first().check()
  await page.getByRole('button', { name: '提交理解检查', exact: true }).click()
  await until(178)
  await page.getByRole('button', { name: '对话历史', exact: true }).click()
  await scene(185, '交互实验', '', () => page.goto(`${base}/experiments`))
  for (let i = 0; i < 5; i++) {
    await until(188 + i * 2)
    await page.getByRole('button', { name: '下一步', exact: true }).click()
  }
  await scene(205, '教师工作台', '', () => login('teacher'))
  await until(213)
  await page.goto(`${base}/analytics`)
  await until(218)
  await page.getByLabel('筛选学情章节').selectOption({label:'线性结构'})
  await page.locator('.matrix-cell').first().click()
  await until(226)
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('tab',{name:'教学干预',exact:true}).click()
  await page.locator('.teaching-groups').scrollIntoViewIfNeeded()
  await scene(230, '针对性任务', '', async () => {
    await page
      .locator('.knowledge-analysis>div')
      .filter({ has: page.getByRole('heading', { name: '数组与链表', exact: true }) })
      .getByRole('button', { name: '分层任务' })
      .click()
  })
  await until(235)
  await page.getByRole('dialog').getByLabel('任务名称').fill(taskTitle)
  await page
    .getByRole('dialog')
    .locator('.checkbox-list label')
    .filter({ hasText: '陈星河' })
    .getByRole('checkbox')
    .check()
  await until(242)
  await page.getByRole('button', { name: '发布分层任务', exact: true }).click()
  await scene(250, '学生完成', '', async () => {
    await login('student1')
    await page.goto(`${base}/practice`)
    await page.getByRole('button', { name: taskTitle, exact: true }).click()
  })
  await page.getByRole('radio').first().check()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await until(257)
  await page.getByRole('button', { name: '下一道练习', exact: true }).click()
  await page.getByRole('radio').first().check()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await scene(265, '任务结果', '', async () => {
    await login('teacher')
    await page.goto(`${base}/analytics?view=intervention`)
    await page
      .locator('.assignment-row')
      .filter({ hasText: taskTitle })
      .getByRole('button', { name: '查看结果', exact: true })
      .click()
  })
  const replay = pathToFileURL(path.join(root, 'docs/development-process/round4-replay.html')).href
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
  JSON.stringify({ width: 1920, height: 1080, duration:totalSeconds, quick, events, shots }, null, 2),
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
