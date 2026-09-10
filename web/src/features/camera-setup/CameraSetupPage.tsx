import { useState } from 'react'
import { useCameraStatus } from '@/api/queries'
import { Button } from '@/components/ui/Button'
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

/** Mockup 3d: title + tabs + "저장 → config.json" on the right; preview (1fr) | step rail (320px). */
export default function CameraSetupPage() {
  const q = useCameraStatus(true)
  return (
    <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
      {(s) => (
        <SetupProvider status={s}>
          <Layout />
        </SetupProvider>
      )}
    </QueryState>
  )
}

function Layout() {
  const { mode, run, pending, disabled } = useSetup()
  const mobile = useIsMobile()
  const [cm, setCm] = useState(5)
  const [saved, setSaved] = useState(false)
  const sticky = mobile && mode !== 'idle'
  const save = async () => {
    const r = await run('save')
    if (r) { setSaved(true); window.setTimeout(() => setSaved(false), 1800) }
  }
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-[18px] font-semibold">{ko.setup.title}</h1>
        <CameraTabs />
        <Button variant="accent" onClick={save} busy={pending === 'save'} disabled={disabled} className="ml-auto">
          {saved ? ko.setup.saved : ko.setup.saveConfig}
        </Button>
      </header>
      <div className="flex flex-col gap-4 xl:grid xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start">
        <div className="order-1 flex flex-col gap-4">
          <SetupWarning />
          <PreviewStage cm={cm} className={sticky ? 'stage-sticky' : ''} />
          <SetupMessage />
          <CenterRoiPanel />
          <StatusJsonPanel />
        </div>
        <aside className="order-2">
          <SetupStepper cm={cm} setCm={setCm} />
        </aside>
      </div>
    </div>
  )
}
