import { useEffect, useState, useCallback } from 'react'
import { listSessions, createSession, deleteSession } from './api'
import AskView from './views/AskView'
import AgentView from './views/AgentView'
import StatsView from './views/StatsView'

export default function App() {
  const [tab, setTab] = useState('ask')
  const [sessions, setSessions] = useState([])
  const [currentId, setCurrentId] = useState(null)
  const [booting, setBooting] = useState(true)

  const refresh = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
    return list
  }, [])

  // 启动：加载会话列表；一个都没有就自动建一个
  useEffect(() => {
    ;(async () => {
      let list = await refresh()
      if (list.length === 0) {
        const created = await createSession('第一次对话')
        list = await refresh()
        setCurrentId(created.id)
      } else {
        setCurrentId(list[0].id)
      }
      setBooting(false)
    })()
  }, [refresh])

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

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="dot" />
          <h1>个人工作助手</h1>
          <span className="tag">RAG + Agent</span>
        </div>
        <nav>
          <button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}>
            知识问答
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
      ) : tab === 'agent' ? (
        <AgentView />
      ) : (
        <StatsView />
      )}
    </div>
  )
}
