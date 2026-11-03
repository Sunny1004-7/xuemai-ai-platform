export type Snapshot = {
  values: number[]
  active: number[]
  sorted: number[]
  message: string
  visited?: number[]
  edges?: [number, number][]
}
export function bubbleSteps(input: number[]): Snapshot[] {
  const a = [...input],
    steps: Snapshot[] = [
      { values: [...a], active: [], sorted: [], message: '准备从相邻元素开始比较。' },
    ]
  for (let end = a.length - 1; end > 0; end--) {
    let swapped = false
    for (let i = 0; i < end; i++) {
      steps.push({
        values: [...a],
        active: [i, i + 1],
        sorted: a.map((_, n) => n).filter((n) => n > end),
        message: `比较 ${a[i]} 与 ${a[i + 1]}：${a[i] > a[i + 1] ? '顺序相反，需要交换。' : '顺序正确，保持不变。'}`,
      })
      if (a[i] > a[i + 1]) {
        ;[a[i], a[i + 1]] = [a[i + 1], a[i]]
        swapped = true
        steps.push({
          values: [...a],
          active: [i, i + 1],
          sorted: a.map((_, n) => n).filter((n) => n > end),
          message: `交换完成，较大元素继续向右移动。`,
        })
      }
    }
    if (!swapped) break
  }
  steps.push({
    values: [...a],
    active: [],
    sorted: a.map((_, i) => i),
    message: '排序完成。通过相邻比较与交换，序列已经有序。',
  })
  return steps
}
export function bfsSteps(): Snapshot[] {
  const edges: [number, number][] = [
    [0, 1],
    [0, 2],
    [1, 3],
    [1, 4],
    [2, 4],
    [2, 5],
  ]
  const queue = [0],
    discovered = new Set([0]),
    visited: number[] = []
  const steps: Snapshot[] = [
    {
      values: [0, 1, 2, 3, 4, 5],
      active: [0],
      sorted: [],
      visited: [],
      edges,
      message: '从节点 A 出发，先把它放入队列。',
    },
  ]
  while (queue.length) {
    const node = queue.shift()!
    visited.push(node)
    for (const [a, b] of edges)
      if (a === node && !discovered.has(b)) {
        discovered.add(b)
        queue.push(b)
      }
    steps.push({
      values: [0, 1, 2, 3, 4, 5],
      active: [...queue],
      sorted: [...visited],
      visited: [...visited],
      edges,
      message: `访问 ${String.fromCharCode(65 + node)}；当前队列：${queue.map((n) => String.fromCharCode(65 + n)).join(' → ') || '空'}。`,
    })
  }
  return steps
}
export function bstSteps(input: number[]): Snapshot[] {
  const nodes: number[] = [],
    edges: [number, number][] = [],
    children = new Map<number, { left?: number; right?: number }>()
  const steps: Snapshot[] = [
    {
      values: [],
      active: [],
      sorted: [],
      edges: [],
      message: '二叉搜索树：左子树值较小，右子树值较大。',
    },
  ]
  for (const value of input) {
    if (nodes.includes(value)) continue
    if (nodes.length) {
      let current = nodes[0]
      while (true) {
        const side = value < current ? 'left' : 'right',
          branch = children.get(current) || {}
        if (branch[side] === undefined) {
          branch[side] = value
          children.set(current, branch)
          edges.push([current, value])
          break
        }
        current = branch[side]!
      }
    }
    nodes.push(value)
    steps.push({
      values: [...nodes],
      active: [value],
      sorted: [],
      edges: [...edges],
      message: `插入 ${value}，沿比较路径放到满足大小关系的位置。`,
    })
  }
  steps.push({
    values: [...nodes],
    active: [],
    sorted: [...nodes].sort((a, b) => a - b),
    edges: [...edges],
    message: `中序遍历：${[...nodes].sort((a, b) => a - b).join(' → ')}。结果是升序序列。`,
  })
  return steps
}
