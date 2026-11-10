import { useState } from 'react'
import { Link } from 'react-router-dom'
import { post, useApi } from '../api'
import type { Row } from '../api'
import { Button, dateLabel, useApp } from '../ui'

export function TeachingActions({ teaching }: { teaching: Row }) {
  const check = teaching.check
  return (
    <div className="teaching-actions">
      <div className="button-row">
        {(teaching.actions || [])
          .filter((a: Row) => a.href)
          .map((action: Row) => (
            <Link className="button secondary small" key={action.kind} to={action.href}>
              {action.title}
            </Link>
          ))}
      </div>
      {check ? <UnderstandingCheck key={check.id} check={check} /> : null}
    </div>
  )
}

function UnderstandingCheck({ check }: { check: Row }) {
  const { notify } = useApp()
  const saved = useApi<Row>(`/ai/checks/${check.id}`, {})
  const [answer, setAnswer] = useState<string | string[]>('')
  const [result, setResult] = useState<Row | null>(null)
  const [busy, setBusy] = useState(false)
  const feedback = result || saved.data.result
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      setResult(await post(`/ai/checks/${check.id}/answer`, { answer }))
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="understanding-check" aria-label="理解检查">
      <h3>理解检查</h3>
      <p>{check.title}</p>
      {feedback ? (
        <div role="status">
          <strong>{feedback.correct ? '检查通过' : '需要再巩固'}</strong>
          <p>{feedback.explanation}</p>
          {feedback.evidence ? (
            <small>
              {feedback.evidence.sufficiency} · 有效证据{' '}
              {Number(feedback.evidence.effective_count).toFixed(1)}
            </small>
          ) : null}
          {feedback.review_schedule ? (
            <p>下次复习：{dateLabel(feedback.review_schedule.next_due)}</p>
          ) : null}
          {feedback.next_action ? (
            <Link className="text-link" to={feedback.next_action.href}>
              {feedback.next_action.title} →
            </Link>
          ) : null}
        </div>
      ) : (
        <form onSubmit={submit}>
          {check.options?.length ? (
            <div className="check-options">
              {check.options.map((option: string) => (
                <label key={option}>
                  <input
                    type={check.type === 'multiple' ? 'checkbox' : 'radio'}
                    name={`check-${check.id}`}
                    value={option}
                    checked={Array.isArray(answer) ? answer.includes(option) : answer === option}
                    onChange={(e) =>
                      setAnswer(
                        check.type === 'multiple'
                          ? e.target.checked
                            ? [...(Array.isArray(answer) ? answer : []), option]
                            : (Array.isArray(answer) ? answer : []).filter((a) => a !== option)
                          : option,
                      )
                    }
                  />
                  {option}
                </label>
              ))}
            </div>
          ) : (
            <input
              aria-label="理解检查答案"
              value={String(answer)}
              onChange={(e) => setAnswer(e.target.value)}
            />
          )}
          <Button variant="small" disabled={busy || saved.loading || !answer.length}>
            {busy ? '正在检查…' : '提交理解检查'}
          </Button>
        </form>
      )}
    </section>
  )
}
