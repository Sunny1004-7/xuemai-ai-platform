import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Play, RotateCcw, Save } from 'lucide-react'
import { post, useApi } from '../api'
import type { Row } from '../api'
import { Button, Panel, Title, useApp } from '../ui'
import { Tabs } from './Workspace'

const cases: Record<
  string,
  {
    title: string
    knowledge: string
    code: string[]
    states: { line: number; values: Record<string, string>; note: string }[]
    answer: string
  }
> = {
  'py-loop': {
    title: '循环逐步执行',
    knowledge: '循环与条件',
    code: ['total = 0', 'for n in [1, 2, 3]:', '    total += n', 'print(total)'],
    states: [
      { line: 0, values: { total: '0', n: '未绑定' }, note: '先建立累计变量。' },
      { line: 1, values: { total: '0', n: '1' }, note: '取得第一个元素。' },
      { line: 2, values: { total: '1', n: '1' }, note: '第一次累计。' },
      { line: 2, values: { total: '3', n: '2' }, note: '第二次累计，保留原来的total。' },
      { line: 2, values: { total: '6', n: '3' }, note: '第三次累计。' },
      { line: 3, values: { total: '6', 输出: '6' }, note: '所有元素已处理，退出循环。' },
    ],
    answer: '6',
  },
  'py-branch': {
    title: '条件与变量状态',
    knowledge: '布尔表达式',
    code: [
      'score = 72',
      'if score >= 60:',
      '    result = "通过"',
      'else:',
      '    result = "待巩固"',
    ],
    states: [
      { line: 0, values: { score: '72', result: '未绑定' }, note: '输入固定为72。' },
      { line: 1, values: { score: '72', 条件: 'True' }, note: '72大于等于60，选择真分支。' },
      { line: 2, values: { score: '72', result: '通过' }, note: '跳过else分支，结果确定。' },
    ],
    answer: '通过',
  },
  'py-list': {
    title: '列表共享与切片',
    knowledge: '字符串与切片',
    code: ['a = [1, 2, 3]', 'b = a', 'c = a[:]', 'b.append(4)', 'print(len(c))'],
    states: [
      { line: 0, values: { a: '[1, 2, 3]' }, note: '创建一个列表对象。' },
      { line: 1, values: { a: '[1, 2, 3]', b: '与a共享对象' }, note: '赋值没有复制列表。' },
      {
        line: 2,
        values: { a: '[1, 2, 3]', c: '[1, 2, 3]（新对象）' },
        note: '浅切片创建新列表容器。',
      },
      {
        line: 3,
        values: { 'a / b': '[1, 2, 3, 4]', c: '[1, 2, 3]' },
        note: '通过b修改共享列表，c不变。',
      },
      { line: 4, values: { 'len(c)': '3', 输出: '3' }, note: 'c仍有三个元素。' },
    ],
    answer: '3',
  },
  'py-function': {
    title: '函数调用与参数',
    knowledge: '函数定义与返回',
    code: ['def double(x):', '    y = x * 2', '    return y', 'n = 4', 'result = double(n)'],
    states: [
      { line: 0, values: { 函数: 'double(x)' }, note: '定义函数，不执行函数体。' },
      { line: 3, values: { n: '4' }, note: '调用前绑定n。' },
      { line: 4, values: { n: '4', 局部x: '4' }, note: '进入新调用帧，形参绑定实参对象。' },
      { line: 1, values: { 局部x: '4', 局部y: '8' }, note: '在局部作用域计算。' },
      { line: 2, values: { 返回值: '8' }, note: 'return将值传回调用者。' },
      { line: 4, values: { n: '4', result: '8' }, note: '调用结束，局部帧退出，n未改变。' },
    ],
    answer: '8',
  },
}
export function PythonLab() {
  const { courseId, notify } = useApp()
  const [params] = useSearchParams()
  const [mode, setMode] = useState(
    cases[params.get('mode') || ''] ? params.get('mode')! : 'py-loop',
  )
  const [step, setStep] = useState(0)
  const [prediction, setPrediction] = useState('')
  const [feedback, setFeedback] = useState('')
  const graph = useApi<Row>(`/courses/${courseId}/graph`, { nodes: [] })
  const current = cases[mode],
    state = current.states[step]
  const kid = graph.data.nodes.find((n: Row) => n.title === current.knowledge)?.id
  return (
    <>
      <Title
        title="Python 交互实验室"
        action={
          <Button
            variant="secondary"
            onClick={async () => {
              try {
                await post('/events', {
                  course_id: courseId,
                  knowledge_id: kid,
                  kind: 'experiment',
                  payload: {
                    mode,
                    steps: step + 1,
                    prediction_correct: prediction === current.answer,
                  },
                })
                notify('实验记录已保存')
              } catch (e) {
                notify((e as Error).message, true)
              }
            }}
          >
            <Save size={16} />
            保存实验记录
          </Button>
        }
      />
      <Tabs
        value={mode}
        onChange={(v) => {
          setMode(v)
          setStep(0)
          setPrediction('')
          setFeedback('')
        }}
        items={Object.entries(cases).map(([id, c]) => [id, c.title])}
      />
      <div className="python-lab">
        <Panel title={current.title}>
          <pre className="python-code">
            {current.code.map((line, i) => (
              <span key={i} className={state.line === i ? 'active' : ''}>
                {i + 1}　{line}
              </span>
            ))}
          </pre>
          <p>{state.note}</p>
          <div className="experiment-controls">
            <Button variant="secondary" onClick={() => setStep(0)} aria-label="重置实验">
              <RotateCcw size={16} />
            </Button>
            <Button variant="secondary" disabled={!step} onClick={() => setStep(step - 1)}>
              上一步
            </Button>
            <span>
              {step + 1} / {current.states.length}
            </span>
            <Button disabled={step === current.states.length - 1} onClick={() => setStep(step + 1)}>
              <Play size={16} />
              下一步
            </Button>
          </div>
        </Panel>
        <Panel title="当前状态">
          <div className="python-state">
            {Object.entries(state.values).map(([name, value]) => (
              <div key={name}>
                <span>{name}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault()
              setFeedback(
                prediction.trim() === current.answer
                  ? '预测正确，请解释每一步变化。'
                  : '再比较执行顺序与变量绑定，返回上一步检查。',
              )
            }}
          >
            <label>
              预测最终输出
              <input
                aria-label="预测最终输出"
                value={prediction}
                onChange={(e) => setPrediction(e.target.value)}
                required
              />
            </label>
            <Button variant="secondary">检查预测</Button>
            {feedback ? <p role="status">{feedback}</p> : null}
          </form>
          <Link className="text-link" to={`/practice?course=${courseId}&knowledge=${kid || ''}`}>
            关联练习 →
          </Link>
        </Panel>
      </div>
    </>
  )
}
