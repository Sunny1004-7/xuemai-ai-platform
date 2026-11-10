import { useState } from 'react'
import { PersonalCharts } from '../components/LearningCharts'
import { Link } from 'react-router-dom'
import { ArrowRight, Plus } from 'lucide-react'
import { post, percent, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Pill, Progress, Title, useApp, dateLabel } from '../ui'

function CourseArt({ variant = 0 }: { variant?: number }) {
  return (
    <div className={`course-art art-${variant % 2}`} aria-hidden="true">
      <svg viewBox="0 0 260 110">
        <path
          d="M25 70Q75 0 130 55T235 35M25 70Q85 110 130 55T235 85"
          fill="none"
          stroke="currentColor"
        />
        {[
          [25, 70],
          [80, 32],
          [130, 55],
          [185, 47],
          [235, 35],
        ].map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={i === 2 ? 16 : 8}
            fill="var(--surface-raised)"
            stroke="currentColor"
          />
        ))}
      </svg>
    </div>
  )
}
export function Dashboard() {
  const { user, courseId, setCourseId } = useApp()
  const query = useApi<Row>('/dashboard', {})
  const teacher = user.role === 'teacher'
  const analysis = useApi<Row>(teacher ? `/analytics?course_id=${courseId}` : '', {})
  const attempts = useApi<Row[]>(teacher ? `/attempts?course_id=${courseId}` : '', [])
  const insights = useApi<Row>(!teacher ? `/learning/insights?course_id=${courseId}` : null, {})
  const d = query.data
  const recommendations: Row[] = d.recommendations || []
  const tasks: Row[] = d.assignments || []
  const next = recommendations[0]
  const courses: Row[] = d.courses || []
  const pending = attempts.data.filter((a) => a.review_status === 'pending_review')
  const weak: Row[] = (analysis.data.knowledge || [])
    .filter((k: Row) => k.weak_students.length)
    .slice(0, 5)
  const open = (r: Row) => {
    if (r.course_id) setCourseId(r.course_id)
  }
  return (
    <>
      <Title title={teacher ? '教学工作台' : '学习概览'} />
      <LoadState {...query} retry={query.reload} />
      {!teacher ? <PersonalCharts data={insights.data} courseId={courseId}/> : null}
      {teacher ? (
        <div className="teacher-desk">
          <div>
            <section className="teacher-command">
              <div>
                <h2>{courses.find((c) => c.id === courseId)?.title || '当前课程'}</h2>
                <p className="muted">
                  {analysis.data.summary?.student_count || 0} 位学生 ·{' '}
                  {tasks.filter((t) => t.course_id === courseId).length} 项教学任务
                </p>
              </div>
              <Link className="button" to="/practice">
                发布作业
                <ArrowRight size={16} />
              </Link>
            </section>
            <div className="teacher-shortcuts">
              <Link className="button secondary" to="/manage">
                课程与班级
              </Link>
              <Link className="button secondary" to="/resources">
                备课与资料
              </Link>
              <Link className="button secondary" to="/graph">
                编辑知识网络
              </Link>
              <Link className="button secondary" to="/classroom">
                课堂互动
              </Link>
            </div>
            <section className="desk-section">
              <header>
                <h2>需要关注的知识</h2>
                <Link to="/analytics">查看证据</Link>
              </header>
              <table className="teacher-ledger">
                <thead>
                  <tr>
                    <th>知识点</th>
                    <th>需关注</th>
                    <th>掌握估计</th>
                    <th>教学行动</th>
                  </tr>
                </thead>
                <tbody>
                  {weak.map((k) => (
                    <tr key={k.id}>
                      <td>{k.title}</td>
                      <td>{k.weak_students.length} 人</td>
                      <td>{percent(k.average_mastery)}%</td>
                      <td>
                        <Link to={`/analytics?knowledge=${k.id}`}>查看与安排</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!weak.length ? <Empty>暂无需要关注的知识点</Empty> : null}
            </section>
            <section className="desk-section">
              <header>
                <h2>课程</h2>
                <Link to="/manage">管理</Link>
              </header>
              <div className="course-shelf">
                {courses.map((c) => (
                  <Link to="/manage" key={c.id} onClick={() => setCourseId(c.id)}>
                    <small>{c.code}</small>
                    <strong>{c.title}</strong>
                    <span>{c.knowledge_count} 个知识点</span>
                    <Progress value={percent(c.progress)} />
                  </Link>
                ))}
              </div>
            </section>
          </div>
          <aside className="desk-side">
            <h2>
              待复核 <span>{pending.length}</span>
            </h2>
            {pending.slice(0, 3).map((a) => (
              <Link className="desk-task" to="/analytics" key={a.id}>
                <strong>
                  {a.student_name} · {a.title}
                </strong>
                <small>主观作答 · 等待复核</small>
              </Link>
            ))}
            {!pending.length ? <p className="muted">当前作答已处理</p> : null}
            <section className="desk-section">
              <header>
                <h2>近期学习</h2>
              </header>
              {(d.recent_events || []).slice(0, 5).map((e: Row) => (
                <div className="compact-evidence" key={e.id}>
                  <div>
                    <strong>{e.student_name}</strong>
                    <p>{e.knowledge_title || '课程活动'}</p>
                  </div>
                  <small>{dateLabel(e.created_at)}</small>
                </div>
              ))}
            </section>
            <Link className="button secondary" to="/analytics">
              跟踪教学任务
            </Link>
          </aside>
        </div>
      ) : (
        <div className="study-desk">
          <div>
            <section className="next-study">
              <div className="study-meta">
                <span>
                  {new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })}
                </span>
                <span>下一项学习</span>
                {next ? <span>预计 {next.estimated_minutes || 15} 分钟</span> : null}
              </div>
              <h2>{next?.title || '开始课程学习'}</h2>
              <p>{next?.reason || '选择知识点，完成一次练习，建立你的学习起点。'}</p>
              <Link
                className="button"
                onClick={() => next && open(next)}
                to={next?.href || '/graph'}
              >
                开始今日学习
                <ArrowRight size={17} />
              </Link>
              {next?.steps ? (
                <div className="study-sequence">
                  {next.steps.map((step: Row, i: number) => (
                    <Link key={i} to={step.href} onClick={() => open(next)}>
                      {step.title}
                    </Link>
                  ))}
                </div>
              ) : null}
            </section>
            <section className="desk-section">
              <header>
                <h2>我的课程</h2>
                <Link to="/courses">全部课程</Link>
              </header>
              <div className="course-shelf">
                {courses.map((c, i) => (
                  <Link key={c.id} to="/graph" onClick={() => setCourseId(c.id)}>
                    <CourseArt variant={i} />
                    <strong>{c.title}</strong>
                    <small>
                      {c.knowledge_count} 个知识点 · 掌握估计 {percent(c.progress)}%
                    </small>
                    <Progress value={percent(c.progress)} />
                  </Link>
                ))}
              </div>
            </section>
            <section className="desk-section">
              <header>
                <h2>接下来</h2>
                <Link to="/plan">学习计划</Link>
              </header>
              {recommendations.slice(1, 4).map((r) => (
                <Link className="desk-task" key={r.id} to={r.href} onClick={() => open(r)}>
                  <strong>{r.title}</strong>
                  <small>{r.reason}</small>
                </Link>
              ))}
            </section>
          </div>
          <aside className="desk-side">
            <h2>课程任务</h2>
            {tasks.slice(0, 4).map((t) => (
              <Link
                to={`/practice?assignment=${t.id}`}
                onClick={() => open(t)}
                className="desk-task"
                key={t.id}
              >
                <strong>{t.title}</strong>
                <small>
                  {t.question_ids?.length} 道题 ·{' '}
                  {t.completed ? '已完成' : t.due_at ? dateLabel(t.due_at) : '待完成'}
                </small>
              </Link>
            ))}
            {!tasks.length ? (
              <Link className="desk-task" to="/practice">
                选择一次自主练习
              </Link>
            ) : null}
            <section className="desk-section">
              <header>
                <h2>最近学习</h2>
              </header>
              {(d.recent_events || []).slice(0, 4).map((e: Row) => (
                <Link
                  to={e.knowledge_id ? `/graph?knowledge=${e.knowledge_id}` : '/graph'}
                  onClick={() => open(e)}
                  className="desk-task"
                  key={e.id}
                >
                  <strong>{e.knowledge_title || '课程活动'}</strong>
                  <small>{dateLabel(e.created_at)}</small>
                </Link>
              ))}
            </section>
            <Link className="button secondary" to="/tutor">
              打开学习伙伴
            </Link>
          </aside>
        </div>
      )}
    </>
  )
}

export function Courses() {
  const { setCourseId, notify } = useApp()
  const query = useApi<Row[]>('/courses', [])
  const [join, setJoin] = useState(false)
  const [code, setCode] = useState('')
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await post('/classes/join', { join_code: code })
      notify('已加入班级，课程已加入学习空间')
      setJoin(false)
      query.reload()
      window.dispatchEvent(new Event('courses-changed'))
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  return (
    <>
      <Title
        title="我的课程"
        subtitle="不同的课程，同一条不断生长的学习脉络"
        action={
          <Button onClick={() => setJoin(true)}>
            <Plus size={17} />
            加入班级
          </Button>
        }
      />
      <LoadState {...query} retry={query.reload} />
      <div className="course-grid full">
        {query.data.map((c, i) => (
          <Link to="/video" className="course-card" key={c.id} onClick={() => setCourseId(c.id)}>
            <CourseArt variant={i} />
            <div className="course-info">
              <Pill tone="blue">{c.code || '课程'}</Pill>
              <h3>{c.title}</h3>
              <p>{c.description}</p>
              <div className="progress-label">
                <span>{c.knowledge_count || 0} 个知识点</span>
                <strong>{percent(c.progress)}%</strong>
              </div>
              <Progress value={percent(c.progress)} />
              <div className="course-bottom">
                <span>{c.teacher_name}</span>
                <span>
                  进入课程
                  <ArrowRight size={15} />
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>
      {join ? (
        <Modal title="加入课程班级" close={() => setJoin(false)}>
          <form onSubmit={submit} className="form-stack">
            <p className="muted">输入教师提供的班级邀请码，加入后即可访问课程、资料与学习任务。</p>
            <label>
              班级邀请码
              <input
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="例如 XM2026"
              />
            </label>
            <Button type="submit">加入班级</Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
