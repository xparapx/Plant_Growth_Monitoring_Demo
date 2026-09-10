import { useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { EnvKpiRow } from './EnvKpiRow'
import { NodeChipRow } from './NodeChipRow'
import { TreatConflictAlert } from './TreatConflictAlert'
import { ValidityCard } from './ValidityCard'
import { CanopySilhouettes } from './CanopySilhouettes'
import { SawtoothCard } from './SawtoothCard'
import { IrrigationCard } from './IrrigationCard'
import { WaterCard } from './WaterCard'

export function OverviewPage() {
  const q = useSummary()
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <CardGrid className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12">
          <TreatConflictAlert summary={s} />
          <EnvKpiRow summary={s} />
          <NodeChipRow summary={s} />
          <ValidityCard summary={s} />
          <CanopySilhouettes summary={s} />
          <SawtoothCard summary={s} />
          <IrrigationCard summary={s} />
          <WaterCard summary={s} />
        </CardGrid>
      )}
    </QueryState>
  )
}
