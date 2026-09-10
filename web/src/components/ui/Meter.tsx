export function Meter({ value, max, label, tone }: { value: number; max: number; label?: string; tone?: 'ok' | 'warn' | 'bad' }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  const color = tone === 'bad' ? 'var(--bad)' : tone === 'warn' ? 'var(--warn)' : 'var(--primary)'
  return (
    <div className="w-full" role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
      <div className="h-2 w-full overflow-hidden rounded-full bg-sunken">
        <div className="h-full rounded-full transition-[width] duration-[var(--dur-slow)]" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}
