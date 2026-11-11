export type Viewport = { width: number; height: number }
export type Camera = { zoom: number; pan: { x: number; y: number } }
export const canvasInsets = { left: 28, right: 28, top: 66, bottom: 78 }

/** 全图适配不设置最小缩放；小窗口使用章节/局部视图获得阅读字号。 */
export function fitCamera(bounds: Viewport, viewport: Viewport): Camera {
  const { left, right, top, bottom } = canvasInsets
  const width = Math.max(1, viewport.width - left - right)
  const height = Math.max(1, viewport.height - top - bottom)
  const zoom = Math.min(1.15, width / Math.max(1, bounds.width), height / Math.max(1, bounds.height))
  return { zoom, pan: { x: left + (width - bounds.width * zoom) / 2, y: top + (height - bounds.height * zoom) / 2 } }
}

export function focusCamera(point: { x: number; y: number }, viewport: Viewport): Camera {
  const zoom = 1.15
  return { zoom, pan: { x: viewport.width / 2 - point.x * zoom, y: viewport.height / 2 - point.y * zoom } }
}

/** 缩放前后的世界坐标保持落在同一鼠标位置。 */
export function zoomCamera(camera: Camera, zoom: number, anchor: { x: number; y: number }): Camera {
  return { zoom, pan: {
    x: anchor.x - (anchor.x - camera.pan.x) * zoom / camera.zoom,
    y: anchor.y - (anchor.y - camera.pan.y) * zoom / camera.zoom,
  } }
}
