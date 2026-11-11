import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Eye, Play, RotateCcw } from 'lucide-react'
import { Button } from '../ui'
import type { Row } from '../api'

const INITIAL = [12, 24, 36]
export function CollectionLab({ mode, onState }: { mode: string; onState: (state: Row) => void }) {
  const [items, setItems] = useState(INITIAL)
  const [input, setInput] = useState('48')
  const [trace, setTrace] = useState<Row[]>([])
  const [message, setMessage] = useState('选择一个操作，观察结构变化。')
  const [result, setResult] = useState<number | null>(null)
  const [motion, setMotion] = useState('')
  const [locked, setLocked] = useState(false)
  const [prediction, setPrediction] = useState('')
  const [check, setCheck] = useState<Row | null>(null)
  const [replayIndex, setReplayIndex] = useState<number | null>(null)
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const stack = mode === 'stack'
  const displayed = replayIndex === null ? items : replayIndex === 0 ? INITIAL : trace[replayIndex - 1].after
  useEffect(() => () => { if (timeout.current) clearTimeout(timeout.current) }, [])
  useEffect(() => {
    onState({ experiment: mode, input: INITIAL, operations: trace.length, operation_sequence: trace,
      final_state: items, prediction: check, participation_completed: trace.filter(item => item.success).length >= 3,
      understanding_checked: Boolean(check), understanding_correct: check?.correct ?? null })
  }, [items, trace, check, mode])
  useEffect(() => {
    if (replayIndex === null) return
    if (replayIndex >= trace.length) { const timer = setTimeout(() => setReplayIndex(null), 900); return () => clearTimeout(timer) }
    const timer = setTimeout(() => setReplayIndex(index => index! + 1), 700)
    return () => clearTimeout(timer)
  }, [replayIndex, trace.length])
  function perform(kind: 'push' | 'pop' | 'peek') {
    if (locked || replayIndex !== null) return
    const value = Number(input)
    let after = [...items], output: number | null = null, success = true
    if (kind === 'push') {
      if (!Number.isFinite(value) || value < 1 || value > 99 || items.length >= 10) { success = false; setMessage(items.length >= 10 ? '已达到容量10，先移除一个元素。' : '请输入1–99之间的数值。') }
      else { after.push(value); setMessage(`${stack ? '入栈' : '入队'} ${value}，元素数 ${items.length} → ${after.length}`) }
    } else if (!items.length) { success = false; setMessage('结构为空，请先加入元素。') }
    else {
      output = stack ? items[items.length - 1] : items[0]
      if (kind === 'pop') { after = stack ? items.slice(0, -1) : items.slice(1); setMessage(`${stack ? '出栈' : '出队'} ${output}，元素数 ${items.length} → ${after.length}`) }
      else setMessage(`${stack ? '栈顶' : '队首'}为 ${output}，结构保持当前状态。`)
    }
    setTrace(previous => [...previous, { kind, before: items, after, value: kind === 'push' ? value : output, success }])
    if (!success) return
    setResult(output)
    setItems(after)
    setMotion(kind)
    setLocked(true)
    timeout.current = setTimeout(() => { setLocked(false); setMotion('') }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 320)
  }
  return <div className="collection-lab">
    <div className={`collection-scene ${stack ? 'is-stack' : 'is-queue'} motion-${motion}`}>
      <div className="collection-port"><span>待加入</span><strong>{input || '—'}</strong><small>容量 {items.length}/10</small></div>
      <div className="collection-structure"><div className="structure-pointer">{stack ? '栈顶' : '队首'} <strong>{displayed.length ? stack ? displayed.at(-1) : displayed[0] : '空'}</strong></div>
        <div className="structure-body">{displayed.length ? displayed.map((value: number, index: number) => <div className={`structure-item ${index === displayed.length - 1 ? 'last' : ''}`} key={`${index}-${value}`}><strong>{value}</strong><small>{index}</small></div>) : <div className="structure-empty">空结构</div>}</div>
        <div className="structure-base">{stack ? '栈底' : '队尾'} <span>{stack ? '后进先出' : '先进先出'}</span></div>
      </div>
      <div className="collection-port result-port"><span>{motion === 'peek' ? '查看结果' : '移出结果'}</span><strong>{replayIndex !== null ? trace[replayIndex - 1]?.value ?? '—' : result ?? '—'}</strong><small>{replayIndex !== null ? `回放 ${replayIndex}/${trace.length}` : `${trace.length}次操作`}</small></div>
    </div>
    <p className="collection-message" role="status">{replayIndex !== null ? trace[replayIndex - 1]?.kind || '初始状态' : message}</p>
    <div className="collection-controls">
      <input type="number" min="1" max="99" aria-label="待加入元素" value={input} onChange={event => setInput(event.target.value)} />
      <Button disabled={locked || replayIndex !== null} onClick={() => perform('push')}><ArrowDown size={16} />{stack ? '压栈' : '入队'}</Button>
      <Button variant="secondary" disabled={locked || replayIndex !== null} onClick={() => perform('pop')}><ArrowUp size={16} />{stack ? '出栈' : '出队'}</Button>
      <Button variant="secondary" disabled={locked || replayIndex !== null} onClick={() => perform('peek')}><Eye size={16} />{stack ? '查看栈顶' : '查看队首'}</Button>
      <Button variant="icon secondary" aria-label="回放操作过程" disabled={!trace.length || locked || replayIndex !== null} onClick={() => setReplayIndex(0)}><Play size={16} /></Button>
      <Button variant="icon secondary" aria-label="重置结构" onClick={() => { if (timeout.current) clearTimeout(timeout.current); setItems(INITIAL); setTrace([]); setResult(null); setCheck(null); setReplayIndex(null); setLocked(false); setMotion(''); setMessage('已恢复初始结构。') }}><RotateCcw size={16} /></Button>
    </div>
    <details className="collection-check"><summary>预测与操作记录</summary><label>下一次{stack ? '出栈' : '出队'}的元素<input aria-label="预测移出元素" value={prediction} onChange={event => setPrediction(event.target.value)} /></label><Button variant="secondary small" onClick={() => setCheck({ answer: prediction, expected: String(items.length ? stack ? items.at(-1) : items[0] : '空'), correct: prediction === String(items.length ? stack ? items.at(-1) : items[0] : '空'), state: items })}>检查预测</Button>{check && <p role="status">{check.correct ? '预测正确' : `请再观察操作端，预期为${check.expected}`}</p>}
      <ol>{trace.map((entry, index) => <li key={index}>{entry.kind} {entry.value ?? ''}　[{entry.before.join(', ')}] → [{entry.after.join(', ')}]{entry.success ? '' : '，边界操作未执行'}</li>)}</ol>
    </details>
  </div>
}
