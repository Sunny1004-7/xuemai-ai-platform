import { Pager, usePage } from '../components/Workspace'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  Download,
  Edit3,
  FileText,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Upload,
  Video,
} from 'lucide-react'
import { api, patch, post, useApi } from '../api'
import type { Row } from '../api'
import { RichText } from '../components/RichText'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'

export function Resources() {
  const { user, courseId, notify } = useApp()
  const [params] = useSearchParams()
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('all')
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const [editing, setEditing] = useState<Row | null>(null)
  const [preview, setPreview] = useState<Row | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [lesson, setLesson] = useState(false)
  useEffect(() => {
    const id = Number(params.get('resource') || params.get('resource_id'))
    if (id) setPreview(resources.data.find((r) => r.id === id) || null)
  }, [params, resources.data])
  const teacher = user.role === 'teacher'
  const list = resources.data.filter(
    (r) =>
      (kind === 'all' || r.kind === kind) &&
      (!search || `${r.title} ${r.content}`.includes(search)),
  )
  const paging = usePage(list, 110, 290)
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
        title={teacher ? '资料与备课' : '课程资源'}
        subtitle={
          teacher
            ? '从资料检索到可编辑教案，把 AI 的建议变成经过审核的教学内容'
            : '课程讲义、学习材料与知识片段，同一处随时查阅'
        }
        action={
          teacher ? (
            <div className="button-row">
              <Link className="button secondary" to={`/teacher-ai?course=${courseId}`}>教学研讨</Link>
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
        {paging.rows.map((r) => (
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
            <p>{resourceSummary(r.content) || '暂无摘要'}</p>
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
      <Pager {...paging} onChange={paging.setPage} label="份资料" />
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
            <div className="resource-document">
              <RichText>{preview.content || '此资源没有文本正文。'}</RichText>
            </div>
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

function resourceSummary(content = '') {
  const text = content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]*>/g, ' ')
    .replace(/[#*`>|_~]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return text.length > 100 ? text.slice(0, 100) + '…' : text
}
