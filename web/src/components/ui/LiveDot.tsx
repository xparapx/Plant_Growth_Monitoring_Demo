import { useLiveStore } from '@/live/liveStore'
import { ko } from '@/i18n/ko'

export function LiveDot() {
  const { connected, mock } = useLiveStore()
  const label = mock ? ko.live.mock : connected ? ko.live.on : ko.live.off
  const color = mock ? 'var(--dummy)' : connected ? 'var(--ok)' : 'var(--warn)'
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-muted" title={label} aria-label={label} role="status">
      <span className="relative inline-flex h-2.5 w-2.5">
        {connected && !mock && <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40" style={{ background: color }} />}
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      </span>
      <span className="hidden sm:inline">{mock ? 'MOCK' : connected ? 'LIVE' : 'POLL'}</span>
    </span>
  )
}
