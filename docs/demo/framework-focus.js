// 坐标来自TikZ实际节点锚点，单位为PDF点，左上角为原点。
export function calculateFocus(regions, name, viewport, padding = 8) {
  const group = regions.groups[name]
  if (!group) throw new Error('未定义的图形分组 ' + name)
  const scale = Math.min(viewport.width / regions.width, viewport.height / regions.height)
  const offsetX = (viewport.width - regions.width * scale) / 2
  const offsetY = (viewport.height - regions.height * scale) / 2
  const box = { left: offsetX + group.x * scale - padding, top: offsetY + group.y * scale - padding,
    width: group.width * scale + padding * 2, height: group.height * scale + padding * 2 }
  const targets = group.members.map(name => {
    const node = regions.nodes[name]
    return { name, left: offsetX + node.x * scale, top: offsetY + node.y * scale,
      width: node.width * scale, height: node.height * scale }
  })
  for (const target of targets) {
    const margins = [target.left-box.left, target.top-box.top,
      box.left+box.width-target.left-target.width, box.top+box.height-target.top-target.height]
    if (Math.min(...margins) < padding - .01) throw new Error('高亮边界未完整包含 ' + target.name)
  }
  return { box, targets, scale, offsetX, offsetY, padding }
}
