import assert from 'node:assert/strict'
import {readFileSync,writeFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import ts from 'typescript'
const require=createRequire(import.meta.url)
const compiled={exports:{}}
new Function('require','module','exports',ts.transpileModule(readFileSync(new URL('../src/graph-layout.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText)(require,compiled,compiled.exports)
const {layoutKnowledge}=compiled.exports
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
 report.push({nodes:count,edges:edges.length,collisions:collision,obstructions:obstruction,elapsed_ms:Math.round(performance.now()-start)})
}
console.log(JSON.stringify(report,null,2))
if(process.argv[2])writeFileSync(process.argv[2],JSON.stringify(report,null,2))
