import ELK from 'elkjs/lib/elk.bundled.js'
import type { ElkNode } from 'elkjs/lib/elk-api'
export type GraphNode = { id: number; chapter_id?: number | null; chapter_title?: string; title: string }
export type GraphEdge = { source: number; target: number }
export type Position = { x: number; y: number }
export type GraphLayout = { positions: Record<number, Position>; routes: {source: number; target: number; points: Position[]}[]; width: number; height: number; clusters?: {id: number; title: string; x: number; y: number; width: number; height: number}[] }
const engine = new ELK()

// ELK计算避障走廊，渲染时将转角圆滑化，保持先修方向与节点间距。
export async function layoutKnowledge(nodes: GraphNode[], edges: GraphEdge[]): Promise<GraphLayout> {
  const ids = new Set(nodes.map(n => n.id))
  const links = edges.filter(e => ids.has(e.source) && ids.has(e.target))
  const chapters = [...new Set(nodes.map(n => n.chapter_id || 0))]
  const clustered = nodes.length >= 16 && chapters.length > 1
  const chapterOverview = nodes.every(n => n.id <= 0)
  const leaf = (n: GraphNode) => ({ id: String(n.id), width: 112, height: 112,
    layoutOptions: {'elk.portConstraints': 'FIXED_POS'}, ports: chapterOverview ? [
      {id: `${n.id}-in`, x: 56, y: 0, width: 0, height: 0},
      {id: `${n.id}-out`, x: 56, y: 112, width: 0, height: 0},
    ] : [
      {id: `${n.id}-in`, x: 0, y: 56, width: 0, height: 0},
      {id: `${n.id}-out`, x: 112, y: 56, width: 0, height: 0},
    ] })
  const result = await engine.layout<ElkNode>({
    id: 'root', layoutOptions: {
      'elk.algorithm': 'layered', 'elk.direction': clustered || chapterOverview ? 'DOWN' : 'RIGHT', 'elk.edgeRouting': 'ORTHOGONAL',
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.spacing.nodeNode': '44', 'elk.layered.spacing.nodeNodeBetweenLayers': '76',
      'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF', 'elk.padding': '[top=45,left=45,bottom=45,right=45]',
    },
    children: clustered ? chapters.map(id => ({id: `chapter-${id}`, layoutOptions: {
      'elk.padding': '[top=46,left=24,bottom=24,right=24]',
      'elk.spacing.nodeNode': '28', 'elk.layered.spacing.nodeNodeBetweenLayers': '45',
    }, children: nodes.filter(n => (n.chapter_id || 0) === id).map(leaf)})) : nodes.map(leaf),
    edges: links.map((e,i) => ({id: String(i), sources: [`${e.source}-out`], targets: [`${e.target}-in`]})),
  })
  const positions: Record<number,Position> = {}
  const offsets: Record<string,Position> = {root: {x:0,y:0}}
  const clusters: NonNullable<GraphLayout['clusters']> = []
  function collect(parent: ElkNode, offset: Position) {
    parent.children?.forEach(n => {
      const point = {x: offset.x + (n.x || 0), y: offset.y + (n.y || 0)}
      offsets[n.id] = point
      if (n.children) {
        const id = Number(n.id.replace('chapter-',''))
        clusters.push({id, title: nodes.find(node => (node.chapter_id || 0) === id)?.chapter_title || `章节 ${id}`, ...point, width: n.width || 0, height: n.height || 0})
        collect(n,point)
      } else positions[Number(n.id)] = {x:point.x+56,y:point.y+56}
    })
  }
  collect(result,{x:0,y:0})
  return { positions, width: result.width || 400, height: result.height || 300,
    clusters,
    routes: (result.edges || []).map(e => {
      const offset = offsets[e.container || 'root'] || {x:0,y:0}
      return {...links[Number(e.id)], points: (e.sections || []).flatMap(s => [s.startPoint, ...(s.bendPoints || []), s.endPoint]).map(p => ({x:p.x+offset.x,y:p.y+offset.y}))}
    }) }
}

export function routePath(points: Position[]) {
  if (!points.length) return ''
  let path = `M${points[0].x},${points[0].y}`
  for (let i = 1; i < points.length - 1; i++) {
    const a = points[i - 1], b = points[i], c = points[i + 1]
    const before = Math.hypot(b.x - a.x, b.y - a.y), after = Math.hypot(c.x - b.x, c.y - b.y)
    if (!before || !after) continue
    const radius = Math.min(16, before / 2, after / 2)
    const start = { x: b.x + (a.x - b.x) * radius / before, y: b.y + (a.y - b.y) * radius / before }
    const end = { x: b.x + (c.x - b.x) * radius / after, y: b.y + (c.y - b.y) * radius / after }
    path += ` L${start.x},${start.y} Q${b.x},${b.y} ${end.x},${end.y}`
  }
  const last = points[points.length - 1]
  return path + ` L${last.x},${last.y}`
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
