import { useEffect, useState } from 'react'
import {
  listWatch, addWatch, removeWatch, listAlerts, ackAlert, scanMonitor, getMonitorStatus,
} from '../api'

function fmtTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour12: false })
}

export default function MonitorView() {
  const [items, setItems] = useState([])
  const [alerts, setAlerts] = useState([])
  const [status, setStatus] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState('')

  async function load() {
    try {
      const [w, a, s] = await Promise.all([listWatch(), listAlerts(50), getMonitorStatus()])
      setItems(w)
      setAlerts(a)
      setStatus(s)
    } catch (err) {
      setBusy(err.message)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [])

  async function add() {
    const symbol = input.trim()
    if (!symbol) return
    setBusy('添加中……')
    try {
      const res = await addWatch(symbol)
      setInput('')
      setBusy(`已添加 ${res.name || res.symbol}`)
      await load()
    } catch (err) {
      setBusy(err.message)
    }
  }

  async function scan() {
    setBusy('扫描中……')
    try {
      const res = await scanMonitor()
      setBusy(`新增 ${res.created} 条告警`)
      await load()
    } catch (err) {
      setBusy(err.message)
    }
  }

  return (
    <div className="page">
      <div className="card chart-card">
        <div className="chart-title">
          自选股监控
          <span className="monitor-status">
            {status?.trading_hours ? '交易时段' : '非交易时段'} · 上次扫描{' '}
            {status?.last_scan ? fmtTime(status.last_scan) : '未扫描'} · 今日告警{' '}
            {status?.alerts_today ?? 0}
          </span>
        </div>

        <div className="kb-create">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="股票代码，如 600519 / 000001"
            onKeyDown={(e) => e.key === 'Enter' && add()}
          />
          <button onClick={add}>添加</button>
          <button onClick={scan}>立即扫描</button>
        </div>
        <div className="meta">{busy}</div>

        <table className="quote-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>现价</th>
              <th>涨跌幅</th>
              <th>振幅</th>
              <th>换手率</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const q = it.quote || {}
              const pct = q.change_pct ?? 0
              return (
                <tr key={it.symbol}>
                  <td>
                    {it.name || q.name || it.symbol}
                    <span className="code">{it.symbol}</span>
                  </td>
                  <td>{q.price ?? '-'}</td>
                  <td className={pct >= 0 ? 'up' : 'down'}>
                    {q.change_pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '-'}
                  </td>
                  <td>{q.amplitude != null ? `${q.amplitude.toFixed(2)}%` : '-'}</td>
                  <td>{q.turnover != null ? `${q.turnover.toFixed(2)}%` : '-'}</td>
                  <td>
                    <button className="del" onClick={() => removeWatch(it.symbol).then(load)}>
                      ×
                    </button>
                  </td>
                </tr>
              )
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-cell">
                  还没有自选股，输入代码添加
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card chart-card">
        <div className="chart-title">异动告警</div>
        {alerts.length === 0 ? (
          <div className="empty">暂无告警。可以点「立即扫描」触发一次。</div>
        ) : (
          <div className="alert-list">
            {alerts.map((a) => (
              <div key={a.id} className={`alert-item ${a.ack ? 'acked' : ''}`}>
                <div className="alert-head">
                  <b>{a.name}</b>
                  <span className="code">{a.symbol}</span>
                  <span className={a.change_pct >= 0 ? 'up' : 'down'}>{a.change_pct?.toFixed(2)}%</span>
                  <span className="alert-rule">{a.title}</span>
                  <span className="alert-time">{fmtTime(a.created_at)}</span>
                  {!a.ack && (
                    <button className="ack" onClick={() => ackAlert(a.id).then(load)}>
                      已读
                    </button>
                  )}
                </div>
                {a.analysis && <div className="alert-analysis">{a.analysis}</div>}
              </div>
            ))}
          </div>
        )}
        <div className="hint-card">
          监控为 5 分钟级轮询，只在交易时段自动运行；告警由规则触发后调用模型解读。
          <b>仅供信息参考，不构成投资建议。</b>
        </div>
      </div>
    </div>
  )
}
