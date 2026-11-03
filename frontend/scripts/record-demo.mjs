// 真实本机页面录制。开发证据是已发生记录的回放，明确不冒充实时生成。
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5175'
const quick = process.env.DEMO_QUICK === '1'
const scale = quick ? 0.03 : 1
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
  await overlay(text)
}
async function login(username) {
  await page.goto(base)
  if (!(await page.getByLabel('账号', { exact: true }).count())) {
    await page.getByRole('button', { name: /课程教师|学习者/ }).click()
  }
  await page.getByLabel('账号', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('Xuemai123!')
  await page.getByRole('button', { name: '进入学脉', exact: true }).click()
  await page.getByRole('navigation', { name: '主导航' }).waitFor()
}

await page.setContent(
  `<html lang="zh-CN"><meta charset="utf-8"><body style="margin:0;background:#19273f;color:white;font-family:'Microsoft YaHei',sans-serif"><main style="padding:180px 160px"><p style="color:#68ceb6;font-size:26px">师生双端 AI 个性化智慧教育平台</p><h1 style="font-size:100px;margin:40px 0">学脉 XueMai</h1><p style="font-size:32px;line-height:1.8">把课程连成知识网络<br>让每一次学习，都成为下一步的依据</p><p style="color:#b4c5db;font-size:22px;margin-top:65px">真实本机操作 · 合成教学数据 · AI 使用 Mock 演示<br>后段为真实开发记录回放 · 旁白为本机合成语音</p></main></body></html>`,
)
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
  await scene(10, '登录', '使用合成学生账号登录；所有操作连接本机真实后端。', () =>
    login('student1'),
  )
  await scene(20, '学习概览', '每项学习推荐都说明原因，并直接连接视频、错题或针对练习。')
  await scene(35, '知识图谱', '统一知识实体连接先修关系、资源与个人掌握状态。', () =>
    page.goto(`${base}/graph?knowledge=6`),
  )
  await until(46)
  await page
    .getByRole('button', { name: /放大/ })
    .click()
    .catch(() => {})
  await until(54)
  await page.mouse.wheel(0, 230)
  await scene(
    65,
    '视频学习',
    '原创教学视频真实播放；字幕定位、时间戳笔记和检查题共用课程知识点。',
    async () => {
      await page.goto(`${base}/video?t=10`)
      const video = page.locator('video')
      await video.waitFor()
      await video.evaluate(async (v) => {
        v.muted = true
        await v.play()
      })
    },
  )
  await until(80)
  const checkpoint = page.getByRole('dialog')
  if (await checkpoint.count()) {
    await checkpoint.getByRole('radio').nth(1).check()
    await checkpoint.getByRole('button', { name: '提交检查' }).click()
  }
  await until(88)
  if (await checkpoint.count()) await checkpoint.getByRole('button', { name: '继续观看' }).click()
  await page.getByRole('button', { name: /我的笔记/ }).click()
  await page
    .getByPlaceholder('想明白了什么？还有什么问题？')
    .fill('每轮通过相邻比较，将最大元素移动到末尾。')
  await page.getByRole('button', { name: '保存笔记' }).click()
  await scene(100, '智能练习', '客观题使用确定性评分；提示使用和独立作答影响学习证据。', () =>
    page.goto(`${base}/practice?question=1`),
  )
  await until(111)
  await page.getByRole('radio').nth(2).check()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await until(119)
  await page.mouse.wheel(0, 300)
  await scene(
    130,
    '课程辅导',
    '本段为 Mock 固定示例，零真实API调用。辅导带入题目、课程资料和版本引用。',
    () => page.goto(`${base}/tutor?knowledge=2&question=1`),
  )
  await page.getByLabel('输入学习问题').fill('栈和队列有什么区别？请先给我一点提示，再做理解检查。')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await until(145)
  await page.getByRole('button', { name: '对话历史' }).click()
  await scene(
    160,
    '交互实验',
    '实验由可测试的真实算法运行，动画与步骤状态同步；AI不替代核心计算。',
    () => page.goto(`${base}/experiments`),
  )
  for (let i = 0; i < 4; i++) {
    await until(166 + i * 4)
    await page
      .getByRole('button', { name: /下一步/ })
      .click()
      .catch(() => {})
  }
  await scene(
    185,
    '教师教学',
    '教师维护题库并发布作业；学生提交后，结果进入同一学习证据模型。',
    async () => {
      await login('teacher')
      await page.goto(`${base}/practice`)
    },
  )
  await until(196)
  await page.getByRole('button', { name: '发布作业', exact: true }).click()
  await page.getByRole('dialog').getByLabel('作业标题').fill('演示：栈与队列的理解检查')
  await page.getByRole('dialog').getByLabel('发布到班级').selectOption('1')
  await page.getByRole('dialog').getByRole('checkbox').first().check()
  await until(207)
  await page.getByRole('dialog').getByRole('button', { name: '发布作业', exact: true }).click()
  await scene(
    215,
    '学情与分层',
    '从薄弱知识与具体错因安排教学任务，完成后再次查看分析；主观题由教师复核。',
    () => page.goto(`${base}/analytics`),
  )
  await until(226)
  await page.getByRole('button', { name: '分层任务', exact: true }).nth(1).click()
  await until(236)
  await page.getByRole('dialog').getByRole('button', { name: '关闭' }).click()
  await scene(240, '课堂互动', '课堂提问和反馈约每7秒同步；学生回答按课程与个人权限隔离。', () =>
    page.goto(`${base}/classroom`),
  )
  await scene(
    250,
    '真实AI协同证据',
    '以下为本次实际开发记录的筛选回放；用户原话与Codex自主分工分开，不冒充实时生成。',
    () =>
      page.goto(
        pathToFileURL(path.join(root, 'docs/development-process/raw-evidence/index.html')).href,
      ),
  )
  const sections = [
    [260, 'knowledge', '知识图谱：真实任务约束、接口契约、数据库占位符错误与修复。'],
    [295, 'practice', '练习与推荐：真实自主任务、学习证据规则、作业发布与权限校验。'],
    [330, 'ai', 'AI辅导：真实FTS误召回、SSE中断与私有视频漏洞，均有修复与测试。'],
  ]
  for (const [at, key, text] of sections) {
    await until(at)
    const tabs = await page.getByRole('button').all()
    // 证据页使用带中文名称的核心链按钮；只通过可见文本选择。
    const names = key === 'knowledge' ? /图谱|知识/ : key === 'practice' ? /练习|作业/ : /AI|辅导/
    for (const tab of tabs) {
      if (names.test(await tab.innerText())) {
        await tab.click()
        break
      }
    }
    await overlay(text)
    for (let i = 1; i <= 5; i++) {
      await until(at + i * 5)
      await page.mouse.wheel(0, 460)
    }
  }
  await until(365)
  await page.keyboard.press('Home')
  await page.mouse.wheel(0, -6000)
  await overlay('真实演进记录关联中文Git提交；本地回归使用Mock，真实联调仅3次、共220 Tokens。')
  await until(385)
  await page.setContent(
    `<html lang="zh-CN"><meta charset="utf-8"><body style="margin:0;background:#19273f;color:white;font-family:'Microsoft YaHei',sans-serif"><main style="padding:160px"><h1 style="font-size:64px">从学习证据，回到教学行动。</h1><p style="font-size:30px;line-height:2;color:#b6d8d4">真实全栈业务 · 可解释学习规则 · 有边界的AI服务<br>中文细粒度提交 · 原始可见Prompt证据 · 本机复现脚本</p><p style="font-size:26px;margin-top:70px">github.com/Sunny1004-7/xuemai-ai-platform</p><p style="font-size:22px;color:#b4c5db">本片为真实本机操作与开发记录回放；预置学习记录为合成数据。<br>生成式内容供教学核对，学习成效仍需真实场景进一步验证。</p></main></body></html>`,
  )
  await until(395)
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
  JSON.stringify({ width: 1920, height: 1080, quick, events, shots }, null, 2),
)
if (!shots.length) throw new Error('没有捕获任何有效视频帧，停止导出')
if (quick) {
  console.log(JSON.stringify({ preflight: 'ok', runDir, seconds: shots.at(-1).at }))
  process.exit(0)
}
const lines = ['ffconcat version 1.0']
for (let i = 0; i < shots.length; i++) {
  lines.push(`file '${shots[i].file}'`)
  lines.push(`duration ${Math.max(0.01, (shots[i + 1]?.at || 395) - shots[i].at).toFixed(3)}`)
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
    development_evidence_seconds: 135,
    runDir,
  }),
)
