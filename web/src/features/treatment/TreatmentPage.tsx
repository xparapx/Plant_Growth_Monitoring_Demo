import { useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { AlignTrendCard } from './AlignTrendCard'
import { BandSettingsCard } from './BandSettingsCard'
import { DroopCard } from './DroopCard'
import { HistogramCard } from './HistogramCard'
import { HowToReadExpander } from './HowToReadExpander'
import { TrajectoryCard } from './TrajectoryCard'
import { TreatKpiRow } from './TreatKpiRow'

/** Mockup 3b: KPI ×3 → (trajectory | band settings + distribution) → reference / alignment / droop. */
export default function TreatmentPage() {
  const q = useSummary()
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <CardGrid className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-12">
          <TreatKpiRow summary={s} />
          <TrajectoryCard summary={s} />
          <div className="flex flex-col gap-3.5 md:col-span-2 xl:col-span-4">
            <BandSettingsCard summary={s} />
            <HistogramCard summary={s} />
          </div>
          <HowToReadExpander />
          <AlignTrendCard summary={s} />
          <DroopCard summary={s} />
        </CardGrid>
      )}
    </QueryState>
  )
}
