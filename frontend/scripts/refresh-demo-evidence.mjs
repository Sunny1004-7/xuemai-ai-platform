// 只补录静态片头与已发生开发回放，不改变原始系统操作帧。
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const directory = path.resolve(process.argv[2] || '')
const recordingRoot = path.join(root, '.local', 'recording') + path.sep
if (!directory.startsWith(recordingRoot)) throw new Error('需要本项目原始录制目录')
const data = JSON.parse(await fs.readFile(path.join(directory, 'recording.json'), 'utf8'))
if (data.quick) throw new Error('不能使用快速预演帧')
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
const inserts = []
try {
  for (const [at, id] of [[0, 'intro'], [280, 'chain1'], [315, 'chain2'], [350, 'chain3'], [385, 'round3'], [410, 'outro']]) {
    await page.goto(pathToFileURL(path.join(root, 'docs/development-process/round3-replay.html')).href + '#' + id)
    await page.evaluate(() => document.fonts.ready)
    const bottom = await page.locator(`#${id}`).evaluate((section) =>
      Math.max(...[...section.children].map((el) => el.getBoundingClientRect().bottom)) - section.getBoundingClientRect().top)
    if (bottom > 970) throw new Error(`回放页面超出内容区域：${id}，${bottom}px`)
    const file = `evidence-${id}.png`
    await page.screenshot({ path: path.join(directory, file) })
    inserts.push({ file, at })
  }
} finally { await browser.close() }
const shots = [...data.shots.filter((s) => s.at >= 12 && s.at < 280), ...inserts].sort((a, b) => a.at - b.at)
const lines = ['ffconcat version 1.0']
for (let i = 0; i < shots.length; i++) {
  lines.push(`file '${shots[i].file}'`, `duration ${Math.max(.01, (shots[i + 1]?.at || 420) - shots[i].at).toFixed(3)}`)
}
lines.push(`file '${shots.at(-1).file}'`)
await fs.writeFile(path.join(directory, 'evidence.ffconcat'), lines.join('\n'))
await fs.writeFile(path.join(directory, '静态画面补录说明.json'), JSON.stringify({
  reason: '四项方法卡片取消继承跨行规则，保持原始系统操作及开发引文',
  original_recording: 'recording.json', inserts, content_bounds_checked: true,
}, null, 2))
const ffmpeg = execFileSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'], { encoding: 'utf8' }).trim()
execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(directory, 'evidence.ffconcat'), '-t', '420', '-r', '24', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path.join(root, '最终参赛提交材料/学脉XueMai-演示视频.mp4')], { stdio: 'inherit' })
console.log(JSON.stringify({ duration: 420, static_frames: inserts.length, original_system_frames_preserved: true }))
