import {chromium} from '@playwright/test'
import {mkdir,writeFile} from 'node:fs/promises'
import path from 'node:path'
import {fileURLToPath,pathToFileURL} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const output=path.join(root,'docs/demo/第四轮演示画板')
await mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
const page=await browser.newPage({viewport:{width:1920,height:1080}})
const report=[]
try{
  for(const id of ['intro','chain1','chain2','chain3','methods','path-results','group-results','outro']){
    await page.goto(pathToFileURL(path.join(root,'docs/development-process/round4-replay.html')).href+'#'+id)
    await page.evaluate(()=>document.fonts.ready)
    const bounds=await page.locator('#'+id).evaluate(el=>({width:el.scrollWidth,height:el.scrollHeight,bottom:Math.max(...[...el.children].map(c=>c.getBoundingClientRect().bottom))}))
    if(bounds.width>1920||bounds.height>1080||bounds.bottom>950)throw new Error(id+'超出字幕安全区：'+JSON.stringify(bounds))
    await page.screenshot({path:path.join(output,id+'.png')})
    report.push({id,...bounds})
  }
}finally{await browser.close()}
await writeFile(path.join(output,'画板检查.json'),JSON.stringify({resolution:'1920x1080',subtitle_safe_bottom:950,slides:report},null,2))
console.log('已检查并导出8张演示画板')
