// 连续记录新画板与历史协作过程，固定总图，只移动高亮。
import path from 'node:path'
import { readFile, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createRecorder, pause, root } from './continuous-recorder.mjs'

const current = JSON.parse(await readFile(path.join(root, 'docs/demo/current.json'), 'utf8'))
const project = path.join(root, current.project)
const scenes = JSON.parse(await readFile(path.join(project, 'scenes.json'), 'utf8'))
const boards = JSON.parse(await readFile(path.join(project, 'boards.json'), 'utf8'))
const phases = JSON.parse(await readFile(path.join(project, 'framework-phases.json'), 'utf8'))
const directory = path.join(root, '.local', 'round11-boards-' + Date.now())
const base = 'http://127.0.0.1:8010/' + current.project.replace('docs/', '') + '/boards.html'
const recorder = await createRecorder({ base, directory })
const { page } = recorder
await page.evaluate(() => window.show('intro'))
const timeline = [], highlights = []
await recorder.start()
try {
  for (const scene of scenes.filter(scene => !['student', 'teacher'].includes(scene.role))) {
    const pieces = scene.role === 'development'
      ? boards.filter(board => board.scene_id === scene.scene_id).map(board => ({ id: board.board_id, duration: scene.duration / 6 }))
      : [{ id: scene.scene_id === 'context' ? 'pain' : scene.scene_id, duration: scene.duration }]
    if (!pieces.length) throw new Error('镜头没有对应素材 ' + scene.scene_id)
    for (const piece of pieces) {
      await page.evaluate(name => window.show(name), piece.id)
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(image => image.decode())) })
      await recorder.mark(piece.id)
      const at = recorder.events.at(-1).at
      timeline.push({ scene_id: scene.scene_id, segment_id: piece.id, at, duration: piece.duration })
      const started = performance.now()
      if (scene.scene_id === 'framework') {
        await page.screenshot({ path: path.join(directory, 'framework-full.png') })
        for (const phase of phases) {
          await pause(Math.max(0, phase.at * 1000 - (performance.now() - started)))
          const audit = await page.evaluate(name => window.highlight(name), phase.name)
          audit.at = phase.at
          highlights.push(audit)
          if (phase.name) await page.screenshot({ path: path.join(directory, 'framework-' + phase.name + '.png') })
        }
      } else if (scene.role === 'development') {
        await pause(3000)
        await page.evaluate(() => window.scrollRecord())
      }
      await pause(Math.max(0, piece.duration * 1000 - (performance.now() - started)))
    }
  }
} finally {
  await recorder.stop()
  const recording = JSON.parse(await readFile(path.join(directory, 'recording.json'), 'utf8'))
  const actual = Number(execFileSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', 'import av,sys;v=av.open(sys.argv[1]);print(v.duration/av.time_base)', path.join(directory, 'continuous.mp4')], { encoding: 'utf8', windowsHide: true }).trim())
  for (const row of timeline) row.capture_at = row.at + actual - recording.elapsed_seconds
  await writeFile(path.join(directory, 'timeline.json'), JSON.stringify(timeline, null, 2))
  await writeFile(path.join(directory, 'highlight-audit.json'), JSON.stringify(highlights, null, 2))
}
const reference = highlights[0]?.image
if (!reference || highlights.some(item => ['x', 'y', 'width', 'height'].some(key => Math.abs(item.image[key] - reference[key]) > .01))) {
  throw new Error('框架位置或比例随高亮变化')
}
await writeFile(path.join(root, '.local/round11-boards-current.json'), JSON.stringify({ directory }))
console.log(JSON.stringify({ directory, fixed_framework: true, scenes: timeline.length }))
