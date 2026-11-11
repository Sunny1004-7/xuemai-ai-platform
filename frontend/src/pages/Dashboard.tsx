import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, Video, Target } from 'lucide-react'
import { PersonalCharts } from '../components/LearningCharts'
import { Pager, Tabs, usePage } from '../components/Workspace'
import { percent, useApi } from '../api'
import type { Row } from '../api'
import { Empty, LoadState, Panel, Title, useApp, dateLabel } from '../ui'

export function Dashboard() {
  const { user, courseId } = useApp()
  const teacher = user.role === 'teacher'
  const query = useApi<Row>(`/dashboard?course_id=${courseId}`, {})
  const insights = useApi<Row>(
    `/${teacher ? 'analytics' : 'learning/insights'}?course_id=${courseId}`,
    {},
  )
  const [view, setView] = useState('tasks')
  const d = query.data
  const tasks: Row[] = (d.assignments || []).filter((r: Row) => r.course_id === courseId)
  const events: Row[] = (d.recent_events || []).filter(
    (r: Row) => !r.course_id || r.course_id === courseId,
  )
  const weak: Row[] = (insights.data.knowledge || []).filter((r: Row) => r.weak_students?.length)
  const list = usePage<Row>(
    view === 'history' ? events : teacher && view === 'focus' ? weak : tasks,
    85,
    500,
  )
  const next = (d.recommendations || []).find(
    (r: Row) => r.course_id === courseId && r.in_current_plan,
  )
  const course = (d.courses || []).find((c: Row) => c.id === courseId)
  return (
    <>
      <Title title={teacher ? '教学工作台' : '学习概览'} />
      <LoadState {...query} retry={query.reload} />
      <section className="overview-command">
        <div>
          <small>{course?.code}</small>
          <h2>{course?.title || '当前课程'}</h2>
          <p>
            {teacher
              ? `${insights.data.summary?.student_count || 0} 位学生 · ${tasks.length} 项任务`
              : `掌握估计 ${percent(course?.progress)}% · ${next ? next.title : '开始一次独立学习'}`}
          </p>
        </div>
        <Link className="button" to={teacher ? '/practice' : next?.href || '/graph'}>
          {teacher ? '安排教学任务' : '继续学习'}
          <ArrowRight size={17} />
        </Link>
      </section>
      <div className="workspace-shortcuts">
        <Link to="/video">
          <Video size={18} />
          视频学习
        </Link>
        <Link to="/resources">
          <BookOpen size={18} />
          {teacher ? '资料与备课' : '课程资料'}
        </Link>
        <Link to={teacher ? '/analytics' : '/plan'}>
          <Target size={18} />
          {teacher ? '班级学情' : '目标与计划'}
        </Link>
        <Link to="/classroom">
          课堂互动
          <ArrowRight size={15} />
        </Link>
      </div>
      <Tabs
        value={view}
        onChange={setView}
        items={
          teacher
            ? [
                ['tasks', '教学任务'],
                ['focus', '需要关注'],
                ['history', '近期记录'],
              ]
            : [
                ['tasks', '课程任务'],
                ['progress', '学习进展'],
                ['history', '近期记录'],
              ]
        }
      />
      {view === 'progress' ? (
        <div className="workspace-body">
          <PersonalCharts data={insights.data} courseId={courseId} />
        </div>
      ) : (
        <Panel className="workspace-list">
          <div className="workspace-list-body">
            {list.rows.map((r: Row) => (
              <Link
                className="desk-task"
                key={r.id}
                to={
                  view === 'history'
                    ? `/graph?knowledge=${r.knowledge_id || ''}`
                    : view === 'focus'
                      ? `/analytics?knowledge=${r.id}`
                      : `/practice?assignment=${r.id}`
                }
              >
                <div>
                  <strong>{r.title || r.knowledge_title || '课程活动'}</strong>
                  <small>
                    {view === 'history'
                      ? `${r.student_name || ''} ${dateLabel(r.created_at)}`
                      : view === 'focus'
                        ? `${r.weak_students.length} 人需巩固 · 掌握估计 ${percent(r.average_mastery)}%`
                        : `${r.question_ids?.length || 0} 道题 · ${r.completed ? '已完成' : r.due_at ? dateLabel(r.due_at) : '进行中'}`}
                  </small>
                </div>
                <ArrowRight size={18} />
              </Link>
            ))}
            {!list.count && !query.loading ? <Empty>当前没有待展示的记录。</Empty> : null}
          </div>
          <Pager {...list} onChange={list.setPage} label="条记录" />
        </Panel>
      )}
    </>
  )
}
