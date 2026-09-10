import { useState } from 'react'
import { useAnalytics, useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { CanopySeriesCard } from './CanopySeriesCard'
import { DeltaRgrCard } from './DeltaRgrCard'
import { ExportCard } from './ExportCard'
import { PhaseChips } from './PhaseChips'
import { PotGrid } from './PotGrid'
import { RgrForestCard } from './RgrForestCard'
import { RgrKpis } from './RgrKpis'
import { RgrTrendCard } from './RgrTrendCard'

/** Mockup 3c: phase chips → 3×2 pot cards with canopy projections → RGR 추이 + ΔRGR → detail cards. */
export default function GrowthPage() {
  const q = useSummary()
  const rgr = useAnalytics('rgr')
  const [mask, setMask] = useState(true)
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <div className="flex flex-col gap-3.5">
          <div className="flex justify-end"><PhaseChips mask={mask} onMask={setMask} /></div>
          <CardGrid className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-12">
            <PotGrid summary={s} rgr={rgr} mask={mask} />
            <RgrTrendCard summary={s} />
            <DeltaRgrCard q={rgr} />
            <div className="md:col-span-2 xl:col-span-12"><RgrKpis q={rgr} /></div>
            <div className="md:col-span-2 xl:col-span-12"><CanopySeriesCard summary={s} /></div>
            <div className="md:col-span-2 xl:col-span-12"><RgrForestCard summary={s} q={rgr} /></div>
            <div className="md:col-span-2 xl:col-span-12"><ExportCard summary={s} /></div>
          </CardGrid>
        </div>
      )}
    </QueryState>
  )
}
