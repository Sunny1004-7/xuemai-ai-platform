import { useCallback, useEffect, useState } from 'react'

export type Row = Record<string, any>
export type User = { id: number; name: string; role: 'student' | 'teacher'; username: string }
const KEY = 'xuemai.session.v1'
export function getSession(): { token: string; user: User } | null {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || 'null')
  } catch {
    return null
  }
}
export function saveSession(value: { token: string; user: User } | null) {
  if (value) sessionStorage.setItem(KEY, JSON.stringify(value))
  else sessionStorage.removeItem(KEY)
}
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getSession()?.token
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...options, headers })
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const error = await response.json()
      message = typeof error.detail === 'string' ? error.detail : '请检查填写内容后再试'
    } catch {
      /* 非 JSON 错误使用状态码 */
    }
    if (response.status === 401 && path !== '/auth/login') {
      saveSession(null)
      window.dispatchEvent(new Event('session-expired'))
    }
    throw new Error(message)
  }
  return response.status === 204 ? undefined : response.json()
}
export const post = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const patch = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export function useApi<T>(path: string | null, initial: T) {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const reload = useCallback(() => setRevision((x) => x + 1), [])
  useEffect(() => {
    if (!path) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setError('')
    api<T>(path, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [path, revision])
  return { data, setData, loading, error, reload }
}
export function percent(value: unknown) {
  const n = Number(value) || 0
  // API 的百分比字段统一为 0–100；1% 不得误显示为 100%。
  return Math.round(Math.max(0, Math.min(100, n)))
}
