import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Activity, ArrowRight, BookOpen, ChartNoAxesCombined, CheckCheck, ChevronDown, CircleHelp, ClipboardList, FlaskConical, GraduationCap, LayoutDashboard, Library, LogOut, MessagesSquare, Network, PanelLeftClose, Sparkles, Target, Users, Video } from 'lucide-react'
import { api, getSession, post, saveSession, useApi } from './api'
import type { Row } from './api'
import { AppContext, Button, Pill } from './ui'
import { LearningPlan } from './pages/Plan'
import { Dashboard, Courses } from './pages/Dashboard'
import { Graph } from './pages/Graph'
import { Practice } from './pages/Practice'
import { Tutor } from './pages/Tutor'
import { VideoPage } from './pages/Video'
import { Experiments } from './pages/Experiments'
import { Management, Resources, Analytics, Classroom } from './pages/Teacher'
import './styles.css'

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('student1')
  const [password, setPassword] = useState('Xuemai123!')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function login(e: React.FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try { saveSession(await post('/auth/login', { username, password })); onLogin() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="login-page"><div className="login-story"><div className="brand"><span className="brand-symbol"><Activity size={27}/></span><span>学脉 <small>XueMai</small></span></div><div className="login-copy"><Pill>为每一种学习节奏而设计</Pill><h1>每一次理解，<br/>都连接下一次成长。</h1><p>把知识串成脉络，让学习有迹可循。<br/>在课程、练习与对话之间，找到适合你的下一步。</p><div className="login-network" aria-hidden="true"><svg viewBox="0 0 580 270"><path d="M40 140L155 65L280 140L405 65L535 140M155 65L155 215L280 140L405 215L535 140"/><g><circle cx="40" cy="140" r="12"/><circle cx="155" cy="65" r="22"/><circle cx="155" cy="215" r="13"/><circle cx="280" cy="140" r="30"/><circle cx="405" cy="65" r="16"/><circle cx="405" cy="215" r="20"/><circle cx="535" cy="140" r="13"/></g><text x="155" y="25">理解概念</text><text x="280" y="201">连接知识</text><text x="405" y="260">迁移应用</text></svg></div></div><div className="login-foot">学生学习与教师教学，共用一条成长脉络。</div></div><div className="login-side"><form className="login-form" onSubmit={login}><span className="welcome-icon"><GraduationCap size={30}/></span><h2>欢迎回到学脉</h2><p>继续你的学习与教学旅程</p><label htmlFor="username">账号</label><input id="username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required/><label htmlFor="password">密码</label><input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required/>{error ? <div className="error-box" role="alert">{error}</div> : null}<Button type="submit" disabled={busy}>{busy ? '正在登录…' : '进入学脉'}<ArrowRight size={18}/></Button><div className="demo-logins"><span>使用合成演示账号</span><div>{[['student1', '学生 · 陈星河'], ['student2', '学生 · 许沐晴'], ['teacher', '教师 · 林知远']].map(([id, label]) => <button key={id} type="button" className={id === username ? 'selected' : ''} onClick={() => { setUsername(id); setPassword('Xuemai123!') }}>{label}</button>)}</div><small>演示密码：Xuemai123!</small></div></form></div></div>
}

const studentNav = [
  ['/', '学习概览', LayoutDashboard], ['/plan', '目标与计划', Target], ['/courses', '我的课程', BookOpen], ['/graph', '知识图谱', Network], ['/practice', '智能练习', ClipboardList], ['/tutor', 'AI 学习伙伴', Sparkles], ['/review', '错题与复习', CheckCheck], ['/experiments', '交互实验室', FlaskConical], ['/classroom', '课堂互动', MessagesSquare],
] as const
const teacherNav = [
  ['/', '教学工作台', LayoutDashboard], ['/manage', '课程与班级', Users], ['/graph', '知识图谱', Network], ['/resources', 'AI 备课与资料', Library], ['/practice', '题库与作业', ClipboardList], ['/video', '视频教学', Video], ['/analytics', '学情与分层', ChartNoAxesCombined], ['/classroom', '课堂互动', MessagesSquare],
] as const
function Shell({ logout }: { logout: () => void }) {
  const user = getSession()!.user
  const [courseId, setCourseId] = useState(1)
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const courses = useApi<Row[]>('/courses', [])
  const status = useApi<Row>('/ai/status', {})
  const location = useLocation()
  const nav = user.role === 'teacher' ? teacherNav : studentNav
  const current = nav.find(x => x[0] === location.pathname)?.[1] || '课程学习'
  useEffect(() => { if (!toast) return; const id = setTimeout(() => setToast(null), 4500); return () => clearTimeout(id) }, [toast])
  useEffect(() => { const reload = () => courses.reload(); window.addEventListener('courses-changed', reload); return () => window.removeEventListener('courses-changed', reload) }, [courses.reload])
  return <AppContext.Provider value={{ user, courseId, setCourseId, notify: (text, error) => setToast({ text, error }) }}><div className={`app-shell ${collapsed ? 'nav-collapsed' : ''}`}><aside className="sidebar"><a className="brand" href="/"><span className="brand-symbol"><Activity size={27}/></span><span className="brand-name">学脉 <small>XueMai</small></span></a><div className="workspace-label">{user.role === 'teacher' ? '教学空间' : '学习空间'}<span>{user.role === 'teacher' ? '教师端' : '学生端'}</span></div><nav aria-label="主导航">{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'} title={label}><Icon size={19}/><span>{label}</span>{to === '/tutor' ? <i>AI</i> : null}</NavLink>)}</nav><div className="sidebar-bottom"><div className="sidebar-note"><span className="status-dot"/>让每一次努力被看见<p>基于学习证据，陪伴持续成长</p></div><button className="profile" onClick={logout} title="退出登录"><span className="avatar">{user.name.slice(0, 1)}</span><span>{user.name}<small>{user.role === 'teacher' ? '课程教师' : '学习者'}</small></span><LogOut size={17}/></button></div></aside><div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button" aria-label="收起或展开导航" onClick={() => setCollapsed(!collapsed)}><PanelLeftClose size={18}/></button><span>{user.role === 'teacher' ? '教学空间' : '学习空间'}</span><span className="crumb-slash">/</span><strong>{current}</strong></div><div className="top-actions"><div className="course-switch"><BookOpen size={15}/><select aria-label="切换当前课程" value={courseId} onChange={e => setCourseId(Number(e.target.value))}>{courses.data.map(c => <option value={c.id} key={c.id}>{c.title}</option>)}</select><ChevronDown size={13}/></div><Pill tone={status.data.mode === 'real' ? 'green' : 'neutral'}><span className="status-dot"/>{status.data.mode === 'real' ? 'DeepSeek 已连接' : '本地演示模式'}</Pill><button className="icon-button" title="查看学习伙伴" aria-label="帮助" onClick={() => { window.location.href = '/tutor' }}><CircleHelp size={19}/></button></div></header><main className="workspace" key={user.id}><Routes><Route path="/" element={<Dashboard/>}/><Route path="/courses" element={<Courses/>}/><Route path="/plan" element={<LearningPlan/>}/><Route path="/graph" element={<Graph/>}/><Route path="/practice" element={<Practice/>}/><Route path="/review" element={<Practice review/>}/><Route path="/tutor" element={<Tutor/>}/><Route path="/video" element={<VideoPage/>}/><Route path="/experiments" element={<Experiments/>}/><Route path="/manage" element={<Management/>}/><Route path="/resources" element={<Resources/>}/><Route path="/analytics" element={<Analytics/>}/><Route path="/classroom" element={<Classroom/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes><footer className="workspace-footer"><span>学脉 XueMai</span><span>演示环境 · 所有预置学习记录为合成数据</span></footer></main></div>{toast ? <div role="status" className={`toast ${toast.error ? 'is-error' : ''}`}>{toast.error ? <CircleHelp size={18}/> : <CheckCheck size={18}/>} {toast.text}</div> : null}</div></AppContext.Provider>
}
function App() {
  const [logged, setLogged] = useState(Boolean(getSession()))
  useEffect(() => { const expire = () => setLogged(false); window.addEventListener('session-expired', expire); return () => window.removeEventListener('session-expired', expire) }, [])
  async function logout() { try { await api('/auth/logout', { method: 'POST' }) } catch { /* 本地仍清除会话 */ } saveSession(null); setLogged(false) }
  return <BrowserRouter>{logged ? <Shell logout={logout}/> : <Login onLogin={() => setLogged(true)}/>}</BrowserRouter>
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>)
