import { useState } from 'react'
import { Link } from 'react-router-dom'
import { post } from '../api'
import type { Row } from '../api'
import { Button, Modal, useApp } from '../ui'

export function TeacherDraft({ artifact, evidence }: { artifact: Row; evidence?: Row }) {
  const { courseId, notify } = useApp()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Row>(artifact.draft || {})
  const [saved, setSaved] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  if (!artifact.id) return artifact.error ? <p role="status">{artifact.error}</p> : null
  if (artifact.kind === 'question' || artifact.kind === 'rubric') return <section className="teacher-draft">
    <h3>{artifact.kind === 'question' ? '题目草稿' : '量规建议'}</h3><p>{draft.title || draft.feedback}</p>
    {draft.options?.map((option: string) => <p key={option}>{option}</p>)}
    {draft.criteria?.map((criterion: Row, index: number) => <p key={index}>{criterion.name}　{criterion.max_score}分</p>)}
    <Link className="button secondary small" to={artifact.kind === 'question' ? `/practice?course=${courseId}&question_draft=${artifact.id}` : `/analytics?course=${courseId}`}>{artifact.kind === 'question' ? '进入题库审核' : '进入教师批阅'}</Link>
  </section>
  return <section className="teacher-draft" aria-label="教学方案草稿">
    <div className="draft-heading"><h3>{draft.title}</h3><span>待确认草稿</span></div>
    <p>{draft.objective}</p>
    <ol>{draft.steps?.map((step: Row, index: number) => <li key={index}><strong>{step.title} <small>{step.minutes}分钟</small></strong><p>{step.activity}</p></li>)}</ol>
    <div className="button-row"><Button variant="secondary small" onClick={() => setEditing(true)}>编辑与保存教案</Button>{saved && <Link className="button secondary small" to={`/resources?course=${courseId}&resource=${saved}`}>打开教案</Link>}</div>
    {draft.groups?.length > 0 && <div className="draft-groups">{draft.groups.map((group: Row, index: number) => <div key={group.group_id}><h4>{group.name || `练习组${index + 1}`}</h4><p>{group.objective}</p><small>{group.student_ids?.length}位学生，{group.question_ids.length}道题</small><Link className="text-link" to={`/practice?course=${courseId}&teaching_draft=${artifact.id}&group=${encodeURIComponent(group.group_id)}`}>审核并发布任务</Link></div>)}</div>}
    {evidence?.summary && <details><summary>查看班级依据</summary><p>{evidence.summary.student_count}位学生，{evidence.summary.attempt_count}次已评分作答</p><Link to={`/analytics?course=${courseId}`}>查看学情与分层</Link></details>}
    {editing && <Modal title="编辑教学安排" close={() => setEditing(false)}><form className="form-stack" onSubmit={async event => {
      event.preventDefault(); setBusy(true)
      try { const response = await post<Row>(`/ai/teacher-drafts/${artifact.id}/save`, draft); setSaved(response.resource_id); setEditing(false); notify('教案草稿已保存') } catch (error) { notify((error as Error).message, true) } finally { setBusy(false) }
    }}><label>教案标题<input required value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label><label>教学目标<textarea required value={draft.objective} onChange={event => setDraft({ ...draft, objective: event.target.value })} /></label>
      {draft.steps?.map((step: Row, index: number) => <fieldset key={index}><label>环节<input required value={step.title} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item: Row, i: number) => i === index ? { ...item, title: event.target.value } : item) })} /></label><label>分钟<input required type="number" min="1" max="120" value={step.minutes} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item: Row, i: number) => i === index ? { ...item, minutes: Number(event.target.value) } : item) })} /></label><label>教学活动<textarea required value={step.activity} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item: Row, i: number) => i === index ? { ...item, activity: event.target.value } : item) })} /></label></fieldset>)}
      <Button disabled={busy}>保存为教案草稿</Button>
    </form></Modal>}
  </section>
}
