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
  ChartNoAxesCombined,
  CheckCheck,
  CircleHelp,
  ClipboardList,
  FlaskConical,
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
import { api, getSession, saveSession, useApi } from './api'
import type { Row } from './api'
import { AppContext } from './ui'
import { CourseSelector } from './components/CourseSelector'
const LearningPlan = lazy(() => import('./pages/Plan').then((m) => ({ default: m.LearningPlan })))
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
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
import { Login } from './pages/Login'
import './styles.css'

const studentNav = [
  ['/', '学习概览', LayoutDashboard],
  ['/plan', '目标与计划', Target],
  ['/video', '视频学习', Video],
  ['/resources', '课程资料', Library],
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
  ['/teacher-ai', 'AI 教学助手', Sparkles],
] as const
const studentGroups = [
  ['学习安排', ['/', '/plan']],
  ['课程学习', ['/video', '/resources', '/graph']],
  ['练习巩固', ['/practice', '/review', '/experiments']],
  ['答疑互动', ['/tutor', '/classroom']],
] as const
const teacherGroups = [
  ['教学组织', ['/', '/manage']],
  ['备课与资源', ['/resources', '/graph', '/video']],
  ['教学实施', ['/practice', '/classroom']],
  ['分析与研讨', ['/analytics', '/teacher-ai']],
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
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    const changed = (e: Event) => {
      const target = e.target as HTMLElement
      const form = target.closest('form')
      if (form) form.dataset.unsaved = 'true'
    }
    document.addEventListener('input', changed)
    return () => document.removeEventListener('input', changed)
  }, [])
  function changeCourse(id: number) {
    if (id === courseId) return
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
      'chapter',
      'mode',
      'plan',
      'view',
    ])
      query.delete(key)
    query.set('course', String(id))
    navigate({ pathname: location.pathname, search: query.toString() })
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
  const groups = user.role === 'teacher' ? teacherGroups : studentGroups
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
            {groups.map(([name, paths]) => (
              <section className="nav-group" key={name} aria-label={name}>
                <h2>{name}</h2>
                {paths.map(path => {
                  const item = nav.find(entry => entry[0] === path)!
                  const [to, label, Icon] = item
                  return <NavLink key={to} to={to} end={to === '/'} title={label}>
                    <Icon size={19} /><span>{label}</span>
                  </NavLink>
                })}
              </section>
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
              <CourseSelector courses={courses.data} reload={courses.reload} />
              <button
                className="icon-button"
                title={user.role === 'teacher' ? 'AI 教学助手' : 'AI 学习伙伴'}
                aria-label="帮助"
                onClick={() => {
                  const query = new URLSearchParams(location.search)
                  query.set('course', String(courseId))
                  navigate(`${user.role === 'teacher' ? '/teacher-ai' : '/tutor'}?${query}`)
                }}
              >
                <CircleHelp size={19} />
              </button>
            </div>
          </header>
          <main
            className="workspace"
            data-module={location.pathname.slice(1) || 'dashboard'}
            key={`${user.id}-${courseId}`}
          >
            <Suspense fallback={<div className="loading">正在加载…</div>}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/courses" element={<Navigate to="/" replace />} />
                <Route path="/plan" element={<LearningPlan />} />
                <Route path="/graph" element={<Graph />} />
                <Route path="/practice" element={<Practice />} />
                <Route path="/review" element={<Practice review />} />
                <Route path="/tutor" element={user.role === 'teacher' ? <Navigate to={`/teacher-ai?course=${courseId}`} replace /> : <Tutor />} />
                <Route path="/teacher-ai" element={user.role === 'teacher' ? <Tutor teacher /> : <Navigate to={`/tutor?course=${courseId}`} replace />} />
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
