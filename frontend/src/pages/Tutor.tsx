import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  CircleStop,
  History,
  Lightbulb,
  MessageCircle,
  Plus,
  Send,
  Sparkles,
} from 'lucide-react'
import { api, getSession, useApi } from '../api'
import type { Row } from '../api'
import { Button, LoadState, Panel, Pill, Title, useApp } from '../ui'

type Message = {
  role: string
  content: string
  citations?: Row[]
  mode?: string
  error?: boolean
  status?: string
}
export function Tutor() {
  const { courseId, user, notify } = useApp()
  const [params] = useSearchParams()
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
  const abortRef = useRef<AbortController | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const currentKnowledge = graph.data.nodes?.find((n: Row) => n.id === knowledgeId)
  useEffect(() => {
    setMessages([])
    setConversationId(undefined)
    setCitations([])
    abortRef.current?.abort()
  }, [courseId])
  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])
  async function openConversation(id: number) {
    if (busy) return
    try {
      const conversation = await api<Row>(`/ai/conversations/${id}`)
      setMessages(conversation.messages || [])
      setConversationId(id)
      setCitations(conversation.messages?.flatMap((m: Row) => m.citations || []).slice(-5) || [])
      setSideOpen(false)
    } catch (e) {
      notify((e as Error).message, true)
    }
  }
  async function send(text = input) {
    if (!text.trim() || busy) return
    const next = [
      ...messages,
      { role: 'user', content: text.trim() },
      { role: 'assistant', content: '', mode: status.data.mode },
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
                i === v.length - 1 ? { ...m, mode: data.mode, citations: data.citations } : m,
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
            completed = true
            setConversationId(data.conversation_id)
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
        title="陪你想明白的学习伙伴"
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
          <div className="tutor-mode">
            <span className="status-dot" />
            <div>
              <strong>
                {status.data.mode === 'real' ? 'DeepSeek 实时辅导' : '本地 Mock 演示'}
              </strong>
              <p>
                {status.data.mode === 'real'
                  ? status.data.model
                  : '使用固定示例回复，不消耗 API 额度'}
              </p>
            </div>
          </div>
        </aside>
        <Panel className="chat-panel">
          <div className="chat-context">
            <span className="ai-avatar">
              <Sparkles size={19} />
            </span>
            <div>
              <strong>学脉学习伙伴</strong>
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
            <Pill tone="green">循序引导</Pill>
          </div>
          <div className="chat-messages" aria-live="polite">
            {!messages.length ? (
              <div className="chat-welcome">
                <div className="ai-welcome-icon">
                  <Sparkles size={33} />
                </div>
                <h2>有些知识，聊着就清楚了。</h2>
                <p>
                  告诉我你困惑的地方。我会结合课程资料，
                  <br />
                  陪你从「不太明白」走向「我能解释」。
                </p>
                <div className="starter-prompts">
                  {[
                    knowledgeId
                      ? `请用一个例子解释${currentKnowledge?.title || '这个知识点'}`
                      : '栈和队列为什么有不同的应用场景？',
                    questionId
                      ? '请先给这道题一点提示，不要直接告诉我答案'
                      : '树的前序、中序、后序遍历怎么区分？',
                    '请用一个理解检查题，帮助我检验是否掌握',
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
                      {m.role === 'user' ? '你' : '学习伙伴'}
                      {m.role !== 'user' ? (
                        <small>{m.mode === 'real' ? 'DeepSeek' : 'Mock 示例'}</small>
                      ) : null}
                    </div>
                    {m.status === 'interrupted' ? (
                      <Pill tone="amber">回答未完成，可继续追问</Pill>
                    ) : null}
                    <div className="message-content">
                      {m.content ||
                        (busy ? (
                          <span className="thinking">
                            <i />
                            <i />
                            <i />
                            正在结合课程内容思考
                          </span>
                        ) : (
                          '对话已停止。你可以继续追问。'
                        ))}
                    </div>
                    {m.citations?.length ? (
                      <div className="message-sources">
                        {m.citations.map((c, n) => (
                          <span key={c.id || n}>
                            <BookOpen size={12} />[{n + 1}] {c.title}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))
            )}
            <div ref={end} />
          </div>
          <form
            className="chat-composer"
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
          >
            <label className="sr-only" htmlFor="chat-input">
              输入学习问题
            </label>
            <textarea
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder="写下你的困惑，或告诉我卡在了哪一步…"
              rows={2}
              maxLength={3000}
            />
            <div>
              <span>Enter 发送 · Shift + Enter 换行</span>
              {busy ? (
                <Button
                  type="button"
                  variant="secondary small"
                  onClick={() => abortRef.current?.abort()}
                >
                  <CircleStop size={16} />
                  停止
                </Button>
              ) : (
                <Button type="submit" variant="small" disabled={!input.trim()}>
                  <Send size={16} />
                  发送
                </Button>
              )}
            </div>
          </form>
          <p className="ai-disclosure">
            AI 的解释可能存在偏差，请结合课程资料核对。
            {status.data.mode !== 'real' ? '当前为本地演示，回复不来自真实模型。' : ''}
          </p>
        </Panel>
        <aside className="context-aside">
          <Panel title="这次对话的知识依据" caption="只检索你有权限访问的课程内容">
            {citations.length ? (
              citations.map((c, i) => (
                <div className="citation-card" key={c.id || i}>
                  <Pill tone="blue">资料 {i + 1}</Pill>
                  <h3>{c.title}</h3>
                  <p>{c.excerpt}</p>
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noreferrer">
                      查看来源
                      <ArrowRight size={13} />
                    </a>
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
          <Panel title="理解，比得到答案更重要">
            <ul className="learning-tips">
              <li>说出你已经知道了什么。</li>
              <li>指出哪一步开始不确定。</li>
              <li>试着用自己的话复述。</li>
              <li>回到练习中独立检验。</li>
            </ul>
            <Link
              to={knowledgeId ? `/practice?knowledge=${knowledgeId}` : '/practice'}
              className="text-link"
            >
              做一次理解检查
              <ArrowRight size={15} />
            </Link>
          </Panel>
        </aside>
      </div>
    </>
  )
}
