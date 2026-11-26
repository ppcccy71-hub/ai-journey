import { useEffect, useState, useCallback } from 'react'
import { listSessions, createSession, deleteSession, getToken, setToken, listKbs } from './api'
import AskView from './views/AskView'
import AgentView from './views/AgentView'
import StatsView from './views/StatsView'
import KnowledgeView from './views/KnowledgeView'

export default function App() {
  const [tab, setTab] = useState('ask')
  const [sessions, setSessions] = useState([])
  const [currentId, setCurrentId] = useState(null)
  const [booting, setBooting] = useState(true)
  const [hasToken, setHasToken] = useState(!!getToken())
  const [bootError, setBootError] = useState('')
  const [kbs, setKbs] = useState([])
  const [kb, setKb] = useState('all')

  const refresh = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
    return list
  }, [])

  // 启动：加载知识库列表
  useEffect(() => {
    listKbs()
      .then((items) => setKbs(items))
      .catch(() => {})
  }, [])

  // 启动：加载会话列表；一个都没有就自动建一个
  useEffect(() => {
    ;(async () => {
      try {
        let list = await refresh()
        if (list.length === 0) {
          const created = await createSession('第一次对话')
          list = await refresh()
          setCurrentId(created.id)
        } else {
          setCurrentId(list[0].id)
        }
      } catch (err) {
        setBootError(err.message)
      } finally {
        setBooting(false)
      }
    })()
  }, [refresh])

  function askToken() {
    const token = window.prompt('输入访问口令（没有就留空）', getToken())
    if (token === null) return
    setToken(token.trim())
    setHasToken(!!token.trim())
    window.location.reload()
  }

  async function newSession() {
    const created = await createSession('新会话')
    await refresh()
    setCurrentId(created.id)
    setTab('ask')
  }

  async function removeSession(id) {
    if (!window.confirm('删除这个会话？')) return
    await deleteSession(id)
    let list = await refresh()
    if (list.length === 0) {
      const created = await createSession('新会话')
      list = await refresh()
      setCurrentId(created.id)
    } else if (currentId === id) {
      setCurrentId(list[0].id)
    }
  }

  if (booting) return <div className="app">加载中……</div>

  if (bootError) {
    return (
      <div className="app">
        <div className="page">
          <div className="card">
            <div className="answer">需要访问口令才能使用。</div>
            <div className="meta">{bootError}</div>
            <div className="bar">
              <button className="agent-btn" onClick={askToken}>
                设置口令
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <img className="logo" src="/logo.svg" alt="logo" />
          <h1>个人工作助手</h1>
          <span className="tag">RAG + Agent</span>
          <button className="token-btn" onClick={askToken}>
            {hasToken ? '口令已设置' : '设置口令'}
          </button>
        </div>
        <nav>
          <button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}>
            知识问答
          </button>
          <button className={tab === 'kb' ? 'active' : ''} onClick={() => setTab('kb')}>
            知识库
          </button>
          <button className={tab === 'agent' ? 'active' : ''} onClick={() => setTab('agent')}>
            Agent 控制台
          </button>
          <button className={tab === 'stats' ? 'active' : ''} onClick={() => setTab('stats')}>
            统计
          </button>
        </nav>
      </header>

      {tab === 'ask' ? (
        <div className="layout">
          <aside className="sidebar">
            <button className="new-session" onClick={newSession}>
              + 新对话
            </button>
            <div className="session-list">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`session-item ${s.id === currentId ? 'active' : ''}`}
                  onClick={() => setCurrentId(s.id)}
                >
                  <div className="session-title">{s.title}</div>
                  <div className="session-meta">{s.msg_count} 条</div>
                  <button
                    className="del"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeSession(s.id)
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </aside>

          <main className="main">
            <AskView
              sessionId={currentId}
              kb={kb}
              kbs={kbs}
              onKbChange={setKb}
              onChanged={refresh}
              onNeedSession={async () => {
                const created = await createSession('新会话')
                await refresh()
                setCurrentId(created.id)
                return created.id
              }}
            />
          </main>
        </div>
      ) : tab === 'kb' ? (
        <KnowledgeView kb={kb} onSelect={setKb} onChanged={setKbs} />
      ) : tab === 'agent' ? (
        <AgentView sessionId={currentId} />
      ) : (
        <StatsView />
      )}
    </div>
  )
}
