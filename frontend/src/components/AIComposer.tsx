import { useEffect, useRef, useState } from 'react'
import { CircleStop, FileText, Mic, Paperclip, Send, Square, X } from 'lucide-react'
import { api, useApi } from '../api'
import type { Row } from '../api'
import { Button, useApp } from '../ui'

export function AIComposer({ value, onChange, model, setModel, attachments, setAttachments, conversationId, busy, send, stop, teacher }: {
  value: string; onChange: (value: string) => void; model: string; setModel: (value: string) => void
  attachments: Row[]; setAttachments: (value: Row[]) => void; conversationId?: number
  busy: boolean; send: () => void; stop: () => void; teacher: boolean
}) {
  const { courseId, notify } = useApp()
  const models = useApi<Row>('/ai/models', { models: [] })
  const [processing, setProcessing] = useState(false)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const audioInput = useRef<HTMLInputElement>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const cancelled = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      cancelled.current = true
      recorder.current?.stop()
      stream.current?.getTracks().forEach(track => track.stop())
      controller.current?.abort()
    }
  }, [])
  useEffect(() => {
    if (!recording) return
    const timer = setInterval(() => setSeconds(value => value + 1), 1000)
    return () => clearInterval(timer)
  }, [recording])
  useEffect(() => { if (recording && seconds >= 60) recorder.current?.stop() }, [recording, seconds])
  async function upload(files: FileList | File[]) {
    if (attachments.length + files.length > 4) { notify('每条消息最多添加4个附件', true); return }
    setProcessing(true)
    controller.current = new AbortController()
    const uploaded: Row[] = []
    try {
      for (const file of Array.from(files)) {
        const body = new FormData()
        body.set('file', file)
        body.set('course_id', String(courseId))
        if (conversationId) body.set('conversation_id', String(conversationId))
        uploaded.push(await api<Row>('/ai/attachments', { method: 'POST', body, signal: controller.current.signal }))
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') notify((error as Error).message, true)
    } finally {
      if (mounted.current) { setAttachments([...attachments, ...uploaded]); setProcessing(false) }
    }
  }
  async function transcribe(file: File) {
    setProcessing(true)
    controller.current = new AbortController()
    try {
      const body = new FormData()
      body.set('file', file)
      const result = await api<Row>('/ai/voice/transcribe', { method: 'POST', body, signal: controller.current.signal })
      if (mounted.current) { onChange([value, result.text].filter(Boolean).join('\n')); notify('语音已转写，可编辑后发送') }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') notify((error as Error).message, true)
    } finally { if (mounted.current) setProcessing(false) }
  }
  async function record() {
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('当前浏览器无法录音，可上传语音文件')
      cancelled.current = false
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      const chunks: Blob[] = []
      const instance = new MediaRecorder(media)
      recorder.current = instance
      instance.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      instance.onstop = () => {
        media.getTracks().forEach(track => track.stop())
        if (!mounted.current) return
        setRecording(false)
        if (!cancelled.current) transcribe(new File(chunks, 'voice.webm', { type: instance.mimeType }))
      }
      instance.start()
      setSeconds(0)
      setRecording(true)
    } catch (error) {
      const code = (error as Error).name
      notify(code === 'NotAllowedError' ? '麦克风权限被拒绝，可在地址栏授权或上传语音' : code === 'NotFoundError' ? '未检测到麦克风，可上传语音文件' : (error as Error).message, true)
    }
  }
  const imageWithPro = model === 'deepseek-v4-pro' && attachments.some(file => file.media_type.startsWith('image/'))
  return <form className="chat-composer" onSubmit={event => { event.preventDefault(); send() }}
    onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!processing && !busy) upload(event.dataTransfer.files) }}>
    {attachments.length > 0 && <div className="composer-attachments">{attachments.map(file => <span key={file.id}><FileText size={16} /><span>{file.filename}</span><button type="button" aria-label={`移除附件${file.filename}`} disabled={busy} onClick={async () => {
      try { await api(`/ai/attachments/${file.id}`, { method: 'DELETE' }); setAttachments(attachments.filter(item => item.id !== file.id)) } catch (error) { notify((error as Error).message, true) }
    }}><X size={14} /></button></span>)}</div>}
    <label className="sr-only" htmlFor="chat-input">{teacher ? '输入教学问题' : '输入学习问题'}</label>
    <textarea id="chat-input" value={value} onChange={event => onChange(event.target.value)} rows={2} maxLength={3000}
      placeholder={teacher ? '结合课程与班级，讨论下一次教学安排…' : '写下问题，也可以添加文件或语音…'}
      onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !processing && !recording) { event.preventDefault(); send() } }} />
    {imageWithPro && <div className="composer-hint">图片由Flash处理 <button type="button" onClick={() => setModel('deepseek-flash')}>切换Flash</button></div>}
    <div className="composer-toolbar">
      <div className="composer-tools">
        <select aria-label="选择AI模型" value={model} onChange={event => setModel(event.target.value)}>{models.data.models.map((item: Row) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <button type="button" className="icon-button" aria-label="添加附件" title="添加附件" disabled={processing || busy} onClick={() => fileInput.current?.click()}><Paperclip size={19} /></button>
        <input ref={fileInput} type="file" multiple accept=".txt,.md,.pdf,.docx,.csv,.png,.jpg,.jpeg" hidden aria-label="选择问答附件" onChange={event => { if (event.target.files) upload(event.target.files); event.target.value = '' }} />
        {recording ? <><button type="button" className="voice-stop" aria-label="停止录音并转写" onClick={() => recorder.current?.stop()}><Square size={14} />{seconds}s</button><button type="button" className="icon-button" aria-label="取消录音" onClick={() => { cancelled.current = true; recorder.current?.stop() }}><X size={16} /></button></> : <button type="button" className="icon-button" title="语音输入" aria-label="开始语音输入" disabled={processing || busy} onClick={record}><Mic size={19} /></button>}
        <button type="button" className="text-link audio-upload" disabled={processing || busy || recording} onClick={() => audioInput.current?.click()}>上传语音</button>
        <input ref={audioInput} type="file" accept=".wav,.webm,.mp3,.m4a,.ogg" hidden aria-label="选择语音文件" onChange={event => { const file = event.target.files?.[0]; if (file) transcribe(file); event.target.value = '' }} />
      </div>
      {processing ? <span role="status">处理中…</span> : busy ? <Button type="button" variant="secondary small" onClick={stop}><CircleStop size={16} />停止</Button> : <Button type="submit" variant="small" disabled={!value.trim() || imageWithPro || recording}><Send size={16} />发送</Button>}
    </div>
  </form>
}
