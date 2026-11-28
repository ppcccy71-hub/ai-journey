import { useEffect, useState } from 'react'
import { listKbs, listWatch, getSectors, getMonitorStatus, listAlerts } from '../api'

const FEATURES = [
  {
    key: 'ask',
    tag: '合规问答',
    title: '查法规、要出处',
    desc: '证券法、信息披露、投资者适当性 351 块，按条文切块；回答带条款编号，投资建议类问题直接拒答。',
    action: '去提问 →',
  },
  {
    key: 'monitor',
    tag: '行情监控',
    title: '自选股与板块',
    desc: '日/周/月 K 线、行业板块涨幅榜、领涨个股；异动规则触发后由模型写解读，30 分钟冷却。',
    action: '看行情 →',
  },
  {
    key: 'agent',
    tag: '金融计算',
    title: '让 Agent 帮你算',
    desc: '复利、等额本息/本金贷款、NPV、IRR、CAGR、持仓盈亏，6 类计算直接调用，附计算过程。',
    action: '打开 Agent →',
  },
]

const QUESTIONS = [
  '内幕信息知情人包括哪些人？',
  '上市公司定期报告包括哪些？',
  '投资者适当性管理的核心要求是什么？',
  '证券公司违反适当性义务会被怎么处理？',
]

function fmtTime(ts) {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour12: false })
}

function fmtPct(v) {
  if (v == null) return '-'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

export default function HomeView({ onNavigate, onAsk }) {
  const [live, setLive] = useState(null)
  const [liveError, setLiveError] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([listKbs(), getSectors(3), listWatch(), getMonitorStatus(), listAlerts(1)])
      .then(([kbs, sectors, watch, status, alerts]) => {
        if (!alive) return
        const finance = (kbs || []).find((k) => k.id === '金融合规')
        const movers = (watch || [])
          .filter((w) => w.quote)
          .sort((a, b) => b.quote.change_pct - a.quote.change_pct)
        setLive({
          finance,
          topSector: (sectors || [])[0] || null,
          watchCount: (watch || []).length,
          topMover: movers[0] || null,
          alerts: status?.alerts_today ?? 0,
          latestAlert: (alerts || [])[0] || null,
          trading: !!status?.trading_hours,
        })
      })
      .catch((err) => alive && setLiveError(err.message))
    return () => {
      alive = false
    }
  }, [])

  const status = {
    ask: live?.finance
      ? `${live.finance.chunk_count} 块法规 · 15/15`
      : '351 块法规 · 15/15',
    monitor: live?.topSector
      ? `自选 ${live.watchCount} 只 · ${live.topSector.name} ${fmtPct(live.topSector.change_pct)}`
      : 'K 线 · 板块 · 异动解读',
    agent: '6 类计算 · 21 个测试',
  }

  return (
    <div className="page home">
      <section className="card home-hero">
        <img className="home-logo" src="/logo.svg" alt="金鉴 AI" />
        <div className="home-hero-text">
          <h1>金鉴 AI</h1>
          <p className="home-tag">金融合规问答 · 行情监控 · 金融计算</p>
          <p className="home-desc">
            面向金融场景的 AI 助手：法规问题给出条款依据，行情异动给出模型解读，金融计算直接算给你看。
          </p>
          {live && (
            <div className="home-live">
              <span className={live.trading ? 'live-dot on' : 'live-dot'} />
              {live.trading ? '交易时段' : '非交易时段'} · 自选 {live.watchCount} 只 · 今日告警{' '}
              {live.alerts} 条
              {live.topMover?.quote && (
                <>
                  {' '}
                  · {live.topMover.name}{' '}
                  <b className={live.topMover.quote.change_pct >= 0 ? 'up' : 'down'}>
                    {fmtPct(live.topMover.quote.change_pct)}
                  </b>
                </>
              )}
            </div>
          )}
          {liveError && !live && (
            <div className="home-live muted">设置访问口令后显示实时数据</div>
          )}
          {live?.latestAlert && (
            <button className="home-alert" onClick={() => onNavigate('monitor')}>
              <span className="alert-dot" /> 最新告警 · {live.latestAlert.name}{' '}
              {live.latestAlert.title} · {fmtTime(live.latestAlert.created_at)}
            </button>
          )}
          <div className="home-actions">
            <button className="home-cta" onClick={() => onNavigate('ask')}>
              开始提问
            </button>
            <button className="home-ghost" onClick={() => onNavigate('monitor')}>
              查看行情
            </button>
          </div>
        </div>
      </section>

      <div className="home-grid">
        {FEATURES.map((f) => (
          <div key={f.key} className="card home-card" onClick={() => onNavigate(f.key)}>
            <div className="home-card-tag">{f.tag}</div>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
            <div className="home-card-status">{status[f.key]}</div>
            <span className="home-card-action">{f.action}</span>
          </div>
        ))}
      </div>

      <section className="card home-questions">
        <div className="chart-title">试试这些问题</div>
        <div className="home-chips">
          {QUESTIONS.map((q) => (
            <button key={q} className="home-chip" onClick={() => onAsk(q)}>
              {q}
            </button>
          ))}
        </div>
      </section>

      <div className="home-stats">
        {[
          [String(live?.finance?.chunk_count ?? 351), '块法规'],
          [live ? String(live.watchCount) : '—', '只自选股'],
          [live ? String(live.alerts) : '—', '今日告警'],
          ['21', '个测试'],
        ].map(([num, label]) => (
          <div key={label} className="home-stat">
            <b>{num}</b>
            <span>{label}</span>
          </div>
        ))}
      </div>

      <p className="home-disclaimer">
        内容仅供信息参考，不构成投资建议。行情与板块数据来自公开接口，可能有延迟。
      </p>
    </div>
  )
}
