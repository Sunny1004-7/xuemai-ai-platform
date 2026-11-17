// 使用录制器时钟和段间保护时间，采集开场、固定框架与协作过程。
import path from 'node:path'
import { readFile, writeFile } from 'node:fs/promises'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const project = path.join(root, 'docs/demo/第十二轮演示源')
const scenes = JSON.parse(await readFile(path.join(project, 'scenes.json'), 'utf8'))
const phases = JSON.parse(await readFile(path.join(project, 'framework-phases.json'), 'utf8'))
const directory = path.join(root, '.local', 'round12-boards-' + Date.now())
const base = 'http://127.0.0.1:8010/demo/第十二轮演示源/boards.html'
const recorder = await createRecorder({ base, directory })
const { page } = recorder
const timeline = [], highlights = []
await recorder.start()
try {
  for (const scene of scenes.filter(scene => ['presentation', 'development'].includes(scene.role))) {
    const boardId = scene.board_id || scene.scene_id
    await page.evaluate(name => window.show(name), boardId)
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(image => image.decode())) })
    await page.mouse.move(1910, 935)
    await pause(900)
    await recorder.mark(boardId)
    const captureAt = recorder.events.at(-1).at
    const started = performance.now()
    await page.screenshot({ path: path.join(directory, boardId + '.png') })
    if (scene.scene_id === 'framework') {
      for (const phase of phases) {
        await pause(Math.max(0, phase.at * 1000 - (performance.now() - started)))
        const geometry = await page.evaluate(name => window.highlight(name), phase.name)
        highlights.push({ ...geometry, at: phase.at })
      }
    } else if (scene.role === 'development') {
      await pause(3400)
      await page.evaluate(() => window.scrollRecord())
    }
    await pause(Math.max(0, scene.duration * 1000 - (performance.now() - started)))
    await pause(1000)
    await recorder.mark(boardId + ':结束保护')
    timeline.push({ scene_id: scene.scene_id, segment_id: boardId, capture_at: captureAt,
      valid_until: recorder.events.at(-1).at, duration: scene.duration, screenshot: boardId + '.png' })
  }
} finally {
  await recorder.stop()
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
  await writeFile(path.join(directory, 'highlight-audit.json'), JSON.stringify(highlights, null, 2))
}
const reference = highlights[0].image
if (highlights.some(item => ['x', 'y', 'width', 'height'].some(key => Math.abs(item.image[key] - reference[key]) > .01))) {
  throw new Error('框架位置或比例发生变化')
}
await writeFile(path.join(root, '.local/round12-boards-current.json'), JSON.stringify({ directory }))
console.log(JSON.stringify({ directory, scenes: timeline.length, framework_stationary: true }))
