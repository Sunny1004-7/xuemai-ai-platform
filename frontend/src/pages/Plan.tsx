import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  CheckCheck,
  Clock3,
  Edit3,
  Plus,
  Save,
  Target,
  Trash2,
} from 'lucide-react'
import { api, patch, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'

const kindNames: Record<string, string> = {
  practice: '针对练习',
  video: '课程视频',
  review: '错题复习',
  experiment: '交互实验',
  reading: '资料阅读',
}
const kindRoutes: Record<string, string> = {
  practice: '/practice',
  video: '/video',
  review: '/review',
  experiment: '/experiments',
  reading: '/resources',
}
export function LearningPlan() {
  const { user, courseId, notify } = useApp()
  const query = useApi<Row>(user.role === 'student' ? `/plan?course_id=${courseId}` : null, {
    goals: [],
    items: [],
    recommendations: [],
  })
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const [edit, setEdit] = useState<Row | null>(null)
  const [kind, setKind] = useState('goal')
  const [busy, setBusy] = useState(false)
  const [knowledgeIds, setKnowledgeIds] = useState<number[]>([])
  if (user.role !== 'student') return <Empty>个人学习计划属于学生的学习空间。</Empty>
  const goals: Row[] = query.data.goals || [],
    items: Row[] = query.data.items || []
  function open(type: string, value: Row = {}) {
    setKind(type)
    setEdit(value)
    setKnowledgeIds(value.knowledge_ids || [])
  }
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const body =
        kind === 'goal'
          ? {
              course_id: courseId,
              title: f.get('title'),
              description: f.get('description'),
              target_date: f.get('target_date') || null,
              daily_minutes: Number(f.get('daily_minutes')),
              knowledge_ids: knowledgeIds,
              status: f.get('status'),
            }
          : {
              course_id: courseId,
              title: f.get('title'),
              description: f.get('description'),
              goal_id: Number(f.get('goal_id')) || null,
              knowledge_id: Number(f.get('knowledge_id')) || null,
              kind: f.get('kind'),
              scheduled_date: f.get('scheduled_date') || null,
              estimated_minutes: Number(f.get('estimated_minutes')),
              status: f.get('status'),
            }
      if (edit?.id) await patch(`/${kind === 'goal' ? 'goals' : 'plans'}/${edit.id}`, body)
      else await post(kind === 'goal' ? '/goals' : '/plans', body)
      query.reload()
      setEdit(null)
      notify(kind === 'goal' ? '个人学习目标已保存' : '学习安排已保存')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function complete(item: Row) {
    try {
      await patch(`/plans/${item.id}`, {
        status: item.status === 'completed' ? 'planned' : 'completed',
      })
      query.reload()
      notify(
        item.status === 'completed'
          ? '已恢复为待完成'
          : '计划已标记完成；掌握度仍依据实际学习证据更新',
      )
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function remove(type: string, id: number) {
    if (!confirm(`删除这项${type === 'goal' ? '学习目标' : '学习安排'}？`)) return
    try {
      await api(`/${type === 'goal' ? 'goals' : 'plans'}/${id}`, { method: 'DELETE' })
      query.reload()
      notify('已删除')
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  return (
    <>
      <Title
        title="按自己的节奏，走好每一步"
        subtitle="设定个人目标，把可解释的学习建议放进日常安排"
        action={
          <div className="button-row">
            <Button variant="secondary" onClick={() => open('goal')}>
              <Target size={16} />
              设定学习目标
            </Button>
            <Button onClick={() => open('plan')}>
              <Plus size={16} />
              新增学习安排
            </Button>
          </div>
        }
      />
      <LoadState {...query} retry={query.reload} />
      <div className="plan-layout">
        <div>
          <Panel title="我的学习目标" caption="从想要理解的知识出发，给自己一个清晰的方向">
            {goals.length ? (
              goals.map((g) => (
                <div className="goal-card" key={g.id}>
                  <span className="goal-icon">
                    <Target size={23} />
                  </span>
                  <div>
                    <div className="goal-title">
                      <h3>{g.title}</h3>
                      <Pill
                        tone={
                          g.status === 'completed'
                            ? 'green'
                            : g.status === 'paused'
                              ? 'neutral'
                              : 'blue'
                        }
                      >
                        {g.status === 'completed'
                          ? '已完成'
                          : g.status === 'paused'
                            ? '暂缓'
                            : '进行中'}
                      </Pill>
                    </div>
                    <p>{g.description || '持续积累，逐步理解。'}</p>
                    <div className="goal-meta">
                      <span>
                        <Clock3 size={13} />
                        每天 {g.daily_minutes} 分钟
                      </span>
                      {g.target_date ? (
                        <span>
                          <CalendarDays size={13} />
                          {g.target_date}
                        </span>
                      ) : null}
                    </div>
                    <div className="goal-knowledge">
                      {g.knowledge_ids?.map((id: number) => (
                        <Link to={`/graph?knowledge=${id}`} key={id}>
                          {graph.data.nodes?.find((n: Row) => n.id === id)?.title || '关联知识'}
                        </Link>
                      ))}
                    </div>
                  </div>
                  <div className="goal-actions">
                    <Button
                      variant="icon ghost"
                      aria-label={`编辑目标${g.title}`}
                      onClick={() => open('goal', g)}
                    >
                      <Edit3 size={15} />
                    </Button>
                    <Button
                      variant="icon ghost"
                      aria-label={`删除目标${g.title}`}
                      onClick={() => remove('goal', g.id)}
                    >
                      <Trash2 size={15} />
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <Empty
                action={
                  <Button variant="secondary" onClick={() => open('goal')}>
                    设定第一个学习目标
                  </Button>
                }
              >
                先选一段想要理解的知识，再为它留一点时间。
              </Empty>
            )}
          </Panel>
          <Panel title="我的学习安排" caption="完成状态是你的自我记录，不会直接提高知识掌握度">
            {items.length ? (
              <div className="personal-plan-list">
                {items.map((item) => (
                  <div key={item.id} className={item.status === 'completed' ? 'completed' : ''}>
                    <button
                      className="plan-check"
                      aria-label={`${item.status === 'completed' ? '恢复' : '完成'}计划${item.title}`}
                      onClick={() => complete(item)}
                    >
                      {item.status === 'completed' ? <CheckCheck size={16} /> : null}
                    </button>
                    <div>
                      <h3>{item.title}</h3>
                      <p>{item.description}</p>
                      <div className="goal-meta">
                        <Pill tone="blue">{kindNames[item.kind]}</Pill>
                        <span>{item.estimated_minutes} 分钟</span>
                        <span>{item.scheduled_date || '自主安排'}</span>
                      </div>
                    </div>
                    <div className="plan-item-actions">
                      <Link
                        to={`${kindRoutes[item.kind] || '/practice'}${item.knowledge_id ? `?knowledge=${item.knowledge_id}` : ''}`}
                        className="button small secondary"
                      >
                        开始
                        <ArrowRight size={13} />
                      </Link>
                      <Button
                        variant="icon ghost"
                        aria-label={`编辑安排${item.title}`}
                        onClick={() => open('plan', item)}
                      >
                        <Edit3 size={14} />
                      </Button>
                      <Button
                        variant="icon ghost"
                        aria-label={`删除安排${item.title}`}
                        onClick={() => remove('plan', item.id)}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                action={
                  <Button variant="secondary" onClick={() => open('plan')}>
                    安排一次学习
                  </Button>
                }
              >
                给视频、练习或实验留出一段专注时间。
              </Empty>
            )}
          </Panel>
        </div>
        <Panel
          title="可以考虑的下一步"
          caption={query.data.explanation || '依据先修关系与近期学习证据推荐'}
        >
          <div className="plan-recommendations">
            {(query.data.recommendations || []).slice(0, 5).map((r: Row, i: number) => (
              <div key={r.id || i}>
                <Pill tone={r.kind === 'review' ? 'amber' : 'green'}>
                  {kindNames[r.kind] || '学习建议'}
                </Pill>
                <h3>{r.title}</h3>
                <p>{r.reason}</p>
                <div className="button-row">
                  <Link to={r.href || '/practice'} className="text-link">
                    直接开始
                    <ArrowRight size={13} />
                  </Link>
                  <Button
                    variant="small ghost"
                    onClick={() =>
                      open('plan', {
                        title: r.title,
                        description: r.reason,
                        knowledge_id: r.knowledge_id,
                        kind: r.kind,
                        estimated_minutes: 15,
                        status: 'planned',
                      })
                    }
                  >
                    <Plus size={13} />
                    加入安排
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      {edit ? (
        <Modal
          title={kind === 'goal' ? '设定个人学习目标' : '安排一次专注学习'}
          close={() => setEdit(null)}
        >
          <form className="form-stack" onSubmit={save}>
            <label>
              {kind === 'goal' ? '目标名称' : '学习安排'}
              <input required name="title" defaultValue={edit.title} maxLength={200} />
            </label>
            <label>
              写给自己的说明
              <textarea name="description" rows={3} defaultValue={edit.description} />
            </label>
            {kind === 'goal' ? (
              <>
                <div className="form-columns">
                  <label>
                    每天计划投入（分钟）
                    <input
                      name="daily_minutes"
                      type="number"
                      min={5}
                      max={240}
                      defaultValue={edit.daily_minutes || 25}
                      required
                    />
                  </label>
                  <label>
                    目标日期
                    <input name="target_date" type="date" defaultValue={edit.target_date || ''} />
                  </label>
                </div>
                <label>
                  目标状态
                  <select name="status" defaultValue={edit.status || 'active'}>
                    <option value="active">进行中</option>
                    <option value="paused">暂缓</option>
                    <option value="completed">已完成</option>
                  </select>
                </label>
                <fieldset>
                  <legend>关联想要掌握的知识</legend>
                  <div className="checkbox-list">
                    {graph.data.nodes?.map((n: Row) => (
                      <label key={n.id}>
                        <input
                          type="checkbox"
                          checked={knowledgeIds.includes(n.id)}
                          onChange={(e) =>
                            setKnowledgeIds((v) =>
                              e.target.checked ? [...v, n.id] : v.filter((id) => id !== n.id),
                            )
                          }
                        />
                        {n.title}
                      </label>
                    ))}
                  </div>
                </fieldset>
              </>
            ) : (
              <>
                <div className="form-columns">
                  <label>
                    学习形式
                    <select name="kind" defaultValue={edit.kind || 'practice'}>
                      {Object.entries(kindNames).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    预计时长（分钟）
                    <input
                      required
                      type="number"
                      min={1}
                      max={240}
                      name="estimated_minutes"
                      defaultValue={edit.estimated_minutes || 15}
                    />
                  </label>
                </div>
                <label>
                  关联目标
                  <select name="goal_id" defaultValue={edit.goal_id || ''}>
                    <option value="">不关联目标</option>
                    {goals.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  关联知识
                  <select name="knowledge_id" defaultValue={edit.knowledge_id || ''}>
                    <option value="">课程通用</option>
                    {graph.data.nodes?.map((n: Row) => (
                      <option key={n.id} value={n.id}>
                        {n.title}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="form-columns">
                  <label>
                    计划日期
                    <input
                      type="date"
                      name="scheduled_date"
                      defaultValue={edit.scheduled_date || ''}
                    />
                  </label>
                  <label>
                    完成状态
                    <select name="status" defaultValue={edit.status || 'planned'}>
                      <option value="planned">待完成</option>
                      <option value="completed">已完成</option>
                      <option value="skipped">暂时跳过</option>
                    </select>
                  </label>
                </div>
              </>
            )}
            <Button disabled={busy}>
              <Save size={16} />
              {busy ? '保存中…' : '保存'}
            </Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
