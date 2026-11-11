import { layoutKnowledge } from './graph-layout'

self.onmessage = async ({ data }) => {
  const layout = await layoutKnowledge(data.nodes, data.edges, data.aspect, data.previous)
  self.postMessage(layout)
}
