import { useState, useRef } from 'react'
import { agentStream, approveAgent } from '../api'

export default function AgentView({ sessionId }) {
  const [input, setInput] = useState('')
  const [answer, setAnswer] = useState('')
  const [events, setEvents] = useState([])
  const [meta, setMeta] = useState('')
  const [loading, setLoading] = useState(false)
  const [pending, setPending] = useState(null)
  const boxRef = useRef(null)
  const toolCount = useRef(0)

  async function run() {
    const task = input.trim()
    if (!task || loading) return

    setInput('')
    setAnswer('')
    setEvents([])
    setMeta('执行中……')
    setPending(null)
    setLoading(true)
    toolCount.current = 0

    try {
      await agentStream(task, sessionId, (evt) => {
        if (evt.type === 'approval_required') {
          setPending({ runId: evt.run_id, tool: evt.tool, args: evt.args })
          setMeta('等待确认写入……')
        } else if (evt.type === 'approval_result') {
          setEvents((prev) => [...prev, evt])
          setMeta(evt.approved ? '已批准，继续执行……' : '已拒绝，继续执行……')
        } else if (evt.type === 'answer') {
          setAnswer(evt.text)
        } else if (evt.type === 'done') {
          setMeta(`${(evt.latency_ms / 1000).toFixed(1)}s · 工具调用 ${toolCount.current} 次`)
        } else if (evt.type === 'error') {
          setAnswer('出错了：' + evt.message)
        } else {
          if (evt.type === 'tool_call') toolCount.current += 1
          setEvents((prev) => [...prev, evt])
        }
      })
    } catch (err) {
      setAnswer('出错了：' + err.message)
    } finally {
      setLoading(false)
      setPending(null)
      boxRef.current?.focus()
    }
  }

  async function decide(approved) {
    if (!pending) return
    try {
      await approveAgent(pending.runId, approved)
      setPending(null)
    } catch (err) {
      setMeta('审批失败：' + err.message)
    }
  }

  return (
    <div className="page">
      <div className="card">
        <div className="answer">
          {answer || '给它一个任务，比如「查一下怎么声明请求体，写到 report.md，再读回来」'}
        </div>

        {events.length > 0 && (
          <div className="trace">
            {events.map((e, i) => {
              if (e.type === 'step') {
                return (
                  <div key={i} className="trace-item muted">
                    第 {e.step} 轮结束（{e.finish_reason}）
                  </div>
                )
              }
              if (e.type === 'tool_call') {
                return (
                  <div key={i} className="trace-item">
                    <span className="tool">
                      [{e.step}] {e.tool}
                    </span>
                    {JSON.stringify(e.args).slice(0, 100)}
                  </div>
                )
              }
              if (e.type === 'tool_result') {
                return (
                  <div key={i} className="trace-item result">
                    ← {String(e.result).slice(0, 160)}
                  </div>
                )
              }
              if (e.type === 'approval_result') {
                return (
                  <div key={i} className="trace-item muted">
                    审批：{e.approved ? '已批准' : e.timeout ? '超时未处理' : '已拒绝'}
                  </div>
                )
              }
              return null
            })}
          </div>
        )}

        {pending && (
          <div className="approval">
            <div className="approval-title">需要确认：写入文件</div>
            <div className="approval-body">
              <code>{pending.tool}</code> {JSON.stringify(pending.args).slice(0, 160)}
            </div>
            <div className="approval-actions">
              <button className="ok" onClick={() => decide(true)}>
                允许写入
              </button>
              <button className="no" onClick={() => decide(false)}>
                拒绝
              </button>
            </div>
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
