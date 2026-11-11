import { Pager, Tabs, usePage } from '../components/Workspace'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Edit3,
  Lightbulb,
  Plus,
  Save,
  Send,
  Sparkles,
  Trash2,
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
  Title,
  dateLabel,
  typeLabels,
  useApp,
} from '../ui'

export function Practice({ review = false }: { review?: boolean }) {
  const { user, courseId, notify } = useApp()
  const [params, setParams] = useSearchParams()
  const assignmentId = Number(params.get('assignment')) || 0
  const knowledgeId = Number(params.get('knowledge')) || 0
  const teacher = user.role === 'teacher'
  const [type, setType] = useState('')
  const questions = useApi<Row[]>(
    review
      ? `/mistakes?course_id=${courseId}`
      : `/questions?course_id=${courseId}${knowledgeId ? `&knowledge_id=${knowledgeId}` : ''}${type ? `&type=${type}` : ''}`,
    [],
  )
  const schedule = useApi<Row[]>(review ? `/review-schedule?course_id=${courseId}` : null, [])
  const assignment = useApi<Row>(assignmentId ? `/assignments/${assignmentId}` : null, {})
  const assignments = useApi<Row[]>(`/assignments?course_id=${courseId}`, [])
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const classes = useApi<Row[]>(teacher ? `/classes?course_id=${courseId}` : null, [])
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState<string | string[]>('')
  const [hints, setHints] = useState(0)
  const [result, setResult] = useState<Row | null>(null)
  const [busy, setBusy] = useState(false)
  const [compose, setCompose] = useState(false)
  const [questionForm, setQuestionForm] = useState(false)
  const [chosen, setChosen] = useState<number[]>([])
  const [draft, setDraft] = useState<Row | null>(null)
  const [generationBusy, setGenerationBusy] = useState(false)
  const list: Row[] = assignmentId ? assignment.data.questions || [] : questions.data
  const [workspaceView, setWorkspaceView] = useState('work')
  const [feedbackView, setFeedbackView] = useState(false)
  const [support, setSupport] = useState('navigation')
  const bankPage = usePage<Row>(list, 106, 310)
  const taskPage = usePage<Row>(assignments.data, 102, 310)
  const schedulePage = usePage<Row>(schedule.data, 88, 310)
  const q = list[index]
  const qid = q?.question_id || q?.id
  useEffect(() => {
    setIndex(0)
  }, [courseId, review, knowledgeId, assignmentId, type])
  useEffect(() => {
    setAnswer('')
    setResult(null)
    setFeedbackView(false)
    setHints(0)
  }, [qid])
  useEffect(() => {
    const question = Number(params.get('question'))
    if (question) {
      const next = list.findIndex((q) => (q.question_id || q.id) === question)
      if (next >= 0) {
        setIndex(next)
        if (teacher) bankPage.setPage(Math.floor(next / bankPage.size) + 1)
      }
    }
  }, [params, list])
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!q) return
    setBusy(true)
    try {
      const response = await post(review ? `/mistakes/${qid}/review` : '/attempts', {
        question_id: qid,
        answer,
        hints_used: hints,
        ...(assignmentId ? { assignment_id: assignmentId } : {}),
      })
      setResult(response)
      setFeedbackView(true)
      notify(
        response.review_status === 'pending_review'
          ? '已提交，等待教师复核'
          : response.correct
            ? '回答正确，学习状态已更新'
            : '已记录错因，接下来一起理清思路',
      )
      assignments.reload()
      schedule.reload()
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  async function publish(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    try {
      await post('/assignments', {
        course_id: courseId,
        title: f.get('title'),
        description: f.get('description'),
        class_id: Number(f.get('class_id')) || null,
        question_ids: chosen,
        due_at: f.get('due_at') || null,
      })
      notify('作业已发布，学生可立即接收')
      setCompose(false)
      assignments.reload()
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function saveQuestion(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    try {
      const body = {
        course_id: courseId,
        knowledge_id: Number(f.get('knowledge_id')),
        title: f.get('title'),
        type: f.get('type'),
        difficulty: Number(f.get('difficulty')),
        options: String(f.get('options') || '')
          .split('\n')
          .filter(Boolean),
        answer:
          f.get('type') === 'multiple'
            ? String(f.get('answer') || '')
                .split(/[,，\n]+/)
                .map((x) => x.trim())
                .filter(Boolean)
            : String(f.get('answer') || ''),
        explanation: f.get('explanation'),
        hints: [String(f.get('hint') || '回忆知识点的定义，再逐项判断。')],
        status: f.get('status') || 'approved',
        skill: f.get('skill') || 'concept',
        diagnostic_map: draft?.diagnostic_map || {},
      }
      const saved = draft?.edit_existing
        ? await patch(`/questions/${draft.id}`, body)
        : await post('/questions', body)
      setParams((previous) => {
        previous.set('question', String(saved.id))
        return previous
      })
      notify('题目已保存至课程题库')
      setQuestionForm(false)
      setDraft(null)
      questions.reload()
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function generate() {
    setGenerationBusy(true)
    try {
      const generated = await post('/ai/generate', {
        course_id: courseId,
        kind: 'question',
        knowledge_point_id: knowledgeId || graph.data.nodes?.[0]?.id,
        prompt: '生成一道基础单选题，包含解析。',
      })
      setDraft(generated.result)
      setQuestionForm(true)
      notify('已生成待审核草稿，请核对后保存')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setGenerationBusy(false)
    }
  }
  return (
    <>
      <Title
        title={teacher ? '题库与作业' : review ? '错题与复习' : '智能练习'}
        subtitle={
          teacher
            ? '维护题库、审核 AI 草稿，为班级发布有针对性的任务'
            : review
              ? '结合错因与复测表现安排巩固，独立完成后更新学习状态'
              : '先独立思考，必要时再取用提示。每次作答都是学习的证据'
        }
        action={
          teacher ? (
            <div className="button-row">
              <Button variant="secondary" onClick={generate} disabled={generationBusy}>
                <Sparkles size={16} />
                {generationBusy ? '生成中…' : 'AI 出题'}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setDraft(null)
                  setQuestionForm(true)
                }}
              >
                <Plus size={16} />
                新增题目
              </Button>
              <Button onClick={() => setCompose(true)}>
                <Send size={16} />
                发布作业
              </Button>
            </div>
          ) : (
            <Link to="/tutor" className="button secondary">
              <Sparkles size={16} />
              学习伙伴
            </Link>
          )
        }
      />
      <div className="practice-top">
        <div className="segmented">
          <button
            className={!assignmentId ? 'active' : ''}
            onClick={() => {
              setParams({})
              setIndex(0)
            }}
          >
            {review ? '待复习错题' : '自主练习'}
          </button>
          <select
            aria-label="选择作业范围"
            value={assignmentId || ''}
            onChange={(e) => {
              const next = new URLSearchParams()
              next.set('course', String(courseId))
              if (e.target.value) next.set('assignment', e.target.value)
              setParams(next)
              setIndex(0)
            }}
          >
            <option value="">全部练习</option>
            {assignments.data.map((a) => (
              <option value={a.id} key={a.id}>
                {a.title}
                {a.completed ? ' · 已完成' : ''}
              </option>
            ))}
          </select>
        </div>
        {!review && !assignmentId ? (
          <select aria-label="按题型筛选" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">全部题型</option>
            {['single', 'multiple', 'true_false', 'fill', 'short', 'step'].map((t) => (
              <option value={t} key={t}>
                {typeLabels[t]}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <LoadState
        loading={questions.loading || assignment.loading}
        error={questions.error || assignment.error}
        retry={() => {
          questions.reload()
          assignment.reload()
        }}
      />
      {knowledgeId ? (
        <div className="scope-indicator">
          专题：{graph.data.nodes?.find((n: Row) => n.id === knowledgeId)?.title} · {list.length} 题{' '}
          <Link to={`/practice?course=${courseId}`}>全部练习</Link>
        </div>
      ) : null}
      {teacher || review ? (
        <Tabs
          value={workspaceView}
          onChange={setWorkspaceView}
          items={
            teacher
              ? [
                  ['work', '课程题库'],
                  ['tasks', '作业记录'],
                ]
              : [
                  ['work', '错题订正'],
                  ['schedule', '复习日程'],
                ]
          }
        />
      ) : null}
      {teacher && workspaceView === 'tasks' ? (
        <Panel className="workspace-list">
          <div className="workspace-list-body">
            {taskPage.rows.map((a) => (
              <AssignmentRow key={a.id} assignment={a} />
            ))}
          </div>
          <Pager {...taskPage} onChange={taskPage.setPage} label="份作业" />
        </Panel>
      ) : null}
      {teacher && workspaceView === 'work' ? (
        <div className="teacher-bank">
          <Panel title="课程题库" caption={`${list.length} 道题目 · 所有 AI 生成内容需教师审核`}>
            <div className="question-bank">
              {bankPage.rows.map((item, j) => (
                <button
                  key={item.id}
                  className={index === (bankPage.page - 1) * bankPage.size + j ? 'active' : ''}
                  onClick={() => setIndex((bankPage.page - 1) * bankPage.size + j)}
                >
                  <span className="question-number">
                    {String((bankPage.page - 1) * bankPage.size + j + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <Pill tone="blue">{typeLabels[item.type] || item.type}</Pill>
                    <h3>{item.title}</h3>
                    <small>
                      {item.difficulty || 1} 星难度 ·{' '}
                      {graph.data.nodes?.find((n: Row) => n.id === item.knowledge_id)?.title ||
                        '课程知识'}
                    </small>
                  </div>
                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
            <Pager {...bankPage} onChange={bankPage.setPage} label="道题" />
          </Panel>
          <div>
            {q ? (
              <Panel
                title="当前题目与审核"
                caption="已被作业引用或已有作答的题目，修改答案需复制新版本"
              >
                <Pill tone={q.status === 'draft' ? 'amber' : 'green'}>
                  {q.status === 'draft' ? '待审核草稿' : '已审核'}
                </Pill>
                <h3 className="teacher-question-title">{q.title}</h3>
                <div className="teacher-answer-preview">
                  <strong>参考答案</strong>
                  <p>{Array.isArray(q.answer) ? q.answer.join('、') : q.answer}</p>
                  <strong>解析</strong>
                  <p>{q.explanation}</p>
                </div>
                <div className="button-row">
                  <Button
                    variant="secondary small"
                    onClick={() => {
                      setDraft({ ...q, edit_existing: true })
                      setQuestionForm(true)
                    }}
                  >
                    <Edit3 size={14} />
                    编辑题目
                  </Button>
                  <Button
                    variant="secondary small"
                    onClick={() => {
                      setDraft({
                        ...q,
                        id: undefined,
                        title: `${q.title}（新版本）`,
                        edit_existing: false,
                      })
                      setQuestionForm(true)
                    }}
                  >
                    <Plus size={14} />
                    复制新版本
                  </Button>
                  <Button
                    variant="danger small"
                    onClick={async () => {
                      if (!confirm('删除当前题目？已被任务使用的题目会保留以维护历史。')) return
                      try {
                        await api(`/questions/${q.id}`, { method: 'DELETE' })
                        questions.reload()
                        notify('题目已删除')
                      } catch (e) {
                        notify((e as Error).message, true)
                      }
                    }}
                  >
                    <Trash2 size={14} />
                    删除
                  </Button>
                </div>
              </Panel>
            ) : null}
          </div>
        </div>
      ) : null}
      {review && !teacher && workspaceView === 'schedule' ? (
        <Panel title="复习安排">
          <div className="review-schedule">
            {schedulePage.rows.map((item) => (
              <Link
                key={item.question_id}
                className={item.due ? 'due' : ''}
                to={`/review?course=${courseId}&question=${item.question_id}`}
              >
                <strong>{item.knowledge_title}</strong>
                <span>{item.due ? '已到期' : dateLabel(item.next_due)}</span>
                <small>
                  间隔 {item.interval_days} 天 · 质量 {item.last_quality}/5
                </small>
              </Link>
            ))}
          </div>
          <Pager {...schedulePage} onChange={schedulePage.setPage} label="项复习" />
        </Panel>
      ) : null}
      {!teacher && (!review || workspaceView === 'work') && q ? (
        <div className="practice-layout">
          <Panel className="question-workspace">
            <div className="question-meta">
              <Pill tone="blue">{typeLabels[q.type] || '知识练习'}</Pill>
              <Pill tone="neutral">{q.difficulty || 1} 星难度</Pill>
              {review ? (
                <Pill tone="amber">
                  {q.error_type || '概念理解'} · 错误 {q.wrong_count || 1} 次
                </Pill>
              ) : null}
              <span>
                第 {index + 1} / {list.length} 题
              </span>
            </div>
            {result ? (
              <Tabs
                value={feedbackView ? 'feedback' : 'question'}
                onChange={(v) => setFeedbackView(v === 'feedback')}
                items={[
                  ['question', '题目'],
                  ['feedback', '作答反馈'],
                ]}
              />
            ) : null}
            {!feedbackView ? (
              <>
                <h2 className="question-title">{q.title}</h2>
                <form onSubmit={submit}>
                  <AnswerInput
                    question={q}
                    answer={answer}
                    setAnswer={setAnswer}
                    disabled={Boolean(result)}
                  />
                  {!result ? (
                    <div className="question-submit">
                      <Button
                        type="submit"
                        disabled={busy || (Array.isArray(answer) ? !answer.length : !answer.trim())}
                      >
                        <CheckCheck size={17} />
                        {busy ? '正在评阅…' : '提交答案'}
                      </Button>
                      <span>先独立完成，再查看解析</span>
                    </div>
                  ) : null}
                </form>
              </>
            ) : null}
            {result && feedbackView ? (
              <div
                className={`answer-feedback ${result.correct ? 'correct' : result.review_status === 'pending_review' ? 'pending' : 'incorrect'}`}
                role="status"
              >
                <h3>
                  {result.review_status === 'pending_review'
                    ? '已提交，等待教师复核'
                    : result.correct
                      ? '思路清晰，回答正确'
                      : '这里值得再想一想'}
                </h3>
                <p>{result.explanation || '请对照知识点定义，重新梳理解题过程。'}</p>
                <div className="feedback-meta">
                  {result.review_status === 'pending_review' ? (
                    <Pill tone="amber">主观题 · 教师复核后确认分数</Pill>
                  ) : (
                    <>
                      <Pill tone={result.correct ? 'green' : 'amber'}>本次得分 {result.score}</Pill>
                      <Pill>掌握度 {percent(result.mastery)}%</Pill>
                    </>
                  )}
                  {result.error_type ? <Pill tone="amber">{result.error_type}</Pill> : null}
                </div>
                {result.knowledge_change ? (
                  <div className="knowledge-change">
                    <div>
                      <span>知识状态</span>
                      <strong>
                        {result.knowledge_change.before}% <ArrowRight size={16} />{' '}
                        {result.knowledge_change.after}%
                      </strong>
                    </div>
                    <p>
                      {result.knowledge_change.weight === 0
                        ? '本次重复成功保留原有证据'
                        : result.knowledge_change.hints
                          ? `使用 ${result.knowledge_change.hints} 次提示，已调整独立性权重`
                          : result.knowledge_change.correlation < 1
                            ? '相近题证据已折减，继续尝试不同情境'
                            : '独立作答已计入知识证据'}
                    </p>
                  </div>
                ) : null}
                {result.evidence ? (
                  <p className="evidence-summary">
                    {result.evidence.sufficiency} · 有效证据{' '}
                    {Number(result.evidence.effective_count).toFixed(1)} · 估计区间{' '}
                    {Math.round(result.evidence.lower * 100)}%–
                    {Math.round(result.evidence.upper * 100)}%
                  </p>
                ) : null}
                {result.review_schedule ? (
                  <p>
                    下次复习：{dateLabel(result.review_schedule.next_due)} · 间隔{' '}
                    {result.review_schedule.interval_days} 天
                  </p>
                ) : null}
                {result.answer ? (
                  <p>
                    <strong>参考答案：</strong>
                    {Array.isArray(result.answer) ? result.answer.join('、') : result.answer}
                  </p>
                ) : null}
                {result.recommendations?.length ? (
                  <div className="feedback-path">
                    <h3>接下来</h3>
                    {result.recommendations.slice(0, 2).map((r: Row) => (
                      <Link key={r.id} to={r.href}>
                        <span>{r.path_position}</span>
                        <div>
                          <strong>{r.title}</strong>
                          <small>{r.reason}</small>
                        </div>
                        <ArrowRight size={16} />
                      </Link>
                    ))}
                  </div>
                ) : null}
                <div className="button-row">
                  <Link
                    to={`/tutor?question=${qid}&knowledge=${q.knowledge_id || ''}`}
                    className="button secondary small"
                  >
                    <Sparkles size={15} />
                    针对这道题聊一聊
                  </Link>
                  <Button
                    variant="small"
                    onClick={() => {
                      if (index < list.length - 1) setIndex(index + 1)
                      else {
                        setAnswer('')
                        setResult(null)
                        questions.reload()
                      }
                    }}
                  >
                    {index < list.length - 1 ? '下一道练习' : '重新巩固'}
                    <ArrowRight size={15} />
                  </Button>
                </div>
              </div>
            ) : null}
            <div className="question-navigation">
              <Button
                variant="ghost small"
                disabled={index === 0}
                onClick={() => setIndex(index - 1)}
              >
                <ChevronLeft size={16} />
                上一题
              </Button>
              <span>
                {index + 1} / {list.length}
              </span>
              <Button
                variant="ghost small"
                disabled={index >= list.length - 1}
                onClick={() => setIndex(index + 1)}
              >
                下一题
                <ChevronRight size={16} />
              </Button>
            </div>
          </Panel>
          <aside>
            <Tabs
              value={support}
              onChange={setSupport}
              items={[
                ['navigation', '题号导航'],
                ['hints', '渐进提示'],
              ]}
            />
            {support === 'hints' ? (
              <Panel title="渐进提示" caption="只在需要时，迈出一小步">
                <div className="hint-intro">
                  <Lightbulb size={23} />
                  <p>先说清楚题目在考什么，再尝试拆解。使用提示会记入本次学习证据。</p>
                </div>
                {(q.hints || []).slice(0, hints).map((h: string, i: number) => (
                  <div className="hint-step" key={i}>
                    <strong>提示 {i + 1}</strong>
                    <p>{h}</p>
                  </div>
                ))}
                <Button
                  variant="secondary wide"
                  disabled={hints >= (q.hints?.length || 1) || Boolean(result)}
                  onClick={async () => {
                    setHints((h) => h + 1)
                    try {
                      await post('/events', {
                        course_id: courseId,
                        knowledge_id: q.knowledge_id,
                        kind: 'hint',
                        payload: { question_id: qid, hint_index: hints },
                      })
                    } catch {
                      /* 作答仍记录 hints_used */
                    }
                  }}
                >
                  <Lightbulb size={16} />
                  {hints ? '再给一点提示' : '查看第一条提示'}
                </Button>
                {!q.hints?.length && hints ? (
                  <p className="hint-step">从定义出发，思考结构的操作顺序与约束。</p>
                ) : null}
              </Panel>
            ) : (
              <Panel title="练习导航">
                <div className="question-dots">
                  {list.map((r, i) => (
                    <button
                      key={r.id || r.question_id}
                      className={i === index ? 'active' : ''}
                      onClick={() => setIndex(i)}
                      aria-label={`跳转第${i + 1}题`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
                <Link to={`/graph?knowledge=${q.knowledge_id}`} className="text-link">
                  查看知识位置
                  <ArrowRight size={15} />
                </Link>
              </Panel>
            )}
          </aside>
        </div>
      ) : null}
      {!teacher && !q && !questions.loading && !assignment.loading ? (
        <Panel>
          <Empty
            action={
              <Link to="/graph" className="button secondary">
                探索知识图谱
              </Link>
            }
          >
            {review
              ? '暂时没有待复习错题，继续保持独立思考。'
              : '当前筛选下还没有练习，试试其他知识点。'}
          </Empty>
        </Panel>
      ) : null}
      {compose ? (
        <Modal title="发布学习作业" close={() => setCompose(false)}>
          <form className="form-stack" onSubmit={publish}>
            <label>
              作业标题
              <input name="title" required placeholder="例如：树结构基础巩固" />
            </label>
            <label>
              发布到班级
              <select name="class_id" required>
                <option value="">请选择班级</option>
                {classes.data.map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              截止时间
              <input type="datetime-local" name="due_at" />
            </label>
            <label>
              学习说明
              <textarea name="description" rows={2} />
            </label>
            <fieldset>
              <legend>选择题目（{chosen.length}）</legend>
              <div className="checkbox-list">
                {questions.data.map((item) => (
                  <label key={item.id}>
                    <input
                      type="checkbox"
                      checked={chosen.includes(item.id)}
                      onChange={(e) =>
                        setChosen((v) =>
                          e.target.checked ? [...v, item.id] : v.filter((id) => id !== item.id),
                        )
                      }
                    />
                    <span>{item.title}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <Button disabled={!chosen.length} type="submit">
              <Send size={16} />
              发布作业
            </Button>
          </form>
        </Modal>
      ) : null}
      {questionForm ? (
        <Modal
          title={
            draft?.edit_existing ? '编辑课程题目' : draft ? '审核 AI 题目草稿' : '创建课程题目'
          }
          close={() => setQuestionForm(false)}
        >
          <form className="form-stack" onSubmit={saveQuestion}>
            {draft && !draft.edit_existing ? (
              <Pill tone="amber">待审核草稿 · 请核对知识与参考答案后保存</Pill>
            ) : null}
            <label>
              所测技能
              <select name="skill" defaultValue={draft?.skill || 'concept'}>
                <option value="concept">概念理解</option>
                <option value="procedure">程序步骤</option>
                <option value="reasoning">逻辑推理</option>
                <option value="transfer">迁移应用</option>
              </select>
            </label>
            <label>
              题目内容
              <textarea
                required
                name="title"
                rows={3}
                defaultValue={draft?.title || draft?.question || ''}
              />
            </label>
            <div className="form-columns">
              <label>
                题型
                <select name="type" aria-label="题型" defaultValue={draft?.type || 'single'}>
                  {['single', 'multiple', 'true_false', 'fill', 'short', 'step'].map((t) => (
                    <option value={t} key={t}>
                      {typeLabels[t]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                难度
                <select name="difficulty" defaultValue={draft?.difficulty || 1}>
                  {[1, 2, 3].map((i) => (
                    <option value={i} key={i}>
                      {i} 星
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              关联知识点
              <select
                name="knowledge_id"
                required
                defaultValue={draft?.knowledge_id || knowledgeId || ''}
              >
                <option value="" disabled>
                  请选择
                </option>
                {graph.data.nodes?.map((n: Row) => (
                  <option key={n.id} value={n.id}>
                    {n.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              选项（每行一个，填空/简答可留空）
              <textarea name="options" rows={4} defaultValue={draft?.options?.join('\n') || ''} />
            </label>
            <label>
              参考答案
              <input
                required
                name="answer"
                defaultValue={
                  Array.isArray(draft?.answer) ? draft.answer.join(',') : draft?.answer || ''
                }
              />
            </label>
            <label>
              答案解析
              <textarea name="explanation" rows={3} defaultValue={draft?.explanation || ''} />
            </label>
            <label>
              首条提示
              <input name="hint" defaultValue={draft?.hints?.[0] || ''} />
            </label>
            <label>
              审核状态
              <select name="status" defaultValue={draft?.status || 'approved'}>
                <option value="draft">保留为草稿</option>
                <option value="approved">审核通过</option>
              </select>
            </label>
            <Button type="submit">
              <Save size={16} />
              审核并保存题目
            </Button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}

export function AnswerInput({
  question: q,
  answer,
  setAnswer,
  disabled,
}: {
  question: Row
  answer: string | string[]
  setAnswer: (a: string | string[]) => void
  disabled?: boolean
}) {
  const multiple = ['multiple', 'multiple_choice'].includes(q.type)
  const bool = ['true_false', 'true_false'].includes(q.type)
  const options = q.options?.length ? q.options : bool ? ['正确', '错误'] : []
  return options.length ? (
    <div className="answer-options">
      {options.map((option: string, i: number) => {
        const selected = Array.isArray(answer) ? answer.includes(option) : answer === option
        return (
          <label key={i} className={`answer-option ${selected ? 'selected' : ''}`}>
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={`answer-${q.id}`}
              checked={selected}
              disabled={disabled}
              onChange={() =>
                setAnswer(
                  multiple
                    ? selected
                      ? (Array.isArray(answer) ? answer : []).filter((v) => v !== option)
                      : [...(Array.isArray(answer) ? answer : []), option]
                    : option,
                )
              }
            />
            <span className="option-letter">
              {bool ? <CircleCheck size={15} /> : String.fromCharCode(65 + i)}
            </span>
            <span>{option}</span>
            {selected ? <CheckCheck size={17} /> : null}
          </label>
        )
      })}
    </div>
  ) : (
    <label className="free-answer">
      你的思考
      <textarea
        required
        aria-label="填写答案"
        disabled={disabled}
        value={typeof answer === 'string' ? answer : answer.join(',')}
        onChange={(e) => setAnswer(e.target.value)}
        rows={q.type === 'fill' ? 2 : 6}
        placeholder={q.type === 'fill' ? '填写答案…' : '写下你的推理过程、关键步骤与结论…'}
      />
    </label>
  )
}
export function AssignmentRow({ assignment }: { assignment: Row }) {
  const [open, setOpen] = useState(false)
  const result = useApi<Row[]>(open ? `/assignments/${assignment.id}/results` : null, [])
  const results = usePage<Row>(Array.isArray(result.data) ? result.data : [], 100, 340)
  return (
    <div className="assignment-row">
      <div>
        <h3>{assignment.title}</h3>
        <small>
          {assignment.question_ids?.length || 0} 道题 · {assignment.submission_count || 0} 次提交
        </small>
      </div>
      <Button variant="small secondary" onClick={() => setOpen(!open)}>
        {open ? '收起结果' : '查看结果'}
      </Button>
      {open ? (
        <Modal title={`${assignment.title} · 提交结果`} close={() => setOpen(false)}>
          <div className="assignment-results">
            <LoadState {...result} />
            {results.rows.map((r: Row, i: number) => (
              <div key={r.student_id || i}>
                <span>{r.name || r.student_name}</span>
                <Pill>{r.completed ? '已完成' : '待完成'}</Pill>
                <strong>{r.score ?? '—'}</strong>
                {r.comparison?.length ? (
                  <div className="intervention-comparison">
                    {r.comparison.map((c: Row) => (
                      <p key={c.knowledge_id}>
                        {c.title}：发布时 {c.baseline}% → 当前 {c.current}%（
                        {c.delta > 0 ? '+' : ''}
                        {c.delta}） · 新增有效证据 {c.new_evidence}
                      </p>
                    ))}
                    <small>状态对照，尚不能据此证明教学效果。</small>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          <Pager {...results} onChange={results.setPage} label="位学生成绩" />
        </Modal>
      ) : null}
    </div>
  )
}
