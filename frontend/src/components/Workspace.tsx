import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '../ui'

export function Tabs({
  value,
  onChange,
  items,
}: {
  value: string
  onChange: (value: string) => void
  items: [string, string][]
}) {
  return (
    <div className="workspace-tabs" role="tablist">
      {items.map(([id, label]) => (
        <button
          type="button"
          key={id}
          role="tab"
          aria-selected={value === id}
          className={value === id ? 'active' : ''}
          onClick={() => onChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export function Pager({
  page,
  count,
  size,
  onChange,
  label = '记录',
}: {
  page: number
  count: number
  size: number
  onChange: (page: number) => void
  label?: string
}) {
  const pages = Math.max(1, Math.ceil(count / size))
  return (
    <nav className="workspace-pager" aria-label={`${label}分页`}>
      <span>
        共 {count} {label}
      </span>
      <div>
        <Button
          variant="secondary small"
          aria-label={`${label}上一页`}
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={16} />
        </Button>
        <span>
          {Math.min(page, pages)} / {pages}
        </span>
        <Button
          variant="secondary small"
          aria-label={`${label}下一页`}
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={16} />
        </Button>
      </div>
    </nav>
  )
}

export function usePage<T>(items: T[], rowHeight = 90, reserve = 330) {
  const [height, setHeight] = useState(window.innerHeight)
  const [page, setPage] = useState(1)
  const [measured, setMeasured] = useState<{ height: number; row: number } | null>(null)
  const [element, setElement] = useState<HTMLDivElement | null>(null)
  const listRef = useCallback((node: HTMLDivElement | null) => setElement(node), [])
  const size = Math.max(1, Math.min(10, Math.floor(measured ? measured.height / measured.row : (height - reserve) / rowHeight)))
  useEffect(() => {
    if (!element) return
    const measure = () => {
      const children = Array.from(element.children) as HTMLElement[]
      const row = Math.max(rowHeight, ...children.map(child => child.getBoundingClientRect().height))
      const available = element.clientHeight
      if (available > 0) setMeasured(previous => previous?.height === available && previous.row === row ? previous : { height: available, row })
    }
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    Array.from(element.children).forEach(child => observer.observe(child))
    document.fonts.ready.then(measure)
    measure()
    return () => observer.disconnect()
  }, [element, items.length, rowHeight, page, size])
  const count = items.length
  useEffect(() => {
    const resize = () => setHeight(window.innerHeight)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  useEffect(() => setPage(1), [count, size])
  const current = Math.min(page, Math.max(1, Math.ceil(count / size)))
  return {
    rows: items.slice((current - 1) * size, current * size),
    page: current,
    setPage,
    size,
    count,
    listRef,
  }
}
