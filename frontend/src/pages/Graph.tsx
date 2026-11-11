import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowDown,
  BookOpen,
  Check,
  Maximize2,
  Minimize2,
  ChevronRight,
  Edit3,
  FlaskConical,
  Focus,
  Link2,
  Minus,
  Network,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Video,
  X,
  PanelRightOpen,
  Scan,
} from 'lucide-react'
import { fitCamera, focusCamera, zoomCamera } from '../graph-camera'
import type { Camera } from '../graph-camera'
import { layoutKnowledge, relatedKnowledge, routePath } from '../graph-layout'
import type { GraphLayout } from '../graph-layout'
import { api, patch, percent, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Progress, Title, useApp } from '../ui'

export function Graph() {
  const { user, courseId, notify } = useApp()
  const [params, setParams] = useSearchParams()
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [], edges: [] })
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const course = useApi<Row>(`/courses/${courseId}`, {})
  const [selected, setSelected] = useState(Number(params.get('knowledge')) || 0)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [search, setSearch] = useState('')
  const [edit, setEdit] = useState<Row | null>(null)
  const [edge, setEdge] = useState(false)
  const [from, setFrom] = useState(0)
  const [to, setTo] = useState(0)
  const [filter, setFilter] = useState('all')
  const prefKey = `xuemai-graph-view-${user.id}-${courseId}`
  const [focusMode, setFocusMode] = useState(() =>
    params.get('knowledge')
      ? 'neighbors'
      : ['all', 'chapters'].includes(localStorage.getItem(prefKey) || '')
        ? localStorage.getItem(prefKey)!
        : 'all',
  )
  useEffect(() => {
    if (['all', 'chapters'].includes(focusMode)) localStorage.setItem(prefKey, focusMode)
  }, [focusMode, prefKey])
  const [chapter, setChapter] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(Boolean(params.get('knowledge')))
  const cameraMode = useRef<'fit' | 'manual'>('fit')
  const savedCamera = useRef<Camera | null>(null)
  const restoreCamera = useRef(false)
  const readAfterLayout = useRef(false)
  const previousSize = useRef({ width: 800, height: 620 })
  const cameraRef = useRef<Camera>({ zoom: 1, pan: { x: 0, y: 0 } })
  cameraRef.current = { zoom, pan }
  const [size, setSize] = useState({ width: 800, height: 620 })
  const canvasRef = useRef<HTMLDivElement>(null)
  const [layout, setLayout] = useState<GraphLayout>({
    positions: {},
    routes: [],
    width: 800,
    height: 620,
  })
  const [layoutBusy, setLayoutBusy] = useState(false)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const teacher = user.role === 'teacher'
  const nodes: Row[] = graph.data.nodes || []
  const edges: Row[] = graph.data.edges || []
  const current = nodes.find((n) => n.id === selected) || nodes[0]
  const currentObserved = Number(current?.evidence?.effective_count || 0) > 0
  const focusId = ['neighbors', 'ancestors'].includes(focusMode) ? current?.id : 0
  const shown = useMemo<{ nodes: Row[]; edges: Row[] }>(() => {
    if (focusMode === 'chapters') {
      const chapters: Row[] = [
        ...(course.data.chapters || []),
        ...(nodes.some((n) => !n.chapter_id) ? [{ id: 0, title: '未分章节' }] : []),
      ]
      const chapterNodes = chapters.map((c) => ({
        ...c,
        id: -c.id,
        count: nodes.filter((n) => (n.chapter_id || 0) === c.id).length,
      }))
      const pairs = edges
        .map((e) => [
          nodes.find((n) => n.id === e.source)?.chapter_id,
          nodes.find((n) => n.id === e.target)?.chapter_id,
        ])
        .filter(([a, b]) => a && b && a !== b)
      const unique = [...new Set(pairs.map(([a, b]) => `${a}:${b}`))]
      return {
        nodes: chapterNodes,
        edges: unique.map((pair) => {
          const [a, b] = pair.split(':').map(Number)
          return { source: -a, target: -b }
        }),
      }
    }
    let ids: Set<number> | null = null
    if (focusMode === 'chapter') {
      ids = new Set(nodes.filter((n) => (n.chapter_id || 0) === chapter).map((n) => n.id))
      // 外部直接先修作为边界上下文，避免带入全图。
      edges.forEach((e) => {
        if (nodes.some((n) => n.id === e.target && n.chapter_id === chapter)) ids!.add(e.source)
      })
    } else if (focusMode !== 'all')
      ids = relatedKnowledge(current?.id || 0, edges as any, focusMode === 'ancestors')
    return {
      nodes: nodes.filter((n) => !ids || ids.has(n.id)),
      edges: edges.filter((e) => !ids || (ids.has(e.source) && ids.has(e.target))),
    }
  }, [nodes, edges, course.data.chapters, focusMode, chapter, focusId])
  function applyCamera(camera: Camera) {
    setZoom(camera.zoom)
    setPan(camera.pan)
  }
  function fitView(next = layout) {
    cameraMode.current = 'fit'
    applyCamera(fitCamera(next, size))
  }
  function readSelected() {
    cameraMode.current = 'manual'
    if (layout.positions[selected] && focusMode !== 'chapters')
      applyCamera(focusCamera(layout.positions[selected], size))
    else {
      readAfterLayout.current = true
      setFocusMode('neighbors')
    }
  }
  function changeZoom(value: number, anchor = { x: size.width / 2, y: size.height / 2 }) {
    cameraMode.current = 'manual'
    applyCamera(
      zoomCamera(cameraRef.current, Math.max(Math.min(0.025, zoom), Math.min(3, value)), anchor),
    )
  }
  function toggleFullscreen() {
    if (!fullscreen) savedCamera.current = cameraRef.current
    else restoreCamera.current = true
    setFullscreen(!fullscreen)
  }
  const layoutKey =
    shown.nodes.map((n) => n.id).join(',') +
    '/' +
    shown.edges.map((e) => `${e.source}:${e.target}`).join(',')
  useEffect(() => {
    let cancelled = false
    setLayoutBusy(true)
    layoutKnowledge(
      shown.nodes.map((n) => ({
        ...n,
        chapter_title: course.data.chapters?.find((c: Row) => c.id === n.chapter_id)?.title,
      })) as any,
      shown.edges as any,
    )
      .then((next) => {
        if (cancelled) return
        setLayout(next)
        if (readAfterLayout.current && next.positions[selected]) {
          readAfterLayout.current = false
          cameraMode.current = 'manual'
          applyCamera(focusCamera(next.positions[selected], size))
        } else fitView(next)
        setLayoutBusy(false)
      })
      .catch(() => {
        if (!cancelled) {
          setLayoutBusy(false)
          notify('图谱布局暂不可用，请重试', true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [layoutKey])
  useEffect(() => {
    if (restoreCamera.current && savedCamera.current) {
      restoreCamera.current = false
      cameraMode.current = 'manual'
      applyCamera(savedCamera.current)
    } else if (cameraMode.current === 'fit') applyCamera(fitCamera(layout, size))
    else
      setPan((p) => ({
        x: p.x + (size.width - previousSize.current.width) / 2,
        y: p.y + (size.height - previousSize.current.height) / 2,
      }))
    previousSize.current = size
  }, [size, layout])
  useEffect(() => {
    if (!canvasRef.current) return
    const observer = new ResizeObserver(([e]) =>
      setSize({ width: e.contentRect.width, height: e.contentRect.height }),
    )
    observer.observe(canvasRef.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    const exit = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && fullscreen && !edit && !edge) {
        restoreCamera.current = true
        setFullscreen(false)
      }
    }
    window.addEventListener('keydown', exit)
    if (fullscreen) document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', exit)
      document.body.style.overflow = ''
    }
  }, [fullscreen])
  useEffect(() => {
    const id = Number(params.get('knowledge'))
    setSelected(nodes.some((n) => n.id === id) ? id : nodes[0]?.id || 0)
  }, [courseId, graph.data])
  useEffect(() => {
    const id = Number(params.get('knowledge'))
    if (nodes.some((n) => n.id === id)) setSelected(id)
  }, [params, nodes])
  function selectNode(id: number) {
    setSelected(id)
    if (focusMode === 'chapters') setFocusMode('neighbors')
    setDetailOpen(true)
    setParams(
      (previous) => {
        previous.set('knowledge', String(id))
        return previous
      },
      { replace: true },
    )
  }
  function selectChapter(id: number) {
    const first = nodes.find((n) => (n.chapter_id || 0) === id)
    setChapter(id)
    setFocusMode('chapter')
    setSearch('')
    if (first) {
      setSelected(first.id)
      setParams(
        (previous) => {
          previous.set('knowledge', String(first.id))
          return previous
        },
        { replace: true },
      )
    }
  }
  useEffect(() => {
    if (!search.trim()) return
    const node = nodes.find((n) => n.title.includes(search.trim()))
    if (node) {
      setSelected(node.id)
      setFocusMode('neighbors')
      setDetailOpen(true)
    }
  }, [search])
  const related = resources.data.filter((r) => r.knowledge_id === current?.id)
  const prerequisites = edges
    .filter((e) => e.target === current?.id)
    .map((e) => nodes.find((n) => n.id === e.source))
    .filter(Boolean)
  async function saveNode(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const values = new FormData(e.currentTarget)
    const body = {
      title: values.get('title'),
      description: values.get('description'),
      chapter_id: Number(values.get('chapter_id')) || null,
      x: edit?.x || 130,
      y: edit?.y || 95,
      objectives: String(values.get('objectives') || '')
        .split('\n')
        .filter(Boolean),
    }
    try {
      const saved = edit?.id
        ? await patch(`/knowledge/${edit.id}`, body)
        : await post(`/courses/${courseId}/knowledge`, body)
      selectNode(saved.id)
      notify('知识点已保存')
      setEdit(null)
      graph.reload()
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function saveEdge(e: React.FormEvent) {
    e.preventDefault()
    try {
      await post(`/courses/${courseId}/edges`, { source: from, target: to })
      setEdge(false)
      graph.reload()
      notify('先修关系已保存并通过环路校验')
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function deleteNode() {
    if (!current) return
    if (!confirm(`删除知识点「${current.title}」及其关联关系？`)) return
    try {
      await api(`/knowledge/${current.id}`, { method: 'DELETE' })
      graph.reload()
      notify('知识点已删除')
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  return (
    <>
      <Title
        title={teacher ? '课程知识图谱' : '知识图谱'}
        subtitle={
          teacher
            ? '组织知识点与先修关系，为学生搭建可循的学习路线'
            : '看见知识的连接，找到现在的位置与下一步方向'
        }
        action={
          teacher ? (
            <div className="button-row">
              <Button variant="secondary" onClick={() => setEdge(true)}>
                <Link2 size={16} />
                编辑先修关系
              </Button>
              <Button onClick={() => setEdit({})}>
                <Plus size={17} />
                新增知识点
              </Button>
            </div>
          ) : (
            <Link to="/practice" className="button">
              <Sparkles size={16} />
              开始针对练习
            </Link>
          )
        }
      />
      <LoadState {...graph} retry={graph.reload} />
      <div
        className={`graph-workspace ${fullscreen ? 'graph-fullscreen' : ''} ${detailOpen ? 'has-detail' : ''}`}
        role={fullscreen ? 'dialog' : undefined}
        aria-label={fullscreen ? '全屏知识图谱' : undefined}
      >
        <div className="graph-toolbar">
          <div className="segmented network-focus">
            {[
              ['chapters', '章节总览'],
              ['all', '全图'],
              ['neighbors', '邻近知识'],
              ['ancestors', '先修链'],
            ].map(([id, label]) => (
              <button
                key={id}
                className={focusMode === id ? 'active' : ''}
                onClick={() => {
                  setSearch('')
                  setFocusMode(id)
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <select
            aria-label="选择图谱章节"
            value={focusMode === 'chapter' ? chapter : ''}
            onChange={(e) => selectChapter(Number(e.target.value))}
          >
            <option value="" disabled>
              选择章节
            </option>
            {course.data.chapters?.map((c: Row) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
          <select
            aria-label="学习状态筛选"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="weak">待巩固</option>
            <option value="mastered">已掌握</option>
          </select>
          <input
            className="search-field"
            aria-label="定位知识点"
            placeholder="查找知识点…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {fullscreen && teacher ? (
            <Button variant="secondary small" onClick={() => setEdit(current || {})}>
              <Edit3 size={16} />
              编辑知识点
            </Button>
          ) : null}
          <Button variant="secondary" onClick={toggleFullscreen}>
            {fullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}{' '}
            {fullscreen ? '退出全屏' : '全屏查看'}
          </Button>
        </div>
        <div className="graph-layout">
          {!detailOpen && current ? (
            <button className="detail-toggle" onClick={() => setDetailOpen(true)}>
              <PanelRightOpen size={16} />
              {current.title}
            </button>
          ) : null}
          <div className="graph-canvas" ref={canvasRef} aria-busy={layoutBusy}>
            <div className="graph-label">
              <Network size={16} />
              <span>{course.data.title}</span>
              <span>
                {shown.nodes.length} {focusMode === 'chapters' ? '个章节' : '个知识点'}
              </span>
              {layoutBusy ? <span>布局中…</span> : null}
            </div>
            <svg
              viewBox={`0 0 ${size.width} ${size.height}`}
              role="img"
              aria-label="课程知识图谱，点击节点查看详情"
              onWheel={(e) => {
                const box = e.currentTarget.getBoundingClientRect()
                changeZoom(zoom * Math.exp(-e.deltaY * 0.0015), {
                  x: e.clientX - box.left,
                  y: e.clientY - box.top,
                })
              }}
              onPointerDown={(e) => {
                cameraMode.current = 'manual'
                drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
                e.currentTarget.setPointerCapture(e.pointerId)
              }}
              onPointerMove={(e) => {
                if (drag.current)
                  setPan({
                    x: drag.current.px + e.clientX - drag.current.x,
                    y: drag.current.py + e.clientY - drag.current.y,
                  })
              }}
              onPointerUp={() => {
                drag.current = null
              }}
              onPointerCancel={() => {
                drag.current = null
              }}
            >
              <defs>
                <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                  <path d="M0,0L0,6L5,3Z" fill="var(--brand-secondary)" />
                </marker>
              </defs>
              <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                {layout.clusters?.map((c) => (
                  <g className="knowledge-cluster" key={c.id}>
                    <rect x={c.x} y={c.y} width={c.width} height={c.height} rx="20" />
                    <text x={c.x + 22} y={c.y + 29}>
                      {c.title}
                    </text>
                  </g>
                ))}
                {layout.routes.map((e, i) => (
                  <path
                    key={i}
                    className={`network-edge ${e.source === selected || e.target === selected ? 'connected' : detailOpen ? 'muted-edge' : ''}`}
                    d={routePath(e.points)}
                    markerEnd="url(#arrow)"
                  />
                ))}
                {shown.nodes.map((n) => {
                  const pos = layout.positions[n.id]
                  if (!pos) return null
                  const value = percent(n.mastery),
                    isChapter = focusMode === 'chapters'
                  const observed = Number(n.evidence?.effective_count || 0) > 0
                  const tone = !observed
                    ? 'unseen'
                    : value >= 75
                      ? 'mastered'
                      : value < 40
                        ? 'weak'
                        : 'learning'
                  const dim =
                    !isChapter &&
                    ((filter === 'weak' && tone !== 'weak') ||
                      (filter === 'mastered' && tone !== 'mastered'))
                  const chunks = String(n.title).match(/.{1,5}/g) || []
                  const lines =
                    chunks.length > 3
                      ? [...chunks.slice(0, 2), chunks[2].slice(0, 4) + '…']
                      : chunks
                  const choose = () => {
                    if (isChapter) selectChapter(-n.id)
                    else selectNode(n.id)
                  }
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${pos.x} ${pos.y})`}
                      className={`knowledge-node ${tone} ${selected === n.id ? 'active' : ''} ${dim ? 'dim' : ''}`}
                      role="button"
                      tabIndex={0}
                      aria-pressed={selected === n.id}
                      aria-label={
                        isChapter
                          ? `${n.title}，展开章节`
                          : `${n.title}，掌握度 ${observed ? value + '%' : '待学习'}`
                      }
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={choose}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          choose()
                        }
                      }}
                    >
                      <circle className="node-halo" r="62" />
                      <circle className="node-body" r="51" />
                      {!isChapter && observed ? (
                        <circle className="node-ring-track" r="55" />
                      ) : null}
                      {!isChapter && observed ? (
                        <circle
                          className="node-ring"
                          r="55"
                          strokeDasharray={`${value * 3.456} 345.6`}
                          transform="rotate(-90)"
                        />
                      ) : null}
                      <text textAnchor="middle" className="node-title">
                        {lines.map((line, i) => (
                          <tspan
                            x="0"
                            dy={
                              i === 0
                                ? lines.length === 1
                                  ? -4
                                  : lines.length === 2
                                    ? -14
                                    : -24
                                : 19
                            }
                            key={i}
                          >
                            {line}
                          </tspan>
                        ))}
                      </text>
                      <text textAnchor="middle" y="32" className="node-value">
                        {isChapter
                          ? `${n.count} 个知识点`
                          : teacher
                            ? '班级状态'
                            : observed
                              ? `${value}%`
                              : '待学习'}
                      </text>
                      <title>{n.description || n.title}</title>
                    </g>
                  )
                })}
              </g>
            </svg>
            <div className="graph-controls">
              <Button
                variant="icon secondary"
                aria-label="放大图谱"
                onClick={() => changeZoom(zoom * 1.25)}
              >
                <Plus size={17} />
              </Button>
              <span>{Math.round(zoom * 100)}%</span>
              <Button
                variant="icon secondary"
                aria-label="缩小图谱"
                onClick={() => changeZoom(zoom / 1.25)}
              >
                <Minus size={17} />
              </Button>
              <Button variant="secondary small" aria-label="重置图谱视角" onClick={() => fitView()}>
                <Scan size={17} />
                适配全图
              </Button>
              <Button variant="secondary small" onClick={readSelected}>
                <Focus size={16} />
                聚焦阅读
              </Button>
            </div>
            <svg
              className="graph-minimap"
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              aria-label="图谱小地图"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') fitView()
              }}
              onClick={(e) => {
                cameraMode.current = 'manual'
                const box = e.currentTarget.getBoundingClientRect()
                const scale = Math.min(box.width / layout.width, box.height / layout.height)
                const x = (e.clientX - box.left - (box.width - layout.width * scale) / 2) / scale
                const y = (e.clientY - box.top - (box.height - layout.height * scale) / 2) / scale
                setPan({ x: size.width / 2 - x * zoom, y: size.height / 2 - y * zoom })
              }}
            >
              {layout.routes.map((e, i) => (
                <path
                  key={i}
                  d={routePath(e.points)}
                  stroke="var(--border)"
                  fill="none"
                  strokeWidth="7"
                />
              ))}
              {Object.entries(layout.positions).map(([id, p]) => (
                <circle
                  key={id}
                  cx={p.x}
                  cy={p.y}
                  r="24"
                  fill={Number(id) === selected ? 'var(--accent)' : 'var(--brand-secondary)'}
                />
              ))}
              <rect
                x={-pan.x / zoom}
                y={-pan.y / zoom}
                width={size.width / zoom}
                height={size.height / zoom}
                fill="none"
                stroke="var(--brand-primary)"
                strokeWidth="6"
              />
            </svg>
          </div>
          <Panel className={`node-detail ${detailOpen ? '' : 'detail-hidden'}`}>
            <button
              className="icon-button close-detail"
              aria-label="收起知识详情"
              onClick={() => setDetailOpen(false)}
            >
              <X size={18} />
            </button>
            {current ? (
              <>
                <div className="node-detail-icon">
                  <Network size={24} />
                </div>
                <h2>{current.title}</h2>
                <p className="node-description">
                  {current.description || '围绕课程学习目标，理解概念并完成实践。'}
                </p>
                <div className="progress-label">
                  <span>{teacher ? '班级平均估计' : '个人掌握度'}</span>
                  <strong>{currentObserved ? percent(current.mastery) + '%' : '待观测'}</strong>
                </div>
                <Progress value={currentObserved ? percent(current.mastery) : 0} />
                <p className="mini-text">
                  {current.evidence?.sufficiency || '待补充证据'} · 有效证据{' '}
                  {Number(current.evidence?.effective_count || 0).toFixed(1)} 条
                </p>
                {prerequisites.length ? (
                  <div className="prerequisites">
                    <h3>先修知识</h3>
                    {prerequisites.map((n: any) => (
                      <button key={n.id} onClick={() => selectNode(n.id)}>
                        <Check size={14} />
                        {n.title}
                        <ChevronRight size={14} />
                      </button>
                    ))}
                  </div>
                ) : null}
                {current.objectives?.length ? (
                  <div className="node-objectives">
                    <h3>学习目标</h3>
                    <ul>
                      {current.objectives.map((o: string, i: number) => (
                        <li key={i}>{o}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="node-actions">
                  <Link className="button" to={`/practice?knowledge=${current.id}`}>
                    <BookOpen size={16} />
                    练习这个知识点
                  </Link>
                  <Link className="button secondary" to={`/tutor?knowledge=${current.id}`}>
                    <Sparkles size={16} />
                    向学习伙伴提问
                  </Link>
                </div>
                <h3 className="section-title">
                  关联学习资源 <small>{related.length}</small>
                </h3>
                <div className="resource-links">
                  {related.map((r) => (
                    <Link
                      to={
                        r.kind === 'video'
                          ? `/video?resource=${r.id}&t=${r.metadata?.start || 0}&knowledge=${current.id}`
                          : r.kind === 'experiment'
                            ? `/experiments?knowledge=${current.id}`
                            : `/resources?course=${courseId}&resource=${r.id}`
                      }
                      key={r.id}
                    >
                      {r.kind === 'video' ? (
                        <Video size={17} />
                      ) : r.kind === 'experiment' ? (
                        <FlaskConical size={17} />
                      ) : (
                        <BookOpen size={17} />
                      )}
                      <div>
                        <strong>{r.title}</strong>
                        <small>
                          {r.kind === 'video'
                            ? '视频片段'
                            : r.kind === 'experiment'
                              ? '动手实验'
                              : '课程资料'}
                        </small>
                      </div>
                      <ChevronRight size={15} />
                    </Link>
                  ))}
                  {!related.length ? (
                    <p className="muted mini-text">暂无关联资源，可先从练习或辅导开始。</p>
                  ) : null}
                </div>
                {teacher ? (
                  <div className="button-row edit-actions">
                    <Button variant="secondary small" onClick={() => setEdit(current)}>
                      <Edit3 size={14} />
                      编辑知识点
                    </Button>
                    <Button variant="danger small" onClick={deleteNode}>
                      <Trash2 size={14} />
                      删除
                    </Button>
                  </div>
                ) : null}
              </>
            ) : (
              <Empty>在课程中添加第一个知识点。</Empty>
            )}
          </Panel>
        </div>
      </div>
      {edit ? (
        <Modal title={edit.id ? '编辑知识点' : '新增知识点'} close={() => setEdit(null)}>
          <form className="form-stack" onSubmit={saveNode}>
            <label>
              知识点名称
              <input name="title" defaultValue={edit.title} required maxLength={80} />
            </label>
            <label>
              所属章节
              <select name="chapter_id" defaultValue={edit.chapter_id || ''}>
                <option value="">未分章节</option>
                {course.data.chapters?.map((c: Row) => (
                  <option value={c.id} key={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              知识说明
              <textarea name="description" defaultValue={edit.description} rows={4} />
            </label>
            <label>
              学习目标（每行一个）
              <textarea
                name="objectives"
                defaultValue={edit.objectives?.join('\n') || ''}
                rows={3}
              />
            </label>
            <Button type="submit">
              <Save size={16} />
              保存知识点
            </Button>
          </form>
        </Modal>
      ) : null}
      {edge ? (
        <Modal title="管理先修关系" close={() => setEdge(false)}>
          <form className="form-stack" onSubmit={saveEdge}>
            <p className="muted">先掌握前置知识，再学习后续知识。保存时自动检查环路。</p>
            <label>
              先修知识
              <select required value={from} onChange={(e) => setFrom(Number(e.target.value))}>
                <option value={0} disabled>
                  请选择
                </option>
                {nodes.map((n) => (
                  <option value={n.id} key={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <ArrowDown size={18} />
            <label>
              后续知识
              <select required value={to} onChange={(e) => setTo(Number(e.target.value))}>
                <option value={0} disabled>
                  请选择
                </option>
                {nodes.map((n) => (
                  <option value={n.id} key={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={!from || !to || from === to}>建立先修关系</Button>
            <div className="edge-list">
              {edges.map((e) => (
                <div key={e.id}>
                  <span>
                    {nodes.find((n) => n.id === e.source)?.title} →{' '}
                    {nodes.find((n) => n.id === e.target)?.title}
                  </span>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="删除先修关系"
                    onClick={async () => {
                      try {
                        await api(`/edges/${e.id}`, { method: 'DELETE' })
                        graph.reload()
                      } catch (e) {
                        notify((e as Error).message, true)
                      }
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
