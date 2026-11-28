import { useState } from 'react'
import { authLogin, authRegister, setToken, getToken } from '../api'

export default function LoginView({ onDone }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit() {
    if (!username.trim() || !password) return
    setBusy(true)
    setError('')
    try {
      const data = mode === 'login'
        ? await authLogin(username.trim(), password)
        : await authRegister(username.trim(), password)
      setToken(data.token)
      onDone?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function tokenLogin() {
    const token = window.prompt('输入访问口令（管理员/Demo 用）', getToken())
    if (!token) return
    setToken(token.trim())
    onDone?.()
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <img className="login-logo" src="/logo.svg" alt="金鉴 AI" />
        <h1>金鉴 AI</h1>
        <p className="login-sub">金融合规问答 · 行情监控 · 金融计算</p>

        <div className="login-tabs">
          <button className={mode === 'login' ? 'on' : ''} onClick={() => setMode('login')}>登录</button>
          <button className={mode === 'register' ? 'on' : ''} onClick={() => setMode('register')}>注册</button>
        </div>

        <input value={username} onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名" autoComplete="username" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="密码（至少 6 位）" autoComplete="current-password"
          onKeyDown={(e) => e.key === 'Enter' && submit()} />
        {error && <div className="login-error">{error}</div>}
        <button className="login-btn" onClick={submit} disabled={busy}>
          {busy ? '请稍候……' : mode === 'login' ? '登录' : '注册并登录'}
        </button>
        <button className="login-link" onClick={tokenLogin}>用访问口令登录</button>
      </div>
    </div>
  )
}
