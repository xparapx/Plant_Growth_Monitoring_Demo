import { useSummary } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { EnvKpiRow } from './EnvKpiRow'
import { NodeChipRow } from './NodeChipRow'
import { TreatConflictAlert } from './TreatConflictAlert'
import { SoilBandCard } from './SoilBandCard'
import { TreatmentCheckCard } from './TreatmentCheckCard'
import { PumpEventsCard } from './PumpEventsCard'
import { CanopySilhouettes } from './CanopySilhouettes'
import { SawtoothCard } from './SawtoothCard'
import { IrrigationCard } from './IrrigationCard'
import { WaterCard } from './WaterCard'
import { CaptureLogCard } from './CaptureLogCard'

/** Mockup 3a: gauges → (soil band | treatment check + pump events) → the 3a fillers (관수 기록 · 촬영 일지) and detail cards. */
export function OverviewPage() {
  const q = useSummary()
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <CardGrid className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-12">
          <TreatConflictAlert summary={s} />
          <EnvKpiRow summary={s} />
          <SoilBandCard summary={s} />
          <div className="flex flex-col gap-3.5 md:col-span-2 xl:col-span-4">
            <TreatmentCheckCard summary={s} />
            <PumpEventsCard summary={s} />
          </div>
          <NodeChipRow summary={s} />
          <CanopySilhouettes summary={s} />
          <SawtoothCard summary={s} />
          <IrrigationCard summary={s} />
          <WaterCard summary={s} />
          <CaptureLogCard />
        </CardGrid>
      )}
    </QueryState>
  )
}
