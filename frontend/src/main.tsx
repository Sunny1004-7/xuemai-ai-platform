import { StrictMode, Suspense, lazy, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  BookOpen,
  ChartNoAxesCombined,
  CheckCheck,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  FlaskConical,
  GraduationCap,
  LayoutDashboard,
  Library,
  LogOut,
  MessagesSquare,
  Network,
  PanelLeftClose,
  Sparkles,
  Target,
  Users,
  Video,
} from 'lucide-react'
import { api, getSession, post, saveSession, useApi } from './api'
import type { Row } from './api'
import { AppContext, Button, Pill } from './ui'
const LearningPlan = lazy(() => import('./pages/Plan').then((m) => ({ default: m.LearningPlan })))
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Courses = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Courses })))
const Graph = lazy(() => import('./pages/Graph').then((m) => ({ default: m.Graph })))
const Practice = lazy(() => import('./pages/Practice').then((m) => ({ default: m.Practice })))
const Tutor = lazy(() => import('./pages/Tutor').then((m) => ({ default: m.Tutor })))
const VideoPage = lazy(() => import('./pages/Video').then((m) => ({ default: m.VideoPage })))
const Experiments = lazy(() =>
  import('./pages/Experiments').then((m) => ({ default: m.Experiments })),
)
const Management = lazy(() => import('./pages/Management').then((m) => ({ default: m.Management })))
const Resources = lazy(() => import('./pages/Resources').then((m) => ({ default: m.Resources })))
const Analytics = lazy(() => import('./pages/Analytics').then((m) => ({ default: m.Analytics })))
const Classroom = lazy(() => import('./pages/Classroom').then((m) => ({ default: m.Classroom })))
import './styles.css'

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('student1')
  const [password, setPassword] = useState('Xuemai123!')
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
    <div className="login-page" data-role={username === 'teacher' ? 'teacher' : 'student'}>
      <section className="login-story">
        <div className="brand">
          <span className="brand-symbol">
            <Activity size={27} />
          </span>
          <span>
            学脉 <small>XueMai</small>
          </span>
        </div>
        <div className="login-copy">
          <h1>
            知识相连
            <br />
            教学相知
          </h1>
          <p>个性化学习与教学平台</p>
          <svg className="entry-network" viewBox="0 0 560 340" aria-label="从基础到应用的知识网络">
            <path d="M75 175C140 175 120 75 210 75S300 175 320 175S390 85 480 85M75 175C150 175 120 275 210 275S290 175 320 175S390 275 480 275" />
            {[
              [75, 175, '基础'],
              [210, 75, '理解'],
              [210, 275, '实践'],
              [320, 175, '连接'],
              [480, 85, '应用'],
              [480, 275, '迁移'],
            ].map(([x, y, label]) => (
              <g key={label} transform={`translate(${x},${y})`}>
                <circle r={label === '连接' ? 45 : 34} />
                <text textAnchor="middle" dy=".35em">
                  {label}
                </text>
              </g>
            ))}
          </svg>
        </div>
        <div className="login-foot">数据结构与算法 · Python程序设计</div>
      </section>
      <div className="login-side">
        <form className="login-form" onSubmit={login}>
          <span className="welcome-icon">
            <GraduationCap size={30} />
          </span>
          <h2>登录学脉</h2>
          <p>选择身份，进入你的工作区</p>
          <label htmlFor="username">账号</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <label htmlFor="password">密码</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          {error ? (
            <div className="error-box" role="alert">
              {error}
            </div>
          ) : null}
          <Button type="submit" disabled={busy}>
            {busy ? '正在登录…' : '进入学脉'}
            <ArrowRight size={18} />
          </Button>
          <div className="demo-logins">
            <span>体验账号 · 合成教学样例</span>
            <div>
              {[
                ['student1', '体验学生端'],
                ['teacher', '体验教师端'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={id === username ? 'selected' : ''}
                  onClick={() => {
                    setUsername(id)
                    setPassword('Xuemai123!')
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <small>演示密码：Xuemai123!</small>
          </div>
        </form>
      </div>
    </div>
  )
}

const studentNav = [
  ['/', '学习概览', LayoutDashboard],
  ['/plan', '目标与计划', Target],
  ['/courses', '我的课程', BookOpen],
  ['/graph', '知识图谱', Network],
  ['/practice', '智能练习', ClipboardList],
  ['/tutor', 'AI 学习伙伴', Sparkles],
  ['/review', '错题与复习', CheckCheck],
  ['/experiments', '交互实验室', FlaskConical],
  ['/classroom', '课堂互动', MessagesSquare],
] as const
const teacherNav = [
  ['/', '教学工作台', LayoutDashboard],
  ['/manage', '课程与班级', Users],
  ['/graph', '知识图谱', Network],
  ['/resources', 'AI 备课与资料', Library],
  ['/practice', '题库与作业', ClipboardList],
  ['/video', '视频教学', Video],
  ['/analytics', '学情与分层', ChartNoAxesCombined],
  ['/classroom', '课堂互动', MessagesSquare],
] as const
function Shell({ logout }: { logout: () => void }) {
  const user = getSession()!.user
  const [courseId, setCourseId] = useState(
    () =>
      Number(
        new URLSearchParams(window.location.search).get('course') ||
          new URLSearchParams(window.location.search).get('course_id') ||
          sessionStorage.getItem(`xuemai-course-${user.id}`),
      ) || 1,
  )
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const courses = useApi<Row[]>('/courses', [])
  const status = useApi<Row>('/ai/status', {})
  const location = useLocation()
  const navigate = useNavigate()
  function changeCourse(id: number) {
    setCourseId(id)
    sessionStorage.setItem(`xuemai-course-${user.id}`, String(id))
    const query = new URLSearchParams(location.search)
    for (const key of [
      'course_id',
      'knowledge',
      'question',
      'resource',
      'resource_id',
      'assignment',
      't',
      'conversation',
    ])
      query.delete(key)
    query.set('course', String(id))
    navigate({ pathname: location.pathname, search: query.toString() }, { replace: true })
  }
  useEffect(() => {
    if (!courses.data.length) return
    const query = new URLSearchParams(location.search)
    const requested = Number(query.get('course') || query.get('course_id'))
    const id = courses.data.some((c) => c.id === requested)
      ? requested
      : courses.data.some((c) => c.id === courseId)
        ? courseId
        : courses.data[0].id
    if (id !== courseId) setCourseId(id)
    sessionStorage.setItem(`xuemai-course-${user.id}`, String(id))
  }, [courses.data, location.search])
  const nav = user.role === 'teacher' ? teacherNav : studentNav
  const current = nav.find((x) => x[0] === location.pathname)?.[1] || '课程学习'
  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 4500)
    return () => clearTimeout(id)
  }, [toast])
  useEffect(() => {
    const reload = () => courses.reload()
    window.addEventListener('courses-changed', reload)
    return () => window.removeEventListener('courses-changed', reload)
  }, [courses.reload])
  return (
    <AppContext.Provider
      value={{
        user,
        courseId,
        setCourseId: changeCourse,
        notify: (text, error) => setToast({ text, error }),
      }}
    >
      <div data-role={user.role} className={`app-shell ${collapsed ? 'nav-collapsed' : ''}`}>
        <aside className="sidebar">
          <a className="brand" href="/">
            <span className="brand-symbol">
              <Activity size={27} />
            </span>
            <span className="brand-name">
              学脉 <small>XueMai</small>
            </span>
          </a>
          <div className="workspace-label">
            {user.role === 'teacher' ? '教学空间' : '学习空间'}
            <span>{user.role === 'teacher' ? '教师端' : '学生端'}</span>
          </div>
          <nav aria-label="主导航">
            {nav.map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === '/'} title={label}>
                <Icon size={19} />
                <span>{label}</span>
                {to === '/tutor' ? <i>AI</i> : null}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <button className="profile" onClick={logout} title="退出登录">
              <span className="avatar">{user.name.slice(0, 1)}</span>
              <span>
                {user.name}
                <small>{user.role === 'teacher' ? '课程教师' : '学习者'}</small>
              </span>
              <LogOut size={17} />
            </button>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button"
                aria-label="收起或展开导航"
                onClick={() => setCollapsed(!collapsed)}
              >
                <PanelLeftClose size={18} />
              </button>
              <span>{user.role === 'teacher' ? '教学空间' : '学习空间'}</span>
              <span className="crumb-slash">/</span>
              <strong>{current}</strong>
            </div>
            <div className="top-actions">
              <div className="course-switch">
                <BookOpen size={15} />
                <select
                  aria-label="切换当前课程"
                  value={courseId}
                  onChange={(e) => changeCourse(Number(e.target.value))}
                >
                  {courses.data.map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
                <ChevronDown size={13} />
              </div>
              <Pill tone={status.data.mode === 'real' ? 'green' : 'neutral'}>
                <span className="status-dot" />
                {status.data.mode === 'real' ? 'DeepSeek 已连接' : '本地演示模式'}
              </Pill>
              <button
                className="icon-button"
                title="查看学习伙伴"
                aria-label="帮助"
                onClick={() => {
                  window.location.href = '/tutor'
                }}
              >
                <CircleHelp size={19} />
              </button>
            </div>
          </header>
          <main className="workspace" key={user.id}>
            <Suspense fallback={<div className="loading">正在加载…</div>}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/courses" element={<Courses />} />
                <Route path="/plan" element={<LearningPlan />} />
                <Route path="/graph" element={<Graph />} />
                <Route path="/practice" element={<Practice />} />
                <Route path="/review" element={<Practice review />} />
                <Route path="/tutor" element={<Tutor />} />
                <Route path="/video" element={<VideoPage />} />
                <Route path="/experiments" element={<Experiments />} />
                <Route path="/manage" element={<Management />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/classroom" element={<Classroom />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </main>
        </div>
        {toast ? (
          <div role="status" className={`toast ${toast.error ? 'is-error' : ''}`}>
            {toast.error ? <CircleHelp size={18} /> : <CheckCheck size={18} />} {toast.text}
          </div>
        ) : null}
      </div>
    </AppContext.Provider>
  )
}
function App() {
  const [logged, setLogged] = useState(Boolean(getSession()))
  useEffect(() => {
    const expire = () => setLogged(false)
    window.addEventListener('session-expired', expire)
    return () => window.removeEventListener('session-expired', expire)
  }, [])
  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch {
      /* 本地仍清除会话 */
    }
    saveSession(null)
    setLogged(false)
  }
  return (
    <BrowserRouter>
      {logged ? <Shell logout={logout} /> : <Login onLogin={() => setLogged(true)} />}
    </BrowserRouter>
  )
}
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
