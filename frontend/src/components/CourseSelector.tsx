import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { BookOpen, Check, ChevronDown, Plus, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { post } from '../api'
import type { Row } from '../api'
import { Button, Modal, useApp } from '../ui'

export function CourseSelector({ courses, reload }: { courses: Row[]; reload: () => void }) {
  const { courseId, setCourseId, user, notify } = useApp()
  const navigate = useNavigate()
  const trigger = useRef<HTMLButtonElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [join, setJoin] = useState(false)
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState({ top: 0, right: 0 })
  const current = courses.find((c) => c.id === courseId)
  function close() {
    setOpen(false)
    trigger.current?.focus()
  }
  function choose(index: number) {
    if (
      courses[index]?.id !== courseId &&
      document.querySelector('form[data-unsaved="true"]') &&
      !window.confirm('当前输入尚未保存，切换课程将放弃这些修改。继续切换？')
    )
      return
    if (courses[index]) setCourseId(courses[index].id)
    close()
  }
  useEffect(() => {
    if (!open) return
    const rect = trigger.current!.getBoundingClientRect()
    setPosition({ top: rect.bottom + 8, right: Math.max(12, window.innerWidth - rect.right) })
    setActive(
      Math.max(
        0,
        courses.findIndex((c) => c.id === courseId),
      ),
    )
    popup.current?.focus()
    const outside = (e: PointerEvent) => {
      if (
        !popup.current?.contains(e.target as Node) &&
        !trigger.current?.contains(e.target as Node)
      )
        close()
    }
    const resize = () => close()
    document.addEventListener('pointerdown', outside)
    window.addEventListener('resize', resize)
    return () => {
      document.removeEventListener('pointerdown', outside)
      window.removeEventListener('resize', resize)
    }
  }, [open])
  return (
    <>
      <button
        ref={trigger}
        className="course-trigger"
        aria-label="切换当前课程"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="course-options"
        onClick={() => setOpen(!open)}
      >
        <BookOpen size={18} />
        <span>{current?.title || '选择课程'}</span>
        <ChevronDown size={15} />
      </button>
      {open &&
        createPortal(
          <div
            className="course-popup"
            data-role={user.role}
            ref={popup}
            tabIndex={-1}
            style={position}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.preventDefault()
                close()
              }
              if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault()
                setActive(
                  (v) =>
                    (v + (e.key === 'ArrowDown' ? 1 : courses.length - 1)) %
                    Math.max(1, courses.length),
                )
              }
              if (e.key === 'Enter' && e.target === popup.current) {
                e.preventDefault()
                choose(active)
              }
              if (e.key === 'Tab') {
                const nodes = Array.from(
                  popup.current!.querySelectorAll<HTMLButtonElement>('button'),
                )
                if (e.shiftKey && (e.target === popup.current || e.target === nodes[0])) {
                  e.preventDefault()
                  nodes.at(-1)?.focus()
                } else if (!e.shiftKey && e.target === nodes.at(-1)) {
                  e.preventDefault()
                  popup.current?.focus()
                }
              }
            }}
          >
            <div
              role="listbox"
              id="course-options"
              aria-label="课程"
              aria-activedescendant={`course-${courses[active]?.id}`}
            >
              {courses.map((course, index) => (
                <button
                  role="option"
                  id={`course-${course.id}`}
                  aria-selected={course.id === courseId}
                  className={active === index ? 'is-focused' : ''}
                  key={course.id}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(index)}
                >
                  <BookOpen size={18} />
                  <span>{course.title}</span>
                  {course.id === courseId && <Check size={17} />}
                </button>
              ))}
            </div>
            <button
              className="course-menu-action"
              onClick={() => {
                close()
                user.role === 'teacher' ? navigate('/manage') : setJoin(true)
              }}
            >
              {user.role === 'teacher' ? <Settings size={16} /> : <Plus size={16} />}{' '}
              {user.role === 'teacher' ? '管理课程' : '加入班级'}
            </button>
          </div>,
          document.body,
        )}
      {join && (
        <Modal
          title="加入班级"
          close={() => {
            setJoin(false)
            trigger.current?.focus()
          }}
        >
          <form
            className="form-stack"
            onSubmit={async (e) => {
              e.preventDefault()
              const code = new FormData(e.currentTarget).get('code')
              try {
                await post('/classes/join', { join_code: code })
                reload()
                setJoin(false)
                notify('已加入班级，课程已更新')
              } catch (error) {
                notify((error as Error).message, true)
              }
            }}
          >
            <label>
              班级邀请码
              <input name="code" required autoFocus maxLength={30} />
            </label>
            <Button>加入班级</Button>
          </form>
        </Modal>
      )}
    </>
  )
}
