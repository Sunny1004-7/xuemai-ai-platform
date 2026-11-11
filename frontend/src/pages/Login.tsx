import { useState } from 'react'
import { Activity, ArrowRight, BookOpen, Eye, EyeOff, GraduationCap } from 'lucide-react'
import { post, saveSession } from '../api'
import { Button } from '../ui'

/** 原创书页结构：知识沿着书脊汇合，双端共用构图与各自的宋式色板。 */
function LearningPages() {
  return (
    <svg className="learning-pages" viewBox="0 0 600 440" aria-hidden="true">
      <ellipse cx="294" cy="375" rx="220" ry="22" fill="currentColor" opacity=".05" />
      <path d="M73 152 280 83 516 154 304 255Z" fill="var(--brand-soft)" opacity=".32" />
      <path d="m80 204 207-68 223 69v125l-208 70L80 330Z" fill="var(--brand-primary)" opacity=".12" />
      <path d="m80 184 207-68v207L80 389Z" fill="var(--surface-raised)" stroke="var(--brand-soft)" />
      <path d="m287 116 223 68v205l-223-66Z" fill="var(--surface)" stroke="var(--brand-soft)" />
      <path d="m80 389 207-66 223 66M287 116v207" fill="none" stroke="var(--brand-secondary)" strokeWidth="2" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <g key={i} fill="none" stroke="var(--brand-soft)" strokeWidth="1.3">
          <path d={`m105 ${218 + i * 24} 154-49`} />
          <path d={`m317 ${172 + i * 24} 164 50`} />
        </g>
      ))}
      <g fill="none" stroke="var(--brand-primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="m111 310 55-18v-48l59-19v-47l62-20 66 20v48l63 19v48l59 18" />
        <path d="m111 358 114-37v-48l62-20 66 20v48l122 37" opacity=".5" />
        <path d="M287 253V158" strokeDasharray="3 7" />
      </g>
      <g fill="var(--surface-raised)" stroke="var(--brand-primary)" strokeWidth="2">
        <path d="m210 178 15-5 15 5v17l-15 5-15-5ZM338 218l15 5 15 5v17l-15-5-15-5Z" />
        <path d="m152 286 14-5 14-4v17l-14 5-14 5ZM402 287l14 4 14 5v17l-14-5-14-4Z" />
      </g>
      <g transform="translate(287 65)" fill="var(--brand-primary)">
        <path d="m0-27 30 14v28L0 29-30 15v-28Z" />
        <path d="m-16 0 10 5 9-14 13 7" fill="none" stroke="var(--surface-raised)" strokeWidth="2.8" />
      </g>
    </svg>
  )
}

export function Login({ onLogin }: { onLogin: () => void }) {
  const [role, setRole] = useState<'student' | 'teacher'>('student')
  const [username, setUsername] = useState('student1')
  const [password, setPassword] = useState('Xuemai123!')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function login(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      saveSession(await post('/auth/login', { username, password }))
      onLogin()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="login-page" data-role={role}>
      <div className="login-scene">
        <section className="login-identity">
          <div className="brand">
            <span className="brand-symbol"><Activity size={26} /></span>
            <span>学脉 <small>XueMai</small></span>
          </div>
          <div className="login-art"><LearningPages /></div>
        </section>
        <section className="login-entry">
          <form className="login-form" onSubmit={login}>
            <h1>欢迎回来</h1>
            <div className="login-roles" aria-label="选择身份">
              {(['student', 'teacher'] as const).map((item) => {
                const Icon = item === 'student' ? GraduationCap : BookOpen
                return <button key={item} type="button" aria-pressed={role === item}
                  className={role === item ? 'selected' : ''} onClick={() => {
                    setRole(item)
                    setUsername(item === 'student' ? 'student1' : 'teacher')
                    setPassword('Xuemai123!')
                    setError('')
                  }}><Icon size={19} />{item === 'student' ? '学生端' : '教师端'}</button>
              })}
            </div>
            <label htmlFor="username">账号</label>
            <input id="username" value={username} onChange={(e) => setUsername(e.target.value)}
              autoComplete="username" required aria-invalid={Boolean(error)} aria-describedby={error ? 'login-error' : undefined} />
            <label htmlFor="password">密码</label>
            <div className="password-field">
              <input id="password" type={showPassword ? 'text' : 'password'} value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
              <button type="button" className="icon-button" aria-label={showPassword ? '隐藏密码' : '显示密码'}
                onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={19} /> : <Eye size={19} />}</button>
            </div>
            {error ? <div id="login-error" className="error-box" role="alert">{error}</div> : null}
            <Button type="submit" disabled={busy}>{busy ? '正在登录…' : '进入学脉'}<ArrowRight size={18} /></Button>
          </form>
        </section>
      </div>
    </main>
  )
}
