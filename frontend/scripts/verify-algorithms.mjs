import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

// 只转译本地算法模块，不导入 UI、HTTP 客户端或任何 AI 服务。
const source = readFileSync(new URL('../src/algorithms.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
})
const compiled = { exports: {} }
new Function('module', 'exports', outputText)(compiled, compiled.exports)
const { bubbleSteps, bfsSteps, bstSteps } = compiled.exports
let cases = 0
for (let n = 2; n <= 12; n++) {
  for (let k = 0; k < 10; k++) {
    const input = Array.from({ length: n }, (_, i) => ((i * 17 + k * 31) % 99) + 1)
    const frozen = [...input]
    const steps = bubbleSteps(input)
    assert.deepEqual(
      steps.at(-1).values,
      [...input].sort((a, b) => a - b),
      '终态必须与独立排序结果一致',
    )
    assert.deepEqual(input, frozen, '不可修改调用者输入')
    for (const s of steps) {
      assert.equal(s.values.length, n)
      assert.deepEqual(
        [...s.values].sort((a, b) => a - b),
        [...input].sort((a, b) => a - b),
        '每个状态保留原有元素',
      )
      assert.ok(
        s.active.every((i) => i >= 0 && i < n),
        '高亮索引必须在范围内',
      )
    }
    cases++
  }
}
for (const input of [[], [1], [2, 2, 1], [9, 8, 7, 6, 5, 4]]) {
  assert.deepEqual(
    bubbleSteps(input).at(-1).values,
    [...input].sort((a, b) => a - b),
  )
}
const bfs = bfsSteps()
assert.deepEqual(bfs.at(-1).visited, [0, 1, 2, 3, 4, 5], 'BFS 必须按层且不重复访问')
assert.equal(new Set(bfs.at(-1).visited).size, 6)
const bst = bstSteps([36, 18, 52, 24, 9, 43, 18])
assert.deepEqual(bst.at(-1).sorted, [9, 18, 24, 36, 43, 52], 'BST 去重且中序遍历应升序')
assert.equal(bst.at(-1).edges.length, 5)
console.log(
  `算法验证通过：${cases} 组排序输入及 4 个边界样本、每步元素/索引不变量、BFS 层序与 BST 去重中序。真实 AI 请求 0 次。`,
)
