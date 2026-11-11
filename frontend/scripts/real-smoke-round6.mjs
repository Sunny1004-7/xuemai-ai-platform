// 显式执行第六轮真实端到端抽样。后端须启用本轮持久预算账本。
import { chromium, expect } from '@playwright/test'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const base=process.env.XUEMAI_REAL_UI || 'http://127.0.0.1:5180'
const directory=path.join(root,'.local/round6-real-ui')
await mkdir(directory,{recursive:true})
const checkpoint=path.join(directory,'results.json')
let results=[]
try { results=JSON.parse(await readFile(checkpoint,'utf8')) } catch {}
const browser=await chromium.launch({channel:process.platform==='win32'?'chrome':undefined,headless:true})
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1})
let currentRole=''
async function login(role) {
  if(currentRole===role)return
  await page.goto(base)
  await page.evaluate(()=>sessionStorage.removeItem('xuemai.session.v1'))
  await page.reload()
  await page.getByLabel('账号',{exact:true}).fill(role==='teacher'?'teacher':'student1')
  await page.getByLabel('密码',{exact:true}).fill('Xuemai123!')
  await page.getByRole('button',{name:'进入学脉',exact:true}).click()
  await expect(page.locator('.app-shell')).toBeVisible()
  const health=await page.request.get(base+'/api/health').then(response=>response.json())
  if(health.ai_mode!=='real')throw new Error('真实联调入口未使用real模式')
  currentRole=role
}
async function saveResult(result) {
  results.push(result)
  await writeFile(checkpoint,JSON.stringify(results,null,2))
  console.log(JSON.stringify({id:result.id,status:result.status,model:result.model,usage:result.usage,duration_ms:result.duration_ms,error:result.error}))
}
async function chatCase(id,role,model,message,{course=1,attachment,voice,image}={}) {
  if(results.some(result=>result.id===id))return
  await login(role)
  if(image) {
    await page.goto(base+'/experiments?course=1&mode=stack')
    await expect(page.locator('.structure-item')).toHaveCount(3)
    await page.screenshot({path:path.join(directory,'stack-input.png')})
  }
  await page.goto(`${base}/${role==='teacher'?'teacher-ai':'tutor'}?course=${course}`)
  await page.getByLabel('选择AI模型').selectOption(model)
  if(attachment) {
    await page.getByLabel('选择问答附件').setInputFiles({name:'队列补充笔记.md',mimeType:'text/markdown',buffer:Buffer.from('队列保持先进先出。广度优先搜索先将起点入队，每次取出队首并把尚未发现的邻居加入队尾。节点在入队时标记，避免重复加入。')})
    await expect(page.locator('.composer-attachments')).toContainText('队列补充笔记.md')
  }
  if(image) {
    await page.getByLabel('选择问答附件').setInputFiles(path.join(directory,'stack-input.png'))
    await expect(page.locator('.composer-attachments')).toContainText('stack-input.png')
  }
  if(voice) {
    await page.getByLabel('选择语音文件').setInputFiles(path.join(root,'.local/round6-voice-sample.mp3'))
    await expect(page.locator('#chat-input')).toHaveValue(/队列/,{timeout:60000})
    await page.screenshot({path:path.join(directory,id+'-transcribed.png')})
    message=await page.locator('#chat-input').inputValue()
    message+='请简短回答。'
  }
  await page.locator('#chat-input').fill(message)
  const responsePromise=page.waitForResponse(response=>response.url().endsWith('/api/ai/chat')&&response.request().method()==='POST',{timeout:90000})
  const started=Date.now()
  await page.getByRole('button',{name:'发送',exact:true}).click()
  const response=await responsePromise
  const body=await response.text()
  const events=body.split('\n').filter(line=>line.startsWith('data: ')).map(line=>JSON.parse(line.slice(6)))
  const meta=events.find(event=>event.conversation_id&&event.mode)
  const done=events.find(event=>event.status==='complete')
  const error=events.find(event=>event.code)
  const result={id,role,model,mode:meta?.mode,status:done?'passed':'failed',duration_ms:Date.now()-started,usage:done?.usage,conversation_id:meta?.conversation_id,
    citations:meta?.citations?.map(source=>({title:source.title,locator:source.locator,source_kind:source.source_kind,version:source.version})),
    method:done?.teaching?.method || done?.teaching?.collaboration?.method,flow_status:done?.teaching?.status || done?.teaching?.collaboration?.status,
    artifact_status:done?.artifact?.status,artifact_id:done?.artifact?.id,
    answer_excerpt:done?.content?.slice(0,350),error:error?.message || (!response.ok?body.slice(0,200):undefined)}
  await page.screenshot({path:path.join(directory,id+'.png')})
  if(done?.teaching?.check) {
    const check=page.getByRole('region',{name:'理解检查'})
    const options=check.locator('input[type=radio],input[type=checkbox]')
    if(await options.count()) {
      await options.first().check()
      const checked=page.waitForResponse(response=>/\/api\/ai\/checks\/\d+\/answer/.test(response.url()))
      await check.getByRole('button',{name:'提交理解检查',exact:true}).click()
      const feedback=await (await checked).json()
      result.understanding_feedback={correct:feedback.correct,attempt_id:feedback.id,transition:feedback.collaboration?.transition}
      await page.screenshot({path:path.join(directory,id+'-check.png')})
    }
  }
  await saveResult(result)
  if(!done)throw new Error(`场景${id}未完成，已停止后续真实请求`)
  if(done.artifact?.status==='invalid')throw new Error(`场景${id}草稿校验失败，先修复本地结构`)
}
async function generateCase(id,kind) {
  if(results.some(result=>result.id===id))return
  await login('teacher')
  if(kind==='question')await page.goto(base+'/practice?course=1')
  if(kind==='lesson') {
    await page.goto(base+'/resources?course=1')
    await page.getByRole('button',{name:'AI 备课',exact:true}).click()
    await page.getByRole('dialog').locator('select[name=knowledge_id]').selectOption({label:'栈与队列'})
    await page.getByLabel('教学意图',{exact:true}).fill('准备一节20分钟栈与队列对照课，字段简洁，三个教学步骤。')
  }
  if(kind==='rubric') {
    await page.goto(base+'/analytics?course=1')
    await page.getByRole('tab',{name:/作答复核/}).click()
    await page.getByRole('button',{name:'查看并复核',exact:true}).first().click()
  }
  const pending=page.waitForResponse(response=>response.url().endsWith('/api/ai/generate')&&response.request().method()==='POST',{timeout:90000})
  const started=Date.now()
  await page.getByRole('button',{name:kind==='question'?'AI 出题':kind==='lesson'?'生成可编辑草稿':'获取 AI 量规建议',exact:true}).click()
  const response=await pending, body=await response.json()
  await page.waitForTimeout(250)
  await page.screenshot({path:path.join(directory,id+'.png')})
  await saveResult({id,role:'teacher',model:body.model,mode:body.mode,status:response.ok?'passed':'failed',kind,duration_ms:Date.now()-started,usage:body.usage,result:body.result,review_status:body.review_status,error:body.detail})
  if(!response.ok)throw new Error(`场景${id}失败，已停止后续请求`)
}
try {
  await chatCase('01-student-flash','student','deepseek-flash','我不明白队列操作为什么错了，请用80字解释并给一个实验和理解检查。')
  await chatCase('02-student-pro','student','deepseek-v4-pro','用一个简短Python例子解释列表别名与切片的差别，控制在100字以内。',{course:2})
  await chatCase('03-document','student','deepseek-flash','根据补充笔记解释BFS为什么在入队时标记，引用相关段落，正文80字以内。',{attachment:true})
  await chatCase('04-image','student','deepseek-flash','图片中栈顶的数值是多少？入栈48后首先出栈哪个值？简短回答。',{image:true})
  await chatCase('05-voice','student','deepseek-flash','',{voice:true})
  await chatCase('06-teacher-discussion','teacher','deepseek-flash','用80字给出队列与栈讲解的课堂提问建议。')
  await chatCase('07-teacher-intervention','teacher','deepseek-v4-pro','这个班在队列和栈的应用题上分别有哪些典型错误？安排40分钟讲评课和两组后续练习。说明正文100字，草稿每环节活动一句话。')
  await generateCase('08-question','question')
  await generateCase('09-lesson','lesson')
  await generateCase('10-rubric','rubric')
  await chatCase('11-teacher-light-recheck','teacher','deepseek-flash','比较栈和队列的课堂提问建议，80字以内。')
  await chatCase('12-scoped-evidence-recheck','teacher','deepseek-v4-pro','这个班在队列和栈的应用题上分别有哪些典型错误？安排40分钟讲评课和两组后续练习。说明正文80字，每环节一句话。')
  await chatCase('13-teacher-question-workflow','teacher','deepseek-flash','围绕Python列表设计题目，生成一道基础单选题供审核。解释正文一句话。',{course:2})
} finally {
  await browser.close()
}
