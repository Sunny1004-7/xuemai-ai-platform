import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'
import type { SimulationNodeDatum } from 'd3-force'

export type GraphNode = { id: number; chapter_id?: number | null; chapter_title?: string; title: string }
export type GraphEdge = { source: number; target: number }
export type Position = { x: number; y: number }
export type GraphLayout = {
  positions: Record<number, Position>
  routes: { source: number; target: number; points: Position[] }[]
  width: number
  height: number
  clusters?: { id: number; title: string; x: number; y: number; width: number; height: number }[]
}
type ForceNode = SimulationNodeDatum & GraphNode & { anchorX: number; anchorY: number }

/** 章节软吸引与确定性初始位置，碰撞半径包含标签与操作热点。 */
export async function layoutKnowledge(nodes: GraphNode[], edges: GraphEdge[], aspect = 1.85, previous: Record<number, Position> = {}): Promise<GraphLayout> {
  if (!nodes.length) return { positions: {}, routes: [], width: 1, height: 1 }
  const sorted = [...nodes].sort((a, b) => a.id - b.id)
  const ids = new Set(sorted.map(node => node.id))
  const links = edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)).map(edge => ({ ...edge }))
  const chapters = [...new Set(sorted.map(node => node.chapter_id || 0))]
  const area = Math.max(90000, nodes.length * 17500)
  const width = Math.sqrt(area * Math.max(.7, Math.min(2.5, aspect)))
  const height = area / width
  const columns = Math.max(1, Math.ceil(Math.sqrt(chapters.length * aspect)))
  const rows = Math.ceil(chapters.length / columns)
  const points: ForceNode[] = sorted.map((node, index) => {
    const group = chapters.indexOf(node.chapter_id || 0)
    const anchorX = width * (.1 + .8 * ((group % columns + .5) / columns))
    const anchorY = height * (.1 + .8 * ((Math.floor(group / columns) + .5) / rows))
    const angle = index * 2.399963
    return { ...node, anchorX: previous[node.id] ? previous[node.id].x * .75 + anchorX * .25 : anchorX,
      anchorY: previous[node.id] ? previous[node.id].y * .75 + anchorY * .25 : anchorY,
      x: previous[node.id]?.x ?? anchorX + Math.cos(angle) * 60,
      y: previous[node.id]?.y ?? anchorY + Math.sin(angle) * 60 }
  })
  const simulation = forceSimulation(points).stop()
    .force('links', forceLink<ForceNode, any>(links).id(node => node.id).distance(115).strength(.28))
    .force('charge', forceManyBody().strength(-310))
    .force('collision', forceCollide<ForceNode>(57).iterations(4))
    .force('x', forceX<ForceNode>(node => node.anchorX).strength(.1))
    .force('y', forceY<ForceNode>(node => node.anchorY).strength(.14))
  simulation.tick(420)
  simulation.stop()
  const left = Math.min(...points.map(node => node.x!)) - 58
  const top = Math.min(...points.map(node => node.y!)) - 58
  const positions = Object.fromEntries(points.map(node => [node.id, { x: node.x! - left, y: node.y! - top }]))
  return { positions, width: Math.max(...Object.values(positions).map(point => point.x)) + 58,
    height: Math.max(...Object.values(positions).map(point => point.y)) + 58,
    routes: edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)).map(edge => ({ ...edge, points: edgePoints(positions[edge.source], positions[edge.target], Object.values(positions)) })) }
}

/** 起终点沿圆边缘留出箭头间距。 */
export function edgePoints(source: Position, target: Position, obstacles: Position[] = []): Position[] {
  const dx = target.x - source.x, dy = target.y - source.y
  const distance = Math.max(1, Math.hypot(dx, dy))
  let best: Position[] = [], bestCost = Infinity
  for (const offset of [0, 35, -35, 70, -70, 110, -110, 160, -160, 230, -230, 320, -320]) {
    for (const fraction of [.5, .3, .7]) {
    const control = { x: source.x + dx * fraction - dy / distance * offset, y: source.y + dy * fraction + dx / distance * offset }
    const a = Math.max(1, Math.hypot(control.x - source.x, control.y - source.y))
    const b = Math.max(1, Math.hypot(control.x - target.x, control.y - target.y))
    const start = { x: source.x + (control.x - source.x) * 45 / a, y: source.y + (control.y - source.y) * 45 / a }
    const end = { x: target.x + (control.x - target.x) * 51 / b, y: target.y + (control.y - target.y) * 51 / b }
    let cost = Math.abs(offset) / 1000
    for (const obstacle of obstacles) {
      if (obstacle === source || obstacle === target) continue
      for (let index = 1; index < 65; index++) {
        const t = index / 65
        const x = (1 - t) ** 2 * start.x + 2 * t * (1 - t) * control.x + t ** 2 * end.x
        const y = (1 - t) ** 2 * start.y + 2 * t * (1 - t) * control.y + t ** 2 * end.y
        cost += Math.max(0, 51 - Math.hypot(x - obstacle.x, y - obstacle.y))
      }
    }
    if (cost < bestCost) { best = [start, control, end]; bestCost = cost }
    if (cost < 1) return best
    }
  }
  return best
}

export function routePath(points: Position[]) {
  if (points.length === 3) return `M${points[0].x},${points[0].y} Q${points[1].x},${points[1].y} ${points[2].x},${points[2].y}`
  return points.map((point, index) => `${index ? 'L' : 'M'}${point.x},${point.y}`).join(' ')
}

export function relatedKnowledge(id: number, edges: GraphEdge[], ancestors = false) {
  const result = new Set([id]), queue = [id]
  for (let index = 0; index < queue.length; index++) {
    for (const edge of edges) {
      const neighbor = edge.target === queue[index] ? edge.source : !ancestors && edge.source === id ? edge.target : 0
      if (neighbor && !result.has(neighbor)) {
        result.add(neighbor)
        if (ancestors) queue.push(neighbor)
      }
    }
  }
  return result
}
