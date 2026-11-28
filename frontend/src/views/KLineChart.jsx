export default function KLineChart({ bars }) {
  if (!bars || bars.length === 0) {
    return <div className="empty" style={{ padding: '24px 0' }}>暂无 K 线数据</div>
  }
  const W = 720
  const H = 280
  const padR = 52
  const priceH = 210
  const volTop = 228
  const volH = 40
  const lows = bars.map((b) => b.low)
  const highs = bars.map((b) => b.high)
  const min = Math.min(...lows)
  const max = Math.max(...highs)
  const span = max - min || 1
  const slot = (W - padR - 8) / bars.length
  const bw = Math.max(1.5, slot * 0.62)
  const volMax = Math.max(...bars.map((b) => b.volume)) || 1

  const y = (p) => 8 + ((max - p) / span) * (priceH - 16)
  const grid = [0, 0.25, 0.5, 0.75, 1].map((r) => {
    const p = max - span * r
    return { y: y(p), p }
  })

  return (
    <svg className="kline" viewBox={`0 0 ${W} ${H}`} role="img">
      {grid.map((g) => (
        <g key={g.p}>
          <line x1="8" x2={W - padR} y1={g.y} y2={g.y} stroke="#eef0f5" strokeWidth="1" />
          <text x={W - padR + 6} y={g.y + 3}>{g.p.toFixed(2)}</text>
        </g>
      ))}

      {bars.map((b, i) => {
        const x = 8 + slot * i + slot / 2
        const up = b.close >= b.open
        const color = up ? '#d93025' : '#188038'
        const top = y(Math.max(b.open, b.close))
        const bottom = y(Math.min(b.open, b.close))
        const h = Math.max(1, bottom - top)
        const vh = (b.volume / volMax) * volH
        return (
          <g key={b.date}>
            <line x1={x} x2={x} y1={y(b.high)} y2={y(b.low)} stroke={color} strokeWidth="1" />
            <rect x={x - bw / 2} y={top} width={bw} height={h} fill={color} />
            <rect x={x - bw / 2} y={volTop + volH - vh} width={bw} height={vh}
              fill={color} opacity="0.35" />
          </g>
        )
      })}

      <text x="8" y={H - 2}>{bars[0].date}</text>
      <text x={W - padR - 60} y={H - 2}>{bars[bars.length - 1].date}</text>
      <text x={W - padR + 6} y={volTop + 10}>量</text>
    </svg>
  )
}
