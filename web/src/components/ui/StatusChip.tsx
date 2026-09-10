import { useEffect, useRef, useState } from 'react'

export type ChipState = 'ok' | 'amber' | 'bad' | 'off' | 'info'
const DOT: Record<ChipState, string> = { ok: 'var(--ok)', amber: 'var(--warn)', bad: 'var(--bad)', off: 'var(--ink-faint)', info: 'var(--primary)' }

export function StatusChip({ label, state, detail, pulseKey, title }: { label: string; state: ChipState; detail?: string; pulseKey?: number; title?: string }) {
  const [pulse, setPulse] = useState(false)
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    if (!pulseKey) return
    setPulse(true)
    const t = window.setTimeout(() => setPulse(false), 700)
    return () => window.clearTimeout(t)
  }, [pulseKey])
  return (
    <span className={`chip ${pulse ? 'pulse' : ''} ${state === 'bad' ? 'border-bad/40 bg-bad-soft' : ''} ${state === 'off' ? 'opacity-55' : ''}`} title={title} style={{ color: DOT[state] }}>
      <span className="dot" style={{ background: DOT[state] }} />
      <b className="text-ink">{label}</b>
      {detail && <span className={`num text-[10.5px] ${state === 'bad' ? 'text-bad-ink' : 'text-muted'}`}>{detail}</span>}
    </span>
  )
}
