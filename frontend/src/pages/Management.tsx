import { Pager, Tabs, usePage } from '../components/Workspace'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  ClipboardList,
  Edit3,
  FileText,
  Layers3,
  Plus,
  Save,
  Users,
} from 'lucide-react'
import { patch, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'

export function Management() {
  const { user, courseId, setCourseId, notify } = useApp()
  const courses = useApi<Row[]>('/courses', [])
  const course = useApi<Row>(`/courses/${courseId}`, {})
  const classes = useApi<Row[]>(`/classes?course_id=${courseId}`, [])
  const [view, setView] = useState('info')
  const chapters = usePage<Row>(course.data.chapters || [], 100, 350)
  const [memberClass, setMemberClass] = useState(0)
  const selected = classes.data.find((c) => c.id === memberClass) || classes.data[0]
  const members = usePage<Row>(selected?.students || [], 45, 420)
  const [form, setForm] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedClass, setSelectedClass] = useState(0)
  if (user.role !== 'teacher') return <Empty>课程管理仅向课程教师开放。</Empty>
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      if (form === 'course') {
        const c = await post('/courses', {
          title: f.get('title'),
          description: f.get('description'),
          code: f.get('code'),
        })
        courses.reload()
        setCourseId(c.id)
        window.dispatchEvent(new Event('courses-changed'))
        notify('课程已创建，接下来可以组织章节与班级')
      }
      if (form === 'edit') {
        await patch(`/courses/${courseId}`, {
          title: f.get('title'),
          description: f.get('description'),
        })
        courses.reload()
        course.reload()
        window.dispatchEvent(new Event('courses-changed'))
        notify('课程信息已保存')
      }
      if (form === 'class') {
        await post('/classes', { course_id: courseId, name: f.get('name') })
        classes.reload()
        notify('班级已创建，可分享邀请码给学生')
      }
      if (form === 'chapter') {
        await post(`/courses/${courseId}/chapters`, { title: f.get('title') })
        course.reload()
        notify('章节已创建')
      }
      if (form === 'member') {
        await post(`/classes/${selectedClass}/members`, { student_id: Number(f.get('student_id')) })
        classes.reload()
        notify('学生已加入班级')
      }
      setForm('')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Title
        title="课程与班级"
        subtitle="课程、章节、班级与内容在同一处管理，学生通过班级获得学习访问权"
        action={
          <Button onClick={() => setForm('course')}>
            <Plus size={17} />
            创建课程
          </Button>
        }
      />
      <Tabs
        value={view}
        onChange={setView}
        items={[
          ['info', '课程信息'],
          ['chapters', '章节内容'],
          ['classes', '授课班级'],
        ]}
      />
      <LoadState {...course} retry={course.reload} />
      <div className="management-layout">
        {view === 'info' ? (
          <>
            <Panel
              title="课程信息"
              action={
                <Button variant="small secondary" onClick={() => setForm('edit')}>
                  <Edit3 size={14} />
                  编辑
                </Button>
              }
            >
              <div className="course-summary">
                <div className="course-large-icon">
                  <BookOpen size={34} />
                </div>
                <div>
                  <Pill tone="blue">{course.data.code || '原创教学课程'}</Pill>
                  <h2>{course.data.title}</h2>
                  <p>{course.data.description}</p>
                  <span className="muted">
                    任课教师：{user.name}　·　{course.data.knowledge_points?.length || 0} 个知识点
                  </span>
                </div>
              </div>
            </Panel>
          </>
        ) : view === 'chapters' ? (
          <>
            <Panel
              title="章节与内容组织"
              caption="先搭建章节结构，再将知识点、视频和练习关联起来"
              action={
                <Button variant="small secondary" onClick={() => setForm('chapter')}>
                  <Plus size={14} />
                  新增章节
                </Button>
              }
            >
              <div className="chapter-list">
                {chapters.rows.map((c: Row, i: number) => (
                  <div key={c.id}>
                    <span className="chapter-number">{String(i + 1).padStart(2, '0')}</span>
                    <div>
                      <h3>{c.title}</h3>
                      <p>
                        {course.data.knowledge_points
                          ?.filter((n: Row) => n.chapter_id === c.id)
                          .map((n: Row) => n.title)
                          .join('、') || '等待添加知识点'}
                      </p>
                    </div>
                    <Link to="/graph" className="text-link">
                      管理知识
                      <ChevronRight size={15} />
                    </Link>
                  </div>
                ))}
              </div>
              {!course.data.chapters?.length ? <Empty>添加章节，开始组织课程内容。</Empty> : null}
              <Pager {...chapters} onChange={chapters.setPage} label="章" />
              <div className="course-shortcuts">
                <Link to="/graph">
                  <Layers3 size={19} />
                  组织知识图谱
                  <ArrowRight size={15} />
                </Link>
                <Link to="/resources">
                  <FileText size={19} />
                  管理教学资料
                  <ArrowRight size={15} />
                </Link>
                <Link to="/practice">
                  <ClipboardList size={19} />
                  编写习题作业
                  <ArrowRight size={15} />
                </Link>
              </div>
            </Panel>
          </>
        ) : (
          <Panel
            title="授课班级"
            caption="学生加入后，课程内容与任务立即可见"
            action={
              <Button variant="small secondary" onClick={() => setForm('class')}>
                <Plus size={14} />
                新建班级
              </Button>
            }
          >
            <LoadState {...classes} retry={classes.reload} />
            <select
              aria-label="选择授课班级"
              value={selected?.id || ''}
              onChange={(e) => setMemberClass(Number(e.target.value))}
            >
              {classes.data.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {(selected ? [selected] : []).map((c) => (
              <div className="class-card" key={c.id}>
                <div className="class-card-heading">
                  <span className="class-icon">
                    <Users size={23} />
                  </span>
                  <div>
                    <h3>{c.name}</h3>
                    <span>{c.students?.length || 0} 位学生</span>
                  </div>
                </div>
                <div className="join-code">
                  <span>班级邀请码</span>
                  <strong>{c.join_code}</strong>
                  <button
                    onClick={() => {
                      navigator.clipboard
                        ?.writeText(c.join_code)
                        .then(() => notify('邀请码已复制'))
                        .catch(() => notify(`邀请码：${c.join_code}`))
                    }}
                  >
                    复制
                  </button>
                </div>
                <div className="student-roster">
                  {members.rows.map((s: Row) => (
                    <span key={s.id}>
                      <i>{s.name.slice(0, 1)}</i>
                      {s.name}
                    </span>
                  ))}
                </div>
                <Pager {...members} onChange={members.setPage} label="位学生" />
                <Button
                  variant="ghost small"
                  onClick={() => {
                    setSelectedClass(c.id)
                    setForm('member')
                  }}
                >
                  <Plus size={14} />
                  添加已有学生
                </Button>
              </div>
            ))}
            {!classes.data.length && !classes.loading ? (
              <Empty>创建班级后分享邀请码给学生。</Empty>
            ) : null}
          </Panel>
        )}
      </div>
      {form ? (
        <Modal
          title={
            {
              course: '创建教学课程',
              edit: '编辑课程信息',
              class: '创建授课班级',
              chapter: '添加课程章节',
              member: '添加班级学生',
            }[form] || '编辑'
          }
          close={() => setForm('')}
        >
          <form className="form-stack" onSubmit={save}>
            {form === 'class' ? (
              <label>
                班级名称
                <input required name="name" placeholder="例如：计算机 2026 级 1 班" />
              </label>
            ) : form === 'member' ? (
              <>
                <p className="muted">输入已存在的学生编号。演示学生编号可从学情页查看。</p>
                <label>
                  学生编号
                  <input type="number" min={1} required name="student_id" />
                </label>
              </>
            ) : (
              <label>
                {form === 'chapter' ? '章节名称' : '课程名称'}
                <input
                  required
                  name="title"
                  defaultValue={form === 'edit' ? course.data.title : ''}
                />
              </label>
            )}
            {form === 'course' ? (
              <label>
                课程代码
                <input name="code" placeholder="例如 CS201" />
              </label>
            ) : null}
            {form === 'course' || form === 'edit' ? (
              <label>
                课程介绍
                <textarea
                  name="description"
                  rows={4}
                  defaultValue={form === 'edit' ? course.data.description : ''}
                />
              </label>
            ) : null}
            <Button type="submit" disabled={busy}>
              <Save size={16} />
              {busy ? '保存中…' : '保存'}
            </Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
