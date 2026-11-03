import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, BookOpen, CheckCheck, Clock3, ListVideo, Play, Save, Search, Sparkles, X } from 'lucide-react'
import { api, getSession, patch, post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Empty, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'
import { AnswerInput } from './Practice'

export const timeLabel = (s: number) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${Math.floor(s % 60).toString().padStart(2, '0')}`
export function VideoPage() {
  const { user, courseId, notify } = useApp()
  const [params] = useSearchParams()
  const resources = useApi<Row[]>(`/resources?course_id=${courseId}`, [])
  const questions = useApi<Row[]>(`/questions?course_id=${courseId}`, [])
  const [chosen, setChosen] = useState(Number(params.get('resource')) || 0)
  const videoResources = resources.data.filter(r => r.kind === 'video')
  const current = videoResources.find(r => r.id === chosen) || videoResources[0]
  const notes = useApi<Row[]>(current ? `/notes?course_id=${courseId}&resource_id=${current.id}` : null, [])
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
  const checkpoints: Row[] = metadata.checkpoints || (metadata.checkpoint_question_id ? [{ time: metadata.checkpoint_time || 15, question_id: metadata.checkpoint_question_id }] : [])
  useEffect(() => {
    if (!current?.url) { setVideoUrl(''); return }
    if (!current.url.startsWith('/api/')) { setVideoUrl(current.url); return }
    const controller = new AbortController()
    let blobUrl = ''
    setVideoUrl('')
    fetch(current.url, { signal: controller.signal, headers: { Authorization: `Bearer ${getSession()?.token || ''}` } })
      .then(async response => { if (!response.ok) throw new Error('没有权限读取视频或文件已失效'); return response.blob() })
      .then(blob => { if (!controller.signal.aborted) { blobUrl = URL.createObjectURL(blob); setVideoUrl(blobUrl) } })
      .catch(e => { if (e.name !== 'AbortError') notify(e.message, true) })
    return () => { controller.abort(); if (blobUrl) URL.revokeObjectURL(blobUrl) }
  }, [current?.id, current?.url])
  function seek(time: number) { if (video.current) { video.current.currentTime = time; setPosition(time) } }
  useEffect(() => { shownChecks.current = new Set(); lastSaved.current = -10; setResult(null); setAnswer('') }, [current?.id])
  async function saveProgress(time: number) {
    if (!current || Math.abs(time - lastSaved.current) < 8) return
    lastSaved.current = time
    try { await post('/events', { course_id: courseId, knowledge_id: current.knowledge_id, kind: 'video_progress', payload: { resource_id: current.id, position: Math.floor(time), duration: Math.floor(duration) } }) } catch { /* 播放不会因网络失败中断 */ }
  }
  function onTime() {
    const time = video.current?.currentTime || 0; setPosition(time); saveProgress(time)
    if (!teacher) for (const cp of checkpoints) {
      const at = cp.time ?? cp.timestamp ?? cp.start ?? 15
      if (time >= at && !shownChecks.current.has(cp.question_id)) {
        const question = questions.data.find(q => q.id === cp.question_id)
        if (question) { shownChecks.current.add(cp.question_id); video.current?.pause(); setCheckpoint(question); setAnswer(''); setResult(null) }
      }
    }
  }
  async function saveNote(e: React.FormEvent) { e.preventDefault(); if (!note.trim() || !current) return; try { await post('/notes', { course_id: courseId, resource_id: current.id, knowledge_id: current.knowledge_id, timestamp: Math.floor(position), content: note }); notify('时间戳笔记已保存'); setNote(''); notes.reload() } catch (e) { notify((e as Error).message, true) } }
  async function answerCheck(e: React.FormEvent) { e.preventDefault(); if (!checkpoint) return; try { const response = await post('/attempts', { question_id: checkpoint.id, answer, hints_used: 0 }); setResult(response); await post('/events', { course_id: courseId, knowledge_id: checkpoint.knowledge_id, kind: 'video_checkpoint', payload: { resource_id: current?.id, question_id: checkpoint.id, attempt_id: response.id, correct: response.correct } }); notify('互动检查已写入学习记录') } catch (e) { notify((e as Error).message, true) } }
  async function saveMetadata(e: React.FormEvent<HTMLFormElement>) { e.preventDefault(); const f = new FormData(e.currentTarget); try { await patch(`/resources/${current.id}`, { title: f.get('title'), metadata: JSON.parse(String(f.get('metadata'))) }); notify('视频时间轴与字幕已保存'); resources.reload(); setEdit(false) } catch (e) { notify((e as Error).message, true) } }
  return <><Title title={teacher ? '让视频教学，有互动也有反馈' : '沿着课程，把知识学扎实'} subtitle={teacher ? '维护视频字幕、知识时间轴与随堂检查，跟踪学习过程' : '看一段课程，记下一个思考，再用练习确认自己的理解'} action={teacher && current ? <Button variant="secondary" onClick={() => setEdit(true)}><ListVideo size={16}/>编辑字幕与检查点</Button> : <Link to="/graph" className="button secondary"><BookOpen size={16}/>返回知识图谱</Link>}/><LoadState {...resources} retry={resources.reload}/>{current ? <><div className="video-layout"><div className="video-main"><div className="video-frame"><video key={current.id} ref={video} controls preload="metadata" src={videoUrl || undefined} onLoadedMetadata={() => { setDuration(video.current?.duration || 0); seek(Number(params.get('t')) || Number(metadata.resume_position) || 0) }} onTimeUpdate={onTime} onPause={() => saveProgress(video.current?.currentTime || 0)} onError={() => notify('视频暂时无法加载，请检查演示媒体是否已生成', true)} aria-label={current.title}/></div><div className="video-caption"><div><div className="button-row"><Pill tone="blue">课程教学视频</Pill><Pill><Clock3 size={12}/>{timeLabel(duration || metadata.duration || 0)}</Pill></div><h2>{current.title}</h2><p>{current.content || '跟随真实课程片段学习，在互动检查中检验理解。'}</p></div><Link className="button secondary" to={`/tutor?knowledge=${current.knowledge_id || ''}&t=${Math.floor(position)}&resource=${current.id}`}><Sparkles size={16}/>问问这个片段</Link></div><Panel title="知识片段导航" caption="点击时间点，直接抵达对应的讲解"><div className="video-timeline">{timeline.length ? timeline.map((item, i) => <button key={i} onClick={() => seek(Number(item.time ?? item.start ?? item.timestamp ?? 0))}><span><Play size={13}/>{timeLabel(Number(item.time ?? item.start ?? item.timestamp ?? 0))}</span><strong>{item.title || item.text || '知识片段'}</strong><small>定位播放</small></button>) : <button onClick={() => seek(0)}><span><Play size={13}/>00:00</span><strong>从课程开头开始</strong><small>定位播放</small></button>}</div>{checkpoints.length ? <div className="video-checkpoints">{checkpoints.map((cp, i) => <button key={i} onClick={() => { const q = questions.data.find(q => q.id === cp.question_id); if (q) { video.current?.pause(); setCheckpoint(q); setResult(null); setAnswer('') } else seek(Number(cp.time ?? cp.timestamp ?? 15)) }}><CheckCheck size={16}/>随堂理解检查 {i + 1}<ArrowRight size={14}/></button>)}</div> : null}</Panel></div><Panel className="video-sidebar"><div className="tab-line">{[['transcript', '字幕检索'], ['notes', `我的笔记 ${notes.data.length}`], ['catalog', '课程目录']].map(([value, label]) => <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{label}</button>)}</div>{tab === 'transcript' ? <><div className="search-box"><Search size={16}/><input value={search} onChange={e => setSearch(e.target.value)} aria-label="搜索视频字幕" placeholder="检索字幕中的关键词…"/></div><div className="transcript-list">{subtitles.filter(s => !search || String(s.text || s.content).includes(search)).map((s, i) => <button key={i} className={position >= Number(s.start ?? s.time ?? 0) && position < Number(s.end ?? (Number(s.start ?? s.time ?? 0) + 10)) ? 'active' : ''} onClick={() => seek(Number(s.start ?? s.time ?? 0))}><time>{timeLabel(Number(s.start ?? s.time ?? 0))}</time><span>{s.text || s.content}</span></button>)}{!subtitles.length ? <Empty>教师尚未添加字幕，可先观看视频并记录笔记。</Empty> : null}</div></> : tab === 'notes' ? <><form onSubmit={saveNote} className="note-composer"><label>记录此刻的思考 <Pill tone="blue">{timeLabel(position)}</Pill><textarea value={note} onChange={e => setNote(e.target.value)} placeholder="想明白了什么？还有什么问题？" rows={3} maxLength={2000}/></label><Button variant="small" disabled={!note.trim()}><Save size={14}/>保存笔记</Button></form><div className="notes-list">{notes.data.map(n => <div key={n.id}><button className="note-time" onClick={() => seek(n.timestamp || 0)}><Play size={12}/>{timeLabel(n.timestamp || 0)}</button><p>{n.content}</p><button className="icon-button" title="删除笔记" aria-label="删除笔记" onClick={async () => { try { await api(`/notes/${n.id}`, { method: 'DELETE' }); notes.reload() } catch (e) { notify((e as Error).message, true) } }}><X size={13}/></button></div>)}</div></> : <div className="video-catalog">{videoResources.map((r, i) => <button className={r.id === current.id ? 'active' : ''} key={r.id} onClick={() => { setChosen(r.id); setTab('transcript') }}><span>{String(i + 1).padStart(2, '0')}</span><div><strong>{r.title}</strong><small>视频课程</small></div><Play size={15}/></button>)}</div>}</Panel></div></> : !resources.loading ? <Panel><Empty action={teacher ? <Link to="/resources" className="button">上传教学视频</Link> : undefined}>当前课程还没有视频资源。</Empty></Panel> : null}{checkpoint ? <Modal title="停一停，做一次理解检查" close={() => { setCheckpoint(null); video.current?.play().catch(() => {}) }}><form className="form-stack" onSubmit={answerCheck}><Pill tone="green">当前视频随堂题</Pill><h3>{checkpoint.title}</h3><AnswerInput question={checkpoint} answer={answer} setAnswer={setAnswer} disabled={Boolean(result)}/>{result ? <div className={`answer-feedback ${result.correct ? 'correct' : 'incorrect'}`}><h3>{result.correct ? '回答正确' : '继续理清概念'}</h3><p>{result.explanation}</p><Pill>掌握度 {Math.round((result.mastery <= 1 ? result.mastery * 100 : result.mastery) || 0)}%</Pill></div> : <Button type="submit" disabled={!answer.length}><CheckCheck size={16}/>提交检查</Button>}{result ? <Button type="button" onClick={() => { setCheckpoint(null); video.current?.play().catch(() => {}) }}><Play size={16}/>继续观看</Button> : null}</form></Modal> : null}{edit && current ? <Modal title="视频字幕与互动时间轴" close={() => setEdit(false)}><form className="form-stack" onSubmit={saveMetadata}><label>视频标题<input name="title" defaultValue={current.title} required/></label><p className="muted">字幕 subtitles 使用 start/end/text；timeline 使用 time/title；checkpoints 使用 time/question_id，关联课程题库中的随堂题。</p><label>时间轴配置<textarea className="code-input" name="metadata" rows={15} defaultValue={JSON.stringify(metadata, null, 2)} required/></label><Button><Save size={16}/>保存时间轴</Button></form></Modal> : null}</>
}
