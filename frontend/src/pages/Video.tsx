import { Tabs } from '../components/Workspace'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCheck,
  Clock3,
  ListVideo,
  Play,
  Plus,
  Save,
  Search,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { api, getSession, patch, percent, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'
import { AnswerInput } from './Practice'

export const timeLabel = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, '0')}:${Math.floor(s % 60)
    .toString()
    .padStart(2, '0')}`
export function VideoPage() {
  const { user, courseId, notify } = useApp()
  const [params] = useSearchParams()
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const questions = useApi<Row[]>(`/questions?course_id=${courseId}`, [])
  const [chosen, setChosen] = useState(Number(params.get('resource')) || 0)
  const videoResources = resources.data.filter((r) => r.kind === 'video')
  const current = videoResources.find((r) => r.id === chosen) || videoResources[0]
  const notes = useApi<Row[]>(
    current ? `/notes?course_id=${courseId}&resource_id=${current.id}` : null,
    [],
  )
  const [tab, setTab] = useState('transcript')
  const [search, setSearch] = useState('')
  const [note, setNote] = useState('')
  const [position, setPosition] = useState(Number(params.get('t')) || 0)
  const [duration, setDuration] = useState(0)
  const [checkpoint, setCheckpoint] = useState<Row | null>(null)
  const [answer, setAnswer] = useState<string | string[]>('')
  const [result, setResult] = useState<Row | null>(null)
  const [edit, setEdit] = useState(false)
  const [videoUrl, setVideoUrl] = useState('')
  const video = useRef<HTMLVideoElement>(null)
  const lastSaved = useRef(-10)
  const shownChecks = useRef(new Set<number>())
  const teacher = user.role === 'teacher'
  const metadata = current?.metadata || {}
  const subtitles: Row[] = metadata.subtitles || metadata.transcript || []
  const timeline: Row[] = metadata.timeline || metadata.chapters || []
  const checkpoints: Row[] =
    metadata.checkpoints ||
    (metadata.checkpoint_question_id
      ? [{ time: metadata.checkpoint_time || 15, question_id: metadata.checkpoint_question_id }]
      : [])
  useEffect(() => {
    if (!current?.url) {
      setVideoUrl('')
      return
    }
    if (!current.url.startsWith('/api/')) {
      setVideoUrl(current.url)
      return
    }
    const controller = new AbortController()
    let blobUrl = ''
    setVideoUrl('')
    fetch(current.url, {
      signal: controller.signal,
      headers: { Authorization: `Bearer ${getSession()?.token || ''}` },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('没有权限读取视频或文件已失效')
        return response.blob()
      })
      .then((blob) => {
        if (!controller.signal.aborted) {
          blobUrl = URL.createObjectURL(blob)
          setVideoUrl(blobUrl)
        }
      })
      .catch((e) => {
        if (e.name !== 'AbortError') notify(e.message, true)
      })
    return () => {
      controller.abort()
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [current?.id, current?.url])
  function seek(time: number) {
    if (video.current) {
      video.current.currentTime = time
      setPosition(time)
    }
  }
  useEffect(() => {
    shownChecks.current = new Set()
    lastSaved.current = -10
    setResult(null)
    setAnswer('')
  }, [current?.id])
  async function saveProgress(time: number) {
    if (!current || Math.abs(time - lastSaved.current) < 8) return
    lastSaved.current = time
    try {
      await post('/events', {
        course_id: courseId,
        knowledge_id: current.knowledge_id,
        kind: 'video_progress',
        payload: {
          resource_id: current.id,
          position: Math.floor(time),
          duration: Math.floor(duration),
        },
      })
    } catch {
      /* 播放不会因网络失败中断 */
    }
  }
  function onTime() {
    const time = video.current?.currentTime || 0
    setPosition(time)
    saveProgress(time)
    if (!teacher)
      for (const cp of checkpoints) {
        const at = cp.time ?? cp.timestamp ?? cp.start ?? 15
        if (time >= at && !shownChecks.current.has(cp.question_id)) {
          const question = questions.data.find((q) => q.id === cp.question_id)
          if (question) {
            shownChecks.current.add(cp.question_id)
            video.current?.pause()
            setCheckpoint(question)
            setAnswer('')
            setResult(null)
          }
        }
      }
  }
  async function saveNote(e: React.FormEvent) {
    e.preventDefault()
    if (!note.trim() || !current) return
    try {
      await post('/notes', {
        course_id: courseId,
        resource_id: current.id,
        knowledge_id: current.knowledge_id,
        timestamp: Math.floor(position),
        content: note,
      })
      notify('时间戳笔记已保存')
      setNote('')
      notes.reload()
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function answerCheck(e: React.FormEvent) {
    e.preventDefault()
    if (!checkpoint) return
    try {
      const response = await post('/attempts', {
        question_id: checkpoint.id,
        answer,
        hints_used: 0,
      })
      setResult(response)
      await post('/events', {
        course_id: courseId,
        knowledge_id: checkpoint.knowledge_id,
        kind: 'video_checkpoint',
        payload: {
          resource_id: current?.id,
          question_id: checkpoint.id,
          attempt_id: response.id,
          correct: response.correct,
        },
      })
      notify('互动检查已写入学习记录')
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  return (
    <>
      <Title
        title="视频学习"
        subtitle={
          teacher
            ? '维护视频字幕、知识时间轴与随堂检查，跟踪学习过程'
            : '看一段课程，记下一个思考，再用练习确认自己的理解'
        }
        action={
          teacher && current ? (
            <Button variant="secondary" onClick={() => setEdit(true)}>
              <ListVideo size={16} />
              编辑字幕与检查点
            </Button>
          ) : (
            <Link to="/graph" className="button secondary">
              <BookOpen size={16} />
              返回知识图谱
            </Link>
          )
        }
      />
      <LoadState {...resources} retry={resources.reload} />
      {current ? (
        <>
          <div className="video-layout">
            <div className="video-main">
              <div className="video-frame">
                <video
                  key={current.id}
                  ref={video}
                  controls
                  preload="metadata"
                  src={videoUrl || undefined}
                  onLoadedMetadata={() => {
                    setDuration(video.current?.duration || 0)
                    seek(Number(params.get('t')) || Number(metadata.resume_position) || 0)
                  }}
                  onTimeUpdate={onTime}
                  onPause={() => saveProgress(video.current?.currentTime || 0)}
                  onError={() => notify('视频暂时无法加载，请检查演示媒体是否已生成', true)}
                  aria-label={current.title}
                />
              </div>
              <div className="video-caption">
                <div>
                  <div className="button-row">
                    <Pill tone="blue">课程教学视频</Pill>
                    <Pill>
                      <Clock3 size={12} />
                      {timeLabel(duration || metadata.duration || 0)}
                    </Pill>
                  </div>
                  <h2>{current.title}</h2>
                  <p>{current.content || '跟随真实课程片段学习，在互动检查中检验理解。'}</p>
                </div>
                <Link
                  className="button secondary"
                  to={`${user.role === 'teacher' ? '/teacher-ai' : '/tutor'}?course=${courseId}&knowledge=${current.knowledge_id || ''}&t=${Math.floor(position)}&resource=${current.id}`}
                >
                  <Sparkles size={16} />
                  问问这个片段
                </Link>
              </div>
            </div>
            <Panel className="video-sidebar">
              <div className="tab-line">
                {[
                  ['transcript', '字幕检索'],
                  ['notes', `我的笔记 ${notes.data.length}`],
                  ['catalog', '课程目录'],
                  ['segments', '片段与检查'],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    className={tab === value ? 'active' : ''}
                    onClick={() => setTab(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === 'transcript' ? (
                <>
                  <div className="search-box">
                    <Search size={16} />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      aria-label="搜索视频字幕"
                      placeholder="检索字幕中的关键词…"
                    />
                  </div>
                  <div className="transcript-list">
                    {subtitles
                      .filter((s) => !search || String(s.text || s.content).includes(search))
                      .map((s, i) => (
                        <button
                          key={i}
                          className={
                            position >= Number(s.start ?? s.time ?? 0) &&
                            position < Number(s.end ?? Number(s.start ?? s.time ?? 0) + 10)
                              ? 'active'
                              : ''
                          }
                          onClick={() => seek(Number(s.start ?? s.time ?? 0))}
                        >
                          <time>{timeLabel(Number(s.start ?? s.time ?? 0))}</time>
                          <span>{s.text || s.content}</span>
                        </button>
                      ))}
                    {!subtitles.length ? (
                      <Empty>教师尚未添加字幕，可先观看视频并记录笔记。</Empty>
                    ) : null}
                  </div>
                </>
              ) : tab === 'segments' ? (
                <>
                  {' '}
                  <Panel title="知识片段导航" caption="点击时间点，直接抵达对应的讲解">
                    <div className="video-timeline">
                      {timeline.length ? (
                        timeline.map((item, i) => (
                          <button
                            key={i}
                            onClick={() =>
                              seek(Number(item.time ?? item.start ?? item.timestamp ?? 0))
                            }
                          >
                            <span>
                              <Play size={13} />
                              {timeLabel(Number(item.time ?? item.start ?? item.timestamp ?? 0))}
                            </span>
                            <strong>{item.title || item.text || '知识片段'}</strong>
                            <small>定位播放</small>
                          </button>
                        ))
                      ) : (
                        <button onClick={() => seek(0)}>
                          <span>
                            <Play size={13} />
                            00:00
                          </span>
                          <strong>从课程开头开始</strong>
                          <small>定位播放</small>
                        </button>
                      )}
                    </div>
                    {checkpoints.length ? (
                      <div className="video-checkpoints">
                        {checkpoints.map((cp, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              const q = questions.data.find((q) => q.id === cp.question_id)
                              if (q) {
                                video.current?.pause()
                                setCheckpoint(q)
                                setResult(null)
                                setAnswer('')
                              } else seek(Number(cp.time ?? cp.timestamp ?? 15))
                            }}
                          >
                            <CheckCheck size={16} />
                            随堂理解检查 {i + 1}
                            <ArrowRight size={14} />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </Panel>
                </>
              ) : tab === 'notes' ? (
                <>
                  <form onSubmit={saveNote} className="note-composer">
                    <label>
                      记录此刻的思考 <Pill tone="blue">{timeLabel(position)}</Pill>
                      <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="想明白了什么？还有什么问题？"
                        rows={3}
                        maxLength={2000}
                      />
                    </label>
                    <Button variant="small" disabled={!note.trim()}>
                      <Save size={14} />
                      保存笔记
                    </Button>
                  </form>
                  <div className="notes-list">
                    {notes.data.map((n) => (
                      <div key={n.id}>
                        <button className="note-time" onClick={() => seek(n.timestamp || 0)}>
                          <Play size={12} />
                          {timeLabel(n.timestamp || 0)}
                        </button>
                        <p>{n.content}</p>
                        <button
                          className="icon-button"
                          title="删除笔记"
                          aria-label="删除笔记"
                          onClick={async () => {
                            try {
                              await api(`/notes/${n.id}`, { method: 'DELETE' })
                              notes.reload()
                            } catch (e) {
                              notify((e as Error).message, true)
                            }
                          }}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="video-catalog">
                  {videoResources.map((r, i) => (
                    <button
                      className={r.id === current.id ? 'active' : ''}
                      key={r.id}
                      onClick={() => {
                        setChosen(r.id)
                        setTab('transcript')
                      }}
                    >
                      <span>{String(i + 1).padStart(2, '0')}</span>
                      <div>
                        <strong>{r.title}</strong>
                        <small>视频课程</small>
                      </div>
                      <Play size={15} />
                    </button>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      ) : !resources.loading ? (
        <Panel>
          <Empty
            action={
              teacher ? (
                <Link to="/resources" className="button">
                  上传教学视频
                </Link>
              ) : undefined
            }
          >
            当前课程还没有视频资源。
          </Empty>
        </Panel>
      ) : null}
      {checkpoint ? (
        <Modal
          title="停一停，做一次理解检查"
          close={() => {
            setCheckpoint(null)
            video.current?.play().catch(() => {})
          }}
        >
          <form className="form-stack" onSubmit={answerCheck}>
            <Pill tone="green">当前视频随堂题</Pill>
            <h3>{checkpoint.title}</h3>
            <AnswerInput
              question={checkpoint}
              answer={answer}
              setAnswer={setAnswer}
              disabled={Boolean(result)}
            />
            {result ? (
              <div className={`answer-feedback ${result.correct ? 'correct' : 'incorrect'}`}>
                <h3>{result.correct ? '回答正确' : '继续理清概念'}</h3>
                <p>{result.explanation}</p>
                <Pill>掌握度 {percent(result.mastery)}%</Pill>
              </div>
            ) : (
              <Button type="submit" disabled={!answer.length}>
                <CheckCheck size={16} />
                提交检查
              </Button>
            )}
            {result ? (
              <Button
                type="button"
                onClick={() => {
                  setCheckpoint(null)
                  video.current?.play().catch(() => {})
                }}
              >
                <Play size={16} />
                继续观看
              </Button>
            ) : null}
          </form>
        </Modal>
      ) : null}
      {edit && current ? (
        <Modal title="视频字幕与互动时间轴" close={() => setEdit(false)}>
          <VideoTimelineEditor
            resource={current}
            measuredDuration={duration}
            questions={questions.data}
            saved={() => {
              resources.reload()
              setEdit(false)
            }}
          />
        </Modal>
      ) : null}
    </>
  )
}

type SubtitleDraft = { key: string; start: string; end: string; text: string; original: Row }
type SegmentDraft = { key: string; time: string; title: string; knowledgeId: string; original: Row }
type CheckpointDraft = { key: string; time: string; questionId: string; original: Row }
const editorKey = () => crypto.randomUUID()
const editorSectionStyle = { borderTop: '1px solid #e7ebf2', paddingTop: 20 }
const editorRowStyle = {
  padding: 15,
  border: '1px solid #e7ebf2',
  borderRadius: 8,
  background: '#fbfcfe',
}

function VideoTimelineEditor({
  resource,
  measuredDuration,
  questions,
  saved,
}: {
  resource: Row
  measuredDuration: number
  questions: Row[]
  saved: () => void
}) {
  const { courseId, notify } = useApp()
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const metadata: Row = resource.metadata || {}
  const initialSubtitles: Row[] = metadata.subtitles || metadata.transcript || []
  const initialSegments: Row[] = metadata.timeline || metadata.chapters || []
  const initialChecks: Row[] =
    metadata.checkpoints ||
    (metadata.checkpoint_question_id
      ? [{ time: metadata.checkpoint_time || 15, question_id: metadata.checkpoint_question_id }]
      : [])
  const [title, setTitle] = useState(String(resource.title || ''))
  const [length, setLength] = useState(
    String(
      metadata.duration ??
        (Number.isFinite(measuredDuration) ? Math.round(measuredDuration * 10) / 10 : 0),
    ),
  )
  const [editorView, setEditorView] = useState('subtitle')
  const [subtitles, setSubtitles] = useState<SubtitleDraft[]>(() =>
    initialSubtitles.map((s) => ({
      key: editorKey(),
      start: String(s.start ?? s.time ?? 0),
      end: String(s.end ?? Number(s.start ?? s.time ?? 0) + 5),
      text: String(s.text ?? s.content ?? ''),
      original: s,
    })),
  )
  const [segments, setSegments] = useState<SegmentDraft[]>(() =>
    initialSegments.map((s) => ({
      key: editorKey(),
      time: String(s.time ?? s.start ?? s.timestamp ?? 0),
      title: String(s.title ?? s.text ?? ''),
      knowledgeId: String(s.knowledge_id ?? ''),
      original: s,
    })),
  )
  const [checks, setChecks] = useState<CheckpointDraft[]>(() =>
    initialChecks.map((s) => ({
      key: editorKey(),
      time: String(s.time ?? s.timestamp ?? s.start ?? 0),
      questionId: String(s.question_id ?? ''),
      original: s,
    })),
  )
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function timeValue(value: string, label: string, videoLength: number) {
    const number = Number(value)
    if (!value.trim() || !Number.isFinite(number) || number < 0 || number > videoLength)
      throw new Error(`${label}需在 0 到 ${videoLength} 秒之间。`)
    return number
  }
  // 兼容已有片段记录的时间字段，同时保留教师没有编辑的扩展信息。
  function syncTimeAliases(original: Row, time: number) {
    const next: Row & { time: number } = { ...original, time }
    if ('timestamp' in original) next.timestamp = time
    if ('start' in original) next.start = time
    return next
  }
  async function save(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const videoLength = Number(length)
      if (!title.trim()) throw new Error('请填写视频标题。')
      if (
        !length.trim() ||
        !Number.isFinite(videoLength) ||
        videoLength <= 0 ||
        videoLength > 86400
      )
        throw new Error('视频时长需大于 0 秒，且不超过 86400 秒。')
      const nextSubtitles = subtitles
        .map((s, i) => {
          const start = timeValue(s.start, `字幕 ${i + 1} 的开始时间`, videoLength)
          const end = timeValue(s.end, `字幕 ${i + 1} 的结束时间`, videoLength)
          if (end <= start) throw new Error(`字幕 ${i + 1} 的结束时间需晚于开始时间。`)
          if (!s.text.trim()) throw new Error(`请填写字幕 ${i + 1} 的文字内容。`)
          const next: Row & { start: number; end: number; text: string } = {
            ...s.original,
            start,
            end,
            text: s.text.trim(),
          }
          if ('time' in s.original) next.time = start
          if ('timestamp' in s.original) next.timestamp = start
          if ('content' in s.original) next.content = s.text.trim()
          return next
        })
        .sort((a, b) => a.start - b.start)
      const nextSegments = segments
        .map((s, i) => {
          const time = timeValue(s.time, `知识片段 ${i + 1} 的时间`, videoLength)
          if (!s.title.trim()) throw new Error(`请填写知识片段 ${i + 1} 的名称。`)
          const knowledgeId = s.knowledgeId ? Number(s.knowledgeId) : null
          if (knowledgeId !== null && !graph.data.nodes.some((n: Row) => n.id === knowledgeId))
            throw new Error(`请选择知识片段 ${i + 1} 在当前课程内的关联知识。`)
          return {
            ...syncTimeAliases(s.original, time),
            title: s.title.trim(),
            knowledge_id: knowledgeId,
          }
        })
        .sort((a, b) => a.time - b.time)
      const usedQuestions = new Set<number>()
      const nextChecks = checks
        .map((s, i) => {
          const time = timeValue(s.time, `互动检查 ${i + 1} 的时间`, videoLength)
          const questionId = Number(s.questionId)
          if (!questions.some((q) => q.id === questionId))
            throw new Error(`请为互动检查 ${i + 1} 选择当前课程的题目。`)
          if (usedQuestions.has(questionId))
            throw new Error('同一道检查题只需设置一次，请为其他检查点选择不同题目。')
          usedQuestions.add(questionId)
          return { ...syncTimeAliases(s.original, time), question_id: questionId }
        })
        .sort((a, b) => a.time - b.time)
      const nextMetadata: Row = {
        ...metadata,
        duration: videoLength,
        subtitles: nextSubtitles,
        timeline: nextSegments,
        checkpoints: nextChecks,
      }
      if ('checkpoint_question_id' in metadata) {
        if (nextChecks.length) {
          nextMetadata.checkpoint_question_id = nextChecks[0].question_id
          nextMetadata.checkpoint_time = nextChecks[0].time
        } else {
          delete nextMetadata.checkpoint_question_id
          delete nextMetadata.checkpoint_time
        }
      }
      setSaving(true)
      await patch(`/resources/${resource.id}`, { title: title.trim(), metadata: nextMetadata })
      notify('视频字幕、知识片段与互动检查已保存')
      saved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }
  return (
    <form className="form-stack" onSubmit={save}>
      <p className="muted">
        按播放秒数安排讲解与互动。字幕、知识片段和检查题会按时间自动排序，保存后学生即可看到。
      </p>
      <label>
        视频标题
        <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <div className="button-row" style={{ alignItems: 'flex-end' }}>
        <label style={{ flex: 1 }}>
          视频时长（秒）
          <input
            type="number"
            min={0.1}
            max={86400}
            step="any"
            required
            value={length}
            onChange={(e) => setLength(e.target.value)}
          />
        </label>
        {measuredDuration > 0 && Number.isFinite(measuredDuration) ? (
          <Button
            type="button"
            variant="secondary small"
            onClick={() => setLength(String(Math.round(measuredDuration * 10) / 10))}
          >
            使用实际时长 {timeLabel(measuredDuration)}
          </Button>
        ) : null}
      </div>
      <Tabs
        value={editorView}
        onChange={setEditorView}
        items={[
          ['subtitle', '字幕'],
          ['segment', '知识片段'],
          ['check', '理解检查'],
        ]}
      />
      <section
        hidden={editorView !== 'subtitle'}
        style={editorSectionStyle}
        aria-labelledby="subtitle-editor-heading"
      >
        <div className="panel-head">
          <div>
            <h3 id="subtitle-editor-heading">字幕内容</h3>
            <p>设置每段字幕出现与结束的时间。</p>
          </div>
          <Button
            type="button"
            variant="secondary small"
            onClick={() =>
              setSubtitles((rows) => [
                ...rows,
                { key: editorKey(), start: '', end: '', text: '', original: {} },
              ])
            }
          >
            <Plus size={14} />
            添加字幕
          </Button>
        </div>
        <div className="form-stack">
          {subtitles.map((row, index) => (
            <div className="form-stack" style={editorRowStyle} key={row.key}>
              <div className="button-row" style={{ justifyContent: 'space-between' }}>
                <Pill tone="blue">字幕 {index + 1}</Pill>
                <Button
                  type="button"
                  variant="ghost small"
                  aria-label={`删除字幕 ${index + 1}`}
                  onClick={() => setSubtitles((rows) => rows.filter((s) => s.key !== row.key))}
                >
                  <Trash2 size={14} />
                  删除
                </Button>
              </div>
              <div className="form-columns">
                <label>
                  开始时间（秒）
                  <input
                    aria-label={`字幕 ${index + 1} 开始时间（秒）`}
                    type="number"
                    min={0}
                    max={Number(length) || 86400}
                    step="any"
                    required
                    value={row.start}
                    onChange={(e) =>
                      setSubtitles((rows) =>
                        rows.map((s) => (s.key === row.key ? { ...s, start: e.target.value } : s)),
                      )
                    }
                  />
                </label>
                <label>
                  结束时间（秒）
                  <input
                    aria-label={`字幕 ${index + 1} 结束时间（秒）`}
                    type="number"
                    min={0}
                    max={Number(length) || 86400}
                    step="any"
                    required
                    value={row.end}
                    onChange={(e) =>
                      setSubtitles((rows) =>
                        rows.map((s) => (s.key === row.key ? { ...s, end: e.target.value } : s)),
                      )
                    }
                  />
                </label>
              </div>
              <label>
                字幕文字
                <textarea
                  aria-label={`字幕 ${index + 1} 文字`}
                  rows={2}
                  maxLength={5000}
                  required
                  value={row.text}
                  onChange={(e) =>
                    setSubtitles((rows) =>
                      rows.map((s) => (s.key === row.key ? { ...s, text: e.target.value } : s)),
                    )
                  }
                />
              </label>
            </div>
          ))}
          {!subtitles.length ? (
            <p className="muted mini-text">还没有字幕。添加后，学生可以搜索文字并定位播放。</p>
          ) : null}
        </div>
      </section>
      <section
        hidden={editorView !== 'segment'}
        style={editorSectionStyle}
        aria-labelledby="segment-editor-heading"
      >
        <div className="panel-head">
          <div>
            <h3 id="segment-editor-heading">知识片段导航</h3>
            <p>为讲解片段设置入口，并关联课程知识点。</p>
          </div>
          <Button
            type="button"
            variant="secondary small"
            onClick={() =>
              setSegments((rows) => [
                ...rows,
                { key: editorKey(), time: '', title: '', knowledgeId: '', original: {} },
              ])
            }
          >
            <Plus size={14} />
            添加知识片段
          </Button>
        </div>
        <LoadState {...graph} retry={graph.reload} />
        <div className="form-stack">
          {segments.map((row, index) => (
            <div className="form-stack" style={editorRowStyle} key={row.key}>
              <div className="button-row" style={{ justifyContent: 'space-between' }}>
                <Pill tone="green">知识片段 {index + 1}</Pill>
                <Button
                  type="button"
                  variant="ghost small"
                  aria-label={`删除知识片段 ${index + 1}`}
                  onClick={() => setSegments((rows) => rows.filter((s) => s.key !== row.key))}
                >
                  <Trash2 size={14} />
                  删除
                </Button>
              </div>
              <div className="form-columns">
                <label>
                  定位时间（秒）
                  <input
                    aria-label={`知识片段 ${index + 1} 定位时间（秒）`}
                    type="number"
                    min={0}
                    max={Number(length) || 86400}
                    step="any"
                    required
                    value={row.time}
                    onChange={(e) =>
                      setSegments((rows) =>
                        rows.map((s) => (s.key === row.key ? { ...s, time: e.target.value } : s)),
                      )
                    }
                  />
                </label>
                <label>
                  关联知识点
                  <select
                    aria-label={`知识片段 ${index + 1} 关联知识点`}
                    value={row.knowledgeId}
                    onChange={(e) =>
                      setSegments((rows) =>
                        rows.map((s) =>
                          s.key === row.key ? { ...s, knowledgeId: e.target.value } : s,
                        ),
                      )
                    }
                  >
                    <option value="">不关联特定知识点</option>
                    {graph.data.nodes.map((n: Row) => (
                      <option value={n.id} key={n.id}>
                        {n.title}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                片段名称
                <input
                  aria-label={`知识片段 ${index + 1} 名称`}
                  maxLength={200}
                  required
                  value={row.title}
                  onChange={(e) =>
                    setSegments((rows) =>
                      rows.map((s) => (s.key === row.key ? { ...s, title: e.target.value } : s)),
                    )
                  }
                />
              </label>
            </div>
          ))}
          {!segments.length ? (
            <p className="muted mini-text">还没有知识片段。添加后，学生可从课程时间轴直接定位。</p>
          ) : null}
        </div>
      </section>
      <section
        hidden={editorView !== 'check'}
        style={editorSectionStyle}
        aria-labelledby="checkpoint-editor-heading"
      >
        <div className="panel-head">
          <div>
            <h3 id="checkpoint-editor-heading">随堂互动检查</h3>
            <p>播放到指定时刻暂停，让学生用题目检验理解。</p>
          </div>
          <Button
            type="button"
            variant="secondary small"
            onClick={() =>
              setChecks((rows) => [
                ...rows,
                { key: editorKey(), time: '', questionId: '', original: {} },
              ])
            }
          >
            <Plus size={14} />
            添加检查点
          </Button>
        </div>
        <div className="form-stack">
          {checks.map((row, index) => (
            <div className="form-stack" style={editorRowStyle} key={row.key}>
              <div className="button-row" style={{ justifyContent: 'space-between' }}>
                <Pill tone="amber">互动检查 {index + 1}</Pill>
                <Button
                  type="button"
                  variant="ghost small"
                  aria-label={`删除检查点 ${index + 1}`}
                  onClick={() => setChecks((rows) => rows.filter((s) => s.key !== row.key))}
                >
                  <Trash2 size={14} />
                  删除
                </Button>
              </div>
              <label>
                暂停时间（秒）
                <input
                  aria-label={`互动检查 ${index + 1} 暂停时间（秒）`}
                  type="number"
                  min={0}
                  max={Number(length) || 86400}
                  step="any"
                  required
                  value={row.time}
                  onChange={(e) =>
                    setChecks((rows) =>
                      rows.map((s) => (s.key === row.key ? { ...s, time: e.target.value } : s)),
                    )
                  }
                />
              </label>
              <label>
                检查题目
                <select
                  aria-label={`互动检查 ${index + 1} 题目`}
                  required
                  value={row.questionId}
                  onChange={(e) =>
                    setChecks((rows) =>
                      rows.map((s) =>
                        s.key === row.key ? { ...s, questionId: e.target.value } : s,
                      ),
                    )
                  }
                >
                  <option value="">请选择当前课程题目</option>
                  {questions.map((q) => (
                    <option value={q.id} key={q.id}>
                      {q.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ))}
          {!checks.length ? (
            <p className="muted mini-text">还没有随堂检查。可从本课程题库选择题目加入视频。</p>
          ) : null}
        </div>
      </section>
      {error ? (
        <div className="error-box" role="alert">
          {error}
        </div>
      ) : null}
      <Button type="submit" disabled={saving || graph.loading || Boolean(graph.error)}>
        <Save size={16} />
        {saving ? '正在保存…' : '保存时间轴'}
      </Button>
    </form>
  )
}
