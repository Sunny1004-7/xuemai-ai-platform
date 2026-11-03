import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCheck,
  ChevronRight,
  ClipboardList,
  Download,
  Edit3,
  FileText,
  Layers3,
  MessageCircle,
  Plus,
  Save,
  Send,
  Sparkles,
  Target,
  Trash2,
  Upload,
  Users,
  Video,
} from 'lucide-react'
import { api, patch, percent, post, useApi } from '../api'
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

export function Management() {
  const { user, courseId, setCourseId, notify } = useApp()
  const courses = useApi<Row[]>('/courses', [])
  const course = useApi<Row>(`/courses/${courseId}`, {})
  const classes = useApi<Row[]>(`/classes?course_id=${courseId}`, [])
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
        title="组织好课程，连接好师生"
        subtitle="课程、章节、班级与内容在同一处管理，学生通过班级获得学习访问权"
        action={
          <Button onClick={() => setForm('course')}>
            <Plus size={17} />
            创建课程
          </Button>
        }
      />
      <div className="management-course-tabs">
        {courses.data.map((c) => (
          <button
            key={c.id}
            className={courseId === c.id ? 'active' : ''}
            onClick={() => setCourseId(c.id)}
          >
            <BookOpen size={18} />
            <span>
              {c.title}
              <small>{c.code || `课程 ${c.id}`}</small>
            </span>
            <ChevronRight size={17} />
          </button>
        ))}
      </div>
      <LoadState {...course} retry={course.reload} />
      <div className="management-layout">
        <div>
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
              {course.data.chapters?.map((c: Row, i: number) => (
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
        </div>
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
          {classes.data.map((c) => (
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
                {c.students?.map((s: Row) => (
                  <span key={s.id}>
                    <i>{s.name.slice(0, 1)}</i>
                    {s.name}
                  </span>
                ))}
              </div>
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

export function Resources() {
  const { user, courseId, notify } = useApp()
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('all')
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const [editing, setEditing] = useState<Row | null>(null)
  const [preview, setPreview] = useState<Row | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [lesson, setLesson] = useState(false)
  const teacher = user.role === 'teacher'
  const list = resources.data.filter(
    (r) =>
      (kind === 'all' || r.kind === kind) &&
      (!search || `${r.title} ${r.content}`.includes(search)),
  )
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const body = {
        course_id: courseId,
        title: f.get('title'),
        kind: f.get('kind'),
        content: f.get('content'),
        knowledge_id: Number(f.get('knowledge_id')) || null,
        url: f.get('url') || '',
        metadata: editing?.metadata || {},
      }
      if (editing?.id) await patch(`/resources/${editing.id}`, body)
      else await post('/resources', body)
      notify('资料已保存，版本记录与课程检索同步更新')
      resources.reload()
      setEditing(null)
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    f.append('course_id', String(courseId))
    setBusy(true)
    try {
      await api('/resources/upload', { method: 'POST', body: f })
      notify('文件已上传并解析为课程资源')
      resources.reload()
      setUploading(false)
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function generateLesson(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const response = await post('/ai/generate', {
        course_id: courseId,
        kind: 'lesson',
        knowledge_id: Number(f.get('knowledge_id')) || undefined,
        prompt: f.get('prompt'),
      })
      const r = response.result
      const text = [
        `教学目标\n${(r.objectives || []).map((s: string) => `• ${s}`).join('\n')}`,
        `先修知识\n${(r.prerequisites || []).join('、')}`,
        `教学过程\n${(r.steps || []).map((s: string, i: number) => `${i + 1}. ${s}`).join('\n')}`,
        `例题与活动\n${(r.examples || []).join('\n')}`,
        `理解检查\n${typeof r.assessment === 'string' ? r.assessment : JSON.stringify(r.assessment)}`,
      ].join('\n\n')
      setEditing({
        title: r.title || '教学方案草稿',
        kind: 'lesson_plan',
        content: text,
        knowledge_id: Number(f.get('knowledge_id')) || undefined,
        ai_draft: true,
      })
      setLesson(false)
      notify('教学草稿已生成，编辑并确认后保存到课程')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Title
        title={teacher ? '让教学准备，更有章法' : '把课程资料，放在手边'}
        subtitle={
          teacher
            ? '从资料检索到可编辑教案，把 AI 的建议变成经过审核的教学内容'
            : '课程讲义、学习材料与知识片段，同一处随时查阅'
        }
        action={
          teacher ? (
            <div className="button-row">
              <Button variant="secondary" onClick={() => setUploading(true)}>
                <Upload size={16} />
                上传资料或视频
              </Button>
              <Button variant="secondary" onClick={() => setEditing({ kind: 'document' })}>
                <Plus size={16} />
                新建资料
              </Button>
              <Button onClick={() => setLesson(true)}>
                <Sparkles size={16} />
                AI 备课
              </Button>
            </div>
          ) : undefined
        }
      />
      {teacher ? (
        <section className="resource-hero">
          <span className="ai-welcome-icon">
            <Sparkles size={27} />
          </span>
          <div>
            <h2>把时间留给教学本身。</h2>
            <p>基于课程知识与已有资料生成教案草稿，目标、步骤和检查题都可逐项修改。</p>
          </div>
          <Button variant="secondary" onClick={() => setLesson(true)}>
            准备下一堂课
            <ArrowRight size={16} />
          </Button>
        </section>
      ) : null}
      <div className="resource-toolbar">
        <div className="segmented">
          {[
            ['all', '全部资料'],
            ['document', '课程讲义'],
            ['lesson_plan', '教学方案'],
            ['video', '教学视频'],
          ].map(([value, label]) => (
            <button
              key={value}
              className={kind === value ? 'active' : ''}
              onClick={() => setKind(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          className="search-field"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索标题与正文…"
          aria-label="搜索课程资料"
        />
      </div>
      <LoadState {...resources} retry={resources.reload} />
      <div className="resource-grid">
        {list.map((r) => (
          <article className="resource-card" key={r.id}>
            <div className={`resource-kind-icon ${r.kind}`}>
              {r.kind === 'video' ? (
                <Video size={25} />
              ) : r.kind === 'lesson_plan' ? (
                <Sparkles size={25} />
              ) : (
                <FileText size={25} />
              )}
            </div>
            <Pill tone={r.kind === 'lesson_plan' ? 'purple' : 'blue'}>
              {r.kind === 'video' ? '视频资源' : r.kind === 'lesson_plan' ? '教学方案' : '课程资料'}
            </Pill>
            <h3>{r.title}</h3>
            <p>{r.content?.slice(0, 120) || '打开查看资源内容与课程关联。'}</p>
            <div className="resource-card-meta">
              <span>
                {graph.data.nodes?.find((n: Row) => n.id === r.knowledge_id)?.title ||
                  '课程通用资料'}
              </span>
              <span>版本 {r.version || 1}</span>
            </div>
            <div className="resource-card-actions">
              <Button variant="small secondary" onClick={() => setPreview(r)}>
                查看内容
                <ArrowRight size={14} />
              </Button>
              {teacher ? (
                <>
                  <Button
                    variant="icon ghost"
                    aria-label={`编辑${r.title}`}
                    onClick={() => setEditing(r)}
                  >
                    <Edit3 size={15} />
                  </Button>
                  <Button
                    variant="icon ghost"
                    aria-label={`删除${r.title}`}
                    onClick={async () => {
                      if (!confirm(`删除资料「${r.title}」？`)) return
                      try {
                        await api(`/resources/${r.id}`, { method: 'DELETE' })
                        resources.reload()
                        notify('资料已删除')
                      } catch (e) {
                        notify((e as Error).message, true)
                      }
                    }}
                  >
                    <Trash2 size={15} />
                  </Button>
                </>
              ) : null}
            </div>
          </article>
        ))}
      </div>
      {!list.length && !resources.loading ? (
        <Panel>
          <Empty>没有找到对应的资料，试试其他筛选条件。</Empty>
        </Panel>
      ) : null}
      {editing ? (
        <Modal
          title={
            editing.ai_draft ? '编辑并审核教学草稿' : editing.id ? '编辑课程资料' : '新建课程资料'
          }
          close={() => setEditing(null)}
        >
          <form className="form-stack" onSubmit={save}>
            {editing.ai_draft ? <Pill tone="amber">AI 生成草稿 · 教师审核后保存</Pill> : null}
            <label>
              资料标题
              <input name="title" required defaultValue={editing.title} />
            </label>
            <div className="form-columns">
              <label>
                资源类型
                <select name="kind" defaultValue={editing.kind || 'document'}>
                  <option value="document">课程讲义</option>
                  <option value="lesson_plan">教学方案</option>
                  <option value="video">视频资源</option>
                  <option value="experiment">交互实验</option>
                </select>
              </label>
              <label>
                关联知识点
                <select name="knowledge_id" defaultValue={editing.knowledge_id || ''}>
                  <option value="">课程通用</option>
                  {graph.data.nodes?.map((n: Row) => (
                    <option key={n.id} value={n.id}>
                      {n.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              正文内容
              <textarea name="content" rows={12} defaultValue={editing.content} />
            </label>
            <label>
              资源地址（可选）
              <input name="url" defaultValue={editing.url} placeholder="本地资源地址或 https://…" />
            </label>
            <Button disabled={busy}>
              <Save size={16} />
              {busy ? '保存中…' : '审核并保存资料'}
            </Button>
          </form>
        </Modal>
      ) : null}
      {uploading ? (
        <Modal title="上传教学资料或视频" close={() => setUploading(false)}>
          <form className="form-stack" onSubmit={upload}>
            <p className="muted">PDF 与文本将解析为可检索的课程资料；视频作为可播放资源保存。</p>
            <label>
              资料标题
              <input name="title" required />
            </label>
            <label>
              关联知识点
              <select name="knowledge_id" defaultValue="">
                <option value="">课程通用</option>
                {graph.data.nodes?.map((n: Row) => (
                  <option key={n.id} value={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="upload-zone">
              <Upload size={28} />
              选择 PDF、Markdown、文本或 MP4 文件
              <input type="file" name="file" required accept=".pdf,.txt,.md,.mp4,.webm" />
            </label>
            <Button disabled={busy}>
              <Upload size={16} />
              {busy ? '正在上传与解析…' : '上传并加入课程'}
            </Button>
          </form>
        </Modal>
      ) : null}
      {lesson ? (
        <Modal title="AI 辅助教学准备" close={() => setLesson(false)}>
          <form className="form-stack" onSubmit={generateLesson}>
            <p className="muted">
              结合知识点与课程资料，生成目标、先修知识、教学步骤、例题和理解检查。结果为待审核草稿。
            </p>
            <label>
              本课知识点
              <select name="knowledge_id" required>
                <option value="">请选择</option>
                {graph.data.nodes?.map((n: Row) => (
                  <option value={n.id} key={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              教学意图
              <textarea
                name="prompt"
                required
                rows={4}
                placeholder="例如：面向初学者，准备 45 分钟的队列课程，结合生活情境讲解先进先出，并安排一个理解检查。"
              />
            </label>
            <Button disabled={busy}>
              <Sparkles size={16} />
              {busy ? '正在组织教学草稿…' : '生成可编辑草稿'}
            </Button>
          </form>
        </Modal>
      ) : null}
      {preview ? (
        <Modal title={preview.title} close={() => setPreview(null)}>
          <div className="resource-preview">
            <Pill tone="blue">版本 {preview.version || 1}</Pill>
            <div className="resource-document">{preview.content || '此资源没有文本正文。'}</div>
            {preview.kind === 'video' ? (
              <Link to={`/video?resource=${preview.id}`} className="button">
                打开视频学习
                <ArrowRight size={16} />
              </Link>
            ) : preview.url ? (
              <a className="button secondary" href={preview.url} target="_blank" rel="noreferrer">
                <Download size={16} />
                打开原始资源
              </a>
            ) : null}
          </div>
        </Modal>
      ) : null}
    </>
  )
}

export function Analytics() {
  const { user, courseId, notify } = useApp()
  const query = useApi<Row>(user.role === 'teacher' ? `/analytics?course_id=${courseId}` : null, {})
  const questions = useApi<Row[]>(
    user.role === 'teacher' ? `/questions?course_id=${courseId}` : null,
    [],
  )
  const attempts = useApi<Row[]>(
    user.role === 'teacher' ? `/attempts?course_id=${courseId}` : null,
    [],
  )
  const [target, setTarget] = useState<Row | null>(null)
  const [review, setReview] = useState<Row | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [rubric, setRubric] = useState<Row | null>(null)
  if (user.role !== 'teacher') return <Empty>班级学情仅向课程教师开放。</Empty>
  const d = query.data,
    summary = d.summary || {},
    knowledge: Row[] = d.knowledge || [],
    students: Row[] = d.students || []
  const pending = attempts.data.filter((a) => String(a.review_status).startsWith('pending'))
  async function publish(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      const ids = questions.data
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
        title="从学习证据，走向精准教学"
        subtitle="发现共同困难，安排分层任务，再用复测结果检验教学是否有效"
        action={
          <Button
            variant="secondary"
            onClick={() => {
              query.reload()
              attempts.reload()
            }}
          >
            刷新学习状态
          </Button>
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
      <div className="analytics-layout">
        <Panel title="知识掌握与教学关注" caption="按知识点识别需要巩固的学生，直接形成教学行动">
          <div className="knowledge-analysis">
            {knowledge.map((k) => (
              <div key={k.id}>
                <div>
                  <h3>{k.title}</h3>
                  <span>{k.weak_students?.length || 0} 位学生需要关注</span>
                </div>
                <div>
                  <Progress
                    value={percent(k.average_mastery)}
                    color={percent(k.average_mastery) < 40 ? '#c8944a' : '#369c88'}
                  />
                  <strong>{percent(k.average_mastery)}%</strong>
                </div>
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
          {!knowledge.length ? <Empty>课程加入知识点与作答后，分析会在这里出现。</Empty> : null}
        </Panel>
        <Panel title="常见错因分布" caption="从错误类型寻找教学切入点">
          <div className="error-distribution">
            {(d.error_distribution || []).map((e: Row, i: number) => (
              <div key={e.name}>
                <div>
                  <span>
                    <i
                      style={{ background: ['#6784dc', '#4caa96', '#d6a45a', '#9d82c7'][i % 4] }}
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
                  color={['#6784dc', '#4caa96', '#d6a45a', '#9d82c7'][i % 4]}
                />
              </div>
            ))}
          </div>
          {!d.error_distribution?.length ? <Empty>暂时没有已记录的错因。</Empty> : null}
        </Panel>
      </div>
      <Panel title="学生学习轨迹概览" caption="掌握度来自可解释的学习证据，观看时长不直接代表理解">
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
              {students.map((s) => (
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
      </Panel>
      <Panel
        title="主观题待复核"
        caption="AI 可给出量规建议，最终评分由教师确认"
        action={<Pill tone="amber">{pending.length} 待处理</Pill>}
      >
        {pending.length ? (
          <div className="pending-reviews">
            {pending.map((a) => (
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
      </Panel>
      {target ? (
        <Modal title={`分层学习 · ${target.title}`} close={() => setTarget(null)}>
          <form className="form-stack" onSubmit={publish}>
            <p className="muted">
              根据知识掌握与错因安排学习任务。发布后学生会收到关联练习，完成情况会重新进入学情分析。
            </p>
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

export function Classroom() {
  const { user, courseId, notify } = useApp()
  const activities = useApi<Row[]>(`/classroom?course_id=${courseId}`, [])
  const [create, setCreate] = useState(false)
  const [busy, setBusy] = useState(false)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const teacher = user.role === 'teacher'
  useEffect(() => {
    const id = setInterval(activities.reload, 7000)
    return () => clearInterval(id)
  }, [activities.reload])
  async function publish(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      await post('/classroom', {
        course_id: courseId,
        title: f.get('title'),
        prompt: f.get('prompt'),
        kind: f.get('kind'),
      })
      notify('课堂互动已发起，学生端将同步收到')
      activities.reload()
      setCreate(false)
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function respond(id: number) {
    if (!answers[id]?.trim()) return
    setBusy(true)
    try {
      await post(`/classroom/${id}/responses`, { answer: answers[id] })
      notify('课堂回答已提交')
      activities.reload()
      setAnswers((v) => ({ ...v, [id]: '' }))
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Title
        title={teacher ? '让课堂里的每个声音，被听见' : '把你的思考，带进课堂'}
        subtitle="即时提问、小测与反馈约每 7 秒同步，连接课堂参与和课后巩固"
        action={
          teacher ? (
            <Button onClick={() => setCreate(true)}>
              <Plus size={16} />
              发起课堂互动
            </Button>
          ) : (
            <Button variant="secondary" onClick={activities.reload}>
              刷新课堂活动
            </Button>
          )
        }
      />
      <LoadState {...activities} retry={activities.reload} />
      <div className="classroom-grid">
        {activities.data.map((a) => (
          <Panel key={a.id} className={`classroom-card ${a.active ? 'is-active' : ''}`}>
            <div className="classroom-card-head">
              <span className="class-icon">
                <MessageCircle size={23} />
              </span>
              <Pill tone={a.active ? 'green' : 'neutral'}>{a.active ? '正在进行' : '已结束'}</Pill>
            </div>
            <h2>{a.title}</h2>
            <p className="classroom-prompt">{a.prompt}</p>
            <div className="classroom-meta">
              <span>
                {a.kind === 'quiz' ? '课堂小测' : a.kind === 'feedback' ? '教学反馈' : '课堂提问'}
              </span>
              <span>{a.responses?.length || 0} 次参与</span>
            </div>
            {teacher ? (
              <>
                <div className="classroom-responses">
                  {a.responses?.map((r: Row, i: number) => (
                    <div key={r.id || i}>
                      <strong>
                        {r.student_name || r.name || `学生 ${r.student_id || r.user_id || ''}`}
                      </strong>
                      <p>{r.answer}</p>
                    </div>
                  ))}
                </div>
                {a.active ? (
                  <Button
                    variant="secondary small"
                    onClick={async () => {
                      try {
                        await patch(`/classroom/${a.id}`, { active: false })
                        activities.reload()
                        notify('课堂互动已结束')
                      } catch (e) {
                        notify((e as Error).message, true)
                      }
                    }}
                  >
                    结束本次互动
                  </Button>
                ) : null}
              </>
            ) : a.active ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  respond(a.id)
                }}
                className="classroom-answer"
              >
                <label>
                  你的回答
                  <textarea
                    required
                    aria-label={`回答${a.title}`}
                    value={answers[a.id] || ''}
                    onChange={(e) => setAnswers((v) => ({ ...v, [a.id]: e.target.value }))}
                    rows={3}
                    placeholder="写下你的理解或反馈…"
                  />
                </label>
                <Button variant="small" disabled={busy || !answers[a.id]?.trim()}>
                  <Send size={15} />
                  提交课堂回答
                </Button>
              </form>
            ) : (
              <Pill>课堂活动已归档</Pill>
            )}
          </Panel>
        ))}
      </div>
      {!activities.data.length && !activities.loading ? (
        <Panel>
          <Empty>
            {teacher
              ? '发起一次课堂互动，了解学生此刻的理解。'
              : '当前还没有课堂活动，教师发起后会自动显示。'}
          </Empty>
        </Panel>
      ) : null}
      {create ? (
        <Modal title="发起课堂即时互动" close={() => setCreate(false)}>
          <form className="form-stack" onSubmit={publish}>
            <label>
              活动标题
              <input name="title" required placeholder="例如：用生活中的例子解释队列" />
            </label>
            <label>
              活动类型
              <select name="kind">
                <option value="question">即时提问</option>
                <option value="quiz">课堂小测</option>
                <option value="feedback">教学反馈</option>
              </select>
            </label>
            <label>
              提问或任务
              <textarea
                required
                name="prompt"
                rows={4}
                placeholder="用清晰的问题引导学生说出自己的理解…"
              />
            </label>
            <Button disabled={busy}>
              <Send size={16} />
              {busy ? '发起中…' : '发布到课堂'}
            </Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
