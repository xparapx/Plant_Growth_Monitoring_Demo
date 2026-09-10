import { useAnalytics, useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { CanopySeriesCard } from './CanopySeriesCard'
import { ExportCard } from './ExportCard'
import { RgrForestCard } from './RgrForestCard'
import { RgrKpis } from './RgrKpis'

/** /growth — the outcome: canopy series, RGR per pot with CI, effect size, CSV export. */
export default function GrowthPage() {
  const q = useSummary()
  const rgr = useAnalytics('rgr')
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <CardGrid className="grid grid-cols-1 gap-4">
          <CanopySeriesCard summary={s} />
          <RgrKpis q={rgr} />
          <RgrForestCard summary={s} q={rgr} />
          <ExportCard summary={s} />
        </CardGrid>
      )}
    </QueryState>
  )
}
