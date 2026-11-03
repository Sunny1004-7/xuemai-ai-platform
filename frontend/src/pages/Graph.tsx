import { useMemo, useRef, useState } from 'react'
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
  Move,
  Network,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Video,
} from 'lucide-react'
import { api, patch, percent, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Progress, Title, useApp } from '../ui'

export function Graph() {
  const { user, courseId, notify } = useApp()
  const [params] = useSearchParams()
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
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const teacher = user.role === 'teacher'
  const nodes: Row[] = graph.data.nodes || []
  const edges: Row[] = graph.data.edges || []
  const current = nodes.find((n) => n.id === selected) || nodes[0]
  const positions = useMemo(
    () =>
      Object.fromEntries(
        nodes.map((n, i) => [
          n.id,
          {
            x: (Number(n.x) || 30 + (i % 4) * 205) * 0.82 + 95,
            y: (Number(n.y) || 60 + Math.floor(i / 4) * 155) * 1.25 + 80,
          },
        ]),
      ),
    [nodes],
  )
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
        title={teacher ? '课程知识图谱' : '知识之间，自有脉络'}
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
            viewBox="0 0 1000 620"
            role="img"
            aria-label="课程知识图谱，点击节点查看详情"
            onWheel={(e) => setZoom((z) => Math.max(0.45, Math.min(2, z - e.deltaY * 0.001)))}
            onPointerDown={(e) => {
              if (e.target === e.currentTarget) {
                drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
                e.currentTarget.setPointerCapture(e.pointerId)
              }
            }}
            onPointerMove={(e) => {
              if (drag.current)
                setPan({
                  x: drag.current.px + (e.clientX - drag.current.x),
                  y: drag.current.py + (e.clientY - drag.current.y),
                })
            }}
            onPointerUp={() => {
              drag.current = null
            }}
          >
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#a8b8cc" />
              </marker>
            </defs>
            <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
              {edges.map((e, i) => {
                const a = positions[e.source],
                  b = positions[e.target]
                return a && b ? (
                  <path
                    key={e.id || i}
                    d={`M${a.x + 68},${a.y} C${a.x + 115},${a.y} ${b.x - 115},${b.y} ${b.x - 73},${b.y}`}
                    stroke={
                      e.target === current?.id || e.source === current?.id ? '#409d8a' : '#c9d3e1'
                    }
                    strokeWidth={e.target === current?.id || e.source === current?.id ? 2.3 : 1.6}
                    fill="none"
                    markerEnd="url(#arrow)"
                  />
                ) : null
              })}
              {nodes.map((n) => {
                const value = percent(n.mastery),
                  pos = positions[n.id],
                  active = current?.id === n.id
                const tone =
                  value >= 75
                    ? 'mastered'
                    : value > 0 && value < 40
                      ? 'weak'
                      : value
                        ? 'learning'
                        : 'new'
                const muted =
                  (search && !n.title.includes(search)) ||
                  (filter === 'weak' && tone !== 'weak') ||
                  (filter === 'mastered' && tone !== 'mastered')
                return (
                  <g
                    key={n.id}
                    transform={`translate(${pos.x} ${pos.y})`}
                    className={`knowledge-node ${tone} ${active ? 'active' : ''} ${muted ? 'dim' : ''}`}
                    onClick={() => setSelected(n.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelected(n.id)
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`${n.title}，掌握度 ${value}%`}
                  >
                    <rect x="-69" y="-37" width="138" height="74" rx="11" />
                    <circle cx="-48" cy="-18" r="3" />
                    <text x="-37" y="-14" className="node-state">
                      {tone === 'mastered'
                        ? '已掌握'
                        : tone === 'weak'
                          ? '待巩固'
                          : tone === 'learning'
                            ? '学习中'
                            : '待探索'}
                    </text>
                    <text x="0" y="9" textAnchor="middle" className="node-title">
                      {n.title.length > 10 ? n.title.slice(0, 10) + '…' : n.title}
                    </text>
                    <rect className="node-track" x="-48" y="22" width="96" height="3" rx="1.5" />
                    <rect
                      className="node-fill"
                      x="-48"
                      y="22"
                      width={value * 0.96}
                      height="3"
                      rx="1.5"
                    />
                  </g>
                )
              })}
            </g>
          </svg>
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
          <div className="graph-help">
            <Move size={13} />
            拖拽画布移动 · 滚轮缩放 · 点击知识点探索
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
                <span>个人掌握度</span>
                <strong>{percent(current.mastery)}%</strong>
              </div>
              <Progress value={percent(current.mastery)} />
              <p className="mini-text">依据独立作答、提示使用与复测表现更新。</p>
              {prerequisites.length ? (
                <div className="prerequisites">
                  <h3>先修知识</h3>
                  {prerequisites.map((n: any) => (
                    <button key={n.id} onClick={() => setSelected(n.id)}>
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
                          : `/resources?resource=${r.id}`
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
