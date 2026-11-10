import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'
import { AlertCircle, ArrowRight, Check, LoaderCircle, RefreshCw, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { User } from './api'

export const AppContext = createContext<{
  user: User
  courseId: number
  setCourseId: (id: number) => void
  notify: (s: string, error?: boolean) => void
}>({} as any)
export const useApp = () => useContext(AppContext)
export function Button({
  children,
  variant = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string }) {
  return (
    <button {...props} className={`button ${variant} ${props.className || ''}`}>
      {children}
    </button>
  )
}
export function Title({ title, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
      </div>
      {action}
    </div>
  )
}
export function Panel({
  title,
  children,
  action,
  className = '',
}: {
  title?: string
  caption?: string
  children: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {title ? (
        <div className="panel-head">
          <div>
            <h2>{title}</h2>
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  )
}
export function Empty({
  children = '这里还没有内容',
  action,
}: {
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <div className="empty-orbit">
        <Check size={21} />
      </div>
      <p>{children}</p>
      {action}
    </div>
  )
}
export function LoadState({
  loading,
  error,
  retry,
}: {
  loading: boolean
  error: string
  retry?: () => void
}) {
  if (loading)
    return (
      <div className="loading" role="status">
        <LoaderCircle className="spin" size={20} />
        正在加载…
      </div>
    )
  if (error)
    return (
      <div className="error-box" role="alert">
        <AlertCircle size={18} />
        <span>{error}</span>
        {retry ? (
          <Button variant="small ghost" onClick={retry}>
            <RefreshCw size={14} />
            重试
          </Button>
        ) : null}
      </div>
    )
  return null
}
export function Progress({ value, color }: { value: number; color?: string }) {
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label="掌握进度"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  )
}
export function Pill({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`pill ${tone}`}>{children}</span>
}
export function Go({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link className="text-link" to={to}>
      {children}
      <ArrowRight size={15} />
    </Link>
  )
}
export function Modal({
  title,
  children,
  close,
}: {
  title: string
  children: ReactNode
  close: () => void
}) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <section className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="panel-head">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={close}>
            <X />
          </button>
        </div>
        {children}
      </section>
    </div>
  )
}
export const typeLabels: Record<string, string> = {
  single: '单选题',
  multiple: '多选题',
  boolean: '判断题',
  fill: '填空题',
  short: '简答题',
  step: '分步题',
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  fill_blank: '填空题',
  short_answer: '简答题',
}
export function dateLabel(value: string) {
  if (!value?.trim()) return '暂未设置'
  const raw = value.trim()
  const explicitZone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(raw)
  const normalized = explicitZone
    ? raw.replace(' ', 'T')
    : raw.includes(' ')
      ? `${raw.replace(' ', 'T')}Z`
      : raw.includes('T')
        ? `${raw}+08:00`
        : `${raw}T00:00:00+08:00`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return '暂未设置'
  return `${date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Shanghai' })}（北京时间）`
}
