export type GraphNode = { id: number; chapter_id?: number | null; title: string }
export type GraphEdge = { source: number; target: number }
export type Position = { x: number; y: number }

// DAG最长路径分层，同层按章节和前驱重心排序。节点间距独立于旧坐标。
export function layoutKnowledge(nodes: GraphNode[], edges: GraphEdge[]) {
  const ids = new Set(nodes.map((n) => n.id))
  const parents = new Map(nodes.map((n) => [n.id, [] as number[]]))
  const children = new Map(nodes.map((n) => [n.id, [] as number[]]))
  for (const e of edges) {
    if (ids.has(e.source) && ids.has(e.target)) {
      parents.get(e.target)!.push(e.source)
      children.get(e.source)!.push(e.target)
    }
  }
  const remaining = new Map(nodes.map((n) => [n.id, parents.get(n.id)!.length]))
  const depths = new Map(nodes.map((n) => [n.id, 0]))
  const queue = nodes.filter((n) => remaining.get(n.id) === 0).map((n) => n.id)
  for (let i = 0; i < queue.length; i++) {
    const id = queue[i]
    for (const target of children.get(id)!) {
      depths.set(target, Math.max(depths.get(target)!, depths.get(id)! + 1))
      remaining.set(target, remaining.get(target)! - 1)
      if (!remaining.get(target)) queue.push(target)
    }
  }
  // 用主题簇限制全局纵向展开；每簇内部按DAG顺序排列，新节点自动扩展行数。
  const chapters = [...new Set(nodes.map((n) => n.chapter_id || 0))]
  const columns = Math.min(3, Math.max(1, chapters.length))
  const clusters = chapters.map((chapter) => ({
    chapter_id: chapter,
    nodes: nodes
      .filter((n) => (n.chapter_id || 0) === chapter)
      .sort((a, b) => depths.get(a.id)! - depths.get(b.id)! || a.id - b.id),
  }))
  const groupWidth = 360
  const groupHeights = clusters.map((c) => 68 + Math.ceil(c.nodes.length / 3) * 116)
  const rowHeights = Array.from({ length: Math.ceil(clusters.length / columns) }, (_, row) =>
    Math.max(...groupHeights.slice(row * columns, (row + 1) * columns)),
  )
  const positions: Record<number, Position> = {}
  const groups = clusters.map((cluster, index) => {
    const row = Math.floor(index / columns),
      col = index % columns
    const x = 20 + col * (groupWidth + 20),
      y = 20 + rowHeights.slice(0, row).reduce((sum, h) => sum + h + 22, 0)
    cluster.nodes.forEach((node, i) => {
      positions[node.id] = { x: x + 65 + (i % 3) * 115, y: y + 86 + Math.floor(i / 3) * 116 }
    })
    return { chapter_id: cluster.chapter_id, x, y, width: groupWidth, height: rowHeights[row] }
  })
  return {
    positions,
    groups,
    width: columns * (groupWidth + 20) + 20,
    height: rowHeights.reduce((sum, h) => sum + h + 22, 20),
  }
}

export function relatedKnowledge(id: number, edges: GraphEdge[], ancestors = false) {
  const result = new Set([id])
  const queue = [id]
  for (let index = 0; index < queue.length; index++) {
    for (const edge of edges) {
      const neighbor =
        edge.target === queue[index]
          ? edge.source
          : !ancestors && edge.source === id
            ? edge.target
            : 0
      if (neighbor && !result.has(neighbor)) {
        result.add(neighbor)
        if (ancestors) queue.push(neighbor)
      }
    }
  }
  return result
}
