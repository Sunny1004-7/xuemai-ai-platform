import { Pager, usePage } from '../components/Workspace'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { CheckCheck, ClipboardList, Edit3, Send, Sparkles, Target, Users } from 'lucide-react'
import { CohortCharts } from '../components/LearningCharts'
import { AssignmentRow } from './Practice'
import { patch, percent, post, useApi } from '../api'
import type { Row } from '../api'
import {
  Button,
  Empty,
  LoadState,
  Modal,
  Panel,
  Pill,
  Progress,
  Title,
  dateLabel,
  useApp,
} from '../ui'

export function Analytics() {
  const { user, courseId, notify } = useApp()
  const [params] = useSearchParams()
  const [classId, setClassId] = useState('')
  const [view, setView] = useState(
    params.get('knowledge') ? 'intervention' : params.get('view') || 'matrix',
  )
  const classes = useApi<Row[]>(`/classes?course_id=${courseId}`, [])
  useEffect(() => setClassId(''), [courseId])
  const query = useApi<Row>(
    user.role === 'teacher'
      ? `/analytics?course_id=${courseId}${classId ? `&class_id=${classId}` : ''}`
      : null,
    {},
  )
  const questions = useApi<Row[]>(
    user.role === 'teacher' ? `/questions?course_id=${courseId}` : null,
    [],
  )
  const attempts = useApi<Row[]>(
    user.role === 'teacher' ? `/attempts?course_id=${courseId}` : null,
    [],
  )
  const [drill, setDrill] = useState<Row | null>(null)
  const evidence = useApi<Row>(
    drill
      ? `/analytics/evidence?course_id=${courseId}&student_id=${drill.student.id}&knowledge_id=${drill.node.id}`
      : null,
    {},
  )
  const [target, setTarget] = useState<Row | null>(null)
  const [review, setReview] = useState<Row | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [rubric, setRubric] = useState<Row | null>(null)
  const d = query.data,
    summary = d.summary || {},
    knowledge: Row[] = d.knowledge || [],
    students: Row[] = d.students || []
  const pending = attempts.data.filter((a) => String(a.review_status).startsWith('pending'))
  const studentPage = usePage<Row>(students, 49, 460)
  const knowledgePage = usePage<Row>(knowledge, 86, 410)
  const errorPage = usePage<Row>(d.error_distribution || [], 65, 440)
  const pendingPage = usePage<Row>(pending, 100, 440)
  const taskPage = usePage<Row>(d.assignments || [], 100, 420)
  if (user.role !== 'teacher') return <Empty>班级学情仅向课程教师开放。</Empty>
  async function publish(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const ids =
        target?.question_ids ||
        questions.data
          .filter((q) => q.knowledge_id === target?.id)
          .map((q) => q.id)
          .slice(0, 4)
      if (!ids.length) {
        notify('该知识点还没有题目，请先创建练习', true)
        return
      }
      await post('/assignments', {
        course_id: courseId,
        title: f.get('title'),
        description: f.get('description'),
        knowledge_id: target?.id,
        question_ids: ids,
        student_ids: selected,
      })
      notify('分层任务已发布给选定学生')
      setTarget(null)
      query.reload()
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function confirmReview(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      await patch(`/attempts/${review?.id}/review`, {
        score: Number(f.get('score')),
        feedback: f.get('feedback'),
      })
      setReview(null)
      attempts.reload()
      query.reload()
      notify('教师复核已完成，学情与错题记录已更新')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function aiReview() {
    if (!review) return
    setBusy(true)
    try {
      const r = await post('/ai/generate', {
        course_id: courseId,
        kind: 'rubric',
        question_id: review.question_id,
        answer: review.answer,
        prompt: '依据题目量规给出评分建议，结果仅供教师复核。',
      })
      setRubric(r.result)
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Title
        title="学情分析"
        subtitle="发现共同困难，安排分层任务，再用复测结果检验教学是否有效"
        action={
          <div className="button-row"><Link className="button secondary" to={`/teacher-ai?course=${courseId}${classId ? `&class=${classId}` : ''}`}>教学研讨</Link>
          <Button
            variant="secondary"
            onClick={() => {
              query.reload()
              attempts.reload()
            }}
          >
            刷新学习状态
          </Button>
          </div>
        }
      />
      <LoadState {...query} retry={query.reload} />
      <div className="stats-row">
        {[
          [Users, '课程学生', summary.student_count || 0],
          [Target, '平均掌握度', `${percent(summary.average_mastery)}%`],
          [ClipboardList, '累计作答', summary.attempt_count || 0],
          [CheckCheck, '客观题正确率', `${percent(summary.accuracy)}%`],
        ].map(([Icon, label, value], i) => {
          const I = Icon as typeof Users
          return (
            <div className="stat" key={i}>
              <span className={`stat-icon stat-${i}`}>
                <I size={21} />
              </span>
              <div>
                <span>{String(label)}</span>
                <strong>{String(value)}</strong>
              </div>
            </div>
          )
        })}
      </div>
      <div className="matrix-filters">
        <select
          aria-label="筛选教学班级"
          value={classId}
          onChange={(e) => setClassId(e.target.value)}
        >
          <option value="">课程全部班级</option>
          {classes.data.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="analytics-tabs" role="tablist" aria-label="学情工作区">
        {[
          ['matrix', '知识矩阵'],
          ['trends', '趋势表现'],
          ['intervention', '教学群组'],
          ['focus', '知识关注'],
          ['tasks', '干预跟踪'],
          ['students', '学生轨迹'],
          ['review', '作答复核'],
        ].map(([id, label]) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            aria-selected={view === id}
            aria-controls={`view-${id}`}
            onClick={() => setView(id)}
          >
            {label}
            {id === 'review' && pending.length ? <span>{pending.length}</span> : null}
          </button>
        ))}
      </div>
      <div id="view-matrix" role="tabpanel" aria-labelledby="tab-matrix" hidden={view !== 'matrix'}>
        <CohortCharts
          view="matrix"
          data={d}
          onCell={(node, student) => setDrill({ node, student })}
          onGroup={(g) => {
            setTarget({ id: g.knowledge_id, title: g.name, question_ids: g.question_ids })
            setSelected(g.student_ids)
          }}
        />
      </div>
      <div
        id="view-intervention"
        role="tabpanel"
        aria-labelledby="tab-intervention"
        hidden={view !== 'intervention'}
      >
        <CohortCharts
          view="groups"
          data={d}
          onCell={(node, student) => setDrill({ node, student })}
          onGroup={(g) => {
            setTarget({ id: g.knowledge_id, title: g.name, question_ids: g.question_ids })
            setSelected(g.student_ids)
          }}
        />
      </div>
      <div role="tabpanel" hidden={view !== 'focus'} className="analytics-layout">
        <Panel title="知识掌握与教学关注" caption="按知识点识别需要巩固的学生，直接形成教学行动">
          <div className="knowledge-analysis">
            {knowledgePage.rows.map((k) => (
              <div key={k.id} data-knowledge={k.id}>
                <div>
                  <h3>{k.title}</h3>
                  <span>{k.weak_students?.length || 0} 位学生需要关注</span>
                </div>
                <div>
                  <Progress
                    value={percent(k.average_mastery)}
                    color={
                      percent(k.average_mastery) < 40 ? 'var(--accent)' : 'var(--brand-primary)'
                    }
                  />
                  <strong>{percent(k.average_mastery)}%</strong>
                </div>
                <Button
                  variant="small ghost"
                  disabled={!k.weak_students?.length}
                  onClick={() => setDrill({ node: k, student: k.weak_students[0] })}
                >
                  查看证据
                </Button>
                <Button
                  variant="small secondary"
                  onClick={() => {
                    setTarget(k)
                    setSelected((k.weak_students || []).map((s: Row) => s.id))
                  }}
                >
                  <Send size={14} />
                  分层任务
                </Button>
              </div>
            ))}
          </div>
          <Pager {...knowledgePage} onChange={knowledgePage.setPage} label="个知识点" />
          {!knowledge.length ? <Empty>课程加入知识点与作答后，分析会在这里出现。</Empty> : null}
        </Panel>
        <Panel title="常见错因分布" caption="从错误类型寻找教学切入点">
          <div className="error-distribution">
            {errorPage.rows.map((e: Row, i: number) => (
              <div key={e.name}>
                <div>
                  <span>
                    <i
                      style={{
                        background: [
                          'var(--data)',
                          'var(--brand-primary)',
                          'var(--accent)',
                          'var(--brand-secondary)',
                        ][i % 4],
                      }}
                    />
                    {e.name}
                  </span>
                  <strong>{e.value} 次</strong>
                </div>
                <Progress
                  value={
                    (e.value /
                      Math.max(1, ...(d.error_distribution || []).map((r: Row) => r.value))) *
                    100
                  }
                  color={
                    [
                      'var(--data)',
                      'var(--brand-primary)',
                      'var(--accent)',
                      'var(--brand-secondary)',
                    ][i % 4]
                  }
                />
              </div>
            ))}
          </div>
          <Pager {...errorPage} onChange={errorPage.setPage} label="类错因" />
          {!d.error_distribution?.length ? <Empty>暂时没有已记录的错因。</Empty> : null}
        </Panel>
      </div>
      <div role="tabpanel" hidden={view !== 'tasks'}>
        <Panel title="教学干预跟踪">
          {taskPage.rows.map((a: Row) => (
            <AssignmentRow key={a.id} assignment={a} />
          ))}
          <Pager {...taskPage} onChange={taskPage.setPage} label="份任务" />
        </Panel>
      </div>
      <div role="tabpanel" hidden={view !== 'trends'}>
        <CohortCharts
          view="trends"
          data={d}
          onCell={(node, student) => setDrill({ node, student })}
          onGroup={() => {}}
        />
      </div>
      <div
        id="view-students"
        role="tabpanel"
        aria-labelledby="tab-students"
        hidden={view !== 'students'}
      >
        <Panel
          title="学生学习轨迹概览"
          caption="掌握度来自可解释的学习证据，观看时长不直接代表理解"
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>学生</th>
                  <th>学生编号</th>
                  <th>综合掌握</th>
                  <th>作答次数</th>
                  <th>正确率</th>
                  <th>教学建议</th>
                </tr>
              </thead>
              <tbody>
                {studentPage.rows.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <span className="table-person">
                        <i>{s.name.slice(0, 1)}</i>
                        {s.name}
                      </span>
                    </td>
                    <td>{s.id}</td>
                    <td>
                      <div className="table-progress">
                        <Progress value={percent(s.mastery)} />
                        <strong>{percent(s.mastery)}%</strong>
                      </div>
                    </td>
                    <td>{s.attempts || 0}</td>
                    <td>{percent(s.accuracy)}%</td>
                    <td>
                      <Pill tone={percent(s.mastery) < 40 ? 'amber' : 'green'}>
                        {percent(s.mastery) < 40
                          ? '关注先修知识与概念辨析'
                          : percent(s.mastery) < 75
                            ? '增加独立练习与复测'
                            : '尝试迁移与进阶应用'}
                      </Pill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager {...studentPage} onChange={studentPage.setPage} label="位学生" />
        </Panel>
      </div>
      <div id="view-review" role="tabpanel" aria-labelledby="tab-review" hidden={view !== 'review'}>
        <Panel
          title="主观题待复核"
          caption="AI 可给出量规建议，最终评分由教师确认"
          action={<Pill tone="amber">{pending.length} 待处理</Pill>}
        >
          {pending.length ? (
            <div className="pending-reviews">
              {pendingPage.rows.map((a) => (
                <div key={a.id}>
                  <span className="class-icon">
                    <Edit3 size={20} />
                  </span>
                  <div>
                    <h3>{a.student_name || `学生 ${a.student_id}`}</h3>
                    <p>
                      {questions.data.find((q) => q.id === a.question_id)?.title ||
                        a.title ||
                        '主观题作答'}
                    </p>
                    <small>{dateLabel(a.created_at)}</small>
                  </div>
                  <Button
                    variant="small secondary"
                    onClick={() => {
                      setReview(a)
                      setRubric(null)
                    }}
                  >
                    查看并复核
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <Empty>当前没有等待复核的主观题。</Empty>
          )}
          <Pager {...pendingPage} onChange={pendingPage.setPage} label="份作答" />
        </Panel>
      </div>
      {drill ? (
        <Modal title={`${drill.student.name} · ${drill.node.title}`} close={() => setDrill(null)}>
          <LoadState {...evidence} />
          <p>
            {evidence.data.state?.sufficiency} · 有效证据{' '}
            {Number(evidence.data.state?.effective_count || 0).toFixed(1)}
          </p>
          <div className="evidence-list">
            {(evidence.data.updates || []).map((e: Row) => (
              <article key={e.id}>
                <h3>{e.title}</h3>
                <p>
                  作答：{Array.isArray(e.answer) ? e.answer.join('、') : e.answer} · 提示{' '}
                  {e.hints_used} 次
                </p>
                <p>
                  {Math.round(e.before_value * 100)}% → {Math.round(e.after_value * 100)}% · 权重{' '}
                  {e.weight.toFixed(2)} · 独立性质量 {e.quality.toFixed(2)}
                </p>
                <small>
                  {dateLabel(e.created_at)} ·{' '}
                  {e.review_status === 'teacher_reviewed' ? '教师复核' : '确定性评分'}
                </small>
              </article>
            ))}
          </div>
          <Button
            onClick={() => {
              setTarget(drill.node)
              setSelected([drill.student.id])
              setDrill(null)
            }}
          >
            发布针对性任务
          </Button>
        </Modal>
      ) : null}
      {target ? (
        <Modal title={`分层学习 · ${target.title}`} close={() => setTarget(null)}>
          <form className="form-stack" onSubmit={publish}>
            <label>
              任务名称
              <input required name="title" defaultValue={`${target.title} · 针对性巩固`} />
            </label>
            <label>
              教学说明
              <textarea
                name="description"
                defaultValue={`请先复习${target.title}的概念，独立完成练习；若仍有困惑，从当前题目进入学习伙伴对话。`}
                rows={3}
              />
            </label>
            <fieldset>
              <legend>选择学生</legend>
              <div className="checkbox-list">
                {students.map((s) => (
                  <label key={s.id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(s.id)}
                      onChange={(e) =>
                        setSelected((v) =>
                          e.target.checked ? [...v, s.id] : v.filter((id) => id !== s.id),
                        )
                      }
                    />
                    {s.name}
                    <Pill>掌握度 {percent(s.mastery)}%</Pill>
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="mini-text muted">
              自动关联该知识点最多 4 道已有练习。若题目不足，请先维护题库。
            </p>
            <Button disabled={!selected.length || busy}>
              <Send size={16} />
              {busy ? '发布中…' : '发布分层任务'}
            </Button>
          </form>
        </Modal>
      ) : null}
      {review ? (
        <Modal title="主观作答与教师复核" close={() => setReview(null)}>
          <form className="form-stack" onSubmit={confirmReview}>
            <h3>{questions.data.find((q) => q.id === review.question_id)?.title}</h3>
            <div className="student-answer">
              <strong>{review.student_name || '学生'} 的作答</strong>
              <p>{Array.isArray(review.answer) ? review.answer.join('、') : review.answer}</p>
            </div>
            <Button type="button" variant="secondary" onClick={aiReview} disabled={busy}>
              <Sparkles size={16} />
              获取 AI 量规建议
            </Button>
            {rubric ? (
              <div className="rubric-advice">
                <Pill tone="amber">AI 建议 · 待教师确认</Pill>
                <p>{rubric.feedback}</p>
                {rubric.criteria?.map((c: Row, i: number) => (
                  <div key={i}>
                    <span>{c.name}</span>
                    <strong>
                      {c.score}/{c.max_score}
                    </strong>
                  </div>
                ))}
              </div>
            ) : null}
            <label>
              最终得分（0–100）
              <input
                name="score"
                type="number"
                required
                min={0}
                max={100}
                key={rubric?.score ?? 'score'}
                defaultValue={rubric?.score ?? 70}
              />
            </label>
            <label>
              教师评语
              <textarea
                required
                name="feedback"
                rows={3}
                key={rubric?.feedback || 'feedback'}
                defaultValue={rubric?.feedback || ''}
              />
            </label>
            <Button disabled={busy}>
              <CheckCheck size={16} />
              确认复核并更新学情
            </Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
