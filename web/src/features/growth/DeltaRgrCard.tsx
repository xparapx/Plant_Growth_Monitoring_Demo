import type { UseQueryResult } from '@tanstack/react-query'
import type { Rgr } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'

/** Mockup 3c right: ΔRGR (F − S) in %/d, Cohen's d, pre-registration note. */
export function DeltaRgrCard({ q }: { q: UseQueryResult<Rgr> }) {
  const r = q.data
  const f = r?.groups.fluct?.mean, s = r?.groups.stable?.mean
  const delta = f !== undefined && s !== undefined ? (f - s) * 100 : null
  const n = r ? Object.values(r.groups).reduce((a, g) => a + g.n, 0) : 0
  return (
    <Card className="flex flex-col justify-center gap-2 md:col-span-2 xl:col-span-4" padded>
      <div className="label normal-case !tracking-[.12em]">{ko.deltaRgr.title}</div>
      {q.isPending && <Skeleton className="h-10 w-32" />}
      {r && (
        <>
          <div className="num text-[34px] font-semibold leading-none text-ink">
            {delta === null ? '—' : `${delta >= 0 ? '+' : ''}${fmtNum(delta, 2)}`} <span className="text-[15px] font-medium text-muted">%/d</span>
          </div>
          <p className="text-[11.5px] leading-relaxed text-muted">{r.comparable ? ko.deltaRgr.caption(r.cohens_d, n) : ko.deltaRgr.oneGroup}</p>
        </>
      )}
    </Card>
  )
}
