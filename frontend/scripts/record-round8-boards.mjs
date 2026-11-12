// 原生连续录制作品介绍、统一框架和可交互的真实开发档案。
import path from 'node:path'
import { writeFile } from 'node:fs/promises'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const base = 'http://127.0.0.1:8010/demo/第八轮演示源/boards.html'
const directory = path.join(root, '.local', 'round8-boards-' + Date.now())
const recorder = await createRecorder({ base, directory })
const { page } = recorder
await page.evaluate(() => window.show('intro'))
await recorder.start()
const origin = performance.now()
const timeline = []
const patch = process.env.DEMO_ROUND8_PATCH === '1'
try {
  const sequence = patch ? ['framework', ...Array.from({ length: 18 }, (_, index) => index)] : ['intro', 'pain', 'framework', ...Array.from({ length: 18 }, (_, index) => index), 'outro']
  for (const name of sequence) {
    const board = await page.evaluate(name => window.show(name), name)
    const at = (performance.now() - origin) / 1000
    timeline.push({ name, at, duration: board.duration, title: board.title || name })
    console.log(name, at.toFixed(2))
    if (name === 'framework') {
      for (let index = 0; index < 4; index++) {
        await page.evaluate(index => window.highlight(index), index)
        await pause(index === 3 ? 7500 : 6500)
      }
    } else if (typeof name === 'number') {
      await page.locator('.original').hover()
      await pause(4300)
      await page.mouse.wheel(0, 170)
      await page.locator('.diff').hover()
      await page.mouse.wheel(0, name % 6 === 3 ? 260 : 100)
      await pause(3200)
    } else await pause(board.duration * 1000)
  }
} finally {
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
  await recorder.stop()
  await writeFile(path.join(root, patch ? '.local/round8-boards-patch-current.json' : '.local/round8-boards-current.json'), JSON.stringify({ directory }))
}
