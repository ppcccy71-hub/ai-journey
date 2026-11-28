import { useEffect, useState } from 'react'
import { getStats, getDailyStats } from '../api'

function Card({ label, value, hint }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export default function StatsView() {
  const [stats, setStats] = useState(null)
  const [daily, setDaily] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    getStats().then(setStats).catch((err) => setError(err.message))
    getDailyStats(7)
      .then((data) => setDaily(data.items || []))
      .catch((err) => setError(err.message))
  }, [])

  if (error && !stats) return <div className="page">统计加载失败：{error}</div>
  if (!stats) return <div className="page">加载中……</div>

  const maxQueries = Math.max(1, ...daily.map((d) => d.queries))
  const avgCost = stats.queries ? stats.total_cost / stats.queries : 0

  return (
    <div className="page">
      <div className="stats-grid">
        <Card label="会话数" value={stats.sessions} />
        <Card label="消息数" value={stats.messages} />
        <Card label="问答次数" value={stats.queries} />
        <Card
          label="总 token"
          value={(stats.tokens_in + stats.tokens_out).toLocaleString()}
          hint={`输入 ${stats.tokens_in} / 输出 ${stats.tokens_out}`}
        />
        <Card
          label="总成本"
          value={`$${stats.total_cost.toFixed(4)}`}
          hint={`约 ${(stats.total_cost * 7.2).toFixed(3)} 元`}
        />
        <Card
          label="平均延迟"
          value={`${(stats.avg_latency_ms / 1000).toFixed(2)}s`}
          hint={`单次约 $${avgCost.toFixed(6)}`}
        />
      </div>

      <div className="card chart-card">
        <div className="chart-title">最近 7 天问答量</div>
        {daily.length === 0 ? (
          <div className="empty">还没有数据，去问几个问题吧</div>
        ) : (
          <div className="chart">
            {daily.map((d) => (
              <div key={d.day} className="bar-col" title={`${d.queries} 次 · ${d.tokens} token`}>
                <div className="bar-wrap">
                  <div
                    className="bar-fill"
                    style={{ height: `${(d.queries / maxQueries) * 100}%` }}
                  />
                </div>
                <div className="bar-value">{d.queries}</div>
                <div className="bar-label">{d.day.slice(5)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card hint-card">
        <b>这些数字能说明什么</b>
        <ul>
          <li>单次成本 ≈ 模型调用 + 向量检索；目前主要在输入 token（资料块）上</li>
          <li>平均延迟包含检索（~1.5s）和生成（~0.8s），换更快的模型能压到 1s 内</li>
          <li>问答次数为 0 说明流量没进来，先解决“有没有人用”，再谈优化</li>
        </ul>
      </div>
    </div>
  )
}
