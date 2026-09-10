export function Sparkline({ data, color, height = 52, flat = false, width = 200 }: { data: (number | null)[]; color: string; height?: number; flat?: boolean; width?: number }) {
  const vals = data.filter((v): v is number => v !== null && Number.isFinite(v))
  if (flat || vals.length < 2) {
    return (
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="block h-[52px] w-full" aria-hidden="true">
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="var(--ink-faint)" strokeWidth="1.5" strokeDasharray="3 4" />
      </svg>
    )
  }
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = max - min || 1
  const pad = 3
  const pts: string[] = []
  let i = 0
  const n = data.length
  for (const v of data) {
    if (v !== null && Number.isFinite(v)) {
      const x = (i / Math.max(1, n - 1)) * width
      const y = height - pad - ((v - min) / span) * (height - 2 * pad)
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`)
    }
    i++
  }
  const d = `M${pts.join(' L')}`
  const last = pts[pts.length - 1].split(',')
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="block h-[52px] w-full" aria-hidden="true">
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={color} opacity="0.10" />
      <path d={d} fill="none" stroke={color} strokeWidth="var(--lw-spark)" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r="2.6" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
