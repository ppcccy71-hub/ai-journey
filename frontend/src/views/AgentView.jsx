import { useState, useRef } from 'react'
import { runAgent } from '../api'

export default function AgentView() {
  const [input, setInput] = useState('')
  const [answer, setAnswer] = useState('')
  const [trace, setTrace] = useState([])
  const [meta, setMeta] = useState('')
  const [loading, setLoading] = useState(false)
  const boxRef = useRef(null)

  async function run() {
    const task = input.trim()
    if (!task || loading) return
    setInput('')
    setAnswer('执行中……')
    setTrace([])
    setMeta('')
    setLoading(true)

    try {
      const data = await runAgent(task)
      setAnswer(data.answer || '（无回答）')
      setTrace(data.trace || [])
      setMeta(
        `${(data.latency_ms / 1000).toFixed(1)}s · 工具调用 ${data.trace?.length || 0} 次` +
          (data.files?.length ? ` · 工作区：${data.files.join('、')}` : ''),
      )
    } catch (err) {
      setAnswer('出错了：' + err.message)
    } finally {
      setLoading(false)
      boxRef.current?.focus()
    }
  }

  return (
    <div className="page">
      <div className="card">
        <div className="answer">
          {answer || '给它一个任务，比如「查一下切块建议，写到 report.md，再读回来」'}
        </div>

        {trace.length > 0 && (
          <div className="trace">
            {trace.map((t, i) => (
              <div key={i}>
                <span className="tool">
                  [{t.step}] {t.tool}
                </span>{' '}
                {JSON.stringify(t.args).slice(0, 80)}
                <br />
                <span className="result">← {String(t.result).slice(0, 120)}</span>
              </div>
            ))}
          </div>
        )}
        <div className="meta">{meta}</div>
      </div>

      <div className="bar">
        <input
          ref={boxRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && run()}
          placeholder="输入任务，回车执行"
          autoFocus
        />
        <button className="agent-btn" onClick={run} disabled={loading}>
          {loading ? '执行中' : '执行'}
        </button>
      </div>
    </div>
  )
}
