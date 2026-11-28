import { useEffect, useState, useCallback } from 'react'
import { listSessions, createSession, deleteSession, getToken, setToken, listKbs, getMe, clearToken } from './api'
import AskView from './views/AskView'
import AgentView from './views/AgentView'
import StatsView from './views/StatsView'
import KnowledgeView from './views/KnowledgeView'
import MonitorView from './views/MonitorView'
import HomeView from './views/HomeView'
import LoginView from './views/LoginView'

export default function App() {
  const [tab, setTab] = useState(() => window.location.hash.slice(1) || 'home')
  const [sessions, setSessions] = useState([])
  const [currentId, setCurrentId] = useState(null)
  const [booting, setBooting] = useState(true)
  const [user, setUser] = useState(null)
  const [kbs, setKbs] = useState([])
  const [kb, setKb] = useState('')
  const [seedQuestion, setSeedQuestion] = useState('')
  const [bootError, setBootError] = useState('')

  const refresh = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
    return list
  }, [])

  // 启动：加载知识库列表
  useEffect(() => {
    listKbs()
      .then((items) => {
        setKbs(items)
        // 金融优先：有金融合规库就默认选它
        setKb((prev) => prev || (items.some((k) => k.id === '金融合规') ? '金融合规' : 'all'))
      })
      .catch(() => {})
  }, [])

  // 启动：先校验登录，再加载会话；一个都没有就自动建一个
  useEffect(() => {
    ;(async () => {
      if (!getToken()) {
        setBooting(false)
        return
      }
      try {
        const me = await getMe()
        setUser(me)
        let list = await refresh()
        if (list.length === 0) {
          const created = await createSession('第一次对话')
          list = await refresh()
          setCurrentId(created.id)
        } else {
          setCurrentId(list[0].id)
        }
      } catch (err) {
        clearToken()
        setUser(null)
      } finally {
        setBooting(false)
      }
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

  if (!user) {
    return <LoginView onDone={() => window.location.reload()} />
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <img className="logo" src="/logo.svg" alt="logo" />
          <h1>金鉴 AI</h1>
          <span className="tag">金融合规 · 行情 · 计算</span>
          <span className="user-chip">{user.username}</span>
          <button
            className="token-btn"
            onClick={() => {
              clearToken()
              window.location.reload()
            }}
          >
            退出
          </button>
        </div>
        <nav>
          <button className={tab === 'home' ? 'active' : ''} onClick={() => setTab('home')}>
            首页
          </button>
          <button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}>
            合规问答
          </button>
          <button className={tab === 'kb' ? 'active' : ''} onClick={() => setTab('kb')}>
            知识库
          </button>
          <button className={tab === 'monitor' ? 'active' : ''} onClick={() => setTab('monitor')}>
            行情监控
          </button>
          <button className={tab === 'agent' ? 'active' : ''} onClick={() => setTab('agent')}>
            Agent 控制台
          </button>
          <button className={tab === 'stats' ? 'active' : ''} onClick={() => setTab('stats')}>
            统计
          </button>
        </nav>
      </header>

      {tab === 'home' ? (
        <HomeView onNavigate={setTab} onAsk={(q) => { setSeedQuestion(q); setTab('ask') }} />
      ) : tab === 'ask' ? (
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
              seedQuestion={seedQuestion}
              onSeedUsed={() => setSeedQuestion('')}
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
      ) : tab === 'monitor' ? (
        <MonitorView />
      ) : tab === 'agent' ? (
        <AgentView sessionId={currentId} />
      ) : (
        <StatsView />
      )}
    </div>
  )
}
