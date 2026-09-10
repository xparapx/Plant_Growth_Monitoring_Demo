import { useSetup } from './setupCtx'
import { ss } from './strings'

const TINT = { good: 'border-ok/40 bg-ok-soft text-ok-ink', warn: 'border-warn/40 bg-warn-soft text-warn-ink', info: 'border-primary/30 bg-info-soft text-ink' } as const

/** Last action message (status.msg) — or the last HTTP error (409 camera_busy etc.). */
export function SetupMessage() {
  const { status, error, disabled } = useSetup()
  const text = error ?? (disabled ? ss.busyJob : status.msg)
  const level: keyof typeof TINT = error ? 'warn' : status.msg_level in TINT ? status.msg_level : 'info'
  return (
    <div className={`rounded-md border px-3.5 py-2.5 text-[13px] ${TINT[level]}`} aria-live="polite" aria-label={ss.message}>
      <span className="num">{text || '—'}</span>
    </div>
  )
}
