import assert from 'node:assert/strict'
import {readFileSync,writeFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import ts from 'typescript'
const require=createRequire(import.meta.url)
const compiled={exports:{}}
new Function('require','module','exports',ts.transpileModule(readFileSync(new URL('../src/graph-layout.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText)(require,compiled,compiled.exports)
const {layoutKnowledge}=compiled.exports
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
   assert.ok(Math.abs(Math.hypot(e.points[0].x-result.positions[e.source].x,e.points[0].y-result.positions[e.source].y)-56)<1)
   for(let k=1;k<e.points.length;k++) for(const n of nodes.filter(n=>n.id!==e.source&&n.id!==e.target)) {
     const a=e.points[k-1],b=e.points[k],p=result.positions[n.id]
     const t=Math.max(0,Math.min(1,((p.x-a.x)*(b.x-a.x)+(p.y-a.y)*(b.y-a.y))/((b.x-a.x)**2+(b.y-a.y)**2||1)))
     if(Math.hypot(p.x-a.x-t*(b.x-a.x),p.y-a.y-t*(b.y-a.y))<54)obstruction++
   }
 }
 assert.equal(collision,0,'节点必须无碰撞');assert.equal(obstruction,0,'连线不能穿过无关节点')
 assert.equal(Object.keys(result.positions).length,count)
 const cameras=[]
 for (const viewport of [{width:1620,height:760},{width:1140,height:660},{width:1060,height:660},{width:300,height:520}]) {
   const camera=fitCamera(result,viewport)
   for(const p of pos) {
     const x=p.x*camera.zoom+camera.pan.x,y=p.y*camera.zoom+camera.pan.y,r=62*camera.zoom
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
