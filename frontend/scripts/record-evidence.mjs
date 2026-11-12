import path from 'node:path'
import { writeFile } from 'node:fs/promises'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const base = 'http://127.0.0.1:8010/demo/第七轮演示源/boards.html'
const directory = path.join(root, '.local/round7-evidence-video')
const recorder = await createRecorder({ base, directory })
const { page } = recorder
await page.evaluate(() => window.show(0))
await recorder.start()
const timeline = []
try {
  const origin = performance.now()
  for (let index = 0; index < 23; index++) {
    const board = await page.evaluate(index => window.show(index), index)
    const at = (performance.now() - origin) / 1000
    timeline.push({ index, at, ...board })
    console.log(index, board.title)
    await pause(board.duration * 1000)
  }
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
} finally {
  await recorder.stop()
}
