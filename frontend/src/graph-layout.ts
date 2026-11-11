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
  return obstacleRoute(source, target, obstacles) || best
}

/** 曲线无法绕开密集节点时，用连续方向的网格搜索寻找空白通道。 */
function obstacleRoute(source: Position, target: Position, obstacles: Position[]): Position[] | undefined {
  const blocked = obstacles.filter(point => point !== source && point !== target)
  const step = 26
  const left = Math.min(source.x, target.x, ...blocked.map(point => point.x)) - 90
  const top = Math.min(source.y, target.y, ...blocked.map(point => point.y)) - 90
  const columns = Math.ceil((Math.max(source.x, target.x, ...blocked.map(point => point.x)) - left + 90) / step)
  const rows = Math.ceil((Math.max(source.y, target.y, ...blocked.map(point => point.y)) - top + 90) / step)
  const point = (id: number) => ({ x: left + id % columns * step, y: top + Math.floor(id / columns) * step })
  const cell = (p: Position) => Math.round((p.y - top) / step) * columns + Math.round((p.x - left) / step)
  const clear = (a: Position, b: Position) => blocked.every(obstacle => {
    const dx = b.x - a.x, dy = b.y - a.y
    const t = Math.max(0, Math.min(1, ((obstacle.x - a.x) * dx + (obstacle.y - a.y) * dy) / Math.max(1, dx * dx + dy * dy)))
    return Math.hypot(obstacle.x - a.x - t * dx, obstacle.y - a.y - t * dy) >= 56
  })
  const start = cell(source), end = cell(target)
  const open = new Set([start]), parents = new Map<number, number>(), costs = new Map([[start, 0]])
  const heuristic = (id: number) => Math.hypot(point(id).x - target.x, point(id).y - target.y)
  while (open.size) {
    let current = start, lowest = Infinity
    for (const id of open) {
      const score = costs.get(id)! + heuristic(id)
      if (score < lowest) { current = id; lowest = score }
    }
    if (current === end) {
      const route = [target]
      while (current !== start) { route.unshift(point(current)); current = parents.get(current)! }
      route.unshift(source)
      const reduced = [source]
      let index = 0
      while (index < route.length - 1) {
        let next = route.length - 1
        while (next > index + 1 && !clear(route[index], route[next])) next--
        reduced.push(route[next]); index = next
      }
      const first = reduced[1], last = reduced[reduced.length - 2]
      const offset = (a: Position, b: Position, radius: number) => {
        const distance = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y))
        return { x: a.x + (b.x - a.x) * radius / distance, y: a.y + (b.y - a.y) * radius / distance }
      }
      reduced[0] = offset(source, first, 45)
      reduced[reduced.length - 1] = offset(target, last, 51)
      // 三点仍使用原有二次曲线格式，插入中点明确区分折线路由。
      if (reduced.length === 3) reduced.splice(1, 0, { x: (reduced[0].x + reduced[1].x) / 2, y: (reduced[0].y + reduced[1].y) / 2 })
      return reduced
    }
    open.delete(current)
    const from = point(current)
    for (const [dx, dy] of [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]]) {
      const x = current % columns + dx, y = Math.floor(current / columns) + dy
      if (x < 0 || x >= columns || y < 0 || y >= rows) continue
      const next = y * columns + x, to = point(next)
      if (!clear(from, to)) continue
      const cost = costs.get(current)! + Math.hypot(dx, dy) * step
      if (cost >= (costs.get(next) ?? Infinity)) continue
      parents.set(next, current); costs.set(next, cost); open.add(next)
    }
  }
}

export function routePath(points: Position[]) {
  if (points.length === 3) return `M${points[0].x},${points[0].y} Q${points[1].x},${points[1].y} ${points[2].x},${points[2].y}`
  if (!points.length) return ''
  let path = `M${points[0].x},${points[0].y}`
  for (let index = 1; index < points.length - 1; index++) {
    const before = points[index - 1], corner = points[index], after = points[index + 1]
    const radius = Math.min(9, Math.hypot(corner.x - before.x, corner.y - before.y) / 3, Math.hypot(after.x - corner.x, after.y - corner.y) / 3)
    const toward = (p: Position) => {
      const distance = Math.max(1, Math.hypot(p.x - corner.x, p.y - corner.y))
      return { x: corner.x + (p.x - corner.x) * radius / distance, y: corner.y + (p.y - corner.y) * radius / distance }
    }
    const a = toward(before), b = toward(after)
    path += ` L${a.x},${a.y} Q${corner.x},${corner.y} ${b.x},${b.y}`
  }
  return path + ` L${points.at(-1)!.x},${points.at(-1)!.y}`
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
