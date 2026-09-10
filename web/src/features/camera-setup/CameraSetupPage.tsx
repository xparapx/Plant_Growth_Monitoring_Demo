import { useState } from 'react'
import { useCameraStatus } from '@/api/queries'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { CameraTabs } from '@/features/capture/CameraTabs'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { CenterRoiPanel } from './CenterRoiPanel'
import { PreviewStage } from './PreviewStage'
import { SetupProvider } from './SetupContext'
import { useSetup } from './setupCtx'
import { SetupMessage } from './SetupMessage'
import { SetupStepper } from './SetupStepper'
import { SetupWarning } from './SetupWarning'
import { StatusJsonPanel } from './StatusJsonPanel'

export default function CameraSetupPage() {
  const q = useCameraStatus(true)
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-[18px] font-bold">{ko.setup.title}</h1>
        <CameraTabs />
      </header>
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
        {(s) => (
          <SetupProvider status={s}>
            <Layout />
          </SetupProvider>
        )}
      </QueryState>
    </div>
  )
}

function Layout() {
  const { mode } = useSetup()
  const mobile = useIsMobile()
  const [cm, setCm] = useState(5)
  const sticky = mobile && mode !== 'idle'
  return (
    <div className="flex flex-col gap-4 xl:grid xl:grid-cols-[340px_1fr] xl:items-start">
      <aside className="order-2 xl:order-1">
        <SetupStepper cm={cm} setCm={setCm} />
      </aside>
      <div className="order-1 flex flex-col gap-4 xl:order-2">
        <SetupWarning />
        <PreviewStage cm={cm} className={sticky ? 'stage-sticky' : ''} />
        <SetupMessage />
        <CenterRoiPanel />
        <StatusJsonPanel />
      </div>
    </div>
  )
}
