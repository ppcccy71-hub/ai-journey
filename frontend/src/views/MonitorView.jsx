import { useEffect, useState } from 'react'
import {
  listWatch, addWatch, removeWatch, listAlerts, ackAlert, scanMonitor, getMonitorStatus,
  getKline, getSectors, getSectorStocks,
} from '../api'
import KLineChart from './KLineChart'

function fmtTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour12: false })
}

const PERIODS = [
  ['day', '日 K'],
  ['week', '周 K'],
  ['month', '月 K'],
]

export default function MonitorView() {
  const [items, setItems] = useState([])
  const [alerts, setAlerts] = useState([])
  const [status, setStatus] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState('')

  const [selected, setSelected] = useState('')
  const [period, setPeriod] = useState('day')
  const [bars, setBars] = useState([])
  const [sectors, setSectors] = useState([])
  const [sector, setSector] = useState(null)
  const [sectorStocks, setSectorStocks] = useState([])

  async function load() {
    try {
      const [w, a, s, sec] = await Promise.all([
        listWatch(), listAlerts(50), getMonitorStatus(), getSectors(16),
      ])
      setItems(w)
      setAlerts(a)
      setStatus(s)
      setSectors(sec)
      if (w.length) setSelected((prev) => prev || w[0].symbol)
    } catch (err) {
      setBusy(err.message)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 20000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!selected) return
    let alive = true
    getKline(selected, period, 120)
      .then((data) => alive && setBars(data))
      .catch(() => alive && setBars([]))
    return () => {
      alive = false
    }
  }, [selected, period])

  async function add() {
    const symbol = input.trim()
    if (!symbol) return
    setBusy('添加中……')
    try {
      const res = await addWatch(symbol)
      setInput('')
      setBusy(`已添加 ${res.name || res.symbol}`)
      await load()
      setSelected(res.symbol)
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

  async function openSector(code, name) {
    setSector({ code, name })
    try {
      setSectorStocks(await getSectorStocks(code, 10))
    } catch {
      setSectorStocks([])
    }
  }

  const current = items.find((it) => it.symbol === selected) || {}
  const currentQuote = current.quote || {}

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
                <tr
                  key={it.symbol}
                  className={it.symbol === selected ? 'selected' : ''}
                  onClick={() => setSelected(it.symbol)}
                >
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
                    <button
                      className="del"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeWatch(it.symbol).then(load)
                      }}
                    >
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

      <div className="monitor-grid">
        <div className="card chart-card">
          <div className="chart-title kline-head">
            {selected ? (
              <>
                <b>{current.name || currentQuote.name || selected}</b>
                <span className="price">
                  {currentQuote.price ?? '-'} ·{' '}
                  <span className={(currentQuote.change_pct ?? 0) >= 0 ? 'up' : 'down'}>
                    {(currentQuote.change_pct ?? 0) >= 0 ? '+' : ''}
                    {(currentQuote.change_pct ?? 0).toFixed(2)}%
                  </span>
                </span>
                <div className="period-switch">
                  {PERIODS.map(([key, label]) => (
                    <button
                      key={key}
                      className={period === key ? 'on' : ''}
                      onClick={() => setPeriod(key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              'K 线图'
            )}
          </div>
          {selected ? (
            <KLineChart bars={bars} />
          ) : (
            <div className="empty" style={{ padding: '36px 0' }}>
              点击上方自选股查看 K 线
            </div>
          )}
        </div>

        <div className="card chart-card">
          <div className="chart-title">行业板块</div>
          <div className="sector-list">
            {sectors.map((s) => (
              <div
                key={s.code}
                className={`sector-item ${sector?.code === s.code ? 'on' : ''}`}
                onClick={() => openSector(s.code, s.name)}
              >
                <span className="name">{s.name}</span>
                <span className="sector-leader">{s.leader}</span>
                <span className={s.change_pct >= 0 ? 'up' : 'down'}>
                  {s.change_pct >= 0 ? '+' : ''}
                  {s.change_pct.toFixed(2)}%
                </span>
              </div>
            ))}
            {sectors.length === 0 && <div className="empty">暂无板块数据</div>}
          </div>

          {sector && (
            <div className="sector-stocks">
              <div className="title">{sector.name} · 领涨个股</div>
              {sectorStocks.map((x) => (
                <div key={x.code} className="sector-item">
                  <span className="name">
                    {x.name} <span className="code">{x.code}</span>
                  </span>
                  <span>{x.price?.toFixed(2)}</span>
                  <span className={x.change_pct >= 0 ? 'up' : 'down'}>
                    {x.change_pct >= 0 ? '+' : ''}
                    {x.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
              {sectorStocks.length === 0 && <div className="empty">暂无数据</div>}
            </div>
          )}
        </div>
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
          监控为 5 分钟级轮询，只在交易时段自动运行；K 线与板块数据来自公开行情接口，可能有延迟。
          <b>仅供信息参考，不构成投资建议。</b>
        </div>
      </div>
    </div>
  )
}
