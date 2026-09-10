import { AlertTriangle, CheckCircle2, Info, OctagonAlert, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

export type AlertLevel = 'bad' | 'warn' | 'info' | 'ok' | 'dummy'

const STYLE: Record<AlertLevel, { cls: string; Icon: typeof Info }> = {
  bad: { cls: 'bg-bad-soft text-bad-ink border-bad/40', Icon: OctagonAlert },
  warn: { cls: 'bg-warn-soft text-warn-ink border-warn/40', Icon: AlertTriangle },
  info: { cls: 'bg-info-soft text-ink border-primary/30', Icon: Info },
  ok: { cls: 'bg-ok-soft text-ok-ink border-ok/40', Icon: CheckCircle2 },
  dummy: { cls: 'bg-dummy-bg text-dummy border-dummy/40', Icon: Info },
}

export function AlertBanner({ level, title, children, dismissible, className = '' }: { level: AlertLevel; title?: ReactNode; children?: ReactNode; dismissible?: boolean; className?: string }) {
  const [gone, setGone] = useState(false)
  if (gone) return null
  const { cls, Icon } = STYLE[level]
  return (
    <div role={level === 'bad' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-md border px-3.5 py-3 text-[13px] ${cls} ${className}`}>
      <Icon size={17} className="mt-0.5 flex-none" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <div className="font-bold">{title}</div>}
        {children && <div className={title ? 'mt-0.5' : ''}>{children}</div>}
      </div>
      {dismissible && (
        <button type="button" aria-label="닫기" onClick={() => setGone(true)} className="-m-1 grid h-7 w-7 place-items-center rounded-md hover:bg-black/5">
          <X size={14} />
        </button>
      )}
    </div>
  )
}
