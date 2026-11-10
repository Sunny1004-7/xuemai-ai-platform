import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  GitBranch,
  Layers3,
  ListOrdered,
  Pause,
  Play,
  RotateCcw,
  Save,
  Sparkles,
} from 'lucide-react'
import { bubbleSteps, bfsSteps, bstSteps } from '../algorithms'
import type { Snapshot } from '../algorithms'
import { post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Panel, Pill, Title, useApp } from '../ui'

export function Experiments() {
  const { courseId, notify } = useApp()
  const [params] = useSearchParams()
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const [mode, setMode] = useState(
    ['sort', 'tree', 'bfs', 'stack', 'queue'].includes(params.get('mode') || '')
      ? params.get('mode')!
      : 'sort',
  )
  const [raw, setRaw] = useState('36, 18, 52, 24, 9, 43')
  const [values, setValues] = useState([36, 18, 52, 24, 9, 43])
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(900)
  const [prediction, setPrediction] = useState('')
  const [predFeedback, setPredFeedback] = useState('')
  const [collection, setCollection] = useState([12, 24, 36])
  const [newValue, setNewValue] = useState('48')
  const [operation, setOperation] = useState('初始结构中有 3 个元素。')
  const [operations, setOperations] = useState(0)
  const [saving, setSaving] = useState(false)
  const snapshots = useMemo(
    () => (mode === 'bfs' ? bfsSteps() : mode === 'tree' ? bstSteps(values) : bubbleSteps(values)),
    [mode, values],
  )
  const snapshot = snapshots[Math.min(step, snapshots.length - 1)]
  const knowledgeId =
    Number(params.get('knowledge')) ||
    graph.data.nodes?.find((n: Row) =>
      n.title.includes(
        mode === 'sort'
          ? '排序'
          : mode === 'tree'
            ? '树'
            : mode === 'bfs'
              ? '图'
              : mode === 'stack'
                ? '栈'
                : '队列',
      ),
    )?.id
  useEffect(() => {
    setStep(0)
    setPlaying(false)
    setPredFeedback('')
    setOperations(0)
    setCollection([12, 24, 36])
  }, [mode, values])
  useEffect(() => {
    if (!playing) return
    const id = setInterval(
      () =>
        setStep((s) => {
          if (s >= snapshots.length - 2) {
            setPlaying(false)
            return snapshots.length - 1
          }
          return s + 1
        }),
      speed,
    )
    return () => clearInterval(id)
  }, [playing, speed, snapshots.length])
  function applyInput(e: React.FormEvent) {
    e.preventDefault()
    const nums = raw
      .split(/[,，\s]+/)
      .filter(Boolean)
      .map(Number)
    if (
      nums.length < 2 ||
      nums.length > 12 ||
      nums.some((n) => !Number.isFinite(n) || n < 1 || n > 99)
    ) {
      notify('请输入 2–12 个 1–99 之间的数字，以逗号分隔', true)
      return
    }
    setValues(nums)
    setStep(0)
  }
  function act(add: boolean) {
    if (add) {
      const n = Number(newValue)
      if (!Number.isFinite(n) || n < 1 || n > 99 || collection.length >= 10) {
        notify('请输入 1–99 之间的数字，最多容纳 10 个元素', true)
        return
      }
      setCollection((c) => [...c, n])
      setOperation(
        `${mode === 'stack' ? '压栈' : '入队'} ${n}：从${mode === 'stack' ? '栈顶' : '队尾'}加入。`,
      )
    } else {
      if (!collection.length) {
        setOperation('结构为空，不能继续移除。')
        return
      }
      const n = mode === 'stack' ? collection[collection.length - 1] : collection[0]
      setCollection((c) => (mode === 'stack' ? c.slice(0, -1) : c.slice(1)))
      setOperation(
        `${mode === 'stack' ? '出栈' : '出队'} ${n}：遵循${mode === 'stack' ? '后进先出' : '先进先出'}。`,
      )
    }
    setOperations((n) => n + 1)
  }
  function predict() {
    const next = snapshots[Math.min(step + 1, snapshots.length - 1)]
    const expected =
      mode === 'bfs' ? String.fromCharCode(65 + (next.visited?.at(-1) || 0)) : next.values.join(',')
    const match =
      prediction
        .replace(/[,，\s]+/g, ',')
        .replace(/^,|,$/g, '')
        .toUpperCase() === expected
    setPredFeedback(
      match
        ? '预测正确！继续执行一步，观察状态变化。'
        : `再观察当前比较或队列状态。下一步结果为：${expected}`,
    )
  }
  async function save() {
    setSaving(true)
    try {
      await post('/events', {
        course_id: courseId,
        knowledge_id: knowledgeId,
        kind: 'experiment',
        payload: {
          experiment: mode,
          input: values,
          steps_completed: step,
          total_steps: snapshots.length - 1,
          operations,
          completed:
            mode === 'stack' || mode === 'queue' ? operations >= 3 : step === snapshots.length - 1,
          prediction_attempted: Boolean(predFeedback),
        },
      })
      notify('实验操作与完成状态已写入学习记录')
    } catch (e) {
      notify((e as Error).message, true)
    } finally {
      setSaving(false)
    }
  }
  const manual = mode === 'stack' || mode === 'queue'
  return (
    <>
      <Title
        title="交互实验"
        subtitle="改一组数据，预测下一步，在真实程序状态里理解运行机制"
        action={
          <Button onClick={save} disabled={saving}>
            <Save size={16} />
            {saving ? '记录中…' : '保存实验记录'}
          </Button>
        }
      />
      <div className="experiment-tabs">
        {[
          ['sort', '冒泡排序', ListOrdered],
          ['stack', '栈的操作', Layers3],
          ['queue', '队列操作', ArrowRight],
          ['tree', '二叉搜索树', GitBranch],
          ['bfs', '广度优先搜索', FlaskConical],
        ].map(([value, label, Icon]) => {
          const I = Icon as typeof ListOrdered
          return (
            <button
              key={String(value)}
              className={mode === value ? 'active' : ''}
              onClick={() => setMode(String(value))}
            >
              <I size={19} />
              {String(label)}
            </button>
          )
        })}
      </div>
      <div className="experiment-layout">
        <div>
          <Panel className="experiment-stage">
            <div className="experiment-stage-head">
              <Pill tone="green">确定性算法 · 真实状态</Pill>
              <span>
                {manual ? `${operations} 次操作` : `步骤 ${step} / ${snapshots.length - 1}`}
              </span>
            </div>
            {mode === 'sort' ? (
              <div className="sort-bars">
                {snapshot.values.map((n, i) => (
                  <div
                    className={`sort-bar ${snapshot.active.includes(i) ? 'comparing' : ''} ${snapshot.sorted.includes(i) ? 'sorted' : ''}`}
                    style={{ height: `${n * 2.7}px` }}
                    key={i}
                  >
                    <strong>{n}</strong>
                    <small>{i}</small>
                  </div>
                ))}
              </div>
            ) : manual ? (
              <div className={`collection-stage ${mode}`}>
                <div className="collection-values">
                  {collection.map((n, i) => (
                    <div className="collection-node" key={`${i}-${n}`}>
                      <strong>{n}</strong>
                      {mode === 'stack' && i === collection.length - 1 ? (
                        <span>栈顶</span>
                      ) : mode === 'queue' && i === 0 ? (
                        <span>队首</span>
                      ) : null}
                    </div>
                  ))}
                  {!collection.length ? <p>结构为空</p> : null}
                </div>
                <p>{mode === 'stack' ? '后进先出 LIFO' : '先进先出 FIFO'}</p>
              </div>
            ) : (
              <TreeStage snapshot={snapshot} bfs={mode === 'bfs'} />
            )}
            <div className="algorithm-explanation">
              <span>
                <LightbulbIcon />
              </span>
              <p>{manual ? operation : snapshot.message}</p>
            </div>
            {manual ? (
              <div className="experiment-controls">
                <input
                  type="number"
                  min={1}
                  max={99}
                  aria-label="待加入元素"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                />
                <Button onClick={() => act(true)}>
                  <ArrowDown size={16} />
                  {mode === 'stack' ? '压栈' : '入队'}
                </Button>
                <Button variant="secondary" onClick={() => act(false)}>
                  <ArrowUp size={16} />
                  {mode === 'stack' ? '出栈' : '出队'}
                </Button>
                <Button
                  variant="icon secondary"
                  aria-label="重置结构"
                  onClick={() => {
                    setCollection([12, 24, 36])
                    setOperations(0)
                  }}
                >
                  <RotateCcw size={16} />
                </Button>
              </div>
            ) : (
              <div className="experiment-controls">
                <Button
                  variant="icon secondary"
                  aria-label="重置实验"
                  onClick={() => {
                    setStep(0)
                    setPlaying(false)
                  }}
                >
                  <RotateCcw size={17} />
                </Button>
                <Button
                  variant="secondary"
                  disabled={step === 0}
                  onClick={() => setStep((s) => s - 1)}
                >
                  <ChevronLeft size={16} />
                  上一步
                </Button>
                <Button
                  onClick={() => {
                    if (step === snapshots.length - 1) setStep(0)
                    setPlaying(!playing)
                  }}
                >
                  {playing ? <Pause size={16} /> : <Play size={16} />}{' '}
                  {playing ? '暂停' : '自动演示'}
                </Button>
                <Button
                  variant="secondary"
                  disabled={step >= snapshots.length - 1}
                  onClick={() => setStep((s) => s + 1)}
                >
                  下一步
                  <ChevronRight size={16} />
                </Button>
                <select
                  aria-label="演示速度"
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                >
                  <option value={1400}>慢速</option>
                  <option value={900}>标准</option>
                  <option value={450}>快速</option>
                </select>
              </div>
            )}
          </Panel>
          {!manual ? (
            <Panel title="先预测，再执行" caption="把观察变成主动思考">
              <form
                className="prediction-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  predict()
                }}
              >
                <label>
                  {mode === 'bfs'
                    ? '下一步访问哪个节点？填写字母'
                    : '下一步的序列是什么？用逗号分隔'}
                  <input
                    value={prediction}
                    onChange={(e) => setPrediction(e.target.value)}
                    required
                    placeholder={mode === 'bfs' ? '例如 B' : '例如 18,36,52,24,9,43'}
                  />
                </label>
                <Button variant="secondary" type="submit">
                  <CheckCheck size={16} />
                  检查预测
                </Button>
              </form>
              {predFeedback ? (
                <p className="prediction-feedback" role="status">
                  {predFeedback}
                </p>
              ) : null}
            </Panel>
          ) : null}
        </div>
        <aside>
          <Panel
            title="实验参数"
            caption={
              mode === 'bfs' ? '示例图从 A 开始按队列顺序搜索' : '小规模数据，更容易看清每一步'
            }
          >
            {!manual && mode !== 'bfs' ? (
              <form className="form-stack" onSubmit={applyInput}>
                <label>
                  输入序列
                  <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={3} />
                </label>
                <p className="mini-text muted">2–12 个数字，范围 1–99，以逗号分隔。</p>
                <Button variant="secondary" type="submit">
                  应用这组数据
                </Button>
              </form>
            ) : (
              <p className="muted">
                {mode === 'bfs'
                  ? '节点在第一次发现时入队，在出队时被访问，避免重复搜索。'
                  : `通过加入与移除元素，对照${mode === 'stack' ? '栈顶与后进先出' : '队首、队尾与先进先出'}规则。`}
              </p>
            )}
          </Panel>
          <Panel title="把实验连接回知识">
            <p className="muted">操作只是开始。试着说明每一步为什么成立，再到练习里独立应用。</p>
            <div className="form-stack">
              <Link to={`/tutor?knowledge=${knowledgeId || ''}`} className="button secondary">
                <Sparkles size={16} />
                让学习伙伴解释
              </Link>
              <Link to={`/practice?knowledge=${knowledgeId || ''}`} className="button secondary">
                做一道相关练习
                <ArrowRight size={16} />
              </Link>
            </div>
          </Panel>
        </aside>
      </div>
    </>
  )
}
function LightbulbIcon() {
  return <FlaskConical size={20} />
}
function TreeStage({ snapshot, bfs }: { snapshot: Snapshot; bfs: boolean }) {
  const positions: Record<number, { x: number; y: number }> = {}
  if (bfs)
    [
      [0, 360, 55],
      [1, 210, 155],
      [2, 510, 155],
      [3, 110, 265],
      [4, 360, 265],
      [5, 610, 265],
    ].forEach(([id, x, y]) => {
      positions[id] = { x, y }
    })
  else {
    const edges = snapshot.edges || []
    function place(value: number, x: number, y: number, spread: number) {
      positions[value] = { x, y }
      for (const [a, b] of edges)
        if (a === value) place(b, x + (b < a ? -spread : spread), y + 85, spread * 0.53)
    }
    if (snapshot.values.length) place(snapshot.values[0], 360, 45, 165)
  }
  return (
    <svg
      className="tree-stage"
      viewBox="0 0 720 390"
      aria-label={bfs ? '广度优先搜索图' : '二叉搜索树状态'}
    >
      {snapshot.edges?.map(([a, b], i) =>
        positions[a] && positions[b] ? (
          <line
            key={i}
            x1={positions[a].x}
            y1={positions[a].y}
            x2={positions[b].x}
            y2={positions[b].y}
            stroke="#bdcada"
            strokeWidth={2}
          />
        ) : null,
      )}
      {snapshot.values.map((n) =>
        positions[n] ? (
          <g
            key={n}
            className={`${snapshot.active.includes(n) ? 'active' : ''} ${snapshot.sorted.includes(n) ? 'visited' : ''}`}
            transform={`translate(${positions[n].x},${positions[n].y})`}
          >
            <circle r={25} />
            <text textAnchor="middle" y={6}>
              {bfs ? String.fromCharCode(65 + n) : n}
            </text>
          </g>
        ) : null,
      )}
      {bfs && snapshot.visited?.length ? (
        <text x="360" y="365" textAnchor="middle" fill="#4c647c" fontSize={14}>
          已访问：{snapshot.visited.map((n) => String.fromCharCode(65 + n)).join(' → ')}
        </text>
      ) : null}
    </svg>
  )
}
