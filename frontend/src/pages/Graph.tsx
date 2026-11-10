import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowDown,
  BookOpen,
  Check,
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
} from 'lucide-react'
import { layoutKnowledge, relatedKnowledge } from '../graph-layout'
import { api, patch, percent, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Progress, Title, useApp } from '../ui'

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
  const [focusMode, setFocusMode] = useState('all')
  const [moved, setMoved] = useState<Record<number, { x: number; y: number }>>({})
  const [hover, setHover] = useState(0)
  const nodeDrag = useRef<{
    id: number
    x: number
    y: number
    startX: number
    startY: number
  } | null>(null)
  const wasDragged = useRef(false)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const teacher = user.role === 'teacher'
  const nodes: Row[] = graph.data.nodes || []
  const edges: Row[] = graph.data.edges || []
  const current = nodes.find((n) => n.id === selected) || nodes[0]
  const layout = useMemo(
    () =>
      layoutKnowledge(
        nodes as { id: number; title: string; chapter_id?: number }[],
        edges as { source: number; target: number }[],
      ),
    [nodes, edges],
  )
  const positions = { ...layout.positions, ...moved }
  const visibleIds =
    focusMode === 'all'
      ? null
      : relatedKnowledge(
          current?.id || 0,
          edges as { source: number; target: number }[],
          focusMode === 'ancestors',
        )
  useEffect(() => {
    const id = Number(params.get('knowledge'))
    setSelected(nodes.some((n) => n.id === id) ? id : nodes[0]?.id || 0)
    setMoved({})
    setPan({ x: 0, y: 0 })
    setZoom(1)
  }, [courseId, graph.data])
  useEffect(() => {
    const id = Number(params.get('knowledge'))
    if (nodes.some((n) => n.id === id)) setSelected(id)
  }, [params, nodes])
  function selectNode(id: number) {
    setSelected(id)
    setParams(
      (previous) => {
        previous.set('knowledge', String(id))
        return previous
      },
      { replace: true },
    )
  }
  useEffect(() => {
    if (!search.trim()) return
    const node = nodes.find((n) => n.title.includes(search.trim()))
    if (node) {
      setSelected(node.id)
      const pos = positions[node.id]
      setZoom(1.65)
      setPan({ x: layout.width / 2 - pos.x * 1.65, y: layout.height / 2 - pos.y * 1.65 })
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
      if (edit?.id) await patch(`/knowledge/${edit.id}`, body)
      else await post(`/courses/${courseId}/knowledge`, body)
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
      <div className="graph-toolbar">
        <div className="segmented">
          {[
            ['all', '全部知识'],
            ['weak', '待巩固'],
            ['mastered', '已掌握'],
          ].map(([value, label]) => (
            <button
              key={value}
              className={filter === value ? 'active' : ''}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="segmented network-focus">
          {[
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
        <div className="graph-legend">
          <span>
            <i className="legend-dot green" />
            已掌握
          </span>
          <span>
            <i className="legend-dot blue" />
            学习中
          </span>
          <span>
            <i className="legend-dot amber" />
            待巩固
          </span>
          <span>
            <i className="legend-dot gray" />
            未接触
          </span>
        </div>
        <input
          className="search-field"
          aria-label="定位知识点"
          placeholder="查找知识点…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="graph-layout">
        <div className="graph-canvas">
          <div className="graph-label">
            <Network size={17} />
            <span>{course.data.title || '课程知识网络'}</span>
            <Pill>{nodes.length} 个知识点</Pill>
          </div>
          <svg
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            role="img"
            aria-label="课程知识图谱，点击节点查看详情"
            onWheel={(e) => setZoom((z) => Math.max(0.5, Math.min(3, z - e.deltaY * 0.001)))}
            onPointerDown={(e) => {
              if (e.target === e.currentTarget) {
                drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
                e.currentTarget.setPointerCapture(e.pointerId)
              }
            }}
            onPointerMove={(e) => {
              if (drag.current) {
                const rect = e.currentTarget.getBoundingClientRect()
                setPan({
                  x:
                    drag.current.px +
                    (e.clientX - drag.current.x) /
                      Math.min(rect.width / layout.width, rect.height / layout.height),
                  y:
                    drag.current.py +
                    (e.clientY - drag.current.y) /
                      Math.min(rect.width / layout.width, rect.height / layout.height),
                })
              }
            }}
            onPointerUp={() => {
              drag.current = null
            }}
          >
            <defs>
              <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                <path d="M0,0L0,6L6,3Z" fill="var(--brand-secondary)" />
              </marker>
            </defs>
            <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              {layout.groups.map((group) => (
                <g key={group.chapter_id} className="knowledge-cluster">
                  <rect x={group.x} y={group.y} width={group.width} height={group.height} rx="12" />
                  <text x={group.x + 18} y={group.y + 30}>
                    {course.data.chapters?.find((c: Row) => c.id === group.chapter_id)?.title ||
                      '未分组'}
                  </text>
                </g>
              ))}
              {edges.map((edge, i) => {
                const a = positions[edge.source],
                  b = positions[edge.target]
                if (!a || !b) return null
                const angle = Math.atan2(b.y - a.y, b.x - a.x)
                const x1 = a.x + Math.cos(angle) * 47,
                  y1 = a.y + Math.sin(angle) * 47,
                  x2 = b.x - Math.cos(angle) * 51,
                  y2 = b.y - Math.sin(angle) * 51
                return (
                  <path
                    key={edge.id || i}
                    className={`network-edge ${edge.source === current?.id || edge.target === current?.id ? 'connected' : ''}`}
                    opacity={
                      visibleIds && (!visibleIds.has(edge.source) || !visibleIds.has(edge.target))
                        ? 0.12
                        : 1
                    }
                    d={`M${x1} ${y1}C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}`}
                    markerEnd="url(#arrow)"
                  />
                )
              })}
              {nodes.map((n) => {
                const value = percent(n.mastery),
                  pos = positions[n.id],
                  active = current?.id === n.id
                const tone = value >= 75 ? 'mastered' : value < 40 ? 'weak' : 'learning'
                const dim =
                  (search && !n.title.includes(search)) ||
                  (filter === 'weak' && tone !== 'weak') ||
                  (filter === 'mastered' && tone !== 'mastered') ||
                  (visibleIds && !visibleIds.has(n.id))
                const lines = String(n.title).match(/.{1,6}/g) || []
                return (
                  <g
                    key={n.id}
                    transform={`translate(${pos.x} ${pos.y})`}
                    className={`knowledge-node ${tone} ${active ? 'active' : ''} ${dim ? 'dim' : ''}`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={active}
                    aria-label={`${n.title}，掌握度 ${value}%`}
                    onMouseEnter={() => setHover(n.id)}
                    onMouseLeave={() => setHover(0)}
                    onClick={() => {
                      if (!wasDragged.current) selectNode(n.id)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        selectNode(n.id)
                      }
                    }}
                    onPointerDown={(e) => {
                      e.stopPropagation()
                      wasDragged.current = false
                      nodeDrag.current = {
                        id: n.id,
                        x: pos.x,
                        y: pos.y,
                        startX: e.clientX,
                        startY: e.clientY,
                      }
                      e.currentTarget.setPointerCapture(e.pointerId)
                    }}
                    onPointerMove={(e) => {
                      if (nodeDrag.current?.id === n.id) {
                        const svg = e.currentTarget.ownerSVGElement!
                        const rect = svg.getBoundingClientRect()
                        const scale =
                          1 /
                          Math.min(rect.width / layout.width, rect.height / layout.height) /
                          zoom
                        const dx = (e.clientX - nodeDrag.current!.startX) * scale,
                          dy = (e.clientY - nodeDrag.current!.startY) * scale
                        if (Math.abs(dx) + Math.abs(dy) > 5) wasDragged.current = true
                        setMoved((v) => ({
                          ...v,
                          [n.id]: { x: nodeDrag.current!.x + dx, y: nodeDrag.current!.y + dy },
                        }))
                      }
                    }}
                    onPointerUp={() => {
                      nodeDrag.current = null
                    }}
                  >
                    <circle className="node-body" r="42" />
                    <circle className="node-ring-track" r="46" />
                    <circle
                      className="node-ring"
                      r="46"
                      strokeDasharray={`${value * 2.89} 289`}
                      transform="rotate(-90)"
                    />
                    <text textAnchor="middle" className="node-title">
                      {lines.map((line, i) => (
                        <tspan x="0" dy={i === 0 ? (lines.length === 1 ? -4 : -12) : 16} key={i}>
                          {line}
                        </tspan>
                      ))}
                    </text>
                    <text textAnchor="middle" y="27" className="node-value">
                      {teacher
                        ? course.data.chapters
                            ?.find((c: Row) => c.id === n.chapter_id)
                            ?.title?.slice(0, 5) || '未分组'
                        : `${value}%`}
                    </text>
                    <title>
                      {n.title} · {n.description}
                    </title>
                  </g>
                )
              })}
            </g>
          </svg>
          {hover ? (
            <div className="node-preview">
              {nodes.find((n) => n.id === hover)?.title} ·{' '}
              {percent(nodes.find((n) => n.id === hover)?.mastery)}%
            </div>
          ) : null}
          <div className="graph-controls">
            <Button
              variant="icon secondary"
              aria-label="放大图谱"
              onClick={() => setZoom((z) => Math.min(2, z + 0.15))}
            >
              <Plus size={17} />
            </Button>
            <span>{Math.round(zoom * 100)}%</span>
            <Button
              variant="icon secondary"
              aria-label="缩小图谱"
              onClick={() => setZoom((z) => Math.max(0.45, z - 0.15))}
            >
              <Minus size={17} />
            </Button>
            <Button
              variant="icon secondary"
              aria-label="重置图谱视角"
              onClick={() => {
                setZoom(1)
                setPan({ x: 0, y: 0 })
              }}
            >
              <Focus size={17} />
            </Button>
          </div>
        </div>
        <Panel className="node-detail">
          {current ? (
            <>
              <div className="node-detail-icon">
                <Network size={24} />
              </div>
              <div className="section-kicker">当前知识点</div>
              <h2>{current.title}</h2>
              <p className="node-description">
                {current.description || '围绕课程学习目标，理解概念并完成实践。'}
              </p>
              <div className="progress-label">
                <span>{teacher ? '班级平均估计' : '个人掌握度'}</span>
                <strong>{percent(current.mastery)}%</strong>
              </div>
              <Progress value={percent(current.mastery)} />
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
