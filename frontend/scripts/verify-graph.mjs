import assert from 'node:assert/strict'
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import ts from 'typescript'
import {createRequire} from 'node:module'
import {pathToFileURL} from 'node:url'
const forceUrl=pathToFileURL(createRequire(import.meta.url).resolve('d3-force')).href
const source=readFileSync(new URL('../src/graph-layout.ts',import.meta.url),'utf8').replaceAll("from 'd3-force'",`from '${forceUrl}'`)
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const temporary=new URL('../../.local/verify-network-layout.mjs',import.meta.url)
mkdirSync(new URL('../../.local',import.meta.url),{recursive:true})
writeFileSync(temporary,compiled)
const {layoutKnowledge}=await import(temporary.href+'?v='+Date.now())
const cameraModule={exports:{}}
new Function('module','exports',ts.transpileModule(readFileSync(new URL('../src/graph-camera.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText)(cameraModule,cameraModule.exports)
const {fitCamera,zoomCamera,focusCamera,canvasInsets}=cameraModule.exports
const report=[]
for(const count of [6,31,80]) {
 const nodes=Array.from({length:count},(_,i)=>({id:i+1,title:`知识点${i+1}`,chapter_id:Math.floor(i/5)}))
 const edges=nodes.flatMap((n,i)=>[...(i+1<count?[{source:n.id,target:n.id+1}]:[]),...(i+5<count&&i%3===0?[{source:n.id,target:n.id+5}]:[])])
 const start=performance.now(), result=await layoutKnowledge(nodes,edges)
 let collision=0,obstruction=0
 const pos=Object.values(result.positions)
 for(let i=0;i<pos.length;i++)for(let j=i+1;j<pos.length;j++)if(Math.hypot(pos[i].x-pos[j].x,pos[i].y-pos[j].y)<112)collision++
 for(const e of result.routes) {
   assert.ok(e.points.length>=2)
   assert.ok(Math.abs(Math.hypot(e.points[0].x-result.positions[e.source].x,e.points[0].y-result.positions[e.source].y)-45)<1)
   for(const n of nodes.filter(n=>n.id!==e.source&&n.id!==e.target)) {
     let blocked=false
     for(let k=0;k<=100;k++) {
       const t=k/100,[a,c,b]=e.points,p=result.positions[n.id]
       const x=(1-t)**2*a.x+2*t*(1-t)*c.x+t*t*b.x
       const y=(1-t)**2*a.y+2*t*(1-t)*c.y+t*t*b.y
       if(Math.hypot(p.x-x,p.y-y)<43)blocked=true
     }
     if(blocked)obstruction++
   }
 }
 assert.equal(collision,0,'节点必须无碰撞')
 const repeated=await layoutKnowledge([...nodes].reverse(),edges)
 assert.deepEqual(repeated.positions,result.positions,'相同结构与节点顺序变化应保持稳定')
 assert.equal(Object.keys(result.positions).length,count)
 const cameras=[]
 for (const viewport of [{width:1620,height:760},{width:1140,height:660},{width:1060,height:660},{width:300,height:520}]) {
   const camera=fitCamera(result,viewport)
   for(const p of pos) {
     const x=p.x*camera.zoom+camera.pan.x,y=p.y*camera.zoom+camera.pan.y,r=49*camera.zoom
     assert.ok(x-r>=0&&x+r<=viewport.width,'全图节点及选中光圈必须在左右边界内')
     assert.ok(y-r>=canvasInsets.top-2&&y+r<=viewport.height-canvasInsets.bottom+2,'全图必须避开标题和工具条')
   }
   const anchor={x:viewport.width*.7,y:viewport.height*.3}
   const next=zoomCamera(camera,camera.zoom*1.4,anchor)
   for(const axis of ['x','y'])assert.ok(Math.abs((anchor[axis]-camera.pan[axis])/camera.zoom-(anchor[axis]-next.pan[axis])/next.zoom)<1e-7,'鼠标锚点缩放不可漂移')
   const focused=focusCamera(pos[0],viewport)
   assert.equal(focused.zoom,1.15)
   cameras.push({viewport,fit_zoom:camera.zoom,visible_nodes:pos.length,anchor_error_below:1e-7})
 }
 report.push({nodes:count,edges:edges.length,collisions:collision,obstructions:obstruction,elapsed_ms:Math.round(performance.now()-start),cameras})
}
console.log(JSON.stringify(report,null,2))
if(process.argv[2])writeFileSync(process.argv[2],JSON.stringify(report,null,2))
