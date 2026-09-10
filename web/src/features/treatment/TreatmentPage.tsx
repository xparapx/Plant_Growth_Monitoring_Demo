import { useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { AlignTrendCard } from './AlignTrendCard'
import { DroopCard } from './DroopCard'
import { HistogramCard } from './HistogramCard'
import { HowToReadExpander } from './HowToReadExpander'

/** /treatment — is the treatment doing what it claims? (measured ρ(w), reference curves, alignment, droop). */
export default function TreatmentPage() {
  const q = useSummary()
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <CardGrid className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <HistogramCard summary={s} />
          <HowToReadExpander />
          <AlignTrendCard summary={s} />
          <DroopCard summary={s} />
        </CardGrid>
      )}
    </QueryState>
  )
}
