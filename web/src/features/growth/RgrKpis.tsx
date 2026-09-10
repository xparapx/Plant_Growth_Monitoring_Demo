import type { UseQueryResult } from '@tanstack/react-query'
import type { Rgr } from '@/api/types'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { KpiTile } from '@/components/ui/KpiTile'
import { QueryState } from '@/components/ui/QueryState'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { G } from './strings'

const LABEL: Record<string, string> = { stable: ko.rgr.stable, fluct: ko.rgr.fluct }

/** Group RGR means + Cohen's d. Only the groups that exist are shown; d only when comparable. */
export function RgrKpis({ q }: { q: UseQueryResult<Rgr> }) {
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-24" />}>
      {(r) => {
        const groups = Object.keys(r.groups ?? {})
        if (!groups.length) return null
        return (
          <div className="flex flex-col gap-3">
            {!r.comparable && <AlertBanner level="info">{ko.rgr.oneGroup}</AlertBanner>}
            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
              {groups.map((g) => {
                const v = r.groups[g]
                return <KpiTile key={g} label={LABEL[g] ?? `RGR ${g}`} value={v.mean} unit="/d" digits={4} deltaLabel={`sd ${fmtNum(v.sd, 4)} · n=${v.n}`} />
              })}
              {r.comparable && (
                <KpiTile label={ko.rgr.d} value={r.cohens_d} digits={2} deltaLabel={r.effect ? G.effect(r.effect) : ''} deltaTone={r.effect === 'large' ? 'ok' : 'muted'} />
              )}
            </div>
          </div>
        )
      }}
    </QueryState>
  )
}
