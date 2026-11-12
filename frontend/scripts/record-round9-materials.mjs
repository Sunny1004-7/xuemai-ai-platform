// 局部补录当前画板与双主题登录。保留原生连续帧，所有AI生成均阻止。
import path from 'node:path'
import { readFile, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const mode = process.argv[2] || 'boards'
const frameworkOnly = process.argv.includes('--framework-only')
const material = frameworkOnly ? 'framework' : mode
const directory = path.join(root, '.local', 'round9-' + material + '-' + Date.now())
const base = mode === 'boards'
  ? 'http://127.0.0.1:8010/demo/第九轮演示源/boards.html'
  : 'http://127.0.0.1:5173'
const recorder = await createRecorder({ base, directory })
const { page } = recorder
await page.route('**/api/ai/**', route => route.abort())
const timeline = []
const highlights = []
if (mode === 'boards') await page.evaluate(() => window.show('intro'))
await page.evaluate(() => document.fonts.ready)
await recorder.start()
try {
  if (mode === 'login') {
    await recorder.mark('双主题背景')
    await pause(4300)
    await recorder.click(page.getByRole('button', { name: '教师端', exact: true }))
    await pause(5000)
  } else {
    const phases = JSON.parse(await readFile(path.join(root, 'docs/demo/第九轮演示源/framework-phases.json'), 'utf8'))
    for (const name of (frameworkOnly ? ['framework'] : ['intro','pain','framework','outro'])) {
      const board = await page.evaluate(name => window.show(name), name)
      await page.evaluate(async () => {
        await document.fonts.ready
        await Promise.all([...document.images].map(image => image.decode()))
      })
      await recorder.mark(name)
      const event = recorder.events.at(-1)
      timeline.push({ name, at: event.at, duration: board.duration })
      const origin = performance.now()
      if (name === 'framework') {
        for (const phase of phases) {
          await pause(Math.max(0, phase.at*1000-(performance.now()-origin)))
          const audit = await page.evaluate(name => window.highlight(name), phase.name)
          highlights.push({ name:phase.name, at:(performance.now()-origin)/1000, ...audit })
        }
      }
      await pause(Math.max(0,board.duration*1000-(performance.now()-origin)))
    }
  }
} finally {
  await recorder.stop()
  const recording = JSON.parse(await readFile(path.join(directory,'recording.json'),'utf8'))
  const python = path.join(root,'.venv/Scripts/python.exe')
  const actual = Number(execFileSync(python,['-c','import av,sys; v=av.open(sys.argv[1]); print(v.duration/av.time_base)',path.join(directory,'continuous.mp4')],{encoding:'utf8',windowsHide:true}).trim())
  const offset = actual-recording.elapsed_seconds
  for (const row of timeline) row.capture_at = row.at + offset
  await writeFile(path.join(directory,'timeline.json'),JSON.stringify(timeline,null,2))
  await writeFile(path.join(directory,'highlight-audit.json'),JSON.stringify(highlights,null,2))
  await writeFile(path.join(root,'.local',`round9-${material}-current.json`),JSON.stringify({directory}))
}
