import {chromium,expect} from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'
const output=path.resolve('../.local/round5-state-audit');await fs.mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true});const states=[]
for(const role of ['student','teacher']){
 const page=await browser.newPage({viewport:{width:1440,height:900}})
 await page.goto('http://127.0.0.1:5178');await page.getByLabel('账号',{exact:true}).fill(role==='student'?'student1':'teacher');await page.getByLabel('密码',{exact:true}).fill('Xuemai123!');await page.getByRole('button',{name:'进入学脉',exact:true}).click();await expect(page.locator('.app-shell')).toBeVisible()
 for(const course of [1,2])for(const viewport of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:1366,height:650}]){
  await page.setViewportSize(viewport)
  for(const route of role==='student'?['/','/plan','/practice','/review','/experiments']:['/manage','/practice','/analytics']){
   await page.goto(`http://127.0.0.1:5178${route}?course=${course}`);await expect(page.locator('main h1')).toBeVisible();await expect(page.locator('main .loading')).toHaveCount(0)
   const names=['default',...await page.locator('main [role=tab]:visible').allTextContents()]
   for(const [index,name]of names.entries()){
    if(index){const tab=page.getByRole('tab',{name,exact:true}).first();if(!await tab.isVisible())continue;await tab.click()}
    await page.waitForTimeout(120)
    const layout=await page.evaluate(()=>({height:document.documentElement.scrollHeight,width:document.documentElement.scrollWidth,viewportHeight:innerHeight,viewportWidth:innerWidth}))
    const state={role,course,route,view:name,...layout,passed:layout.height<=viewport.height+2&&layout.width<=viewport.width+2};states.push(state)
    if(!state.passed){const file=`${role}-${course}-${viewport.height}-${route.replaceAll('/','')||'home'}-${index}.png`;await page.screenshot({path:path.join(output,file)});console.log(JSON.stringify(state))}
   }
  }
 }
 await page.close()
}
await browser.close();await fs.writeFile(path.join(output,'results.json'),JSON.stringify({states,passed:states.every(s=>s.passed)},null,2));console.log(`检查 ${states.length} 个工作状态，${states.filter(s=>!s.passed).length} 个需要修正`)
