import { Pager, usePage } from './Workspace'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Row } from '../api'
import { Panel, Button } from '../ui'

export function TrendChart({ rows = [] }: { rows?: Row[] }) {
  const top = Math.max(1, ...rows.map((r) => r.count))
  return (
    <div className="trend-chart" aria-label="近十四天练习趋势">
      {rows.map((r, index) => (
        <Link
          aria-label={`${r.day}，${r.count}次作答，正确率${r.accuracy ?? '待观测'}${r.accuracy == null ? '' : '%'}`}
          to="/practice"
          key={r.day}
          title={`${r.day}：${r.count} 次作答，正确率 ${r.accuracy ?? '—'}%`}
        >
          <span className="trend-column">
            <i style={{ height: `${r.count ? Math.max(3, (r.count / top) * 100) : 0}%` }} />
            {r.accuracy != null ? <b style={{ bottom: `${r.accuracy}%` }} /> : null}
          </span>
          <small>
            {(index % 3 === 0 && index < rows.length - 2) || index === rows.length - 1
              ? r.day.slice(5)
              : ''}
          </small>
        </Link>
      ))}
      <div className="chart-key">
        <span>柱：作答次数（最高 {Math.max(0, ...rows.map((r) => r.count))} 次）</span>
        <span>点：正确率</span>
      </div>
    </div>
  )
}

export function PersonalCharts({ data, courseId }: { data: Row; courseId: number }) {
  const chapters = [...new Set((data.knowledge || []).map((n: Row) => n.chapter_title))]
  const names: Record<string, string> = {
    attempt: '练习',
    video_progress: '视频',
    experiment: '实验',
    understanding_check: '辅导检查',
    teacher_review: '教师反馈',
  }
  return (
    <div className="learning-chart-grid">
      <Panel title="知识领域">
        <div className="domain-bars">
          {chapters.map((name: any) => {
            const nodes: Row[] = data.knowledge.filter((n: Row) => n.chapter_title === name)
            const known = nodes.filter((n) => n.observed_count > 0)
            const value = known.length
              ? Math.round(known.reduce((s, n) => s + n.average_mastery, 0) / known.length)
              : null
            return (
              <Link
                key={name}
                to={`/graph?course=${courseId}&knowledge=${nodes[0]?.id}`}
                title={`${known.length}/${nodes.length} 个知识点已有证据`}
              >
                <span>{name || '未分章节'}</span>
                <i>
                  <b style={{ width: `${value || 0}%` }} />
                </i>
                <strong>{value === null ? '待学习' : `${value}%`}</strong>
              </Link>
            )
          })}
        </div>
      </Panel>
      <Panel title="学习进展">
        <TrendChart rows={data.trend} />
      </Panel>
      <Panel title="学习活动">
        <div className="activity-chips">
          {(data.activities || []).map((r: Row) => (
            <Link
              key={r.kind}
              to={
                r.kind.includes('video')
                  ? '/video'
                  : r.kind === 'experiment'
                    ? '/experiments'
                    : r.kind.includes('check')
                      ? '/tutor'
                      : '/practice'
              }
            >
              <strong>{r.count}</strong>
              <span>{names[r.kind] || '学习记录'}</span>
            </Link>
          ))}
        </div>
      </Panel>
      <Panel title="能力表现">
        <div className="domain-bars">
          {(data.skills || []).map((r: Row) => (
            <Link key={r.skill} to="/practice" title={`${r.count} 条已评分作答`}>
              <span>{r.name}</span>
              <i>
                <b style={{ width: `${r.performance || 0}%`, background: 'var(--data)' }} />
              </i>
              <strong>{r.performance === null ? '待检验' : `${r.performance}%`}</strong>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  )
}

export function CohortCharts({
  data,
  onCell,
  onGroup,
  view = 'matrix',
}: {
  data: Row
  view?: 'matrix' | 'groups' | 'trends'
  onCell: (node: Row, student: Row) => void
  onGroup: (group: Row) => void
}) {
  const [chapter, setChapter] = useState('all')
  const [student, setStudent] = useState('')
  const [state, setState] = useState('all')
  const nodes: Row[] = (data.knowledge || []).filter(
    (n: Row) => chapter === 'all' || String(n.chapter_id) === chapter,
  )
  const chapters: Row[] = [
    ...new Map(
      (data.knowledge || []).map((n: Row) => [
        n.chapter_id,
        { id: n.chapter_id, title: n.chapter_title },
      ]),
    ).values(),
  ] as Row[]
  const rows = usePage<Row>(
    (data.heatmap || []).filter((r: Row) => r.name.includes(student)),
    47,
    530,
  )
  const [columnPage, setColumnPage] = useState(1)
  const columns = nodes.slice((columnPage - 1) * 6, columnPage * 6)
  return (
    <>
      {view === 'matrix' ? (
        <>
          <Panel title="班级知识矩阵">
            <div className="matrix-filters">
              <select
                aria-label="筛选学情章节"
                value={chapter}
                onChange={(e) => {
                  setChapter(e.target.value)
                  setColumnPage(1)
                }}
              >
                <option value="all">全部章节</option>
                {chapters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
              <input
                aria-label="筛选学生"
                placeholder="查找学生"
                value={student}
                onChange={(e) => setStudent(e.target.value)}
              />
              <select
                aria-label="筛选关注状态"
                value={state}
                onChange={(e) => setState(e.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="weak">待巩固</option>
                <option value="unknown">待观测</option>
              </select>
            </div>
            <div className="knowledge-matrix">
              <table>
                <thead>
                  <tr>
                    <th>学生 / 知识</th>
                    {columns.map((n) => (
                      <th key={n.id}>
                        <Link to={`/graph?knowledge=${n.id}`}>{n.title}</Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.rows.map((row: Row) => (
                    <tr key={row.student_id}>
                      <th>{row.name}</th>
                      {columns.map((n) => {
                        const cell = row.cells.find((c: Row) => c.knowledge_id === n.id)
                        const value = cell?.value,
                          tone =
                            value == null
                              ? 'unknown'
                              : value >= 75
                                ? 'mastered'
                                : value < 40
                                  ? 'weak'
                                  : 'learning'
                        return (
                          <td key={n.id}>
                            <button
                              className={`matrix-cell ${tone} ${state !== 'all' && state !== tone ? 'muted-cell' : ''}`}
                              onClick={() => onCell(n, { id: row.student_id, name: row.name })}
                              title={`${row.name} · ${n.title} · ${value == null ? '待观测' : value + '%'} · 有效证据${cell?.count || 0}`}
                              aria-label={`${row.name}，${n.title}，${value == null ? '待观测' : value + '%'}`}
                            >
                              {value ?? '—'}
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="matrix-pagers">
              <Pager {...rows} onChange={rows.setPage} label="位学生" />
              <Pager
                page={columnPage}
                size={6}
                count={nodes.length}
                onChange={setColumnPage}
                label="个知识点"
              />
            </div>
            <div className="chart-key">
              <span>— 待观测</span>
              <span>0–39 待巩固</span>
              <span>40–74 学习中</span>
              <span>75–100 较稳固</span>
            </div>
          </Panel>
        </>
      ) : null}
      {view === 'trends' ? (
        <>
          <div className="learning-chart-grid">
            <Panel title="班级练习趋势">
              <TrendChart rows={data.trend} />
            </Panel>
            <Panel title="知识状态分布">
              <div className="distribution-bars">
                {nodes.slice(0, 6).map((n) => (
                  <button key={n.id} onClick={() => onCell(n, data.students?.[0] || {})}>
                    <span>{n.title}</span>
                    <i>
                      {['mastered', 'learning', 'weak', 'unknown'].map((t) => (
                        <b
                          className={t}
                          key={t}
                          style={{
                            width: `${((n.distribution?.[t] || 0) / Math.max(1, data.students?.length)) * 100}%`,
                          }}
                          title={`${t}：${n.distribution?.[t] || 0}人`}
                        />
                      ))}
                    </i>
                  </button>
                ))}
              </div>
            </Panel>
          </div>
        </>
      ) : null}
      {view === 'groups' ? (
        <Panel title="动态教学群组">
          <div className="teaching-groups">
            {(data.groups || []).map((g: Row) => (
              <article key={g.id}>
                <span className="group-size">
                  {g.student_ids.length}
                  <small>人</small>
                </span>
                <h3>{g.name}</h3>
                <p>{g.strategy}</p>
                <div className="group-features">
                  {Object.entries(g.features)
                    .slice(0, 4)
                    .map(([label, v]) => (
                      <div key={label}>
                        <span>{label}</span>
                        <i style={{ width: `${Number(v) * 100}%` }} />
                      </div>
                    ))}
                </div>
                <Button variant="secondary small" onClick={() => onGroup(g)}>
                  安排匹配任务
                </Button>
              </article>
            ))}
          </div>
        </Panel>
      ) : null}
    </>
  )
}
