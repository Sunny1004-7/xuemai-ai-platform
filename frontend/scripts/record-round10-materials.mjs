// 原生连续录制大字画板与逐阶段开发原始记录，模型请求由实验账本管理。
import path from 'node:path'
import { readFile, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createRecorder, pause, root } from './continuous-recorder.mjs'
const frameworkOnly=process.argv.includes('--framework-only')
const material=frameworkOnly?'framework':'boards'
const directory=path.join(root,'.local','round10-'+material+'-'+Date.now())
const recorder=await createRecorder({base:'http://127.0.0.1:8010/demo/第十轮演示源/boards.html',directory})
const {page}=recorder
await page.evaluate(()=>window.show('intro'))
await page.evaluate(()=>document.fonts.ready)
const timeline=[],highlights=[]
await recorder.start()
try {
  const phases=JSON.parse(await readFile(path.join(root,'docs/demo/第十轮演示源/framework-phases.json'),'utf8'))
  for(const name of (frameworkOnly?['framework']:['intro','pain','framework','results',...Array.from({length:18},(_,i)=>String(i)),'outro'])){
    const board=await page.evaluate(name=>window.show(name),name)
    await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))})
    await recorder.mark(name);const at=recorder.events.at(-1).at
    timeline.push({name,at,duration:board.duration})
    const origin=performance.now()
    if(name==='framework')for(const phase of phases){await pause(Math.max(0,phase.at*1000-(performance.now()-origin)));highlights.push(await page.evaluate(n=>window.highlight(n),phase.name))}
    if(/^\d+$/.test(name)){await pause(3200);await page.evaluate(()=>window.scrollRecord())}
    await pause(Math.max(0,board.duration*1000-(performance.now()-origin)))
  }
} finally {
  await recorder.stop()
  const recording=JSON.parse(await readFile(path.join(directory,'recording.json'),'utf8'))
  const actual=Number(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c','import av,sys;v=av.open(sys.argv[1]);print(v.duration/av.time_base)',path.join(directory,'continuous.mp4')],{encoding:'utf8',windowsHide:true}).trim())
  for(const row of timeline)row.capture_at=row.at+actual-recording.elapsed_seconds
  await writeFile(path.join(directory,'timeline.json'),JSON.stringify(timeline,null,2))
  await writeFile(path.join(directory,'highlight-audit.json'),JSON.stringify(highlights,null,2))
  await writeFile(path.join(root,'.local',`round10-${material}-current.json`),JSON.stringify({directory}))
}
