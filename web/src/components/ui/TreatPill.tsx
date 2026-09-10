import { TREAT_NAME, trtVar } from '@/lib/treat'

/** Filled treatment pill from the mockup: stable = #7FB3D8 with navy text, fluct = #D84C27 with light text. */
export function TreatPill({ treat, label, size = 'sm', className = '' }: { treat: string | null | undefined; label?: string; size?: 'sm' | 'lg'; className?: string }) {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  return (
    <span
      className={`pill ${size === 'lg' ? 'pill-lg' : ''} ${className}`}
      style={t ? { background: trtVar(t, 'fill'), color: trtVar(t, 'on') } : { background: 'var(--bg-sunken)', color: 'var(--ink-muted)' }}
    >
      {label ?? (t ? TREAT_NAME[t] : '—')}
    </span>
  )
}

/** Verdict pill: ok → stable fill, not ok → accent fill (ALIGNED / SEPARATED in the mockup). */
export function VerdictPill({ ok, children, size = 'sm', tone }: { ok: boolean; children: string; size?: 'sm' | 'lg'; tone?: 'stable' | 'accent' }) {
  const t = tone ?? (ok ? 'stable' : 'accent')
  return (
    <span
      className={`pill ${size === 'lg' ? 'pill-lg' : ''}`}
      style={t === 'stable' ? { background: 'var(--stable)', color: 'var(--stable-on)' } : { background: 'var(--accent)', color: '#F2F2F2' }}
    >
      {children}
    </span>
  )
}

/** Soft tinted pill ("P2 F" grid in the mockup's treatment step). */
export function TreatTag({ treat, children }: { treat: string | null | undefined; children: React.ReactNode }) {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  return (
    <span
      className="rounded-[7px] px-0 py-1.5 text-center text-[10px] font-medium"
      style={t ? { background: `color-mix(in srgb, ${trtVar(t, 'fill')} 15%, transparent)`, color: trtVar(t, 'ink') } : { background: 'var(--bg-sunken)', color: 'var(--ink-muted)' }}
    >
      {children}
    </span>
  )
}
