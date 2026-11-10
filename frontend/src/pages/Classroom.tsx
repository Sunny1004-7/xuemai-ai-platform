import { useEffect, useState } from 'react'

import { MessageCircle, Plus, Send } from 'lucide-react'
import { patch, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'

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
        title="课堂互动"
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
              <>
                {a.responses?.length ? (
                  <div className="classroom-responses" aria-label="已提交回答">
                    {a.responses.map((r: Row) => (
                      <div key={r.id}>
                        <strong>已提交</strong>
                        <p>{r.answer}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
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
              </>
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
