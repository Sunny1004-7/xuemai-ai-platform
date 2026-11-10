// 补录实际实验步骤及修正排版后的公开证据页，保留原始录制帧和补录说明。
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
import {execFileSync} from 'node:child_process'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const directory=process.argv[2]
if(!directory)throw new Error('需要原始录制目录')
const data=JSON.parse(await fs.readFile(path.join(directory,'recording.json'),'utf8'))
if(data.quick)throw new Error('不能使用快速预演帧')
const b=await chromium.launch({channel:'chrome',headless:true});const p=await b.newPage({viewport:{width:1920,height:1080}})
const inserts=[]
try{
 await p.goto('http://127.0.0.1:5175');await p.getByRole('button',{name:'体验学生端',exact:true}).click();await p.getByRole('button',{name:'进入学脉',exact:true}).click();await p.getByRole('navigation',{name:'主导航'}).waitFor()
 await p.goto('http://127.0.0.1:5175/experiments');await p.locator('.sort-bar').first().waitFor()
 for(let i=0;i<6;i++){
  if(i)await p.getByRole('button',{name:'下一步',exact:true}).click()
  await p.waitForTimeout(300)
  const file=`refresh-experiment-${i}.png`;await p.screenshot({path:path.join(directory,file)})
  inserts.push({file,at:185+i*3.3})
 }
 for(const [at,id] of [[280,'chain1'],[315,'chain2'],[350,'chain3'],[385,'round2']]){
  await p.goto(pathToFileURL(path.join(root,'docs/development-process/round2-replay.html')).href+'#'+id)
  const file=`refresh-${id}.png`;await p.screenshot({path:path.join(directory,file)})
  inserts.push({file,at})
 }
}finally{await b.close()}
const shots=[...data.shots.filter(s=>!(s.at>=185&&s.at<205)&&!(s.at>=280&&s.at<410)),...inserts].sort((a,b)=>a.at-b.at)
const lines=['ffconcat version 1.0']
for(let i=0;i<shots.length;i++){lines.push(`file '${shots[i].file}'`);lines.push(`duration ${Math.max(.01,(shots[i+1]?.at||420)-shots[i].at).toFixed(3)}`)}
lines.push(`file '${shots.at(-1).file}'`)
await fs.writeFile(path.join(directory,'refreshed.ffconcat'),lines.join('\n'))
await fs.writeFile(path.join(directory,'补录说明.json'),JSON.stringify({reason:'实验图表数值对比度调整、开发回放画面分页修正',original_recording:'recording.json',refreshed_windows:[[185,205],[280,410]],inserts},null,2))
const ffmpeg=execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c','import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}).trim()
execFileSync(ffmpeg,['-y','-loglevel','error','-f','concat','-safe','0','-i',path.join(directory,'refreshed.ffconcat'),'-r','24','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',path.join(root,'最终参赛提交材料/学脉XueMai-演示视频.mp4')],{stdio:'inherit'})
console.log(JSON.stringify({output:'演示视频.mp4',duration:420,refreshed_frames:inserts.length}))
