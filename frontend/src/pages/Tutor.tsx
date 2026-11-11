import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  History,
  Lightbulb,
  MessageCircle,
  Plus,
  Sparkles,
} from 'lucide-react'
import { RichText } from '../components/RichText'
import { TeachingActions } from '../components/TeachingActions'
import { AIComposer } from '../components/AIComposer'
import { TeacherDraft } from '../components/TeacherDraft'
import { api, getSession, useApi } from '../api'
import type { Row } from '../api'
import { Button, LoadState, Modal, Panel, Pill, Title, useApp } from '../ui'

type Message = {
  role: string
  content: string
  citations?: Row[]
  mode?: string
  error?: boolean
  status?: string
  teaching?: Row
  model?: string
  attachments?: Row[]
  artifact?: Row
}
export function Tutor({ teacher = false }: { teacher?: boolean }) {
  const { courseId, user, notify } = useApp()
  const [params, setParams] = useSearchParams()
  const knowledgeId = Number(params.get('knowledge')) || undefined
  const questionId = Number(params.get('question')) || undefined
  const videoTimestamp = params.has('t') ? Number(params.get('t')) : undefined
  const status = useApi<Row>('/ai/status', {})
  const history = useApi<Row[]>(`/ai/conversations?course_id=${courseId}`, [])
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<number | undefined>()
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [citations, setCitations] = useState<Row[]>([])
  const [sideOpen, setSideOpen] = useState(false)
  const [model, setModel] = useState('deepseek-flash')
  const [attachments, setAttachments] = useState<Row[]>([])
  const [source, setSource] = useState<Row | null>(null)
  const [composerKey, setComposerKey] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const historyRequest = useRef<AbortController | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const currentKnowledge = graph.data.nodes?.find((n: Row) => n.id === knowledgeId)
  useEffect(() => {
    setMessages([])
    setConversationId(undefined)
    setCitations([])
    abortRef.current?.abort()
  }, [courseId])
  useEffect(
    () => () => {
      abortRef.current?.abort()
      historyRequest.current?.abort()
    },
    [],
  )
  useEffect(() => {
    const box = end.current?.parentElement
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' })
  }, [messages])
  async function openConversation(id: number) {
    if (busy) return
    try {
      historyRequest.current?.abort()
      const controller = new AbortController()
      historyRequest.current = controller
      const conversation = await api<Row>(`/ai/conversations/${id}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      const context = conversation.context || {}
      const next = new URLSearchParams()
      next.set('course', String(context.course_id || courseId))
      if (context.knowledge_point_id) next.set('knowledge', String(context.knowledge_point_id))
      if (context.question_id) next.set('question', String(context.question_id))
      if (context.resource_id) next.set('resource', String(context.resource_id))
      if (context.video_timestamp !== null && context.video_timestamp !== undefined)
        next.set('t', String(context.video_timestamp))
      setParams(next, { replace: true })
      setMessages(conversation.messages || [])
      setConversationId(id)
      setCitations(conversation.messages?.flatMap((m: Row) => m.citations || []).slice(-5) || [])
      setSideOpen(false)
      setInput('')
      setAttachments([])
      setComposerKey(key => key + 1)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') notify((e as Error).message, true)
    }
  }
  async function send(text = input) {
    if (!text.trim() || busy) return
    const next = [
      ...messages,
      { role: 'user', content: text.trim(), attachments },
      { role: 'assistant', content: '', mode: status.data.mode, model },
    ]
    setMessages(next)
    setInput('')
    setBusy(true)
    const controller = new AbortController()
    abortRef.current = controller
    let streamError = false,
      completed = false
    try {
      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getSession()?.token || ''}`,
        },
        body: JSON.stringify({
          course_id: courseId,
          message: text,
          conversation_id: conversationId,
          knowledge_id: knowledgeId,
          question_id: questionId,
          video_timestamp: videoTimestamp,
          resource_id: Number(params.get('resource')) || undefined,
          model,
          attachment_ids: attachments.map(item => item.id),
          class_id: Number(params.get('class')) || undefined,
          request_id: crypto.randomUUID(),
        }),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '学习伙伴暂时无法响应，请稍后重试')
      }
      if (!response.body) throw new Error('当前浏览器不支持流式读取')
      const reader = response.body.getReader(),
        decoder = new TextDecoder()
      let buffer = '',
        event = 'message'
      const process = (block: string) => {
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw || raw === '[DONE]') continue
          const data = JSON.parse(raw)
          if (event === 'meta') {
            setConversationId(data.conversation_id)
            setCitations(data.citations || [])
            setMessages((v) =>
              v.map((m, i) =>
                i === v.length - 1 ? { ...m, mode: data.mode, model: data.model, citations: data.citations } : m,
              ),
            )
          }
          if (event === 'delta')
            setMessages((v) =>
              v.map((m, i) =>
                i === v.length - 1 ? { ...m, content: m.content + (data.content || '') } : m,
              ),
            )
          if (event === 'done') {
            setMessages((v) =>
              v.map((m, i) =>
                i === v.length - 1
                  ? { ...m, teaching: data.teaching, artifact: data.artifact, content: data.content ?? m.content }
                  : m,
              ),
            )
            completed = true
            setConversationId(data.conversation_id)
            setAttachments([])
          }
          if (event === 'error') {
            streamError = true
            throw new Error(data.message || '辅导服务暂时不可用')
          }
        }
      }
      while (true) {
        const chunk = await reader.read()
        if (chunk.done) break
        buffer += decoder.decode(chunk.value, { stream: true }).replace(/\r/g, '')
        let boundary
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          process(block)
        }
      }
      if (buffer.trim()) process(buffer)
      if (!completed) throw new Error('回答传输中断，内容尚未完成，可继续追问')
      history.reload()
    } catch (e) {
      const error = e as Error
      if (error.name === 'AbortError') {
        setMessages((v) =>
          v.map((m, i) => (i === v.length - 1 ? { ...m, status: 'interrupted' } : m)),
        )
      } else {
        streamError = true
        setMessages((v) =>
          v.map((m, i) =>
            i === v.length - 1
              ? {
                  ...m,
                  content: `${m.content}${m.content ? '\n\n' : ''}${error.message}`,
                  error: true,
                }
              : m,
          ),
        )
        notify(error.message, true)
      }
    } finally {
      setBusy(false)
      if (!streamError) history.reload()
    }
  }
  return (
    <>
      <Title
        title={teacher ? 'AI 教学助手' : 'AI 学习伙伴'}
        subtitle="带着课程上下文，一步步解释、追问与理解；所有建议都需要你主动思考"
        action={
          <Button variant="secondary" onClick={() => setSideOpen(!sideOpen)}>
            <History size={16} />
            对话历史
          </Button>
        }
      />
      <div className={`tutor-layout ${sideOpen ? 'show-history' : ''}`}>
        <aside className="conversation-list">
          <Button
            variant="secondary wide"
            onClick={() => {
              if (busy) return
              setMessages([])
              setConversationId(undefined)
              setCitations([])
              setInput('')
              setAttachments([])
              setComposerKey(key => key + 1)
            }}
          >
            <Plus size={17} />
            开启新对话
          </Button>
          <h3>最近对话</h3>
          <LoadState {...history} retry={history.reload} />
          {history.data.map((h) => (
            <button
              key={h.id}
              className={conversationId === h.id ? 'active' : ''}
              onClick={() => openConversation(h.id)}
            >
              <MessageCircle size={16} />
              <span>{h.title || '课程学习对话'}</span>
              <ChevronRight size={14} />
            </button>
          ))}
          {!history.loading && !history.data.length ? (
            <p className="mini-text muted">你的课程对话会保存在这里，随时可以接续。</p>
          ) : null}
        </aside>
        <Panel className="chat-panel">
          <div className="chat-context">
            <span className="ai-avatar">
              <Sparkles size={19} />
            </span>
            <div>
              <strong>{teacher ? '教学研讨' : '学脉学习伙伴'}</strong>
              <small>
                {currentKnowledge
                  ? `正在讨论：${currentKnowledge.title}`
                  : questionId
                    ? '已带入当前习题与课程上下文'
                    : videoTimestamp !== undefined
                      ? `已带入视频 ${Math.floor(videoTimestamp)} 秒附近上下文`
                      : '基于当前课程资料回答'}
              </small>
            </div>
          </div>
          <div className="chat-messages" aria-live="polite">
            {!messages.length ? (
              <div className="chat-welcome">
                <div className="ai-welcome-icon">
                  <Sparkles size={33} />
                </div>
                <h2>{currentKnowledge?.title || '从一个问题开始'}</h2>
                <div className="starter-prompts">
                  {[
                    teacher ? '这个班在队列和栈的应用题上有哪些典型错误？安排40分钟讲评课和两组后续练习。' : knowledgeId
                      ? `请用一个例子解释${currentKnowledge?.title || '这个知识点'}`
                      : '栈和队列为什么有不同的应用场景？',
                    teacher ? '结合当前课程资料，设计一节有先修检查和课后复测的教学课。' : questionId
                      ? '请先给这道题一点提示，不要直接告诉我答案'
                      : '树的前序、中序、后序遍历怎么区分？',
                    teacher ? '查看这个班的学习证据，哪些知识点需要优先关注？' : '请用一个理解检查题，帮助我检验是否掌握',
                  ].map((p) => (
                    <button key={p} onClick={() => send(p)}>
                      <Lightbulb size={16} />
                      {p}
                      <ArrowRight size={15} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={`chat-message ${m.role} ${m.error ? 'error' : ''}`}>
                  <span className={`message-avatar ${m.role}`}>
                    {m.role === 'user' ? user.name.slice(0, 1) : <Sparkles size={17} />}
                  </span>
                  <div>
                    <div className="message-label">
                      {m.role === 'user' ? '你' : teacher ? '教学助手' : '学习伙伴'}
                      {m.role !== 'user' ? (
                        <small>{m.model === 'deepseek-v4-pro' ? 'DeepSeek Pro' : 'DeepSeek Flash'}{m.mode === 'mock' ? ' · 本地样例' : ''}</small>
                      ) : null}
                    </div>
                    {m.status === 'interrupted' ? (
                      <Pill tone="amber">回答未完成，可继续追问</Pill>
                    ) : null}
                    <div className="message-content">
                      {m.content ? (
                        <RichText>{m.content}</RichText>
                      ) : busy ? (
                        <span className="thinking">
                          <i />
                          <i />
                          <i />
                          正在结合课程内容思考
                        </span>
                      ) : (
                        '对话已停止。你可以继续追问。'
                      )}
                    </div>
                    {m.attachments?.length ? <div className="message-attachments">{m.attachments.map(file => <button key={file.id} onClick={async () => {
                      try { const detail = await api<Row>(`/ai/attachments/${file.id}`); setSource({ title: detail.filename, excerpt: detail.chunks.map((chunk: Row) => `${chunk.locator}\n${chunk.content}`).join('\n\n') }) } catch (error) { notify((error as Error).message, true) }
                    }}>{file.filename}</button>)}</div> : null}
                    {m.teaching && !teacher ? <TeachingActions teaching={m.teaching} /> : null}
                    {m.teaching && teacher ? <details className="collaboration-trace"><summary>教学依据与处理过程</summary><ol>{m.teaching.trace?.map((step: Row, index: number) => <li key={index}><strong>{step.role}</strong><span>{typeof step.result === 'string' ? step.result : JSON.stringify(step.result)}</span></li>)}</ol></details> : null}
                    {teacher && m.artifact ? <TeacherDraft artifact={m.artifact} evidence={m.teaching?.evidence} /> : null}
                    {m.citations?.length ? (
                      <div className="message-sources">
                        {m.citations.map((c, n) => (
                          <button type="button" key={c.id || n} onClick={() => setSource(c)}>
                            <BookOpen size={12} />[{n + 1}] {c.title}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))
            )}
            <div ref={end} />
          </div>
          <AIComposer key={composerKey} value={input} onChange={setInput} model={model} setModel={setModel} attachments={attachments} setAttachments={setAttachments} conversationId={conversationId} busy={busy} send={() => send()} stop={() => abortRef.current?.abort()} teacher={teacher} />
          <p className="ai-disclosure">回答供学习参考，可对照课程资料核对。</p>
        </Panel>
        <aside className="context-aside">
          <Panel title="这次对话的知识依据" caption="只检索你有权限访问的课程内容">
            {citations.length ? (
              citations.map((c, i) => (
                <div className="citation-card" key={c.id || i}>
                  <Pill tone="blue">资料 {i + 1}</Pill>
                  <h3>{c.title}</h3>
                  <p>
                    {String(c.excerpt || '')
                      .replace(/^#+\s*/gm, '')
                      .slice(0, 180)}
                    {String(c.excerpt || '').length > 180 ? '…' : ''}
                  </p>
                  {c.url ? (
                    <button className="text-link" onClick={() => setSource(c)}>
                      查看来源
                      <ArrowRight size={13} />
                    </button>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="tutor-tip">
                <BookOpen size={26} />
                <p>提问后，会在这里显示检索到的资料依据与课程片段。</p>
              </div>
            )}
          </Panel>
        </aside>
      </div>
      {source && <Modal title={source.title} close={() => setSource(null)}><p className="mini-text">{source.locator}{source.version ? ` · 版本${source.version}` : ''}</p><RichText>{source.excerpt || ''}</RichText></Modal>}
    </>
  )
}
