import { usePumpRecent } from '@/api/queries'
import type { Summary } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtHm } from '@/lib/format'
import { trtVar } from '@/lib/treat'

/** Mockup 3a right column, bottom: "급수 이벤트" — HH:MM · P4 fluct · dose 3.2s ✓ */
export function PumpEventsCard({ summary }: { summary: Summary }) {
  const q = usePumpRecent(3)
  return (
    <Card padded>
      <div className="mb-2 flex items-center gap-2">
        <span className="card-title !text-[12px]">{ko.pumpEvents.title}</span>
        {summary.dummy.includes('pump') && <DummyBadge />}
      </div>
      {q.isPending && <Skeleton lines={3} />}
      {q.data && q.data.rows.length === 0 && <p className="text-[11.5px] text-muted">{ko.pumpEvents.none}</p>}
      {q.data && q.data.rows.length > 0 && (
        <ul className="flex flex-col gap-1.5 text-[11.5px] text-muted">
          {q.data.rows.map((r) => {
            const treat = r.treat?.toLowerCase()
            const ok = r.rise !== null && r.rise > 0 && r.reason !== 'verify fail' && r.reason !== 'no rise'
            const right = r.pump_s !== null ? `${ko.pumpEvents.dose(r.pump_s)}${ok ? ' ✓' : ''}` : (r.reason ?? '—')
            return (
              <li key={r.ts + r.pot} className="flex gap-2.5">
                <span className="num">{fmtHm(r.ts)}</span>
                <span className="text-ink">{r.pot.toUpperCase()} {treat ?? ''}</span>
                <span className="num ml-auto" style={{ color: ok ? trtVar(treat, 'ink') : r.reason === 'verify fail' || r.reason === 'no rise' ? 'var(--bad-ink)' : undefined }}>{right}</span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
