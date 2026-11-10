import ELK from 'elkjs/lib/elk.bundled.js'
import type { ElkNode } from 'elkjs/lib/elk-api'
export type GraphNode = { id: number; chapter_id?: number | null; title: string }
export type GraphEdge = { source: number; target: number }
export type Position = { x: number; y: number }
export type GraphLayout = { positions: Record<number, Position>; routes: {source: number; target: number; points: Position[]}[]; width: number; height: number }
const engine = new ELK()

// ELK分层交叉最小化与正交路由；固定端口对齐圆形左右边缘。
export async function layoutKnowledge(nodes: GraphNode[], edges: GraphEdge[]): Promise<GraphLayout> {
  const ids = new Set(nodes.map(n => n.id))
  const links = edges.filter(e => ids.has(e.source) && ids.has(e.target))
  const result = await engine.layout<ElkNode>({
    id: 'root', layoutOptions: {
      'elk.algorithm': 'layered', 'elk.direction': 'RIGHT', 'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '50', 'elk.layered.spacing.nodeNodeBetweenLayers': '90',
      'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF', 'elk.padding': '[top=45,left=45,bottom=45,right=45]',
    },
    children: nodes.map(n => ({ id: String(n.id), width: 112, height: 112,
      layoutOptions: {'elk.portConstraints': 'FIXED_POS'}, ports: [
        {id: `${n.id}-in`, x: 0, y: 56, width: 0, height: 0},
        {id: `${n.id}-out`, x: 112, y: 56, width: 0, height: 0},
      ] })),
    edges: links.map((e,i) => ({id: String(i), sources: [`${e.source}-out`], targets: [`${e.target}-in`]})),
  })
  const positions: Record<number,Position> = {}
  result.children?.forEach(n => { positions[Number(n.id)] = {x: (n.x || 0)+56, y: (n.y || 0)+56} })
  return { positions, width: result.width || 400, height: result.height || 300,
    routes: (result.edges || []).map(e => ({...links[Number(e.id)], points: (e.sections || []).flatMap(s => [s.startPoint, ...(s.bendPoints || []), s.endPoint])})) }
}

export function routePath(points: Position[]) {
  return points.map((p,i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')
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
