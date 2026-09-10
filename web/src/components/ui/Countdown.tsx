import { useEffect, useState } from 'react'
import { fmtDateTime } from '@/lib/format'

function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000))
  return { h: Math.floor(s / 3600), m: Math.floor((s % 3600) / 60), s: s % 60, total: s }
}

export function Countdown({ to, format = 'hms', onZero, className = '' }: { to: string | null | undefined; format?: 'hms' | 's'; onZero?: () => void; className?: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  useEffect(() => {
    if (to && new Date(to).getTime() <= now) onZero?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [now])
  if (!to) return <span className={`num ${className}`}>—</span>
  const p = parts(new Date(to).getTime() - now)
  const text = format === 's' ? `${p.total}s` : `${String(p.h).padStart(2, '0')}:${String(p.m).padStart(2, '0')}:${String(p.s).padStart(2, '0')}`
  return <span className={`num tabular-nums ${className}`} title={fmtDateTime(to)} aria-live="off">{text}</span>
}
