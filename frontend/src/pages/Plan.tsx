import { Pager, Tabs, usePage } from '../components/Workspace'
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
  const [view, setView] = useState('today')
  const [activityKind, setActivityKind] = useState('practice')
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const questions = useApi<Row[]>(`/questions?course_id=${courseId}`, [])
  const [busy, setBusy] = useState(false)
  const [knowledgeIds, setKnowledgeIds] = useState<number[]>([])

  const goals: Row[] = query.data.goals || [],
    items: Row[] = query.data.items || []
  const goalPage = usePage<Row>(goals, 180, 330)
  const today = new Date().toLocaleDateString('en-CA')
  const shownItems = items.filter((r) =>
    view === 'history'
      ? r.status !== 'planned'
      : view === 'today'
        ? r.status === 'planned' && (!r.scheduled_date || r.scheduled_date <= today)
        : r.status === 'planned',
  )
  const itemPage = usePage<Row>(shownItems, 128, 330)
  const recs: Row[] = (query.data.recommendations || []).filter((r: Row) =>
    view === 'next' ? !r.in_current_plan : r.in_current_plan,
  )
  const recPage = usePage<Row>(recs, 160, 350)
  if (user.role !== 'student') return <Empty>个人学习计划属于学生的学习空间。</Empty>
  function open(type: string, value: Row = {}) {
    setKind(type)
    setActivityKind(value.kind || 'practice')
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
              target:
                activityKind === 'video' || activityKind === 'reading'
                  ? {
                      resource_id: Number(f.get('resource_id')) || undefined,
                      video_timestamp: Number(f.get('video_timestamp')) || 0,
                      completion_kind: activityKind === 'video' ? 'video_progress' : 'self_report',
                    }
                  : activityKind === 'experiment'
                    ? { experiment_id: f.get('experiment_id'), completion_kind: 'experiment' }
                    : {
                        question_id: Number(f.get('question_id')) || undefined,
                        completion_kind: 'attempt',
                      },
              scheduled_date: f.get('scheduled_date') || null,
              estimated_minutes: Number(f.get('estimated_minutes')),
              status: f.get('status'),
            }
      if (edit?.id) await patch(`/${kind === 'goal' ? 'goals' : 'plans'}/${edit.id}`, body)
      else await post(kind === 'goal' ? '/goals' : '/plans', body)
      query.reload()
      setView(kind === 'goal' ? 'goals' : 'today')
      goalPage.setPage(1)
      itemPage.setPage(1)
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
        title="目标与计划"
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
      <Tabs
        value={view}
        onChange={setView}
        items={[
          ['today', '今日安排'],
          ['week', '后续安排'],
          ['goals', '学习目标'],
          ['current', '预算内路径'],
          ['next', '后续候选'],
          ['history', '完成记录'],
        ]}
      />
      <div className="plan-workspace">
        {view === 'goals' ? (
          <>
            <Panel title="我的学习目标" caption="从想要理解的知识出发，给自己一个清晰的方向">
              {goals.length ? (
                goalPage.rows.map((g) => (
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
              <Pager {...goalPage} onChange={goalPage.setPage} label="项目标" />
            </Panel>
          </>
        ) : ['today', 'week', 'history'].includes(view) ? (
          <>
            <Panel title="我的学习安排" caption="完成状态是你的自我记录，不会直接提高知识掌握度">
              {items.length ? (
                <div className="personal-plan-list">
                  {itemPage.rows.map((item) => (
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
                          <span>
                            {item.estimated_minutes} 分钟
                            {item.completion_source === 'self_report'
                              ? ' · 自报完成'
                              : item.completion_source === 'event'
                                ? ' · 活动完成'
                                : ''}
                          </span>
                          <span>{item.scheduled_date || '自主安排'}</span>
                        </div>
                      </div>
                      <div className="plan-item-actions">
                        <Link
                          to={item.href || kindRoutes[item.kind] || '/practice'}
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
              <Pager {...itemPage} onChange={itemPage.setPage} label="项安排" />
            </Panel>
          </>
        ) : (
          <Panel
            title={
              view === 'current'
                ? `本次 ${query.data.recommendations?.[0]?.path_plan?.budget || 30} 分钟预算内路径`
                : '后续学习候选'
            }
            caption={query.data.explanation || '依据先修关系与近期学习证据推荐'}
          >
            <div className="plan-recommendations">
              {recPage.rows.map((r: Row, i: number) => (
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
                          estimated_minutes: r.estimated_minutes,
                          target: r.target,
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
            <Pager {...recPage} onChange={recPage.setPage} label="条建议" />
          </Panel>
        )}
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
                    <select
                      name="kind"
                      value={activityKind}
                      onChange={(e) => setActivityKind(e.target.value)}
                    >
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
                {['video', 'reading'].includes(activityKind) ? (
                  <label>
                    具体资源
                    <select name="resource_id" defaultValue={edit.target?.resource_id || ''}>
                      <option value="">按关联知识选择</option>
                      {resources.data
                        .filter((r) => r.kind === (activityKind === 'video' ? 'video' : 'document'))
                        .map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.title}
                          </option>
                        ))}
                    </select>
                  </label>
                ) : activityKind === 'experiment' ? (
                  <label>
                    具体实验
                    <select
                      name="experiment_id"
                      defaultValue={edit.target?.experiment_id || 'sort'}
                    >
                      {[
                        ['sort', '排序'],
                        ['tree', '二叉树'],
                        ['bfs', '广度优先'],
                        ['stack', '栈'],
                        ['queue', '队列'],
                        ['py-loop', 'Python循环'],
                        ['py-branch', 'Python条件'],
                        ['py-list', 'Python列表'],
                        ['py-function', 'Python函数'],
                      ].map(([id, title]) => (
                        <option key={id} value={id}>
                          {title}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <label>
                    具体题目
                    <select name="question_id" defaultValue={edit.target?.question_id || ''}>
                      <option value="">按关联知识选择</option>
                      {questions.data.map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.title}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {activityKind === 'video' ? (
                  <label>
                    开始时间（秒）
                    <input
                      type="number"
                      name="video_timestamp"
                      min={0}
                      defaultValue={edit.target?.video_timestamp || 0}
                    />
                  </label>
                ) : null}
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
