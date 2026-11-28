import { useState, useRef, useEffect } from 'react'
import { askStream, getSession } from '../api'

export default function AskView({ sessionId, onChanged, onNeedSession, kb, kbs, onKbChange }) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState('')
  const [sources, setSources] = useState([])
  const [meta, setMeta] = useState('')
  const [refused, setRefused] = useState(false)
  const [loading, setLoading] = useState(false)
  const [input, setInput] = useState('')
  const [mode, setMode] = useState('quality')
  const [web, setWeb] = useState(false)
  const boxRef = useRef(null)
  const bottomRef = useRef(null)

  // 切换会话：重新加载历史
  useEffect(() => {
    setMessages([])
    setStreaming('')
    setSources([])
    setMeta('')
    setRefused(false)
    if (!sessionId) return
    let alive = true
    getSession(sessionId)
      .then((data) => {
        if (alive) setMessages(data.messages || [])
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [sessionId])

  // 新消息时滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  async function send() {
    const question = input.trim()
    if (!question || loading) return

    let sid = sessionId
    if (!sid && onNeedSession) sid = await onNeedSession()

    setInput('')
    setStreaming('')
    setSources([])
    setRefused(false)
    setMeta('检索中……')
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'user', content: question }])

    let acc = ''
    try {
      await askStream(question, sid, (evt) => {
        if (evt.type === 'sources') {
          setSources(evt.sources || [])
          setMeta(evt.sources?.length ? '生成中……' : '未检索到资料')
        } else if (evt.type === 'delta') {
          acc += evt.text
          setStreaming(acc)
        } else if (evt.type === 'refused') {
          acc = evt.text
          setStreaming(acc)
          setRefused(true)
          setMeta('拒答 · 0 token')
        } else if (evt.type === 'done') {
          const u = evt.usage || {}
          setMeta(
            `${(evt.latency_ms / 1000).toFixed(2)}s · token ${u.prompt_tokens || 0}→` +
              `${u.completion_tokens || 0} · $${(evt.cost || 0).toFixed(6)}`,
          )
        }
      }, mode, kb, web)
    } catch (err) {
      acc = '出错了：' + err.message
    } finally {
      setMessages((prev) => [...prev, { role: 'assistant', content: acc }])
      setStreaming('')
      setLoading(false)
      onChanged?.()
      boxRef.current?.focus()
    }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && !streaming && (
          <div className="empty">
            <b>问点什么</b>
            比如「RAG 有哪几个步骤？」「怎么声明请求体？」
            <br />
            回答会标注出处；资料里没有的会直接拒答。
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            <div className={`avatar ${m.role === 'user' ? 'me' : 'ai'}`}>
              {m.role === 'user' ? '我' : 'AI'}
            </div>
            <div className={`bubble ${m.role}`}>{m.content}</div>
          </div>
        ))}

        {streaming && (
          <div className="row assistant">
            <div className="avatar ai">AI</div>
            <div className={`bubble assistant ${refused ? 'refused' : ''}`}>{streaming}</div>
          </div>
        )}

        {loading && !streaming && (
          <div className="row assistant">
            <div className="avatar ai">AI</div>
            <div className="bubble assistant">
              <span className="typing">
                <i />
                <i />
                <i />
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-footer">
        {sources.length > 0 && (
          <div className="chips">
            {sources.map((s) => {
              const isUrl = s.source.startsWith('http')
              let label = s.source
              if (isUrl) {
                try {
                  label = new URL(s.source).hostname
                } catch {
                  label = s.source
                }
              }
              return (
                <span key={s.index} className="chip">
                  [{s.index}]{' '}
                  {isUrl ? (
                    <a href={s.source} target="_blank" rel="noreferrer">
                      {label}
                    </a>
                  ) : (
                    s.source
                  )}{' '}
                  · {s.score}
                </span>
              )
            })}
          </div>
        )}
        <div className="meta-row">
          <select className="kb-select" value={kb} onChange={(e) => onKbChange(e.target.value)}>
            <option value="all">全部知识库</option>
            {(kbs || []).map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </select>
          <div className="mode-switch">
            <button className={mode === 'quality' ? 'on' : ''} onClick={() => setMode('quality')}>
              质量
            </button>
            <button className={mode === 'speed' ? 'on' : ''} onClick={() => setMode('speed')}>
              速度
            </button>
            <button
              className={web ? 'on' : ''}
              onClick={() => setWeb((v) => !v)}
              title="用网页搜索结果回答；关闭时只查本地知识库"
            >
              联网
            </button>
          </div>
          <div className="meta">{meta}</div>
        </div>
        <div className="input-row">
          <input
            ref={boxRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="输入问题，回车发送"
            autoFocus
          />
          <button onClick={send} disabled={loading}>
            {loading ? '生成中' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}
